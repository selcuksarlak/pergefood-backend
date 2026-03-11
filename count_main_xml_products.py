
import requests
import xml.etree.ElementTree as ET

url = "https://www.pergefood.com/xml.php"
try:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "windows-1254"
    root = ET.fromstring(resp.text.encode("utf-8"))
    # In this feed, the item element might be different. Let's list children of root.
    print(f"Root tag: {root.tag}")
    first_child = root[0] if len(root) > 0 else None
    if first_child is not None:
        print(f"First child tag: {first_child.tag}")
    items = list(root)
    print(f"Total items in root: {len(items)}")
except Exception as e:
    print(f"Error: {e}")
