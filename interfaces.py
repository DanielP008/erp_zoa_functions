from typing import TypedDict, Optional, List, Union, Dict

# --- DATA INTERFACES (CODE DOCUMENTATION) ---

class BaseRequest(TypedDict):
    company_id: str  # Mandatory
    option: str      # Mandatory

class DetalleClienteRequest(BaseRequest): # option: 'detalle_cliente'
    """
    Recupera los detalles de un cliente por su NIF/DNI.
    Llama a get_customer_by_nif en el ERP correspondiente.
    """
    nif: str         # Mandatory

class GetPoliciesRequest(BaseRequest): # option: 'get_policies'
    """
    Obtiene todas las pólizas activas asociadas a un cliente por su NIF o filtradas por ramo.
    Llama a get_all_policys_by_client_category o get_customer_policies.
    """
    nif: str         # Mandatory
    lines: Optional[str] # Optional

class GetClaimsRequest(BaseRequest): # option: 'get_claims'
    """
    Obtiene los siniestros de un cliente filtrados por un ramo específico.
    Llama a get_customer_claims_by_category en el ERP correspondiente.
    """
    nif: str         # Mandatory

class GetClaimByRiskRequest(BaseRequest): # option: 'get_claim_by_risk'
    """
    Obtiene los siniestros de un cliente filtrados por el riesgo de la póliza asociada (ej. matrícula).
    Llama a get_claim_by_risk en el ERP correspondiente.
    """
    nif: str         # Mandatory
    risk: str        # Mandatory

class GetDocPoliciesRequest(BaseRequest): # option: 'get_doc_policies'
    num_poliza: str  # Mandatory

class GetPolicyByNumRequest(BaseRequest): # option: 'get_policy_by_num'
    """
    Busca y retorna los detalles de una póliza específica usando su número.
    Llama a get_policy_by_num en el ERP correspondiente.
    """
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
    """
    Obtiene el estado actual de un siniestro a partir de su ID interno.
    Llama a get_claim_status en el ERP correspondiente.
    """
    id_siniestro: int # Mandatory


class CreateCustomerRequest(BaseRequest): # option: 'create_customer'
    """
    Da de alta a un nuevo cliente en el ERP.
    Llama a post_customer en el ERP correspondiente.
    """
    name: str        # Mandatory
    surname: str     # Mandatory
    nif: str         # Mandatory
    address: str     # Mandatory

class AddDocumentClaimRequest(BaseRequest): # option: 'add_document_claim'
    """
    Sube un documento asociado a un número de siniestro específico.
    Llama a add_document_to_claim_by_num.
    """
    num_claim: str # Mandatory
    filename: str    # Mandatory
    base64_content: str # Mandatory
    notes: Optional[str]


    notes: Optional[str]

class GetReturnedReceiptsRequest(BaseRequest): # option: 'get_returned_receipts'
    """
    Obtiene los recibos devueltos en un rango temporal.
    Llama a get_returned_receipts en el ERP.
    """
    start_date: Optional[str]
    end_date: Optional[str]

class AddDocumentPolicyRequest(BaseRequest): # option: 'add_document_policy'
    """
    Sube un documento asociado a una póliza específica.
    Llama a add_document_to_policy_by_num.
    """
    num_poliza: str  # Mandatory
    filename: str    # Mandatory
    base64_content: str # Mandatory
    notes: Optional[str]

class LoadRenewalsRequest(BaseRequest): # option: 'load_renewals'
    """
    Procesa las renovaciones masivas de una compañía evaluando incremento de prima.
    Llama a process_load_renewals.
    """
    percent_threshold: Optional[float]
    amount_threshold: Optional[float]

class GetNewFlaggedClaimsRequest(BaseRequest): # option: 'get_new_flagged_claims'
    """
    Calcula y obtiene los siniestros recientes que contienen una plantilla de aviso.
    """
    pass

class GetNewPoliciesTodayRequest(BaseRequest): # option: 'get_new_policies_today'
    """
    Obtiene las pólizas de nueva creación del día de hoy.
    """
    pass

class GetCustomerPhoneByNifRequest(BaseRequest): # option: 'get_customer_phone_by_nif'
    """
    Devuelve el número de teléfono principal de un cliente dado su NIF/DNI.
    """
    nif: str         # Mandatory

class AddDocumentCustomerRequest(BaseRequest): # option: 'add_document_customer'
    """
    Sube un documento al perfil de un cliente aportando su NIF/DNI.
    """
    nif: str         # Mandatory
    filename: str    # Mandatory
    base64_content: str # Mandatory
    notes: Optional[str]

class CreateCandidateRequest(BaseRequest): # option: 'create_candidate'
    """
    Crea un nuevo candidato en el ERP.
    """
    name: str        # Mandatory
    phone: str       # Mandatory

class GetNewCandidatesTodayRequest(BaseRequest): # option: 'get_new_candidates_today'
    """
    Obtiene los candidatos creados o modificados hoy.
    """
    pass

class GetCandidateByNifRequest(BaseRequest): # option: 'get_candidate_by_nif'
    """
    Obtiene los datos de un candidato buscando por NIF/DNI.
    """
    nif: str         # Mandatory
    
class GetClaimAssessmentRequest(BaseRequest): # option: 'get_claim_assessment'
    """
    Obtiene los datos de peritación asociados a un siniestro, buscando por su número (companyReference).
    Llama a get_claim_assessment_by_num.
    """
    num_claim: str   # Mandatory

class AddClaimAssessmentRequest(BaseRequest): # option: 'add_claim_assessment'
    """
    Añade o actualiza los datos de peritación de un siniestro (companyReference).
    Llama a add_claim_assessment_by_num.
    """
    num_claim: str   # Mandatory
    assessment_data: Dict # Mandatory

    
# ---------------------------------------------------

# --- OUTPUT INTERFACES (RESPONSES) ---

class ReceiptInfo(TypedDict):
    id: int
    amount: float
    status: str

class LoadRenewalsEntry(TypedDict):
    policy_number: str
    client_nif: str
    p_receipt: ReceiptInfo
    c_receipt: ReceiptInfo
    percent_diff: float

LoadRenewalsResponse = List[LoadRenewalsEntry]


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




class GetNewFlaggedClaimsEntry(TypedDict):
    desc_siniestro: str
    client_name: str
    gestor: Union[str, Dict]

GetNewFlaggedClaimsResponse = List[GetNewFlaggedClaimsEntry]

class CandidateResponse(TypedDict):
    id: int
    name: str
    phone: str
    signupDate: str

GetNewCandidatesTodayResponse = List[CandidateResponse]
GetCandidateByNifResponse = List[CandidateResponse]

GetNewPoliciesTodayResponse = List[Dict] # Generic Dict for full policy object

GetCustomerPhoneByNifResponse = Optional[str]

class AddDocumentCustomerResponse(TypedDict): # option: 'add_document_customer' reuse if possible or new
    id: int
    filename: str
    description: str

GetClaimAssessmentResponse = List[Dict] # option: 'get_claim_assessment'
AddClaimAssessmentResponse = Dict       # option: 'add_claim_assessment'

# --- MERLIN REQUESTS ---

class MerlinConsultaVehiculoRequest(BaseRequest): # option: 'merlin_consulta_vehiculo' o 'tarificador_consulta_vehiculo'
    """
    Consulta a la DGT los datos de un vehículo a partir de su matrícula a través de Merlin o Avant2.
    Llama a consulta_vehiculo_merlin_tool o consulta_vehiculo_avant2_tool según configuración.
    """
    matricula: str   # Mandatory

class MerlinGetTownByCpRequest(BaseRequest): # option: 'merlin_get_town_by_cp' o 'tarificador_get_town_by_cp'
    """
    Obtiene la población (municipio y provincia) a partir de un Código Postal mediante Merlin o Avant2.
    Llama a get_town_by_cp_merlin_tool o get_town_by_cp_avant2_tool.
    """
    cp: str          # Mandatory

class MerlinConsultarCatastroRequest(BaseRequest): # option: 'merlin_consultar_catastro' o 'tarificador_consultar_catastro'
    """
    Consulta los datos catastrales de una vivienda (año de construcción, metros, etc) mediante Merlin o Avant2.
    Llama a consultar_catastro_merlin_tool o consultar_catastro_avant2_tool.
    """
    provincia: str     # Mandatory
    municipio: str     # Mandatory
    tipo_via: Optional[str]      # Optional (default 'CL') but good to list
    nombre_via: str    # Mandatory
    numero: str        # Mandatory
    bloque: Optional[str]
    escalera: Optional[str]
    planta: Optional[str]
    piso: Optional[str] # Alias for planta
    puerta: Optional[str]

class MerlinCreateProjectRequest(BaseRequest): # option: 'merlin_create_project' o 'tarificador_create_project'
    """
    Inicia la tarificación y creación de un proyecto/presupuesto (Auto u Hogar) en Merlin o Avant2.
    Llama a create_retarificacion_merlin_project_tool o crea el proyecto en Avant2 según la configuración (tarificador_config).
    """
    # Base fields
    ramo: Optional[str] # AUTO o HOGAR
    dni: str            # Mandatory
    codigo_postal: str  # Mandatory for HOGAR
    fecha_efecto: str   # Mandatory

    # AUTO fields
    matricula: Optional[str]
    tipo_de_garaje: Optional[str]
    es_tomador: Optional[bool]       # True if conductor == tomador
    es_propietario: Optional[bool]   # True if conductor == propietario
    
    # HOGAR fields
    nombre_via: Optional[str]
    numero_calle: Optional[str]
    piso: Optional[str]
    puerta: Optional[str]
    numero_personas_vivienda: Optional[str]

    # ... and many other optional fields for HOGAR like 'alarma', 'tiene_piscina', etc.

# --- MERLIN RESPONSES ---

class MerlinConsultaVehiculoResponse(TypedDict):
    success: bool
    datos_vehiculo: Dict
    raw_data: Optional[Dict]

class MerlinGetTownByCpResponse(TypedDict):
    success: bool
    poblacion: str
    id_provincia: str
    descripcion_provincia: str

class MerlinConsultarCatastroResponse(TypedDict):
    success: bool
    anio_construccion: Optional[int]
    superficie: Optional[int]
    referencia_catastral: Optional[str]
    uso: Optional[str]
    codigo_postal: Optional[str]
    error: Optional[str]

class MerlinCreateProjectResponse(TypedDict):
    success: bool
    proyecto_id: Optional[str]
    id_pasarela: Optional[str]
    tarificacion_iniciada: Optional[bool]
    subramo: Optional[str]
    mensaje: Optional[str]
    num_aseguradoras: Optional[int]
    proyecto: Optional[Dict]
    error: Optional[str]
