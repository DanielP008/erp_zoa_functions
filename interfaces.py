from typing import TypedDict, Optional, List, Union, Dict

# --- DATA INTERFACES (CODE DOCUMENTATION) ---

class BaseRequest(TypedDict):
    company_id: str  # Mandatory
    option: str      # Mandatory

class DetalleClienteRequest(BaseRequest): # option: 'detalle_cliente'
    nif: str         # Mandatory

class GetPoliciesRequest(BaseRequest): # option: 'get_policies'
    nif: str         # Mandatory
    lines: Optional[str] # Optional

class GetClaimsRequest(BaseRequest): # option: 'get_claims'
    nif: str         # Mandatory

class GetClaimByRiskRequest(BaseRequest): # option: 'get_claim_by_risk'
    nif: str         # Mandatory
    risk: str        # Mandatory

class GetDocPoliciesRequest(BaseRequest): # option: 'get_doc_policies'
    num_poliza: str  # Mandatory

class GetPolicyByNumRequest(BaseRequest): # option: 'get_policy_by_num'
    num_poliza: str  # Mandatory

class DocumentoReciboRequest(BaseRequest): # option: 'documento_recibo'
    num_poliza: str  # Mandatory

class InfoBancoDevolucionRequest(BaseRequest): # option: 'info_banco_devolucion'
    num_poliza: str  # Mandatory

class RenovacionesAutoSemanaRequest(BaseRequest): # option: 'renovaciones_auto_semana'
    start_date: Optional[str] 
    frequency: Optional[int]   

class RenovacionesRecibosRequest(BaseRequest): # option: 'renovaciones_recibos'
    start_date: Optional[str]
    frequency: Optional[int]

class GetStatusClaimsRequest(BaseRequest): # option: 'get_status_claims'
    id_siniestro: int # Mandatory


class CreateCustomerRequest(BaseRequest): # option: 'create_customer'
    name: str        # Mandatory
    surname: str     # Mandatory
    nif: str         # Mandatory
    address: str     # Mandatory

class AddDocumentClaimRequest(BaseRequest): # option: 'add_document_claim'
    num_claim: str # Mandatory
    filename: str    # Mandatory
    base64_content: str # Mandatory
    notes: Optional[str]

class AddDocumentPolicyRequest(BaseRequest): # option: 'add_document_policy'
    num_poliza: str  # Mandatory
    filename: str    # Mandatory
    base64_content: str # Mandatory
    notes: Optional[str]

# ---------------------------------------------------

# --- OUTPUT INTERFACES (RESPONSES) ---

class GetClaimsResponse(TypedDict): # option: 'get_claims'
    id: str
    opening_date: str
    risk: str
    status: str

class GetClaimByRiskResponse(TypedDict): # option: 'get_claim_by_risk'
    id: str
    opening_date: str
    risk: str
    status: str
    

class GetPoliciesResponse(TypedDict): # option: 'get_policies'
    number: str
    company_id: str
    company_name: str
    risk: str
    phones: Dict[str, str]

class GetDocPoliciesResponse(TypedDict): # option: 'get_doc_policies'
    description: str
    filename: str
    data: str # Base64

class DocumentoReciboResponse(TypedDict): # option: 'documento_recibo'
    description: str
    filename: str
    data: str # Base64

class RenovacionesAutoSemanaResponse(TypedDict): # option: 'renovaciones_auto_semana'
    client_nif: str
    client_name: str
    gestor: str # Or Dict

class RenovacionesRecibosResponse(TypedDict): # option: 'renovaciones_recibos'
    client_nif: str
    client_name: str
    gestor: str # Or Dict

class GetStatusClaimsResponse(TypedDict): # option: 'get_status_claims'
    Status: str

class DetalleClienteResponse(TypedDict): # option: 'detalle_cliente'
    id: int
    legal_id: str
    name: str
    surname1: str
    phone: str
    email: str
    address: Dict

class CreateCustomerResponse(TypedDict): # option: 'create_customer'
    id: int
    legal_id: str
    name: str
    surname1: str
    address: Dict

class AddDocumentResponse(TypedDict): # option: 'add_document_claim' / 'add_document_policy'
    id: int
    filename: str
    description: str


