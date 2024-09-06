from typing import Dict, List
import requests


API_URL = "https://api.gologin.com"


class TestBrowserController:
    def headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": "Bearer " + access_token,
            "User-Agent": "Selenium-API",
        }

    def test_getBrowserCookies(self, access_token: str, profile_id: str):
        response = requests.get(
            f"{API_URL}/browser/{profile_id}/cookies",
            headers=self.headers(access_token)
        )
        assert response.ok is True
        assert 'application/json' in response.headers.get('Content-Type', '')
        

    def test_postBrowserCookies(
        self, access_token: str, profile_id: str, cookies: List
    ):
        response = requests.post(
            f"{API_URL}/browser/{profile_id}/cookies",
            headers=self.headers(access_token),
            json=cookies,
        )
        assert response.ok is True
