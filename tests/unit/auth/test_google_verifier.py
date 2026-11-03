"""The real ``GoogleIdTokenVerifier`` against locally signed tokens, without the network.

The transport serves a test public key in place of Google's certificates; the
checks themselves (signature, issuer, audience, expiry) are google-auth's.
"""

import json
import time
from collections.abc import Mapping
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt, transport

from taxi_service.modules.auth.exceptions import (
    GoogleLoginUnavailableError,
    InvalidGoogleTokenError,
)
from taxi_service.modules.auth.google import GoogleClaims, GoogleIdTokenVerifier

AUDIENCE = "test-client-id.apps.googleusercontent.com"
KEY_ID = "test-key"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"


def private_key_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def public_key_pem(private_pem: bytes) -> str:
    key = serialization.load_pem_private_key(private_pem, password=None)
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


@pytest.fixture(scope="module")
def google_key() -> bytes:
    return private_key_pem()


@pytest.fixture(scope="module")
def foreign_key() -> bytes:
    return private_key_pem()


class CertsResponse(transport.Response):
    def __init__(self, status: int, body: Mapping[str, str]) -> None:
        self._status = status
        self._data = json.dumps(body).encode()

    @property
    def status(self) -> int:
        return self._status

    @property
    def headers(self) -> Mapping[str, str]:
        return {"content-type": "application/json"}

    @property
    def data(self) -> bytes:
        return self._data


class CertsTransport(transport.Request):
    def __init__(self, certs: Mapping[str, str], *, status: int = 200) -> None:
        self.certs = certs
        self.status = status
        self.urls: list[str] = []

    def __call__(
        self,
        url: Any,
        method: Any = "GET",
        body: Any = None,
        headers: Any = None,
        timeout: Any = None,
        **kwargs: Any,
    ) -> transport.Response:
        self.urls.append(url)
        return CertsResponse(self.status, self.certs)


def claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    return {
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
        "sub": "10001",
        "email": "alice@gmail.com",
        "email_verified": True,
        "name": "Alice Smith",
        "iat": now,
        "exp": now + 3600,
        **overrides,
    }


def token(private_pem: bytes, payload: Mapping[str, Any]) -> str:
    signer = crypt.RSASigner.from_string(private_pem, key_id=KEY_ID)  # type: ignore[no-untyped-call]
    encoded: bytes = jwt.encode(signer, payload)  # type: ignore[no-untyped-call]
    return encoded.decode()


@pytest.fixture
def certs_transport(google_key: bytes) -> CertsTransport:
    return CertsTransport({KEY_ID: public_key_pem(google_key)})


@pytest.fixture
def verifier(certs_transport: CertsTransport) -> GoogleIdTokenVerifier:
    return GoogleIdTokenVerifier(certs_transport)


async def test_valid_token_gives_its_claims(
    verifier: GoogleIdTokenVerifier, certs_transport: CertsTransport, google_key: bytes
) -> None:
    result = await verifier.verify(token(google_key, claims()), audience=AUDIENCE)

    assert result == GoogleClaims(
        sub="10001", email="alice@gmail.com", email_verified=True, name="Alice Smith"
    )
    assert certs_transport.urls == [GOOGLE_CERTS_URL]


async def test_unverified_email_and_missing_name_are_reported(
    verifier: GoogleIdTokenVerifier, google_key: bytes
) -> None:
    payload = claims(email_verified=False)
    del payload["name"]

    result = await verifier.verify(token(google_key, payload), audience=AUDIENCE)

    assert (result.email_verified, result.name) == (False, None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-else.apps.googleusercontent.com"},
        {"iss": "https://evil.example"},
        {"iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600},
        {"sub": ""},
    ],
    ids=["audience", "issuer", "expired", "empty_subject"],
)
async def test_wrong_claims_are_invalid(
    verifier: GoogleIdTokenVerifier, google_key: bytes, overrides: dict[str, Any]
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await verifier.verify(token(google_key, claims(**overrides)), audience=AUDIENCE)


async def test_token_signed_by_another_key_is_invalid(
    verifier: GoogleIdTokenVerifier, foreign_key: bytes
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await verifier.verify(token(foreign_key, claims()), audience=AUDIENCE)


@pytest.mark.parametrize("credential", ["not-a-jwt", "a.b.c", ""])
async def test_garbage_is_invalid(verifier: GoogleIdTokenVerifier, credential: str) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await verifier.verify(credential, audience=AUDIENCE)


async def test_unreachable_certificates_make_google_unavailable(google_key: bytes) -> None:
    verifier = GoogleIdTokenVerifier(CertsTransport({}, status=500))

    with pytest.raises(GoogleLoginUnavailableError):
        await verifier.verify(token(google_key, claims()), audience=AUDIENCE)
