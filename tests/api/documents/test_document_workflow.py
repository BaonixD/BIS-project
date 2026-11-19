import httpx
import pytest

from support.auth import register_and_login
from support.documents import pdf_bytes
from support.drivers import DriverFactory, complete_profile, login_as


async def test_upload_review_revision_and_private_access(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.admin_id()
    driver = await register_and_login(client, "doc_driver", role="driver")
    assert (
        await client.patch(
            "/api/v1/drivers/me", json=complete_profile(), headers=driver.csrf_headers
        )
    ).status_code == 200
    for kind in ["identity_card", "driver_license"]:
        response = await client.put(
            f"/api/v1/drivers/me/documents/{kind}",
            files={"file": ("id.pdf", pdf_bytes(), "application/pdf")},
            headers=driver.csrf_headers,
        )
        assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_submit"] is True
    first = body["package"]
    file_id = body["documents"][0]["id"]
    submit = {"package_id": first["id"], "version": first["version"]}
    assert (
        await client.post(
            "/api/v1/drivers/me/documents/submit", json=submit, headers=driver.csrf_headers
        )
    ).status_code == 200
    locked = await client.put(
        "/api/v1/drivers/me/documents/identity_card",
        files={"file": ("new.pdf", pdf_bytes(), "application/pdf")},
        headers=driver.csrf_headers,
    )
    assert locked.status_code == 409
    admin = await login_as(client, "admin")
    denied = await client.post(
        f"/api/v1/admin/drivers/{driver.id}/approve", headers=admin.csrf_headers
    )
    assert denied.status_code == 409
    viewed = await client.get(f"/api/v1/documents/{file_id}/content")
    assert viewed.status_code == 200
    assert viewed.content.startswith(b"%PDF-")
    assert viewed.headers["cache-control"] == "private, no-store"
    reject = await client.post(
        f"/api/v1/admin/drivers/{driver.id}/documents/reject",
        json={**submit, "reason": "Upload a clearer copy"},
        headers=admin.csrf_headers,
    )
    assert reject.status_code == 200
    driver = await login_as(client, "doc_driver")
    revised = await client.post(
        "/api/v1/drivers/me/documents/revise", json=submit, headers=driver.csrf_headers
    )
    assert revised.status_code == 200, revised.text
    second = revised.json()["package"]
    assert second["version"] == first["version"] + 1
    next_submit = {"package_id": second["id"], "version": second["version"]}
    assert (
        await client.post(
            "/api/v1/drivers/me/documents/submit", json=next_submit, headers=driver.csrf_headers
        )
    ).status_code == 200
    admin = await login_as(client, "admin")
    assert (
        await client.post(
            f"/api/v1/admin/drivers/{driver.id}/approve", json=submit, headers=admin.csrf_headers
        )
    ).status_code == 409
    approved = await client.post(
        f"/api/v1/admin/drivers/{driver.id}/approve",
        json={**next_submit, "car_class": "business"},
        headers=admin.csrf_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval_status"] == "approved"
    await register_and_login(client, "outsider")
    assert (await client.get(f"/api/v1/documents/{file_id}/content")).status_code == 404


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("html", "invalid_document"),
        ("oversized", "document_too_large"),
    ],
)
async def test_invalid_pdf_is_rejected(client: httpx.AsyncClient, case: str, code: str) -> None:
    driver = await register_and_login(client, "driver", role="driver")
    await client.patch("/api/v1/drivers/me", json=complete_profile(), headers=driver.csrf_headers)
    data = (
        b"<html>not a pdf</html>"
        if case == "html"
        else b"x" * (10 * 1024 * 1024 + 65537)
        if case == "oversized"
        else pdf_bytes(active=case == "active", encrypted=case == "encrypted")
    )
    response = await client.put(
        "/api/v1/drivers/me/documents/driver_license",
        files={"file": ("file.pdf", data, "application/pdf")},
        headers=driver.csrf_headers,
    )
    assert response.status_code == (413 if case == "oversized" else 422)
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("identity_card", pdf_bytes(encrypted=True)),
        ("driver_license", pdf_bytes(active=True)),
    ],
)
async def test_upload_does_not_parse_pdf(client: httpx.AsyncClient, kind: str, data: bytes) -> None:
    driver = await register_and_login(client, "driver", role="driver")
    profile = await client.patch(
        "/api/v1/drivers/me", json=complete_profile(), headers=driver.csrf_headers
    )
    assert profile.status_code == 200
    response = await client.put(
        f"/api/v1/drivers/me/documents/{kind}",
        files={"file": ("file.pdf", data, "application/pdf")},
        headers=driver.csrf_headers,
    )
    assert response.status_code == 200, response.text
    [document] = response.json()["documents"]
    assert document["kind"] == kind
    assert document["page_count"] is None
