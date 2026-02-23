"""Cliente para la API pública del Catastro (Sede Electrónica).

Consulta datos no protegidos de inmuebles (superficie, año de construcción, uso)
a partir de la dirección (provincia, municipio, tipo vía, nombre vía, número).

API: https://ovc.catastro.meh.es/ovcservweb/ovcswlocalizacionrc/ovccallejero.asmx
Endpoint usado: Consulta_DNPLOC (HTTP GET, sin autenticación, XML response).
"""

import logging
import time
import unicodedata
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CATASTRO_BASE_URL = (
    "https://ovc.catastro.meh.es/ovcservweb/ovcswlocalizacionrc/ovccallejero.asmx"
)
CATASTRO_TIMEOUT = 15
CATASTRO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/xml, text/xml, */*",
}
CATASTRO_RETRY_DELAY = 0.5  # seconds between retries on 400


def _remove_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _generate_street_name_variants(nombre_via: str) -> list:
    raw_name = nombre_via.strip().upper()
    name = _remove_accents(raw_name)

    variants = [name]
    if raw_name != name:
        variants.append(raw_name)

    if "'" in name:
        variants.extend([name.replace("'", ""), name.replace("'", " ")])
        if name.startswith("D'"):
            variants.extend([name[2:], "DE " + name[2:]])

    current_variants = list(variants)
    for v in current_variants:
        if v.startswith("DE LA "):
            variants.append(v[6:])
        elif v.startswith("DEL "):
            variants.append(v[4:])
        elif v.startswith("DE "):
            variants.append(v[3:])

    current_variants = list(variants)
    for v in current_variants:
        if "SS" in v:
            variants.append(v.replace("SS", "S"))
        if "NY" in v:
            variants.append(v.replace("NY", "N"))

    seen = set()
    final_variants = []
    for v in variants:
        v_clean = v.strip()
        if v_clean and v_clean not in seen:
            final_variants.append(v_clean)
            seen.add(v_clean)
    return final_variants[:15]


def _normalize_province_for_catastro(provincia: str) -> str:
    p = provincia.strip().upper()
    mapping = {
        "BALEARES": "ILLES BALEARS", "ISLAS BALEARES": "ILLES BALEARS",
        "BALEARS": "ILLES BALEARS", "GERONA": "GIRONA", "LERIDA": "LLEIDA",
        "ORENSE": "OURENSE", "CORUÑA": "A CORUÑA", "LA CORUÑA": "A CORUÑA",
        "VALENCIA/VALÈNCIA": "VALENCIA", "VALÈNCIA": "VALENCIA",
        "ALICANTE/ALACANT": "ALICANTE",
        "CASTELLÓN/CASTELLÓ": "CASTELLON", "CASTELLÓ": "CASTELLON",
        "CASTELLON/CASTELLO": "CASTELLON", "JAÉN": "JAEN",
    }
    if p in mapping:
        return mapping[p]
    if "/" in p:
        first_part = p.split("/")[0].strip()
        if first_part in mapping:
            return mapping[first_part]
        p = first_part
    normalized = _remove_accents(p)
    if normalized in mapping:
        return mapping[normalized]
    return normalized


def _generate_municipality_variants(municipio: str) -> list:
    raw = municipio.strip().upper()
    name = _remove_accents(raw)
    variants = [name]
    if raw != name:
        variants.append(raw)

    renames = {
        "PALMA DE MALLORCA": "PALMA", "EIVISSA": "EIVISSA",
        "IBIZA": "EIVISSA", "MAHON": "MAO", "GERONA": "GIRONA",
        "LERIDA": "LLEIDA", "ORENSE": "OURENSE",
    }
    for key, val in renames.items():
        if name == key:
            variants.append(val)
        elif name == val and key not in variants:
            variants.append(key)

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


def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return tag[:tag.index("}") + 1]
    return ""


def _find_text(parent: Optional[ET.Element], tag: str, ns: str) -> Optional[str]:
    if parent is None:
        return None
    elem = parent.find(f"{ns}{tag}") if ns else parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return None


def _extract_ref_catastral(idbi: Optional[ET.Element], ns: str) -> Optional[str]:
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
    candidates = []
    rcdnp_list = root.findall(f".//{ns}rcdnp") if ns else root.findall(".//rcdnp")
    for rcdnp in rcdnp_list[:10]:
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


def _parse_catastro_response(xml_text: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error(f"[CATASTRO] XML parse error: {exc}")
        return {"success": False, "error": "Error parseando respuesta del Catastro"}

    ns = _detect_namespace(root)

    error_elem = root.find(f".//{ns}err") if ns else root.find(".//err")
    if error_elem is not None:
        error_desc = _find_text(error_elem, "des", ns) or "Error desconocido"
        error_code = _find_text(error_elem, "cod", ns) or ""
        logger.warning(f"[CATASTRO] API error {error_code}: {error_desc}")
        candidates = _extract_candidates(root, ns)
        if candidates:
            return {"success": False, "error": error_desc, "multiple_results": True, "candidates": candidates}
        return {"success": False, "error": error_desc}

    bico = root.find(f".//{ns}bico") if ns else root.find(".//bico")
    if bico is None:
        candidates = _extract_candidates(root, ns)
        if candidates:
            return {"success": False, "error": "Se encontraron múltiples inmuebles.", "multiple_results": True, "candidates": candidates}
        return {"success": False, "error": "No se encontraron datos del inmueble"}

    bi = bico.find(f"{ns}bi") if ns else bico.find("bi")
    debi = bi.find(f"{ns}debi") if bi is not None else None
    idbi = bi.find(f"{ns}idbi") if bi is not None else None

    result: Dict[str, Any] = {"success": True}

    rc = _extract_ref_catastral(idbi, ns)
    if rc:
        result["referencia_catastral"] = rc

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
                    dp = _find_text(lourb, "dp", ns)
                    if dp:
                        result["codigo_postal"] = dp

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

    logger.info(
        f"[CATASTRO] Found: ref={result.get('referencia_catastral', '?')}, "
        f"superficie={result.get('superficie', '?')}m², "
        f"año={result.get('anio_construccion', '?')}"
    )
    return result


def _query_catastro_by_reference(provincia: str, municipio: str, referencia: str) -> Dict[str, Any]:
    url = f"{CATASTRO_BASE_URL}/Consulta_DNPRC"
    params = {"Provincia": provincia, "Municipio": municipio, "RC": referencia}
    logger.info(f"[CATASTRO] Querying by reference: {referencia}")
    try:
        resp = requests.get(url, params=params, headers=CATASTRO_HEADERS, timeout=CATASTRO_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": str(exc)}
    return _parse_catastro_response(resp.text)


def _try_catastro_address(
    url, provincia, municipio, tipo_via, nombre_via, numero,
    bloque="", escalera="", planta="", puerta="",
) -> Dict[str, Any]:
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
            params = {**common_params, "Provincia": provincia, "Municipio": muni, "Calle": variant}
            logger.info(f"[CATASTRO] Querying: {params['Provincia']}, {params['Municipio']}, {params['Sigla']} {params['Calle']} {params['Numero']}")

            max_retries = 2
            resp = None
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.get(url, params=params, headers=CATASTRO_HEADERS, timeout=CATASTRO_TIMEOUT)
                    if resp.status_code >= 500:
                        resp.raise_for_status()
                    if resp.status_code == 400:
                        body_preview = resp.text[:300] if resp.text else "(empty)"
                        logger.warning(
                            f"[CATASTRO] Got 400 for '{variant}' in '{muni}' "
                            f"(attempt {attempt+1}/{max_retries+1}). "
                            f"URL: {resp.request.url} | Body: {body_preview}"
                        )
                        if attempt < max_retries:
                            time.sleep(CATASTRO_RETRY_DELAY * (attempt + 1))
                            continue
                        break
                    break
                except requests.exceptions.RequestException as exc:
                    logger.error(f"[CATASTRO] Request failed: {exc}")
                    return {"success": False, "error": f"Error consultando el Catastro: {exc}"}

            if resp is None or resp.status_code == 400:
                continue

            last_result = _parse_catastro_response(resp.text)
            if last_result.get("success"):
                return last_result

            last_result["_resolved_municipio"] = muni
            error_msg = last_result.get("error", "").upper()

            if "PROVINCIA NO EXISTE" in error_msg:
                return last_result
            if "MUNICIPIO NO EXISTE" in error_msg:
                break
            if any(k in error_msg for k in ["VIA NO EXISTE", "NUMERO NO EXISTE", "INMUEBLE", "PARAMETROS", "NO EXISTE"]):
                continue
            return last_result

    return last_result


def consultar_catastro_por_direccion(
    provincia, municipio, tipo_via, nombre_via, numero,
    bloque="", escalera="", planta="", puerta="",
) -> Dict[str, Any]:
    url = f"{CATASTRO_BASE_URL}/Consulta_DNPLOC"
    normalized_provincia = _normalize_province_for_catastro(provincia)
    has_unit = bool((planta or "").strip() or (puerta or "").strip())

    result = _try_catastro_address(
        url, normalized_provincia, municipio, tipo_via, nombre_via, numero,
        bloque, escalera, planta, puerta,
    )
    if result.get("success"):
        return result

    # Fallback: retry without planta/puerta to find the building
    if has_unit:
        logger.info("[CATASTRO] Unit not found, retrying without planta/puerta...")
        result_building = _try_catastro_address(
            url, normalized_provincia, municipio, tipo_via, nombre_via, numero,
            bloque, escalera, "", "",
        )
        if result_building.get("success"):
            return result_building

        candidates = result_building.get("candidates", [])
        if candidates:
            first_ref = candidates[0].get("ref_catastral", "")
            first_muni = result_building.get("_resolved_municipio", "")
            if first_ref and first_muni:
                logger.info(f"[CATASTRO] Querying first candidate by ref: {first_ref}")
                ref_result = _query_catastro_by_reference(normalized_provincia, first_muni, first_ref)
                if ref_result.get("success"):
                    return ref_result

    return result
