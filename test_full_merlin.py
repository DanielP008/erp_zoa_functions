"""Full test of Merlin Hogar flow: Create, Capitals, Tarify, Offers."""
import json
import logging
import time
from Merlin.merlin_client import MerlinClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_full_flow():
    config = {"user": "DANIEL", "pass": "Merlin2021"}
    client = MerlinClient(config)
    
    datos = {
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
        "max_wait_polling": 120
    }

    print("\n=== STEP 1: CREATE PROJECT ===")
    client.login()
    aseguradoras = client.obtener_aseguradoras("HOGAR")
    plantillas_ids = [a["plantilla_id"] for a in aseguradoras.values()]
    proyecto = client.obtener_proyecto_nuevo(plantillas_ids)
    
    # Fill basic data
    from Merlin.merlin_client import DATOS_BASICOS_HOGAR_CLASS, _build_riesgo_hogar, _build_persona
    datos_basicos = proyecto.get("datosBasicos") or proyecto.get("datos_basicos", {})
    datos_basicos["vivienda"] = _build_riesgo_hogar(datos)
    datos_basicos["propietario"] = _build_persona(datos, "PROPIETARIO")
    datos_basicos["tomador"] = _build_persona(datos, "TOMADOR")
    datos_basicos["@class"] = DATOS_BASICOS_HOGAR_CLASS
    datos_basicos["class_name"] = DATOS_BASICOS_HOGAR_CLASS
    
    if "datosBasicos" in proyecto: proyecto["datosBasicos"] = datos_basicos
    else: proyecto["datos_basicos"] = datos_basicos
    
    saved = client.guardar_proyecto(proyecto)
    mongo_id = saved.get("id")
    pasarela_id = saved.get("id_proyecto_en_pasarela") or saved.get("idProyectoEnPasarela")
    print(f"Project saved. Mongo ID: {mongo_id}, Pasarela ID: {pasarela_id}")

    print("\n=== STEP 2: GET RECOMMENDED CAPITALS ===")
    dgs_list = list({a["dgs"] for a in aseguradoras.values()})
    
    cap_resp = None
    try:
        cap_resp = client.solicitar_capitales_recomendados(mongo_id, dgs_list)
    except Exception as e:
        print(f"Warning: Could not get recommended capitals: {e}")
    
    capitals = []
    if cap_resp and cap_resp.get("idProcesoPasarela"):
        proc_id = cap_resp.get("idProcesoPasarela")
        print(f"Polling capitals (process {proc_id})...")
        for i in range(10):
            time.sleep(3)
            status = client.consultar_estado_capitales(proc_id)
            if status.get("terminado"):
                capitals = status.get("capitales", [])
                print(f"Capitals received: {len(capitals)}")
                break
    
    if capitals:
        # Pick first valid capital for tarification
        valid_cap = next((c for c in capitals if (c.get("continente") or 0) > 0), None)
        if valid_cap:
            datos["capital_continente"] = valid_cap["continente"]
            datos["capital_contenido"] = valid_cap["contenido"]
            print(f"Using capitals: Continente={datos['capital_continente']}, Contenido={datos['capital_contenido']}")
        else:
            datos["capital_continente"] = 150000
            datos["capital_contenido"] = 30000
            print("No valid capitals found, using defaults.")
    else:
        datos["capital_continente"] = 150000
        datos["capital_contenido"] = 30000
        print("No capitals received, using defaults.")

    print("\n=== STEP 3: TARIFY AND GET OFFERS ===")
    # Save additional data (capitals)
    try:
        client.guardar_datos_adicionales_hogar(str(pasarela_id), datos)
        print("Additional data saved successfully.")
    except Exception as e:
        print(f"Warning: Failed to save additional data: {e}")
    
    # Tarify
    ok, offers, final_proj = client._tarificar_y_obtener_ofertas(mongo_id, "HOGAR", max_wait=120)
    
    print(f"\nTarification Finished: {ok}")
    print(f"Total Offers: {len(offers)}")
    for off in offers[:5]:
        print(f"  - {off['nombre_aseguradora']}: {off['prima_anual']} EUR")

    if not offers:
        print("\nDEBUG: Final Project State:")
        # print(json.dumps(final_proj, indent=2))

if __name__ == "__main__":
    test_full_flow()
