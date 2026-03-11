from app.api.routes.auth import router as auth_router
from app.api.routes.products import router as products_router
from app.api.routes.stock import router as stock_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.invoices import router as invoices_router
from app.api.routes.ai_price import router as ai_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.market import router as market_router
from app.api.routes.shipping import router as shipping_router
from app.api.routes.offers import router as offers_router

__all__ = [
    "auth_router", "products_router", "stock_router",
    "suppliers_router", "invoices_router", "ai_router",
    "analytics_router", "market_router", "shipping_router", "offers_router"
]
