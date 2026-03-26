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
        
        self.timeout = config.get("timeout", 180)
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
            
            # Incluir el payload en el error para depuración
            payload_str = json.dumps(kwargs.get('json', {}), ensure_ascii=False)
            logger.error(f"[AVANT2] 400 Bad Request Payload: {payload_str}")
            
            raise Avant2ClientError(
                f"HTTP {exc.response.status_code if exc.response is not None else '?'} on {endpoint}: {error_msg}. Payload sent: {payload_str[:500]}"
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

    def create_insurance_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new insurance project.
        
        Endpoint: POST /insurances
        """
        logger.info("[AVANT2] Creating new insurance project...")
        return self._make_request("POST", "/insurances", json=payload)

    def get_insurance_project(self, project_id: str) -> Dict[str, Any]:
        """Retrieve an insurance project.
        
        Endpoint: GET /insurances/{id}
        """
        logger.info(f"[AVANT2] Fetching insurance project {project_id}...")
        return self._make_request("GET", f"/insurances/{project_id}")

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


