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
        """
        if not self.spreadsheet:
            raise Exception("Spreadsheet not opened. Call login() first.")
        
        try:
            # Assume data is in the first sheet
            worksheet = self.spreadsheet.get_worksheet(0)
            return worksheet.get_all_records()
        except Exception as e:
            print(f"[ERROR] get_all_records: {e}")
            return []

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str=None):
        """
        Retrieves policies for a client based on NIF and filters by category (ramo).
        Expected columns: Num. Póliza, Alias compañía, Riesgo, Nombre completo, Descripción riesgo, Cliente.Nif
        """
        try:
            records = self.get_all_records()
            
            polizas_ramo = []
            ramo_normalized = ramo.lower().replace('.', '')
            
            for record in records:
                # Match NIF (case-insensitive and strip whitespace)
                record_nif = str(record.get('Cliente.Nif', '')).strip().upper()
                target_nif = str(nif).strip().upper()
                
                if record_nif == target_nif:
                    # Match ramo (category) against 'Descripción riesgo'
                    desc_riesgo = str(record.get('Descripción riesgo', '')).lower().replace('.', '')
                    
                    if ramo_normalized in desc_riesgo:
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
    spreadsheet_url = erp_config.get('spreadsheet_url')
    if not spreadsheet_url:
        # Fallback to 'url' or 'client_id' if spreadsheet_url is not specifically named
        spreadsheet_url = erp_config.get('url') or erp_config.get('client_id')

    try:
        client = GoogleSheetsClient(spreadsheet_url=spreadsheet_url)
        client.login()
        return client
    except Exception as e:
        print(f"[ERROR] excel_functions.py: {e}")
        return None
