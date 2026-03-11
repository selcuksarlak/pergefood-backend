from sqlalchemy import create_engine, text
from app.core.config import settings

def test_encoding(use_utf8=True):
    print(f"\n--- Testing with use_utf8={use_utf8} ---")
    connect_args = {"charset": "utf8"} if use_utf8 else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
    
    with engine.connect() as conn:
        # Create a temp table with NVARCHAR
        conn.execute(text("IF OBJECT_ID('temp_test', 'U') IS NOT NULL DROP TABLE temp_test"))
        conn.execute(text("CREATE TABLE temp_test (val NVARCHAR(100))"))
        
        test_str = "İçecekler Şahin Öçüğ"
        print(f"Writing: {test_str}")
        
        # Use SQLAlchemy's parameter binding which handles the N prefix for Unicode
        conn.execute(text("INSERT INTO temp_test (val) VALUES (:v)"), {"v": test_str})
        conn.commit()
        
        # Read back
        res = conn.execute(text("SELECT val, CAST(val AS VARBINARY(MAX)) FROM temp_test")).fetchone()
        read_val = res[0]
        hex_val = res[1].hex()
        
        print(f"Read back: {read_val}")
        print(f"Bytes: {hex_val}")
        print(f"Code points: {[ord(c) for c in read_val]}")
        
        if read_val == test_str:
            print("SUCCESS: Values match!")
        else:
            print("FAILURE: Values mismatch!")

if __name__ == "__main__":
    test_encoding(use_utf8=True)
    test_encoding(use_utf8=False)
