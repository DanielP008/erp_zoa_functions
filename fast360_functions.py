import requests
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from utils import get_phones

logger = logging.getLogger(__name__)

class Fast360APIError(Exception):
    pass

class Fast360Client:
    def __init__(self, domain: str, association: str, association_id: str, brokerage_id: str, office_id: str):
        self.domain = domain
        self.association = association
        self.association_id = association_id
        self.brokerage_id = brokerage_id
        self.office_id = office_id
        
        self.BASE_URL = "https://blackbox.fast360cloud.com"
        self.AUTH_URL = f"{self.BASE_URL}/api/auth/login/{self.domain}api"
        self.api_root = f"{self.BASE_URL}/api/customers/{self.domain}"
        
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None

    def login(self, username: str, password: str) -> Dict[str, Any]:
        try:
            payload = {
                "Login": username,
                "Password": password,
                "Asociacion": self.association
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(self.AUTH_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data.get("AccessToken")
            self.refresh_token = data.get("RefreshToken")
            self.expires_at = datetime.now() + timedelta(hours=1) 
            
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
            return data
        except Exception as e:
            logger.error(f"Fast360 Login failed: {e}")
            raise Fast360APIError(f"Authentication failed: {str(e)}")

    def _ensure_valid_token(self):
        if not self.access_token:
            raise Fast360APIError("No active session. Call login() first.")
        
        if self.expires_at and datetime.now() >= self.expires_at - timedelta(seconds=60):
            # In a real scenario, we might re-login or use refresh token
            pass

    def _make_request(self, endpoint: str, extra_params: Optional[Dict] = None) -> Any:
        self._ensure_valid_token()
        url = f"{self.api_root}/{endpoint}"
        
        request_data = {
            "Asociacion": self.association,
            "AsociacionId": self.association_id,
            "CorreduriaId": self.brokerage_id,
        }
        if self.office_id:
            request_data["OficinaId"] = self.office_id
            
        if extra_params:
            request_data.update(extra_params)
            
        payload = {"Request": request_data}
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        response_obj = data.get("Response", {})
        errors = response_obj.get("Errors", [])
        if errors:
            raise Fast360APIError(f"API Error in {endpoint}: {errors}")
            
        result_str = response_obj.get("Result")
        if result_str:
            try:
                # Result can be a JSON string inside the JSON response
                return json.loads(result_str)
            except json.JSONDecodeError:
                return result_str
        return response_obj

    # ========== Interface methods for main.py ==========

    def get_customer_by_nif(self, nif: str) -> List[Dict]:
        result = self._make_request("ConsultaClienteDniNif", {"DniNif": nif})
        client_data = result.get("ClienteConsulta")
        if client_data:
            return [{
                "id": client_data.get("Id"),
                "name": client_data.get("Nombre"),
                "surname": f"{client_data.get('Apellido1', '')} {client_data.get('Apellido2', '')}".strip(),
                "legalId": client_data.get("Documento"),
                "phone": self._extract_principal_phone(client_data),
                "email": self._extract_principal_email(client_data)
            }]
        return []

    def _extract_principal_phone(self, client_data: Dict) -> str:
        phones = client_data.get("Telefonos", [])
        for p in phones:
            if p.get("Principal"):
                return p.get("Numero")
        return phones[0].get("Numero") if phones else ""

    def _extract_principal_email(self, client_data: Dict) -> str:
        emails = client_data.get("DireccionesCorreo", [])
        for e in emails:
            if e.get("Principal"):
                return e.get("Direccion")
        return emails[0].get("Direccion") if emails else ""

    def get_customer_policies(self, nif: str) -> List[Dict]:
        customers = self.get_customer_by_nif(nif)
        if not customers:
            return []
        
        client_id = customers[0].get("id")
        result = self._make_request("PolizasCliente", {"ClienteId": client_id})
        policies = result.get("PolizasCliente", [])
        
        mapped_policies = []
        for p in policies:
            # Note: Fetching full details for each policy to get 'risk' and 'company/ramo' info
            policy_id = p.get("Id")
            detail = self.get_policy_by_id(policy_id)
            pd = detail.get("PolizaConsulta", {})
            mapped_policies.append({
                "id": policy_id,
                "number": p.get("NumeroPoliza"),
                "status": {"id": "V" if not p.get("FechaAnulacion") else "A"},
                "risk": pd.get("Riesgos", [""])[0] if isinstance(pd.get("Riesgos"), list) else pd.get("Riesgos", ""),
                "company": {"name": pd.get("Compania"), "id": pd.get("Compania")},
                "subcategory": {"name": pd.get("Ramo"), "category": {"name": pd.get("Ramo")}}
            })
        return mapped_policies

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str = None) -> List[Dict]:
        policies = self.get_customer_policies(nif)
        filtered = []
        ramo_normalized = ramo.lower().replace(".", "")
        for p in policies:
            category_name = p.get("subcategory", {}).get("category", {}).get("name", "").lower().replace(".", "")
            subcategory_name = p.get("subcategory", {}).get("name", "").lower().replace(".", "")
            
            if ramo_normalized in subcategory_name or ramo_normalized in category_name:
                company_name = p.get("company", {}).get("name", "")
                filtered.append({
                    "number": p.get("number"),
                    "company_id": p.get("company", {}).get("id"),
                    "company_name": company_name,
                    "risk": p.get("risk"),
                    "phones": get_phones(company_name)
                })
        return filtered

    def get_all_policys_by_client_risk(self, nif: str, risk: str, company_id: str = None) -> List[Dict]:
        policies = self.get_customer_policies(nif)
        filtered = []
        for p in policies:
            if risk.lower() in p.get("risk", "").lower():
                company_name = p.get("company", {}).get("name", "")
                filtered.append({
                    "number": p.get("number"),
                    "company_id": p.get("company", {}).get("id"),
                    "company_name": company_name,
                    "risk": p.get("risk"),
                    "phones": get_phones(company_name)
                })
        return filtered

    def get_customer_claims_by_category(self, nif: str, ramo: str) -> List[Dict]:
        policies = self.get_customer_policies(nif)
        all_claims = []
        ramo_normalized = ramo.lower().replace(".", "")
        
        for p in policies:
            category_name = p.get("subcategory", {}).get("category", {}).get("name", "").lower().replace(".", "")
            if ramo_normalized in category_name:
                claims_result = self._make_request("SiniestrosPoliza", {"PolizaId": p.get("id")})
                claims = claims_result.get("SiniestrosPoliza", [])
                for c in claims:
                    all_claims.append({
                        "id": c.get("Id"),
                        "opening_date": c.get("FechaDeclaracion"),
                        "risk": p.get("risk"),
                        "status": "Pendiente"
                    })
        return all_claims

    def get_claim_by_risk(self, nif: str, risk: str) -> List[Dict]:
        policies = self.get_customer_policies(nif)
        all_claims = []
        for p in policies:
            if risk.lower() in p.get("risk", "").lower():
                claims_result = self._make_request("SiniestrosPoliza", {"PolizaId": p.get("id")})
                claims = claims_result.get("SiniestrosPoliza", [])
                for c in claims:
                    all_claims.append({
                        "id": c.get("Id"),
                        "opening_date": c.get("FechaDeclaracion"),
                        "risk": p.get("risk"),
                        "status": "Pendiente"
                    })
        return all_claims

    def get_claim_status(self, claim_id: str) -> Dict:
        result = self._make_request("ConsultaSiniestro", {"SiniestroId": claim_id})
        claim = result.get("SiniestroConsulta", {})
        return {"Status": claim.get("Situacion")}

    def get_new_flagged_claims(self) -> List[Dict]:
        return []

    def get_claim_by_company_reference(self, company_reference: str) -> List[Dict]:
        return []

    def get_claim_assessment_by_num(self, num_claim: str) -> List[Dict]:
        return []

    def add_claim_assessment_by_num(self, num_claim: str, assessment_data: Dict) -> Dict:
        return {}

    def get_policy_by_id(self, policy_id: str) -> Dict:
        return self._make_request("ConsultaPoliza", {"PolizaId": policy_id})

    def get_policy_by_num(self, policy_num: str) -> List[Dict]:
        logger.warning(f"get_policy_by_num ({policy_num}) not directly supported in Fast360.")
        return []

    def get_new_policies_today(self) -> List[Dict]:
        return []

    def get_policy_doc_by_policynum(self, policy_num: str) -> List[Dict]:
        return []

    def get_returned_receipts(self, start_date=None, end_date=None) -> List[Dict]:
        return []

    def get_newest_receipt(self, num_poliza: str) -> Dict:
        return {}

    def get_active_receipt(self, num_poliza: str) -> Dict:
        return {}

    def get_doc_receipts_by_num_policy(self, num_poliza: str) -> List[Dict]:
        return []

    def get_customer_phone_by_nif(self, nif: str) -> Optional[str]:
        customers = self.get_customer_by_nif(nif)
        if customers:
            return customers[0].get("phone")
        return None

    def post_customer(self, customer: Dict) -> Dict:
        """
        Creates a customer using the AltaCliente endpoint.
        Maps standard customer fields to Fast360 structure.
        """
        # Mapping standard fields to Fast360
        first_name = customer.get("first_name", customer.get("name", ""))
        last_name = customer.get("last_name", customer.get("surname", ""))
        
        # Split last name if it's a single string with space
        parts = last_name.split(" ", 1)
        apellido1 = parts[0]
        apellido2 = parts[1] if len(parts) > 1 else ""

        payload = {
            "Nombre": first_name,
            "Apellido1": apellido1,
            "Apellido2": apellido2,
            "Documento": customer.get("legalId", customer.get("nif", "")),
            "TipoDocumento": "NI",  # Defaulting to NIF
            "Direcciones": [
                {
                    "Direccion": customer.get("address_street", customer.get("address", "")),
                    "Numero": customer.get("address_number", ""),
                    "Piso": customer.get("address_floor", ""),
                    "IdPoblacion": 0, # Placeholder, search might be needed
                    "Principal": True
                }
            ],
            "Telefonos": [
                {
                    "Numero": customer.get("phone", ""),
                    "Tipo": "M", # Movil
                    "Principal": True
                }
            ],
            "DireccionesCorreo": [
                {
                    "Direccion": customer.get("email", ""),
                    "Principal": True
                }
            ]
        }
        
        return self._make_request("AltaCliente", payload)

    def post_candidate(self, candidate: Dict) -> Dict:
        """
        Fast360 doesn't distinguish between candidates and customers in the provided API.
        """
        return self.post_customer(candidate)

    def get_new_candidates_today(self) -> List[Dict]:
        return []

    def get_candidate_by_nif(self, nif: str) -> List[Dict]:
        return self.get_customer_by_nif(nif)

    def process_load_renewals(self, **kwargs) -> List[Dict]:
        return []

    def add_document_to_claim_by_num(self, num_claim: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        # Similar to policy
        raise Fast360APIError("Search by claim number not supported for document upload in this version.")

    def add_document_to_policy_by_num(self, num_poliza: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        # Note: Finding policy GUID by number is complex in Fast360 without a global search.
        # This implementation assumes the policy must be found first.
        # For now, it will fail if a search mechanism isn't clear.
        raise Fast360APIError("Search by policy number not supported for document upload in this version.")

    def add_document_to_customer_by_nif(self, nif: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        customers = self.get_customer_by_nif(nif)
        if not customers:
            raise Fast360APIError(f"Customer with NIF {nif} not found for document upload.")
        
        customer_id = customers[0].get("id")
        return self._upload_document(customer_id, 0, filename, base64_content, notes)

    def _upload_document(self, entity_id: str, entity_type: int, filename: str, base64_content: str, notes: str = "") -> Dict:
        """
        Generic AltaDocumento call.
        TipoEntidad: 0=Cliente, 1=Poliza, 2=Recibo, 3=Siniestro
        """
        name_parts = filename.rsplit(".", 1)
        name = name_parts[0]
        ext = f".{name_parts[1]}" if len(name_parts) > 1 else ""

        payload = {
            "EntidadId": entity_id,
            "TipoEntidad": entity_type,
            "Nombre": name,
            "Extension": ext,
            "Descripcion": notes,
            "Imagen": base64_content
        }
        return self._make_request("AltaDocumento", payload)

    def close(self):
        self.session.close()
