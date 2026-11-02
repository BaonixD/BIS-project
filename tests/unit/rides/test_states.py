import pytest

from taxi_service.modules.rides.states import (
    ACTIVE_RIDE_STATUSES,
    PRE_START_RIDE_STATUSES,
    TERMINAL_OFFER_STATUSES,
    TERMINAL_RIDE_STATUSES,
    OfferStatus,
    RideStatus,
)


def test_ride_status_values_match_the_api_contract() -> None:
    assert [status.value for status in RideStatus] == [
        "searching",
        "assigned",
        "arrived",
        "in_progress",
        "completed",
        "cancelled",
        "no_driver",
    ]


def test_active_ride_statuses() -> None:
    assert {
        RideStatus.SEARCHING,
        RideStatus.ASSIGNED,
        RideStatus.ARRIVED,
        RideStatus.IN_PROGRESS,
    } == ACTIVE_RIDE_STATUSES


def test_terminal_ride_statuses() -> None:
    assert {
        RideStatus.COMPLETED,
        RideStatus.CANCELLED,
        RideStatus.NO_DRIVER,
    } == TERMINAL_RIDE_STATUSES


def test_every_ride_status_is_either_active_or_terminal() -> None:
    assert ACTIVE_RIDE_STATUSES.isdisjoint(TERMINAL_RIDE_STATUSES)
    assert set(RideStatus) == ACTIVE_RIDE_STATUSES | TERMINAL_RIDE_STATUSES


def test_pre_start_statuses_are_active_and_exclude_in_progress() -> None:
    assert {
        RideStatus.SEARCHING,
        RideStatus.ASSIGNED,
        RideStatus.ARRIVED,
    } == PRE_START_RIDE_STATUSES
    assert PRE_START_RIDE_STATUSES < ACTIVE_RIDE_STATUSES


def test_offer_status_values_match_the_api_contract() -> None:
    assert [status.value for status in OfferStatus] == [
        "pending",
        "accepted",
        "rejected",
        "expired",
        "revoked",
    ]


@pytest.mark.parametrize("status", [s for s in OfferStatus if s is not OfferStatus.PENDING])
def test_every_decided_offer_is_terminal(status: OfferStatus) -> None:
    assert status in TERMINAL_OFFER_STATUSES


def test_pending_offer_is_not_terminal() -> None:
    assert OfferStatus.PENDING not in TERMINAL_OFFER_STATUSES
