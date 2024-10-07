import requests


PROFILES_URL = "https://gprofiles-new.gologin.com/"


class TestProfiles:
    def test_uploadEmptyProfile(self):
        response = requests.get(f"{PROFILES_URL}/zero_profile.zip")
        assert response.ok is True
        assert "application/zip" in response.headers.get("Content-Type", "")
        # with open("gologin_zeroprofile.zip", "wb") as f:
        #     f.write(response.content)
