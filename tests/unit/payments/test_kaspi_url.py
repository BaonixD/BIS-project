import pytest

from taxi_service.modules.payments.config import (
    InvalidKaspiPaymentUrlError,
    validate_kaspi_payment_url,
)

TEST_URL = "https://pay.kaspi.kz/pay/test123"


@pytest.mark.parametrize(
    "raw",
    [TEST_URL, "https://pay.kaspi.kz/pay/abc123", "https://pay.kaspi.kz/pay/A1_b-2"],
)
def test_point_of_sale_link_is_accepted(raw: str) -> None:
    assert validate_kaspi_payment_url(raw) == raw


@pytest.mark.parametrize("raw", [f"  {TEST_URL}\n", f"\t{TEST_URL} "])
def test_surrounding_whitespace_is_trimmed(raw: str) -> None:
    assert validate_kaspi_payment_url(raw) == TEST_URL


def test_scheme_is_normalised_to_lowercase() -> None:
    assert validate_kaspi_payment_url("HTTPS://pay.kaspi.kz/pay/test123") == TEST_URL


REJECTED = {
    "http": "http://pay.kaspi.kz/pay/test123",
    "ftp": "ftp://pay.kaspi.kz/pay/test123",
    "javascript": "javascript:alert(1)",
    "no_scheme": "pay.kaspi.kz/pay/test123",
    "scheme_relative": "//pay.kaspi.kz/pay/test123",
    "empty_host": "https:///pay/test123",
    "parent_domain": "https://kaspi.kz/pay/test123",
    "other_host": "https://evil.com/pay/test123",
    "lookalike_suffix": "https://pay.kaspi.kz.evil.com/pay/test123",
    "host_in_path": "https://evil.com/pay.kaspi.kz",
    "host_in_path_no_scheme": "evil.com/pay.kaspi.kz",
    "subdomain": "https://sub.pay.kaspi.kz/pay/test123",
    "trailing_dot": "https://pay.kaspi.kz./pay/test123",
    "uppercase_host": "https://PAY.KASPI.KZ/pay/test123",
    "userinfo": "https://user@pay.kaspi.kz/pay/test123",
    "userinfo_password": "https://user:secret@pay.kaspi.kz/pay/test123",
    "host_as_userinfo": "https://pay.kaspi.kz@evil.com/pay/test123",
    "backslash_trick": "https://pay.kaspi.kz\\@evil.com/pay/test123",
    "default_port": "https://pay.kaspi.kz:443/pay/test123",
    "custom_port": "https://pay.kaspi.kz:8443/pay/test123",
    "root": "https://pay.kaspi.kz",
    "root_slash": "https://pay.kaspi.kz/",
    "missing_id": "https://pay.kaspi.kz/pay/",
    "other_path": "https://pay.kaspi.kz/other/test123",
    "extra_segment": "https://pay.kaspi.kz/pay/test123/extra",
    "trailing_slash": "https://pay.kaspi.kz/pay/test123/",
    "dot_segments": "https://pay.kaspi.kz/pay/../admin",
    "percent_encoded": "https://pay.kaspi.kz/pay/%2e%2e",
    "too_long_id": "https://pay.kaspi.kz/pay/" + "a" * 65,
    "invented_amount_query": "https://pay.kaspi.kz/pay/test123?amount=1500",
    "fragment": "https://pay.kaspi.kz/pay/test123#x",
    "inner_tab": "https://pay.kaspi.kz/pay/te\tst123",
    "inner_newline": "https://pay.kaspi.kz/pay/test123\nhttps://evil.com",
    "inner_space": "https://pay.kaspi.kz /pay/test123",
    "ipv6_garbage": "https://[pay.kaspi.kz/pay/test123",
}


@pytest.mark.parametrize("raw", list(REJECTED.values()), ids=list(REJECTED))
def test_unsafe_or_unexpected_link_is_rejected_without_echo(raw: str) -> None:
    with pytest.raises(InvalidKaspiPaymentUrlError) as caught:
        validate_kaspi_payment_url(raw)

    message = str(caught.value)
    assert "KASPI_PAYMENT_URL" in message
    assert raw.strip() not in message
