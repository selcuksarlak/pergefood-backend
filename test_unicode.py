from app.core.database import SessionLocal
from app.models.supplier import Supplier
import uuid

def test_turkish_chars():
    db = SessionLocal()
    try:
        test_name = "Test Tedarikçi Şahin Öçüğış - " + str(uuid.uuid4())[:8]
        print(f"Creating supplier with name: {test_name}")
        
        supplier = Supplier(
            supplier_name=test_name,
            contact_person="Özgür Şahin",
            address="Beşiktaş / İstanbul"
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        
        print(f"Stored supplier ID: {supplier.id}")
        
        # Retrieve it back
        retrieved = db.query(Supplier).filter(Supplier.id == supplier.id).first()
        print(f"Retrieved name: {retrieved.supplier_name}")
        
        if retrieved.supplier_name == test_name:
            print("SUCCESS: Turkish characters are stored and retrieved correctly.")
        else:
            print("FAILURE: Character mismatch!")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_turkish_chars()
