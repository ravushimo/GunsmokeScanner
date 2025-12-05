import requests
import os
from typing import Dict, Any, Tuple

class GunsmokeClient:
    def __init__(self, api_url: str = 'https://gunsmoke.app'):
        self.api_url = api_url

    def set_environment(self, is_production: bool):
        if is_production:
            self.api_url = 'https://gunsmoke.app'
        else:
            self.api_url = 'http://localhost:5000'

            self.api_url = 'http://localhost:5000'

    def verify_credentials(self, username: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Verify user credentials"""
        verify_url = f"{self.api_url}/api/v1/auth/verify"
        try:
            response = requests.post(
                verify_url,
                json={'username': username, 'password': password},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                return True, "Authenticated", result.get('data', {})
            else:
                return False, result.get('message', 'Authentication failed'), {}
        except Exception as e:
            return False, f"Verification error: {str(e)}", {}

    def upload_file(self, filepath: str, username: str, password: str, remove_missing: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        """Upload CSV file"""
        if not os.path.exists(filepath):
            return False, "File not found", {}

        upload_url = f"{self.api_url}/api/v1/gunsmoke/upload"
        
        try:
            with open(filepath, 'rb') as f:
                files = {'csv_file': (os.path.basename(filepath), f, 'text/csv')}
                data = {
                    'username': username,
                    'password': password,
                    'remove_missing': '1' if remove_missing else '0'
                }
                
                response = requests.post(upload_url, files=files, data=data, timeout=30)
                result = response.json()
                
                if response.status_code == 200 and result.get('success'):
                    return True, result.get('message', 'Upload successful'), result.get('data', {})
                else:
                    return False, result.get('message', 'Upload failed'), {}
        except Exception as e:
            return False, f"Upload error: {str(e)}", {}
