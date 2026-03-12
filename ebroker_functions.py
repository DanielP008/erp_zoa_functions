import requests
from utils import get_phones
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import zoa_functions

class EBrokerAPIError(Exception):
    pass

class EBrokerClient:
    def __init__(self, client_id: int = 20100995):
        self.realm_id = client_id
        if client_id == 20100995:
            self.ADMIN_API = "https://pre-erp.ebroker.es/erp-admin-services"
            self.BUSINESS_API = "https://pre-erp.ebroker.es/erp-business-services"
            self.CRM_API = "https://pre-erp.ebroker.es/erp-crm-services"
            self.AUTH_URL = "https://pre-sso.ebroker.es/realms/20100995/protocol/openid-connect/token"
        else:
            self.ADMIN_API = f"https://usr{client_id}.ebroker.es/erp-admin-services"
            self.BUSINESS_API = f"https://usr{client_id}.ebroker.es/erp-business-services"
            self.CRM_API = f"https://usr{client_id}.ebroker.es/erp-crm-services"
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
    def get_customer_by_nif(self, nif: str) -> List[Dict]:
        result = self._make_request("crm", "GET", f"/v1/customers?query=legalId:{nif}")
        return result

    def get_customer_policies(self, nif: str) -> List[Dict]:
        customers = self.get_customer_by_nif(nif)
        if not customers:
            return []  # Return empty list if no customer found

        customer_id = customers[0].get('id')
        if not customer_id:
            return []  # Return empty list if customer has no ID

        return self._make_request("crm", "GET", f"/v1/customers/{customer_id}/policies")

    def post_customer(self, customer: Dict) -> Dict:
        payload = customer.copy()
        payload.update({
                "management_office_id": 1,
                "production_office_id": 1,
                "charge_office_id": 1
        })
        return self._make_request("crm", "POST", "/v1/customers", data=payload)

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str=None) -> List[Dict]:
        polizas = self.get_customer_policies(nif)
        polizas_ramo = []
        for p in polizas:
            status_id = p.get('status', {}).get('id')
            subcategory_name = p.get('subcategory', {}).get('name', '').lower().replace('.', '')
            category_name = p.get('subcategory', {}).get('category', {}).get('name', '').lower().replace('.', '')
            ramo_normalized = ramo.lower().replace('.', '')

            # TODO RE-ENABLE V
            # if status_id == 'V':
            if ramo_normalized in subcategory_name or ramo_normalized in category_name:
                company_name = p.get('company', {}).get('name', '')
                company_id = p.get('company', {}).get('id', '')
                polizas_ramo.append({
                    'number': p.get('number', ''),
                    'company_id': company_id,
                    'company_name': company_name,
                    'risk': p.get('risk', ''),
                    'phones': get_phones(company_name)
                })
        return polizas_ramo
    
    def get_policies_by_renewal_date(self,renewal_date: str) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/policies?query=customer.managementUser.username:MARIAJESUS&size=20&query=status.id:V&query=renewalDate:{renewal_date}")
    def get_policies_by_effect_date(self,effect_date: str) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/policies?query=customer.managementUser.username:MARIAJESUS&size=20&query=status.id:V&query=effectDate:{effect_date}")

    def get_all_policys_by_client_risk(self, nif: str, risk: str, company_id: str=None) -> List[Dict]:
        polizas = self.get_customer_policies(nif)
        polizas_risk = []
        for p in polizas:
            risk_poliza = p.get('risk', '')
            if risk.lower() in risk_poliza.lower():
                company_name = p.get('company', {}).get('name', '')
                company_id = p.get('company', {}).get('id', '')
                polizas_risk.append({
                    'number': p.get('number', ''),
                    'company_id': company_id,
                    'company_name': company_name,
                    'risk': risk_poliza,
                    'phones': get_phones(company_name)
                })
        return polizas_risk


    def get_customer_claims_by_category(self, nif: str, ramo: str) -> List[Dict]:
        customers = self.get_customer_by_nif(nif)
        if not customers:
            return []  # Return empty list if no customer found

        customer_id = customers[0].get('id')
        if not customer_id:
            return []  # Return empty list if customer has no ID
        claims = self._make_request("crm", "GET", f"/v1/customers/{customer_id}/claims")
        claims_ramo = []
        for claim in claims:
            if ramo.lower().replace('.', '') in claim.get('subcategory', {}).get('name', '').lower().replace('.', '') or ramo.lower().replace('.', '') in claim.get('subcategory', {}).get('category', {}).get('name', '').lower().replace('.', '') :
                claims_ramo.append({
                    'id': claim.get('id', ''),
                    'opening_date': claim.get('opening_date', ''),
                    'risk': claim.get('policy', {}).get('risk', ''),
                    'status':claim.get('status', {}).get('description', '')
                })
        return claims_ramo

    def get_claim_by_risk(self, nif: str, risk: str) -> List[Dict]:
        customers = self.get_customer_by_nif(nif)
        if not customers:
            return []  # Return empty list if no customer found

        customer_id = customers[0].get('id')
        if not customer_id:
            return []  # Return empty list if customer has no ID
        claims = self._make_request("crm", "GET", f"/v1/customers/{customer_id}/claims")
        claims_ramo = []
        for claim in claims:
            if risk.lower() in claim.get('policy', {}).get('risk', '').lower() :
                claims_ramo.append({
                    'id': claim.get('id', ''),
                    'opening_date': claim.get('opening_date', ''),
                    'risk': claim.get('policy', {}).get('risk', ''),
                    'status':claim.get('status', {}).get('description', '')
                })
        return claims_ramo

    # ========== Business methods used by main.py ==========

    #CLAIMS
    def get_claim_by_company_reference(self, company_reference: str) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/claims?query=companyReference:{company_reference}&order=ASC")

    def get_claim_assessment_by_num(self, num_claim: str) -> List[Dict]:
        claim_list = self.get_claim_by_company_reference(num_claim)
        if not claim_list:
             raise ValueError(f"Siniestro con referencia {num_claim} no encontrado")
        claim_id = claim_list[0].get('id')
        return self._make_request("business", "GET", f"/v1/claims/{claim_id}/assessment")

    def add_claim_assessment_by_num(self, num_claim: str, assessment_data: Dict) -> Dict:
        """
        Adds assessment data to a claim.
        """
        claim_list = self.get_claim_by_company_reference(num_claim)
        if not claim_list:
             raise ValueError(f"Siniestro con referencia {num_claim} no encontrado")
        claim_id = claim_list[0].get('id')
        return self._make_request("business", "POST", f"/v1/claims/{claim_id}/assessment", data=assessment_data)

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

    #POLICIES
    def get_policy_by_num(self, policy_num: str) -> Dict:
        return self._make_request("business", "GET", f"/v1/policies?query=number:{policy_num}&order=ASC")



    #CUSTOMERS
    def get_customer_phone_by_nif(self, nif: str) -> Optional[str]:
        customers = self.get_customer_by_nif(nif)
        if customers and len(customers) > 0:
             return customers[0].get('phone')
        return None

    #CANDIDATES
    def get_candidate_by_nif(self, nif: str) -> List[Dict]:
        return self._make_request("crm", "GET", f"/v1/candidates?query=legalId:{nif}")

    def post_candidate(self, candidate: Dict) -> Dict:
        """
        Creates a candidate, ensuring office IDs are appended.
        """
        payload = candidate.copy()
        payload.update({
            "management_office_id": 1,
            "production_office_id": 1,
            "charge_office_id": 1
        })
        return self._make_request("crm", "POST", "/v1/candidates", data=payload)

    def get_new_candidates_today(self) -> List[Dict]:
        return self._make_request("crm", "GET", f"/v1/candidates?query=signupDate:{datetime.now().strftime('%Y-%m-%d')}")

    #RECEIPTS
    def get_receipts_by_num_policy(self, num_poliza: int) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/receipts?query=policy.number:{num_poliza}")

    def get_upcoming_receipts(self, start_date=None, frequency: int = 7):
        if not start_date:
            start_date = datetime.now()
        elif isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                # Try to correct format with days/months without zero-padding (e.g., 2001-2-9 -> 2001-02-09)
                try:
                    parts = start_date.split('-')
                    if len(parts) == 3:
                        fixed_date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                        start_date = datetime.strptime(fixed_date, "%Y-%m-%d")
                    else:
                        raise ValueError
                except ValueError:
                    start_date = datetime.now()
        ini_date = (start_date - timedelta(days=1)).strftime("%Y-%m-%d")
        fin_date = (start_date + timedelta(days=frequency)).strftime("%Y-%m-%d")
        endpoint = f"/v1/receipts?query=dueDate>{ini_date}&query=dueDate<{fin_date}&size=2000"
        receipts = self._make_request("business", "GET", endpoint)

        # Filter out receipts with status description 'ANULADO'
        filtered_receipts = []
        if isinstance(receipts, list):
            for receipt in receipts:
                status = receipt.get('status', {})
                if status and status.get('description') != 'ANULADO':
                    filtered_receipts.append(receipt)
            return filtered_receipts
        return receipts
    
    def get_returned_receipts(self, start_date=None, end_date=None) -> List[Dict]:
        """
        Retrieves receipts with specific returned statuses within a date range.
        Statuses:
        - PENDIENTE/DVTO.BANCO
        - PENDIENTE/DVTO. EN CÍA
        - PENDIENTE/DVTO.BANCO/ENTE
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
            
        # Ensure dates are datetime objects if strings are passed (basic handling)
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        str_start = start_date.strftime("%Y-%m-%d")
        str_end = end_date.strftime("%Y-%m-%d")

        statuses = [
            "PENDIENTE/DVTO.BANCO",
            "PENDIENTE/DVTO. EN CIA",
            "PENDIENTE/DVTO.BANCO/ENTE"
        ]

        all_receipts = []
        
        for status in statuses:
            try:
                # User requested no quotes and no encoding.
                # Format: ?query=status.description:STATUS,effectDate>START,effectDate<END&size=2000
                url = f"/v1/receipts?query=status.description:{status},effectDate>{str_start},effectDate<{str_end}&size=2000"
                receipts = self._make_request("business", "GET", url)
                if isinstance(receipts, list):
                    all_receipts.extend(receipts)
            except Exception as e:
                print(f"Error fetching receipts for status {status}: {e}")
                continue

        return all_receipts
    
    def get_upcoming_renewals(self, start_date=None, frequency: int = 7) -> List[Dict]:
        receipts = self.get_upcoming_receipts(start_date, frequency)
        if not receipts:
            return []
            
        policies = {}
        for receipt in receipts:
            policy = receipt.get('policy')
            if policy:
                # Ensure customer data is present since process_load_renewals needs it
                if 'customer' not in policy and 'customer' in receipt:
                     policy['customer'] = receipt['customer']
                     
                policy_id = policy.get('id')
                # Use policy number as key if ID is missing? No, ID should be there.
                if policy_id and policy_id not in policies:
                    policies[policy_id] = policy
                    
        return list(policies.values())

    
    #DOCUMENTS
    def add_document_to_claim_by_num(self, num_claim: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        claim_list = self.get_claim_by_company_reference(num_claim)
        if not claim_list:
             raise ValueError(f"Claim number {num_claim} not found")
        
        claim_id = claim_list[0].get('id')
        return self.add_document_to_claim(claim_id, filename, base64_content, notes,101)

    def add_document_to_claim(self, claim_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        """
        Uploads a document to a specific claim.
        """
        payload = {
            "filename": filename,
            "notes": notes,
            "base64_content": base64_content,
            "document_folder_id": document_folder_id
        }
        return self._make_request("business", "POST", f"/v1/claims/{claim_id}/documents", data=payload)
    def add_document_to_policy(self, policy_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        """
        Uploads a document to a specific policy.
        """
        payload = {
            "filename": filename,
            "notes": notes,
            "base64_content": base64_content,
            "document_folder_id": document_folder_id
        }
        return self._make_request("business", "POST", f"/v1/policies/{policy_id}/documents", data=payload)
    def add_document_to_customer_by_nif(self, nif: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        customer_list = self.get_customer_by_nif(nif)
        if not customer_list:
             raise ValueError(f"Customer number {nif} not found")
        
        customer_id = customer_list[0].get('id')
        return self.add_document_to_customer(customer_id, filename, base64_content, notes,101)

    def add_document_to_customer(self, customer_id: int, filename: str, base64_content: str, notes: str = "", document_folder_id: int = 101) -> Dict:
        """
        Uploads a document to a specific customer.
        """
        payload = {
            "filename": filename,
            "notes": notes,
            "base64_content": base64_content,
            "document_folder_id": document_folder_id
        }
        return self._make_request("business", "POST", f"/v1/customers/{customer_id}/documents", data=payload)
    def add_document_to_policy_by_num(self, num_poliza: str, filename: str, base64_content: str, notes: str = "") -> Dict:
        policy_list = self.get_policy_by_num(num_poliza)
        if not policy_list:
             raise ValueError(f"Policy number {num_poliza} not found")
        
        policy_id = policy_list[0].get('id')
        return self.add_document_to_policy(policy_id, filename, base64_content, notes,101)

    def import_zoa_client_notes(self, client_id: int, notes: List[Dict]) -> Dict:
        """
        Imports notes to a specific client.
        """
        payload = {
            "notes": notes
        }
        return self._make_request("business", "POST", f"/v1/clients/{client_id}/notes", data=payload)
    
    def get_document(self, document_id: int) -> Dict:
        return self._make_request("business", "GET", f"/v1/documents/{document_id}")

    def get_new_policies_today(self) -> List[Dict]:
        return self._make_request("business", "GET", f"/v1/policies?query=createdDate:{datetime.now().strftime('%Y-%m-%d')}")

    def get_policy_doc_by_policynum(self, policy_num: str) -> List[Dict]:
        resultado = []
        api_poliza = self.get_policy_by_num(policy_num)
        if api_poliza and len(api_poliza) > 0:
            documentos_poliza = api_poliza[0].get('documents', [])
            for documento_poliza in documentos_poliza:
                doc_id = documento_poliza.get('id')
                try:
                    doc_data = self.get_document(doc_id)
                except Exception:
                    continue

                filename = documento_poliza.get('filename', '')
                if filename.startswith("pol") and filename.endswith(".pdf"):
                    resultado.append({
                        'description': documento_poliza.get('description'),
                        'filename': filename,
                        'data': doc_data.get('base64_content'),
                    })

        return resultado

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

    def process_load_renewals(self, company_id: str, start_date=None, frequency: int = 7, 
                              percent_threshold: float = 8.0, 
                              amount_threshold: float = 0.0) -> List[Dict]:
        if start_date is None:
            start_date = (datetime.now() + timedelta(days=1))
            
        upcoming_renewals_policies = self.get_upcoming_renewals(start_date=start_date, frequency=frequency)
        result_list = []

        for policy in upcoming_renewals_policies:
            policy_num = policy.get('number')
            if not policy_num:
                continue

            receipts = self.get_receipts_by_num_policy(policy_num)
            
            latest_p = None
            latest_c = None

            # Sort by dueDate descending
            receipts.sort(key=lambda x: x.get('dueDate', ''), reverse=True)

            for r in receipts:
                status_id = r.get('status', {}).get('id', '')
                if not latest_p and 'P' in status_id:
                    latest_p = r
                if not latest_c and 'C' in status_id:
                    latest_c = r
                
                if latest_p and latest_c:
                    break
            
            if latest_p and latest_c:
                try:
                    p_premium = float(latest_p.get('total_premium', 0))
                    c_premium = float(latest_c.get('total_premium', 0))

                    if p_premium > 0:
                        diff = p_premium - c_premium
                        percent_diff = (diff / c_premium) * 100 if c_premium > 0 else 0

                        # Flag if either percentage or absolute amount exceeds threshold
                        is_flagged = percent_diff >= percent_threshold
                        if amount_threshold > 0:
                            is_flagged = is_flagged or (diff >= amount_threshold)

                        # Extract phone number from customer data
                        customer = policy.get("customer", {})
                        client_phone = ""
                        phones = customer.get("phones", [])
                        if phones and isinstance(phones, list):
                            client_phone = str(phones[0].get("number", ""))
                        elif isinstance(customer.get("phone"), str):
                            client_phone = customer.get("phone")

                        # Differentiate between Type A and Type B
                        if is_flagged:
                            title = f"Renovación tipo A {policy_num}"
                            tag = f">{int(percent_threshold)}%"
                        else:
                            title = f"Renovación tipo B {policy_num}"
                            tag = f"<{int(percent_threshold)}%"

                        # Create Card in Zoa
                        card_payload = {
                            "company_id": company_id,
                            "action": "cards",
                            "option": "create",
                            "title": title,
                            "phone": "34" + client_phone,
                            "card_type": "opportunity",
                            "pipeline_name": "Renovaciones",
                            "stage_name": "Nuevo",
                            "amount": p_premium,
                            "tags_name": tag
                        }
                        
                        try:
                            zoa_functions.create_card(card_payload)
                        except Exception:
                            pass # Or log error

                        # All processed renewals are added to result_list
                        result_list.append({
                            "policy_number": policy_num,
                            "client_nif": customer.get("legal_id"),
                            "p_receipt": {
                                "id": latest_p.get("id"),
                                "amount": p_premium,
                                "status": latest_p.get("status", {}).get("description")
                            },
                            "c_receipt": {
                                "id": latest_c.get("id"),
                                "amount": c_premium,
                                "status": latest_c.get("status", {}).get("description")
                            },
                            "percent_diff": round(percent_diff, 2),
                            "amount_diff": round(diff, 2),
                            "is_flagged": is_flagged
                        })
                except (ValueError, TypeError, ZeroDivisionError):
                    continue

        return result_list


    def close(self):
        for session in self.sessions.values():
            session.close()



# ========== Utility function relocated to utils.py ==========

