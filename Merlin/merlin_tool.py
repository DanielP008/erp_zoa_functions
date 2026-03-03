"""Merlin Multitarificador LLM Functions.

Tool wrappers that expose Merlin functionality to the AI and backend.
"""
import logging
import json
import os
from typing import Dict, Any

from .merlin_client import MerlinClient, get_vehicle_info_by_matricula, get_town_by_cp
from catastro_client import consultar_catastro_por_direccion

logger = logging.getLogger(__name__)

def _extract_tarificador_config(context: dict) -> dict:
    if not context or not isinstance(context, dict):
        return {}
    if "tarificador" in context:
        return context.get("tarificador", {})
    return context

def get_town_by_cp_merlin_tool(cp: str, context: dict = None) -> Dict[str, Any]:
    """Get town info by postal code for Merlin projects."""
    cfg = _extract_tarificador_config(context)
    return get_town_by_cp(cp, cfg)

def consulta_vehiculo_merlin_tool(matricula: str, context: dict = None) -> Dict[str, Any]:
    """Lookup vehicle info via DGT for Merlin projects."""
    cfg = _extract_tarificador_config(context)
    return get_vehicle_info_by_matricula(matricula, cfg)

def consultar_catastro_merlin_tool(
    provincia: str, municipio: str, tipo_via: str, nombre_via: str, numero: str, 
    bloque: str = "", escalera: str = "", planta: str = "", puerta: str = ""
) -> Dict[str, Any]:
    """Lookup property info via Catastro for Merlin projects."""
    return consultar_catastro_por_direccion(
        provincia, municipio, tipo_via, nombre_via, numero, 
        bloque, escalera, planta, puerta
    )

def create_retarificacion_merlin_project_tool(payload: dict, context: dict = None) -> str:
    """Create Merlin project with enrichment logic and initiate rating.
    
    Args:
        payload: The LLM/backend JSON containing the required info.
        context: Context dictionary with the 'tarificador' structure and environment.
    """
    logger.info("[MERLIN_TOOL] Starting Merlin project creation via tool...")
    
    try:
        company_config = context if context else {}
        cfg = _extract_tarificador_config(context)
        
        ramo = str(payload.get("ramo", "AUTO")).upper()
        cp = payload.get("codigo_postal")

        # 1. Enrichment for AUTO only (Vehicle info)
        if ramo == "AUTO":
            matricula = payload.get("matricula")
            if matricula:
                dgt_result = get_vehicle_info_by_matricula(matricula, cfg)
                if dgt_result.get("success"):
                    v = dgt_result.get("vehiculo", {})
                    payload.update({
                        "marca": v.get("marca"),
                        "modelo": v.get("modelo"),
                        "version": v.get("version"),
                        "combustible": v.get("combustible"),
                        "fecha_matriculacion": v.get("fecha_matriculacion"),
                        "km_anuales": v.get("km_anuales"),
                        "km_totales": v.get("km_totales"),
                        "tipo_de_garaje": v.get("garaje") or payload.get("tipo_de_garaje", "COLECTIVO"),
                        "id_auto_base7": v.get("id_auto_base7"),
                        "id_tipo_base7": v.get("id_tipo_base7"),
                        "id_categoria_base7": v.get("id_categoria_base7"),
                        "id_clase_base7": v.get("id_clase_base7"),
                        "potencia": v.get("potencia_cv"),
                        "cilindrada": v.get("cilindrada"),
                        "precio_vp": v.get("precio_vp"),
                    })

        # 2. Enrichment for both (Town/CP)
        if cp:
            try:
                town_result = get_town_by_cp(cp, cfg)
                if town_result.get("success"):
                    payload.update({
                        "poblacion": town_result.get("poblacion"),
                        "id_provincia": town_result.get("id_provincia"),
                        "descripcion_provincia": town_result.get("descripcion_provincia"),
                    })
                else:
                    logger.warning(f"[MERLIN_TOOL] Town enrichment failed for CP {cp}: {town_result.get('error')}")
            except Exception as e:
                logger.error(f"[MERLIN_TOOL] Town enrichment unexpected error for CP {cp}: {e}")

        # 3. Catastro enrichment for HOGAR
        if ramo == "HOGAR":
            nombre_via = payload.get("nombre_via", "")
            numero_calle = str(payload.get("numero_calle", ""))
            tipo_via = payload.get("id_tipo_via", "CL")
            provincia_desc = payload.get("descripcion_provincia", "")
            municipio_desc = payload.get("poblacion", "")
            piso = payload.get("piso", "")
            puerta = payload.get("puerta", "")

            if nombre_via and numero_calle and provincia_desc and municipio_desc:
                catastro_result = consultar_catastro_por_direccion(
                    provincia=provincia_desc,
                    municipio=municipio_desc,
                    tipo_via=tipo_via,
                    nombre_via=nombre_via,
                    numero=numero_calle,
                    bloque=payload.get("bloque", ""),
                    escalera=payload.get("escalera", ""),
                    planta=piso,
                    puerta=puerta,
                )

                if catastro_result.get("success"):
                    cat_superficie = catastro_result.get("superficie")
                    cat_anio = catastro_result.get("anio_construccion")
                    cat_ref = catastro_result.get("referencia_catastral")

                    if cat_superficie:
                        payload["superficie_vivienda"] = int(cat_superficie)
                    if cat_anio:
                        payload["anio_construccion"] = int(cat_anio)
                    if cat_ref:
                        payload["referencia_catastral"] = cat_ref
                else:
                    logger.warning(f"[MERLIN_TOOL] Catastro Enrichment failed: {catastro_result.get('error', 'unknown')}")

            # Fallback values / Defaults
            if "superficie_vivienda" not in payload: payload["superficie_vivienda"] = 90
            if "anio_construccion" not in payload: payload["anio_construccion"] = 2000
            
            defaults = {
                "tipo_vivienda": "PISO_EN_ALTO",
                "situacion_vivienda": "NUCLEO_URBANO",
                "regimen_ocupacion": "PROPIEDAD",
                "uso_vivienda": "VIVIENDA_HABITUAL",
                "utilizacion_vivienda": "VIVIENDA_EXCLUSIVAMENTE",
                "calidad_construccion": "NORMAL",
                "materiales_construccion": "SOLIDA_PIEDRAS_LADRILLOS_ETC",
                "tipo_tuberias": "POLIPROPILENO",
                "tipo_puerta": "DE_MADERA_PVC_METALICA_ETC",
                "alarma": "SIN_ALARMA",
                "tiene_piscina": False,
                "alquiler_vacacional": False,
                "vivienda_rehabilitada": False,
                "numero_personas_vivienda": "3",
                "numero_habitaciones": "3",
            }
            for k, v in defaults.items():
                if k not in payload: payload[k] = v

            # Capitals: recommended values are fetched from Merlin after project
            # creation (inside merlin_client.crear_proyecto_completo).
            # We do NOT inject defaults here anymore, so the client can detect missing capitals
            # and return recommendations for the user to choose.
            pass

        # 4. Create project using the original Merlin client
        from .merlin_client import create_merlin_project
        result = create_merlin_project(payload, company_config)
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as exc:
        logger.exception("[MERLIN_TOOL] Error in create_retarificacion_merlin_project_tool")
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
