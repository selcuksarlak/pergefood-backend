import requests

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cats = requests.get(f"{base_url}/categories/", headers=headers).json()
print(f"Total Categories: {len(cats)}")
for c in cats:
    print(f"ID {c['id']}: {c['name']}")
