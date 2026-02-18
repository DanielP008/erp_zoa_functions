"""Cliente para la API pública del Catastro (Sede Electrónica).

Consulta datos no protegidos de inmuebles (superficie, año de construcción, uso)
a partir de la dirección (provincia, municipio, tipo vía, nombre vía, número).

API: https://ovc.catastro.meh.es/ovcservweb/ovcswlocalizacionrc/ovccallejero.asmx
Endpoint usado: Consulta_DNPLOC (HTTP GET, sin autenticación, XML response).
"""

import logging
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CATASTRO_BASE_URL = (
    "https://ovc.catastro.meh.es/ovcservweb/ovcswlocalizacionrc/ovccallejero.asmx"
)
CATASTRO_TIMEOUT = 15


def _generate_street_name_variants(nombre_via: str) -> list:
    """Generate common spelling variants for Spanish street names.
    
    The Catastro API requires exact name matches. This generates variants
    to handle prepositions (DE, DEL, DE LA), bilingual spellings (SS/S),
    and Valencian/Catalan specificities (apostrophes, prepositions).
    """
    import unicodedata
    
    def remove_accents(s):
        return "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    raw_name = nombre_via.strip().upper()
    name = remove_accents(raw_name)
    
    variants = [name]
    if raw_name != name:
        variants.append(raw_name)

    # 1. Handle apostrophes (e.g., "D'EN RUBI" -> "EN RUBI", "DEN RUBI", "DE EN RUBI")
    if "'" in name:
        no_apostrophe = name.replace("'", "")
        space_apostrophe = name.replace("'", " ")
        variants.extend([no_apostrophe, space_apostrophe])
        
        # Specific Valencian/Catalan "D'" -> "DE " or removal
        if name.startswith("D'"):
            variants.append(name[2:])
            variants.append("DE " + name[2:])

    # 2. Prepositions DE, DEL, DE LA
    current_variants = list(variants)
    for v in current_variants:
        if v.startswith("DE "):
            variants.append(v[3:])
        elif v.startswith("DEL "):
            variants.append(v[4:])
        elif v.startswith("DE LA "):
            variants.append(v[6:])
        else:
            variants.append(f"DE {v}")

    # 3. Bilingual spellings (SS -> S)
    current_variants = list(variants)
    for v in current_variants:
        if "SS" in v:
            variants.append(v.replace("SS", "S"))
        if "NY" in v: # Catalan/Valencian NY -> N (sometimes)
            variants.append(v.replace("NY", "N"))

    # 4. Remove duplicates and keep order
    seen = set()
    final_variants = []
    for v in variants:
        v_clean = v.strip()
        if v_clean and v_clean not in seen:
            final_variants.append(v_clean)
            seen.add(v_clean)

    return final_variants[:15] # Limit to 15 attempts to avoid timeout


def _normalize_province_for_catastro(provincia: str) -> str:
    """Normalizes province names to the format accepted by the Catastro API.

    Verified empirically against the live Catastro API (Feb 2026).
    The API uses modern/official names, NOT the old Castilian names.
    E.g. it expects 'ILLES BALEARS' (not 'BALEARES'), 'GIRONA' (not 'GERONA').
    """
    import unicodedata

    p = provincia.strip().upper()

    # Exact mapping verified against the real Catastro API
    mapping = {
        # Baleares -> ILLES BALEARS (tested: BALEARES ✗, ILLES BALEARS ✓)
        "BALEARES": "ILLES BALEARS",
        "ISLAS BALEARES": "ILLES BALEARS",
        "BALEARS": "ILLES BALEARS",
        # Girona (tested: GIRONA ✓, GERONA ✗)
        "GERONA": "GIRONA",
        # Lleida (tested: LLEIDA ✓, LERIDA ✗)
        "LERIDA": "LLEIDA",
        # Ourense (tested: OURENSE ✓, ORENSE ✗)
        "ORENSE": "OURENSE",
        # A Coruña (tested: A CORUÑA ✓, CORUÑA ✗, LA CORUÑA ✗)
        "CORUÑA": "A CORUÑA",
        "LA CORUÑA": "A CORUÑA",
        # Valencia bilingual forms
        "VALENCIA/VALÈNCIA": "VALENCIA",
        "VALÈNCIA": "VALENCIA",
        # Alicante bilingual forms (both work, normalize to ALICANTE)
        "ALICANTE/ALACANT": "ALICANTE",
        # Castellón bilingual forms
        "CASTELLÓN/CASTELLÓ": "CASTELLON",
        "CASTELLÓ": "CASTELLON",
        "CASTELLON/CASTELLO": "CASTELLON",

        "JAÉN": "JAEN"
    }

    if p in mapping:
        return mapping[p]

    # Handle bilingual "X/Y" formats: take the first part
    if "/" in p:
        first_part = p.split("/")[0].strip()
        if first_part in mapping:
            return mapping[first_part]
        p = first_part

    # Remove accents only for non-special provinces (keep Ñ for A CORUÑA)
    normalized = "".join(
        c for c in unicodedata.normalize('NFD', p)
        if unicodedata.category(c) != 'Mn'
    )

    # Re-check mapping after accent removal
    if normalized in mapping:
        return mapping[normalized]

    return normalized


def _generate_municipality_variants(municipio: str) -> list:
    """Generate common municipality name variants for the Catastro API.

    E.g. 'PALMA DE MALLORCA' was renamed to 'PALMA' in 2016.
    The Catastro uses current official names.
    """
    import unicodedata

    raw = municipio.strip().upper()
    name = "".join(
        c for c in unicodedata.normalize('NFD', raw)
        if unicodedata.category(c) != 'Mn'
    )

    variants = [name]
    if raw != name:
        variants.append(raw)

    # Known municipal renames / common mismatches
    renames = {
        "PALMA DE MALLORCA": "PALMA",
        "EIVISSA": "EIVISSA",
        "IBIZA": "EIVISSA",
        "MAHON": "MAO",
        "GERONA": "GIRONA",
        "LERIDA": "LLEIDA",
        "ORENSE": "OURENSE",
    }
    for key, val in renames.items():
        if name == key:
            variants.append(val)
        elif name == val and key not in variants:
            variants.append(key)

    # Try removing common suffixes like "DE MALLORCA", "DE MAR", etc.
    for suffix in [" DE MALLORCA", " DE MAR", " DE LA FRONTERA", " DEL VALLES",
                   " DE HENARES", " DE LLOBREGAT", " DEL CAMPO"]:
        if name.endswith(suffix):
            variants.append(name[: -len(suffix)])

    seen = set()
    final = []
    for v in variants:
        v = v.strip()
        if v and v not in seen:
            final.append(v)
            seen.add(v)
    return final


def _query_catastro_by_reference(
    provincia: str, municipio: str, referencia: str
) -> Dict[str, Any]:
    """Query full property data using a cadastral reference (Consulta_DNPRC).

    Used as fallback when Consulta_DNPLOC cannot find the exact unit
    but the building exists.
    """
    url = f"{CATASTRO_BASE_URL}/Consulta_DNPRC"
    params = {
        "Provincia": provincia,
        "Municipio": municipio,
        "RC": referencia,
    }
    logger.info(f"[CATASTRO] Querying by reference: {referencia} in {municipio} ({provincia})")

    try:
        resp = requests.get(url, params=params, timeout=CATASTRO_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error(f"[CATASTRO] Reference query failed: {exc}")
        return {"success": False, "error": str(exc)}

    return _parse_catastro_response(resp.text)


def consultar_catastro_por_direccion(
    provincia: str,
    municipio: str,
    tipo_via: str,
    nombre_via: str,
    numero: str,
    bloque: str = "",
    escalera: str = "",
    planta: str = "",
    puerta: str = "",
) -> Dict[str, Any]:
    """Query the Catastro for property data by address.

    Retry strategy:
    - Municipality variants if "EL MUNICIPIO NO EXISTE" (error 22).
    - Street name variants if "LA VÍA NO EXISTE" (error 33) or "EL NUMERO NO EXISTE" (43).
    - When "NO EXISTE NINGÚN INMUEBLE" (error 5) and planta/puerta were given,
      retries WITHOUT planta/puerta; if that returns candidates, queries the
      first one by cadastral reference to get full building data.

    Returns:
        dict with success flag and property data.
    """
    url = f"{CATASTRO_BASE_URL}/Consulta_DNPLOC"
    normalized_provincia = _normalize_province_for_catastro(provincia)
    has_unit = bool(planta.strip() or puerta.strip())

    result = _try_catastro_address(
        url, normalized_provincia, municipio, tipo_via, nombre_via, numero,
        bloque, escalera, planta, puerta,
    )

    if result.get("success"):
        return result

    # Fallback: if unit (planta/puerta) was specified and error is "no property found",
    # retry without planta/puerta to find the building, then query by reference.
    error_upper = result.get("error", "").upper()
    if has_unit and ("INMUEBLE" in error_upper or "PARAMETROS" in error_upper):
        logger.info("[CATASTRO] Unit not found, retrying without planta/puerta...")
        result_building = _try_catastro_address(
            url, normalized_provincia, municipio, tipo_via, nombre_via, numero,
            bloque, escalera, "", "",
        )

        if result_building.get("success"):
            return result_building

        # Got multiple results: query the first candidate by reference
        candidates = result_building.get("candidates", [])
        if candidates:
            first_ref = candidates[0].get("ref_catastral", "")
            first_muni = result_building.get("_resolved_municipio", "")
            if first_ref and first_muni:
                logger.info(f"[CATASTRO] Querying first candidate by ref: {first_ref}")
                ref_result = _query_catastro_by_reference(
                    normalized_provincia, first_muni, first_ref
                )
                if ref_result.get("success"):
                    return ref_result

    return result


def _try_catastro_address(
    url: str,
    provincia: str,
    municipio: str,
    tipo_via: str,
    nombre_via: str,
    numero: str,
    bloque: str = "",
    escalera: str = "",
    planta: str = "",
    puerta: str = "",
) -> Dict[str, Any]:
    """Inner loop: try municipality + street variants for a single query."""
    common_params = {
        "Sigla": tipo_via.strip().upper(),
        "Numero": str(numero).strip(),
        "Bloque": (bloque or "").strip(),
        "Escalera": (escalera or "").strip(),
        "Planta": (planta or "").strip(),
        "Puerta": (puerta or "").strip(),
    }

    street_variants = _generate_street_name_variants(nombre_via)
    muni_variants = _generate_municipality_variants(municipio)
    last_result: Dict[str, Any] = {"success": False, "error": "Sin resultados"}

    for muni in muni_variants:
        for variant in street_variants:
            params = {
                **common_params,
                "Provincia": provincia,
                "Municipio": muni,
                "Calle": variant,
            }
            logger.info(
                f"[CATASTRO] Querying: {params['Provincia']}, {params['Municipio']}, "
                f"{params['Sigla']} {params['Calle']} {params['Numero']}"
            )

            try:
                resp = requests.get(url, params=params, timeout=CATASTRO_TIMEOUT)
                resp.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.error(f"[CATASTRO] Request failed: {exc}")
                return {"success": False, "error": f"Error consultando el Catastro: {exc}"}

            last_result = _parse_catastro_response(resp.text)

            if last_result.get("success"):
                return last_result

            # Store the municipality that was accepted for later use
            last_result["_resolved_municipio"] = muni

            error_msg = last_result.get("error", "").upper()

            # Province error -> no point retrying
            if "PROVINCIA NO EXISTE" in error_msg:
                logger.error(f"[CATASTRO] Province '{provincia}' not recognized")
                return last_result

            # Municipality error -> try next municipality variant
            if "MUNICIPIO NO EXISTE" in error_msg:
                logger.info(f"[CATASTRO] Municipality '{muni}' not found, trying next variant...")
                break

            # Street not found or number not found -> try next street variant
            if "VIA NO EXISTE" in error_msg or "NUMERO NO EXISTE" in error_msg:
                logger.info(f"[CATASTRO] Street variant '{variant}' not found, trying next...")
                continue

            # "NO EXISTE NINGÚN INMUEBLE" (error 5) -> street exists but unit doesn't
            if "INMUEBLE" in error_msg or "PARAMETROS" in error_msg:
                logger.info(f"[CATASTRO] No property at unit level for '{variant}', trying next...")
                continue

            # Any other "NO EXISTE" -> try next variant
            if "NO EXISTE" in error_msg:
                logger.info(f"[CATASTRO] '{variant}' not found, trying next...")
                continue

            # Other errors -> return immediately
            return last_result

    return last_result


def _parse_catastro_response(xml_text: str) -> Dict[str, Any]:
    """Parse the Catastro XML response extracting property data."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error(f"[CATASTRO] XML parse error: {exc}")
        return {"success": False, "error": "Error parseando respuesta del Catastro"}

    ns = _detect_namespace(root)

    # Check for errors
    error_elem = root.find(f".//{ns}err") if ns else root.find(".//err")
    if error_elem is not None:
        error_desc = _find_text(error_elem, "des", ns) or "Error desconocido"
        error_code = _find_text(error_elem, "cod", ns) or ""
        logger.warning(f"[CATASTRO] API error {error_code}: {error_desc}")

        # If multiple properties found, return list of candidates
        candidates = _extract_candidates(root, ns)
        if candidates:
            return {
                "success": False,
                "error": error_desc,
                "multiple_results": True,
                "candidates": candidates,
            }
        return {"success": False, "error": error_desc}

    # Look for property data (bico = bien inmueble completo)
    bico = root.find(f".//{ns}bico") if ns else root.find(".//bico")
    if bico is None:
        # Try to find list of properties (lrcdnp)
        candidates = _extract_candidates(root, ns)
        if candidates:
            return {
                "success": False,
                "error": "Se encontraron múltiples inmuebles. Especifica planta y puerta.",
                "multiple_results": True,
                "candidates": candidates,
            }
        return {"success": False, "error": "No se encontraron datos del inmueble"}

    # Extract property details
    bi = bico.find(f"{ns}bi") if ns else bico.find("bi")
    debi = bi.find(f"{ns}debi") if bi is not None else None
    lcons = bi.find(f"{ns}lcons") if bi is not None else None
    idbi = bi.find(f"{ns}idbi") if bi is not None else None

    result: Dict[str, Any] = {"success": True}

    # Cadastral reference
    rc = _extract_ref_catastral(idbi, ns)
    if rc:
        result["referencia_catastral"] = rc

    # Address from response
    dt = idbi.find(f"{ns}dt") if idbi is not None else None
    if dt is not None:
        locs = dt.find(f"{ns}locs") if ns else dt.find("locs")
        if locs is not None:
            lous = locs.find(f"{ns}lous") if ns else locs.find("lous")
            if lous is not None:
                lourb = lous.find(f"{ns}lourb") if ns else lous.find("lourb")
                if lourb is not None:
                    result["bloque"] = _find_text(lourb, "bq", ns) or ""
                    result["escalera"] = _find_text(lourb, "es", ns) or ""
                    result["planta"] = _find_text(lourb, "pt", ns) or ""
                    result["puerta"] = _find_text(lourb, "pu", ns) or ""
                    # Código postal (dp element)
                    dp = _find_text(lourb, "dp", ns)
                    if dp:
                        result["codigo_postal"] = dp

    # Economic/construction data
    if debi is not None:
        sfc = _find_text(debi, "sfc", ns)
        if sfc:
            try:
                result["superficie"] = int(sfc)
            except ValueError:
                result["superficie"] = sfc

        ant = _find_text(debi, "ant", ns)
        if ant:
            try:
                result["anio_construccion"] = int(ant)
            except ValueError:
                result["anio_construccion"] = ant

        uso = _find_text(debi, "luso", ns)
        if uso:
            result["uso"] = uso

        cpt = _find_text(debi, "cpt", ns)
        if cpt:
            result["coeficiente_participacion"] = cpt

    # Construction units (lcons) - extract to determine type
    if lcons is not None:
        units = lcons.findall(f"{ns}cons") if ns else lcons.findall("cons")
        construction_units = []
        for unit in units:
            lcd = _find_text(unit, "lcd", ns) or ""
            dfcons = unit.find(f"{ns}dfcons") if ns else unit.find("dfcons")
            stl = _find_text(dfcons, "stl", ns) if dfcons is not None else None
            construction_units.append({
                "uso": lcd,
                "superficie": int(stl) if stl and stl.isdigit() else stl,
            })
        if construction_units:
            result["unidades_constructivas"] = construction_units

    logger.info(
        f"[CATASTRO] Found: ref={result.get('referencia_catastral', '?')}, "
        f"superficie={result.get('superficie', '?')}m², "
        f"año={result.get('anio_construccion', '?')}, "
        f"uso={result.get('uso', '?')}, "
        f"CP={result.get('codigo_postal', '?')}"
    )
    return result


def _detect_namespace(root: ET.Element) -> str:
    """Detect XML namespace from root element tag."""
    tag = root.tag
    if tag.startswith("{"):
        ns_end = tag.index("}")
        return tag[:ns_end + 1]
    return ""


def _find_text(parent: Optional[ET.Element], tag: str, ns: str) -> Optional[str]:
    """Find text content of a child element, namespace-aware."""
    if parent is None:
        return None
    elem = parent.find(f"{ns}{tag}") if ns else parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return None


def _extract_ref_catastral(idbi: Optional[ET.Element], ns: str) -> Optional[str]:
    """Extract full cadastral reference from idbi element."""
    if idbi is None:
        return None
    rc = idbi.find(f"{ns}rc") if ns else idbi.find("rc")
    if rc is None:
        return None
    pc1 = _find_text(rc, "pc1", ns) or ""
    pc2 = _find_text(rc, "pc2", ns) or ""
    car = _find_text(rc, "car", ns) or ""
    cc1 = _find_text(rc, "cc1", ns) or ""
    cc2 = _find_text(rc, "cc2", ns) or ""
    return f"{pc1}{pc2}{car}{cc1}{cc2}" if pc1 else None


def _extract_candidates(root: ET.Element, ns: str) -> list:
    """Extract list of candidate properties when multiple matches found.

    The Catastro XML nests the reference inside <rc> with fields:
    pc1, pc2, car, cc1, cc2  (full 20-char reference).
    """
    candidates = []
    rcdnp_list = root.findall(f".//{ns}rcdnp") if ns else root.findall(".//rcdnp")
    for rcdnp in rcdnp_list[:10]:
        # Extract cadastral reference from <rc> child
        rc_elem = rcdnp.find(f"{ns}rc") if ns else rcdnp.find("rc")
        if rc_elem is not None:
            pc1 = _find_text(rc_elem, "pc1", ns) or ""
            pc2 = _find_text(rc_elem, "pc2", ns) or ""
            car = _find_text(rc_elem, "car", ns) or ""
            cc1 = _find_text(rc_elem, "cc1", ns) or ""
            cc2 = _find_text(rc_elem, "cc2", ns) or ""
            ref = f"{pc1}{pc2}{car}{cc1}{cc2}"
        else:
            ref = ""

        dt = rcdnp.find(f"{ns}dt") if ns else rcdnp.find("dt")
        locs = dt.find(f"{ns}locs") if dt is not None else None
        lous = locs.find(f"{ns}lous") if locs is not None else None
        lourb = lous.find(f"{ns}lourb") if lous is not None else None
        loint = lourb.find(f"{ns}loint") if lourb is not None else None

        candidate: Dict[str, Any] = {"ref_catastral": ref}
        if loint is not None:
            candidate["planta"] = _find_text(loint, "pt", ns) or ""
            candidate["puerta"] = _find_text(loint, "pu", ns) or ""
        if lourb is not None:
            candidate["bloque"] = _find_text(lourb, "bq", ns) or ""
            candidate["escalera"] = _find_text(lourb, "es", ns) or ""

        candidates.append(candidate)

    return candidates
