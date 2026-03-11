
import requests
import xml.etree.ElementTree as ET

url = "https://www.pergefood.com/xml.php?custom=OrnekXML"
try:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "windows-1254"
    root = ET.fromstring(resp.text.encode("utf-8"))
    items = root.findall("Products")
    print(f"Total products in XML: {len(items)}")
except Exception as e:
    print(f"Error: {e}")
