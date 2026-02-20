def get_company_config(company_id: str):
    """
    MOCK: Returns a dummy configuration for testing.
    Bypasses Firebase connection.
    """
    return {
        "system": "test_system",
        "erp": {
            "erp_type": "ebroker",
            "user": "dummy_user",
            "password": "dummy_password",
            "client_id": "dummy_client_id"
        }
    }
