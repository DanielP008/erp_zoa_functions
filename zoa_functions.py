import requests
import json

def create_card(params: dict) -> dict:
    """
    Creates a card (opportunity, task, etc.) in the Zoa Flows system.
    """
    #url = 'https://api.zoasuite.com/api/flows'
    url = 'https://test-673887944015.europe-southwest1.run.app/'
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(params))
    
    try:
        return response.json()
    except Exception:
        return {
            "error": "Failed to parse JSON response",
            "status_code": response.status_code,
            "text": response.text
        }
