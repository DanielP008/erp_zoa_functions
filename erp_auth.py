import ebroker_functions
import tesis_functions

def get_erp_client(data):
    """
    Initializes and authenticates the ERP client based on domain configuration.
    """
    erp = data.get('erp', {})
    password = erp.get('password')
    user = erp.get('user')
    client_id = erp.get('client_id')
    erp_type = erp.get('erp_type', 'ebroker')
    api_key = erp.get('api_key', '')
    environment = erp.get('environment', 'production')
    x_user_email = erp.get('x_user_email', user)#necesario en metodos de tesis

    # Default to ebroker if type matches or is unknown (as per original logic)
    try:
        match erp_type:
            case 'ebroker':
                client = ebroker_functions.EBrokerClient(client_id=client_id)
                client.login(user, password)
                return client
            case 'tesis':
                client = tesis_functions.TesisClient(api_key=api_key, environment=environment)
                client.login(user, password, x_user_email)
                return client
            case _:
                # Fallback/Default behavior
                client = ebroker_functions.EBrokerClient(client_id=client_id)
                client.login(user, password)
                return client
    except Exception as e:
        return f"[ERROR] erp_auth.py: Failed to initialize/login ERP client: {e}"
