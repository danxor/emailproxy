import os

from dotenv import load_dotenv

class Config:
    """A class that holds the current configuration"""
    bind: str
    port: int
    client_id: str
    authorize_url: str
    token_url: str
    credentials_file: str

    def __init__(self):
        load_dotenv()

        self.bind = os.getenv('SMTP_SERVER_BIND', '127.0.0.1')
        self.port = int(os.getenv('SMTP_SERVER_PORT', '1587'))
        self.client_id = os.getenv('OAUTH2_CLIENT_ID')
        self.authorize_url = os.getenv('OAUTH2_AUTHORIZE_URL', 'https://login.microsoftonline.com/common/oauth2/v2.0/devicecode')
        self.token_url = os.getenv('OAUTH2_TOKEN_URL', 'https://login.microsoftonline.com/openbox.se/oauth2/v2.0/token')
        self.credentials_file = os.getenv('CREDENTIALS_FILE', 'data/credentials.json')

    def is_valid(self) -> bool:
        errors = self.get_validation_errors()
        return len(errors) == 0

    def get_validation_errors(self) -> list[str]:
        errors = []

        if not self.client_id:
            errors.append('The environment variable OAUTH2_CLIENT_ID is required')
        
        return errors