import uuid

import httpx

from support.auth import register_and_login
from support.drivers import DriverFactory, login_as


async def test_support_replies_unread_idempotency_and_reopening(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.admin_id()
    owner = await register_and_login(client, "support_user")
    body = {
        "client_request_id": str(uuid.uuid4()),
        "category": "payment",
        "subject": "Cash issue",
        "body": "Please help",
    }
    created = await client.post("/api/v1/support/tickets", json=body, headers=owner.csrf_headers)
    assert created.status_code == 201, created.text
    ticket = created.json()
    repeated = await client.post("/api/v1/support/tickets", json=body, headers=owner.csrf_headers)
    assert repeated.json()["id"] == ticket["id"]
    ticket_id = ticket["id"]
    await register_and_login(client, "outsider")
    assert (await client.get(f"/api/v1/support/tickets/{ticket_id}")).status_code == 404
    admin = await login_as(client, "admin")
    assert (await client.get("/api/v1/support/unread")).json()["count"] == 1
    assert (
        await client.post(
            f"/api/v1/support/tickets/{ticket_id}/read",
            json={"last_read_seq": 99},
            headers=admin.csrf_headers,
        )
    ).status_code == 422
    sent = {"client_message_id": str(uuid.uuid4()), "body": "<script>plain text</script>"}
    reply = await client.post(
        f"/api/v1/support/tickets/{ticket_id}/messages", json=sent, headers=admin.csrf_headers
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["seq"] == 2
    assert (
        await client.post(
            f"/api/v1/support/tickets/{ticket_id}/messages", json=sent, headers=admin.csrf_headers
        )
    ).json()["seq"] == 2
    closed = await client.patch(
        f"/api/v1/admin/support/tickets/{ticket_id}",
        json={"status": "resolved"},
        headers=admin.csrf_headers,
    )
    assert closed.status_code == 200, closed.text
    owner = await login_as(client, "support_user")
    assert (await client.get("/api/v1/support/unread")).json()["count"] == 1
    pages = await client.get(f"/api/v1/support/tickets/{ticket_id}/messages?limit=1")
    assert pages.json()["items"][0]["seq"] == 2
    await client.post(
        f"/api/v1/support/tickets/{ticket_id}/read",
        json={"last_read_seq": 2},
        headers=owner.csrf_headers,
    )
    assert (await client.get("/api/v1/support/unread")).json()["count"] == 0
    response = await client.post(
        f"/api/v1/support/tickets/{ticket_id}/messages",
        json={"client_message_id": str(uuid.uuid4()), "body": "Still not fixed"},
        headers=owner.csrf_headers,
    )
    assert response.json()["seq"] == 3
    assert (await client.get(f"/api/v1/support/tickets/{ticket_id}")).json()["status"] == "open"
