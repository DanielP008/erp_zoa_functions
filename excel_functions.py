import gspread
from google.auth import default
from utils import get_phones

class GoogleSheetsClient:
    """
    Client for interacting with Google Sheets.
    """
    def __init__(self, spreadsheet_url):
        self.spreadsheet_url = spreadsheet_url
        self.client = None
        self.spreadsheet = None

    def login(self):
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
            self.spreadsheet = self.client.open_by_url(self.spreadsheet_url)
            return True
        except Exception as e:
            raise Exception(f"Login failed: {e}")

    def get_spreadsheet_title(self):
        """Returns the title of the opened spreadsheet."""
        if not self.spreadsheet:
            return "No spreadsheet opened"
        return self.spreadsheet.title

    def get_all_records(self):
        """
        Returns all rows of the first worksheet as an array.
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
        except Exception:
            return []

    def get_all_policys_by_client_category(self, nif: str, ramo: str, company_id: str=None):
        """
        Retrieves policies for a client based on NIF and filters by category (ramo).
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
                record_nif = clean_nif(record.get('Cliente.Nif', ''))
                
                if record_nif == target_nif and target_nif != '':
                    row_ramo = str(record.get('Producto.Ramo.GrupoDeRamos.Alias', '')).lower()
                    full_risk = str(record.get('Riesgo', '')).lower()
                    
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
        except Exception:
            return []

    def get_customer_claims_by_category(self, nif: str, ramo: str):
        """Placeholder for getting claims from Excel."""
        return {"message": "Method not yet implemented for Excel", "nif": nif}

    def process_load_renewals(self, company_id: str, start_date=None, frequency: int = 7, 
                              percent_threshold: float = 8.0, 
                              amount_threshold: float = 0.0):
        if not self.spreadsheet:
            raise Exception("Spreadsheet not opened. Call login() first.")
        
        try:
            worksheet = self.spreadsheet.get_worksheet(0)
            rows = worksheet.get_all_values()
        except Exception:
            return []

        if not rows or len(rows) < 2:
            return []
            
        result_list = []
        
        for row in rows[1:]:
            if len(row) < 19:
                continue
                
            policy_num = str(row[0]).strip()
            if not policy_num:
                continue
                
            nif = str(row[7]).strip()
            phone = str(row[11]).strip()
            
            p_actual_str = str(row[17]).replace('.', '').replace(',', '.').strip()
            p_anterior_str = str(row[18]).replace('.', '').replace(',', '.').strip()

            try:
                p_premium = float(p_actual_str) if p_actual_str else 0.0
                c_premium = float(p_anterior_str) if p_anterior_str else 0.0
            except ValueError:
                continue
                
            if p_premium > 0 and c_premium > 0:
                diff = p_premium - c_premium
                percent_diff = (diff / c_premium) * 100 if c_premium > 0 else 0
                
                is_flagged = percent_diff >= percent_threshold
                if amount_threshold > 0:
                    is_flagged = is_flagged or (diff >= amount_threshold)
                    
                if is_flagged:
                    title = f"Renovación tipo A {policy_num}"
                    tag = f">{int(percent_threshold)}%"
                else:
                    title = f"Renovación tipo B {policy_num}"
                    tag = f"<{int(percent_threshold)}%"
                    
                client_phone = phone.replace('+', '').replace(' ', '')
                if len(client_phone) == 9:
                    client_phone = "34" + client_phone
                    
                card_payload = {
                    "company_id": company_id,
                    "action": "cards",
                    "option": "create",
                    "title": title,
                    "phone": client_phone,
                    "card_type": "opportunity",
                    "pipeline_name": "Renovaciones",
                    "stage_name": "Nuevo",
                    "amount": p_premium,
                    "tags_name": tag
                }
                
                try:
                    import zoa_functions
                    zoa_functions.create_card(card_payload)
                except Exception:
                    pass
                    
                result_list.append({
                    "policy_number": policy_num,
                    "client_nif": nif,
                    "p_receipt": {
                        "id": f"P_{policy_num}",
                        "amount": p_premium,
                        "status": "PENDIENTE/DVTO.BANCO"
                    },
                    "c_receipt": {
                        "id": f"C_{policy_num}",
                        "amount": c_premium,
                        "status": "COBRADO"
                    },
                    "percent_diff": round(percent_diff, 2),
                    "amount_diff": round(diff, 2),
                    "is_flagged": is_flagged
                })
                
        return result_list


def get_erp_client(data):
    """
    Initializes and authenticates the Google Sheets client.
    """
    erp_config = data.get('erp', {})
    if not isinstance(erp_config, dict):
        raise ValueError(f"erp_config must be a dictionary, got {type(erp_config).__name__}")

    # Try common keys for the spreadsheet URL
    spreadsheet_url = erp_config.get('url')

    if not spreadsheet_url:
        raise ValueError("Spreadsheet URL not found in erp configuration (checked 'url')")
    
    spreadsheet_url = str(spreadsheet_url).strip()
    if not spreadsheet_url.startswith('https://'):
        raise ValueError(f"Invalid Google Sheet URL (must start with https://): {spreadsheet_url}")

    # Normalize URL: strip trailing /edit, #gid, etc. to get the base spreadsheet URL
    if '/edit' in spreadsheet_url:
        spreadsheet_url = spreadsheet_url.split('/edit')[0]

    client = GoogleSheetsClient(spreadsheet_url=spreadsheet_url)
    client.login()
    return client
