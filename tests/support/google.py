"""Google ID tokens without the network: the fake verifier is injected into ``create_app``.

``FakeGoogleVerifier.issue`` returns a credential string the fake accepts, but only
for the audience it was issued to, as Google's real check would. The real
``GoogleIdTokenVerifier`` is tested offline with locally signed tokens
(``tests/unit/auth/test_google_verifier.py``).
"""

from dataclasses import dataclass, field

from taxi_service.modules.auth.exceptions import InvalidGoogleTokenError
from taxi_service.modules.auth.google import GoogleClaims

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
GOOGLE_URL = "/api/v1/auth/google"
PROVIDERS_URL = "/api/v1/auth/providers"


@dataclass
class FakeGoogleVerifier:
    calls: list[str] = field(default_factory=list)
    _tokens: dict[str, tuple[str, GoogleClaims]] = field(default_factory=dict)

    def issue(
        self,
        sub: str,
        email: str | None,
        *,
        name: str | None = None,
        email_verified: bool = True,
        audience: str = CLIENT_ID,
    ) -> str:
        credential = f"fake-google-id-token-{len(self._tokens) + 1}"
        claims = GoogleClaims(sub=sub, email=email, email_verified=email_verified, name=name)
        self._tokens[credential] = (audience, claims)
        return credential

    async def verify(self, credential: str, *, audience: str) -> GoogleClaims:
        self.calls.append(credential)
        found = self._tokens.get(credential)
        if found is None or found[0] != audience:
            raise InvalidGoogleTokenError
        return found[1]
