"""Check login response body and try session-based approach."""
import requests
import json

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"

# Check login response body
s = requests.Session()
r = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Login status: {r.status_code}")
print(f"Login body: '{r.text}'")
print(f"Login body bytes: {r.content}")
print(f"All cookies: {dict(s.cookies)}")
print(f"Set-Cookie headers: {r.headers.get('Set-Cookie', 'none')}")

# Decode JWT to see claims
import base64
parts = token.replace("Bearer ", "").split(".")
if len(parts) >= 2:
    payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
    decoded = base64.b64decode(payload).decode("utf-8")
    print(f"\nJWT payload: {decoded}")

# Check user endpoint like the browser does
s.headers.update({"Authorization": token, "Content-Type": "application/json"})
r2 = s.get(f"{base}/user", params={"id": "DANIEL"}, timeout=30)
print(f"\nGET /user?id=DANIEL: {r2.status_code}")
if r2.status_code == 200:
    user_data = r2.json()
    print(f"  username: {user_data.get('username')}")
    print(f"  role: {user_data.get('role')}")
    print(f"  Session cookies after /user: {dict(s.cookies)}")

# Check if session was created
r3 = s.get(f"{base}/sesions/user/DANIEL/last", timeout=10)
print(f"\nLast session: {r3.status_code} -> {r3.text[:200] if r3.text else '(empty)'}")

# Now try POST /proyecto/nuevo after fetching user info
print("\n=== AFTER USER FETCH ===")
r4 = s.get(f"{base}/aseguradoras", params={"subramo": "HOGAR"}, timeout=30)
items = r4.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]

body = {
    "idsPlantillasSeleccionadas": ids,
    "idsPlantillasComplementarioSeleccionadas": [],
    "complementarioTarificacion": {
        "aplicacionObligatoria": False,
        "seguroComplementarioIncluido": False,
        "importeDesglosado": True,
        "ramosComplementarios": [],
        "seguroComplementarioActivo": True,
    },
}

r5 = s.post(f"{base}/proyecto/nuevo", json=body, timeout=30)
print(f"POST /proyecto/nuevo: {r5.status_code} -> {r5.text[:300] if r5.text else '(empty)'}")
print(f"All session cookies: {dict(s.cookies)}")
print(f"All request headers sent: {dict(s.headers)}")

# Try: what if we need to send the body as a raw string with specific encoding?
print("\n=== RAW BODY TEST ===")
body_str = json.dumps(body, separators=(",", ":"))
print(f"Body string (first 200): {body_str[:200]}")
r6 = s.post(f"{base}/proyecto/nuevo", data=body_str.encode("utf-8"),
            headers={"Content-Type": "application/json;charset=UTF-8"}, timeout=30)
print(f"Raw body: {r6.status_code} -> {r6.text[:300] if r6.text else '(empty)'}")

# Try with different JSON serialization (Python's json vs browser)
print("\n=== DIFFERENT SERIALIZATION ===")
body_pretty = json.dumps(body)
r7 = s.post(f"{base}/proyecto/nuevo", data=body_pretty.encode("utf-8"), timeout=30)
print(f"Pretty JSON: {r7.status_code} -> {r7.text[:300] if r7.text else '(empty)'}")

print("\nDONE")
