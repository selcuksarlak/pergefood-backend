"""
Stock XML Sync API
- Manual & scheduled sync endpoints
- Alert management (list / acknowledge)
- Dashboard summary
"""

import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.stock_sync import StockSyncLog, StockSyncItemLog, StockSyncAlert
from app.models.stock import StockLevel
from app.models.product import Product
from app.services.stock_xml_service import StockXMLSyncService

router = APIRouter(prefix="/stock-xml-sync", tags=["Stock XML Sync"])

DEFAULT_URL = "https://www.pergefood.com/xml.php?custom=OrnekXML"


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    url: str = DEFAULT_URL
    item_element: str = "product"
    extra_mapping: Optional[dict] = None
    create_missing: bool = False


# ─── Sync endpoints ───────────────────────────────────────────────────────────

@router.post("/sync-now")
def sync_now(
    body: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run stock sync immediately and wait for results."""
    svc = StockXMLSyncService(db)
    log = svc.run_sync(
        url=body.url,
        item_element=body.item_element,
        extra_mapping=body.extra_mapping,
        create_missing=body.create_missing,
    )
    return _log_dict(log)


@router.post("/sync")
def sync_background(
    body: SyncRequest = SyncRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run stock sync in background (returns immediately)."""
    background_tasks.add_task(_bg_sync, body.url, body.item_element, body.extra_mapping, body.create_missing)
    return {"detail": "Stock sync started in background", "url": body.url}


# ─── Logs ────────────────────────────────────────────────────────────────────

@router.get("/logs")
def list_logs(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    logs = db.query(StockSyncLog).order_by(StockSyncLog.id.desc()).limit(limit).all()
    return [_log_dict(log) for log in logs]


@router.get("/logs/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    log = db.query(StockSyncLog).filter(StockSyncLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return _log_detail(log, db)


@router.get("/logs/{log_id}/items")
def log_items(
    log_id: int,
    result_filter: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockSyncItemLog).filter(StockSyncItemLog.sync_log_id == log_id)
    if result_filter:
        q = q.filter(StockSyncItemLog.result == result_filter)
    items = q.order_by(StockSyncItemLog.id).limit(limit).all()
    return [_item_dict(i) for i in items]


# ─── Alerts ──────────────────────────────────────────────────────────────────

@router.get("/alerts")
def list_alerts(
    unacknowledged_only: bool = True,
    alert_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(StockSyncAlert)
    if unacknowledged_only:
        q = q.filter(StockSyncAlert.is_acknowledged == False)
    if alert_type:
        q = q.filter(StockSyncAlert.alert_type == alert_type)
    alerts = q.order_by(StockSyncAlert.id.desc()).limit(limit).all()
    return [_alert_dict(a, db) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import datetime, timezone
    alert = db.query(StockSyncAlert).filter(StockSyncAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Alert acknowledged"}


@router.post("/alerts/acknowledge-all")
def acknowledge_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    db.query(StockSyncAlert).filter(StockSyncAlert.is_acknowledged == False).update(
        {"is_acknowledged": True, "acknowledged_at": now}
    )
    db.commit()
    return {"detail": "All alerts acknowledged"}


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregated sync dashboard stats."""
    last_log = db.query(StockSyncLog).order_by(StockSyncLog.id.desc()).first()

    total_logs = db.query(func.count(StockSyncLog.id)).scalar() or 0
    total_updated = db.query(func.sum(StockSyncLog.products_updated)).scalar() or 0
    total_errors = db.query(func.sum(StockSyncLog.error_count)).scalar() or 0
    total_alerts = db.query(func.count(StockSyncAlert.id)).scalar() or 0
    unack_alerts = db.query(func.count(StockSyncAlert.id)).filter(StockSyncAlert.is_acknowledged == False).scalar() or 0

    # Low stock products right now
    low_stock = (
        db.query(StockLevel, Product)
        .join(Product, StockLevel.product_id == Product.id)
        .filter(
            StockLevel.current_stock < StockLevel.minimum_stock_level,
            Product.active_status == True,
        )
        .order_by(Product.id)
        .limit(10)
        .all()
    )

    # Recent alerts (last 5)
    recent_alerts = (
        db.query(StockSyncAlert)
        .filter(StockSyncAlert.is_acknowledged == False)
        .order_by(StockSyncAlert.id.desc())
        .order_by(StockSyncAlert.id.desc())
        .limit(5)
        .all()
    )

    return {
        "last_sync": _log_dict(last_log) if last_log else None,
        "total_sync_runs": total_logs,
        "total_products_updated": int(total_updated),
        "total_errors": int(total_errors),
        "total_alerts": int(total_alerts),
        "unacknowledged_alerts": int(unack_alerts),
        "low_stock_products": [
            {
                "product_id": p.id,
                "product_name": p.product_name,
                "product_code": p.product_code,
                "current_stock": float(sl.current_stock or 0),
                "minimum_stock_level": float(sl.minimum_stock_level or 0),
            }
            for sl, p in low_stock
        ],
        "recent_alerts": [_alert_dict(a, db) for a in recent_alerts],
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _log_dict(log: StockSyncLog) -> dict:
    if not log:
        return {}
    return {
        "id": log.id,
        "sync_date": log.sync_date.isoformat() if log.sync_date else None,
        "finished_at": log.finished_at.isoformat() if log.finished_at else None,
        "status": log.status,
        "source_url": log.source_url,
        "products_processed": log.products_processed,
        "products_updated": log.products_updated,
        "products_added": log.products_added,
        "products_skipped": log.products_skipped,
        "alerts_generated": log.alerts_generated,
        "error_count": log.error_count,
    }


def _log_detail(log: StockSyncLog, db: Session) -> dict:
    d = _log_dict(log)
    errors = []
    if log.errors:
        try:
            errors = json.loads(log.errors)
        except Exception:
            errors = [{"raw": log.errors}]
    d["errors"] = errors
    return d


def _item_dict(i: StockSyncItemLog) -> dict:
    return {
        "id": i.id,
        "product_id": i.product_id,
        "product_code": i.product_code,
        "product_name": i.product_name,
        "xml_stock": float(i.xml_stock) if i.xml_stock is not None else None,
        "prev_stock": float(i.prev_stock) if i.prev_stock is not None else None,
        "new_stock": float(i.new_stock) if i.new_stock is not None else None,
        "drop_pct": i.drop_pct,
        "result": i.result,
        "note": i.note,
    }


def _alert_dict(a: StockSyncAlert, db: Session) -> dict:
    product = db.query(Product).filter(Product.id == a.product_id).first()
    return {
        "id": a.id,
        "sync_log_id": a.sync_log_id,
        "product_id": a.product_id,
        "product_name": product.product_name if product else None,
        "product_code": product.product_code if product else None,
        "alert_type": a.alert_type,
        "alert_message": a.alert_message,
        "prev_stock": float(a.prev_stock) if a.prev_stock is not None else None,
        "current_stock": float(a.current_stock) if a.current_stock is not None else None,
        "minimum_stock": float(a.minimum_stock) if a.minimum_stock is not None else None,
        "drop_pct": a.drop_pct,
        "is_acknowledged": a.is_acknowledged,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _bg_sync(url: str, item_element: str, extra_mapping: Optional[dict], create_missing: bool):
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        StockXMLSyncService(db).run_sync(url=url, item_element=item_element, extra_mapping=extra_mapping, create_missing=create_missing)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("BG stock sync error: %s", exc)
    finally:
        db.close()
