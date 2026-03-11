from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")

def run_alter(conn, table, column, type_str, nullable=True):
    null_str = "NULL" if nullable else "NOT NULL"
    print(f"Altering {table}.{column} to {type_str} {null_str}...")
    try:
        # Check if column is indexed
        # For simplicity in this script, we'll try to drop common indexes if they fail the alter
        conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} {type_str} {null_str}"))
        print(f"Success: {table}.{column}")
    except Exception as e:
        if "index" in str(e).lower() or "statistics" in str(e).lower():
            print(f"Index conflict for {table}.{column}, attempting to find and drop index...")
            # This is a bit complex for a generic script, but let's handle the known ones
            if table == "products" and column == "product_name":
                try: conn.execute(text("DROP INDEX ix_products_product_name ON products"))
                except: pass
            elif table == "suppliers" and column == "supplier_name":
                try: conn.execute(text("DROP INDEX ix_suppliers_supplier_name ON suppliers"))
                except: pass
            elif table == "offers" and column == "customer_name":
                try: conn.execute(text("DROP INDEX ix_offers_customer_name ON offers"))
                except: pass
            
            # Try again
            try:
                conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} {type_str} {null_str}"))
                print(f"Success after index drop: {table}.{column}")
                # Recreate index if it was a known one
                if table == "products" and column == "product_name":
                    conn.execute(text("CREATE INDEX ix_products_product_name ON products (product_name)"))
                elif table == "suppliers" and column == "supplier_name":
                    conn.execute(text("CREATE INDEX ix_suppliers_supplier_name ON suppliers (supplier_name)"))
            except Exception as e2:
                print(f"Failed again for {table}.{column}: {e2}")
        else:
            print(f"Error {table}.{column}: {e}")

with engine.connect() as conn:
    # Suppliers
    run_alter(conn, "suppliers", "supplier_name", "NVARCHAR(200)", False)
    run_alter(conn, "suppliers", "contact_person", "NVARCHAR(150)")
    run_alter(conn, "suppliers", "phone", "NVARCHAR(30)")
    run_alter(conn, "suppliers", "email", "NVARCHAR(100)")
    run_alter(conn, "suppliers", "address", "NVARCHAR(MAX)")

    # Products
    run_alter(conn, "products", "product_name", "NVARCHAR(200)", False)
    run_alter(conn, "products", "product_code", "NVARCHAR(50)", False)
    run_alter(conn, "products", "barcode", "NVARCHAR(50)")

    # Invoices
    run_alter(conn, "invoices", "invoice_number", "NVARCHAR(100)")
    run_alter(conn, "invoices", "pdf_path", "NVARCHAR(500)")
    run_alter(conn, "invoices", "raw_ocr_text", "NVARCHAR(MAX)")
    run_alter(conn, "invoices", "processing_status", "NVARCHAR(30)")

    # Invoice Items
    run_alter(conn, "invoice_items", "raw_product_name", "NVARCHAR(300)", False)
    run_alter(conn, "invoice_items", "match_status", "NVARCHAR(20)")

    # Stock Entries
    run_alter(conn, "stock_entries", "invoice_number", "NVARCHAR(100)")
    run_alter(conn, "stock_entries", "supplier_name", "NVARCHAR(200)")
    run_alter(conn, "stock_entries", "notes", "NVARCHAR(MAX)")

    # Stock Outputs
    run_alter(conn, "stock_outputs", "customer", "NVARCHAR(200)")
    run_alter(conn, "stock_outputs", "notes", "NVARCHAR(MAX)")

    # Market Prices
    run_alter(conn, "market_prices", "competitor_name", "NVARCHAR(200)", False)
    run_alter(conn, "market_prices", "product_name_on_site", "NVARCHAR(300)", False)
    run_alter(conn, "market_prices", "website_source", "NVARCHAR(500)")

    # AI Predictions
    run_alter(conn, "ai_price_predictions", "demand_prediction", "NVARCHAR(50)")
    run_alter(conn, "ai_price_predictions", "model_used", "NVARCHAR(50)")

    # XML Feed Config
    run_alter(conn, "xml_feed_configs", "name", "NVARCHAR(100)", False)
    run_alter(conn, "xml_feed_configs", "feed_type", "NVARCHAR(50)")
    run_alter(conn, "xml_feed_configs", "url", "NVARCHAR(500)", False)
    run_alter(conn, "xml_feed_configs", "custom_param", "NVARCHAR(200)")
    run_alter(conn, "xml_feed_configs", "root_element", "NVARCHAR(100)")
    run_alter(conn, "xml_feed_configs", "item_element", "NVARCHAR(100)")
    run_alter(conn, "xml_feed_configs", "image_save_dir", "NVARCHAR(300)")
    run_alter(conn, "xml_feed_configs", "last_sync_status", "NVARCHAR(20)")

    # XML Sync Logs
    run_alter(conn, "xml_sync_logs", "status", "NVARCHAR(20)")
    run_alter(conn, "xml_sync_logs", "error_detail", "NVARCHAR(MAX)")
    run_alter(conn, "xml_sync_logs", "raw_url", "NVARCHAR(500)")

    # XML Product Images
    run_alter(conn, "xml_product_images", "original_url", "NVARCHAR(500)", False)
    run_alter(conn, "xml_product_images", "local_path", "NVARCHAR(500)")

    # Stock Sync
    run_alter(conn, "stock_sync_logs", "status", "NVARCHAR(20)")
    run_alter(conn, "stock_sync_logs", "source_url", "NVARCHAR(500)")
    run_alter(conn, "stock_sync_logs", "errors", "NVARCHAR(MAX)")
    run_alter(conn, "stock_sync_item_logs", "product_code", "NVARCHAR(50)")
    run_alter(conn, "stock_sync_item_logs", "product_name", "NVARCHAR(200)")
    run_alter(conn, "stock_sync_item_logs", "result", "NVARCHAR(30)")
    run_alter(conn, "stock_sync_item_logs", "note", "NVARCHAR(300)")
    run_alter(conn, "stock_sync_alerts", "alert_type", "NVARCHAR(30)", False)
    run_alter(conn, "stock_sync_alerts", "alert_message", "NVARCHAR(500)", False)

    # Shipping
    run_alter(conn, "shipping_methods", "name", "NVARCHAR(100)", False)

    # Offers (already mostly handled but for completeness)
    run_alter(conn, "offers", "customer_name", "NVARCHAR(200)", False)
    run_alter(conn, "offers", "status", "NVARCHAR(50)", False)
    run_alter(conn, "offers", "billing_info", "NVARCHAR(2000)")
    run_alter(conn, "offers", "shipping_address", "NVARCHAR(1000)")
    run_alter(conn, "offers", "public_token", "NVARCHAR(64)")

    print("Database full unicode conversion finished.")
