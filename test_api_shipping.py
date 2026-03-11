import requests

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

ship_res = requests.get(f"{base_url}/shipping/", headers=headers)
print("Shipping Status:", ship_res.status_code)
if ship_res.status_code != 200:
    print(ship_res.text)

