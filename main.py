import functions_framework
import erp_auth
import database_functions
import json
import firebase_admin
from firebase_admin import db,credentials,storage,firestore
from datetime import datetime
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
        print('Datos no proporcionados en formato JSON', 400)

    #Cargar datos de JSON
    company_id =  request_json.get('company_id')
    option =  request_json.get('option')
    nif =  request_json.get('nif')
    num_poliza = request_json.get('num_poliza')
    phone = request_json.get('phone')
    #TODO FORMATO STANDARD DE DATE es dia mes año, ebroker espera año mes dia
    start_date = request_json.get('start_date', '')
    frequency = request_json.get('frequency', 7)
    lines = request_json.get('lines', '')
    id_siniestro = request_json.get('id_siniestro', '')
    risk = request_json.get('risk', '')



    # Cargar datos Firebase
    domain_info = database_functions.get_company_config(company_id)

    if isinstance(domain_info, dict) and "error" in domain_info:
        return domain_info, 500

    if not domain_info:
        return {"error": f"Configuración no encontrada para company_id: {company_id}"}, 404

    try:
        client = erp_auth.get_erp_client(domain_info)
        if isinstance(client, str):
            return {"error": f'Error conectando con el ERP: {client}'}, 500
        if not client:
            return {"error": "Error conectando con el ERP (Login fallido)"}, 500
    except Exception as e:
        return {'error': f'Error conectando con el ERP: {str(e)}'}, 500


    #========== MÉTODOS TOOL ==========
    try:
        #CLIENTES    
        if option == 'detalle_cliente':
            if not nif: return {"error": "Falta parámetro obligatorio: nif"}, 400
            cliente = client.get_customer_by_nif(nif)
            print(cliente)
            return cliente

        #SINIESTROS
        #Necesita otro dato en el JSON de entrada 'nif_cliente'
        if option == 'get_claims':
            if not nif: return {"error": "Falta parámetro obligatorio: nif"}, 400
            siniestros_cliente = client.get_customer_claims_by_category(nif,lines)
            return siniestros_cliente

        if option == 'get_claim_by_risk':
            if not risk: return {"error": "Falta parámetro obligatorio: risk"}, 400
            siniestro = client.get_claim_by_risk(nif,risk)
            return siniestro

        if option == 'get_status_claims':
            if not id_siniestro: return {"error": "Falta parámetro obligatorio: id_siniestro"}, 400
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
                except Exception as e:
                    print(f"Error buscando cliente de siniestro en Zoa: {e}")
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
                    print(f"Siniestro {siniestro.get('desc_siniestro')} enviado: {res_envio.json()}")
                except Exception as e:
                    print(f"Error enviando mensaje de siniestro: {e}")

                seguimiento_siniestros.append({
                    'desc_siniestro': siniestro.get('desc_siniestro'),
                    'client_name': nombre,
                    'gestor': gestor
                })

            return seguimiento_siniestros
        
        '''
        #Recibo nif y un JSON "datos_siniestro" con procedure,blame,num_poliza,incidence_date
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

        # POLIZAS
        if option == 'get_policies':
            if not nif: return {"error": "Falta parámetro obligatorio: nif"}, 400
            return client.get_all_policys_by_client_category(nif, lines)

        #ELIMINAR AL TERMINAR PRUEBAS
        if option == 'get_policy_by_num':
            if not num_poliza: return {"error": "Falta parámetro obligatorio: num_poliza"}, 400
            return client.get_policy_by_num(num_poliza)
        #------------------------

        #Consulta
        if option == 'get_doc_policies':
            if not num_poliza: return {"error": "Falta parámetro obligatorio: num_poliza"}, 400
            return client.get_policy_doc_by_policynum(num_poliza)

        #RECIBOS (Impagos, Duplicado recibo, Renovaciones)
        #Impagos
        if option == 'info_banco_devolucion':
            if not num_poliza: return {"error": "Falta parámetro obligatorio: num_poliza"}, 400
            api_poliza = client.get_policy_by_num(num_poliza)
            cust_banks = api_poliza.get('customer').get('bank_accounts')

            cust_acc_num = 0
            for cust_bank in cust_banks:
                if cust_bank.get('default_account') == True:
                    cust_acc_num = cust_bank.get('account_number')
                    break
            return cust_acc_num

        #Duplicado recibo
        if option == 'documento_recibo':
            if not num_poliza: return {"error": "Falta parámetro obligatorio: num_poliza"}, 400
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

        #Renovaciones
        if option == 'renovaciones_auto_semana':
            url = "https://flow-zoav2-673887944015.europe-southwest1.run.app"
            renovaciones_vigentes = []
            renovaciones = client.get_renewals_lable(start_date,frequency)
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
                            
                try:
                    res_zoa = requests.post(url, json=payload_search, timeout=10)
                    res_zoa.raise_for_status()
                    datos_zoa = res_zoa.json()
                    client_phone = datos_zoa.get('phone')
                except Exception as e:
                    print(f"Error buscando cliente en Zoa: {e}")
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
                    print(f"Resultado envío: {template_enviado.json()}")
                except Exception as e:
                    print(f"Error enviando template: {e}")

                # Añadir a la lista de retorno
                gestor = json_cliente.get('management_user', {})
                renovaciones_vigentes.append({
                    'client_nif': nif,
                    'client_name': nombre,
                    'gestor': gestor if gestor else 'Sin gestor'
                })

            return renovaciones_vigentes

    except Exception as e:
        return {'error': f"Error ejecutando la operación {option}: {str(e)}"}, 500




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
    except Exception as e:
        return (f"Error buscando cliente en Zoa: {e}")
