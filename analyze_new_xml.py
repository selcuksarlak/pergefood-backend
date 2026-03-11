import requests

def fetch_xml(url, name):
    print(f"Fetching {name}...")
    try:
        res = requests.get(url)
        print(f"Status: {res.status_code}")
        print(f"Content length: {len(res.text)}")
        print("First 500 chars:")
        print(res.text[:500])
        print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")

fetch_xml("https://www.pergefood.com/xml.php?custom=MarkaXML", "Brands")
fetch_xml("https://www.pergefood.com/xml.php?custom=KategoriXML", "Categories")
