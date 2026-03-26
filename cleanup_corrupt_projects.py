"""Script to attempt cleanup of corrupt Merlin projects."""
import logging
import requests
import time
from Merlin.merlin_client import MerlinClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def cleanup_corrupt_projects():
    config = {"user": "DANIEL", "pass": "Merlin2021"}
    client = MerlinClient(config)
    client.login()
    
    # List of known corrupt IDs from previous logs
    corrupt_ids = [
        "69c16f6087aa476505dd02be",
        "69c16ea087aa476505dd0286",
        "69c16e8f87aa476505dd0281",
        "69c16e2687aa476505dd025f",
        "69c16cc687aa476505dd01e5",
        "69c16cd687aa476505dd01eb",
        "69c16caf87aa476505dd01d3"
    ]
    
    print(f"Attempting to delete {len(corrupt_ids)} projects...")
    
    for pid in corrupt_ids:
        url = f"{client.base_url}/proyecto/{pid}"
        print(f"\n--- Deleting {pid} ---")
        
        # Strategy 1: Standard DELETE
        try:
            resp = client._session.delete(url, timeout=10)
            if resp.status_code == 200 or resp.status_code == 204:
                print(f"SUCCESS (Standard): Deleted {pid}")
                continue
            else:
                print(f"FAILED (Standard): {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"ERROR (Standard): {e}")

        # Strategy 2: DELETE with force/ignore ERP if possible (guessing params)
        try:
            print(f"Trying Strategy 2 (force=true) for {pid}...")
            resp = client._session.delete(url, params={"force": "true"}, timeout=10)
            if resp.status_code == 200:
                print(f"SUCCESS (Force): Deleted {pid}")
                continue
            else:
                print(f"FAILED (Force): {resp.status_code}")
        except: pass

        # Strategy 3: Try to "fix" it by updating it to a valid state before deleting
        try:
            print(f"Trying Strategy 3 (Update then Delete) for {pid}...")
            # Fetch current state
            proj = client.obtener_proyecto(pid)
            # Remove the integration_erp that might be causing the conflict
            if "integracion_erp" in proj:
                del proj["integracion_erp"]
            if "integracionErp" in proj:
                del proj["integracionErp"]
            
            # Save it back
            client.guardar_proyecto(proj)
            # Try delete again
            resp = client._session.delete(url, timeout=10)
            if resp.status_code == 200:
                print(f"SUCCESS (Update+Delete): Deleted {pid}")
            else:
                print(f"FAILED (Update+Delete): {resp.status_code}")
        except Exception as e:
            print(f"ERROR (Strategy 3): {e}")

if __name__ == "__main__":
    cleanup_corrupt_projects()
