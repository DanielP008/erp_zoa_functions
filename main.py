import functions_framework
import erp_auth
import database_functions
import excel_functions
import json
import firebase_admin
from firebase_admin import db,credentials,storage,firestore
from datetime import datetime, timedelta
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
    risk = request_json.get('risk', '')



    # Load Firebase data
    company_config = database_functions.get_company_config(company_id)
    system = company_config.get('system', "")

    if isinstance(company_config, dict) and "error" in company_config:
        return company_config, 500

    if not company_config:
        return {"error": f"Configuration not found for company_id: {company_id}"}, 404

    # Extract ERP config for local usage
    erp_config = company_config.get('erp', {})

    # Normalize erp_type
    raw_erp_type = str(erp_config.get('erp_type', '')).strip().lower()

    if raw_erp_type == 'ebroker':
        try:
            client = erp_auth.get_erp_client(company_config)
            if not client:
                return {"error": "Error conectando con ebroker (Login fallido)"}, 500
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

        # REMOVE AFTER TESTING
        if option == 'get_policy_by_num':
            if not num_poliza: return {"error": "Missing mandatory parameter: num_poliza"}, 400
            return client.get_policy_by_num(num_poliza)
        #------------------------

        # Query
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

        # Duplicate receipt
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
        if option == 'get_customer_phone_by_nif':
            if not nif: return {"error": "Missing mandatory parameter: nif"}, 400
            return client.get_customer_phone_by_nif(nif)
        if option == 'renovaciones_recibos' and system != 'old':
            # "revisar desde el siguiente dia" -> Start tomorrow
            start_date_calc = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

            url = "https://flow-zoav2-673887944015.europe-southwest1.run.app"
            renovaciones_vigentes = []
            renovaciones = client.get_receipts_label(start_date_calc, int(period))
            for renovacion in renovaciones:
                nif = renovacion.get('nif')
                ramo = renovacion.get('ramo')
                nombre = renovacion.get('nombre')
                riesgo = renovacion.get('riesgo')
                prima = renovacion.get('prima')
                plantilla = renovacion.get('plantilla')
                gestor = renovacion.get('gestor')
                payload_search = {
                    "company_id": company_id,
                    "action": "contacts",
                    "option": "search",
                    "nif": nif
                }

                '''            
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
                    "template_name": plantilla,
                    "type": "template",
                    "params": f"{nombre};{riesgo};{ramo};{prima}",
                    "image": "", "audio": "", "video": "", "document": "", "location": ""
                }

                try:
                    template_enviado = requests.post(url, json=payload_send, timeout=10)
                except Exception:
                    pass
                '''
                # Add to return list
                renovaciones_vigentes.append({
                    'client_nif': nif,
                    'client_name': nombre,
                    'gestor': gestor if gestor else 'No manager',
                    'riesgo': riesgo,
                    'ramo': ramo,
                    'prima': prima,
                    'plantilla': plantilla
                })

            return renovaciones_vigentes

        elif option == 'renovaciones_recibos' and system == 'old':
            # "revisar desde el siguiente dia" -> Start tomorrow
            start_date_calc = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

            url = "https://flow-zoav2-673887944015.europe-southwest1.run.app"
            renovaciones_vigentes = []
            renovaciones = client.get_receipts_label(start_date_calc, int(period))
            for renovacion in renovaciones:
                nif = renovacion.get('nif')
                ramo = renovacion.get('ramo')
                nombre = renovacion.get('nombre')
                riesgo = renovacion.get('riesgo')
                prima = renovacion.get('prima')
                plantilla = renovacion.get('plantilla')
                gestor = renovacion.get('gestor')
                
                #Get client phone
                payload_search = {
                    "company_id": company_id,
                    "action": "contacts",
                    "option": "search",
                    "nif": nif
                }         
                try:
                    res_zoa = requests.post(url, json=payload_search, timeout=10)
                    res_zoa.raise_for_status()
                    datos_zoa = res_zoa.json()
                    client_phone = datos_zoa.get('phone')
                except Exception:
                    continue
                
                #Get template id
                url = "https://api.zoasuite.com/api/flows"
                payload_send = {
                    "company_id": company_id,
                    "action": "conversations",
                    "option": "get_template_id",
                    "template_name": plantilla,
                }
                headers = {
                    "Content-Type": "application/json"
                }
                #Params for template
                params = f"{nombre};{riesgo};{ramo};{prima}"
                
                try:
                    Id_Plantilla = requests.post(url, headers=headers,data=json.dumps(payload_send), timeout=10)
                except Exception:
                    pass
                url = f"https://europe-west3-zoa-suite.cloudfunctions.net/write_WP?phone={client_phone}&option=cloud_template&message={plantilla}&message_id={Id_Plantilla}&header_params=&body_params={params}&company={company_id}"

                try:
                    template_enviado = requests.post(url, timeout=10)
                except Exception:
                    pass
                
                # Add to return list
                renovaciones_vigentes.append({
                    'client_nif': nif,
                    'client_name': nombre,
                    'gestor': gestor if gestor else 'No manager',
                    'riesgo': riesgo,
                    'ramo': ramo,
                    'prima': prima,
                    'plantilla': plantilla
                })
    except Exception as e:
        return {'error': f"Error executing operation {option}: {str(e)}"}, 500




def get_nif_by_phone(phone):
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
