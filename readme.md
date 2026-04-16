# Zoa Flow ERP Integration (Middleware)

This repository contains a Python-based Google Cloud Function designed to act as a middleware integration between **Zoa Flow** and various insurance ERPs (ebroker, Tesis) and multi-quoters (Codeoscopic, Merlin).

> **Note**: This project was developed during my time at Zoa Suite, where I was responsible for building and maintaining this repository to handle the middleware logic described in this documentation.

The service automates queries and operations related to customers, policies, claims, and receipts, facilitating bidirectional communication between the Zoa platform and insurance brokerage management systems.

## 🚀 Architecture

The project is structured as an HTTP function (`main`) that processes JSON-formatted POST requests.

- **Language**: Python 3.11
- **Framework**: Google Functions Framework (`functions-framework`)
- **Persistence & Configuration**: Firebase Firestore (Google Cloud Firestore)
- **External Integrations**: 
  - **ebroker / Tesis ERP**: Direct connection to CRM, Business, and Admin services.
  - **Zoa Flow**: Sends notifications and updates to the Zoa platform.
  - **Codeoscopic (Avant2) / Merlin**: Multi-insurer pricing engines.
  - **Data Enrichment**: Automated property data from Catastro and vehicle data from DGT.
- **Containerization**: Dockerized for local development or deployment via Google Cloud Run.

### Workflow

1. The function receives an HTTP POST request with a `company_id` and an `option` (action to perform).
2. It queries **Firestore** (`clientIDs` collection) to retrieve the ERP and multi-quoter credentials for that specific `company_id`.
3. It authenticates against the target services.
4. It executes the requested logic based on the `option` parameter.
5. It returns processed data or performs secondary actions (like updating Zoa memory).

## 📂 Project Structure

- `main.py`: Entry point for the Cloud Function. Handles routing and core logic.
- `Avant2/`: Integration client and tools for Codeoscopic API.
- `Merlin/`: Integration client and tools for Merlin Multitarificador.
- `catastro_client.py`: Public API client for Spanish property data enrichment.
- `database_functions.py`: Handles Firebase Firestore interactions.
- `Dockerfile`: Container image definition.
- `docker-compose.yml`: Orchestration for local development.
- `requirements.txt`: Project dependencies.

## 🛠️ Installation & Local Setup

### Prerequisites

- Docker and Docker Compose
- Google Cloud credentials (`service-account.json`) with Firestore access.

### Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/DanielP008/erp_zoa_functions.git
   cd erp_zoa_functions
   ```

2. **Configure Credentials**:
   Place your Google Cloud credentials file in the project root named `service-account.json`.
   > **Note**: This file is ignored by git for security.

## 📡 API Usage

The service expects POST requests with a JSON body.

### Common Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `company_id` | String | Unique ID of the company (required to fetch credentials). |
| `option` | String | Action to execute (see list below). |
| `dni` | String | Customer ID / NIF (required for most operations). |
| `matricula` | String | Vehicle registration plate. |
| `phone` | String | Customer phone number. |

## Documentation of API Options

### Customers & Candidates
- `detalle_cliente`: Retrieves customer details by NIF/DNI.
- `create_customer`: Registers a new customer in the ERP.
- `create_candidate`: Creates a potential lead/candidate.

### Policies & Claims
- `get_policies`: Returns all active policies for a customer.
- `get_policy_by_num`: Detailed info of a specific policy.
- `get_claims`: Retrieves claims filtered by category.
- `get_status_claims`: Current status of a specific claim ID.

### Insurance Quoting (Avant2 & Merlin)
- `tarificador_consulta_vehiculo`: Fetches technical vehicle data from DGT by plate.
- `tarificador_get_town_by_cp`: Converts Postal Code to official municipality name.
- `tarificador_consultar_catastro`: Automated property data (sqm, year built) for home insurance.
- `tarificador_create_project`: Standardized data submission to generate multi-insurer quotes.
