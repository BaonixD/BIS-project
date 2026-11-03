import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.schemas import (
    PaymentCommandResponse,
    PaymentConfirmRequest,
    PaymentMethodRequest,
    PaymentReportRequest,
    PaymentResponse,
)
from taxi_service.modules.payments.service import PaymentResult, PaymentService
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides/{ride_id}/payment", tags=["payments"])

COMMAND_ERRORS = error_responses(401, 403, 404, 409)


def get_payment_settings(request: Request) -> PaymentSettings:
    """FastAPI dependency: the settings ``create_app`` read once (``KASPI_PAYMENT_URL``)."""
    settings: PaymentSettings = request.app.state.payment_settings
    return settings


PaymentSettingsDep = Annotated[PaymentSettings, Depends(get_payment_settings)]


def get_payment_service(
    session: SessionDep, clock: ClockDep, settings: PaymentSettingsDep
) -> PaymentService:
    return PaymentService(session, clock, settings)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


def _respond(
    result: PaymentResult, settings: PaymentSettings, user: AuthenticatedUser
) -> PaymentCommandResponse:
    return PaymentCommandResponse.after(
        result.payment,
        settings,
        changed=result.changed,
        for_admin=user.role is UserRole.ADMIN,
    )


@router.get("", responses=error_responses(401, 404, 409))
async def read_payment(
    ride_id: uuid.UUID,
    user: CurrentUser,
    payments: PaymentServiceDep,
    settings: PaymentSettingsDep,
) -> PaymentResponse:
    """How to pay a completed ride, and the payment's state.

    For the ride's passenger, its driver and admins. Cash is the default; with
    `kaspi_link` the response has the configured Kaspi `payment_url` until the
    payment is confirmed: the buyer enters `amount_kzt` in Kaspi by hand, and
    opening the link, scanning its QR code or coming back from Kaspi does not
    confirm anything. Confirmation is always manual (`verification: manual`).

    Errors: `404 ride_not_found` (unknown ride or not yours); `409
    ride_not_completed` (no payment before the ride is completed).
    """
    payment = await payments.get(ride_id, user_id=user.id, role=user.role)
    return PaymentResponse.build(payment, settings, for_admin=user.role is UserRole.ADMIN)


@router.put("/method", responses=error_responses(401, 403, 404, 409, 503))
async def change_payment_method(
    ride_id: uuid.UUID,
    body: PaymentMethodRequest,
    user: CurrentUser,
    payments: PaymentServiceDep,
    settings: PaymentSettingsDep,
) -> PaymentCommandResponse:
    """The passenger chooses `cash` or `kaspi_link` until the payment is confirmed.

    The status goes back to `unpaid` (a Kaspi statement does not carry over to
    cash); choosing the current method again changes nothing (`changed: false`).
    `503 kaspi_unavailable` when no Kaspi link is configured.

    Errors: `404 ride_not_found` (unknown ride or not yours); `403
    payment_action_forbidden` (not your action); `409 ride_not_completed`;
    `409 invalid_payment_transition` (`details.action`, `method`, `status`).
    """
    result = await payments.change_method(ride_id, body.method, user_id=user.id, role=user.role)
    return _respond(result, settings, user)


@router.post("/report", responses=COMMAND_ERRORS)
async def report_payment(
    ride_id: uuid.UUID,
    user: CurrentUser,
    payments: PaymentServiceDep,
    settings: PaymentSettingsDep,
    body: PaymentReportRequest | None = None,
) -> PaymentCommandResponse:
    """The passenger says "I paid" by Kaspi: `unpaid` -> `reported`, never `confirmed`.

    It is only a statement; an admin confirms after checking Kaspi. Repeating
    it changes nothing. Cash has no report.

    Errors: `404 ride_not_found` (unknown ride or not yours); `403
    payment_action_forbidden` (not your action); `409 ride_not_completed`;
    `409 invalid_payment_transition` (`details.action`, `method`, `status`).
    """
    result = await payments.report(ride_id, user_id=user.id, role=user.role)
    return _respond(result, settings, user)


@router.post("/confirm", responses=COMMAND_ERRORS)
async def confirm_payment(
    ride_id: uuid.UUID,
    user: CurrentUser,
    payments: PaymentServiceDep,
    settings: PaymentSettingsDep,
    body: PaymentConfirmRequest | None = None,
) -> PaymentCommandResponse:
    """Manual confirmation: cash by the ride's driver or an admin, Kaspi by an admin only.

    Kaspi needs `reference`, the note of the check in the Kaspi POS (`422
    confirmation_reference_required`; `422 invalid_confirmation_reference`
    for more than 200 characters or control characters). Who and when are
    stored and audited. Confirming again answers `200` with `changed: false`
    and records nothing.

    Errors: `404 ride_not_found` (unknown ride or not yours); `403
    payment_action_forbidden` (not your action); `409 ride_not_completed`;
    `409 invalid_payment_transition` (`details.action`, `method`, `status`).
    """
    reference = body.reference if body is not None else None
    result = await payments.confirm(ride_id, reference, user_id=user.id, role=user.role)
    return _respond(result, settings, user)
