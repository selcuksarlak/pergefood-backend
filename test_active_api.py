import requests

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

products = requests.get(f"{base_url}/products/", params={"active_only": "true"}, headers=headers)
print("Status:", products.status_code)
if products.status_code == 200:
    data = products.json()
    print("Found total products:", len(data))
    if data:
        print("First product keys:", data[0].keys())
else:
    print(products.text)
