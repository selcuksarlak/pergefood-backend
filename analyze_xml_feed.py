
import requests

url = "https://www.pergefood.com/xml.php?custom=OrnekXML"
try:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    # The feed is in windows-1254 (Turkish charset)
    resp.encoding = "windows-1254"
    print(resp.text[:2000])
except Exception as e:
    print(f"Error fetching XML: {e}")
