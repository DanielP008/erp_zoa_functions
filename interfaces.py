from typing import TypedDict, Optional, List, Union

# --- INTERFACES DE DATOS (DOCUMENTACIÓN DE CÓDIGO) ---

class BaseRequest(TypedDict):
    company_id: str  # Obligatorio
    option: str      # Obligatorio

class DetailCustomerRequest(BaseRequest):
    nif: str         # Obligatorio

class PoliciesRequest(BaseRequest):
    nif: str         # Obligatorio
    lines: Optional[str] # Opcional: Ramo a filtrar (hogar, auto...)

class ClaimsRequest(BaseRequest):
    nif: str         # Obligatorio

class PolicyDocRequest(BaseRequest):
    num_poliza: str  # Obligatorio

class ReceiptDocRequest(BaseRequest):
    num_poliza: str  # Obligatorio

class RenewalsRequest(BaseRequest):
    start_date: Optional[str] # Opcional: ebroker espera YYYY-MM-DD
    frequency: Optional[int]   # Opcional: Días de rango

class ClaimStatusRequest(BaseRequest):
    id_siniestro: int # Obligatorio

# ---------------------------------------------------