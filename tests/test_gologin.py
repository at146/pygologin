from pygologin import GoLogin


def test_gologin(access_token: str, profile_id: str) -> None:
    GoLogin(
        {
            "token": access_token,
            "profile_id": None,
        }
    )
