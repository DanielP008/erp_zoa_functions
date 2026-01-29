import requests
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EBrokerAPIError(Exception):
    pass

class EBrokerClient:
    def __init__(self, client_id: int = 20100995):
        self.realm_id = client_id
        if client_id == 20100995:
            self.ADMIN_API = "http://pre-erp.ebroker.es/erp-admin-services"
            self.BUSINESS_API = "http://pre-erp.ebroker.es/erp-business-services"
            self.CRM_API = "http://pre-erp.ebroker.es/erp-crm-services"
            self.AUTH_URL = "https://pre-sso.ebroker.es/realms/20100995/protocol/openid-connect/token"
        else:
            self.ADMIN_API = f"http://usr{client_id}.ebroker.es/erp-admin-services"
            self.BUSINESS_API = f"http://usr{client_id}.ebroker.es/erp-business-services"
            self.CRM_API = f"http://usr{client_id}.ebroker.es/erp-crm-services"
            self.AUTH_URL = f"https://sso.ebroker.es/realms/{client_id}/protocol/openid-connect/token"

        self.api_urls = {"admin": self.ADMIN_API, "business": self.BUSINESS_API, "crm": self.CRM_API}
        self.client_ids = {"admin": "erp-admin-services", "business": "erp-business-services", "crm": "erp-crm-services"}
        self.sessions = {"admin": requests.Session(), "business": requests.Session(), "crm": requests.Session()}
        self.tokens = {k: {"access_token": None, "refresh_token": None, "expires_at": None} for k in self.sessions}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        results = {}
        errors = []
        for api_type in ["admin", "business", "crm"]:
            try:
                payload = {"grant_type": "password", "client_id": self.client_ids[api_type], "username": username, "password": password}
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                response = requests.post(self.AUTH_URL, data=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                self.tokens[api_type]["access_token"] = data.get("access_token")
                self.tokens[api_type]["refresh_token"] = data.get("refresh_token", self.tokens[api_type]["refresh_token"])
                expires_in = data.get("expires_in", 300)
                self.tokens[api_type]["expires_at"] = datetime.now() + timedelta(seconds=expires_in)
                self.sessions[api_type].headers.update({"Authorization": f"Bearer {self.tokens[api_type]['access_token']}"})
                results[api_type] = data
            except Exception as e:
                logger.error(f"Login error for {api_type}: {e}")
                errors.append(str(e))
        if errors and len(errors) == 3:
            raise EBrokerAPIError(f"Authentication failed for all APIs: {'; '.join(errors)}")
        return results

    def refresh_access_token(self, api_type: str) -> Dict[str, Any]:
        if not self.tokens[api_type]["refresh_token"]:
            raise EBrokerAPIError(f"No refresh token for {api_type}")
        payload = {"grant_type": "refresh_token", "client_id": self.client_ids[api_type], "refresh_token": self.tokens[api_type]["refresh_token"]}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self.AUTH_URL, data=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        self.tokens[api_type]["access_token"] = data.get("access_token")
        if "refresh_token" in data:
            self.tokens[api_type]["refresh_token"] = data.get("refresh_token")
        expires_in = data.get("expires_in", 300)
        self.tokens[api_type]["expires_at"] = datetime.now() + timedelta(seconds=expires_in)
        self.sessions[api_type].headers.update({"Authorization": f"Bearer {self.tokens[api_type]['access_token']}"})
        return data

    def _ensure_valid_token(self, api_type: str):
        if not self.tokens[api_type]["access_token"]:
            raise EBrokerAPIError(f"No active session for {api_type}. Call login() first.")
        expires_at = self.tokens[api_type]["expires_at"]
        if expires_at and datetime.now() >= expires_at - timedelta(seconds=30):
            self.refresh_access_token(api_type)

    def _make_request(self, api_type: str, method: str, endpoint: str,
                      params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        self._ensure_valid_token(api_type)
        base_url = self.api_urls[api_type]
        url = f"{base_url}{endpoint}"
        response = self.sessions[api_type].request(method=method, url=url, params=params, json=data)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # ========== CRM methods used by main.py ==========
    def search_customers(self, query: str, sort: Optional[str] = None,
                         order: str = "ASC", page: int = 0, size: int = 20) -> List[Dict]:
        params = {"query": query, "page": page, "size": size, "order": order}
        if sort:
            params["sort"] = sort
        return self._make_request("crm", "GET", "/v1/customers", params=params)

    def get_customer_by_nif(self, nif: str) -> Dict:
        return self._make_request("crm", "GET", f"/v1/customers?query=legalId:{nif}&order=ASC")

    def get_customer_policies(self, nif: int) -> List[Dict]:
        customers = self.get_customer_by_nif(nif)
        if not customers or len(customers) == 0:
            return []
        customer_id = customers[0]['id']  # ← Extract just the ID number
        return self._make_request("crm", "GET", f"/v1/customers/{customer_id}/policies")

    def get_customer_active_policies(self, nif: int) -> List[Dict]:
        polizas_vigentes = []
        polizas = self.get_customer_policies(nif)
        for p in polizas:
            if p.get('status', {}).get('id') == 'V':
                company_name = p.get('company', {}).get('name', '')
                polizas_vigentes.append({
                    'company_name': company_name,
                    'risk': p.get('risk', ''),
                    'category_name': p.get('subcategory', {}).get('category', {}).get('name', ''),
                    'subcategory_name': p.get('subcategory', {}).get('name', ''),
                    'phones': get_phones(company_name)
                })
        return polizas_vigentes

    def get_all_policys_by_client_category(self,nif,ramo):
        polizas = self.get_customer_policies(nif)
        polizas_ramo = []
        for p in polizas:
            if p.get('status', {}).get('id') == 'V' :
                if ramo.lower().replace('.', '') in p.get('subcategory', {}).get('name', '').lower().replace('.', '') or ramo.lower().replace('.', '') in p.get('subcategory', {}).get('category', {}).get('name', '').lower().replace('.', '') :
                    company_name = p.get('company', {}).get('name', '')
                    company_id = p.get('company', {}).get('id', '')
                    polizas_ramo.append({
                        'company_id': company_id,
                        'company_name': company_name,
                        'risk': p.get('risk', ''),
                        'phones': get_phones(company_name)
                    })
        return polizas_ramo


    def get_customer_claims_by_category(self, nif: int,ramo:str) -> List[Dict]:
        customer_id = self.get_customer_by_nif(nif)[0]
        claims = self._make_request("crm", "GET", f"/v1/customers/{customer_id}/claims")
        claims_ramo = []
        for claim in claims:
            if ramo.lower().replace('.', '') in claim.get('subcategory', {}).get('name', '').lower().replace('.', '') or ramo.lower().replace('.', '') in claim.get('subcategory', {}).get('category', {}).get('name', '').lower().replace('.', '') :
                claims_ramo.append({
                    'id': claim.get('id', ''),
                    'opening_date': claim.get('opening_date', ''),
                    'risk': claim.get('risk', '')
                })
        return claims_ramo

    # ========== Business methods used by main.py ==========
    def get_claims(self, query: Optional[str] = None, sort: Optional[str] = None,
                   order: str = "ASC", page: int = 0, size: int = 20) -> List[Dict]:
        params = {"page": page, "size": size, "order": order}
        if query:
            params["query"] = query
        if sort:
            params["sort"] = sort
        return self._make_request("business", "GET", "/v1/claims", params=params)

    def get_claim_labels(self, claim_id: int) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/claims/{claim_id}/labels")

    def get_claim_by_date(self, date: str) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/claims?query=opening_date:{date.strftime('%Y/%m/%d')}&order=ASC")

    def get_claim_status(self, claim_id: int) -> Dict:
        return {"Status":self._make_request("business", "GET", f"/v1/claims/{claim_id}").get('status', {}).get('description', '')}

    def get_new_flagged_claims(self):
        timenow = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        claims = self.get_claim_by_date(timenow)
        data = {}
        for claim in claims:
            claimlbls = self.get_claim_labels(claim.get('id'))
            for claimlbl in claimlbls:
                policy = claim.get('policy', {})
                json_cliente = policy.get('customer', {})
                desc_siniestro = claim.get('description', {})
                plantilla = claimlbl.get("value")
                nombre = str(json_cliente.get('name', ''))
                riesgo = str(policy.get('risk', ''))
                fecha_ocurrencia = str(claim.get('sinister_date', ''))
                no_referencia = str(claim.get('company_reference', ''))
                gestor = json_cliente.get('management_user', {})
                params_comunicacion = f"{nombre};{riesgo};{fecha_ocurrencia};{no_referencia}"
                data = {
                    "nif": json_cliente.get('legal_id'),
                    "params": params_comunicacion,
                    "template_name": plantilla,
                    "desc_siniestro": desc_siniestro,
                    "gestor": gestor
                }
        return data

    def get_policy_by_num(self, policy_num: str) -> Dict:
        return self._make_request("business", "GET", f"/v1/policies?query=number:{policy_num}&order=ASC")

    def get_document(self, document_id: int) -> Dict:
        return self._make_request("business", "GET", f"/v1/documents/{document_id}")

    def get_policy_doc_by_policynum(self, policy_num: str) -> List[Dict]:
        resultado = []
        api_poliza = self.get_policy_by_num(policy_num)
        if api_poliza and len(api_poliza) > 0:
            documentos_poliza = api_poliza[0].get('documents', {})
            for documento_poliza in documentos_poliza:
                doc_data = self.get_document(documento_poliza.get('id'))
                filename = documento_poliza.get('filename', '')
                if filename.startswith("pol") and filename.endswith(".pdf"):
                    resultado.append({
                        'description': documento_poliza.get('description'),
                        'filename': filename,
                        'data': doc_data.get('base64_content'),
                    })
        return resultado

    def get_receipts_by_num_policy(self, num_poliza: int) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/receipts?query=policy.number:{num_poliza}")

    def get_doc_receipts_by_num_policy(self, num_poliza: int) -> List[Dict]:
        result = []
        recibos = self.get_receipts_by_num_policy(num_poliza)
        if recibos:
            recibo = recibos[0]
            docs_recibo = recibo.get('documents', [])
            for doc_recibo in docs_recibo:
                doc = self.get_document(doc_recibo.get('id'))
                result.append({'description': doc_recibo.get('description'), 'filename': doc_recibo.get('filename'), 'data': doc.get('base64_content')})
        return result

    def get_policies_for_specific_date(self, date) -> List[Dict]:
        params = {"query": f"renewalDate:{date}"}
        return self._make_request("business", "GET", "/v1/policies", params=params)

    def get_upcoming_renewals(self, start_date=None, frequency: int = 7):
        if start_date is None:
            start_date = datetime.now()
        master_policy_list = []
        for i in range(frequency):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            policies_day = self.get_policies_for_specific_date(date_str)
            master_policy_list.extend(policies_day)
        return master_policy_list

    def get_policy_labels(self, policy_id: int) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/policies/{policy_id}/labels")

    def get_renewals_lable(self, start_date, frequency):
        if start_date is None:
            start_date = datetime.now()
        result = []
        polizas = self.get_upcoming_renewals(start_date,frequency)
        for poliza in polizas:
            cliente = poliza.get('customer')
            lbls = self.get_policy_labels(poliza.get('id'))
            for lbl in lbls:
                if lbl != []:
                    nombre = str(cliente.get('name', ''))
                    ramo = str(polizas.get('subcategory', {}).get('name', ''))
                    riesgo = str(poliza.get('risk', ''))
                    prima = str(self.get_receipts_by_num_policy(polizas.get('number')).get('amount'))
                    nif = str(cliente.get('legal_id'))
                    gestor = str(cliente.get('management_user'))
                    plantilla = str(lbl.get("value"))
                    result.append({
                        'nif':nif,
                        'ramo':ramo,
                        'nombre':nombre,
                        'riesgo':riesgo,
                        'prima':prima, 
                        'plantilla':plantilla,
                        'gestor': gestor
                    })

# ========== Utility function required by kept methods ==========
def get_phones(company_name):
    if not company_name:
        return {}
    with open('insurance_phones.json', 'r', encoding='utf-8') as f:
        company_phones = json.load(f)
    comapnies = {
        'OCCIDENT': 'catalana_occidente',
        'GENERALI': 'generali',
        'GENERALI SEGUROS': 'generali',
        'MAPFRE': 'mapfre',
        'ALLIANZ': 'allianz',
        'AXA': 'axa',
        'ZURICH': 'zurich',
        'REALE': 'reale',
        'FIATC': 'fiatc',
        'MUTUA MADRILEÑA': 'mutua_madrilena',
        'SANITAS': 'sanitas',
        'ADESLAS': 'adeslas',
        'DKV': 'dkv',
        'ASISA': 'asisa',
        'PELAYO': 'pelayo',
        'LIBERTY': 'liberty',
        'HELVETIA': 'helvetia',
        'OCASO': 'ocaso',
        'SANTA LUCIA': 'santa_lucia',
        'QUALITAS': 'qualitas',
        'ARAG': 'arag',
        'DAS': 'das',
        'EUROINS': 'euroins',
        'PREVENTIVA': 'preventiva',
        'AIG': 'aig',
        'AURA': 'aura',
        'CESCE': 'cesce',
        'FE': 'fe',
        'PREVISORA GENERAL': 'previsora_general',
        'PREVISION MALLORQUINA': 'prevision_mallorquina',
        'SURNE': 'surne',
        'WR BERKLEY': 'wr_berkley'
    }
    company_upper = company_name.upper().strip()
    key = comapnies.get(company_upper)
    if key:
        return company_phones.get(key, {})
    company_lower = company_name.lower().replace(' ', '_')
    return company_phones.get(company_lower, {})
