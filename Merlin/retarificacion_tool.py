"""Tools para tarificación en Merlin Multitarificador (Auto y Hogar).

Contiene tres herramientas:
  1. consulta_vehiculo_tool: Consulta DGT por matrícula y muestra datos al cliente.
  2. get_town_by_cp_tool: Obtiene población por código postal.
  3. create_retarificacion_project_tool: Crea el proyecto final en Merlin (Auto o Hogar).
"""

import json
import logging
from langchain.tools import tool
from Merlin.merlin_client import create_merlin_project, get_vehicle_info_by_matricula, get_town_by_cp
from ebroker_functions import get_all_policys_by_client_risk
from catastro_client import consultar_catastro_por_direccion

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS_AUTO = ["dni", "matricula", "fecha_efecto"]
_REQUIRED_FIELDS_HOGAR = ["dni", "codigo_postal", "fecha_efecto", "nombre_via", "numero_calle"]


# ============================================================================
# TOOL 1: Consulta de vehículo (DGT) - Solo AUTO
# ============================================================================

@tool
def consulta_vehiculo_tool(matricula: str) -> dict:
    """
    Consulta los datos técnicos de un vehículo en la DGT a partir de su matrícula.
    Devuelve marca, modelo, versión, combustible, garaje, km, fechas, etc.

    Usa esta herramienta en cuanto el cliente proporcione la matrícula.
    Muestra los datos al cliente en una LISTA DE PUNTOS y pregúntale si son correctos.

    Args:
        matricula: Matrícula del vehículo (ej: "3492GYW")

    Returns:
        dict con los datos del vehículo recuperados de la DGT.
    """
    matricula = matricula.strip().upper()
    logger.info(f"[CONSULTA_VEHICULO] Looking up vehicle: {matricula}")
    dgt_result = get_vehicle_info_by_matricula(matricula)

    if dgt_result.get("success"):
        v = dgt_result.get("vehiculo", {})
        logger.info(
            f"[CONSULTA_VEHICULO] Found: {v.get('marca')} {v.get('modelo')} "
            f"({v.get('version')}) - {v.get('combustible_descripcion')}"
        )

        def clean(val):
            if val is None:
                return "No especificado"
            s = str(val).strip()
            return s if s else "No especificado"

        return {
            "success": True,
            "datos_vehiculo": {
                "Marca": clean(v.get("marca")),
                "Modelo": clean(v.get("modelo")),
                "Versión": clean(v.get("version")),
                "Combustible": clean(v.get("combustible_descripcion")),
                "Fecha de Matriculación": clean(v.get("fecha_matriculacion")),
                "Kilómetros Anuales": clean(v.get("km_anuales")),
                "Kilómetros Totales": clean(v.get("km_totales")),
                "Garaje": clean(v.get("garaje")),
            },
        }
    else:
        logger.error(f"[CONSULTA_VEHICULO] Failed: {dgt_result.get('error')}")
        return dgt_result


# ============================================================================
# TOOL 2: Consulta de población (CP) - Ambos ramos
# ============================================================================

@tool
def get_town_by_cp_tool(cp: str) -> dict:
    """
    Obtiene la población y provincia a partir de un código postal.

    Usa esta herramienta en cuanto el cliente proporcione el código postal.
    Muestra la población al cliente y pregúntale si es correcta.

    Args:
        cp: Código postal (ej: "28001")

    Returns:
        dict con la población y provincia.
    """
    cp = cp.strip()
    logger.info(f"[GET_TOWN_BY_CP] Looking up CP: {cp}")
    result = get_town_by_cp(cp)
    if result.get("success"):
        logger.info(f"[GET_TOWN_BY_CP] Found: {result.get('poblacion')} ({result.get('descripcion_provincia')})")
    else:
        logger.error(f"[GET_TOWN_BY_CP] Failed: {result.get('error')}")
    return result


# ============================================================================
# TOOL 3: Consulta de Catastro (Hogar)
# ============================================================================

@tool
def consultar_catastro_tool(
    provincia: str,
    municipio: str,
    tipo_via: str,
    nombre_via: str,
    numero: str,
    bloque: str = "",
    escalera: str = "",
    planta: str = "",
    puerta: str = "",
    piso: str = "",  # Alias for planta
    numero_personas: str = "3",
    tipo_vivienda: str = "PISO_EN_ALTO",
) -> str:
    """
    Consulta los datos de una vivienda en el Catastro (superficie, año construcción, uso).

    Usa esta herramienta en cuanto el cliente proporcione la dirección completa en Hogar.
    Muestra los datos recuperados (año y superficie) al cliente y pregúntale si son correctos.

    Args:
        provincia: Nombre de la provincia (ej: "MADRID")
        municipio: Nombre del municipio/población (ej: "MADRID")
        tipo_via: Código del tipo de vía (CL, AV, PZ, PO, RD, CLZ, CM)
        nombre_via: Nombre de la vía (ej: "ALCALA")
        numero: Número de la vía (ej: "5")
        bloque: Bloque (opcional)
        escalera: Escalera (opcional)
        planta: Planta (ej: "5")
        puerta: Puerta (ej: "A")
        piso: Alias para planta (opcional)
        numero_personas: Número de personas en la vivienda (ej: "3")
        tipo_vivienda: Tipo de vivienda (PISO_EN_ALTO, PISO_EN_BAJO, ATICO, CHALET_O_VIVIENDA_UNIFAMILIAR, CHALET_O_VIVIENDA_ADOSADA)
    """
    # Combine planta/piso
    final_planta = planta or piso
    
    # La normalización de provincia ahora se maneja internamente en consultar_catastro_por_direccion

    logger.info(f"[CONSULTAR_CATASTRO] Looking up: {tipo_via} {nombre_via} {numero} {final_planta} {puerta} in {municipio} ({provincia})")
    
    try:
        result = consultar_catastro_por_direccion(
            provincia=provincia,
            municipio=municipio,
            tipo_via=tipo_via,
            nombre_via=nombre_via,
            numero=numero,
            bloque=bloque,
            escalera=escalera,
            planta=final_planta,
            puerta=puerta,
        )
        
        if result.get("success"):
            anio = result.get("anio_construccion", "NO DISPONIBLE")
            superficie = result.get("superficie", "NO DISPONIBLE")
            ref = result.get("referencia_catastral", "")
            uso_catastro = result.get("uso", "")
            cp_catastro = result.get("codigo_postal", "")
            
            # Inferencia básica de uso
            uso_vivienda = "VIVIENDA_HABITUAL"
            utilizacion = "VIVIENDA_EXCLUSIVAMENTE"
            if uso_catastro and not uso_catastro.startswith("R"):
                 pass

            logger.info(f"[CONSULTAR_CATASTRO] SUCCESS - Año: {anio}, Superficie: {superficie}m², Ref: {ref}, CP: {cp_catastro}")
            
            # Calcular capital continente basado en JSON de precios del Ministerio y factores por tipología
            precio_m2_base = 1500
            capital_continente = 0
            capital_contenido = 25000
            factor_tipologia = 1.0
            
            # Factores de corrección por tipo de vivienda (Coste de reconstrucción)
            factores = {
                "PISO_EN_ALTO": 1.0,  # Base: comparte estructura, tejado y cimentación con otros.
                "ATICO": 1.0,         # Similar a piso en alto en términos de estructura compartida.
                "PISO_EN_BAJO": 1.1,  # Mayor riesgo de humedades y elementos constructivos propios a nivel de suelo.
                "CHALET_O_VIVIENDA_ADOSADA": 1.2, # Tejado propio y al menos 2 fachadas independientes (más materiales).
                "CHALET_O_VIVIENDA_UNIFAMILIAR": 1.4 # Máximo coste: 4 fachadas, tejado y cimentación 100% propios.
            }

            # Factores para el cálculo del contenido (€/m2 según tipología)
            factores_contenido = {
                "PISO_EN_ALTO": 250,
                "ATICO": 350,
                "PISO_EN_BAJO": 250,
                "CHALET_O_VIVIENDA_ADOSADA": 350,
                "CHALET_O_VIVIENDA_UNIFAMILIAR": 450
            }
            
            factor_tipologia = factores.get(tipo_vivienda, 1.0)
            precio_m2_contenido = factores_contenido.get(tipo_vivienda, 250)
            
            logger.info(f"[CONSULTAR_CATASTRO] Calculando capitales: tipo={tipo_vivienda}, factor_cont={factor_tipologia}, m2_contenido={precio_m2_contenido}")
            
            if str(superficie).isdigit():
                try:
                    import os
                    json_path = os.path.join(os.path.dirname(__file__), "..", "precios_m2.json") #Actulizado a fecha de Diciembre de 2025
                    logger.info(f"[CONSULTAR_CATASTRO] Leyendo precios desde: {json_path}")
                    with open(json_path, "r", encoding="utf-8") as f:
                        precios = json.load(f)
                    
                    # Intentar buscar por municipio, luego por provincia
                    mun_upper = str(municipio).strip().upper()
                    prov_upper = str(provincia).strip().upper()
                    logger.info(f"[CONSULTAR_CATASTRO] Buscando zona: mun={mun_upper}, prov={prov_upper}")
                    
                    if mun_upper in precios:
                        precio_m2_base = precios[mun_upper]
                        logger.info(f"[CONSULTAR_CATASTRO] Encontrado precio por municipio: {precio_m2_base}")
                    elif prov_upper in precios:
                        precio_m2_base = precios[prov_upper]
                        logger.info(f"[CONSULTAR_CATASTRO] Encontrado precio por provincia: {precio_m2_base}")
                    else:
                        precio_m2_base = precios.get("DEFAULT", 1500)
                        logger.info(f"[CONSULTAR_CATASTRO] Usando precio DEFAULT: {precio_m2_base}")
                        
                    # Aplicar factor de tipología sobre el precio base de la zona para Continente
                    precio_final_m2 = float(precio_m2_base) * factor_tipologia
                    capital_continente = int(superficie) * int(precio_final_m2)
                    
                    # Calcular Contenido basado en m2 y tipología
                    capital_contenido = int(superficie) * precio_m2_contenido
                    
                    logger.info(f"[CONSULTAR_CATASTRO] Calculo final: Continente={capital_continente}€, Contenido={capital_contenido}€")
                except Exception as e:
                    logger.error(f"[CONSULTAR_CATASTRO] Error calculando capitales: {e}")
                    capital_continente = int(superficie) * 1500
                    capital_contenido = 25000
            else:
                logger.warning(f"[CONSULTAR_CATASTRO] Superficie no es digito: {superficie}")
            
            # Construimos un string con los datos encontrados y los valores por defecto para que el LLM los presente
            return (
                f"DATOS ENCONTRADOS: Año: {anio}, Superficie: {superficie}, Ref: {ref}, CP: {cp_catastro}\n"
                f"VALORES SUGERIDOS (CONFIRMAR CON CLIENTE):\n"
                f"- Situación: NUCLEO_URBANO\n"
                f"- Régimen: PROPIEDAD\n"
                f"- Uso: {uso_vivienda}\n"
                f"- Utilización: {utilizacion}\n"
                f"- Nº Personas: {numero_personas}\n"
                f"- Calidad: NORMAL\n"
                f"- Materiales: SOLIDA_PIEDRAS_LADRILLOS_ETC\n"
                f"- Tuberías: POLIPROPILENO\n"
                f"PROTECCIONES (POR DEFECTO):\n"
                f"- Puerta principal: DE_MADERA_PVC_METALICA_ETC\n"
                f"- Puerta secundaria: NO_TIENE\n"
                f"- Ventanas: SIN_PROTECCION\n"
                f"- Alarmas (Robo/Incendio/Agua): SIN_ALARMA\n"
                f"- Caja fuerte: NO_TIENE\n"
                f"- Vigilancia: SIN_VIGILANCIA\n"
                f"CAPITALES RECOMENDADOS (USAR EN PASO 6):\n"
                f"- Capital Continente Recomendado: {capital_continente} € (Precio base zona: {int(precio_m2_base)} €/m² | Factor tipo {tipo_vivienda}: {factor_tipologia}x)\n"
                f"- Capital Contenido Recomendado: {capital_contenido} € (Calculado a {precio_m2_contenido} €/m² según tipo {tipo_vivienda})"
            )
        else:
            err = result.get('error', 'Desconocido')
            logger.error(f"[CONSULTAR_CATASTRO] Failed: {err}")
            return f"NO SE ENCONTRARON DATOS: {err}. Usa valores por defecto."
            
    except Exception as e:
        logger.error(f"[CONSULTAR_CATASTRO] EXCEPTION: {e}", exc_info=True)
        return f"ERROR TECNICO: {str(e)}. Usa valores por defecto."


# ============================================================================
# TOOL 4: Creación de proyecto en Merlin (Auto o Hogar)
# ============================================================================

@tool
def create_retarificacion_project_tool(data: str) -> dict:
    """
    Crea un proyecto de tarificación de seguro (Auto o Hogar) en Merlin.
    Enriquece automáticamente los datos usando la DGT, el ERP, el Catastro y servicios de localización.
    
    Si la tarificación tiene éxito, devuelve el objeto 'proyecto' completo con las ofertas de las aseguradoras
    en el campo 'tarificaciones' o 'afinaciones'.

    Input: JSON string con los datos recopilados.

    Campo de ramo:
    - ramo: str ("AUTO" o "HOGAR", por defecto "AUTO")

    Campos comunes obligatorios:
    - dni: str (NIF/DNI del tomador)
    - fecha_efecto: str ("YYYY-MM-DD")

    Campos adicionales para AUTO:
    - matricula: str (matrícula del vehículo)

    Campos adicionales para HOGAR (obligatorios):
    - codigo_postal: str
    - nombre_via: str (nombre de la calle, ej: "Gran Vía")
    - numero_calle: str (número del edificio, ej: "3")
    - piso: str (opcional, ej: "3")
    - puerta: str (opcional, ej: "Izquierda")
    - numero_personas_vivienda: str (ej: "3")

    Campos adicionales para HOGAR (opcionales, se obtienen automáticamente del Catastro si no se proporcionan):
    - id_tipo_via: str ("CL", "AV", "PZ", etc. - por defecto "CL")
    - anio_construccion: int (año de construcción - auto del Catastro)
    - superficie_vivienda: int (metros cuadrados - auto del Catastro)
    - tipo_vivienda: str ("PISO_EN_ALTO", "CHALET_O_VIVIENDA_UNIFAMILIAR", etc. - por defecto "PISO_EN_ALTO")
    - capital_continente: int (valor reconstrucción confirmado por el cliente, ej: 240000)
    - capital_contenido: int (valor mobiliario confirmado por el cliente, ej: 25000)
    - situacion_vivienda: str (ej: "NUCLEO_URBANO")
    - regimen_ocupacion: str (ej: "PROPIEDAD")
    - uso_vivienda: str (ej: "VIVIENDA_HABITUAL")
    - utilizacion_vivienda: str (ej: "VIVIENDA_EXCLUSIVAMENTE")
    - calidad_construccion: str (ej: "NORMAL")
    - materiales_construccion: str (ej: "SOLIDA_PIEDRAS_LADRILLOS_ETC")
    - tipo_tuberias: str (ej: "POLIPROPILENO")
    - bloque: str (opcional)
    - escalera: str (opcional)
    - planta: str (opcional)
    - puerta: str (opcional)
    """
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return {"success": False, "error": "Formato JSON inválido"}

    ramo = str(payload.get("ramo", "AUTO")).upper()

    required = _REQUIRED_FIELDS_AUTO if ramo == "AUTO" else _REQUIRED_FIELDS_HOGAR
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return {
            "success": False,
            "error": f"Campos obligatorios faltantes para {ramo}: {', '.join(missing)}",
        }

    dni = payload.get("dni")
    cp = payload.get("codigo_postal")

    # 1. Enrichment for AUTO only
    if ramo == "AUTO":
        matricula = payload.get("matricula")
        logger.info(f"[RETARIFICACION] Enriching with DGT for {matricula}")
        dgt_result = get_vehicle_info_by_matricula(matricula)
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

        if dni and matricula:
            company_id = payload.get("company_id", "")
            if company_id:
                logger.info(f"[RETARIFICACION] Checking ERP for policy (DNI={dni}, Risk={matricula})")
                erp_result = get_all_policys_by_client_risk(dni, matricula, company_id)
                if erp_result.get("success"):
                    policy = erp_result.get("policy", {})
                    payload.update({
                        "aseguradora_actual": policy.get("company_name") or policy.get("company_id"),
                        "num_poliza": policy.get("number"),
                    })

    # 2. Enrichment for both (Town/CP)
    if cp:
        logger.info(f"[RETARIFICACION] Enriching town for CP {cp}")
        town_result = get_town_by_cp(cp)
        if town_result.get("success"):
            payload.update({
                "poblacion": town_result.get("poblacion"),
                "id_provincia": town_result.get("id_provincia"),
                "descripcion_provincia": town_result.get("descripcion_provincia"),
            })

    # 3. Catastro enrichment for HOGAR (superficie, año construcción)
    if ramo == "HOGAR":
        nombre_via = payload.get("nombre_via", "")
        numero_calle = str(payload.get("numero_calle", ""))
        tipo_via = payload.get("id_tipo_via", "CL")
        provincia_desc = payload.get("descripcion_provincia", "")
        municipio_desc = payload.get("poblacion", "")
        piso = payload.get("piso", "")
        puerta = payload.get("puerta", "")

        if nombre_via and numero_calle and provincia_desc and municipio_desc:
            logger.info(f"[RETARIFICACION] Enriching with Catastro: "
                        f"{tipo_via} {nombre_via} {numero_calle} {piso} {puerta}, {municipio_desc} ({provincia_desc})")
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

                if cat_superficie and "superficie_vivienda" not in payload:
                    payload["superficie_vivienda"] = int(cat_superficie)
                    logger.info(f"[RETARIFICACION] Catastro -> superficie: {cat_superficie}m²")

                if cat_anio and "anio_construccion" not in payload:
                    payload["anio_construccion"] = int(cat_anio)
                    logger.info(f"[RETARIFICACION] Catastro -> año construcción: {cat_anio}")

                if cat_ref:
                    payload["referencia_catastral"] = cat_ref
                    logger.info(f"[RETARIFICACION] Catastro -> ref catastral: {cat_ref}")
            else:
                logger.warning(f"[RETARIFICACION] Catastro lookup failed: {catastro_result.get('error')}")
                if catastro_result.get("multiple_results"):
                    logger.info("[RETARIFICACION] Multiple properties found - may need planta/puerta")

        # Fallback values if Catastro didn't provide them
        if "superficie_vivienda" not in payload:
            payload["superficie_vivienda"] = 90
            logger.warning("[RETARIFICACION] Using default superficie (90m²) - Catastro unavailable")
        if "anio_construccion" not in payload:
            payload["anio_construccion"] = 2000
            logger.warning("[RETARIFICACION] Using default año construcción (2000) - Catastro unavailable")

    # 4. Default values for HOGAR
    if ramo == "HOGAR":
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
            if k not in payload:
                payload[k] = v

    # 5. Create project in Merlin
    logger.info(f"[RETARIFICACION] Creating {ramo} project in Merlin for DNI: {dni}")
    result = create_merlin_project(payload)

    if result.get("success"):
        logger.info(f"[RETARIFICACION] Project created: ID={result.get('proyecto_id')}")
    else:
        logger.error(f"[RETARIFICACION] Failed: {result.get('error')}")

    return result
