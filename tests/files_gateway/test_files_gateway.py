from typing import Dict
import requests


FILES_GATEWAY = "https://files-gateway.gologin.com"


class TestFilesGateway:
    def headers(self, access_token: str, profile_id: str) -> Dict[str, str]:
        return {
            "Authorization": "Bearer " + access_token,
            # "User-Agent": "Selenium-API",
            "browserId": profile_id,
        }

    def test_downloadProfileZip(self, access_token: str, profile_id: str) -> None:
        response = requests.get(
            f"{FILES_GATEWAY}/download",
            headers=self.headers(access_token, profile_id),
        )
        assert response.ok is True
        assert "application/zip" in response.headers.get("Content-Type", "")
        # Проверка на существование профиля
        assert len(response.content) != 0

        # profile_zip_path = f"gologin_{profile_id}.zip"
        # with open(profile_zip_path, "wb") as f:
        #     f.write(response.content)
