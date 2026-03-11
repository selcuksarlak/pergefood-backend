from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
import app.models  # noqa: F401 — ensure all models are registered before create_all

from app.api.routes.auth import router as auth_router
from app.api.routes.products import router as products_router
from app.api.routes.stock import router as stock_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.invoices import router as invoices_router
from app.api.routes.ai_price import router as ai_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.market import router as market_router
from app.api.routes.xml_feeds import router as xml_router
from app.api.routes.stock_xml_sync import router as stock_xml_router
from app.api.routes.xml import router as xml_quick_router
from app.api.routes.shipping import router as shipping_router
from app.api.routes.offers import router as offers_router
from app.api.routes.brands import router as brands_router
from app.api.routes.categories import router as categories_router

logger = logging.getLogger(__name__)


def _start_scheduler():
    """Start APScheduler for periodic XML sync (if apscheduler is available)."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(timezone="Europe/Istanbul")

        def run_active_feeds():
            db = SessionLocal()
            try:
                from app.models.xml_feed import XMLFeedConfig
                from app.services.xml_service import XMLSyncService
                feeds = db.query(XMLFeedConfig).filter(XMLFeedConfig.is_active == True).all()
                for feed in feeds:
                    logger.info("Scheduled sync for feed: %s", feed.name)
                    try:
                        XMLSyncService(db).run_sync(feed.id)
                    except Exception as exc:
                        logger.error("Scheduled sync error (feed %d): %s", feed.id, exc)
            finally:
                db.close()

        # Check every 30 minutes; each feed's own interval is respected inside service
        scheduler.add_job(run_active_feeds, "interval", minutes=30, id="xml_feed_sync")
        def run_stock_xml_sync():
            db2 = SessionLocal()
            try:
                from app.services.stock_xml_service import StockXMLSyncService
                StockXMLSyncService(db2).run_sync()
            except Exception as exc:
                logger.error("Scheduled stock sync error: %s", exc)
            finally:
                db2.close()

        # Stock XML sync every 30 minutes
        scheduler.add_job(run_stock_xml_sync, "interval", minutes=30, id="stock_xml_sync")
        scheduler.start()
        logger.info("APScheduler started — XML feeds and stock sync every 30 min")
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed — install with: pip install apscheduler")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    os.makedirs("static/product_images", exist_ok=True)
    scheduler = _start_scheduler()
    yield
    # Shutdown
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.APP_NAME,
    description="AI destekli ERP sistemi - Pergefood",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow local dev and Capacitor Android WebView
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # If using "*", credentials must be False
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static dir exists before mounting (StaticFiles raises if missing)
os.makedirs("static/product_images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

PREFIX = settings.API_V1_STR

app.include_router(auth_router, prefix=PREFIX)
app.include_router(products_router, prefix=PREFIX)
app.include_router(stock_router, prefix=PREFIX)
app.include_router(suppliers_router, prefix=PREFIX)
app.include_router(invoices_router, prefix=PREFIX)
app.include_router(ai_router, prefix=PREFIX)
app.include_router(analytics_router, prefix=PREFIX)
app.include_router(market_router, prefix=PREFIX)
app.include_router(xml_router, prefix=PREFIX)
app.include_router(stock_xml_router, prefix=PREFIX)
app.include_router(xml_quick_router, prefix=PREFIX)
app.include_router(shipping_router, prefix=PREFIX)
app.include_router(offers_router, prefix=PREFIX)
app.include_router(brands_router, prefix=PREFIX)
app.include_router(categories_router, prefix=PREFIX)


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["Root"])
def health():
    return {"status": "healthy"}
