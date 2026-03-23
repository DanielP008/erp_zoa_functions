"""Replicate the exact browser request for POST /proyecto/nuevo."""
import requests
import json

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"
s = requests.Session()

# Login
login_resp = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = login_resp.headers.get("Authorization", "")
print(f"Token: {token[:50]}...")
print(f"Login response headers: {dict(login_resp.headers)}")
print(f"Login cookies: {dict(login_resp.cookies)}")

# Get templates
r = s.get(f"{base}/aseguradoras", params={"subramo": "HOGAR"}, timeout=30,
          headers={"Authorization": token})
items = r.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]
print(f"\nTemplates: {ids}")

# Try with complementarioTarificacion included
bodies = [
    {
        "label": "with complementarioTarificacion (full)",
        "body": {
            "idsPlantillasSeleccionadas": ids,
            "idsPlantillasComplementarioSeleccionadas": [],
            "complementarioTarificacion": {
                "aplicacionObligatoria": False,
                "seguroComplementarioIncluido": False,
                "importeDesglosado": True,
                "ramosComplementarios": [],
                "seguroComplementarioActivo": True,
            },
        },
    },
    {
        "label": "with complementario (minimal)",
        "body": {
            "idsPlantillasSeleccionadas": ids,
            "complementarioTarificacion": {
                "seguroComplementarioActivo": False,
            },
        },
    },
    {
        "label": "just ids (original)",
        "body": {
            "idsPlantillasSeleccionadas": ids,
        },
    },
    {
        "label": "ids + empty complementario arrays",
        "body": {
            "idsPlantillasSeleccionadas": ids,
            "idsPlantillasComplementarioSeleccionadas": [],
        },
    },
]

# Browser-like headers
browser_headers = {
    "Authorization": token,
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://drseguros.merlin.insure",
    "Referer": "https://drseguros.merlin.insure/multitarificador4-servicios/proyecto",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

for test in bodies:
    label = test["label"]
    body = test["body"]
    
    # Test 1: with browser headers
    r = requests.post(f"{base}/proyecto/nuevo", json=body, headers=browser_headers, timeout=30)
    resp = r.text[:300] if r.text else "(empty)"
    print(f"\n{label} + browser headers: {r.status_code} -> {resp}")
    
    if r.status_code in (200, 201):
        proj = r.json()
        print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}, instante={proj.get('instante_de_creacion')}")
        # Cleanup
        pid = proj.get("id")
        if pid:
            requests.delete(f"{base}/proyecto/{pid}", headers={"Authorization": token}, timeout=10)
        break
    
    # Test 2: with simple headers
    simple_headers = {"Authorization": token, "Content-Type": "application/json"}
    r2 = requests.post(f"{base}/proyecto/nuevo", json=body, headers=simple_headers, timeout=30)
    resp2 = r2.text[:300] if r2.text else "(empty)"
    print(f"{label} + simple headers: {r2.status_code} -> {resp2}")
    
    if r2.status_code in (200, 201):
        proj = r2.json()
        print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}")
        pid = proj.get("id")
        if pid:
            requests.delete(f"{base}/proyecto/{pid}", headers={"Authorization": token}, timeout=10)
        break

# Also try with the session (which preserves cookies from login)
print("\n=== WITH SESSION (preserves cookies) ===")
s2 = requests.Session()
login2 = s2.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token2 = login2.headers.get("Authorization", "")
s2.headers.update({"Authorization": token2, "Content-Type": "application/json"})
print(f"Session cookies after login: {dict(s2.cookies)}")

# Add browser-like headers to session
s2.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://drseguros.merlin.insure",
    "Referer": "https://drseguros.merlin.insure/multitarificador4-servicios/proyecto",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})

body_full = {
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

r = s2.post(f"{base}/proyecto/nuevo", json=body_full, timeout=30)
resp = r.text[:500] if r.text else "(empty)"
print(f"POST /proyecto/nuevo: {r.status_code} -> {resp}")
if r.status_code in (200, 201):
    proj = r.json()
    print(f"  SUCCESS! pasarela={proj.get('id_proyecto_en_pasarela')}")
    pid = proj.get("id")
    if pid:
        s2.delete(f"{base}/proyecto/{pid}", timeout=10)

print("\nDONE")
