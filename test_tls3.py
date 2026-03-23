"""Test with curl_cffi Chrome impersonation - fixed JSON parsing."""
import json
from curl_cffi import requests as cf_requests

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"

# Use regular requests for setup, curl_cffi just for the critical call
import requests as std_requests

s_std = std_requests.Session()
r = s_std.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Login: {r.status_code}")

r2 = s_std.get(f"{base}/aseguradoras", params={"subramo": "HOGAR", "orderString": "ASC"},
               headers={"Authorization": token}, timeout=30)
items = r2.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]
print(f"Templates: {len(ids)}")
dgs_list = [item["compania"]["dgs"] for item in items if "compania" in item]
print(f"DGS: {dgs_list}")

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

# Test with curl_cffi Chrome impersonation
for impersonate_target in ["chrome", "chrome110", "chrome120", "chrome124", "safari", "safari17_0"]:
    try:
        s_cf = cf_requests.Session(impersonate=impersonate_target)
        body_bytes = json.dumps(body).encode("utf-8")
        r3 = s_cf.post(
            f"{base}/proyecto/nuevo",
            content=body_bytes,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
            },
            timeout=30,
        )
        resp = r3.text[:300] if r3.text else "(empty)"
        print(f"\n{impersonate_target}: {r3.status_code} -> {resp}")
        if r3.status_code == 200:
            proj = r3.json()
            print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}")
            pid = proj.get("id")
            if pid:
                std_requests.delete(f"{base}/proyecto/{pid}", headers={"Authorization": token}, timeout=10)
            break
    except Exception as e:
        print(f"\n{impersonate_target}: ERROR -> {e}")

# Also try: what if we need to create a session in Merlin first?
print("\n=== Trying to create session first ===")
import time

# Create a session entry
session_body = {
    "username": "DANIEL",
    "login": list(time.localtime()[:7]),
}
r_session = s_std.post(f"{base}/sesions", json=session_body,
                       headers={"Authorization": token, "Content-Type": "application/json"}, timeout=10)
print(f"POST /sesions: {r_session.status_code} -> {r_session.text[:200] if r_session.text else '(empty)'}")

# Try proyecto/nuevo after session
r4 = s_std.post(f"{base}/proyecto/nuevo", json=body,
                headers={"Authorization": token}, timeout=30)
print(f"POST /proyecto/nuevo after session: {r4.status_code} -> {r4.text[:300] if r4.text else '(empty)'}")

print("\nDONE")
