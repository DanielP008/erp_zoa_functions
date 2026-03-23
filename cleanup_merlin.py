"""Cleanup projects with null idProyectoEnPasarela to allow new tests."""
import requests
import logging
from Merlin.merlin_client import MerlinClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup():
    config = {"user": "DANIEL", "pass": "Merlin2021"}
    client = MerlinClient(config)
    token = client.login()
    
    base = client.base_url
    headers = {"Authorization": token}
    
    # We can't easily search for nulls via API, but we can try to find the project that's causing the duplicate key
    # Actually, the error says 'idProyectoEnPasarela_1 dup key: { idProyectoEnPasarela: null }'
    # This means there is at least one project with idProyectoEnPasarela = null.
    
    # Let's try to list recent projects and delete those with null idProyectoEnPasarela
    # The API doesn't have a clear "list all" but let's try some common patterns or just delete by ID if we had it.
    
    print("Searching for projects to cleanup...")
    # Try to get the last session projects
    r = requests.get(f"{base}/sesions/user/DANIEL/last", headers=headers)
    if r.status_code == 200:
        session_id = r.json().get("id")
        print(f"Last session: {session_id}")
    
    # Since we can't easily find the ID, let's try to force a project creation and see if we can get more info
    # or just report the situation.
    print("Manual cleanup required via Merlin UI or DB if API doesn't allow listing/deleting by null field.")

if __name__ == "__main__":
    cleanup()
