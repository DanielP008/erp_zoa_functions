"""Find and delete projects with null idProyectoEnPasarela via search."""
import requests
import logging
from Merlin.merlin_client import MerlinClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_merlin_v2():
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
    
    # Try to find the problematic projects via /proyectos (plural)
    print("\n--- Fetching project list via /proyectos ---")
    # We try common pagination params
    r = requests.get(f"{base}/proyectos", params={"page": 0, "size": 50}, headers=headers)
    
    if r.status_code == 200:
        projects = r.json()
        items = projects.get("content", projects) if isinstance(projects, dict) else projects
        
        found_nulls = []
        for p in items:
            pid = p.get("id")
            pasarela = p.get("idProyectoEnPasarela") or p.get("id_proyecto_en_pasarela")
            print(f"Project {pid} | Pasarela: {pasarela}")
            if pasarela is None:
                found_nulls.append(pid)
        
        if found_nulls:
            print(f"\nFOUND {len(found_nulls)} PROJECTS WITH NULL PASARELA ID. DELETING...")
            for nid in found_nulls:
                dr = requests.delete(f"{base}/proyecto/{nid}", headers=headers)
                print(f"Delete {nid}: {dr.status_code}")
        else:
            print("\nNo projects with null Pasarela ID found.")
    else:
        print(f"Failed to list projects: {r.status_code} -> {r.text}")

if __name__ == "__main__":
    fix_merlin_v2()
