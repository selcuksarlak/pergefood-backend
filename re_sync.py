import requests
import time

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("1. Deleting all Brands and Categories...")
requests.delete(f"{base_url}/brands/all", headers=headers)
requests.delete(f"{base_url}/categories/all", headers=headers)

print("2. Syncing Brands with correct encoding...")
b_res = requests.post(f"{base_url}/brands/sync", headers=headers)
print("Brands sync:", b_res.json())

print("3. Syncing Categories with correct encoding...")
c_res = requests.post(f"{base_url}/categories/sync", headers=headers)
print("Categories sync:", c_res.json())

# Fetch products to ensure no empty response and no MSSQL Error
print("4. Testing Products API...")
p_res = requests.get(f"{base_url}/products/?active_only=true", headers=headers)
if p_res.status_code == 200:
    print(f"Products API works! Received {len(p_res.json())} active products.")
else:
    print(f"Products API Failed: {p_res.text}")
