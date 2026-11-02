import re

import httpx
import pytest

REQUEST_ID_HEADER = "X-Request-ID"
GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")


async def test_request_id_is_generated(client: httpx.AsyncClient) -> None:
    first = await client.get("/openapi.json")
    second = await client.get("/openapi.json")

    assert GENERATED_ID.fullmatch(first.headers[REQUEST_ID_HEADER])
    assert GENERATED_ID.fullmatch(second.headers[REQUEST_ID_HEADER])
    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


async def test_valid_client_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json", headers={REQUEST_ID_HEADER: "client-req.42_A"})

    assert response.headers[REQUEST_ID_HEADER] == "client-req.42_A"


@pytest.mark.parametrize("unsafe_id", ["", "has space", "x" * 65, "line\tbreak", "ключ"])
async def test_unsafe_client_request_id_is_replaced(
    client: httpx.AsyncClient, unsafe_id: str
) -> None:
    response = await client.get(
        "/openapi.json", headers=[(REQUEST_ID_HEADER.encode(), unsafe_id.encode())]
    )

    assert GENERATED_ID.fullmatch(response.headers[REQUEST_ID_HEADER])
