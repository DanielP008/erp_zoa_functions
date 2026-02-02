from typing import TypedDict, Optional, List, Union, Dict

# --- INTERFACES DE DATOS (DOCUMENTACIÓN DE CÓDIGO) ---

class BaseRequest(TypedDict):
    company_id: str  # Obligatorio
    option: str      # Obligatorio

class DetalleClienteRequest(BaseRequest): # option: 'detalle_cliente'
    nif: str         # Obligatorio

class GetPoliciesRequest(BaseRequest): # option: 'get_policies'
    nif: str         # Obligatorio
    lines: Optional[str] # Opcional

class GetClaimsRequest(BaseRequest): # option: 'get_claims'
    nif: str         # Obligatorio

class GetDocPoliciesRequest(BaseRequest): # option: 'get_doc_policies'
    num_poliza: str  # Obligatorio

class GetPolicyByNumRequest(BaseRequest): # option: 'get_policy_by_num'
    num_poliza: str  # Obligatorio

class DocumentoReciboRequest(BaseRequest): # option: 'documento_recibo'
    num_poliza: str  # Obligatorio

class InfoBancoDevolucionRequest(BaseRequest): # option: 'info_banco_devolucion'
    num_poliza: str  # Obligatorio

class RenovacionesAutoSemanaRequest(BaseRequest): # option: 'renovaciones_auto_semana'
    start_date: Optional[str] 
    frequency: Optional[int]   

class GetStatusClaimsRequest(BaseRequest): # option: 'get_status_claims'
    id_siniestro: int # Obligatorio

# ---------------------------------------------------

# --- INTERFACES DE SALIDA (RESPUESTAS) ---

class GetClaimsResponse(TypedDict): # option: 'get_claims'
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
    gestor: str # O Dict

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

