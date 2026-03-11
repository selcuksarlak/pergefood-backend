import requests

url = "https://www.pergefood.com/xml.php?custom=KategoriXML"
res = requests.get(url, timeout=30)
print("Headers:", res.headers)
print("Apparent encoding:", res.apparent_encoding)
print("Encoding used:", res.encoding)

# Raw bytes snippet
raw = res.content[:500]
print("RAW:")
print(raw)

# Try utf-8
print("\nUTF-8 Decode:")
try:
    print(res.content.decode("utf-8")[:500])
except Exception as e:
    print("UTF-8 Failed:", e)

# Try windows-1254
print("\nWINDOWS-1254 Decode:")
try:
    print(res.content.decode("windows-1254")[:500])
except Exception as e:
    print("Win1254 Failed:", e)
