import json

def get_phones(company_name):
    """
    Retrieves contact phone numbers for an insurance company from insurance_phones.json.
    """
    if not company_name:
        return {}
    
    try:
        with open('insurance_phones.json', 'r', encoding='utf-8') as f:
            company_phones = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load insurance_phones.json: {e}"}
    
    company_clean = company_name.lower().replace('_', ' ')
    
    # 1. Manual aliases for cases that don't match by name (e.g., brand change)
    aliases = {
        'occident': 'catalana_occidente'
    }
    
    for alias_key, target_key in aliases.items():
        if alias_key in company_clean:
             return company_phones.get(target_key, {})

    # 2. Loose search: See if any JSON key is contained within the company name
    for key, phones in company_phones.items():
        key_normalized = key.replace('_', ' ')
        if key_normalized in company_clean:
            return phones
        if key in company_clean:
            return phones
            
    return {}
