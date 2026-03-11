from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel
from decimal import Decimal
from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.product import Product, ProductCost, UnitType
from app.models.stock import StockLevel
from app.api.routes.stock import StockLevelResponse
from app.models.user import User

router = APIRouter(prefix="/products", tags=["Ürün Yönetimi"])


# --- Schemas ---
class ProductCostCreate(BaseModel):
    raw_material: Decimal = Decimal("0")
    packaging: Decimal = Decimal("0")
    labor: Decimal = Decimal("0")
    energy: Decimal = Decimal("0")
    transport: Decimal = Decimal("0")
    storage: Decimal = Decimal("0")
    distribution: Decimal = Decimal("0")
    other: Decimal = Decimal("0")
    profit_margin: Decimal = Decimal("35")
    notes: Optional[str] = None


class ProductCreate(BaseModel):
    product_name: str
    category_id: int
    brand_id: Optional[int] = None
    product_code: str
    barcode: Optional[str] = None
    unit_type: UnitType = UnitType.adet
    package_size: Optional[float] = None
    
    # Yeni Fiyatlandırma Alanları
    purchase_price: Decimal = Decimal("0")
    profit_margin_percent: Decimal = Decimal("35")
    manual_profit: Decimal = Decimal("0")
    shipping_cost: Decimal = Decimal("0")
    
    cost: Optional[ProductCostCreate] = None


class BulkMarginUpdate(BaseModel):
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    apply_manual: bool = False
    manual_stock_margin: Optional[Decimal] = None
    apply_xml: bool = False
    xml_stock_margin: Optional[Decimal] = None


class ProductDropdownResponse(BaseModel):
    id: int
    product_name: str

    class Config:
        from_attributes = True
    unit_type: UnitType

    class Config:
        from_attributes = True


class ProductCostResponse(BaseModel):
    id: int
    raw_material: Decimal
    packaging: Decimal
    labor: Decimal
    energy: Decimal
    transport: Decimal
    storage: Decimal
    distribution: Decimal
    other: Decimal
    real_cost: Decimal
    profit_margin: Decimal
    calculated_price: Decimal
    notes: Optional[str]

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class BrandResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    id: int
    product_name: str
    category_id: Optional[int]
    brand_id: Optional[int]
    category: Optional[CategoryResponse]
    brand: Optional[BrandResponse]
    product_code: str
    barcode: Optional[str]
    unit_type: UnitType
    package_size: Optional[float]
    active_status: bool
    
    # Yeni Fiyatlandırma Alanları
    purchase_price: Decimal
    profit_margin_percent: Decimal
    manual_profit: Decimal
    shipping_cost: Decimal
    calculated_sale_price: Decimal
    is_xml_price: bool
    stock_level: Optional[StockLevelResponse] = None
    
    costs: List[ProductCostResponse] = []

    class Config:
        from_attributes = True


def _calc_cost(cost_data: ProductCostCreate) -> tuple[Decimal, Decimal]:
    """Calculate real_cost and calculated_price from cost components."""
    real_cost = (
        cost_data.raw_material + cost_data.packaging + cost_data.labor +
        cost_data.energy + cost_data.transport + cost_data.storage +
        cost_data.distribution + cost_data.other
    )
    # New Margin-on-Sales formula: CalculatedPrice = RealCost / (1 - Margin/100)
    margin_decimal = cost_data.profit_margin / 100
    if margin_decimal >= 1:
        margin_decimal = Decimal("0.999")  # Prevent division by zero
    
    calculated_price = real_cost / (1 - margin_decimal)
    return real_cost, calculated_price


def _calc_sale_price(purchase: Decimal, margin: Decimal, manual: Decimal, shipping: Decimal) -> Decimal:
    """
    FinalPrice = (PurchasePrice + ManualProfit + ShippingCost) / (1 - ProfitMarginPercent/100)
    """
    margin_decimal = margin / 100
    if margin_decimal >= 1:
        margin_decimal = Decimal("0.999")
        
    return (purchase + manual + shipping) / (1 - margin_decimal)


# --- Endpoints ---
@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "finance"))
):
    existing = db.query(Product).filter(Product.product_code == data.product_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu ürün kodu zaten mevcut")

    calc_sale_price = _calc_sale_price(
        data.purchase_price, data.profit_margin_percent, data.manual_profit, data.shipping_cost
    )

    product = Product(
        product_name=data.product_name,
        category_id=data.category_id,
        brand_id=data.brand_id,
        product_code=data.product_code,
        barcode=data.barcode,
        unit_type=data.unit_type,
        package_size=data.package_size,
        purchase_price=data.purchase_price,
        profit_margin_percent=data.profit_margin_percent,
        manual_profit=data.manual_profit,
        shipping_cost=data.shipping_cost,
        calculated_sale_price=calc_sale_price,
    )
    db.add(product)
    db.flush()

    # Create initial stock level entry
    stock_level = StockLevel(product_id=product.id, current_stock=0, minimum_stock_level=10)
    db.add(stock_level)

    # Create cost entry if provided
    if data.cost:
        real_cost, calc_price = _calc_cost(data.cost)
        cost = ProductCost(
            product_id=product.id,
            **data.cost.model_dump(exclude={"notes"}),
            notes=data.cost.notes,
            real_cost=real_cost,
            calculated_price=calc_price,
        )
        db.add(cost)

    db.commit()
    db.refresh(product)
    return product


@router.get("/", response_model=List[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = Query(None),
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    q = db.query(Product).options(
        selectinload(Product.category),
        selectinload(Product.brand),
        selectinload(Product.stock_entries),
        selectinload(Product.costs),
        selectinload(Product.stock_level)
    )
    if active_only:
        q = q.filter(Product.active_status == True)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    return q.order_by(Product.id.desc()).offset(skip).limit(limit).all()


@router.get("/dropdown", response_model=List[ProductDropdownResponse])
def get_products_dropdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ultra fast lightweight endpoint returning exclusively IDs and Names for standard <select> elements.
    Bypasses deep relationship nesting and calculation loops.
    """
    return db.query(Product).filter(Product.active_status == True).order_by(Product.id.desc()).all()


@router.post("/bulk-margins")
def bulk_update_margins(
    payload: BulkMarginUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    query = db.query(Product).filter(Product.active_status == True).options(
        selectinload(Product.stock_entries)
    )
    
    if payload.category_id:
        query = query.filter(Product.category_id == payload.category_id)
        
    if payload.brand_id:
        query = query.filter(Product.brand_id == payload.brand_id)
        
    products = query.all()
    updated_count = 0
    
    for product in products:
        # Check if the product has only XML price (no invoiced stock)
        is_web_product = product.is_xml_price
        
        updated = False
        if is_web_product and payload.apply_xml and payload.xml_stock_margin is not None:
            product.profit_margin_percent = payload.xml_stock_margin
            updated = True
            
        elif not is_web_product and payload.apply_manual and payload.manual_stock_margin is not None:
            product.profit_margin_percent = payload.manual_stock_margin
            updated = True
            
        if updated:
            product.calculated_sale_price = _calc_sale_price(
                product.purchase_price, 
                product.profit_margin_percent, 
                product.manual_profit, 
                product.shipping_cost
            )
            updated_count += 1
            
    db.commit()
    return {"detail": f"{updated_count} adet ürünün satış fiyatı güncellendi", "updated_count": updated_count}


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "finance"))
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    update_data = data.model_dump(exclude={"cost"})
    
    # Recalculate sale price
    purchase = update_data.get("purchase_price", product.purchase_price)
    margin = update_data.get("profit_margin_percent", product.profit_margin_percent)
    manual = update_data.get("manual_profit", product.manual_profit)
    shipping = update_data.get("shipping_cost", product.shipping_cost)
    
    update_data["calculated_sale_price"] = _calc_sale_price(
        Decimal(str(purchase)), Decimal(str(margin)), Decimal(str(manual)), Decimal(str(shipping))
    )

    for field, value in update_data.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/costs", response_model=ProductCostResponse, status_code=201)
def add_product_cost(
    product_id: int,
    cost_data: ProductCostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "finance"))
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    real_cost, calc_price = _calc_cost(cost_data)
    cost = ProductCost(
        product_id=product_id,
        **cost_data.model_dump(exclude={"notes"}),
        notes=cost_data.notes,
        real_cost=real_cost,
        calculated_price=calc_price,
    )
    db.add(cost)
    db.commit()
    db.refresh(cost)
    return cost


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    product.active_status = False  # soft delete
    db.commit()
    return {"detail": "Ürün devre dışı bırakıldı"}
