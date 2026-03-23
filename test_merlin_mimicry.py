"""Test the updated Merlin client with the new browser-mimicking logic."""
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
    print("\n=== STARTING MERLIN HOGAR TEST WITH BROWSER MIMICRY ===")
    
    try:
        result = client.crear_proyecto_completo(datos_hogar)
        
        print("\n=== TEST RESULT ===")
        print(f"Success: {result.get('success')}")
        
        if result.get('success'):
            print(f"Project ID: {result.get('proyecto_id')}")
            print(f"Pasarela ID: {result.get('id_pasarela')}")
            print(f"Action Required: {result.get('action_required')}")
            
            capitals = result.get('capitales_recomendados', [])
            if capitals:
                print(f"\nRECEIVED {len(capitals)} RECOMMENDED CAPITALS:")
                for cap in capitals[:5]: # Show first 5
                    print(f"  - {cap.get('nombre_aseguradora', cap.get('dgs'))}: Continente={cap.get('continente')}, Contenido={cap.get('contenido')}")
            else:
                print("\nNo recommended capitals received.")
                
            offers = result.get('ofertas', [])
            if offers:
                print(f"\nRECEIVED {len(offers)} OFFERS:")
                for off in offers[:3]:
                    print(f"  - {off.get('nombre_aseguradora')}: {off.get('prima_anual')} EUR")
        else:
            print(f"Error: {result.get('error')}")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hogar_project()
