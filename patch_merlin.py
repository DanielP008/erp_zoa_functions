import os

path = r'C:\Users\Danisu\Desktop\TRABAJO\.cursor\Proyectos\zoa_flow_erp\Merlin\merlin_client.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """                logger.info(f"[MERLIN] Syncing persons for Hogar project {id_pasarela}...")
                # Fetch the project again from the server to get the full object with all IDs
                full_project = self.obtener_proyecto(result.get("id"))
                
                # Ensure the full_project has the correct keys for the /personas endpoint
                # The browser trace shows it expects the whole project object
                self._request(
                    "PUT", f"/proyectos-hogar/{id_pasarela}/personas", "merlin_sync_personas",
                    json=full_project 
                )"""

new_block = """                logger.info(f"[MERLIN] Syncing persons for Hogar project {id_pasarela}...")
                # Fetch the project again from the server to get the full object with all IDs
                full_project = self.obtener_proyecto(result.get("id"))
                
                # IMPORTANT: Merge our local data back into the fetched project 
                # because the server might have wiped it out during the main PUT
                local_db = proyecto.get("datos_basicos") or proyecto.get("datosBasicos")
                if local_db and "datos_basicos" in full_project:
                    full_project["datos_basicos"].update(local_db)
                
                # Ensure the full_project has the correct keys for the /personas endpoint
                self._request(
                    "PUT", f"/proyectos-hogar/{id_pasarela}/personas", "merlin_sync_personas",
                    json=full_project 
                )"""

if old_block in content:
    new_content = content.replace(old_block, new_block)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS: File updated.")
else:
    print("ERROR: Could not find the old block in the file.")
    # Print a small part of the file to debug
    index = content.find("Syncing persons")
    if index != -1:
        print("Found 'Syncing persons' at index", index)
        print("Context:", content[index-100:index+300])
    else:
        print("Could not even find 'Syncing persons' in the file.")
