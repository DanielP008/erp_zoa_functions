# Zoa Flow ERP Integration (ebroker)

Este repositorio contiene una Google Cloud Function desarrollada en Python diseñada para actuar como middleware de integración entre **Zoa Flow** y el ERP de seguros **ebroker**. 

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

3. **Ejecutar con Docker Compose**:
   ```bash
   docker-compose up --build
   ```
   El servicio estará disponible en `http://localhost:8080`.

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

### Opciones Disponibles (`option`)

#### Clientes
- `detalle_cliente`: Devuelve información detallada de un cliente dado su NIF.

#### Siniestros
- `get_claims`: Obtiene siniestros de un cliente filtrados por ramo (`lines`).
- `get_status_claims`: Consulta el estado de un siniestro por su ID (`id_siniestro`).
- `get_new_flagged_claims`: Busca nuevos siniestros marcados y envía notificaciones a Zoa.
- `apertura_siniestro`: (Comentado en código) Lógica para apertura de siniestros.

#### Pólizas
- `get_policies`: Obtiene las pólizas vigentes de un cliente filtradas por ramo.
- `get_doc_policies`: Descarga documentos PDF asociados a una póliza.

#### Recibos
- `info_banco_devolucion`: Obtiene la cuenta bancaria por defecto para devoluciones.
- `documento_recibo`: Obtiene el último recibo en formato PDF.

#### Renovaciones
- `renovaciones_auto_semana`: Procesa renovaciones próximas y envía notificaciones automáticas.

## 📦 Dependencias

Las dependencias principales se encuentran en `requeriments.txt`:
- `functions-framework`: Para ejecutar la Cloud Function.
- `firebase-admin` & `google-cloud-firestore`: Para interacción con Firebase.
- `requests`: Para llamadas HTTP externas.

## 📝 Notas de Desarrollo

- El archivo `requeriments.txt` contiene un error tipográfico en el nombre (debería ser `requirements.txt`), pero el `Dockerfile` lo referencia tal cual está.
- La autenticación con ebroker maneja tokens de acceso y refresco para múltiples servicios (CRM, Business, Admin).
