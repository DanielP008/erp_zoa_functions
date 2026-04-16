# Zoa Flow ERP Integration (ebroker)

Este repositorio contiene una Google Cloud Function desarrollada en Python diseñada para actuar como middleware de integración entre **Zoa Flow** y el ERP de seguros **ebroker**. 

> **Note**: This project was developed during my time at Zoa Suite, where I was responsible for building and maintaining this repository to handle the middleware logic described in this documentation.

El servicio permite automatizar consultas y operaciones relacionadas con clientes, pólizas, siniestros y recibos, facilitando la comunicación bidireccional entre la plataforma Zoa y los sistemas de gestión de las corredurías.

## 🚀 Arquitectura

El proyecto está estructurado como una función HTTP (`main`) que procesa peticiones POST en formato JSON.

- **Lenguaje**: Python 3.11
- **Framework**: Google Functions Framework (`functions-framework`)
- **Persistencia y Configuración**: Firebase Firestore (Google Cloud Firestore)
- **Integraciones Externas**: 
  - **ebroker ERP**: Se conecta a los servicios CRM, Business y Admin de ebroker.
  - **Zoa Flow**: Envía notificaciones y actualizaciones a la plataforma Zoa.
- **Contenedor**: Dockerized para despliegue local o en Google Cloud Run.

### Flujo de Trabajo

1. La función recibe una petición HTTP POST con un `company_id` y una `option` (acción a realizar).
2. Consulta **Firestore** (`waba_accounts`) para obtener las credenciales de acceso al ERP ebroker correspondientes al `company_id`.
3. Se autentica contra los servicios de ebroker (`EBrokerClient`).
4. Ejecuta la lógica solicitada según el parámetro `option`.
5. Retorna los datos procesados o realiza acciones secundarias (como enviar notificaciones a Zoa).

## 📂 Estructura del Proyecto

- `main.py`: Punto de entrada de la Cloud Function. Maneja el enrutamiento de peticiones y la lógica principal.
- `ebroker_functions.py`: Cliente API para ebroker (`EBrokerClient`). Encapsula la autenticación y las llamadas a los endpoints del ERP.
- `insurance_phones.json`: Base de datos estática de teléfonos de asistencia de compañías aseguradoras.
- `Dockerfile`: Definición de la imagen del contenedor.
- `docker-compose.yml`: Orquestación para desarrollo local.
- `requeriments.txt`: Dependencias del proyecto.

## 🛠️ Instalación y Configuración Local

### Prerrequisitos

- Docker y Docker Compose
- Credenciales de Google Cloud (`service-account.json`) con acceso a Firestore.

### Pasos

1. **Clonar el repositorio**:
   ```bash
   git clone <url-del-repositorio>
   cd zoa_flow_erp
   ```

2. **Configurar Credenciales**:
   Coloca tu archivo de credenciales de Google Cloud en la raíz del proyecto con el nombre `service-account.json`.
   > **Nota**: Este archivo está ignorado por git por seguridad.

## 📡 Uso de la API

El servicio espera peticiones POST con un cuerpo JSON. 

### Parámetros Comunes

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `company_id` | String | ID de la compañía (obligatorio para buscar credenciales). |
| `option` | String | Acción a ejecutar (ver lista abajo). |
| `nif` | String | NIF del cliente (requerido para muchas operaciones). |
| `num_poliza` | String | Número de póliza. |
| `phone` | String | Teléfono del cliente. |

# Documentación de API y Opciones de Zoa Flow ERP

Este documento detalla todas las entradas (`option`) procesadas por el archivo `main.py` de Zoa y los métodos asociados en los ERP subyacentes (`ebroker`, `tesis`, `fast360`) así como los tarificadores (`merlin`, `avant2`).

---

## Clientes

### `detalle_cliente`
* **Descripción:** Recupera los detalles de un cliente por su documento de identidad (NIF/DNI).
* **Parámetros:** `nif` (str)
* **Opción ERP** `get_customer_by_nif`

### `create_customer`
* **Descripción:** Da de alta a un nuevo cliente en el ERP.
* **Parámetros:** `name` (str), `surname` (str), `nif` (str), `address` (str)
* **Opción ERP** `post_customer`

### `get_customer_phone_by_nif`
* **Descripción:** Devuelve el número de teléfono principal de un cliente.
* **Parámetros:** `nif` (str)
* **Opción ERP** `get_customer_phone_by_nif`

### `add_document_customer`
* **Descripción:** Sube un fichero en Base64 al perfil documental del cliente.
* **Parámetros:** `nif` (str), `filename` (str), `base64_content` (str), `notes` (str, opcional)
* **Opción ERP** `add_document_to_customer_by_nif`

---

## Candidatos

### `create_candidate`
* **Descripción:** Crea un nuevo candidato (potencial cliente) en el ERP.
* **Parámetros:** `name` (str), `phone` (str)
* **Opción ERP** `post_candidate`

### `get_new_candidates_today`
* **Descripción:** Obtiene los candidatos que se han registrado o modificado hoy.
* **Parámetros:** Ninguno
* **Opción ERP** `get_new_candidates_today`

### `get_candidate_by_nif`
* **Descripción:** Obtiene los datos de un candidato buscando por NIF/DNI.
* **Parámetros:** `nif` (str)
* **Opción ERP** `get_candidate_by_nif`

---

## Pólizas

### `get_policies`
* **Descripción:** Obtiene todas las pólizas activas asociadas a un cliente. Opcionalmente filtra por ramo (usando `lines`).
* **Parámetros:** `nif` (str), `lines` (str, opcional)
* **Opción ERP** `get_all_policys_by_client_category` o `get_customer_policies`

### `get_policy_by_num`
* **Descripción:** Busca y retorna los detalles de una póliza específica usando su número asignado.
* **Parámetros:** `num_poliza` (str)
* **Opción ERP** `get_policy_by_num`

### `get_new_policies_today`
* **Descripción:** Obtiene las pólizas de nueva creación del día en curso.
* **Parámetros:** Ninguno
* **Opción ERP** `get_new_policies_today`

### `add_document_policy`
* **Descripción:** Sube un documento asociado a una póliza específica.
* **Parámetros:** `num_poliza` (str), `filename` (str), `base64_content` (str), `notes` (str, opcional)
* **Opción ERP** `add_document_to_policy_by_num`

---

## Siniestros

### `get_claims`
* **Descripción:** Obtiene los siniestros de un cliente filtrados por un ramo específico.
* **Parámetros:** `nif` (str), además de `lines` (str) mapeado internamente.
* **Opción ERP** `get_customer_claims_by_category`

### `get_claim_by_risk`
* **Descripción:** Obtiene los siniestros de un cliente filtrados por el riesgo de la póliza asociada (ej. matrícula).
* **Parámetros:** `nif` (str), `risk` (str)
* **Opción ERP** `get_claim_by_risk`

### `get_status_claims`
* **Descripción:** Obtiene el estado actual de un siniestro a partir de su ID interno.
* **Parámetros:** `id_siniestro` (int)
* **Opción ERP** `get_claim_status`

### `get_claim_assessment`
* **Descripción:** Obtiene los datos de peritación asociados a un siniestro, buscando por su número de referencia propio de la aseguradora.
* **Parámetros:** `num_claim` (str)
* **Opción ERP** `get_claim_assessment_by_num`

### `add_claim_assessment`
* **Descripción:** Añade o actualiza datos (ej: fecha, perito asignado, etc) de peritación a un siniestro.
* **Parámetros:** `num_claim` (str), `assessment_data` (dict)
* **Opción ERP** `add_claim_assessment_by_num`

### `get_new_flagged_claims`
* **Descripción:** Calcula y devuelve de forma masiva los siniestros recientes que contienen una plantilla de aviso o marca.
* **Parámetros:** Ninguno
* **Opción ERP** `get_new_flagged_claims`

### `add_document_claim`
* **Descripción:** Sube un archivo documental al registro de un siniestro de la base de datos de la correduría.
* **Parámetros:** `num_claim` (str), `filename` (str), `base64_content` (str), `notes` (str, opcional)
* **Opción ERP** `add_document_to_claim_by_num`

---

## Recibos y Renovaciones

### `get_newest_receipt`
* **Descripción:** Obtiene el recibo general más reciente creado para una póliza.
* **Parámetros:** `num_poliza` (str)
* **Opción ERP** `get_newest_receipt`

### `get_active_receipt`
* **Descripción:** Obtiene el recibo activo (En vigor o pendiente de cobro) más reciente de una póliza.
* **Parámetros:** `num_poliza` (str)
* **Opción ERP** `get_active_receipt`

### `get_returned_receipts`
* **Descripción:** Obtiene los recibos devueltos en un rango temporal por la entidad bancaria o compañía.
* **Parámetros:** `start_date` (str, opcional), `end_date` (str, opcional)
* **Opción ERP** `get_returned_receipts`

### `load_renewals`
* **Descripción:** Procesa las renovaciones masivas de una compañía, analizando y detectando incrementos de prima (porcentaje o cantidad fija).
* **Parámetros:** `percent_threshold` (float, opcional), `amount_threshold` (float, opcional)
* **Opción ERP** `process_load_renewals`

*(Opciones operativas complejas en Excel_Tools: `renovaciones_auto_semana`, `renovaciones_recibos`, `info_banco_devolucion`, `documento_recibo`)*

---

## Calculadores / Tarificadores (Merlin y Avant2)
*Todas estas opciones operan de manera agnóstica mediante la clave de entorno del tarificador y son respondidas bien por `merlin_tool` o `avant2_client`.*

### `merlin_consulta_vehiculo` o `tarificador_consulta_vehiculo`
* **Descripción:** Consulta a la DGT / Base de Datos los detalles técnicos de un vehículo mediante su matrícula para el presupuesto.
* **Parámetros:** `matricula` (str)
* **Función Subyacente:** `consulta_vehiculo_merlin_tool` o `consulta_vehiculo_avant2_tool`

### `merlin_get_town_by_cp` o `tarificador_get_town_by_cp`
* **Descripción:** Convierte un Código Postal en su localidad / municipio oficial.
* **Parámetros:** `cp` (str)
* **Función Subyacente:** `get_town_by_cp_merlin_tool` o `get_town_by_cp_avant2_tool`

### `merlin_consultar_catastro` o `tarificador_consultar_catastro`
* **Descripción:** Consulta los datos catastrales de una vivienda (año de construcción, m2, etc) para calcular riesgo en Hogar.
* **Parámetros:** `provincia`, `municipio`, `nombre_via`, `numero` (strs, requeridos), `bloque`, `escalera`, `planta`, `puerta` (opcionales)
* **Función Subyacente:** `consultar_catastro_merlin_tool` o `consultar_catastro_avant2_tool`

### `merlin_create_project` o `tarificador_create_project`
* **Descripción:** Manda los datos estandarizados a la plataforma B2B para generar la parrilla de cotización real. Crea un proyecto (proyecto = presupuesto de multi-oferta).
* **Parámetros Principales:** `ramo` (AUTO, HOGAR...), `dni`, `codigo_postal`, `fecha_efecto`
* **Adicionales (Auto):** `matricula`, `es_tomador`, `es_propietario`...
* **Adicionales (Hogar):** Detalle de dirección de riesgo, uso, alarma...
* **Función Subyacente:** `create_retarificacion_merlin_project_tool` o logica en Avant2.
