from pathlib import Path

import pytest
from pydantic import ValidationError

from taxi_service.modules.payments.config import PaymentSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEST_URL = "https://pay.kaspi.kz/pay/test123"


@pytest.fixture(autouse=True)
def _isolate_payment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KASPI_PAYMENT_URL", raising=False)


def test_without_link_kaspi_is_disabled() -> None:
    settings = PaymentSettings(_env_file=None)

    assert settings.kaspi_payment_url is None
    assert settings.kaspi_enabled is False


def test_blank_link_from_env_example_means_disabled() -> None:
    settings = PaymentSettings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.kaspi_enabled is False


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_blank_link_from_environment_means_disabled(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("KASPI_PAYMENT_URL", value)

    settings = PaymentSettings(_env_file=None)

    assert settings.kaspi_payment_url is None
    assert settings.kaspi_enabled is False


def test_valid_link_is_read_from_unprefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KASPI_PAYMENT_URL", f" {TEST_URL}\n")

    settings = PaymentSettings(_env_file=None)

    assert settings.kaspi_payment_url == TEST_URL
    assert settings.kaspi_enabled is True


def test_valid_link_is_read_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"KASPI_PAYMENT_URL={TEST_URL}\nUNRELATED=1\n", encoding="utf-8")

    assert PaymentSettings(_env_file=env_file).kaspi_payment_url == TEST_URL


@pytest.mark.parametrize(
    "value",
    [
        "http://pay.kaspi.kz/pay/test123",
        "https://pay.kaspi.kz.evil.com/pay/test123",
        "https://user@pay.kaspi.kz/pay/test123",
        "https://pay.kaspi.kz:8443/pay/test123",
        "https://pay.kaspi.kz/pay/test123?amount=1500",
    ],
)
def test_invalid_link_fails_at_load_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("KASPI_PAYMENT_URL", value)

    with pytest.raises(ValidationError) as caught:
        PaymentSettings(_env_file=None)

    message = str(caught.value)
    assert "kaspi_payment_url" in message
    assert "KASPI_PAYMENT_URL" in message
    assert value not in message


def test_explicit_value_is_validated_too() -> None:
    with pytest.raises(ValidationError):
        PaymentSettings(_env_file=None, kaspi_payment_url="https://evil.com/pay/test123")
