import requests

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
if res.status_code != 200:
    print("Login failed:", res.text)
    exit(1)
    
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

products_res = requests.get(f"{base_url}/products/?active_only=true", headers=headers)
print("Status Code:", products_res.status_code)
if products_res.status_code == 200:
    docs = products_res.json()
    if docs:
        print("First product keys:", list(docs[0].keys()))
        print("First product ID:", docs[0].get('id'))
        print("First product name:", docs[0].get('product_name'))
    else:
        print("No products returned")
