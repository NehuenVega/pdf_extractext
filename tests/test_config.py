import pytest
from pydantic import ValidationError

from App.core.config import Settings


def test_defaults_match_the_load_test_setup():
    settings = Settings()

    assert settings.EXTRACTION_WORKERS == 1
    assert settings.MAX_QUEUE_SIZE == 8
    assert settings.max_file_size_bytes == 32 * 1024 * 1024


def test_values_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("MAX_QUEUE_SIZE", "0")
    monkeypatch.setenv("QUEUE_TIMEOUT_SECONDS", "2.5")

    settings = Settings()

    assert settings.MAX_QUEUE_SIZE == 0
    assert settings.QUEUE_TIMEOUT_SECONDS == 2.5


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("EXTRACTION_WORKERS", "0"),
        ("MAX_QUEUE_SIZE", "-1"),
        ("QUEUE_TIMEOUT_SECONDS", "nan"),
        ("UPLOAD_TIMEOUT_SECONDS", "0"),
        ("MAX_FILE_SIZE_MB", "muchos"),
        ("PORT", "70000"),
        ("LOG_LEVEL", "VERBOSE"),
    ],
)
def test_invalid_values_stop_the_application(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()
