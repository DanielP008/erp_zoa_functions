"""Test with curl_cffi using correct API + test HTTP/2."""
import json
from curl_cffi import requests as cf_requests
import requests as std_requests

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"

# Get token and templates via standard requests
s = std_requests.Session()
r = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Token: {token[:50]}...")

r2 = s.get(f"{base}/aseguradoras", params={"subramo": "HOGAR"},
           headers={"Authorization": token}, timeout=30)
items = r2.json()
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
body_bytes = json.dumps(body).encode("utf-8")

# Test with curl_cffi impersonation targets
for target in ["chrome", "chrome110", "chrome120", "chrome124", "safari", "safari17_0", "edge99", "edge101"]:
    try:
        s_cf = cf_requests.Session(impersonate=target)
        r3 = s_cf.post(
            f"{base}/proyecto/nuevo",
            data=body_bytes,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
            },
            timeout=30,
        )
        resp = r3.text[:300] if r3.text else "(empty)"
        status = r3.status_code
        print(f"{target}: {status} -> {resp}")
        if status == 200:
            try:
                proj = r3.json()
                print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}")
                pid = proj.get("id")
                if pid:
                    std_requests.delete(f"{base}/proyecto/{pid}", headers={"Authorization": token}, timeout=10)
            except:
                print(f"  JSON parse failed, raw: {r3.text[:500]}")
            break
    except Exception as e:
        print(f"{target}: ERROR -> {type(e).__name__}: {e}")

# Test: what if we need to pass the XSRF-TOKEN cookie?
print("\n=== Testing with manual XSRF token ===")
import uuid
xsrf_token = str(uuid.uuid4())
r5 = std_requests.post(f"{base}/proyecto/nuevo", json=body,
    headers={
        "Authorization": token,
        "X-XSRF-TOKEN": xsrf_token,
    },
    cookies={"XSRF-TOKEN": xsrf_token},
    timeout=30)
print(f"With XSRF token: {r5.status_code} -> {r5.text[:300] if r5.text else '(empty)'}")

# Test: what if the body uses camelCase field names for the nested object?
print("\n=== Testing with Java-style boolean field names ===")
body_java = {
    "idsPlantillasSeleccionadas": ids,
    "idsPlantillasComplementarioSeleccionadas": [],
    "complementarioTarificacion": {
        "aplicacionObligatoria": False,
        "seguroComplementarioIncluido": False,
        "importeDesglosado": True,
        "ramosComplementarios": [],
        "seguroComplementarioActivo": True,
        "hspActivo": True,
        "hspIncluido": False,
    },
}
r6 = std_requests.post(f"{base}/proyecto/nuevo", json=body_java,
    headers={"Authorization": token}, timeout=30)
print(f"Java-style: {r6.status_code} -> {r6.text[:300] if r6.text else '(empty)'}")

# Test: body with subramo added
print("\n=== Testing with subramo in body ===")
body_sub = {**body, "subramo": "HOGAR"}
r7 = std_requests.post(f"{base}/proyecto/nuevo", json=body_sub,
    headers={"Authorization": token}, timeout=30)
print(f"With subramo: {r7.status_code} -> {r7.text[:300] if r7.text else '(empty)'}")

print("\nDONE")
