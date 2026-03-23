"""Merlin Multitarificador API client.

Creates auto and home insurance projects in Merlin and launches multi-insurer pricing.
API Docs: https://drseguros.merlin.insure/multi/multitarificador4-servicios/doc.html

Flow:
  1. POST /login                                          -> JWT token
  2. GET  /aseguradoras?subramo=...                       -> Available insurer templates
  3. POST /proyecto/nuevo (preferred) OR                  -> Project with auto-generated IDs
     GET  /proyecto/afinaciones + POST /proyecto (fallback) -> Fallback if /nuevo is unavailable
  4. Fill datos_basicos (vehiculo/riesgo_hogar, tomador, conductor/propietario, historial)
  5. PUT  /proyecto                                       -> Save project to DB
  6. (Hogar only) PUT /proyectos-hogar/{idPasarela}/datosAdicionales
"""

import json
import os
import time
import logging
import requests
from typing import Dict, Any, Optional, List



logger = logging.getLogger(__name__)

SUBRAMO_AUTO = "AUTOS_PRIMERA"
SUBRAMO_HOGAR = "HOGAR"
DATOS_BASICOS_AUTO_CLASS = "ebroker.multi4.data.proyectos.autos1.DatosBasicosAutos1"
DATOS_BASICOS_HOGAR_CLASS = "ebroker.multi4.data.proyectos.hogar.DatosBasicosHogar"

# Province code -> description mapping (INE system, first 2 digits of Spanish CP)
PROVINCIAS_ES: Dict[str, str] = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alicante/Alacant",
    "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Illes Balears", "08": "Barcelona", "09": "Burgos",
    "10": "Cáceres", "11": "Cádiz", "12": "Castellón/Castelló",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña",
    "16": "Cuenca", "17": "Girona", "18": "Granada",
    "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva",
    "22": "Huesca", "23": "Jaén", "24": "León",
    "25": "Lleida", "26": "La Rioja", "27": "Lugo",
    "28": "Madrid", "29": "Málaga", "30": "Murcia",
    "31": "Navarra", "32": "Ourense", "33": "Asturias",
    "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra",
    "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria",
    "40": "Segovia", "41": "Sevilla", "42": "Soria",
    "43": "Tarragona", "44": "Teruel", "45": "Toledo",
    "46": "Valencia", "47": "Valladolid", "48": "Bizkaia",
    "49": "Zamora", "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}


# =============================================================================
# Exceptions
# =============================================================================

class MerlinClientError(Exception):
    """Merlin API client error."""
    pass


# =============================================================================
# Helper builders
# =============================================================================

def _parse_date(date_str: Optional[str]) -> Optional[List[int]]:
    """Convert 'YYYY-MM-DD' string to Merlin date format [YYYY, M, D]."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        return [int(parts[0]), int(parts[1]), int(parts[2])]
    except (ValueError, IndexError):
        return None


def _build_vehiculo(data: dict) -> dict:
    """Build vehiculo dict for datos_basicos from collected data."""
    fecha_mat = _parse_date(data.get("fecha_matriculacion"))

    v: Dict[str, Any] = {
        "matricula": data.get("matricula", ""),
        "tipo_matricula": data.get("tipo_matricula", "ACTUAL"),
        "marca": data.get("marca", ""),
        "modelo": data.get("modelo", ""),
        "version": data.get("version", ""),
        "combustible": data.get("combustible", "G"),
        "km_actuales": data.get("km_actuales", 0),
        "km_anuales": data.get("km_anuales", 10000),
        "tipo_de_garaje": data.get("tipo_de_garaje", "COLECTIVO"),
        "precio_vp": data.get("precio_vp", 0),
        "pma": data.get("pma", 0),
        "cilindrada": data.get("cilindrada", 0),
        "potencia": data.get("potencia", 0),
        "accesorios": [],
    }

    if fecha_mat:
        v["fecha_matriculacion"] = fecha_mat
        v["fecha_primera_matriculacion"] = fecha_mat
        v["fecha_de_compra"] = fecha_mat

    for key in ("id_auto_base7", "id_tipo_base7", "id_categoria_base7", "id_clase_base7"):
        val = data.get(key)
        if val:
            v[key] = val

    return v


def _normalize_enum(value: str) -> str:
    """Normalize a human-readable Spanish string to SCREAMING_SNAKE_CASE enum.

    e.g. 'Núcleo Urbano' -> 'NUCLEO_URBANO', 'Vivienda Habitual' -> 'VIVIENDA_HABITUAL'
    """
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(value))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.strip().upper().replace(" ", "_")


def _build_riesgo_hogar(data: dict) -> dict:
    """Build vivienda dict for datos_basicos (Hogar projects).
    Matches the structure from the working Colab example.
    """
    return {
        "caracteristicas": {
            "tipo_vivienda": _normalize_enum(data.get("tipo_vivienda", "PISO_EN_ALTO")),
            "uso_vivienda": _normalize_enum(data.get("uso_vivienda", "VIVIENDA_HABITUAL")),
            "regimen_ocupacion": _normalize_enum(data.get("regimen_ocupacion", "PROPIEDAD")),
            "numero_personas_vivienda": int(data.get("numero_personas_vivienda", 4)),
            "situacion_vivienda": _normalize_enum(data.get("situacion_vivienda", "NUCLEO_URBANO")),
        },
        "datos_construccion": {
            "anio_construccion": int(data.get("anio_construccion") or data.get("ano_construccion") or 1997),
            "superficie_vivienda": int(data.get("superficie_construida") or data.get("superficie") or 160),
            "capital_continente": int(data.get("capital_continente") or 150000),
            "capital_contenido": int(data.get("capital_contenido") or 30000),
            "calidad_construccion": _normalize_enum(data.get("calidad_construccion", "NORMAL")),
            "materiales_construccion": _normalize_enum(data.get("materiales_construccion", "SOLIDA_PIEDRAS_LADRILLOS_ETC")),
        },
        "direccion": {
            "codigo_postal": data.get("codigo_postal", "46025"),
            "poblacion": data.get("municipio", data.get("poblacion", "VALENCIA")),
            "nombre_via": data.get("nombre_via", "ANDRES PILES IBARS"),
            "numero": data.get("numero_calle", "4"),
            "piso": data.get("piso", "5"),
            "puerta": data.get("puerta", "13"),
            "id_provincia": data.get("id_provincia", "46"),
            "id_pais": data.get("id_pais", "108-6"),
        },
        "protecciones": {
            "puerta_principal": data.get("tipo_puerta", "BLINDADA_ACORAZADA"),
            "alarma": data.get("alarma", "SIN_ALARMA"),
        },
    }


def _build_persona(data: dict, tipo_figura: str) -> dict:
    """Build persona dict for datos_basicos."""
    nombre = data.get("nombre", "")
    apellido1 = data.get("apellido1", "")
    apellido2 = data.get("apellido2", "")
    nombre_completo = f"{apellido1} {apellido2}, {nombre}".strip(", ")

    codigo_postal = data.get("codigo_postal", "")
    poblacion = data.get("poblacion", "")
    nombre_via = data.get("nombre_via", "")
    id_provincia = data.get("id_provincia", "")
    nacionalidad = data.get("nacionalidad", "108-6")

    p: Dict[str, Any] = {
        "numero_documento": data.get("dni", ""),
        "tipo_identificacion": data.get("tipo_identificacion", "NIF"),
        "sexo": data.get("sexo", "MASCULINO"),
        "estado_civil": data.get("estado_civil", "SOLTERO"),
        "tipo_figura": tipo_figura,
        "nacionalidad": nacionalidad,
        "zona_expedicion": nacionalidad,
        "codigo_postal": codigo_postal,
        "nombre_completo": nombre_completo,
        "lugar": poblacion,
        "cliente": {
            "tipo": "FISICA",
            "nombre": nombre,
            "apellido1": apellido1,
            "apellido2": apellido2,
            "nombre_completo": nombre_completo,
        },
        "direccion": {
            "id_pais": nacionalidad,
            "codigo_postal": codigo_postal,
            "id_tipo_via": data.get("id_tipo_via", "CL"),
            "nombre_via": nombre_via,
            "numero": data.get("numero_calle", ""),
            "portal": data.get("portal", ""),
            "escalera": data.get("escalera", ""),
            "piso": data.get("piso", ""),
            "puerta": data.get("puerta", ""),
            "poblacion": poblacion,
            "id_provincia": id_provincia,
            "descripcion_provincia": data.get("descripcion_provincia", ""),
            "ajuste_poblacion": {
                "codigo": "", "descripcion": "", "codigo_postal": "",
                "provincia": "", "nombre_via": "", "id_municipio": "",
                "id_poblacion": "", "id_provincia": "", "nombre_municipio": "",
                "id_zona": "",
            },
        },
    }

    fecha_nac = _parse_date(data.get("fecha_nacimiento"))
    if fecha_nac:
        p["fecha_nacimiento"] = fecha_nac

    p["tipo_carnet"] = data.get("tipo_carnet", "B")

    fecha_carnet = _parse_date(data.get("fecha_carnet") or data.get("fecha_expedicion_carnet"))
    if fecha_carnet:
        p["fecha_carnet"] = fecha_carnet

    if tipo_figura == "CONDUCTOR":
        p["is_innominada"] = False

    return p


def _build_historial(data: dict) -> dict:
    """Build historial_asegurador dict for datos_basicos."""
    from Merlin.aseguradoras_map import find_aseguradora_code

    fecha_efecto = _parse_date(data.get("fecha_efecto"))

    raw_poliza = str(data.get("num_poliza", "")).strip()
    digits_only = "".join(c for c in raw_poliza if c.isdigit())
    num_poliza_short = digits_only[-5:] if digits_only else ""

    raw_aseguradora = data.get("aseguradora_actual", "")
    aseguradora_code = find_aseguradora_code(raw_aseguradora) or raw_aseguradora
    logger.info(f"[MERLIN] Aseguradora mapping: '{raw_aseguradora}' -> '{aseguradora_code}'")

    return {
        "fecha": fecha_efecto or [2026, 3, 1],
        "matricula": data.get("matricula", ""),
        "tipo_matricula": data.get("tipo_matricula", "ACTUAL"),
        "anos_asegurados": 0,
        "num_poliza": num_poliza_short,
        "aseguradora_actual": aseguradora_code,
        "anos_compania": 0,
        "siniestros": False,
        "anos_sin_siniestros": 0,
        "datos_validos": True,
    }


# =============================================================================
# Merlin API Client
# =============================================================================

class MerlinClient:
    """Client for the Merlin Multitarificador API."""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.base_url = config.get("url", "https://drseguros.merlin.insure/multi/multitarificador4-servicios") 
        self._enfocar_base_url = self.base_url.replace(
            "/multi/multitarificador4-servicios",
            "/e-nfocar-services",
        )
        self.username = config.get("user") 
        self.password = config.get("pass") 
        self.timeout = config.get("timeout", 300) 
        self._session = requests.Session()
        self._token: Optional[str] = None

        enfocar_cfg = config.get("enfocar", {})
        self._enfocar_user = enfocar_cfg.get("user") or os.environ.get("ENFOCAR_USERNAME", "ebroker")
        self._enfocar_pass = enfocar_cfg.get("pass") or os.environ.get("ENFOCAR_PASSWORD", "ebrokerPM")

    def _ensure_config(self):
        if not self.username or not self.password:
            raise MerlinClientError("MERLIN_USERNAME and MERLIN_PASSWORD must be configured")

    def _request(self, method: str, path: str, timer_label: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        # parent = get_current_agent()
        # with Timer("merlin", timer_label, parent=parent):
        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except requests.exceptions.Timeout:
            raise MerlinClientError(f"Timeout calling {timer_label}")
        except requests.exceptions.ConnectionError as exc:
            raise MerlinClientError(f"Connection error ({timer_label}): {exc}")
        except requests.exceptions.HTTPError as exc:
            resp = exc.response
            body = resp.text[:300] if resp is not None else ""
            code = resp.status_code if resp is not None else "?"
            logger.error(f"[MERLIN] HTTP {code} on {timer_label} | URL: {url} | Body: {body}")
            raise MerlinClientError(
                f"HTTP {code} on {timer_label}: {body}"
            )

    # -- Public API -----------------------------------------------------------

    def login(self) -> str:
        self._ensure_config()
        logger.info("[MERLIN] Logging in...")
        
        # Base headers to mimic a real browser (Chrome 145)
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://drseguros.merlin.insure",
            "Referer": "https://drseguros.merlin.insure/login",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Accept-Encoding": "gzip, deflate, br, zstd",
        })

        try:
            resp = self._session.post(
                f"{self.base_url}/login",
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise MerlinClientError(f"Login failed: {exc}")

        self._token = resp.headers.get("Authorization")
        if not self._token:
            # Try to get it from body if not in headers
            self._token = resp.json().get("token")
            
        if not self._token:
            raise MerlinClientError("No Authorization token received from Merlin")

        if not self._token.startswith("Bearer "):
            self._token = f"Bearer {self._token}"

        self._session.headers["Authorization"] = self._token
        
        # CRITICAL: Merlin requires fetching user info to fully initialize the session
        try:
            logger.info(f"[MERLIN] Fetching user info for {self.username}...")
            self._session.get(f"{self.base_url}/user", params={"id": self.username}, timeout=self.timeout)
        except Exception as exc:
            logger.warning(f"[MERLIN] Failed to fetch user info: {exc}")

        logger.info(f"[MERLIN] Login successful. user={self.username}")
        return self._token

    def obtener_aseguradoras(self, subramo: str) -> Dict[str, Any]:
        logger.info(f"[MERLIN] Fetching insurers for '{subramo}'...")
        items = self._request("GET", "/aseguradoras", "merlin_aseguradoras", params={"subramo": subramo})
        logger.info(f"[MERLIN] Raw aseguradoras response: {len(items)} items")

        aseguradoras: Dict[str, Any] = {}
        for item in items:
            dgs = item.get("dgs", item.get("id", ""))
            nombre = item.get("nombre", "")
            for p in item.get("plantillas", []):
                if p.get("activa"):
                    pid = p.get("id")
                    aseguradoras[f"{dgs}_{pid}"] = {
                        "nombre": nombre,
                        "dgs": dgs,
                        "plantilla_id": pid,
                        "plantilla_nombre": p.get("nombre", ""),
                    }

        logger.info(f"[MERLIN] Found {len(aseguradoras)} active insurer templates for '{subramo}'.")
        return aseguradoras

    def obtener_afinaciones(self, plantillas_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch afinaciones for the given template IDs (replaces old GET /proyecto/nuevo)."""
        ids_str = ",".join(str(i) for i in plantillas_ids)
        logger.info(f"[MERLIN] Fetching afinaciones for {len(plantillas_ids)} templates...")
        return self._request(
            "GET", "/proyecto/afinaciones", "merlin_proyecto_afinaciones",
            params={"idsPlantillasSeleccionadas": ids_str},
        )

    def crear_proyecto(self, afinaciones: List[Dict[str, Any]], subramo: str) -> Dict[str, Any]:
        """Create a new project via POST /proyecto with afinaciones."""
        logger.info(f"[MERLIN] Creating project via POST /proyecto (subramo={subramo})...")
        
        # Exact date format from browser trace: [YYYY, M, D, H, M, S, nanoseconds]
        import datetime
        now = datetime.datetime.now()
        instante = [now.year, now.month, now.day, now.hour, now.minute, now.second, now.microsecond * 1000]
        
        # Generate a random pasarela ID
        import random
        id_pasarela_temp = random.randint(1000000, 9999999)
        
        body = {
            "afinaciones": afinaciones, 
            "subramo": subramo,
            "instante_de_creacion": instante,
            "id_proyecto_en_pasarela": id_pasarela_temp,
            "usuario": {
                "id": self.username,
                "nombre": "DANIEL ROMERO LLINARES",
                "rol": "ADMINISTRADOR"
            },
            "integracion_erp": {
                "id_proyecto": str(id_pasarela_temp),
                "fecha_creacion": instante,
                "fecha_modificacion": instante
            }
        }
        
        return self._request(
            "POST", "/proyecto", "merlin_crear_proyecto",
            json=body,
        )

    def obtener_proyecto_nuevo(self, plantillas_ids: List[str]) -> Dict[str, Any]:
        """Create a new project template using the EXACT structure from browser cURL.
        Note: The browser uses snake_case keys in the POST body for this endpoint.
        """
        logger.info(f"[MERLIN] Creating new project with {len(plantillas_ids)} templates via POST (Browser Mimicry)")

        # EXACT body from browser cURL: snake_case keys!
        body = {
            "ids_plantillas_seleccionadas": [str(i) for i in plantillas_ids],
            "ids_plantillas_complementario_seleccionadas": []
        }

        # EXACT headers from browser cURL
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://drseguros.merlin.insure/project/home/insurers",
            "Origin": "https://drseguros.merlin.insure",
        }

        try:
            proyecto = self._request(
                "POST", "/proyecto/nuevo", "merlin_proyecto_nuevo",
                json=body,
                headers=headers
            )
            
            pasarela_id = proyecto.get("id_proyecto_en_pasarela") or proyecto.get("idProyectoEnPasarela")
            logger.info(f"[MERLIN] Got project template via POST. Pasarela ID: {pasarela_id}")
            return proyecto
            
        except Exception as exc:
            logger.warning(f"[MERLIN] POST /proyecto/nuevo failed ({exc}), falling back to afinaciones+POST flow")
            # Fallback to the manual creation method if the official one fails
            afinaciones = self.obtener_afinaciones(plantillas_ids)
            proyecto = self.crear_proyecto(afinaciones, "HOGAR")
            logger.info(f"[MERLIN] Created project via fallback flow. id={proyecto.get('id')}")
            return proyecto

    def obtener_proyecto(self, id_proyecto: str) -> Dict[str, Any]:
        """Get full project details by MongoDB ID."""
        logger.info(f"[MERLIN] Fetching project {id_proyecto}...")
        return self._request(
            "GET", f"/proyecto/{id_proyecto}", "merlin_obtener_proyecto"
        )

    def guardar_proyecto(self, proyecto: Dict[str, Any]) -> Dict[str, Any]:
        """Save project to Merlin.
        For Hogar, we ensure the top-level keys match what the UI expects.
        """
        # Ensure we use 'datos_basicos' (snake_case) if that's what worked in creation
        if "datosBasicos" in proyecto:
            proyecto["datos_basicos"] = proyecto.pop("datosBasicos")
            
        datos_b = proyecto.get("datos_basicos", {})
        logger.info(f"[MERLIN] Saving project... datos_basicos keys: {list(datos_b.keys()) if isinstance(datos_b, dict) else 'N/A'}")
        
        result = self._request("PUT", "/proyecto", "merlin_guardar_proyecto", json=proyecto)
        logger.info(f"[MERLIN] Project saved. ID={result.get('id', 'unknown')}")
        return result

    def guardar_datos_adicionales_hogar(self, id_pasarela: str, data: dict) -> Dict[str, Any]:
        """Save additional data for Hogar projects (capitals, questionnaire).
        This uses a dedicated endpoint that Merlin requires for Hogar projects.
        """
        def _safe_int(val):
            try: return int(val) if val is not None else 0
            except: return 0

        logger.info(f"[MERLIN] Saving additional Hogar data for pasarela ID {id_pasarela}...")
        
        # Use simple date format [YYYY, M, D]
        import datetime
        now = datetime.datetime.now()
        fecha_efecto = _parse_date(data.get("fecha_efecto")) or [now.year, now.month, now.day]

        datos_adicionales = {
            "fecha": fecha_efecto,
            "capitales": {
                "continente": _safe_int(data.get("capital_continente")) or 150000,
                "continente_primer_riesgo": None,
                "obras_reforma": None,
                "mobiliario_general": _safe_int(data.get("capital_contenido")) or 30000,
                "mobiliario_dependencias_anexas": None,
                "mobiliario_profesional": None,
                "vehiculos_en_garaje": None,
                "descripcion_garaje": "",
            },
            "capitales_recomendados": [],
            "otros_capitales": {
                "joyas_dentro_caja_fuerte": None,
                "joyas_fuera_caja_fuerte": None,
                "dinero_dentro_caja_fuerte": None,
                "dinero_fuera_caja_fuerte": None,
                "objetos_valor": None,
                "joyas_en_banco": None,
            },
            "cuestionario_hogar": {
                "numero_gatos_dom": None,
                "numero_perros_dom": None,
                "animales": False,
                "num_perros_peligrosos": None,
                "num_otros_animales_domesticos": None,
            },
        }

        return self._request(
            "PUT",
            f"/proyectos-hogar/{id_pasarela}/datosAdicionales",
            "merlin_hogar_datos_adicionales",
            json=datos_adicionales,
        )

    def solicitar_capitales_recomendados(self, id_proyecto: str, dgs_companias: List[str]) -> Dict[str, Any]:
        """Request recommended capitals from all insurers for a HOGAR project."""
        dgs_csv = ",".join(dgs_companias)
        logger.info(f"[MERLIN] Requesting capitals: project={id_proyecto}, dgs={dgs_csv}")
        
        url = f"{self.base_url}/capitales-recomendados"
        try:
            resp = self._session.get(url, params={"idProyecto": id_proyecto, "dgsCompanias": dgs_csv}, timeout=self.timeout)
            resp.raise_for_status()
            # The response is a raw string (the process ID), not JSON
            return {"idProcesoPasarela": resp.text.strip().strip('"')}
        except Exception as exc:
            logger.error(f"[MERLIN] Error requesting capitals: {exc}")
            raise MerlinClientError(f"Error requesting capitals: {exc}")

    def consultar_estado_capitales(self, id_proceso_pasarela: str, subramo: str = "HOGAR") -> Dict[str, Any]:
        """Poll recommended capitals status."""
        return self._request(
            "GET", "/capitales-recomendados/estado", "merlin_capitales_estado",
            params={"idProcesoPasarela": id_proceso_pasarela, "subramo": subramo},
        )

    def _poll_capitales_recomendados(
        self, id_proceso_pasarela: str, subramo: str = "HOGAR",
        max_wait: int = 60, interval: int = 2,
    ) -> Optional[List[Dict[str, Any]]]:
        """Poll capitales-recomendados/estado until finished or timeout."""
        start = time.time()
        last_capitales = []

        while (time.time() - start) < max_wait:
            time.sleep(interval)
            try:
                resp = self.consultar_estado_capitales(id_proceso_pasarela, subramo)
                capitales = resp.get("capitales", [])
                last_capitales = capitales

                if resp.get("terminado", False):
                    return capitales

                valid = sum(1 for c in capitales if (c.get("continente") or 0) > 0)
                if capitales and valid / len(capitales) >= 0.9 and (time.time() - start) > 5:
                    logger.info(f"[MERLIN] Capitals early return: {valid}/{len(capitales)} valid.")
                    return capitales
            except Exception as exc:
                logger.warning(f"[MERLIN] Capitals poll error: {exc}")

        logger.warning(f"[MERLIN] Capitals poll timed out after {round(time.time() - start, 1)}s.")
        return last_capitales

    def iniciar_tarificacion(self, id_proyecto: str) -> Dict[str, Any]:
        """Launch the multi-insurer tarification process for a saved project.
        Uses GET /tarificacion/iniciar?id={mongo_id}.
        """
        logger.info(f"[MERLIN] Launching tarification for project ID {id_proyecto}...")
        return self._request(
            "GET", "/tarificacion/iniciar", "merlin_iniciar_tarificacion",
            params={"id": id_proyecto},
        )

    def consultar_estado_tarificacion(self, mongo_id: str, subramo: str, pasarela_ids: Optional[dict] = None) -> Dict[str, Any]:
        """Check tarification process status and save results to project.
        Uses Spring-style nested query params if pasarela_ids are provided,
        otherwise uses the minimal idProyecto.id as seen in working examples.
        """
        params = {
            "idProyecto.id": mongo_id,
            "subramo": subramo,
        }
        
        if pasarela_ids:
            id1 = pasarela_ids.get("id_pasarela1") or pasarela_ids.get("idPasarela1")
            id2 = pasarela_ids.get("id_pasarela2") or pasarela_ids.get("idPasarela2")
            if id1: params["idProcesoPasarela.idPasarela1"] = id1
            if id2: params["idProcesoPasarela.idPasarela2"] = id2

        logger.info(f"[MERLIN] Checking tarification status for project={mongo_id}...")
        return self._request(
            "GET", "/tarificacion/estado", "merlin_estado_tarificacion",
            params=params,
        )

    def _poll_tarificacion(
        self, mongo_id: str, subramo: str, pasarela_ids: Optional[dict] = None,
        max_wait: int = 100, interval: int = 5,
    ) -> bool:
        """Poll tarificacion/estado until finished or timeout."""
        start = time.time()
        consecutive_errors = 0

        while (time.time() - start) < max_wait:
            time.sleep(interval)
            try:
                resp = self.consultar_estado_tarificacion(mongo_id, subramo, pasarela_ids)
                consecutive_errors = 0
                if resp.get("tarificacionFinalizada") or resp.get("tarificacion_finalizada"):
                    logger.info(f"[MERLIN] Tarification completed in {round(time.time() - start, 1)}s.")
                    return True
            except Exception as exc:
                consecutive_errors += 1
                logger.warning(f"[MERLIN] Tarification poll error ({consecutive_errors}/3): {exc}")
                if consecutive_errors >= 3:
                    break

        logger.warning(f"[MERLIN] Tarification timed out after {round(time.time() - start, 1)}s.")
        return False

    def _extract_all_offers(self, proyecto: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract ALL offers from the real Merlin project structure.

        Merlin nests offers inside:
          procesos_de_tarificacion[last].tarificaciones[N].resultado.modalidades[M]

        Each tarificacion = one insurer, each modalidad = one product/tier.
        Returns a flat list of dicts with insurer name, product name, and price,
        sorted by price ascending.
        """
        all_offers: List[Dict[str, Any]] = []

        procesos = proyecto.get("procesos_de_tarificacion", [])
        if not procesos:
            logger.warning("[MERLIN] No procesos_de_tarificacion found in project")
            return all_offers

        # Use the last (most recent) tarification process
        proceso = procesos[-1]
        tarificaciones = proceso.get("tarificaciones", [])
        logger.info(f"[MERLIN] Found {len(tarificaciones)} tarificaciones in latest process")

        for tarif in tarificaciones:
            resultado = tarif.get("resultado", {})
            if not resultado:
                continue

            nombre_aseguradora = resultado.get("nombre_aseguradora", "")
            dgs = resultado.get("dgs", "")
            finalizada = resultado.get("finalizada", False)
            con_respuesta = resultado.get("con_respuesta_de_compania", False)

            if not finalizada or not con_respuesta:
                continue

            modalidades = resultado.get("modalidades", [])
            for mod_entry in modalidades:
                modalidad = mod_entry.get("modalidad", {})
                if not modalidad:
                    continue

                descripcion = modalidad.get("descripcion", "")
                contratable = modalidad.get("contratable", False)

                prima_anual = modalidad.get("prima_anual", {})
                price = None
                if isinstance(prima_anual, dict):
                    price = prima_anual.get("prima_anualizada")

                if price is None:
                    continue
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    continue
                if price <= 0:
                    continue

                nombre_completo = f"{nombre_aseguradora} {descripcion}".strip()
                all_offers.append({
                    "nombre_aseguradora": nombre_completo,
                    "dgs": dgs,
                    "descripcion": descripcion,
                    "prima_anual": round(price, 2),
                    "contratable": contratable,
                    "nombre_completo": nombre_completo,
                })

        all_offers.sort(key=lambda x: x["prima_anual"])
        logger.info(f"[MERLIN] Extracted {len(all_offers)} total offers across all insurers")
        return all_offers

    def _tarificar_y_obtener_ofertas(self, mongo_id: str, subramo: str, max_wait: int = 100) -> tuple:
        """Launch tarification, poll, fetch final project and extract offers.
        Returns (tarificacion_ok, ofertas, proyecto_final).
        """
        tarificacion_ok = False
        proyecto_final = {}
        ofertas = []

        try:
            tar_resp = self.iniciar_tarificacion(mongo_id)
            pasarela_ids = tar_resp.get("id_proceso_pasarela") or tar_resp.get("idProcesoPasarela")
            tarificacion_ok = self._poll_tarificacion(mongo_id, subramo, pasarela_ids, max_wait=max_wait)
        except Exception as exc:
            logger.warning(f"[MERLIN] Tarification launch failed: {exc}")

        try:
            proyecto_final = self.obtener_proyecto(mongo_id)
            ofertas = self._extract_all_offers(proyecto_final)
            estado = proyecto_final.get("estado", proyecto_final.get("estadoProyecto", ""))
            if estado == "TARIFICADO" or ofertas:
                tarificacion_ok = True
        except Exception as exc:
            logger.warning(f"[MERLIN] Failed to fetch final project: {exc}")

        return tarificacion_ok, ofertas, proyecto_final

    def _obtener_capitales_recomendados_hogar(
        self, mongo_id: str, id_pasarela, datos: dict, afinaciones: list
    ) -> Optional[Dict[str, Any]]:
        """For HOGAR without capitals: save initial data, fetch insurer recommendations.
        Returns a response dict if capitals are needed (early return), or None to continue.
        """
        def _safe_int(val):
            try: return int(val) if val is not None else 0
            except (ValueError, TypeError): return 0

        has_continente = _safe_int(datos.get("capital_continente")) > 0
        has_contenido = _safe_int(datos.get("capital_contenido")) > 0

        if has_continente and has_contenido:
            try:
                self.guardar_datos_adicionales_hogar(id_pasarela, datos)
            except Exception as exc:
                logger.warning(f"[MERLIN] Hogar additional data save failed: {exc}")
            return None

        dgs_list = list({af.get("afinacion", {}).get("dgs", "") for af in afinaciones} - {""})
        logger.info(f"[MERLIN] Capitals missing. Fetching recommendations from {len(dgs_list)} insurers...")

        capitales_list = []
        try:
            self.guardar_datos_adicionales_hogar(id_pasarela, datos)
            cap_resp = self.solicitar_capitales_recomendados(mongo_id, dgs_list)
            cap_process_id = cap_resp.get("idProcesoPasarela") or cap_resp.get("id_proceso_pasarela", "")
            if isinstance(cap_process_id, dict):
                cap_process_id = cap_process_id.get("idPasarela2", "")

            if cap_process_id:
                capitales_list = self._poll_capitales_recomendados(str(cap_process_id)) or []
                dgs_to_name = {
                    af.get("afinacion", {}).get("dgs", ""): af.get("afinacion", {}).get("nombre", af.get("descripcion_plantilla", ""))
                    for af in afinaciones
                }
                for cap in capitales_list:
                    cap["nombre_aseguradora"] = dgs_to_name.get(cap.get("dgs", ""), cap.get("dgs", ""))
        except Exception as exc:
            logger.warning(f"[MERLIN] Recommended capitals fetch failed: {exc}")

        return {
            "success": True,
            "action_required": "select_capitals",
            "mensaje": "Se requieren seleccionar los capitales de continente y contenido."
                       if capitales_list else
                       "No se pudieron obtener recomendaciones de capitales a tiempo. Indica los capitales manualmente.",
            "proyecto_id": mongo_id,
            "id_pasarela": id_pasarela,
            "capitales_recomendados": capitales_list,
        }

    def crear_proyecto_completo(self, datos: dict) -> Dict[str, Any]:
        """Create a complete insurance project in Merlin and launch tarification."""
        try:
            self.login()
            ramo = str(datos.get("ramo", "AUTO")).upper()
            subramo = SUBRAMO_AUTO if ramo == "AUTO" else SUBRAMO_HOGAR
            max_wait_polling = int(datos.get("max_wait_polling", 100))

            aseguradoras = self.obtener_aseguradoras(subramo)
            if not aseguradoras:
                return {"success": False, "error": f"No insurers available for {ramo}"}

            plantillas_ids = [a["plantilla_id"] for a in aseguradoras.values()]
            logger.info(f"[MERLIN] {len(aseguradoras)} insurers, {len(plantillas_ids)} templates")
            proyecto = self.obtener_proyecto_nuevo(plantillas_ids)

            # Ensure we use 'datos_basicos' (snake_case)
            if "datosBasicos" in proyecto:
                proyecto["datos_basicos"] = proyecto.pop("datosBasicos")
            
            datos_basicos = proyecto.get("datos_basicos", {})

            if ramo == "AUTO":
                datos_basicos["vehiculo"] = _build_vehiculo(datos)
                datos_basicos["conductor"] = _build_persona(datos, "CONDUCTOR")
                datos_basicos["propietario"] = _build_persona(datos, "PROPIETARIO")
                datos_basicos["historial_asegurador"] = _build_historial(datos)
                datos_basicos["conductor_es_tomador"] = datos.get("es_tomador", True)
                datos_basicos["conductor_es_propietario"] = datos.get("es_propietario", True)
                datos_basicos["@class"] = DATOS_BASICOS_AUTO_CLASS
                datos_basicos["class_name"] = DATOS_BASICOS_AUTO_CLASS
            else:
                # For HOGAR, we use 'vivienda' inside 'datos_basicos'
                datos_basicos["vivienda"] = _build_riesgo_hogar(datos)
                datos_basicos["propietario"] = _build_persona(datos, "PROPIETARIO")
                datos_basicos["@class"] = DATOS_BASICOS_HOGAR_CLASS
                datos_basicos["class_name"] = DATOS_BASICOS_HOGAR_CLASS

            datos_basicos["tomador"] = _build_persona(datos, "TOMADOR")
            proyecto["datos_basicos"] = datos_basicos

            result = self.guardar_proyecto(proyecto)
            mongo_id = result.get("id")
            id_pasarela = result.get("id_proyecto_en_pasarela") or result.get("idProyectoEnPasarela")

            if ramo == "HOGAR" and id_pasarela and mongo_id:
                capitals_response = self._obtener_capitales_recomendados_hogar(
                    mongo_id, id_pasarela, datos, proyecto.get("afinaciones", [])
                )
                if capitals_response is not None:
                    return capitals_response

            tarificacion_ok, ofertas, proyecto_final = self._tarificar_y_obtener_ofertas(
                mongo_id, subramo, max_wait_polling
            )

            return {
                "success": True,
                "proyecto_id": mongo_id,
                "id_pasarela": id_pasarela,
                "tarificacion_iniciada": tarificacion_ok,
                "subramo": subramo,
                "mensaje": f"Proyecto de {ramo} creado con {len(plantillas_ids)} aseguradoras"
                           + (" y tarificación iniciada" if tarificacion_ok else ""),
                "num_aseguradoras": len(plantillas_ids),
                "ofertas": ofertas,
                "proyecto": proyecto_final,
            }

        except MerlinClientError as exc:
            logger.error(f"[MERLIN] Project creation failed: {exc}")
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"[MERLIN] Unexpected error creating project: {exc}")
            return {"success": False, "error": f"Error inesperado: {exc}"}

    def finalizar_proyecto_hogar(self, datos: dict) -> Dict[str, Any]:
        """Finalize an existing HOGAR project with chosen capitals and launch tarification."""
        try:
            self.login()
            mongo_id = datos.get("proyecto_id")
            id_pasarela = datos.get("id_pasarela")
            if not mongo_id or not id_pasarela:
                return {"success": False, "error": "proyecto_id and id_pasarela are required"}

            self.guardar_datos_adicionales_hogar(str(id_pasarela), datos)
            logger.info("[MERLIN] Hogar additional data (capitals) saved.")

            max_wait_polling = int(datos.get("max_wait_polling", 100))
            tarificacion_ok, ofertas, proyecto_final = self._tarificar_y_obtener_ofertas(
                mongo_id, SUBRAMO_HOGAR, max_wait_polling
            )

            return {
                "success": True,
                "proyecto_id": mongo_id,
                "id_pasarela": id_pasarela,
                "tarificacion_iniciada": tarificacion_ok,
                "subramo": SUBRAMO_HOGAR,
                "mensaje": f"Proyecto HOGAR finalizado con capitales y tarificación "
                           f"{'completada' if tarificacion_ok else 'en proceso'}",
                "ofertas": ofertas,
                "proyecto": proyecto_final,
            }
        except MerlinClientError as exc:
            logger.error(f"[MERLIN] Finalize hogar failed: {exc}")
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"[MERLIN] Unexpected error finalizing hogar: {exc}")
            return {"success": False, "error": f"Error inesperado: {exc}"}

    def consultar_dgt_por_matricula(self, matricula: str) -> Dict[str, Any]:
        """Consulta datos del vehiculo en la DGT via e-nfocar-services."""
        try:
            if not self._enfocar_user or not self._enfocar_pass:
                raise MerlinClientError(
                    "e-nfocar credentials not configured. Set enfocar.user/enfocar.pass "
                    "in tarificador config, or ENFOCAR_USER/ENFOCAR_PASS env vars."
                )
            dgt_url = f"{self._enfocar_base_url}/v1/vehiculos/{matricula}"
            logger.info(f"[MERLIN] DGT lookup: {dgt_url}")
            try:
                resp = requests.get(
                    dgt_url,
                    params={"categoria": "1"},
                    auth=(self._enfocar_user, self._enfocar_pass),
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )
                logger.info(f"[MERLIN] DGT response status: {resp.status_code}")
                resp.raise_for_status()
                results = resp.json()
            except requests.exceptions.RequestException as exc:
                raise MerlinClientError(f"DGT lookup failed: {exc}")

            if not results or not isinstance(results, list) or len(results) == 0:
                return {"success": False, "error": f"No se encontraron datos para la matricula {matricula}"}

            vehiculo = results[0]
            logger.info(f"[MERLIN] DGT raw response keys: {list(vehiculo.keys())}")

            base7 = vehiculo.get("base7", {}) or {}
            motor = base7.get("motor", {}) or vehiculo.get("motor", {})
            combustible_id = motor.get("id", "") if isinstance(motor, dict) else ""
            combustible_desc = motor.get("descripcion", "") if isinstance(motor, dict) else ""
            categoria = base7.get("categoria", {}) or {}
            tipo = base7.get("tipo", {}) or {}
            clase = base7.get("clase", {}) or {}
            datos_adicionales = vehiculo.get("datosAdicionalesVehiculo", {}) or {}
            garaje_info = datos_adicionales.get("garaje", {}) or {}
            garaje_desc = garaje_info.get("descripcion", "") if isinstance(garaje_info, dict) else ""

            logger.info(
                f"[MERLIN] DGT found: {base7.get('marca')} {base7.get('modelo')} "
                f"({base7.get('version')}) - {combustible_desc}"
            )

            return {
                "success": True,
                "vehiculo": {
                    "marca": base7.get("marca") or vehiculo.get("marca"),
                    "modelo": base7.get("modelo") or vehiculo.get("modelo"),
                    "version": base7.get("version") or vehiculo.get("version"),
                    "combustible": combustible_id,
                    "combustible_descripcion": combustible_desc,
                    "fecha_matriculacion": datos_adicionales.get("fechaMatriculacion") or base7.get("fechaMatriculacion"),
                    "fecha_primera_matriculacion": datos_adicionales.get("fechaPrimeraMatriculacion"),
                    "fecha_compra": datos_adicionales.get("fechaCompra"),
                    "cilindrada": base7.get("cilindrada") or vehiculo.get("cilindrada"),
                    "potencia_cv": base7.get("cv") or vehiculo.get("cv"),
                    "precio_vp": base7.get("precioVp") or vehiculo.get("precioVp"),
                    "descripcion_completa": base7.get("descripcion") or vehiculo.get("descripcion"),
                    "id_auto_base7": base7.get("id", ""),
                    "id_tipo_base7": tipo.get("id", ""),
                    "id_categoria_base7": categoria.get("id", ""),
                    "id_clase_base7": clase.get("idClase", ""),
                    "km_anuales": datos_adicionales.get("kilometrosAnuales"),
                    "km_totales": datos_adicionales.get("kilometrosTotales"),
                    "garaje": garaje_desc,
                },
            }

        except MerlinClientError as exc:
            logger.error(f"[MERLIN] DGT lookup failed: {exc}")
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error(f"[MERLIN] DGT lookup unexpected error: {exc}")
            return {"success": False, "error": str(exc)}

    def obtener_poblacion_por_cp(self, cp: str) -> Dict[str, Any]:
        """Obtiene la población y provincia a partir del código postal.

        Uses the free zippopotam.us API for Spanish postal codes.
        The province ID (id_provincia) is derived from the first two digits
        of the postal code, which corresponds to the Spanish INE standard.
        """
        try:
            cp = str(cp).strip().zfill(5)
            url = f"https://api.zippopotam.us/es/{cp}"
            logger.info(f"[MERLIN] Postal code lookup: {url}")

            # Verify SSL is disabled to avoid certificate issues in some environments
            # or ensure certificates are up to date. For now, we'll use verify=False
            # as a fallback if standard verification fails, but default to True.
            try:
                resp = requests.get(url, timeout=10)
            except requests.exceptions.SSLError:
                logger.warning("[MERLIN] SSL verification failed for zippopotam.us, retrying without verification.")
                resp = requests.get(url, timeout=10, verify=False)

            logger.info(f"[MERLIN] Postal code response status: {resp.status_code}")

            if resp.status_code == 404:
                return {"success": False, "error": f"No se encontró población para el CP {cp}"}
            
            # Handle potential 500/503 from zippopotam
            if resp.status_code >= 500:
                logger.error(f"[MERLIN] Zippopotam service error: {resp.status_code}")
                return {"success": False, "error": f"Error del servicio de códigos postales ({resp.status_code})"}

            resp.raise_for_status()
            data = resp.json()

            places = data.get("places", [])
            if not places:
                return {"success": False, "error": f"No se encontró población para el CP {cp}"}

            place = places[0]
            poblacion = place.get("place name", "")
            id_provincia = cp[:2]
            descripcion_provincia = PROVINCIAS_ES.get(id_provincia, place.get("state", ""))

            logger.info(
                f"[MERLIN] Postal code resolved: {poblacion} ({descripcion_provincia}) - "
                f"id_provincia={id_provincia}"
            )

            return {
                "success": True,
                "poblacion": poblacion,
                "id_provincia": id_provincia,
                "descripcion_provincia": descripcion_provincia,
                "codigo_postal": cp,
            }

        except Exception as exc:
            logger.error(f"[MERLIN] Postal code lookup failed: {exc}")
            return {"success": False, "error": str(exc)}


# =============================================================================
# Wrapper functions for tools
# =============================================================================

def _extract_tarificador_config(config: Optional[dict]) -> dict:
    """Safely extract tarificador config, handling None and nested structures."""
    if not config or not isinstance(config, dict):
        return {}
    if "tarificador" in config:
        return config.get("tarificador", {})
    return config


def create_merlin_project(datos: dict, tarificador_config: Optional[dict] = None) -> Dict[str, Any]:
    """Create a complete Merlin insurance project (Auto or Hogar)."""
    client = MerlinClient(_extract_tarificador_config(tarificador_config))
    return client.crear_proyecto_completo(datos)


def get_vehicle_info_by_matricula(matricula: str, tarificador_config: Optional[dict] = None) -> Dict[str, Any]:
    """Get vehicle info from DGT via Merlin e-nfocar-services."""
    client = MerlinClient(config=_extract_tarificador_config(tarificador_config))
    return client.consultar_dgt_por_matricula(matricula)


def get_town_by_cp(cp: str, tarificador_config: Optional[dict] = None) -> Dict[str, Any]:
    """Get town/poblacion info by postal code from Merlin."""
    client = MerlinClient(config=_extract_tarificador_config(tarificador_config))
    return client.obtener_poblacion_por_cp(cp)


def finalize_hogar_project(datos: dict, tarificador_config: Optional[dict] = None) -> Dict[str, Any]:
    """Finalize a HOGAR project with chosen capitals and launch tarification."""
    client = MerlinClient(_extract_tarificador_config(tarificador_config))
    return client.finalizar_proyecto_hogar(datos)
