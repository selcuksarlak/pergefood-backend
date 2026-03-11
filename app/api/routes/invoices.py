import os
import io
import re
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from app.core.database import get_db
from app.core.security import require_role
from app.models.supplier import Invoice, InvoiceItem, Supplier
from app.models.product import Product
from app.models.stock import StockEntry
from app.models.user import User

router = APIRouter(prefix="/invoices", tags=["Fatura İşleme (PDF/OCR)"])

UPLOADS_DIR = "uploads/invoices"
os.makedirs(UPLOADS_DIR, exist_ok=True)


class InvoiceItemResponse(BaseModel):
    id: int
    raw_product_name: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    match_status: str
    match_score: Optional[float]
    product_id: Optional[int]

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: Optional[str]
    processing_status: str
    total_amount: Optional[Decimal]
    pdf_path: Optional[str]
    invoice_items: List[InvoiceItemResponse] = []

    class Config:
        from_attributes = True


def _extract_text_from_pdf(pdf_path: str) -> list[str]:
    """Extract rows of text from PDF using PyMuPDF with layout awareness."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        rows = []
        for page in doc:
            # get_text("words") returns list of (x0, y0, x1, y1, "word", block_no, line_no, word_no)
            words = page.get_text("words")
            # Group words by Y-coordinates (with a small tolerance)
            y_groups = {}
            for w in words:
                y = round(w[1], 1)  # Use y0 coordinate
                if y not in y_groups:
                    y_groups[y] = []
                y_groups[y].append(w)
            
            # Sort words in each row by X-coordinate and join
            sorted_y = sorted(y_groups.keys())
            for y in sorted_y:
                line_words = sorted(y_groups[y], key=lambda x: x[0])
                line_text = " ".join(w[4] for w in line_words)
                rows.append(line_text)
        doc.close()
        return rows
    except Exception:
        return []


def _ocr_pdf(pdf_path: str) -> str:
    """Fallback OCR using Tesseract if text extraction fails."""
    try:
        import fitz
        from PIL import Image
        import pytesseract
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            full_text += pytesseract.image_to_string(img, lang="tur+eng")
        doc.close()
        return full_text
    except Exception as e:
        return f"OCR Error: {str(e)}"


BLACKLIST = {"mah", "sk", "no", "iban", "tr", "vergi", "telefon", "banka", "adres", "tel:", "fax:", "mersis", "ticaret"}

def _parse_invoice_text(rows: list[str]) -> dict:
    """Improved parsing with blacklist and row validation logic."""
    result = {
        "invoice_number": None,
        "lines": []
    }
    
    # Common invoice number patterns
    inv_patterns = [
        r"(Fatura No|Invoice No|Invoice #|Fatura Numarası)[:\s#]*([A-Z0-9\-/]+)",
        r"(Sıra No)[:\s#]*([A-Z0-9\-/]+)"
    ]

    for line in rows:
        # Check blacklist
        lower_line = line.lower()
        if any(word in lower_line for word in BLACKLIST):
            continue

        # Look for invoice number if not found yet
        if not result["invoice_number"]:
            for pattern in inv_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    result["invoice_number"] = match.group(2).strip()
                    break

        # Extract numbers - handle Turkish and English decimal separators
        parts = line.split()
        # Regex to find numbers that look like prices or quantities
        num_pattern = r"^\d+([.,]\d+)?$"
        nums = [p for p in parts if re.match(num_pattern, p)]
        
        # Heuristic for product row:
        # 1. Product name (words)
        # 2. Quantity
        # 3. Unit price
        # 4. Total price
        # Rule: At least 2 of these fields must exist.
        
        # Try to identify potential quantity and prices
        # Usually: QTY is first num, TOTAL is last num, UNIT is penultimate num
        if len(nums) >= 1:
            try:
                # Basic product name extraction (parts that aren't numeric)
                product_name = " ".join(p for p in parts if not re.match(num_pattern, p)).strip()
                
                # Check for at least 2 fields
                fields_found = 0
                if product_name: fields_found += 1
                
                qty = None
                unit_price = None
                total = None

                if len(nums) >= 1:
                    # If we only have 1 number, it's hard to tell if it's qty or total
                    # But if we have a name and 1 number, that's 2 fields.
                    try:
                        val = float(nums[0].replace(",", "."))
                        if val > 0:
                            qty = val
                            fields_found += 1
                    except: pass

                if len(nums) >= 2:
                    try:
                        total_val = float(nums[-1].replace(",", "."))
                        if total_val > 0:
                            total = total_val
                            fields_found += 1
                    except: pass
                
                if len(nums) >= 3:
                     try:
                        unit_val = float(nums[-2].replace(",", "."))
                        if unit_val > 0:
                            unit_price = unit_val
                            fields_found += 1
                     except: pass

                if fields_found >= 2 and product_name:
                    result["lines"].append({
                        "raw_product_name": product_name[:300],
                        "quantity": qty or 0,
                        "unit_price": unit_price or 0,
                        "total_price": total or 0,
                    })
            except Exception:
                continue
    return result


def _fuzzy_match_product(db: Session, name: str) -> tuple[Optional[Product], float]:
    """Use fuzzy string matching to find the closest product in the database."""
    try:
        from thefuzz import fuzz
        products = db.query(Product).filter(Product.active_status == True).all()
        best_score = 0
        best_product = None
        for product in products:
            score = fuzz.token_sort_ratio(name.lower(), product.product_name.lower())
            if score > best_score:
                best_score = score
                best_product = product
        return best_product, best_score / 100.0
    except ImportError:
        return None, 0.0


@router.post("/upload", response_model=InvoiceResponse, status_code=201)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse", "finance"))
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyaları yüklenebilir")

    # Save file
    file_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create invoice record
    invoice = Invoice(pdf_path=file_path, processing_status="processing")
    db.add(invoice)
    db.flush()

    # Extract text with coordinate awareness
    rows = _extract_text_from_pdf(file_path)
    if not rows or (len(rows) < 3):
        # Fallback to OCR if PyMuPDF returns nothing or very little
        text_raw = _ocr_pdf(file_path)
        rows = text_raw.splitlines()

    invoice.raw_ocr_text = "\n".join(rows) if isinstance(rows, list) else str(rows)
    parsed = _parse_invoice_text(rows if isinstance(rows, list) else str(rows).splitlines())
    invoice.invoice_number = parsed["invoice_number"]

    # Process lines
    total = Decimal("0")
    for line in parsed["lines"]:
        matched_product, score = _fuzzy_match_product(db, line["raw_product_name"])
        # Threshold 70% (0.7)
        status = "matched" if score >= 0.70 else ("unmatched" if score < 0.4 else "new_suggestion")
        item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=matched_product.id if matched_product and score >= 0.70 else None,
            raw_product_name=line["raw_product_name"],
            quantity=Decimal(str(line["quantity"])),
            unit_price=Decimal(str(line["unit_price"])),
            total_price=Decimal(str(line["total_price"])),
            match_score=score,
            match_status=status,
        )
        db.add(item)
        total += Decimal(str(line["total_price"]))

        # Auto-create stock entry ONLY for high-confidence matches AND validated fields
        if matched_product and score >= 0.70 and line["quantity"] > 0:
            stock_entry = StockEntry(
                product_id=matched_product.id,
                quantity=Decimal(str(line["quantity"])),
                unit_cost=Decimal(str(line["unit_price"])),
                invoice_id=invoice.id,
                notes=f"PDF fatura otomatik girişi: {file.filename}",
            )
            db.add(stock_entry)
            # Update stock level
            from app.models.stock import StockLevel
            level = db.query(StockLevel).filter(StockLevel.product_id == matched_product.id).first()
            if level:
                level.current_stock = Decimal(str(level.current_stock)) + Decimal(str(line["quantity"]))
            else:
                new_level = StockLevel(product_id=matched_product.id, current_stock=Decimal(str(line["quantity"])))
                db.add(new_level)

    invoice.total_amount = total
    invoice.processing_status = "done"
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/items/{item_id}/match", response_model=InvoiceItemResponse)
def match_invoice_item(
    invoice_id: int,
    item_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    """Manually link an invoice item to a product and update stock."""
    item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fatura kalemi bulunamadı")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    # Validation
    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail="Miktar sıfırdan büyük olmalıdır")

    item.product_id = product_id
    item.match_status = "matched"
    item.match_score = 1.0

    # Create stock entry
    stock_entry = StockEntry(
        product_id=product_id,
        quantity=item.quantity,
        unit_cost=item.unit_price,
        invoice_id=invoice_id,
        notes=f"Manuel fatura eşleme girişi (Kalem ID: {item_id})",
    )
    db.add(stock_entry)

    # Update stock level
    from app.models.stock import StockLevel
    level = db.query(StockLevel).filter(StockLevel.product_id == product_id).first()
    if level:
        level.current_stock += item.quantity
    else:
        new_level = StockLevel(product_id=product_id, current_stock=item.quantity)
        db.add(new_level)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{invoice_id}/items/{item_id}")
def delete_invoice_item(
    invoice_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    """Delete or ignore an invoice line."""
    item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fatura kalemi bulunamadı")
    
    db.delete(item)
    db.commit()
    return {"detail": "Kalem silindi"}
