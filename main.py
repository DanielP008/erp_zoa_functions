import functions_framework
import erp_auth
import database_functions
import excel_functions
import json
import firebase_admin
import os
from firebase_admin import db,credentials,storage,firestore
from datetime import datetime, timedelta
from Merlin.merlin_client import create_merlin_project, get_vehicle_info_by_matricula, get_town_by_cp
from Merlin.catastro_client import consultar_catastro_por_direccion
import requests


firebase_admin.initialize_app()


@functions_framework.http
def main(request):

    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """

    request_json = request.get_json(silent=True)
    
    if request_json is None:
        return {'error': 'Data not provided in JSON format'}, 400

    # Load data from JSON
    company_id =  str(request_json.get('company_id'))
    option =  request_json.get('option')
    nif =  request_json.get('nif')
    num_poliza = request_json.get('num_poliza')
    phone = request_json.get('phone')
    #TODO FORMATO STANDARD DE DATE es dia mes año, ebroker espera año mes dia
    day = request_json.get('day', '')
    period = request_json.get('period', 7)
    lines = request_json.get('lines', '')
    id_siniestro = request_json.get('id_siniestro', '')
    num_claim = request_json.get('num_claim', '')
    risk = request_json.get('risk', '')
    name = request_json.get('name', '')
    surname = request_json.get('surname', '')
    address = request_json.get('address', '')
    #Document data
    filename = request_json.get('filename', '')
    base64_content = request_json.get('base64_content', '')
    notes = request_json.get('notes', '')
    start_date = request_json.get('start_date')
    end_date = request_json.get('end_date')



    # Load Firebase data
   
    company_config = database_functions.get_company_config(company_id)

    system = company_config.get('system', "")

    if not (option and option.startswith('merlin_')):
        if isinstance(company_config, dict) and "error" in company_config:
            return company_config, 500

        if not company_config:
            return {"error": f"Configuration not found for company_id: {company_id}"}, 404
    
    # Extract ERP config for local usage
    erp_config = company_config.get('erp', {})

    # Normalize erp_type
    raw_erp_type = str(erp_config.get('erp_type', '')).strip().lower()

    client = None
    # Skip ERP login for Merlin operations that don't need it
    if option and option.startswith('merlin_'):
        pass
    elif raw_erp_type == 'ebroker':
        try:
            client = erp_auth.get_erp_client(company_config)
            if not client or isinstance(client, str):
                return {"error": f"Error conectando con ebroker (Login fallido): {client}"}, 500
        except Exception as e:
            return {'error': f'Error conectando con ebroker: {str(e)}'}, 500
    elif raw_erp_type in ['excel', 'excell']:
        try:
            client = excel_functions.get_erp_client(company_config)
            #TO DELETE
            return client
        except Exception as e:
            return {'error': f'Error conectando con excel: {str(e)}'}, 500
    else:
        return {"error": f"Invalid ERP type: {raw_erp_type}"}, 400
    


    #========== TOOL METHODS ==========
    try:
        # Inyect tarificador config from Firebase into payload for Merlin
        if isinstance(company_config, dict):
            request_json['tarificador_config'] = company_config.get('tarificador', {})
        
        # CLAIMS
        # Needs another piece of data in the input JSON 'nif_cliente'
        if option == 'get_claims':
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            siniestros_cliente = client.get_customer_claims_by_category(nif,lines)
            return siniestros_cliente

        if option == 'get_claim_by_risk':
            if not risk: return {"error": "Missing mandatory parameter: risk"}, 400
            siniestro = client.get_claim_by_risk(nif,risk)
            return siniestro

        if option == 'get_status_claims':
            if not id_siniestro: return {"error": "Missing mandatory parameter: id_siniestro"}, 400
            siniestros = client.get_claim_status(id_siniestro)
            return siniestros 

        if option == 'get_new_flagged_claims': 
            siniestros = client.get_new_flagged_claims()
            seguimiento_siniestros = []
            url = "https://flow-zoav2-673887944015.europe-southwest1.run.app"
            for siniestro in siniestros:
                
                payload_search = {
                    "company_id": company_id,
                    "action": "contacts",
                    "option": "search",
                    "nif": siniestro.get('nif')
                }

                try:
                    res_zoa = requests.post(url, json=payload_search, timeout=10)
                    res_zoa.raise_for_status()
                    datos_zoa = res_zoa.json()
                    client_phone = datos_zoa.get('phone')
                except Exception:
                    continue

                payload_send = {
                    "company_id": company_id,
                    "action": "conversations",
                    "option": "send",
                    "phone": client_phone,
                    "template_name": siniestro.get('plantilla'),
                    "type": "template",
                    "params": siniestro.get('params'),
                    "image": "", "audio": "", "video": "", "document": "", "location": ""
                }

                try:
                    res_envio = requests.post(url, json=payload_send, timeout=10)
                except Exception:
                    pass

                seguimiento_siniestros.append({
                    'desc_siniestro': siniestro.get('desc_siniestro'),
                    'client_name': nombre,
                    'gestor': gestor
                })

            return seguimiento_siniestros
        
        '''
        # Receive nif and a JSON "datos_siniestro" with procedure,blame,num_poliza,incidence_date
        if option == "apertura_siniestro":
            datos_siniestro = request_json.get('datos_siniestro')
            num_poliza = datos_siniestro.get('num_poliza')
            id_poliza = client_business.get_policy_by_docno(num_poliza).get('id')
            nif = request_json.get('nif')
            payload_send = {
                "procedure" : datos_siniestro.get('procedure'),
                "blame" : datos_siniestro.get('blame'),
                "policy_id" : id_poliza,
                "incidence_date" : datos_siniestro.get('incidence_date')
            }
            return client.create_claim(payload_send)
        '''

        # POLICIES
        if option == 'get_policies':
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            return client.get_all_policys_by_client_category(nif, lines,company_id)

        if option == 'get_new_policies':
            return client.get_new_policies_today()

        if option == 'get_policy_by_num':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            return client.get_policy_by_num(num_poliza)

        if option == 'get_doc_policies':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            return client.get_policy_doc_by_policynum(num_poliza)

        # RECEIPTS (Unpaid, Duplicate receipt, Renewals)
        # Unpaid
        if option == 'info_banco_devolucion':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            api_poliza = client.get_policy_by_num(num_poliza)
            cust_banks = api_poliza.get('customer').get('bank_accounts')

            cust_acc_num = 0
            for cust_bank in cust_banks:
                if cust_bank.get('default_account') == True:
                    cust_acc_num = cust_bank.get('account_number')
                    break
            return cust_acc_num

        if option == 'get_returned_receipts':
            return client.get_returned_receipts(start_date, end_date)

        # Documents
        if option == 'documento_recibo':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            ultimo_recibo = None
            fecha_ultimo_recibo = None
            recibos= client.get_doc_receipts_by_num_policy(num_poliza)
            for recibo in recibos:
                if fecha_ultimo_recibo == None or fecha_ultimo_recibo>recibo.get('created_date'):
                    ultimo_recibo = recibo
                    fecha_ultimo_recibo = recibo.get('created_date')
            
            if ultimo_recibo == None:
                return []
            else:
                return ultimo_recibo
        
        if option == 'add_document_claim':
            if not num_claim: return {"error": "Missing mandatory parameter: num_claim"}, 400
            if not filename: return {"error": "Missing mandatory parameter: filename"}, 400
            if not base64_content: return {"error": "Missing mandatory parameter: base64_content"}, 400
            
            return client.add_document_to_claim_by_num(num_claim, filename, base64_content,notes)
            
        if option == 'add_document_policy':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            if not filename: return {"error": "Missing mandatory parameter: filename"}, 400
            if not base64_content: return {"error": "Missing mandatory parameter: base64_content"}, 400
            
            return client.add_document_to_policy_by_num(num_poliza, filename, base64_content,notes)

        # Customer
        if option == 'get_customer_phone_by_nif':
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            return client.get_customer_phone_by_nif(nif)
        
        if option == 'create_customer':
            if not name: return {"error": "Missing mandatory parameter: name"}, 400
            if not surname: return {"error": "Missing mandatory parameter: surname"}, 400
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            if not address: return {"error": "Missing mandatory parameter: address"}, 400
            
            customer_data = {
                "name": name,
                "surname": surname,
                "legalId": nif,
                "address": address
            }
            return client.post_customer(customer_data)

        if option == 'add_document_customer':
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            if not filename: return {"error": "Missing mandatory parameter: filename"}, 400
            if not base64_content: return {"error": "Missing mandatory parameter: base64_content"}, 400
            
            return client.add_document_to_customer_by_nif(nif, filename, base64_content,notes)


        # Candidate
        if option == 'create_candidate':
            if not name: return {"error": "Missing mandatory parameter: name"}, 400
            if not phone: return {"error": "Missing mandatory parameter: phone"}, 400
            
            candidate_data = {
                "name": name,
                "phone": phone
            }
            return client.post_candidate(candidate_data)

        if option == 'get_new_candidates':
            return client.get_new_candidates_today()
        
        if option == 'get_candidate_by_nif':
             if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
             return client.get_candidate_by_nif(nif)

        if option == 'load_renewals':
            percent_threshold = request_json.get('percent_threshold', 8.0)
            amount_threshold = request_json.get('amount_threshold', 0.0)

            return client.process_load_renewals(
                company_id=company_id,
                percent_threshold=percent_threshold,
                amount_threshold=amount_threshold
            )




        # MERLIN / RETARIFICACION
        if option == 'merlin_consulta_vehiculo':
            # Input: {"option": "merlin_consulta_vehiculo", "matricula": "1234ABC"}
            matricula = request_json.get('matricula', '').strip().upper()
            if not matricula:
                return {"error": "Missing mandatory parameter: matricula"}, 400
            
            dgt_result = get_vehicle_info_by_matricula(matricula, request_json.get('tarificador_config'))
            if dgt_result.get("success"):
                v = dgt_result.get("vehiculo", {})
                def clean(val):
                    if val is None: return "No especificado"
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
                    "raw_data": v # Return raw data too for frontend usage if needed
                }
            else:
                return dgt_result, 404 if "No se encontraron" in str(dgt_result) else 500

        if option == 'merlin_get_town_by_cp':
            # Input: {"option": "merlin_get_town_by_cp", "cp": "28001"}
            cp = request_json.get('cp', '').strip()
            if not cp:
                return {"error": "Missing mandatory parameter: cp"}, 400
            return get_town_by_cp(cp, request_json.get('tarificador_config'))

        if option == 'merlin_consultar_catastro':
            # Input: {"option": "merlin_consultar_catastro", "provincia": "...", "municipio": "...", ...}
            # Mandatory: provincia, municipio, tipo_via, nombre_via, numero
            provincia = request_json.get('provincia')
            municipio = request_json.get('municipio')
            tipo_via = request_json.get('tipo_via') or "CL"
            nombre_via = request_json.get('nombre_via')
            numero = str(request_json.get('numero', ''))
            
            if not all([provincia, municipio, nombre_via, numero]):
                return {"error": "Missing mandatory parameters for Catastro (provincia, municipio, nombre_via, numero)"}, 400

            # Optional params
            bloque = request_json.get('bloque', '')
            escalera = request_json.get('escalera', '')
            planta = request_json.get('planta', '') or request_json.get('piso', '')
            puerta = request_json.get('puerta', '')
            
            result = consultar_catastro_por_direccion(
                provincia=provincia,
                municipio=municipio,
                tipo_via=tipo_via,
                nombre_via=nombre_via,
                numero=numero,
                bloque=bloque,
                escalera=escalera,
                planta=planta,
                puerta=puerta,
            )
            
            # Calculate capitals if successful, to help the agent suggest values
            if result.get("success"):
                try:
                    tipo_vivienda = request_json.get('tipo_vivienda', 'PISO_EN_ALTO')
                    superficie = result.get('superficie', 90)
                    
                    factores = {
                        "PISO_EN_ALTO": 1.0,
                        "ATICO": 1.0,
                        "PISO_EN_BAJO": 1.1,
                        "CHALET_O_VIVIENDA_ADOSADA": 1.2,
                        "CHALET_O_VIVIENDA_UNIFAMILIAR": 1.4
                    }
                    factores_contenido = {
                        "PISO_EN_ALTO": 250,
                        "ATICO": 350,
                        "PISO_EN_BAJO": 250,
                        "CHALET_O_VIVIENDA_ADOSADA": 350,
                        "CHALET_O_VIVIENDA_UNIFAMILIAR": 450
                    }
                    
                    factor_tipologia = factores.get(tipo_vivienda, 1.0)
                    precio_m2_contenido = factores_contenido.get(tipo_vivienda, 250)
                    
                    precio_m2_base = 1500
                    capital_continente = 0
                    capital_contenido = 25000
                    
                    if str(superficie).isdigit():
                        json_path = os.path.join(os.path.dirname(__file__), "Merlin", "precios_m2.json")
                        if os.path.exists(json_path):
                            with open(json_path, "r", encoding="utf-8") as f:
                                precios = json.load(f)
                            
                            mun_upper = str(municipio).strip().upper()
                            prov_upper = str(provincia).strip().upper()
                            
                            if mun_upper in precios:
                                precio_m2_base = precios[mun_upper]
                            elif prov_upper in precios:
                                precio_m2_base = precios[prov_upper]
                            else:
                                precio_m2_base = precios.get("DEFAULT", 1500)
                        
                        precio_final_m2 = float(precio_m2_base) * factor_tipologia
                        capital_continente = int(superficie) * int(precio_final_m2)
                        capital_contenido = int(superficie) * precio_m2_contenido
                    else:
                        capital_continente = 90 * 1500
                        capital_contenido = 25000
                        
                    result['capital_continente'] = capital_continente
                    result['capital_contenido'] = capital_contenido
                    result['precio_m2_base'] = precio_m2_base
                    result['factor_tipologia'] = factor_tipologia
                    result['precio_m2_contenido'] = precio_m2_contenido
                    
                except Exception as e:
                    print(f"Error calculating capitals in merlin_consultar_catastro: {e}")
                    # Don't fail the whole request, just return without capitals
                    pass

            return result

        if option == 'merlin_create_project':
            # Input: {"option": "merlin_create_project", ... full payload ...}
            payload = request_json.copy()
            # Remove main API wrapper params if present
            payload.pop('company_id', None)
            payload.pop('option', None)
            
            ramo = str(payload.get("ramo", "AUTO")).upper()
            dni = payload.get("dni")
            cp = payload.get("codigo_postal")

            # 1. Enrichment for AUTO only (Vehicle info)
            if ramo == "AUTO":
                matricula = payload.get("matricula")
                if matricula:
                    dgt_result = get_vehicle_info_by_matricula(matricula, request_json.get('tarificador_config'))
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
                    
                    # ERP Enrichment for current policy info
                    if dni and matricula and company_id:
                         # We use the existing 'client' instance from main logic
                        try:
                            # Verify if method exists on this client type
                            # Assuming client is EBrokerClient
                            if hasattr(client, 'get_all_policys_by_client_risk'):
                                erp_result = client.get_all_policys_by_client_risk(dni, matricula, company_id)
                                if erp_result:
                                    # Take first match
                                    policy = erp_result[0]
                                    payload.update({
                                        "aseguradora_actual": policy.get("company_name") or policy.get("company_id"),
                                        "num_poliza": policy.get("number"),
                                    })
                        except Exception as e:
                            print(f"ERP enrichment failed: {e}") # Non-blocking

            # 2. Enrichment for both (Town/CP)
            if cp:
                try:
                    town_result = get_town_by_cp(cp, request_json.get('tarificador_config'))
                    if town_result.get("success"):
                        payload.update({
                            "poblacion": town_result.get("poblacion"),
                            "id_provincia": town_result.get("id_provincia"),
                            "descripcion_provincia": town_result.get("descripcion_provincia"),
                        })
                    else:
                        print(f"[MERLIN] Town enrichment failed for CP {cp}: {town_result.get('error')}")
                except Exception as e:
                    print(f"[MERLIN] Town enrichment unexpected error for CP {cp}: {e}")

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
                        print(f"[CATASTRO] Enrichment failed: {catastro_result.get('error', 'unknown')}")

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

                # Calcular capitales continente y contenido
                if "capital_continente" not in payload or "capital_contenido" not in payload:
                    superficie = payload.get("superficie_vivienda", 90)
                    tipo_vivienda = payload.get("tipo_vivienda", "PISO_EN_ALTO")
                    
                    factores = {
                        "PISO_EN_ALTO": 1.0,
                        "ATICO": 1.0,
                        "PISO_EN_BAJO": 1.1,
                        "CHALET_O_VIVIENDA_ADOSADA": 1.2,
                        "CHALET_O_VIVIENDA_UNIFAMILIAR": 1.4
                    }
                    factores_contenido = {
                        "PISO_EN_ALTO": 250,
                        "ATICO": 350,
                        "PISO_EN_BAJO": 250,
                        "CHALET_O_VIVIENDA_ADOSADA": 350,
                        "CHALET_O_VIVIENDA_UNIFAMILIAR": 450
                    }
                    
                    factor_tipologia = factores.get(tipo_vivienda, 1.0)
                    precio_m2_contenido = factores_contenido.get(tipo_vivienda, 250)
                    
                    capital_continente = 0
                    capital_contenido = 25000
                    precio_m2_base = 1500
                    
                    if str(superficie).isdigit():
                        try:
                            json_path = os.path.join(os.path.dirname(__file__), "Merlin", "precios_m2.json")
                            with open(json_path, "r", encoding="utf-8") as f:
                                precios = json.load(f)
                            
                            mun_upper = str(payload.get("poblacion", "")).strip().upper()
                            prov_upper = str(payload.get("descripcion_provincia", "")).strip().upper()
                            
                            if mun_upper in precios:
                                precio_m2_base = precios[mun_upper]
                            elif prov_upper in precios:
                                precio_m2_base = precios[prov_upper]
                            else:
                                precio_m2_base = precios.get("DEFAULT", 1500)
                                
                            precio_final_m2 = float(precio_m2_base) * factor_tipologia
                            capital_continente = int(superficie) * int(precio_final_m2)
                            capital_contenido = int(superficie) * precio_m2_contenido
                        except Exception as e:
                            capital_continente = int(superficie) * 1500
                            capital_contenido = 25000
                    else:
                        capital_continente = 90 * 1500
                        capital_contenido = 25000
                        
                    if "capital_continente" not in payload: payload["capital_continente"] = capital_continente
                    if "capital_contenido" not in payload: payload["capital_contenido"] = capital_contenido


            # 5. Create project in Merlin
            import json as _json
            print(f"[MAIN] Payload keys before create_merlin_project: {list(payload.keys())}")
            print(f"[MAIN] Payload (first 2000): {_json.dumps(payload, default=str, ensure_ascii=False)[:2000]}")
            result = create_merlin_project(payload,company_config)
            return result
    
    except Exception as e:
        return {'error': f"Error executing operation {option}: {str(e)}"}, 500

    finally:
        if client and hasattr(client, 'close'):
            client.close()
    return {"error": "Invalid option"}, 400

def get_nif_by_phone(company_id, phone):
    url = "https://flow-zoav2-673887944015.europe-southwest1.run.app"
    payload_search = {
        "company_id": company_id,
        "action": "contacts",
        "option": "search",
        "phone": phone
    }
    try:
        res_zoa = requests.post(url, json=payload_search, timeout=10)
        res_zoa.raise_for_status()
        datos_zoa = res_zoa.json()
        return datos_zoa.get('nif')
    except Exception:
        return None
