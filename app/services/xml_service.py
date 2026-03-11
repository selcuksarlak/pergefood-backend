"""
XML Product Data Integration Engine — Core Service
Handles: fetch → parse → validate → match → upsert → image download
"""

import os
import json
import logging
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal
from thefuzz import fuzz

from sqlalchemy.orm import Session

from app.models.product import Product, ProductCost, UnitType
from app.models.brand_category import Brand, Category
from app.models.stock import StockEntry, StockLevel
from app.models.xml_feed import XMLFeedConfig, XMLSyncLog, XMLProductImage

logger = logging.getLogger(__name__)

# ─── Default field mapping (XML tag → internal field name) ────────────────────
DEFAULT_FIELD_MAPPING = {
    # English style
    "ProductName": "product_name",
    "ProductCode": "product_code",
    "Barcode": "barcode",
    "Category": "category",
    "StockQuantity": "stock_quantity",
    "Stock": "stock_quantity",
    "PurchasePrice": "purchase_price",
    "SalePrice": "sale_price",
    "Price": "sale_price",
    "Description": "description",
    "ImageURL": "image_url",
    "Image": "image_url",
    "ProductID": "external_id",
    "UnitType": "unit_type",
    # Turkish style
    "urun_adi": "product_name",
    "urun_kodu": "product_code",
    "barkod": "barcode",
    "kategori": "category",
    "stok": "stock_quantity",
    "stok_miktari": "stock_quantity",
    "fiyat": "sale_price",
    "alis_fiyati": "purchase_price",
    "satis_fiyati": "sale_price",
    "aciklama": "description",
    "resim": "image_url",
    "gorsel": "image_url",
}


class XMLSyncService:

    def __init__(self, db: Session):
        self.db = db
        self._product_cache = {}  # code -> Product
        self._stock_cache = {}    # product_id -> StockLevel
        self._barcode_cache = {}  # barcode -> Product
        self._category_cache = {} # name -> Category id
        self._brand_cache = {}    # name -> Brand id

    # ─── Public entry point ───────────────────────────────────────────────────

    def run_sync(self, feed_config_id: int) -> XMLSyncLog:
        """Fetch, parse and upsert products for given feed config. Returns sync log."""
        config = self.db.query(XMLFeedConfig).filter(XMLFeedConfig.id == feed_config_id).first()
        if not config:
            raise ValueError(f"XMLFeedConfig {feed_config_id} not found")

        log = XMLSyncLog(feed_config_id=config.id, status="running")
        self.db.add(log)
        self.db.flush()

        errors = []
        try:
            url = self._build_url(config)
            log.raw_url = url

            xml_text = self._fetch_xml(url)
            items = self._parse_xml(xml_text, config)
            log.products_fetched = len(items)

            mapping = self._resolve_mapping(config)

            for raw in items:
                # Use a savepoint for each item to handle failures gracefully without poison
                with self.db.begin_nested():
                    try:
                        data = self._apply_mapping(raw, mapping)
                        # DEBUG LOG
                        if log.products_created + log.products_updated + log.error_count < 5:
                            logger.info("Mapped data: %s", data)
                        
                        err = self._validate(data)
                        if err:
                            errors.append({"product": data.get("product_name", "?"), "error": err})
                            log.products_flagged += 1
                            continue

                        created = self._upsert_product(data)
                        if created:
                            log.products_created += 1
                        else:
                            log.products_updated += 1

                        if config.download_images and data.get("image_url"):
                            ok = self._download_image(data, config)
                            if ok:
                                log.images_downloaded += 1

                    except Exception as exc:
                        logger.warning("Error processing item: %s", exc)
                        errors.append({"product": str(raw.get("Name") or raw.get("ProductName", "?")), "error": str(exc)})
                        log.error_count += 1
                        # The 'with begin_nested' will automatically rollback the savepoint here

            log.status = "error" if log.error_count > 0 and log.products_created + log.products_updated == 0 else \
                         "partial" if log.error_count > 0 else "success"

        except Exception as exc:
            logger.error("XML sync failed: %s", exc)
            errors.append({"fatal": str(exc)})
            log.status = "error"
            log.error_count += 1

        log.error_detail = json.dumps(errors, ensure_ascii=False) if errors else None
        log.finished_at = datetime.now(timezone.utc)

        # Update config runtime fields
        config.last_sync_at = log.finished_at
        config.last_sync_status = log.status

        self.db.commit()
        return log

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _build_url(self, config: XMLFeedConfig) -> str:
        url = config.url.rstrip("?&")
        if config.custom_param:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}custom={config.custom_param}"
        return url

    def _fetch_xml(self, url: str, retries: int = 3, timeout: int = 15) -> str:
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, timeout=timeout, headers={"User-Agent": "PergefoodERP/1.0"})
                resp.raise_for_status()
                
                # The Pergefood XML server now returns UTF-8. We should trust the Content-Type header
                # or let requests auto-detect if not specified.
                if "charset=" in resp.headers.get("Content-Type", "").lower():
                    # If server explicitly specifies charset, respect it
                    pass
                else:
                    # Default to utf-8 if not specified, as confirmed by diagnostics
                    resp.encoding = "utf-8"
                
                return resp.text
            except Exception as exc:
                if attempt == retries:
                    raise RuntimeError(f"XML fetch failed after {retries} attempts: {exc}")
                logger.warning("Retry %d/%d for %s: %s", attempt, retries, url, exc)

    def _parse_xml(self, xml_text: str, config: XMLFeedConfig) -> list[dict]:
        """Parse XML and return list of raw tag→value dicts."""
        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError as exc:
            raise RuntimeError(f"Invalid XML: {exc}")

        item_tag = config.item_element or "product"
        # Try direct children first, then recursive search
        items = root.findall(item_tag)
        if not items:
            items = root.findall(f".//{item_tag}")

        result = []
        for node in items:
            row: dict = {}
            for child in node:
                row[child.tag] = (child.text or "").strip()
            if row:
                result.append(row)
        return result

    def _resolve_mapping(self, config: XMLFeedConfig) -> dict:
        """Merge config-specific mapping on top of defaults."""
        mapping = dict(DEFAULT_FIELD_MAPPING)
        if config.field_mapping and isinstance(config.field_mapping, dict):
            mapping.update(config.field_mapping)
        return mapping

    def _apply_mapping(self, raw: dict, mapping: dict) -> dict:
        """Translate XML field names to internal field names."""
        out: dict = {}
        for xml_key, value in raw.items():
            internal = mapping.get(xml_key, xml_key.lower())
            out[internal] = value
        return out

    def _validate(self, data: dict) -> Optional[str]:
        """Return error string if data is invalid, None if OK."""
        name = data.get("product_name", "").strip()
        if not name:
            return "Empty product_name"

        code = data.get("product_code", "").strip()
        if not code:
            return "Empty product_code"

        for price_field in ("purchase_price", "sale_price"):
            val = data.get(price_field)
            if val is not None and val != "":
                parsed = self._to_float(val)
                if parsed is None:
                    return f"Invalid {price_field}: {val}"
                if parsed < 0:
                    return f"Negative {price_field}: {val}"

        stock = data.get("stock_quantity")
        if stock is not None and stock != "":
            parsed = self._to_float(stock)
            if parsed is None:
                return f"Invalid stock_quantity: {stock}"
            if parsed < 0:
                return f"Negative stock_quantity: {stock}"

        return None

    def _upsert_product(self, data: dict) -> bool:
        """Create or update product + stock level. Returns True if created."""
        db = self.db

        product_code = data.get("product_code", "").strip()
        barcode = data.get("barcode", "").strip() or None
        product_name = data.get("product_name", "").strip()

        # Brand and Category Lookups
        category_name = data.get("category", "Genel").strip() or "Genel"
        brand_name = data.get("brand", "").strip() or data.get("mark", "").strip() or None
        
        category_id = self._get_or_create_category(category_name)
        brand_id = self._get_or_create_brand(brand_name) if brand_name else None

        # 1. Check local cache first
        product = self._product_cache.get(product_code)
        if not product and barcode:
            product = self._barcode_cache.get(barcode)

        # 2. Try match by product_code in DB
        if not product:
            product = db.query(Product).filter(Product.product_code == product_code).first()

        # 3. Try by barcode in DB
        if not product and barcode:
            product = db.query(Product).filter(Product.barcode == barcode).first()

        # 4. Fuzzy name match (threshold 85) - DISABLING TEMPORARILY TO PREVENT OVER-MATCHING
        # if not product:
        #     candidates = db.query(Product).filter(Product.active_status == True).all()
        #     best_score = 0
        #     for cand in candidates:
        #         score = fuzz.token_sort_ratio(product_name.lower(), cand.product_name.lower())
        #         if score > best_score:
        #             best_score = score
        #             if score >= 85:
        #                 product = cand
        
        created = product is None

        if created:
            product = Product(
                product_name=product_name,
                category_id=category_id,
                brand_id=brand_id,
                product_code=product_code,
                barcode=barcode,
                unit_type=UnitType.adet,
                active_status=True,
            )
            db.add(product)
            db.flush()  # get product.id
            logger.info("Created new product with ID %s", product.id)

        else:
            # Update mutable fields
            product.category_id = category_id
            if brand_id:
                product.brand_id = brand_id
            if barcode:
                product.barcode = barcode

        # Update cache
        self._product_cache[product_code] = product
        if barcode:
            self._barcode_cache[barcode] = product

        # Update Product pricing fields from XML
        purchase_price = self._to_float(data.get("purchase_price") or data.get("sale_price"))
        
        if purchase_price is not None:
            purchase_price_dec = Decimal(str(purchase_price))
            product.purchase_price = purchase_price_dec
            
            # Recalculate based on existing margin/manual/shipping if available
            margin = Decimal(str(product.profit_margin_percent))
            manual = Decimal(str(product.manual_profit))
            shipping = Decimal(str(product.shipping_cost))
            
            product.calculated_sale_price = purchase_price_dec + (purchase_price_dec * margin / 100) + manual + shipping

        # Update / create ProductCost from XML prices for legacy support/history
        if purchase_price is not None:
            # Always create a new cost snapshot for traceability
            existing_cost = db.query(ProductCost).filter(
                ProductCost.product_id == product.id
            ).order_by(ProductCost.id.desc()).first()

            margin_float = float(existing_cost.profit_margin) if existing_cost else 35.0
            sale_price = self._to_float(data.get("sale_price"))
            calc_price = sale_price if sale_price else purchase_price * (1 + margin_float / 100)

            new_cost = ProductCost(
                product_id=product.id,
                raw_material=purchase_price,
                real_cost=purchase_price,
                profit_margin=margin_float,
                calculated_price=calc_price,
                notes="Imported from XML feed",
            )
            db.add(new_cost)

        # Consolidated Stock Level Update (Fail-safe)
        stock_qty = self._to_float(data.get("stock_quantity"))
        if stock_qty is not None:
            level = self._stock_cache.get(product.id)
            
            if not level:
                # Check DB
                level = db.query(StockLevel).filter(StockLevel.product_id == product.id).first()
            
            if not level:
                # Last resort: check if any StockLevel in the session has this product_id
                # (SQLAlchemy 2.x session iteration)
                for obj in db:
                    if isinstance(obj, StockLevel) and getattr(obj, 'product_id', None) == product.id:
                        level = obj
                        break
            
            if level:
                level.current_stock = stock_qty
            else:
                level = StockLevel(
                    product_id=product.id, 
                    current_stock=stock_qty, 
                    minimum_stock_level=10
                )
                db.add(level)
            
            self._stock_cache[product.id] = level
            db.flush() # Ensure it has ID and is in identity map for next iterate
        return created

    def _download_image(self, data: dict, config: XMLFeedConfig) -> bool:
        """Download product image to local storage."""
        image_url = data.get("image_url", "").strip()
        if not image_url:
            return False

        save_dir = config.image_save_dir or "static/product_images"
        os.makedirs(save_dir, exist_ok=True)

        product_code = data.get("product_code", "unknown")
        ext = os.path.splitext(image_url.split("?")[0])[-1] or ".jpg"
        filename = hashlib.md5(image_url.encode()).hexdigest()[:12] + ext
        local_path = os.path.join(save_dir, filename)

        if os.path.exists(local_path):
            return True  # already downloaded

        try:
            resp = requests.get(image_url, timeout=10, stream=True)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # Find product
            product = self.db.query(Product).filter(
                Product.product_code == product_code
            ).first()
            if product:
                existing_imgs = self.db.query(XMLProductImage).filter(
                    XMLProductImage.product_id == product.id
                ).count()
                img = XMLProductImage(
                    product_id=product.id,
                    original_url=image_url,
                    local_path=local_path,
                    is_primary=(existing_imgs == 0),
                )
                self.db.add(img)
                self.db.flush()
            return True

        except Exception as exc:
            logger.warning("Image download failed %s: %s", image_url, exc)
            return False

    @staticmethod
    def _to_float(val) -> Optional[float]:
        if val is None or str(val).strip() == "":
            return None
        # Clean the value: remove spaces, handle Turkish thousands/decimal separators
        # Case 1: 5.350,00 -> 5350.00
        # Case 2: 5,350.00 -> 5350.00
        s = str(val).strip().replace(" ", "")
        
        # If there's both a dot and a comma
        if "." in s and "," in s:
            if s.find(".") < s.find(","): # 5.350,00
                s = s.replace(".", "").replace(",", ".")
            else: # 5,350.00
                s = s.replace(",", "")
        elif "," in s: # Only comma, e.g. 12,50 or 5.350
            # Heuristic: if comma is followed by exactly 2 digits, it's likely decimal
            parts = s.split(",")
            if len(parts[-1]) == 2:
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")
                
        try:
            return float(s)
        except ValueError:
            return None

    def _get_or_create_category(self, name: str) -> int:
        if name in self._category_cache:
            return self._category_cache[name]
            
        cat = self.db.query(Category).filter(Category.name == name).first()
        if not cat:
            cat = Category(name=name)
            self.db.add(cat)
            self.db.flush()
        
        self._category_cache[name] = cat.id
        return cat.id
        
    def _get_or_create_brand(self, name: str) -> int:
        if name in self._brand_cache:
            return self._brand_cache[name]
            
        brand = self.db.query(Brand).filter(Brand.name == name).first()
        if not brand:
            brand = Brand(name=name)
            self.db.add(brand)
            self.db.flush()
            
        self._brand_cache[name] = brand.id
        return brand.id
