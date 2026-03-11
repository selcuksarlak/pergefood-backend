"""
Stock XML Synchronization Engine — Core Service

Rules:
  - DatabaseStock = XMLStock  (hard overwrite)
  - Only updates existing products (does NOT create new ones)
  - Generates StockSyncAlert when stock drops > DROP_THRESHOLD % 
  - Generates restock recommendation when stock < minimum level
  - Retries on connection failure
"""

import json
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from thefuzz import fuzz

from app.models.product import Product
from app.models.stock import StockLevel
from app.models.stock_sync import StockSyncLog, StockSyncItemLog, StockSyncAlert

logger = logging.getLogger(__name__)

# Drop threshold — 30 % drop triggers an alert
DROP_THRESHOLD = 30.0

# Default XML tag → stock field mapping
STOCK_FIELD_HINTS = {
    # ProductCode identifiers
    "ProductCode": "product_code",
    "urun_kodu": "product_code",
    "product_code": "product_code",
    "Code": "product_code",
    "Kod": "product_code",
    # Barcode identifiers
    "Barcode": "barcode",
    "barkod": "barcode",
    "EAN": "barcode",
    "barcode": "barcode",
    # Name identifiers
    "ProductName": "product_name",
    "urun_adi": "product_name",
    "Name": "product_name",
    # Stock quantity
    "StockQuantity": "stock_quantity",
    "Stock": "stock_quantity",
    "stok": "stock_quantity",
    "stok_miktari": "stock_quantity",
    "Quantity": "stock_quantity",
    "Miktar": "stock_quantity",
    "Stok": "stock_quantity",
}


class StockXMLSyncService:

    def __init__(self, db: Session):
        self.db = db

    # ─── Public entry point ───────────────────────────────────────────────────

    def run_sync(
        self,
        url: str = "https://www.pergefood.com/xml.php?custom=OrnekXML",
        item_element: str = "product",
        extra_mapping: Optional[dict] = None,
        create_missing: bool = False,
    ) -> StockSyncLog:
        """
        Full stock sync cycle. Returns finished StockSyncLog.
        create_missing=False means skip products not in DB (stock-only mode).
        """
        log = StockSyncLog(source_url=url, status="running")
        self.db.add(log)
        self.db.flush()

        errors = []
        try:
            xml_text = self._fetch(url)
            items = self._parse(xml_text, item_element)
            log.products_processed = len(items)

            mapping = dict(STOCK_FIELD_HINTS)
            if extra_mapping:
                mapping.update(extra_mapping)

            for raw in items:
                data = self._map_fields(raw, mapping)
                result = self._process_item(data, log, create_missing)
                if result.get("error"):
                    errors.append(result["error"])

            log.status = (
                "error" if log.error_count > 0 and log.products_updated == 0
                else "partial" if log.error_count > 0
                else "success"
            )

        except Exception as exc:
            logger.error("Stock XML sync fatal: %s", exc)
            errors.append({"fatal": str(exc)})
            log.status = "error"
            log.error_count += 1

        log.errors = json.dumps(errors, ensure_ascii=False) if errors else None
        log.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        return log

    # ─── Per-item processing ─────────────────────────────────────────────────

    def _process_item(self, data: dict, log: StockSyncLog, create_missing: bool) -> dict:
        """Process one XML item. Updates stock, generates alerts. Returns result dict."""
        product_code = data.get("product_code", "").strip()
        barcode = data.get("barcode", "").strip()
        product_name = data.get("product_name", "").strip()
        raw_stock = data.get("stock_quantity")

        # Validate stock value
        xml_stock = self._to_float(raw_stock)
        if xml_stock is None or xml_stock < 0:
            item_log = StockSyncItemLog(
                sync_log_id=log.id,
                product_code=product_code or None,
                product_name=product_name or None,
                result="invalid",
                note=f"Invalid stock value: {raw_stock!r}",
            )
            self.db.add(item_log)
            log.products_skipped += 1
            log.error_count += 1
            self.db.flush()
            return {"error": {"code": product_code, "msg": f"Invalid stock: {raw_stock}"}}

        # Match product
        product = self._match_product(barcode, product_code, product_name)

        if not product:
            item_log = StockSyncItemLog(
                sync_log_id=log.id,
                product_code=product_code or None,
                product_name=product_name or None,
                xml_stock=xml_stock,
                result="not_found",
                note="No matching product in database",
            )
            self.db.add(item_log)
            log.products_skipped += 1
            self.db.flush()
            return {}

        # Get / create stock level
        level = self.db.query(StockLevel).filter(StockLevel.product_id == product.id).first()
        if not level:
            level = StockLevel(product_id=product.id, current_stock=0, minimum_stock_level=10)
            self.db.add(level)
            self.db.flush()

        prev_stock = float(level.current_stock or 0)
        drop_pct = self._drop_pct(prev_stock, xml_stock)

        # ── Hard overwrite rule ──
        level.current_stock = xml_stock
        self.db.flush()

        # Determine result label
        result_label = "updated"
        note = f"{prev_stock} → {xml_stock}"
        alerts_created = 0

        # Alert: drop > DROP_THRESHOLD
        if drop_pct <= -DROP_THRESHOLD and prev_stock > 0:
            alert = StockSyncAlert(
                sync_log_id=log.id,
                product_id=product.id,
                alert_type="drop_alert",
                alert_message=(
                    f"Stok %{abs(drop_pct):.1f} düştü: {prev_stock:.1f} → {xml_stock:.1f}"
                ),
                prev_stock=prev_stock,
                current_stock=xml_stock,
                minimum_stock=float(level.minimum_stock_level or 0),
                drop_pct=drop_pct,
            )
            self.db.add(alert)
            alerts_created += 1
            result_label = "alert"
            note += f" | DROP ALERT: {drop_pct:.1f}%"

        # Alert: below minimum
        min_level = float(level.minimum_stock_level or 0)
        if xml_stock < min_level:
            alert = StockSyncAlert(
                sync_log_id=log.id,
                product_id=product.id,
                alert_type="below_minimum" if xml_stock > 0 else "out_of_stock",
                alert_message=(
                    f"Stok minimum seviyenin altında: {xml_stock:.1f} < {min_level:.1f}"
                    if xml_stock > 0 else
                    f"Stok tükendi! (min: {min_level:.1f})"
                ),
                prev_stock=prev_stock,
                current_stock=xml_stock,
                minimum_stock=min_level,
                drop_pct=drop_pct,
            )
            self.db.add(alert)
            alerts_created += 1
            if result_label != "alert":
                result_label = "below_minimum"

        item_log = StockSyncItemLog(
            sync_log_id=log.id,
            product_id=product.id,
            product_code=product.product_code,
            product_name=product.product_name,
            xml_stock=xml_stock,
            prev_stock=prev_stock,
            new_stock=xml_stock,
            drop_pct=drop_pct,
            result=result_label,
            note=note,
        )
        self.db.add(item_log)
        self.db.flush()

        log.products_updated += 1
        log.alerts_generated += alerts_created

        return {}

    # ─── Product matching ─────────────────────────────────────────────────────

    def _match_product(self, barcode: str, product_code: str, product_name: str) -> Optional[Product]:
        db = self.db

        # 1. Barcode (highest priority)
        if barcode:
            p = db.query(Product).filter(Product.barcode == barcode, Product.active_status == True).first()
            if p:
                return p

        # 2. ProductCode
        if product_code:
            p = db.query(Product).filter(Product.product_code == product_code, Product.active_status == True).first()
            if p:
                return p

        # 3. Fuzzy product name (threshold 85)
        if product_name:
            candidates = db.query(Product).filter(Product.active_status == True).all()
            best: Optional[Product] = None
            best_score = 0
            for cand in candidates:
                score = fuzz.token_sort_ratio(product_name.lower(), cand.product_name.lower())
                if score > best_score:
                    best_score = score
                    best = cand
            if best_score >= 85:
                return best

        return None

    # ─── XML fetch & parse ────────────────────────────────────────────────────

    def _fetch(self, url: str, retries: int = 3, timeout: int = 15) -> str:
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, timeout=timeout, headers={"User-Agent": "PergefoodStockSync/1.0"})
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except Exception as exc:
                if attempt == retries:
                    raise RuntimeError(f"XML fetch failed after {retries} retries: {exc}")
                logger.warning("Retry %d/%d — %s: %s", attempt, retries, url, exc)

    def _parse(self, xml_text: str, item_element: str = "product") -> list[dict]:
        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError as exc:
            raise RuntimeError(f"Invalid XML: {exc}")

        items = root.findall(item_element) or root.findall(f".//{item_element}")
        result = []
        for node in items:
            row = {child.tag: (child.text or "").strip() for child in node}
            if row:
                result.append(row)
        return result

    def _map_fields(self, raw: dict, mapping: dict) -> dict:
        out: dict = {}
        for xml_key, value in raw.items():
            internal = mapping.get(xml_key, xml_key.lower())
            out[internal] = value
        return out

    # ─── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_float(val) -> Optional[float]:
        if val is None or str(val).strip() == "":
            return None
        try:
            return float(str(val).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _drop_pct(prev: float, new: float) -> float:
        if prev == 0:
            return 0.0
        return ((new - prev) / prev) * 100
