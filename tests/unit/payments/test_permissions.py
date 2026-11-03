import pytest

from taxi_service.core.errors import AppError
from taxi_service.modules.payments.exceptions import (
    ConfirmationReferenceRequiredError,
    InvalidConfirmationReferenceError,
    PaymentActionForbiddenError,
    RideNotCompletedError,
)
from taxi_service.modules.payments.permissions import (
    MAX_CONFIRMATION_REFERENCE_LENGTH,
    PaymentActor,
    authorize_payment_action,
    normalize_confirmation_reference,
)
from taxi_service.modules.payments.rules import PaymentAction, PaymentMethod
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.users.models import UserRole

CASH = PaymentMethod.CASH
KASPI = PaymentMethod.KASPI_LINK
REPORT = PaymentAction.REPORT
CONFIRM = PaymentAction.CONFIRM
CHANGE = PaymentAction.CHANGE_METHOD

# (role, is_ride_passenger, is_assigned_driver)
ACTORS: dict[str, tuple[UserRole, bool, bool]] = {
    "ride_passenger": (UserRole.PASSENGER, True, False),
    "other_passenger": (UserRole.PASSENGER, False, False),
    "assigned_driver": (UserRole.DRIVER, False, True),
    "other_driver": (UserRole.DRIVER, False, False),
    "admin": (UserRole.ADMIN, False, False),
}
STRANGERS = {"other_passenger", "other_driver"}
ALLOWED = {
    ("ride_passenger", REPORT, CASH),
    ("ride_passenger", REPORT, KASPI),
    ("ride_passenger", CHANGE, CASH),
    ("ride_passenger", CHANGE, KASPI),
    ("assigned_driver", CONFIRM, CASH),
    ("admin", CONFIRM, CASH),
    ("admin", CONFIRM, KASPI),
}


def actor(name: str, *, ride_completed: bool) -> PaymentActor:
    role, is_passenger, is_driver = ACTORS[name]
    return PaymentActor(
        role=role,
        is_ride_passenger=is_passenger,
        is_assigned_driver=is_driver,
        ride_completed=ride_completed,
    )


def expected_error(
    name: str, action: PaymentAction, method: PaymentMethod, ride_completed: bool
) -> type[AppError] | None:
    if name in STRANGERS:
        return RideNotFoundError
    if (name, action, method) not in ALLOWED:
        return PaymentActionForbiddenError
    if not ride_completed:
        return RideNotCompletedError
    return None


@pytest.mark.parametrize("ride_completed", [True, False], ids=["completed", "not_completed"])
@pytest.mark.parametrize("method", list(PaymentMethod))
@pytest.mark.parametrize("action", list(PaymentAction))
@pytest.mark.parametrize("name", list(ACTORS))
def test_permission_matrix(
    name: str, action: PaymentAction, method: PaymentMethod, ride_completed: bool
) -> None:
    caller = actor(name, ride_completed=ride_completed)
    error = expected_error(name, action, method, ride_completed)

    if error is None:
        authorize_payment_action(action, caller, method=method)
    else:
        with pytest.raises(error):
            authorize_payment_action(action, caller, method=method)


def test_stranger_sees_ride_not_found_like_other_ride_rules() -> None:
    with pytest.raises(RideNotFoundError) as caught:
        authorize_payment_action(CONFIRM, actor("other_driver", ride_completed=True), method=CASH)

    assert caught.value.status_code == 404
    assert caught.value.code == "ride_not_found"


def test_participant_without_right_gets_forbidden_with_action() -> None:
    with pytest.raises(PaymentActionForbiddenError) as caught:
        authorize_payment_action(
            CONFIRM, actor("assigned_driver", ride_completed=True), method=KASPI
        )

    assert caught.value.status_code == 403
    assert caught.value.code == "payment_action_forbidden"
    assert caught.value.details == {"action": "confirm"}


def test_cash_confirmation_before_completion_is_a_conflict() -> None:
    with pytest.raises(RideNotCompletedError) as caught:
        authorize_payment_action(
            CONFIRM, actor("assigned_driver", ride_completed=False), method=CASH
        )

    assert caught.value.status_code == 409
    assert caught.value.code == "ride_not_completed"


@pytest.mark.parametrize(
    "caller",
    [
        PaymentActor(
            role=UserRole.DRIVER,
            is_ride_passenger=True,
            is_assigned_driver=False,
            ride_completed=True,
        ),
        PaymentActor(
            role=UserRole.ADMIN,
            is_ride_passenger=True,
            is_assigned_driver=False,
            ride_completed=True,
        ),
    ],
    ids=["driver_flagged_passenger", "admin_flagged_passenger"],
)
def test_passenger_flag_without_passenger_role_grants_nothing(caller: PaymentActor) -> None:
    with pytest.raises((RideNotFoundError, PaymentActionForbiddenError)):
        authorize_payment_action(REPORT, caller, method=KASPI)


def test_passenger_flagged_as_driver_cannot_confirm_cash() -> None:
    caller = PaymentActor(
        role=UserRole.PASSENGER,
        is_ride_passenger=True,
        is_assigned_driver=True,
        ride_completed=True,
    )

    with pytest.raises(PaymentActionForbiddenError):
        authorize_payment_action(CONFIRM, caller, method=CASH)


# --- confirmation note / reconciliation reference ----------------------------------------


@pytest.mark.parametrize("raw", [None, "", "   ", "\t \n"])
def test_kaspi_confirmation_requires_reference(raw: str | None) -> None:
    with pytest.raises(ConfirmationReferenceRequiredError) as caught:
        normalize_confirmation_reference(KASPI, raw)

    assert caught.value.status_code == 422
    assert caught.value.code == "confirmation_reference_required"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("POS-2026-11-03 #145", "POS-2026-11-03 #145"),
        ("  сверено в Kaspi POS  ", "сверено в Kaspi POS"),
        ("x" * MAX_CONFIRMATION_REFERENCE_LENGTH, "x" * MAX_CONFIRMATION_REFERENCE_LENGTH),
    ],
)
def test_kaspi_reference_is_trimmed_and_kept(raw: str, expected: str) -> None:
    assert normalize_confirmation_reference(KASPI, raw) == expected


@pytest.mark.parametrize("method", list(PaymentMethod))
@pytest.mark.parametrize(
    "raw",
    [
        "x" * (MAX_CONFIRMATION_REFERENCE_LENGTH + 1),
        "line one\nline two",
        "tab\tinside",
        "nul\x00byte",
        "escape\x1b[31m",
        "bidi \u202e override",
        "zero\u200bwidth",
        "line\u2028separator",
    ],
    ids=["too_long", "newline", "tab", "nul", "ansi", "bidi", "zero_width", "line_sep"],
)
def test_unsafe_or_long_reference_is_rejected(method: PaymentMethod, raw: str) -> None:
    with pytest.raises(InvalidConfirmationReferenceError) as caught:
        normalize_confirmation_reference(method, raw)

    assert caught.value.status_code == 422
    assert caught.value.details == {"max_length": MAX_CONFIRMATION_REFERENCE_LENGTH}
    assert raw not in caught.value.message


@pytest.mark.parametrize(("raw", "expected"), [(None, None), ("", None), ("  ", None)])
def test_cash_note_is_optional(raw: str | None, expected: str | None) -> None:
    assert normalize_confirmation_reference(CASH, raw) == expected


def test_cash_note_is_trimmed_when_given() -> None:
    assert normalize_confirmation_reference(CASH, " received 1500 ") == "received 1500"
