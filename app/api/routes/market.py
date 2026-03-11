import requests
import re
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from app.core.database import get_db
from app.core.security import require_role, get_current_active_user
from app.models.stock import MarketPrice
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/market", tags=["Piyasa Fiyat Takibi"])


class MarketPriceCreate(BaseModel):
    product_id: int
    competitor_name: str
    product_name_on_site: str
    competitor_price: Decimal
    website_source: str = ""


class MarketPriceResponse(BaseModel):
    id: int
    product_id: int
    competitor_name: str
    product_name_on_site: str
    competitor_price: Decimal
    website_source: str
    scraped_at: datetime

    class Config:
        from_attributes = True


class MarketAggResponse(BaseModel):
    product_id: int
    product_name: str
    avg_price: float
    min_price: float
    max_price: float
    entries: int


@router.post("/prices", response_model=MarketPriceResponse, status_code=201)
def add_market_price(
    data: MarketPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    """Manually add a competitor price entry."""
    mp = MarketPrice(**data.model_dump())
    db.add(mp)
    db.commit()
    db.refresh(mp)
    return mp


@router.get("/prices/{product_id}", response_model=List[MarketPriceResponse])
def get_market_prices(
    product_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    prices = (
        db.query(MarketPrice)
        .filter(MarketPrice.product_id == product_id)
        .order_by(MarketPrice.scraped_at.desc())
        .limit(limit)
        .all()
    )
    return prices


@router.get("/aggregate/{product_id}", response_model=MarketAggResponse)
def get_market_aggregate(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    prices = db.query(MarketPrice).filter(MarketPrice.product_id == product_id).all()
    if not prices:
        raise HTTPException(status_code=404, detail="Bu ürün için piyasa fiyatı verisi yok")
    values = [float(p.competitor_price) for p in prices]
    return {
        "product_id": product_id,
        "product_name": product.product_name,
        "avg_price": round(sum(values) / len(values), 2),
        "min_price": round(min(values), 2),
        "max_price": round(max(values), 2),
        "entries": len(values),
    }


@router.post("/scrape/{product_id}", status_code=202)
def trigger_scrape(
    product_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    """Trigger background web scraping for a product's competitor prices."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    background_tasks.add_task(_scrape_prices_task, product_id, product.product_name, db)
    return {"detail": f"'{product.product_name}' için fiyat tarama başlatıldı"}


def _scrape_prices_task(product_id: int, product_name: str, db: Session):
    """
    Background scraping task. Uses enhanced HTTP headers to bypass basic bot protection.
    """
    import time
    import random

    search_engines = [
        {
            "name": "Migros Online",
            "url": f"https://www.migros.com.tr/search?q={product_name.replace(' ', '+')}",
            "price_pattern": r'"price":\s*"?(\d+[\.,]\d+)"?',
        },
        {
            "name": "A101 Online",
            "url": f"https://www.a101.com.tr/search/?q={product_name.replace(' ', '+')}",
            "price_pattern": r'(\d+[,.]\d+)\s*TL',
        },
    ]

    base_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1"
    }

    for engine in search_engines:
        try:
            # Random delay to appear more human
            time.sleep(random.uniform(1, 3))
            
            response = requests.get(engine["url"], headers=base_headers, timeout=15)
            
            if response.status_code != 200:
                print(f"Scraping blocked for {engine['name']} (Status: {response.status_code})")
                continue

            matches = re.findall(engine["price_pattern"], response.text)
            added_count = 0
            for match in matches:
                if added_count >= 3:
                    break
                    
                price_str = match.replace(",", ".")
                try:
                    price = Decimal(price_str)
                    if 1.0 < price < 100000:
                        mp = MarketPrice(
                            product_id=product_id,
                            competitor_name=engine["name"],
                            product_name_on_site=product_name,
                            competitor_price=price,
                            website_source=engine["url"],
                            scraped_at=datetime.utcnow()
                        )
                        db.add(mp)
                        added_count += 1
                except Exception:
                    continue
            
            if added_count > 0:
                db.commit()
                print(f"Successfully scraped {added_count} prices from {engine['name']}")
            else:
                print(f"No matches found for {product_name} on {engine['name']}")
                
        except Exception as e:
            print(f"Scraping error for {engine['name']}: {e}")
            continue
