import requests
import time

base_url = "http://localhost:8000/api/v1"
res = requests.post(f"{base_url}/auth/login", data={"username": "admin", "password": "pergefood1234"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

feeds_res = requests.get(f"{base_url}/xml-feeds/", headers=headers)
feeds = feeds_res.json()

main_feed_id = None
for f in feeds:
    if "OrnekXML" in f.get("url", "") or "urunXML" in f.get("custom_param", "") or f.get("id") == 1 or f.get("id") == 2:
        main_feed_id = f["id"]
        break

if not main_feed_id and feeds:
    main_feed_id = feeds[0]["id"]

if main_feed_id:
    print(f"Initiating XML Sync for Feed {main_feed_id}...")
    sync_res = requests.post(f"{base_url}/xml-feeds/{main_feed_id}/sync-now", headers=headers)
    print("Sync Request Status:", sync_res.status_code)
    try:
        print(sync_res.json())
    except:
        print(sync_res.text)
else:
    print("No feeds found to sync.")
