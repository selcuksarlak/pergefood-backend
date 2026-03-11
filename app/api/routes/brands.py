from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import requests
import xml.etree.ElementTree as ET

from app.core.database import get_db
from app.models.brand_category import Brand
from app.core.security import get_current_active_user, require_role

router = APIRouter(prefix="/brands", tags=["Markalar"])

@router.get("/")
def list_brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.name).all()

@router.delete("/all")
def delete_all_brands(db: Session = Depends(get_db), current_user = Depends(require_role("admin"))):
    try:
        db.query(Brand).delete()
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
def sync_brands(db: Session = Depends(get_db), current_user = Depends(require_role("admin", "manager"))):
    url = "https://www.pergefood.com/xml.php?custom=MarkaXML"
    try:
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        res.encoding = "utf-8"
        
        # Parse XML
        root = ET.fromstring(res.text)
        added = 0
        
        # Expected: <marks><mark><![CDATA[Brand Name]]></mark></marks>
        # Extract unique names first to prevent duplicate key errors during loop
        unique_names = set()
        for mark_el in root.findall('.//mark'):
            name = mark_el.text
            if name:
                name = name.strip()
                if name:
                    unique_names.add(name)

        for name in unique_names:
            existing = db.query(Brand).filter(Brand.name == name).first()
            if not existing:
                db.add(Brand(name=name))
                added += 1
                        
        db.commit()
        return {"status": "success", "added": added}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Marka senkronizasyon hatası: {str(e)}")
