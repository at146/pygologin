from typing import Any, Dict, List, Union
import requests


API_URL_BROWSER = "https://api.gologin.com/browser"


class TestBrowserController:
    def headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": "Bearer " + access_token,
            "User-Agent": "Selenium-API",
        }

    def test_getBrowserCookies(self, access_token: str, profile_id: str):
        response = requests.get(
            f"{API_URL_BROWSER}/{profile_id}/cookies",
            headers=self.headers(access_token),
        )
        assert response.ok is True
        assert "application/json" in response.headers.get("Content-Type", "")
        json = response.json()
        assert json is not None

    def test_postBrowserCookies(
        self, access_token: str, profile_id: str, cookies: List[Dict[str, Any]]
    ):
        response = requests.post(
            f"{API_URL_BROWSER}/{profile_id}/cookies",
            headers=self.headers(access_token),
            json=cookies,
        )
        assert response.ok is True

    def test_patchBrowserProxy(
        self,
        access_token: str,
        profile_id: str,
        proxy: Dict[str, Union[str, int]] = {"mode": "none"},
    ):
        response = requests.patch(
            f"{API_URL_BROWSER}/{profile_id}/proxy",
            headers=self.headers(access_token),
            json=proxy,
        )
        assert response.ok is True
