"""Avant2 Multitarificador LLM Functions.

Tool wrappers that expose Avant2 functionality to the AI.
Uses avant2_client.py, dgt_client.py, cp_client.py, and catastro_client.py.
"""
import logging
import json
from typing import Dict, Any

from .avant2_client import Avant2Client, SUBRAMO_AUTO
from .cp_client import obtener_poblacion_por_cp
from Merlin.merlin_client import get_vehicle_info_by_matricula as consultar_dgt_por_matricula
from .catastro_client import consultar_catastro_por_direccion

logger = logging.getLogger(__name__)

def _extract_tarificador_config(config: dict) -> dict:
    if not config or not isinstance(config, dict):
        return {}
    if "tarificador" in config:
        return config.get("tarificador", {})
    return config

def get_town_by_cp_avant2_tool(cp: str) -> Dict[str, Any]:
    """Get town info by postal code for Avant2 projects."""
    return obtener_poblacion_por_cp(cp)

def consulta_vehiculo_avant2_tool(matricula: str, context: dict = None) -> Dict[str, Any]:
    """Lookup vehicle info via DGT for Avant2 projects."""
    cfg = _extract_tarificador_config(context)
    return consultar_dgt_por_matricula(matricula, cfg)

def consultar_catastro_avant2_tool(
    provincia: str, municipio: str, tipo_via: str, nombre_via: str, numero: str, 
    bloque: str = "", escalera: str = "", planta: str = "", puerta: str = ""
) -> Dict[str, Any]:
    """Lookup property info via Catastro for Avant2 projects."""
    return consultar_catastro_por_direccion(
        provincia, municipio, tipo_via, nombre_via, numero, 
        bloque, escalera, planta, puerta
    )

def _build_avant2_payload(llm_data: dict) -> dict:
    """Build the Codeoscopic /insurances payload from the generic LLM JSON."""
    ramo = str(llm_data.get("ramo", "AUTO")).upper()
    
    # Map generic 'ramo' to Codeoscopic 'insuranceLine'
    ramo_map = {
        "AUTO": "Car",
        "HOGAR": "Home",
        "MOTO": "Motorcycle",
        "VIDA": "TermLife",
        "SALUD": "Health",
        "DECESOS": "Burial"
    }
    insurance_line = ramo_map.get(ramo, "Car")

    # 1. Base Structure
    payload = {
        "insuranceLine": {"id": insurance_line},
        "effectiveDate": llm_data.get("fecha_efecto", "2026-03-15"), # Uses LLM provided or fallback
        "holder": _build_person(llm_data, "tomador")
    }

    # 2. Add specific risk data depending on line
    if insurance_line == "Car":
        payload["risk"] = _build_auto_risk(llm_data)
    elif insurance_line == "Home":
        payload["risk"] = _build_home_risk(llm_data)
    elif insurance_line == "Motorcycle":
        payload["risk"] = _build_motorcycle_risk(llm_data)
    elif insurance_line == "TermLife":
        payload["risk"] = _build_life_risk(llm_data)
    elif insurance_line == "Health":
        payload["risk"] = _build_health_risk(llm_data)
    elif insurance_line == "Burial":
        payload["risk"] = _build_burial_risk(llm_data)

    return payload

def _build_person(llm_data: dict, person_type: str) -> dict:
    """Map LLM generic person to Codeoscopic Person."""
    person_data = llm_data.get(person_type)
    if not person_data and person_type == "tomador":
        person_data = llm_data # Fallback if flat
        
    doc = str(person_data.get("dni", person_data.get("numero_documento", "")))
    doc_type = "Nie" if doc.startswith(("X", "Y", "Z")) else "Cif" if len(doc) == 9 and doc[0].isalpha() and doc[0] not in ('X', 'Y', 'Z') else "Dni"

    # Defaulting some values directly if missing from LLM data
    person_obj = {
        "identificationDocument": {
            "type": {"id": doc_type},
            "id": doc
        },
        "name": person_data.get("nombre", ""),
        "surname": person_data.get("apellido1", ""),
        "surname2": person_data.get("apellido2", ""),
        "maritalStatus": {"id": person_data.get("estado_civil", "Single")}, 
        "gender": {"id": person_data.get("sexo", "Male")}, 
        "birthCountry": {"code": "ESP"},
        "birthDate": person_data.get("fecha_nacimiento", "1980-01-01"),
        "smoker": bool(person_data.get("fumador", False)),
        "phones": [],
        "emails": [], 
        "addresses": [], 
    }
    
    # Phone
    phone = person_data.get("telefono")
    if phone:
        person_obj["phones"].append({"number": phone, "primary": True})

    # Email
    email = person_data.get("email")
    if email:
        person_obj["emails"].append({"address": email, "primary": True})
        
    # Build a sample address based on the Codeoscopic payload structure if we have CP
    cp = person_data.get("codigo_postal")
    if cp:
        addr = {
            "postalCode": cp,
            "town": {"id": 3679}, # Placeholder: actual town id mapping is needed
            "primary": True
        }
        # Only add road info if provided to match the simpler health example
        if person_data.get("direccion"):
            addr["roadType"] = {"id": person_data.get("id_tipo_via", "Calle")}
            addr["roadName"] = person_data.get("direccion")
            addr["roadNumber"] = str(person_data.get("numero", "1"))
            
        person_obj["addresses"].append(addr)
        
    # Optional Driving License (only add if present, to keep other risks clean)
    if "fecha_carnet" in person_data:
        person_obj["drivingLicenses"] = [
            {
                "type": {"id": "B"},
                "date": person_data.get("fecha_carnet", "2000-01-01"),
                "issuingZone": {"id": "Spain"}
            }
        ]
        
    # Optional employment
    if "profesion" in person_data:
        person_obj["employmentStatus"] = {"id": "Employee"}
        person_obj["economicOccupation"] = {"code": person_data.get("profesion", "2612")}
        
    return person_obj

def _build_auto_risk(llm_data: dict) -> dict:
    """Map LLM generic auto data to Codeoscopic Car risk."""
    
    # This structure is highly nested and requires IDs for categories (like Code, PostalCode, etc.)
    risk_obj = {
        "vehicle": {
            # Typically mapped from an internal ID provider or matched string
            "code": llm_data.get("codigo_vehiculo", "00080160927") 
        },
        "registrationPlate": llm_data.get("matricula", "1234ABC"),
        "registrationDate": llm_data.get("fecha_matriculacion", "2018-03-08"),
        "purchaseDate": llm_data.get("fecha_compra", "2018-03-08"),
        "circulationAddress": {
            "postalCode": llm_data.get("tomador", {}).get("codigo_postal", "08013"),
            "town": {
                "id": 3679 # Default/Placeholder mapped ID
            }
        },
        "kilometersPerYear": llm_data.get("kilometros_anuales", 10000),
        "owner": _build_person(llm_data, "propietario"),
        "primaryDriver": _build_person(llm_data, "conductor"),
        "lightTrailer": False,
        "garageType": {
            "id": llm_data.get("parking", "CommunalParking")
        }
    }
    
    # Previous Insurance handling
    poliza_previa = llm_data.get("poliza_previa")
    if poliza_previa:
        risk_obj["previouslyInsured"] = True
        risk_obj["previousInsurance"] = {
            "policyNumber": poliza_previa.get("numero", "000000"),
            "registrationPlate": risk_obj["registrationPlate"],
            "totalYearsInsured": poliza_previa.get("anios_asegurado", 5),
            "yearsInPreviousCompany": poliza_previa.get("anios_compania_actual", 5),
            "yearsWithoutAccidents": poliza_previa.get("siniestros_5_anios", 0) == 0 and 5 or 0,
            "previousCompany": {
                # Code mapping required for companies. Using a fallback for the example
                "code": poliza_previa.get("cia_actual", "M0083")
            }
        }
    else:
        risk_obj["previouslyInsured"] = False
        
    return risk_obj

def _build_home_risk(llm_data: dict) -> dict:
    """Map LLM generic home data to Codeoscopic Home risk."""
    risk_obj = {
        "address": {
            "postalCode": llm_data.get("codigo_postal", "08013"),
            "town": {
                "id": 3679 # Default/Placeholder mapped ID
            },
            "roadType": {"id": llm_data.get("id_tipo_via", "Calle")},
            "roadName": llm_data.get("nombre_via", "Direccion"),
            "roadNumber": str(llm_data.get("numero_calle", "1")),
        },
        "yearBuilt": llm_data.get("anio_construccion", 2000),
        "floorArea": llm_data.get("superficie_vivienda", 90),
        "rooms": int(llm_data.get("numero_habitaciones", 3)),
        "buildingType": {"id": "Flat"}, # Base mapping, needs translation from PISO_EN_ALTO, etc.
        "use": {"id": "MainResidence"}, 
        "occupancy": {"id": "Owner"},
        "location": {"id": "Urban"},
        "materials": {"id": "Solid"},
        "buildQuality": {"id": "Normal"},
        "alarm": {"id": "None"},
        "securityMainDoor": True,
        "securityWindows": False,
        "gatedCommunity": False,
        "settlementType": {"id": "ReplacementCost"},
        "buildingsLimit": llm_data.get("capital_continente", 90000),
        "contentsLimit": llm_data.get("capital_contenido", 25000),
        "jewelsInSafeBoxLimit": llm_data.get("joyas_caja_fuerte", 0),
        "jewelsOutSafeBoxLimit": llm_data.get("joyas_fuera_caja", 0),
        "highValueItemsLimit": llm_data.get("objetos_valor", 0),
        "numberOfDangerousDogs": 0
    }
    
    # Translation heuristic for building types if present
    tipo_vivienda = llm_data.get("tipo_vivienda", "PISO_EN_ALTO")
    if "CHALET" in tipo_vivienda or "UNIFAMILIAR" in tipo_vivienda:
        risk_obj["buildingType"]["id"] = "DetachedHouse"
    elif "ADOSAD" in tipo_vivienda:
        risk_obj["buildingType"]["id"] = "SemiDetachedHouse"
        
    return risk_obj

def _build_motorcycle_risk(llm_data: dict) -> dict:
    """Map LLM generic moto data to Codeoscopic Motorcycle risk."""
    risk_obj = {
        "vehicle": {
            "code": llm_data.get("codigo_vehiculo", "00000000000") # Base7 mapping
        },
        "registrationPlate": llm_data.get("matricula", "1234ABC"),
        "registrationDate": llm_data.get("fecha_matriculacion", "2020-01-01"),
        "purchaseDate": llm_data.get("fecha_compra", "2020-01-01"),
        "circulationAddress": {
            "postalCode": llm_data.get("tomador", {}).get("codigo_postal", "08013"),
            "town": {"id": 3679}
        },
        "kilometersPerYear": llm_data.get("kilometros_anuales", 5000),
        "owner": _build_person(llm_data, "propietario"),
        "primaryDriver": _build_person(llm_data, "conductor"),
        "garageType": {"id": llm_data.get("parking", "CommunalParking")},
        "drivingExperience": {"id": "None"}
    }
    
    # Previous Insurance handling
    poliza_previa = llm_data.get("poliza_previa")
    if poliza_previa:
        risk_obj["previouslyInsured"] = True
        risk_obj["previousInsurance"] = {
            "policyNumber": poliza_previa.get("numero", "000000"),
            "registrationPlate": risk_obj["registrationPlate"],
            "totalYearsInsured": poliza_previa.get("anios_asegurado", 5),
            "yearsInPreviousCompany": poliza_previa.get("anios_compania_actual", 5),
            "yearsWithoutAccidents": poliza_previa.get("siniestros_5_anios", 0) == 0 and 5 or 0,
            "previousCompany": {"code": poliza_previa.get("cia_actual", "M0083")}
        }
    else:
        risk_obj["previouslyInsured"] = False
        
    return risk_obj

def _build_life_risk(llm_data: dict) -> dict:
    """Map LLM generic vida data to Codeoscopic TermLife risk."""
    return {
        "insured": _build_person(llm_data, "asegurado"),
        "deathBenefit": llm_data.get("capital_fallecimiento", 100000),
        "accidentalDeathBenefit": llm_data.get("capital_invalidez", 0),
        "permanentDisabilityBenefit": llm_data.get("capital_invalidez_absoluta", 0)
    }

def _build_health_risk(llm_data: dict) -> dict:
    """Map LLM generic salud data to Codeoscopic Health risk."""
    # Health normally expects an array of insureds
    asegurados_raw = llm_data.get("asegurados", [])
    if not asegurados_raw:
        # Fallback to single insured if array not provided
        asegurados = [_build_person(llm_data, "asegurado")]
    else:
        asegurados = []
        # Need to rebuild them as Person object arrays
        for a in asegurados_raw:
            a_built = _build_person(a, "asegurado")
            
            # The API allows insured objects to drop emails/phones sometimes,
            # but Codeoscopic usually ignores empty arrays.
            asegurados.append(a_built)
            
    return {"insureds": asegurados}

def _build_burial_risk(llm_data: dict) -> dict:
    """Map LLM generic decesos data to Codeoscopic Burial risk."""
    asegurados_raw = llm_data.get("asegurados", [])
    if not asegurados_raw:
        asegurados = [_build_person(llm_data, "asegurado")]
    else:
        asegurados = []
        for a in asegurados_raw:
            a_built = _build_person(a, "asegurado")
            asegurados.append(a_built)
            
    return {
        "insureds": asegurados,
        "products": [] # Custom options per product if needed
    }

def _extract_offers_from_avant2_response(insurances_response: dict) -> list:
    """Extract standard offers format from the complex Codeoscopic response."""
    offers_out = []
    raw_offers = insurances_response.get("offers", [])
    raw_quotes = insurances_response.get("mainQuotes", [])
    
    # Map quotes by id for easy lookup
    quotes_map = {q.get("id"): q for q in raw_quotes}

    for offer in raw_offers:
        main_quote_ref = offer.get("mainQuote", {})
        quote_id = main_quote_ref.get("id")
        
        if quote_id and quote_id in quotes_map:
            quote = quotes_map[quote_id]
            product = quote.get("product", {})
            vendor = product.get("vendor", {})
            modality = product.get("modality", {})
            
            offers_out.append({
                "nombre_aseguradora": f"{vendor.get('name', '')} {product.get('name', '')}".strip(),
                "dgs": "", # Not easily available in sample
                "descripcion": modality.get("name", ""),
                "prima_anual": float(offer.get("totalPremium", 0.0)),
                "contratable": not quote.get("estimate", False), # If it's an estimate, it might not be strictly contratable yet
                "nombre_completo": f"{vendor.get('name', '')} {modality.get('name', '')}",
            })

    offers_out.sort(key=lambda x: x["prima_anual"])
    return offers_out

def create_retarificacion_avant2_project_tool(datos: dict, context: dict = None) -> str:
    """Create Avant2 project from generic JSON and initiate rating.
    
    Args:
        datos: The generic LLM JSON containing parsed data matching our global interface.
        context: Context dictionary with the 'tarificador' structure and environment.
    """
    logger.info("[AVANT2_TOOL] Starting Avant2 project creation via tool...")
    
    try:
        cfg = _extract_tarificador_config(context)
        client = Avant2Client(cfg)
        
        # 1. Login
        client.login()
        
        # 1.5 Internal Enrichment (to match Merlin behavior)
        ramo = str(datos.get("ramo", "AUTO")).upper()
        cp = datos.get("codigo_postal")

        # Enrich Auto
        if ramo == "AUTO":
            matricula = datos.get("matricula")
            if matricula:
                try:
                    dgt_result = consultar_dgt_por_matricula(matricula, cfg)
                    if dgt_result.get("success"):
                        v = dgt_result.get("vehiculo", {})
                        # Mapear datos devueltos al JSON genérico esperado por Avant2
                        datos.update({
                            "marca": v.get("marca"),
                            "modelo": v.get("modelo"),
                            "version": v.get("version"),
                            "combustible": v.get("combustible"),
                            "fecha_matriculacion": v.get("fecha_matriculacion"),
                            "potencia": v.get("potencia_cv"),
                            "cilindrada": v.get("cilindrada"),
                        })
                except Exception as e:
                    logger.warning(f"[AVANT2_TOOL] DGT enrichment failed: {e}")

        # Enrich Town via CP
        if cp:
            try:
                town_result = obtener_poblacion_por_cp(cp)
                if town_result.get("success"):
                    datos.update({
                        "poblacion": town_result.get("poblacion"),
                        "id_provincia": town_result.get("id_provincia"),
                        "descripcion_provincia": town_result.get("descripcion_provincia"),
                    })
            except Exception as e:
                logger.warning(f"[AVANT2_TOOL] Town enrichment failed: {e}")

        # Enrich Hogar
        if ramo == "HOGAR":
            nombre_via = datos.get("nombre_via", "")
            numero_calle = str(datos.get("numero_calle", ""))
            tipo_via = datos.get("id_tipo_via", "CL")
            provincia_desc = datos.get("descripcion_provincia", "")
            municipio_desc = datos.get("poblacion", "")
            
            if nombre_via and numero_calle and provincia_desc and municipio_desc:
                try:
                    catastro_result = consultar_catastro_por_direccion(
                        provincia=provincia_desc,
                        municipio=municipio_desc,
                        tipo_via=tipo_via,
                        nombre_via=nombre_via,
                        numero=numero_calle,
                        bloque=datos.get("bloque", ""),
                        escalera=datos.get("escalera", ""),
                        planta=datos.get("piso", ""),
                        puerta=datos.get("puerta", ""),
                    )
                    if catastro_result.get("success"):
                        cat_superficie = catastro_result.get("superficie")
                        cat_anio = catastro_result.get("anio_construccion")
                        
                        if cat_superficie: datos["superficie_vivienda"] = int(cat_superficie)
                        if cat_anio: datos["anio_construccion"] = int(cat_anio)
                except Exception as e:
                    logger.warning(f"[AVANT2_TOOL] Catastro Enrichment failed: {e}")

        # 2. Build payload from the generic enriched `datos`
        payload = _build_avant2_payload(datos)
        
        # 3. Create the project via POST /insurances
        project_response = client.create_insurance_project(payload)
        project_id = str(project_response.get("id"))
        
        if not project_id or project_id == "None":
            logger.error("[AVANT2_TOOL] Failed to acquire project ID from Codeoscopic")
            return json.dumps({
                "success": False, 
                "error": "Could not get an ID for the created Avant2 project. Check credentials or payload format."
            })
            
        logger.info(f"[AVANT2_TOOL] Created project: {project_id}")
            
        # 4. Wait for tarification to complete and get the full project containing quotes/offers.
        import time
        time.sleep(5) 
        
        final_project = client.get_insurance_project(project_id)
        
        # Extract offers and format them so the LLM output can be standard
        mapped_offers = _extract_offers_from_avant2_response(final_project)
        
        # We can also handle the errors array from the response to give feedback
        errors = final_project.get("errors", [])
        
        result = {
            "success": True,
            "proyecto_id": project_id,
            "mensaje": f"Proyecto {datos.get('ramo', 'AUTO')} creado en Avant2.",
            "num_ofertas": len(mapped_offers),
            "num_errores": len(errors),
            "ofertas": mapped_offers,
            "errors": [{"aseguradora": e.get("product", {}).get("vendor", {}).get("name"), "mensajes": e.get("messages", [])} for e in errors][:5]
        }
        
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as exc:
        logger.exception("[AVANT2_TOOL] Error in create_retarificacion_avant2_project_tool")
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
