import gspread
from google.auth import default
from utils import get_phones

class GoogleSheetsClient:
    """
    Client for interacting with Google Sheets.
    """
    def __init__(self, spreadsheet_url=None):
        self.spreadsheet_url = spreadsheet_url
        self.client = None
        self.spreadsheet = None

    def login(self, user=None, password=None):
        """
        Authenticates using Application Default Credentials (ADC).
        Note: The Spreadsheet must be shared with the Service Account email.
        """
        try:
            # Scopes for Google Sheets and Google Drive
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Authenticate using default credentials
            credentials, project_id = default(scopes=scopes)
            self.client = gspread.authorize(credentials)
            
            if self.spreadsheet_url:
                self.spreadsheet = self.client.open_by_url(self.spreadsheet_url)
            
            return True
        except Exception as e:
            raise Exception(f"Failed to authenticate with Google Sheets: {e}")

    def get_spreadsheet_title(self):
        """Returns the title of the opened spreadsheet."""
        if not self.spreadsheet:
            return "No spreadsheet opened"
        return self.spreadsheet.title

    def get_all_records(self):
        """
        Returns all rows of the first worksheet as an array of JSON (dictionaries).
        Uses position-based mapping (1-indexed columns):
        1: number, 2: company_name, 3: ramo, 4: risk_part1, 5: customer_name, 6: risk_part2, 7: nif
        """
        if not self.spreadsheet:
            raise Exception("Spreadsheet not opened. Call login() first.")
        
        try:
            worksheet = self.spreadsheet.get_worksheet(0)
            rows = worksheet.get_all_values()
            
            records = []
            for row in rows:
                if len(row) < 7: continue
                
                # Join risk from column 4 (index 3: Riesgo) and column 6 (index 5: Descripción riesgo)
                risk_p1 = str(row[3]).strip()
                risk_p2 = str(row[5]).strip()
                full_risk = f"{risk_p1} {risk_p2}".strip()
                
                records.append({
                    'Num. Póliza': str(row[0]).strip(),
                    'Alias compañía': str(row[1]).strip(),
                    'Producto.Ramo.GrupoDeRamos.Alias': str(row[2]).strip(),
                    'Riesgo': full_risk,
                    'Nombre completo': str(row[4]).strip(),
                    'Cliente.Nif': str(row[6]).strip()
                })
            return records
        except Exception as e:
            print(f"[ERROR] get_all_records: {e}")
            return []

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str=None):
        """
        Retrieves policies for a client based on NIF and filters by category (ramo).
        Uses position-based data from get_all_records.
        """
        try:
            records = self.get_all_records()
            
            polizas_ramo = []
            ramo_normalized = str(ramo or '').lower().replace('.', '').strip()
            
            # Robust NIF cleaner
            def clean_nif(v):
                return ''.join(filter(str.isalnum, str(v))).upper()

            target_nif = clean_nif(nif)
            
            for record in records:
                # Get NIF and clean it
                record_nif = clean_nif(record.get('Cliente.Nif', ''))
                
                if record_nif == target_nif and target_nif != '':
                    # Match ramo against 'Producto.Ramo.GrupoDeRamos.Alias' OR 'Riesgo'
                    row_ramo = str(record.get('Producto.Ramo.GrupoDeRamos.Alias', '')).lower()
                    full_risk = str(record.get('Riesgo', '')).lower()
                    
                    # If ramo is empty, it should match everything for that NIF
                    if not ramo_normalized or ramo_normalized in row_ramo or ramo_normalized in full_risk:
                        company_name = record.get('Alias compañía', '')
                        polizas_ramo.append({
                            'number': record.get('Num. Póliza', ''),
                            'company_name': company_name,
                            'risk': record.get('Riesgo', ''),
                            'company_id': company_id,
                            'phones': get_phones(company_name)
                        })
            
            return polizas_ramo
        except Exception as e:
            print(f"[ERROR] get_all_policys_by_client_category: {e}")
            return []

    def get_customer_claims_by_category(self, nif: str, ramo: str):
        """Placeholder for getting claims from Excel."""
        return {"message": "Method not yet implemented for Excel", "nif": nif}


def get_erp_client(erp_config):
    """
    Initializes and authenticates the Google Sheets client.
    Matches the signature expected by erp_auth.py and main.py.
    """
    print(f"[DEBUG] excel_functions.py erp_config: {erp_config}")
    spreadsheet_url = erp_config.get('url')

    print(f"[DEBUG] excel_functions.py: Attempting login with URL: {spreadsheet_url}")
    try:
        client = GoogleSheetsClient(spreadsheet_url=spreadsheet_url)
        client.login()
        return client
    except Exception as e:
        print(f"[ERROR] excel_functions.py Login failed: {e}")
        return None
