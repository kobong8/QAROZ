import pytest

from qa_manager.core.security import protect_for_storage, redact, validate_http_url


def test_redact_nested_secrets():
    value = redact(
        {
            "headers": {
                "Authorization": "Bearer secret",
                "X-API-Key": "key",
                "Accept": "json",
            },
            "password": "pw",
        }
    )
    assert value["headers"] == {
        "Authorization": "[REDACTED]",
        "X-API-Key": "[REDACTED]",
        "Accept": "json",
    }
    assert value["password"] == "[REDACTED]"


def test_url_validation_rejects_credentials_and_remote_when_local():
    with pytest.raises(ValueError):
        validate_http_url("http://me:pw@localhost")
    with pytest.raises(ValueError):
        validate_http_url("https://example.com", allow_remote=False)


def test_storage_keeps_environment_reference_but_not_secret():
    assert (
        protect_for_storage({"Authorization": "env:QAROZ_TOKEN"})["Authorization"]
        == "env:QAROZ_TOKEN"
    )
    assert (
        protect_for_storage({"Authorization": "real-secret"})["Authorization"]
        == "[REDACTED]"
    )
