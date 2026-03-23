"""Run this directly on Windows (not Docker) to test IP-based restrictions."""
import requests
import json

base = "https://drseguros.merlin.insure/multi/multitarificador4-servicios"
s = requests.Session()

# Login
r = s.post(f"{base}/login", json={"username": "DANIEL", "password": "Merlin2021"}, timeout=30)
token = r.headers.get("Authorization", "")
print(f"Login: {r.status_code}, token={token[:50]}...")
s.headers.update({"Authorization": token})

# Get templates
r2 = s.get(f"{base}/aseguradoras", params={"subramo": "HOGAR", "orderString": "ASC"}, timeout=30)
items = r2.json()
ids = [p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]
print(f"Templates ({len(ids)}): {ids}")

# Get DGS codes for capitales-recomendados
dgs_list = []
for item in items:
    comp = item.get("compania", {})
    dgs = comp.get("dgs")
    if dgs:
        dgs_list.append(dgs)
dgs_str = ",".join(dgs_list)
print(f"DGS codes: {dgs_str}")

# POST /proyecto/nuevo - body exactly matching the schema
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

print(f"\n=== POST /proyecto/nuevo ===")
r3 = s.post(f"{base}/proyecto/nuevo", json=body, timeout=30)
print(f"Status: {r3.status_code}")
print(f"Body: {r3.text[:500] if r3.text else '(empty)'}")

if r3.status_code == 200:
    proj = r3.json()
    proyecto_id = proj.get("id")
    id_pasarela = proj.get("id_proyecto_en_pasarela")
    instante = proj.get("instante_de_creacion")
    print(f"SUCCESS! id={proyecto_id}, pasarela={id_pasarela}, instante={instante}")

    # Now try capitales-recomendados
    print(f"\n=== GET /capitales-recomendados ===")
    r4 = s.get(f"{base}/capitales-recomendados",
               params={"idProyecto": proyecto_id, "dgsCompanias": dgs_str},
               timeout=30)
    print(f"Status: {r4.status_code}")
    print(f"Body: {r4.text[:300] if r4.text else '(empty)'}")
    
    if r4.status_code == 200:
        id_proceso = r4.text.strip().strip('"')
        print(f"Proceso ID: {id_proceso}")
        
        # Poll estado
        import time
        for i in range(10):
            time.sleep(2)
            r5 = s.get(f"{base}/capitales-recomendados/estado",
                       params={"idProcesoPasarela": id_proceso, "subramo": "HOGAR"},
                       timeout=30)
            print(f"Estado poll {i+1}: {r5.status_code}")
            if r5.status_code == 200:
                data = r5.json()
                if data.get("terminado"):
                    print(f"TERMINADO! Capitales: {json.dumps(data.get('capitales', []), indent=2)[:1000]}")
                    break
                else:
                    print(f"  Still running...")
else:
    print(f"FAILED. Response headers: {dict(r3.headers)}")

print("\nDONE")
