"""Test the updated Merlin client with the new browser-mimicking logic (FIXED BODY)."""
import json
import logging
import os
from Merlin.merlin_client import MerlinClient

# Configure logging to see the details
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def test_hogar_project():
    # Configuration from the user's previous logs
    config = {
        "user": "DANIEL",
        "pass": "Merlin2021"
    }
    
    # Payload based on the last successful data extraction
    datos_hogar = {
        "ramo": "HOGAR",
        "dni": "23940602V",
        "nombre": "DANIEL",
        "apellido1": "PULGAR",
        "apellido2": "SORIANO",
        "fecha_nacimiento": "2000-12-31",
        "sexo": "MASCULINO",
        "estado_civil": "SOLTERO",
        "codigo_postal": "46025",
        "tipo_via": "CL",
        "nombre_via": "ANDRES PILES IBARS",
        "numero_calle": "4",
        "piso": "5",
        "puerta": "13",
        "numero_personas_vivienda": 4,
        "tipo_vivienda": "PISO_EN_ALTO",
        "situacion_vivienda": "NUCLEO_URBANO",
        "regimen_ocupacion": "PROPIEDAD",
        "uso_vivienda": "VIVIENDA_HABITUAL",
        "utilizacion_vivienda": "VIVIENDA_EXCLUSIVAMENTE",
        "fecha_efecto": "2026-03-24",
        "anio_construccion": 1997,
        "superficie_construida": 160,
        "calidad_construccion": "NORMAL",
        "materiales_construccion": "SOLIDA_PIEDRAS_LADRILLOS_ETC",
        "tipo_tuberias": "POLIPROPILENO",
        "max_wait_polling": 30 # Short wait for test
    }

    client = MerlinClient(config)
    print("\n=== STARTING MERLIN HOGAR TEST WITH BROWSER MIMICRY (FIXED BODY) ===")
    
    try:
        # Step 1: Login and establish session
        client.login()
        
        # Step 2: Get insurers
        aseguradoras = client.obtener_aseguradoras("HOGAR")
        plantillas_ids = [a["plantilla_id"] for a in aseguradoras.values()]
        
        # Step 3: Try POST /proyecto/nuevo with EXACT body from browser
        # The browser sends:
        # {
        #   "idsPlantillasSeleccionadas": [...],
        #   "idsPlantillasComplementarioSeleccionadas": [],
        #   "complementarioTarificacion": {
        #     "aplicacionObligatoria": false,
        #     "seguroComplementarioIncluido": false,
        #     "importeDesglosado": true,
        #     "ramosComplementarios": [],
        #     "seguroComplementarioActivo": true
        #   }
        # }
        
        body = {
            "idsPlantillasSeleccionadas": plantillas_ids,
            "idsPlantillasComplementarioSeleccionadas": [],
            "complementarioTarificacion": {
                "aplicacionObligatoria": False,
                "seguroComplementarioIncluido": False,
                "importeDesglosado": True,
                "ramosComplementarios": [],
                "seguroComplementarioActivo": True
            }
        }
        
        print("\n=== ATTEMPTING POST /proyecto/nuevo with full browser body ===")
        # We use client._request to bypass the internal logic for a moment to see the raw response
        try:
            proyecto = client._request("POST", "/proyecto/nuevo", "merlin_proyecto_nuevo", json=body)
            print(f"SUCCESS! Status: 200")
            print(f"Project ID: {proyecto.get('id')}")
            print(f"Pasarela ID: {proyecto.get('id_proyecto_en_pasarela')}")
            print(f"Instante: {proyecto.get('instante_de_creacion')}")
            
            # If successful, we can try to get capitals
            if proyecto.get('id'):
                dgs_list = [a["dgs"] for a in aseguradoras.values()]
                print(f"\nRequesting capitals for {len(dgs_list)} insurers...")
                cap_resp = client.solicitar_capitales_recomendados(proyecto.get('id'), dgs_list)
                print(f"Capitals Request Response: {cap_resp}")
                
                proc_id = cap_resp.get("idProcesoPasarela")
                if proc_id:
                    print("\nPolling for capitals...")
                    import time
                    for i in range(5):
                        time.sleep(2)
                        status = client.consultar_estado_capitales(proc_id)
                        print(f"Poll {i+1}: terminado={status.get('terminado')}")
                        if status.get('terminado'):
                            print(f"CAPITALS RECEIVED: {len(status.get('capitales', []))}")
                            break
                            
        except Exception as exc:
            print(f"FAILED: {exc}")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    test_hogar_project()
