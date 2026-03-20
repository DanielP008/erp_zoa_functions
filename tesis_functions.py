import requests
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from utils import get_phones
import zoa_functions

logger = logging.getLogger(__name__)

class TesisAPIError(Exception):
    pass

class TesisClient:
    def __init__(self, api_key: str = "", environment: str = "production"):
        """
        Inicializa el cliente para Codeoscopic / Tesis Broker Manager.
        """
        self.api_key = api_key
        self.environment = environment
        
        if self.environment == "production":
            self.BASE_URL = "https://portal.api.codeoscopic.io"
        else:
            self.BASE_URL = "https://portal.api-int.codeoscopic.io"
            
        self.session = requests.Session()
        self.access_token = None
        self.expires_at = None

    def login(self, username: str, password: str, x_user_email: str) -> Dict[str, Any]:
        """
        Autentica en el ERP Tesis (Codeoscopic) y guarda el token usando client_credentials.
        """
        try:
            if self.environment == "production":
                auth_url = "https://api.codeoscopic.io/oauth2/token"
            else:
                auth_url = "https://api-int.codeoscopic.io/oauth2/token"
                
            payload = {
                "grant_type": "client_credentials",
                "client_id": username,
                "client_secret": password
            }
                
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            # The API expects form data, so we use 'data=payload' not 'json=payload'
            response = requests.post(auth_url, data=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self.expires_at = datetime.now() + timedelta(seconds=expires_in) 
            
            self.x_user_email = x_user_email
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "X-User-Email": self.x_user_email
            })
            return data
        except Exception as e:
            logger.error(f"Tesis Login failed: {e}")
            raise TesisAPIError(f"Authentication failed: {str(e)}")

    def _ensure_valid_token(self):
        if not self.access_token:
            raise TesisAPIError("No active session. Call login() first.")
        
        if self.expires_at and datetime.now() >= self.expires_at - timedelta(seconds=60):
            # Lógica para refrescar el token si es necesario
            pass

    def _make_request(self, method: str, endpoint: str, extra_params: Optional[Dict] = None, data: Optional[Dict] = None, retry: bool = True) -> Any:
        self._ensure_valid_token()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = self.session.request(method=method, url=url, params=extra_params, json=data)
            response.raise_for_status()
            
            if response.status_code == 204 or not response.content:
                return {}
                
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API Error in {endpoint}: {e}")
            raise TesisAPIError(f"API Error in {endpoint}: {str(e)}")

    # ========== CRM / Customer Methods ==========

    def get_customer_by_nif(self, nif: str) -> List[Dict]:#Podemos no necesitar mapear, pero asi mantenemos compatibilidad con el agente
        result = self._make_request("GET", "/clients", extra_params={"identificationDocumentId": nif})
        
        clients_list = result if isinstance(result, list) else result.get("data", [])
        mapped_clients = []
        
        for client in clients_list:
            # Extract primary phone
            phone = ""
            for p in client.get("phones", []):
                if p.get("primary"):
                    phone = p.get("number", "")
                    break
            if not phone and client.get("phones"):
                phone = client.get("phones")[0].get("number", "")
                
            # Extract primary email
            email = ""
            for e in client.get("emails", []):
                if e.get("primary"):
                    email = e.get("address", "")
                    break
            if not email and client.get("emails"):
                email = client.get("emails")[0].get("address", "")
                
            doc = client.get("identificationDocument", {})
            mapped_clients.append({
                "id": client.get("id"),
                "name": client.get("name", ""),
                "surname": f"{client.get('surname', '')} {client.get('surname2', '')}".strip(),
                "legal_id": doc.get("id", ""), # Compatibilidad ebroker
                "legalId": doc.get("id", ""),  # Compatibilidad fast360
                "phone": phone,
                "email": email
            })
            
        return mapped_clients

    def get_customer_policies(self, nif: str) -> List[Dict]:
        return []

    def post_customer(self, customer: Dict) -> Dict:
        """
        Crea un cliente. Mapear los campos estándar a los que requiere Tesis.
        """
        name = customer.get("first_name", customer.get("name", ""))
        surname = customer.get("last_name", customer.get("surname", ""))
        nif = customer.get("legalId", customer.get("nif", ""))
        email = customer.get("email", "")
        phone = customer.get("phone", "")
        
        # Determine document type (NIF, NIE, Passport, CIF)
        # Defaulting to NIF, with a soft check for NIE (X, Y, Z start)
        doc_type = "NIF"
        nif_upper = nif.upper() if nif else ""
        if nif_upper.startswith(("X", "Y", "Z")):
            doc_type = "NIE"
        elif nif_upper and nif_upper[0].isalpha() and not nif_upper.startswith(("X", "Y", "Z")):
            doc_type = "CIF"
            
        payload = {
            "identificationDocument": {
                "type": {
                    "id": doc_type
                },
                "id": nif
            },
            "name": name,
            "surname": surname,
            "status": {
                "id": "Active"
            }
        }
        
        # Opcionales según el payload base
        addresses_list = []
        address = customer.get("address", "")
        if address:
            addresses_list.append({
                "postalCode": customer.get("postal_code", ""),
                "street": address, # Optional based on true capabilities of Zoa
                "primary": True
            })
        if addresses_list:
            payload["addresses"] = addresses_list

        if email:
            payload["emails"] = [
                {
                    "address": email,
                    "primary": True
                }
            ]
            
        if phone:
            payload["phones"] = [
                {
                    "number": phone.replace(" ", ""),
                    "primary": True
                }
            ]

        # Call Tesis wrapper
        return self._make_request("POST", "/clients", data=payload)

    def update_customer(self, nif: str, customer_data: Dict) -> Dict:
        """
        Updates a client.
        """
        customer_id = customer_data.get("id")
        if not customer_id:
            if not nif:
                raise ValueError("NIF is required to find customer for update if 'id' is not provided in data")
            customers = self.get_customer_by_nif(nif)
            if not customers:
                raise ValueError(f"Customer with NIF {nif} not found")
            customer_id = customers[0].get("id")

        return self._make_request("PUT", f"/clients/{customer_id}", data=customer_data)

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str = None) -> List[Dict]:
        polizas = self.get_customer_policies(nif)
        polizas_ramo = []
        ramo_normalized = ramo.lower().replace('.', '')
        for p in polizas:
            subcategory_name = p.get('subcategory', {}).get('name', '').lower().replace('.', '')
            category_name = p.get('subcategory', {}).get('category', {}).get('name', '').lower().replace('.', '')
            
            if ramo_normalized in subcategory_name or ramo_normalized in category_name:
                company_name = p.get('company', {}).get('name', '')
                polizas_ramo.append({
                    'number': p.get('number', ''),
                    'company_id': p.get('company', {}).get('id', ''),
                    'company_name': company_name,
                    'risk': p.get('risk', ''),
                    'phones': get_phones(company_name)
                })
        return polizas_ramo

    def get_all_policys_by_client_risk(self, nif: str, risk: str, company_id: str = None) -> List[Dict]:
        return []

    def get_customer_phone_by_nif(self, nif: str) -> Optional[str]:
        customers = self.get_customer_by_nif(nif)
        if customers and len(customers) > 0:
             return customers[0].get('phone')
        return None

    # ========== Claims Methods ==========

    def get_customer_claims_by_category(self, nif: str, ramo: str) -> List[Dict]:
        return []

    def get_claim_by_risk(self, nif: str, risk: str) -> List[Dict]:
        return []

    def get_claim_labels(self, claim_id: int) -> List[Dict]:
        return []

    def get_claim_by_date(self, date: str) -> List[Dict]:
        return []

    def get_claim_status(self, claim_id: int) -> Dict:
        return {}

    def get_new_flagged_claims(self) -> Dict:
        return {}

    def get_claim_by_company_reference(self, company_reference: str) -> List[Dict]:
        return []

    def get_claim_assessment_by_num(self, num_claim: str) -> List[Dict]:
        return []

    def add_claim_assessment_by_num(self, num_claim: str, assessment_data: Dict) -> Dict:
        return {}

    # ========== Policies Methods ==========

    def get_policy_by_num(self, policy_num: str) -> List[Dict]:
        return []

    def get_new_policies_today(self) -> List[Dict]:
        return []

    # ========== Candidates Methods ==========

    def get_candidate_by_nif(self, nif: str) -> List[Dict]:
        return []

    def post_candidate(self, candidate: Dict) -> Dict:
        return {}

    def get_new_candidates_today(self) -> List[Dict]:
        return []

    # ========== Receipts Methods ==========

    def get_receipts_by_num_policy(self, num_poliza: int) -> List[Dict]:
        return []

    def get_upcoming_receipts(self, start_date=None, frequency: int = 7) -> List[Dict]:
        return []

    def get_newest_receipt(self, num_poliza: str) -> Dict:
        return {}

    def get_active_receipt(self, num_poliza: str) -> Dict:
        return {}

    def get_returned_receipts(self, start_date=None, end_date=None) -> List[Dict]:
        return []

    def get_upcoming_renewals(self, start_date=None, frequency: int = 7) -> List[Dict]:
        return []

    # ========== Documents Methods ==========

    def add_document_to_claim(self, claim_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        return {}

    def add_document_to_claim_by_num(self, num_claim: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        return {}

    def add_document_to_policy(self, policy_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        return {}

    def add_document_to_policy_by_num(self, num_poliza: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        return {}

    def add_document_to_customer(self, customer_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        return {}

    def add_document_to_customer_by_nif(self, nif: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        return {}


    
    def get_document(self, document_id: int) -> Dict:
        return {}

    def get_policy_doc_by_policynum(self, policy_num: str) -> List[Dict]:
        return []

    def get_doc_receipts_by_num_policy(self, num_poliza: int) -> List[Dict]:
        return []

    # ========== Complex Operations ==========

    def process_load_renewals(self, company_id: str, start_date=None, frequency: int = 7, 
                              percent_threshold: float = 8.0, 
                              amount_threshold: float = 0.0) -> List[Dict]:
        return []

    def close(self):
        self.session.close()

