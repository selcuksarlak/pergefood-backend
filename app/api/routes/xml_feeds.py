"""
XML Feed Integration API Routes
CRUD for XMLFeedConfig + manual sync trigger + sync logs
"""

import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.xml_feed import XMLFeedConfig, XMLSyncLog
from app.services.xml_service import XMLSyncService

router = APIRouter(prefix="/xml-feeds", tags=["XML Feed Integration"])


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class XMLFeedCreate(BaseModel):
    name: str
    feed_type: str = "product_list"
    url: str
    custom_param: Optional[str] = None
    sync_interval_minutes: int = 60
    field_mapping: Optional[dict] = None
    root_element: str = "products"
    item_element: str = "product"
    download_images: bool = True
    image_save_dir: str = "static/product_images"


class XMLFeedUpdate(BaseModel):
    name: Optional[str] = None
    feed_type: Optional[str] = None
    url: Optional[str] = None
    custom_param: Optional[str] = None
    sync_interval_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    field_mapping: Optional[dict] = None
    root_element: Optional[str] = None
    item_element: Optional[str] = None
    download_images: Optional[bool] = None


# ─── Feed config CRUD ─────────────────────────────────────────────────────────

@router.get("/")
def list_feeds(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    feeds = db.query(XMLFeedConfig).order_by(XMLFeedConfig.id.desc()).all()
    return [_feed_dict(f) for f in feeds]


@router.post("/")
def create_feed(body: XMLFeedCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    feed = XMLFeedConfig(**body.model_dump())
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return _feed_dict(feed)


@router.get("/{feed_id}")
def get_feed(feed_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    feed = _get_or_404(db, feed_id)
    return _feed_dict(feed)


@router.put("/{feed_id}")
def update_feed(feed_id: int, body: XMLFeedUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    feed = _get_or_404(db, feed_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(feed, field, value)
    db.commit()
    db.refresh(feed)
    return _feed_dict(feed)


@router.delete("/{feed_id}")
def delete_feed(feed_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    feed = _get_or_404(db, feed_id)
    db.delete(feed)
    db.commit()
    return {"detail": "Feed deleted"}


# ─── Manual sync trigger ──────────────────────────────────────────────────────

@router.post("/{feed_id}/sync")
def trigger_sync(
    feed_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Trigger an immediate sync for this feed (runs in background)."""
    _get_or_404(db, feed_id)
    background_tasks.add_task(_run_sync_task, feed_id)
    return {"detail": "Sync started in background", "feed_id": feed_id}


@router.post("/{feed_id}/sync-now")
def sync_now(feed_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Synchronous sync — waits for result and returns log immediately."""
    _get_or_404(db, feed_id)
    service = XMLSyncService(db)
    log = service.run_sync(feed_id)
    return _log_dict(log)


# ─── Sync logs ────────────────────────────────────────────────────────────────

@router.get("/{feed_id}/logs")
def get_logs(
    feed_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _get_or_404(db, feed_id)
    logs = (
        db.query(XMLSyncLog)
        .filter(XMLSyncLog.feed_config_id == feed_id)
        .order_by(XMLSyncLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_log_dict(l) for l in logs]


@router.get("/logs/all")
def all_logs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregated sync logs across all feeds (for dashboard)."""
    logs = db.query(XMLSyncLog).order_by(XMLSyncLog.id.desc()).limit(limit).all()
    return [_log_dict(l) for l in logs]


@router.get("/logs/dashboard")
def sync_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Dashboard summary: per-feed last sync + aggregated totals."""
    feeds = db.query(XMLFeedConfig).all()
    result = []
    for f in feeds:
        last_log = (
            db.query(XMLSyncLog)
            .filter(XMLSyncLog.feed_config_id == f.id)
            .order_by(XMLSyncLog.id.desc())
            .first()
        )
        result.append({
            "feed_id": f.id,
            "feed_name": f.name,
            "feed_type": f.feed_type,
            "is_active": f.is_active,
            "sync_interval_minutes": f.sync_interval_minutes,
            "last_sync_at": f.last_sync_at.isoformat() if f.last_sync_at else None,
            "last_sync_status": f.last_sync_status,
            "last_log": _log_dict(last_log) if last_log else None,
        })
    return result


# ─── Default field mapping info ───────────────────────────────────────────────

@router.get("/mapping/defaults")
def default_mappings(_: User = Depends(get_current_user)):
    """Return the built-in default field mapping for reference."""
    from app.services.xml_service import DEFAULT_FIELD_MAPPING
    return DEFAULT_FIELD_MAPPING


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, feed_id: int) -> XMLFeedConfig:
    feed = db.query(XMLFeedConfig).filter(XMLFeedConfig.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return feed


def _feed_dict(f: XMLFeedConfig) -> dict:
    return {
        "id": f.id,
        "name": f.name,
        "feed_type": f.feed_type,
        "url": f.url,
        "custom_param": f.custom_param,
        "is_active": f.is_active,
        "sync_interval_minutes": f.sync_interval_minutes,
        "field_mapping": f.field_mapping,
        "root_element": f.root_element,
        "item_element": f.item_element,
        "download_images": f.download_images,
        "last_sync_at": f.last_sync_at.isoformat() if f.last_sync_at else None,
        "last_sync_status": f.last_sync_status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _log_dict(log: XMLSyncLog) -> dict:
    errors = []
    if log.error_detail:
        try:
            errors = json.loads(log.error_detail)
        except Exception:
            errors = [{"raw": log.error_detail}]
    return {
        "id": log.id,
        "feed_config_id": log.feed_config_id,
        "status": log.status,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "finished_at": log.finished_at.isoformat() if log.finished_at else None,
        "products_fetched": log.products_fetched,
        "products_created": log.products_created,
        "products_updated": log.products_updated,
        "products_skipped": log.products_skipped,
        "products_flagged": log.products_flagged,
        "images_downloaded": log.images_downloaded,
        "error_count": log.error_count,
        "errors": errors,
        "raw_url": log.raw_url,
    }


def _run_sync_task(feed_id: int):
    """Background task — creates its own DB session."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        service = XMLSyncService(db)
        service.run_sync(feed_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Background sync error: %s", exc)
    finally:
        db.close()
