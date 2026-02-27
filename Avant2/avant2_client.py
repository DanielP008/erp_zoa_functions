"""Client for Avant2 tarification using Codeoscopic API.

Creates auto and home insurance projects in Avant2 and launches multi-insurer pricing.
API Docs: https://portal.api-int.codeoscopic.io/
"""

import logging
import requests
import json
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Constants and Mappings (can be moved or expanded as Avant2 structure becomes clearer)
SUBRAMO_AUTO = "AUTOS_PRIMERA"

class Avant2ClientError(Exception):
    """Avant2 API client error."""
    pass


class Avant2Client:
    """Client for the Avant2 API (Codeoscopic)."""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.environment = config.get("environment", "integration").lower()
        if self.environment == "production":
            self.base_url = "https://api.codeoscopic.io"
        else:
            self.base_url = "https://api-int.codeoscopic.io"
            
        self.client_id = config.get("user")  # Equivalent to client_id
        self.client_secret = config.get("pass")  # Equivalent to client_secret
        self.x_user_email = config.get("email") # Required for some Codeoscopic endpoints
        
        self.timeout = config.get("timeout", 60)
        self._session = requests.Session()
        
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    def _ensure_config(self):
        if not self.client_id or not self.client_secret:
            raise Avant2ClientError("Avant2 user (client_id) and pass (client_secret) must be configured")

    def _get_valid_token(self) -> str:
        """Ensure we have a valid access token, authenticating if necessary."""
        if not self.access_token or time.time() >= self.token_expiry:
            self.login()
        return self.access_token

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        self._get_valid_token()
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            
            # Check if empty response
            if not response.content:
                return {}
                
            return response.json()
        except requests.exceptions.Timeout:
            raise Avant2ClientError(f"Timeout calling Avant2 API at {endpoint}")
        except requests.exceptions.ConnectionError as exc:
            raise Avant2ClientError(f"Connection error to Avant2 API ({endpoint}): {exc}")
        except requests.exceptions.HTTPError as exc:
            try:
                error_msg = exc.response.json()
            except json.JSONDecodeError:
                error_msg = exc.response.text[:300]
            raise Avant2ClientError(
                f"HTTP {exc.response.status_code if exc.response else '?'} on {endpoint}: {error_msg}"
            )

    # -- Public API -----------------------------------------------------------

    def login(self) -> str:
        """Authenticate with the Codeoscopic OAuth2 endpoint using client_credentials."""
        self._ensure_config()
        logger.info(f"[AVANT2] Logging in to {self.base_url}...")
        
        auth_url = f"{self.base_url}/oauth2/token"
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            resp = requests.post(auth_url, data=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            token_data = resp.json()
            
            self.access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            
            # Add a small buffer (e.g., 60 seconds) to avoid edge cases during requests
            self.token_expiry = time.time() + expires_in - 60
            
            # Update session headers with the new token and the required X-User-Email
            self._session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.codeoscopic.v1+json"
            })
            if self.x_user_email:
                self._session.headers["X-User-Email"] = self.x_user_email
                
            logger.info("[AVANT2] Login successful.")
            return self.access_token
            
        except requests.exceptions.RequestException as exc:
            logger.error(f"[AVANT2] Login failed: {exc}")
            raise Avant2ClientError(f"Avant2 Login failed: {exc}")

    def obtener_aseguradoras(self) -> List[Dict[str, Any]]:
        """Get the available insurance companies.
        
        Endpoint: GET /insurance-companies
        Documentation: https://portal.api-int.codeoscopic.io/#get-/insurance-companies
        """
        logger.info("[AVANT2] Fetching insurance companies...")
        items = self._make_request("GET", "/insurance-companies")
        logger.info(f"[AVANT2] Found {len(items) if isinstance(items, list) else 'unknown'} insurance companies.")
        return items

    def create_insurance_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new insurance project.
        
        Endpoint: POST /insurances
        """
        logger.info("[AVANT2] Creating new insurance project...")
        return self._make_request("POST", "/insurances", json=payload)

    def update_insurance_project(self, project_id: str, payload: Dict[str, Any]) -> None:
        """Update an existing insurance project.
        
        Endpoint: PATCH /insurances/{id}
        """
        logger.info(f"[AVANT2] Updating insurance project {project_id}...")
        self._make_request("PATCH", f"/insurances/{project_id}", json=payload)
        
    def get_insurance_project(self, project_id: str) -> Dict[str, Any]:
        """Retrieve an insurance project.
        
        Endpoint: GET /insurances/{id}
        """
        logger.info(f"[AVANT2] Fetching insurance project {project_id}...")
        return self._make_request("GET", f"/insurances/{project_id}")

    def create_report(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a report of the specified type.
        
        Endpoint: POST /insurances/{id}/reports
        """
        logger.info(f"[AVANT2] Creating report for project {project_id}...")
        return self._make_request("POST", f"/insurances/{project_id}/reports", json=payload)

    def crear_proyecto_completo(self, datos: dict) -> Dict[str, Any]:
        """[TODO] Complete implementation for creating and rating a project using the new endpoints."""
        try:
            self.login()
            ramo = str(datos.get("ramo", "AUTO")).upper()
            
            # TODO: Map `datos` to the Codeoscopic `/insurances` payload format
            # This is a placeholder payload based on the docs provided
            initial_payload = {
                "insuranceLine": {
                    "id": "Car" if ramo == "AUTO" else "Home"
                }
                # ... other mapping logic ...
            }
            
            # 1. Create project
            # project_data = self.create_insurance_project(initial_payload)
            # project_id = project_data.get("id")
            
            # 2. Update with patch (if needed for the flow, or just create with all data at once)
            # self.update_insurance_project(project_id, full_payload)
            
            # 3. Request tarification (Need to check doc for the exact endpoint to trigger rating, 
            # maybe it's automatic on GET /insurances/{id} or there is a specific action)
            
            return {
                "success": True,
                "proyecto_id": "TODO",
                "subramo": SUBRAMO_AUTO if ramo == "AUTO" else "HOGAR",
                "mensaje": f"Proyecto {ramo} en Avant2 (En desarrollo con nueva API)",
                "ofertas": [],
                "proyecto": {},
            }
        except Avant2ClientError as exc:
            logger.error(f"[AVANT2] Project creation failed: {exc}")
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"[AVANT2] Unexpected error creating project: {exc}")
            return {"success": False, "error": f"Error inesperado: {exc}"}

# =============================================================================
# Wrapper functions for tools (Skeletons to match Merlin's interface)
# =============================================================================

def _extract_tarificador_config(config: Optional[dict]) -> dict:
    """Safely extract tarificador config, handling None and nested structures."""
    if not config or not isinstance(config, dict):
        return {}
    if "tarificador" in config:
        return config.get("tarificador", {})
    return config

def create_avant2_project(datos: dict, tarificador_config: Optional[dict] = None) -> Dict[str, Any]:
    """Create a complete Avant2 insurance project."""
    client = Avant2Client(_extract_tarificador_config(tarificador_config))
    return client.crear_proyecto_completo(datos)

