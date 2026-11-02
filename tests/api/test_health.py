import httpx


async def test_live_reports_running_process(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_is_honest_until_database_is_connected(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body == {
        "error": {
            "code": "database_not_configured",
            "message": body["error"]["message"],
            "details": {},
        },
        "request_id": response.headers["X-Request-ID"],
    }
    assert body["error"]["message"]
