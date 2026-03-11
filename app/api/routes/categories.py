from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import requests
import xml.etree.ElementTree as ET

from app.core.database import get_db
from app.models.brand_category import Category
from app.core.security import get_current_active_user, require_role

router = APIRouter(prefix="/categories", tags=["Kategoriler"])

@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()

@router.delete("/all")
def delete_all_categories(db: Session = Depends(get_db), current_user = Depends(require_role("admin"))):
    try:
        db.query(Category).delete()
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
def sync_categories(db: Session = Depends(get_db), current_user = Depends(require_role("admin", "manager"))):
    url = "https://www.pergefood.com/xml.php?custom=KategoriXML"
    try:
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        res.encoding = "utf-8"
        
        root = ET.fromstring(res.text)
        added = 0
        
        # Expected: <Categories><Category_Tree><![CDATA[Category Name]]></Category_Tree></Categories>
        # Extract unique names first to prevent duplicate key errors during loop
        unique_names = set()
        for cat_el in root.findall('.//Category_Tree'):
            name = cat_el.text
            if name:
                name = name.strip()
                if name:
                    unique_names.add(name)

        for name in unique_names:
            existing = db.query(Category).filter(Category.name == name).first()
            if not existing:
                db.add(Category(name=name))
                added += 1
                        
        db.commit()
        return {"status": "success", "added": added}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kategori senkronizasyon hatası: {str(e)}")
