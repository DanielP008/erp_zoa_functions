"""Transform AI Chat card data into the flat payload expected by Merlin tools.

Maps the nested card structure (tomador, inmueble, uso, vehiculo, poliza_actual)
into the flat dictionary that create_retarificacion_merlin_project_tool expects.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_VIA_PREFIXES = re.compile(
    r"^(Calle|Avenida|Avda\.?|Av\.?|Plaza|Pza\.?|Paseo|Camino|Carretera|Ronda|Travesía|Glorieta|Urbanización|Urb\.?)\s+",
    re.IGNORECASE,
)

_EXPLICIT_NUM = re.compile(
    r",?\s*(?:n(?:ú|u)mero|nº|num\.?|#)\s*(\d+[\w]*)",
    re.IGNORECASE,
)

_TRAILING_NUM = re.compile(r"\s+(\d+[\w]*)(?:\s*,.*)?$")


def _parse_direccion(direccion: str) -> tuple:
    """Extract nombre_via and numero_calle from a free-text address string.

    Examples:
        "Calle Andrés Piles Ibars, número 4"  -> ("ANDRES PILES IBARS", "4")
        "Avenida de la Constitución 23"        -> ("DE LA CONSTITUCION", "23")
        "Gran Via 10, 3ºB"                     -> ("GRAN VIA", "10")
    """
    import unicodedata

    s = direccion.strip()
    if not s:
        return ("", "")

    numero = ""

    explicit = _EXPLICIT_NUM.search(s)
    if explicit:
        numero = explicit.group(1)
        s = s[:explicit.start()].strip().rstrip(",").strip()
    else:
        parts = re.split(r"\s*,\s*", s, maxsplit=1)
        base = parts[0]
        trailing = _TRAILING_NUM.search(base)
        if trailing:
            numero = trailing.group(1)
            base = base[:trailing.start()].strip()
        s = base

    prefix_match = _VIA_PREFIXES.match(s)
    if prefix_match:
        s = s[prefix_match.end():].strip()

    nfkd = unicodedata.normalize("NFKD", s)
    nombre_via = "".join(c for c in nfkd if not unicodedata.combining(c)).upper()

    return (nombre_via, numero)


def _convert_fecha_efecto(fecha: str) -> str:
    """Convert DD/MM/YYYY to YYYY-MM-DD for Merlin. Pass through if already ISO."""
    if not fecha:
        return ""
    fecha = fecha.strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", fecha)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return fecha


def _map_regimen(regimen: str) -> str:
    """Map uso.regimen values to Merlin's regimen_ocupacion values."""
    r = regimen.strip().upper()
    mapping = {
        "PROPIEDAD": "PROPIEDAD",
        "ALQUILER": "ALQUILER",
        "INQUILINO": "ALQUILER",
    }
    return mapping.get(r, r)


def transform_card_to_merlin_payload(body_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform an AI Chat card structure into a flat Merlin-compatible payload.

    Args:
        body_type: "auto_sheet" or "home_sheet"
        data: The nested card data (tomador, inmueble/vehiculo, uso, poliza_actual)

    Returns:
        Flat dict ready for create_retarificacion_merlin_project_tool
    """
    ramo = "HOGAR" if body_type == "home_sheet" else "AUTO"
    payload: Dict[str, Any] = {"ramo": ramo}

    tomador = data.get("tomador", {})
    poliza = data.get("poliza_actual", {})

    for field in (
        "nombre", "apellido1", "apellido2", "dni", "fecha_nacimiento",
        "sexo", "estado_civil", "codigo_postal", "telefono", "email",
        "fecha_carnet",
    ):
        val = tomador.get(field)
        if val:
            payload[field] = val

    if payload.get("nombre"):
        payload["nombre"] = payload["nombre"].upper()
    if payload.get("apellido1"):
        payload["apellido1"] = payload["apellido1"].upper()
    if payload.get("apellido2"):
        payload["apellido2"] = payload["apellido2"].upper()
    if payload.get("dni"):
        payload["dni"] = payload["dni"].upper().replace(" ", "")

    fecha_efecto = poliza.get("fecha_efecto", "")
    if fecha_efecto:
        payload["fecha_efecto"] = _convert_fecha_efecto(fecha_efecto)

    if poliza.get("numero_poliza"):
        payload["numero_poliza"] = poliza["numero_poliza"]
    if poliza.get("company"):
        payload["aseguradora_actual"] = poliza["company"]
    if poliza.get("precio_anual") is not None:
        payload["precio_anual"] = poliza["precio_anual"]

    if ramo == "HOGAR":
        inmueble = data.get("inmueble", {})
        uso = data.get("uso", {})

        direccion = inmueble.get("direccion", "")
        if direccion:
            nombre_via, numero_calle = _parse_direccion(direccion)
            payload["nombre_via"] = nombre_via
            payload["numero_calle"] = numero_calle
        
        if inmueble.get("piso"):
            payload["piso"] = inmueble["piso"]
        if inmueble.get("puerta"):
            payload["puerta"] = inmueble["puerta"]

        cp = inmueble.get("codigo_postal") or tomador.get("codigo_postal")
        if cp:
            payload["codigo_postal"] = cp

        if inmueble.get("tipo_vivienda"):
            payload["tipo_vivienda"] = inmueble["tipo_vivienda"]

        if uso.get("tipo_uso"):
            payload["uso_vivienda"] = uso["tipo_uso"]

        if uso.get("regimen"):
            payload["regimen_ocupacion"] = _map_regimen(uso["regimen"])

    elif ramo == "AUTO":
        vehiculo = data.get("vehiculo", {})
        if vehiculo.get("matricula"):
            payload["matricula"] = vehiculo["matricula"].upper().replace(" ", "")

    logger.info(
        f"[CARD_TRANSFORMER] Transformed {body_type} card -> ramo={ramo}, "
        f"keys={list(payload.keys())}"
    )
    return payload
