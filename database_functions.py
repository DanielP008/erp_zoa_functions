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
        docs = firestore_db.collection(u'clientIDs').where(u'ids', u'array_contains', company_id).get()
    except Exception as e:
        return {"error": f"[ERROR] Database connection failed: {e}"}
    
    if not docs:
        return None
        
    return docs[0].to_dict()