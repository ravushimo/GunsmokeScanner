import requests
from typing import Tuple
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
        Compare two version strings (e.g. 'v1.2.0' vs 'v1.1.0').
        Pre-release suffixes like '-dev' / '-beta' are ignored for ordering.
        Returns True if remote_ver > local_ver
        """
        try:
            return self._version_parts(remote_ver) > self._version_parts(local_ver)
        except ValueError:
            return False

    @staticmethod
    def _version_parts(ver: str) -> list:
        base = ver.lstrip("v").split("-", 1)[0].split("+", 1)[0]
        parts = [int(p) for p in base.split(".") if p != ""]
        # Pad so 1.2 compares cleanly with 1.2.0
        while len(parts) < 3:
            parts.append(0)
        return parts
