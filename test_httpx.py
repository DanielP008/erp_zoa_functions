"""Test with httpx (HTTP/2) and urllib3 to rule out requests library issue."""
import json
import http.client
import ssl
from urllib.parse import urlparse

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"
host = "drseguros.merlin.insure"

# Use http.client directly (lowest level)
ctx = ssl.create_default_context()
conn = http.client.HTTPSConnection(host, timeout=30, context=ctx)

# Login
login_body = json.dumps({"username": "DANIEL", "password": "Merlin2021"})
conn.request("POST", "/multi/multitarificador4-servicios/login",
             body=login_body,
             headers={"Content-Type": "application/json", "Host": host})
resp = conn.getresponse()
token = resp.getheader("Authorization")
body = resp.read().decode()
print(f"Login: {resp.status} token={token[:60]}...")
print(f"  Body: {body}")

# Try /proyecto/nuevo with http.client
ids = ["62f109514b22d912058b1732", "628b8d681861ee59091322cf"]
req_body = json.dumps({
    "idsPlantillasSeleccionadas": ids,
    "idsPlantillasComplementarioSeleccionadas": [],
    "complementarioTarificacion": {
        "aplicacionObligatoria": False,
        "seguroComplementarioIncluido": False,
        "importeDesglosado": True,
        "ramosComplementarios": [],
        "seguroComplementarioActivo": True,
    },
})

# Test 1: Standard headers
print("\n=== http.client POST /proyecto/nuevo (standard) ===")
conn2 = http.client.HTTPSConnection(host, timeout=30, context=ctx)
conn2.request("POST", "/multi/multitarificador4-servicios/proyecto/nuevo",
              body=req_body,
              headers={
                  "Content-Type": "application/json",
                  "Authorization": token,
                  "Host": host,
                  "Accept": "application/json, text/plain, */*",
              })
resp2 = conn2.getresponse()
headers2 = {h: v for h, v in resp2.getheaders()}
body2 = resp2.read().decode() or "(empty)"
print(f"  Status: {resp2.status}")
print(f"  Headers: {headers2}")
print(f"  Body: {body2[:300]}")

# Test 2: With all browser headers on fresh connection
print("\n=== http.client POST /proyecto/nuevo (browser-like) ===")
conn3 = http.client.HTTPSConnection(host, timeout=30, context=ctx)
conn3.request("POST", "/multi/multitarificador4-servicios/proyecto/nuevo",
              body=req_body,
              headers={
                  "Host": host,
                  "Connection": "keep-alive",
                  "Content-Type": "application/json",
                  "Authorization": token,
                  "Accept": "application/json, text/plain, */*",
                  "Origin": "https://drseguros.merlin.insure",
                  "Referer": "https://drseguros.merlin.insure/multitarificador4-servicios/",
                  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                  "Sec-Fetch-Dest": "empty",
                  "Sec-Fetch-Mode": "cors",
                  "Sec-Fetch-Site": "same-origin",
                  "Accept-Encoding": "gzip, deflate, br, zstd",
                  "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
              })
resp3 = conn3.getresponse()
body3 = resp3.read().decode() or "(empty)"
print(f"  Status: {resp3.status}")
print(f"  Body: {body3[:300]}")

# Test 3: Try with Transfer-Encoding chunked
print("\n=== http.client POST (chunked) ===")
conn4 = http.client.HTTPSConnection(host, timeout=30, context=ctx)
conn4.request("POST", "/multi/multitarificador4-servicios/proyecto/nuevo",
              body=req_body,
              headers={
                  "Content-Type": "application/json",
                  "Authorization": token,
                  "Host": host,
                  "Transfer-Encoding": "chunked",
              })
resp4 = conn4.getresponse()
body4 = resp4.read().decode() or "(empty)"
print(f"  Status: {resp4.status} -> {body4[:300]}")

# Test 4: Check if endpoint requires specific XSRF/CSRF token
print("\n=== Checking for CSRF/XSRF requirements ===")
import requests
s = requests.Session()
s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token_req = s.headers.get("Authorization", s.cookies.get("Authorization", "none"))
print(f"  Session cookies: {dict(s.cookies)}")

# Fetch root page to get CSRF token
r_root = s.get("https://drseguros.merlin.insure/multitarificador4-servicios/", timeout=30)
print(f"  GET /multitarificador4-servicios/: {r_root.status_code}, cookies after: {dict(s.cookies)}")
print(f"  Set-Cookie headers: {r_root.headers.get('Set-Cookie', 'none')}")

# Try fetching the XSRF token endpoint
for path in ["/csrf", "/api/csrf", "/_csrf"]:
    try:
        full = f"{base}{path}"
        r_csrf = s.get(full, headers={"Authorization": token}, timeout=10)
        print(f"  GET {path}: {r_csrf.status_code} -> {r_csrf.text[:100]}")
    except Exception as e:
        print(f"  GET {path}: ERROR {e}")

print("\nDONE")
