import requests

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

products = requests.get(f"{base_url}/products/?limit=5", headers=headers).json()
for p in products:
    print(p["product_name"])
    print(" - Category:", dict(p.get("category", {})))
    print(" - Brand:", dict(p.get("brand", {})))
