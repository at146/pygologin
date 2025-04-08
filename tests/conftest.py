import os
import pytest


@pytest.fixture()
def access_token() -> str:
    access_token = os.environ.get("ACCESS_TOKEN")
    if not access_token:
        raise ValueError("ACCESS_TOKEN environment variable is not set")
    return access_token


@pytest.fixture()
def profile_id() -> str:
    profile_id = os.environ.get("PROFILE_ID")
    if not profile_id:
        raise ValueError("PROFILE_ID environment variable is not set")
    return profile_id
