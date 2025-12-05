import requests
from typing import Tuple, Optional
from src.constants import APP_VERSION, GITHUB_REPO

class UpdateChecker:
    def __init__(self):
        self.current_version = APP_VERSION
        self.repo = GITHUB_REPO

    def check_for_updates(self) -> Tuple[bool, str, str]:
        """
        Check GitHub for the latest release.
        Returns: (update_available, latest_version, release_url)
        """
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get("tag_name", "").strip()
                html_url = data.get("html_url", "")
                
                if latest_tag:
                    if self.is_newer(latest_tag, self.current_version):
                        return True, latest_tag, html_url
                    
        except Exception as e:
            print(f"Update check failed: {e}")
            
        return False, "", ""

    def is_newer(self, remote_ver: str, local_ver: str) -> bool:
        """
        Compare two version strings (e.g. 'v1.2.0' vs 'v1.1.0')
        Returns True if remote_ver > local_ver
        """
        try:
            # Strip 'v' prefix and split by '.'
            r_parts = [int(p) for p in remote_ver.lstrip('v').split('.')]
            l_parts = [int(p) for p in local_ver.lstrip('v').split('.')]
            
            # Pad with zeros if lengths differ (e.g. 1.2 vs 1.2.1)
            length = max(len(r_parts), len(l_parts))
            r_parts.extend([0] * (length - len(r_parts)))
            l_parts.extend([0] * (length - len(l_parts)))
            
            return r_parts > l_parts
        except ValueError:
            # Fallback for non-semver tags: just strictly not equal? 
            # Or safer to return False to avoid loop? Let's return False if parse fails.
            return False
