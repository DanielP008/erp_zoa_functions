"""Test with curl_cffi to mimic browser TLS fingerprint."""
import json

try:
    from curl_cffi import requests as cf_requests
    print("curl_cffi available")
    HAS_CURL_CFFI = True
except ImportError:
    print("curl_cffi NOT available, installing...")
    import subprocess
    subprocess.run(["pip", "install", "curl_cffi"], check=True, capture_output=True)
    from curl_cffi import requests as cf_requests
    HAS_CURL_CFFI = True

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"

# Login with curl_cffi (Chrome impersonation)
s = cf_requests.Session(impersonate="chrome")
r = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Login: {r.status_code}, token={token[:50]}...")

# Get templates
r2 = s.get(f"{base}/aseguradoras", params={"subramo": "HOGAR"}, timeout=30,
           headers={"Authorization": token})
items = r2.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]
print(f"Templates: {len(ids)}")

# POST /proyecto/nuevo with Chrome TLS fingerprint
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

print(f"\n=== curl_cffi (chrome impersonation) POST /proyecto/nuevo ===")
r3 = s.post(f"{base}/proyecto/nuevo", json=body, timeout=30,
            headers={"Authorization": token, "Content-Type": "application/json"})
resp = r3.text[:500] if r3.text else "(empty)"
print(f"Status: {r3.status_code}")
print(f"Body: {resp}")

if r3.status_code == 200:
    proj = r3.json()
    print(f"SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}, instante={proj.get('instante_de_creacion')}")
    # Clean up
    pid = proj.get("id")
    if pid:
        s.delete(f"{base}/proyecto/{pid}", headers={"Authorization": token}, timeout=10)
else:
    print(f"Headers: {dict(r3.headers)}")

# Try different impersonation targets
for target in ["chrome110", "chrome120", "safari", "firefox"]:
    try:
        s2 = cf_requests.Session(impersonate=target)
        r_login = s2.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
        t2 = r_login.headers.get("Authorization", "")
        r4 = s2.post(f"{base}/proyecto/nuevo", json=body, timeout=30,
                     headers={"Authorization": t2, "Content-Type": "application/json"})
        resp4 = r4.text[:200] if r4.text else "(empty)"
        print(f"\n{target}: {r4.status_code} -> {resp4}")
        if r4.status_code == 200:
            proj = r4.json()
            print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}")
            pid = proj.get("id")
            if pid:
                s2.delete(f"{base}/proyecto/{pid}", headers={"Authorization": t2}, timeout=10)
            break
    except Exception as e:
        print(f"\n{target}: ERROR {e}")

print("\nDONE")
