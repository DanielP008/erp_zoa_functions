import ebroker_functions

def get_erp_client(erp):
    """
    Initializes and authenticates the ERP client based on domain configuration.
    """
    password = erp.get('password')
    user = erp.get('user')
    client_id = erp.get('client_id')
    erp_type = erp.get('erp_type', 'ebroker')

    # Default to ebroker if type matches or is unknown (as per original logic)
    try:
        match erp_type:
            case 'ebroker':
                client = ebroker_functions.EBrokerClient(client_id=client_id)
                client.login(user, password)
                return client
            case _:
                # Fallback/Default behavior
                client = ebroker_functions.EBrokerClient(client_id=client_id)
                client.login(user, password)
                return client
    except Exception as e:
        return f"[ERROR] erp_auth.py: Failed to initialize/login ERP client: {e}"
