"""Merlin Multitarificador API client.

Creates auto and home insurance projects in Merlin and launches multi-insurer pricing.
API Docs: https://drseguros.merlin.insure/multi/multitarificador4-servicios/doc.html

Flow:
  1. POST /login                         -> JWT token
  2. GET  /aseguradoras?subramo=...      -> Available insurer templates
  3. GET  /proyecto/nuevo?ids...         -> In-memory project template
  4. Fill datos_basicos (vehiculo/riesgo_hogar, tomador, conductor/propietario, historial)
  5. PUT  /proyecto                      -> Save project to DB
  6. (Hogar only) PUT /proyectos-hogar/{idPasarela}/datosAdicionales
"""

import json
import os
import time
import logging
import requests
from typing import Dict, Any, Optional, List

from infra.timing import Timer, get_current_agent

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


def _build_riesgo_hogar(data: dict) -> dict:
    """Build riesgo_hogar dict for datos_basicos (Hogar projects)."""
    return {
        "caracteristicas": {
            "tipo_vivienda": data.get("tipo_vivienda", "PISO"),
            "situacion_vivienda": data.get("situacion_vivienda", "NUCLEO_URBANO"),
            "regimen_ocupacion": data.get("regimen_ocupacion", "PROPIEDAD"),
            "alquiler_vacacional": data.get("alquiler_vacacional", False),
            "uso_vivienda": data.get("uso_vivienda", "VIVIENDA_HABITUAL"),
            "utilizacion_vivienda": data.get("utilizacion_vivienda", "VIVIENDA_EXCLUSIVAMENTE"),
            "numero_personas_vivienda": str(data.get("numero_personas_vivienda", "3")),
        },
        "datos_construccion": {
            "anio_construccion": int(data.get("anio_construccion", 2010)),
            "superficie_vivienda": int(data.get("superficie_vivienda", 90)),
            "numero_habitaciones": str(data.get("numero_habitaciones", "3")),
            "calidad_construccion": data.get("calidad_construccion", "NORMAL"),
            "materiales_construccion": data.get("materiales_construccion", "SOLIDA_PIEDRAS_LADRILLOS_ETC"),
            "tipo_tuberias": data.get("tipo_tuberias", "POLIPROPILENO"),
            "vivienda_rehabilitada": data.get("vivienda_rehabilitada", False),
            "referencia_catastral": data.get("referencia_catastral", ""),
        },
        "direccion": {
            "codigo_postal": data.get("codigo_postal", ""),
            "poblacion": data.get("poblacion", ""),
            "id_tipo_via": data.get("id_tipo_via", "CL"),
            "nombre_via": data.get("nombre_via", ""),
            "numero": data.get("numero_calle", "1"),
            "portal": data.get("portal", ""),
            "escalera": data.get("escalera", ""),
            "piso": data.get("piso", ""),
            "puerta": data.get("puerta", ""),
            "id_provincia": data.get("id_provincia", ""),
            "id_pais": data.get("id_pais", "108-6"),
            "descripcion_provincia": data.get("descripcion_provincia", ""),
            "ajuste_poblacion": {
                "codigo": "", "descripcion": "", "codigo_postal": "",
                "provincia": "", "nombre_via": "", "id_municipio": "",
                "id_poblacion": "", "id_provincia": "", "nombre_municipio": "",
                "id_zona": "",
            },
        },
        "dependencias_anexas": {
            "piscinas": data.get("tiene_piscina", False),
        },
        "protecciones": {
            "puerta_principal": data.get("tipo_puerta", "DE_MADERA_PVC_METALICA_ETC"),
            "puerta_secundaria": data.get("puerta_secundaria", "NO_TIENE"),
            "ventanas": data.get("ventanas", "SIN_PROTECCION"),
            "alarma": data.get("alarma", "SIN_ALARMA"),
            "alarma_incendio": data.get("alarma_incendio", "SIN_ALARMA"),
            "alarma_agua": data.get("alarma_agua", "SIN_ALARMA"),
            "caja_fuerte": data.get("caja_fuerte", "NO_TIENE"),
            "vigilancia": data.get("vigilancia", "SIN_VIGILANCIA"),
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

    fecha_carnet = _parse_date(data.get("fecha_carnet"))
    if fecha_carnet:
        p["fecha_carnet"] = fecha_carnet

    if tipo_figura == "CONDUCTOR":
        p["is_innominada"] = False

    return p


def _build_historial(data: dict) -> dict:
    """Build historial_asegurador dict for datos_basicos."""
    fecha_efecto = _parse_date(data.get("fecha_efecto"))

    return {
        "fecha": fecha_efecto or [2026, 3, 1],
        "matricula": data.get("matricula", ""),
        "tipo_matricula": data.get("tipo_matricula", "ACTUAL"),
        "anos_asegurados": data.get("anos_asegurado", 0),
        "num_poliza": data.get("num_poliza", ""),
        "aseguradora_actual": data.get("aseguradora_actual", ""),
        "anos_compania": data.get("anos_compania", 0),
        "siniestros": data.get("siniestros", False),
        "anos_sin_siniestros": data.get("anos_sin_siniestros", 0),
        "datos_validos": True,
    }


# =============================================================================
# Merlin API Client
# =============================================================================

class MerlinClient:
    """Client for the Merlin Multitarificador API."""

    def __init__(self):
        self.base_url = os.environ.get(
            "MERLIN_BASE_URL",
            "https://drseguros.merlin.insure/multi/multitarificador4-servicios",
        ).rstrip("/")
        self._enfocar_base_url = self.base_url.replace(
            "/multi/multitarificador4-servicios",
            "/e-nfocar-services",
        )
        self.username = os.environ.get("MERLIN_USERNAME", "")
        self.password = os.environ.get("MERLIN_PASSWORD", "")
        self.timeout = int(os.environ.get("MERLIN_TIMEOUT", "30"))
        self._session = requests.Session()
        self._token: Optional[str] = None

    def _ensure_config(self):
        if not self.username or not self.password:
            raise MerlinClientError("MERLIN_USERNAME and MERLIN_PASSWORD must be configured")

    def _request(self, method: str, path: str, timer_label: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        parent = get_current_agent()
        with Timer("merlin", timer_label, parent=parent):
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
                body = exc.response.text[:300] if exc.response is not None else ""
                raise MerlinClientError(
                    f"HTTP {exc.response.status_code if exc.response else '?'} on {timer_label}: {body}"
                )

    # -- Public API -----------------------------------------------------------

    def login(self) -> str:
        self._ensure_config()
        logger.info("[MERLIN] Logging in...")
        parent = get_current_agent()
        with Timer("merlin", "merlin_login", parent=parent):
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
            raise MerlinClientError("No Authorization token received from Merlin")

        self._session.headers.update({
            "Authorization": self._token,
            "Content-Type": "application/json",
        })
        logger.info("[MERLIN] Login successful.")
        return self._token

    def obtener_aseguradoras(self, subramo: str) -> Dict[str, Any]:
        logger.info(f"[MERLIN] Fetching insurers for '{subramo}'...")
        items = self._request("GET", "/aseguradoras", "merlin_aseguradoras", params={"subramo": subramo})
        aseguradoras: Dict[str, Any] = {}
        for item in items:
            dgs = item.get("id", "")
            nombre = item.get("nombre", "")
            plantillas = item.get("plantillas", [])
            activa = next((p for p in plantillas if p.get("activa")), plantillas[0] if plantillas else None)
            if activa:
                aseguradoras[dgs] = {
                    "nombre": nombre,
                    "plantilla_id": activa.get("id"),
                    "plantilla_nombre": activa.get("nombre"),
                }
        logger.info(f"[MERLIN] Found {len(aseguradoras)} insurers.")
        return aseguradoras

    def obtener_proyecto_nuevo(self, plantillas_ids: List[str]) -> Dict[str, Any]:
        ids_str = ",".join(str(i) for i in plantillas_ids)
        logger.info(f"[MERLIN] Creating new project template (ids={ids_str[:60]}...)")
        proyecto = self._request(
            "GET", "/proyecto/nuevo", "merlin_proyecto_nuevo",
            params={"idsPlantillasSeleccionadas": ids_str},
        )
        logger.info(f"[MERLIN] Got project template with {len(proyecto.get('aseguradoras', []))} insurers.")
        return proyecto

    def obtener_proyecto(self, id_proyecto: str) -> Dict[str, Any]:
        """Get full project details by MongoDB ID."""
        logger.info(f"[MERLIN] Fetching project {id_proyecto}...")
        return self._request(
            "GET", f"/proyecto/{id_proyecto}", "merlin_obtener_proyecto"
        )

    def guardar_proyecto(self, proyecto: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[MERLIN] Saving project...")
        result = self._request("PUT", "/proyecto", "merlin_guardar_proyecto", json=proyecto)
        logger.info(f"[MERLIN] Project saved. ID={result.get('id', 'unknown')}")
        return result

    def guardar_datos_adicionales_hogar(self, id_pasarela: str, data: dict) -> Dict[str, Any]:
        """Save additional data for Hogar projects (capitals, questionnaire).
        This uses a dedicated endpoint that Merlin requires for Hogar projects.
        """
        logger.info(f"[MERLIN] Saving additional Hogar data for pasarela ID {id_pasarela}...")
        fecha_efecto = _parse_date(data.get("fecha_efecto")) or [2026, 3, 1]

        datos_adicionales = {
            "fecha": fecha_efecto,
            "capitales": {
                "continente": int(data.get("capital_continente", 100000)),
                "continente_primer_riesgo": None,
                "obras_reforma": None,
                "mobiliario_general": int(data.get("capital_contenido", 10000)),
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

    def iniciar_tarificacion(self, id_pasarela: str) -> Dict[str, Any]:
        """Launch the multi-insurer tarification process for a saved project.

        Calls GET /tarificacion/iniciar?id={id_pasarela}.
        """
        logger.info(f"[MERLIN] Launching tarification for pasarela ID {id_pasarela}...")
        return self._request(
            "GET", "/tarificacion/iniciar", "merlin_iniciar_tarificacion",
            params={"id": id_pasarela},
        )

    def consultar_estado_tarificacion(self, process_id: str, mongo_id: str, subramo: str) -> Dict[str, Any]:
        """Check tarification process status and save results to project.

        Uses Spring-style nested query params:
          GET /tarificacion/estado?idProcesoPasarela.idPasarela2={process_id}&idProyecto.id={mongo_id}&subramo={subramo}

        IMPORTANT: each call to this endpoint persists the latest results
        into the project document.  The project estado flips to TARIFICADO
        only after the backend writes the insurer responses.
        """
        logger.info(
            f"[MERLIN] Checking tarification status for process={process_id}, "
            f"project={mongo_id}, subramo={subramo}..."
        )
        return self._request(
            "GET", "/tarificacion/estado", "merlin_estado_tarificacion",
            params={
                "idProcesoPasarela.idPasarela2": process_id,
                "idProyecto.id": mongo_id,
                "subramo": subramo,
            },
        )

    def _poll_tarificacion(
        self,
        process_id: str,
        mongo_id: str,
        subramo: str,
        max_wait: int = 60,
        interval: int = 5,
    ) -> bool:
        """Poll tarificacion/estado until finished or timeout.

        Each poll saves insurer results into the project document.
        Returns True if tarification completed, False on timeout/error.
        """
        elapsed = 0
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            try:
                resp = self.consultar_estado_tarificacion(
                    process_id, mongo_id, subramo
                )
                logger.debug(f"[MERLIN] Estado response: {resp}")
                finished = resp.get("tarificacionFinalizada", False)
                logger.info(
                    f"[MERLIN] Tarification poll ({elapsed}s): "
                    f"finished={finished}"
                )
                if finished:
                    logger.info("[MERLIN] Tarification completed successfully.")
                    return True
            except Exception as exc:
                logger.warning(f"[MERLIN] Tarification poll error ({elapsed}s): {exc}")
                break
        if elapsed >= max_wait:
            logger.warning(f"[MERLIN] Tarification timed out after {max_wait}s.")
        return False

    def crear_proyecto_completo(self, datos: dict) -> Dict[str, Any]:
        """Create a complete insurance project in Merlin and launch tarification."""
        try:
            self.login()
            ramo = str(datos.get("ramo", "AUTO")).upper()
            subramo = SUBRAMO_AUTO if ramo == "AUTO" else SUBRAMO_HOGAR

            aseguradoras = self.obtener_aseguradoras(subramo)
            if not aseguradoras:
                return {"success": False, "error": f"No insurers available for {ramo}"}

            plantillas_ids = [a["plantilla_id"] for a in aseguradoras.values()]
            proyecto = self.obtener_proyecto_nuevo(plantillas_ids)

            datos_basicos = proyecto.get("datosBasicos") or proyecto.get("datos_basicos", {})

            if ramo == "AUTO":
                datos_basicos["vehiculo"] = _build_vehiculo(datos)
                datos_basicos["conductor"] = _build_persona(datos, "CONDUCTOR")
                datos_basicos["historial_asegurador"] = _build_historial(datos)
                datos_basicos["@class"] = DATOS_BASICOS_AUTO_CLASS
            else:
                datos_basicos["riesgo_hogar"] = _build_riesgo_hogar(datos)
                datos_basicos["propietario"] = _build_persona(datos, "PROPIETARIO")
                datos_basicos["class_name"] = DATOS_BASICOS_HOGAR_CLASS

            datos_basicos["tomador"] = _build_persona(datos, "TOMADOR")

            if "datosBasicos" in proyecto:
                proyecto["datosBasicos"] = datos_basicos
            else:
                proyecto["datos_basicos"] = datos_basicos

            result = self.guardar_proyecto(proyecto)

            mongo_id = result.get("id")
            id_pasarela = result.get("id_proyecto_en_pasarela")

            # Hogar requires a second call for capitals and questionnaire
            if ramo == "HOGAR" and id_pasarela:
                try:
                    self.guardar_datos_adicionales_hogar(id_pasarela, datos)
                    logger.info("[MERLIN] Hogar additional data saved successfully.")
                except Exception as exc:
                    logger.warning(f"[MERLIN] Hogar additional data save failed: {exc}")

            # Launch tarification and poll until complete
            tarificacion_ok = False
            if mongo_id:
                try:
                    tar_resp = self.iniciar_tarificacion(mongo_id)
                    process_id = (
                        tar_resp.get("id_proceso_pasarela", {}).get("id_pasarela2", "")
                    )
                    if process_id:
                        tarificacion_ok = self._poll_tarificacion(
                            process_id, mongo_id, subramo
                        )
                    else:
                        logger.warning("[MERLIN] No process ID returned from iniciar.")
                except Exception as exc:
                    logger.warning(f"[MERLIN] Tarification launch failed: {exc}")

            # Always fetch final project – polling calls persist insurer
            # results, so the project may be tarified even on timeout.
            proyecto_final = {}
            if mongo_id:
                try:
                    proyecto_final = self.obtener_proyecto(mongo_id)
                    logger.info(f"[MERLIN] Final project keys: {list(proyecto_final.keys())}")
                    estado = proyecto_final.get("estado", proyecto_final.get("estadoProyecto", "DESCONOCIDO"))
                    logger.info(f"[MERLIN] Final project estado: {estado}")
                    ofertas = proyecto_final.get("ofertas", proyecto_final.get("aseguradoras", []))
                    logger.info(f"[MERLIN] Final project ofertas count: {len(ofertas) if isinstance(ofertas, list) else 'N/A'}")
                    if estado == "TARIFICADO":
                        tarificacion_ok = True
                    # Dump project JSON to test/json_renovaciones/
                    try:
                        dump_dir = os.path.join(os.path.dirname(__file__), "..", "test", "json_renovaciones")
                        os.makedirs(dump_dir, exist_ok=True)
                        dump_path = os.path.join(dump_dir, f"proyecto_tarificado_{mongo_id}.json")
                        with open(dump_path, "w", encoding="utf-8") as f:
                            json.dump(proyecto_final, f, ensure_ascii=False, indent=2, default=str)
                        logger.info(f"[MERLIN] Project JSON dumped to {dump_path}")
                    except Exception as dump_exc:
                        logger.warning(f"[MERLIN] Failed to dump project JSON: {dump_exc}")

                except Exception as exc:
                    logger.warning(f"[MERLIN] Failed to fetch final project: {exc}")

            return {
                "success": True,
                "proyecto_id": mongo_id,
                "id_pasarela": id_pasarela,
                "tarificacion_iniciada": tarificacion_ok,
                "subramo": subramo,
                "mensaje": f"Proyecto de {ramo} creado con {len(plantillas_ids)} aseguradoras"
                           + (" y tarificación iniciada" if tarificacion_ok else ""),
                "num_aseguradoras": len(plantillas_ids),
                "proyecto": proyecto_final,
            }

        except MerlinClientError as exc:
            logger.error(f"[MERLIN] Project creation failed: {exc}")
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"[MERLIN] Unexpected error creating project: {exc}")
            return {"success": False, "error": f"Error inesperado: {exc}"}

    def consultar_dgt_por_matricula(self, matricula: str) -> Dict[str, Any]:
        """Consulta datos del vehiculo en la DGT via e-nfocar-services."""
        try:
            dgt_url = f"{self._enfocar_base_url}/v1/vehiculos/{matricula}"
            logger.info(f"[MERLIN] DGT lookup: {dgt_url}")

            enfocar_auth = (
                os.environ.get("ENFOCAR_USERNAME", "ebroker"),
                os.environ.get("ENFOCAR_PASSWORD", "ebrokerPM"),
            )

            parent = get_current_agent()
            with Timer("merlin", "merlin_dgt_lookup", parent=parent):
                try:
                    resp = requests.get(
                        dgt_url,
                        params={"categoria": "1"},
                        auth=enfocar_auth,
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

            parent = get_current_agent()
            with Timer("merlin", "merlin_towns_lookup", parent=parent):
                resp = requests.get(url, timeout=10)
                logger.info(f"[MERLIN] Postal code response status: {resp.status_code}")

            if resp.status_code == 404:
                return {"success": False, "error": f"No se encontró población para el CP {cp}"}

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

def create_merlin_project(datos: dict) -> Dict[str, Any]:
    """Create a complete Merlin insurance project (Auto or Hogar)."""
    client = MerlinClient()
    return client.crear_proyecto_completo(datos)


def get_vehicle_info_by_matricula(matricula: str) -> Dict[str, Any]:
    """Get vehicle info from DGT via Merlin e-nfocar-services."""
    client = MerlinClient()
    return client.consultar_dgt_por_matricula(matricula)


def get_town_by_cp(cp: str) -> Dict[str, Any]:
    """Get town/poblacion info by postal code from Merlin."""
    client = MerlinClient()
    return client.obtener_poblacion_por_cp(cp)
