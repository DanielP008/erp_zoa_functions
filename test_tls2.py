"""Test with curl_cffi to mimic browser TLS fingerprint (fixed)."""
import json
from curl_cffi import requests as cf_requests

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"

# Chrome impersonation
s = cf_requests.Session(impersonate="chrome")
r = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Login: {r.status_code}, token={token[:50]}...")

# Need to pass Authorization in every request since curl_cffi sessions are different
headers = {"Authorization": token}

r2 = s.get(f"{base}/aseguradoras?subramo=HOGAR&orderString=ASC", timeout=30, headers=headers)
print(f"Aseguradoras: {r2.status_code}, length={len(r2.text)}")
items = r2.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]
print(f"Templates: {len(ids)}: {ids}")

dgs_list = [item.get("compania", {}).get("dgs") for item in items if item.get("compania", {}).get("dgs")]
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

print(f"\n=== POST /proyecto/nuevo (Chrome TLS) ===")
r3 = s.post(f"{base}/proyecto/nuevo", json=body, timeout=30, headers=headers)
resp = r3.text[:500] if r3.text else "(empty)"
print(f"Status: {r3.status_code}")
print(f"Body: {resp}")

if r3.status_code == 200:
    proj = r3.json()
    print(f"SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}, instante={proj.get('instante_de_creacion')}")
else:
    # Try just idsPlantillasSeleccionadas
    print(f"\n=== Trying minimal body ===")
    r4 = s.post(f"{base}/proyecto/nuevo", 
                json={"idsPlantillasSeleccionadas": ids},
                timeout=30, headers=headers)
    print(f"Minimal: {r4.status_code} -> {r4.text[:300] if r4.text else '(empty)'}")

    # Try with data instead of json
    print(f"\n=== Trying data= instead of json= ===")
    body_str = json.dumps(body)
    h2 = {**headers, "Content-Type": "application/json"}
    r5 = s.post(f"{base}/proyecto/nuevo", data=body_str.encode(), timeout=30, headers=h2)
    print(f"data=: {r5.status_code} -> {r5.text[:300] if r5.text else '(empty)'}")

print("\nDONE")
