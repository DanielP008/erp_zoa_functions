"""Find and delete projects with null idProyectoEnPasarela to fix the 500 duplicate error."""
import requests
import logging
from Merlin.merlin_client import MerlinClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_merlin():
    config = {"user": "DANIEL", "pass": "Merlin2021"}
    client = MerlinClient(config)
    token = client.login()
    
    base = client.base_url
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    }
    
    # Try to find the problematic projects. 
    # Usually there is a search or list endpoint. Let's try /proyecto (GET)
    print("\n--- Fetching project list to find null IDs ---")
    # We try common pagination params
    r = requests.get(f"{base}/proyecto", params={"page": 0, "size": 20, "sort": "instanteDeCreacion,desc"}, headers=headers)
    
    if r.status_code == 200:
        projects = r.json()
        # If it's a Spring Page object, projects are in 'content'
        items = projects.get("content", projects) if isinstance(projects, dict) else projects
        
        found_nulls = []
        for p in items:
            pid = p.get("id")
            pasarela = p.get("idProyectoEnPasarela") or p.get("id_proyecto_en_pasarela")
            subramo = p.get("subramo")
            print(f"Project {pid} | Pasarela: {pasarela} | Subramo: {subramo}")
            if pasarela is None:
                found_nulls.append(pid)
        
        if found_nulls:
            print(f"\nFOUND {len(found_nulls)} PROJECTS WITH NULL PASARELA ID. DELETING...")
            for nid in found_nulls:
                dr = requests.delete(f"{base}/proyecto/{nid}", headers=headers)
                print(f"Delete {nid}: {dr.status_code}")
        else:
            print("\nNo projects with null Pasarela ID found in the first page.")
    else:
        print(f"Failed to list projects: {r.status_code} -> {r.text}")

    # Now let's try a very specific POST /proyecto/nuevo variation
    print("\n--- Final probe for POST /proyecto/nuevo ---")
    # Variation: what if it's the 'hsp' object instead of 'complementarioTarificacion' in the REQUEST?
    # (Documentation says one thing, but your trace showed 'hsp' in the response)
    
    # Let's get templates again
    r_ins = requests.get(f"{base}/aseguradoras", params={"subramo": "HOGAR"}, headers=headers)
    items = r_ins.json()
    plantillas = list(set([p["id"] for item in items for p in item.get("plantillas", []) if p.get("activa")]))
    
    test_bodies = [
        {
            "name": "Strict Documentation",
            "payload": {
                "idsPlantillasSeleccionadas": plantillas,
                "idsPlantillasComplementarioSeleccionadas": [],
                "complementarioTarificacion": {
                    "aplicacionObligatoria": False,
                    "seguroComplementarioIncluido": False,
                    "importeDesglosado": True,
                    "ramosComplementarios": [],
                    "seguroComplementarioActivo": True
                }
            }
        },
        {
            "name": "Minimal (only IDs)",
            "payload": {
                "idsPlantillasSeleccionadas": plantillas
            }
        }
    ]
    
    for test in test_bodies:
        print(f"Testing: {test['name']}")
        tr = requests.post(f"{base}/proyecto/nuevo", json=test['payload'], headers=headers)
        print(f"Result: {tr.status_code} | Body: {tr.text[:100]}")

if __name__ == "__main__":
    fix_merlin()
