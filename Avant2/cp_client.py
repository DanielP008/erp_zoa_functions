import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

PROVINCIAS_ES: Dict[str, str] = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alicante/Alacant",
    "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Illes Balears", "08": "Barcelona", "09": "Burgos",
    "10": "Cáceres", "11": "Cádiz", "12": "Castellón/Castelló",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña",
    "16": "Cuenca", "17": "Girona", "18": "Granada",
    "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva",
    "22": "Huesca", "23": "Jaén", "24": "León",
    "25": "Lleida", "26": "La Rioja", "27": "Lugo",
    "28": "Madrid", "29": "Málaga", "30": "Murcia",
    "31": "Navarra", "32": "Ourense", "33": "Asturias",
    "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra",
    "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria",
    "40": "Segovia", "41": "Sevilla", "42": "Soria",
    "43": "Tarragona", "44": "Teruel", "45": "Toledo",
    "46": "Valencia", "47": "Valladolid", "48": "Bizkaia",
    "49": "Zamora", "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}

def obtener_poblacion_por_cp(cp: str) -> Dict[str, Any]:
    """Obtiene la población y provincia a partir del código postal.

    Uses the free zippopotam.us API for Spanish postal codes.
    The province ID (id_provincia) is derived from the first two digits
    of the postal code, which corresponds to the Spanish INE standard.
    """
    try:
        cp = str(cp).strip().zfill(5)
        url = f"https://api.zippopotam.us/es/{cp}"
        logger.info(f"[AVANT2_CP] Postal code lookup: {url}")

        try:
            resp = requests.get(url, timeout=10)
        except requests.exceptions.SSLError:
            logger.warning("[AVANT2_CP] SSL verification failed for zippopotam.us, retrying without verification.")
            resp = requests.get(url, timeout=10, verify=False)

        if resp.status_code == 404:
            return {"success": False, "error": f"No se encontró población para el CP {cp}"}
        
        if resp.status_code >= 500:
            logger.error(f"[AVANT2_CP] Zippopotam service error: {resp.status_code}")
            return {"success": False, "error": f"Error del servicio de códigos postales ({resp.status_code})"}

        resp.raise_for_status()
        data = resp.json()

        places = data.get("places", [])
        if not places:
            return {"success": False, "error": f"No se encontró población para el CP {cp}"}

        place = places[0]
        poblacion = place.get("place name", "")
        id_provincia = cp[:2]
        descripcion_provincia = PROVINCIAS_ES.get(id_provincia, place.get("state", ""))

        logger.info(
            f"[AVANT2_CP] Postal code resolved: {poblacion} ({descripcion_provincia}) - "
            f"id_provincia={id_provincia}"
        )

        return {
            "success": True,
            "poblacion": poblacion,
            "id_provincia": id_provincia,
            "descripcion_provincia": descripcion_provincia,
            "codigo_postal": cp,
        }

    except Exception as exc:
        logger.error(f"[AVANT2_CP] Postal code lookup failed: {exc}")
        return {"success": False, "error": str(exc)}
