from firebase_admin import firestore
import firebase_admin

def get_company_config(company_id: str):
    """
    Retrieves the configuration for a company from Firebase Firestore.
    """
    # Ensure app is initialized (idempotent)
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
        
    firestore_db = firestore.client()
    try:
        docs = firestore_db.collection(u'waba_accounts').where(u'phones_ids', u'array_contains', company_id).get()
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None
    
    if not docs:
        return None
        
    values = docs[0].to_dict()
    domain_info = next((d for d in values.get('domains', []) if d.get('phone_id') == company_id), None)
    
    return domain_info
