"""Raising a searching ride to a higher tariff for the difference in its quote's prices.

Only while searching: Kaspi is charged at assignment, so the payment's amount is simply
changed. The search restarts among cars of the new class with a fresh time budget.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.bonuses import records as bonus_records
from taxi_service.modules.payments import records as payment_records
from taxi_service.modules.rides import dispatch
from taxi_service.modules.rides.exceptions import (
    RideNotFoundError,
    RideUpgradeUnavailableError,
    TariffNotHigherError,
)
from taxi_service.modules.rides.models import Ride, RideQuote
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.schemas import RideUpgradeOptions, RideUpgradeRequest, UpgradeOption
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.tariffs import TARIFFS, Tariff
from taxi_service.modules.rides.transitions import lock_ride
from taxi_service.modules.users.service import require_account_access


async def upgrade_options(
    db: AsyncSession, ride_id: uuid.UUID, passenger_id: uuid.UUID
) -> RideUpgradeOptions:
    async with read_transaction(db):
        ride = await db.get(Ride, ride_id)
        if ride is None or ride.passenger_id != passenger_id:
            raise RideNotFoundError
        quote = await db.get(RideQuote, ride.quote_id)
        balance = await bonus_records.balance(db, passenger_id)
    options: list[UpgradeOption] = []
    if ride.status is RideStatus.SEARCHING and quote is not None:
        for tariff in _above(ride.tariff):
            amount = quote.amount_for(tariff)
            room = bonus_records.bonus_limit(amount) - ride.bonus_kzt
            options.append(
                UpgradeOption(
                    tariff=tariff,
                    amount_kzt=amount,
                    surcharge_kzt=amount - ride.amount_kzt,
                    bonus_kzt=max(0, min(room, balance)),
                )
            )
    return RideUpgradeOptions(
        tariff=ride.tariff,
        amount_kzt=ride.amount_kzt,
        bonus_kzt=ride.bonus_kzt,
        bonus_balance_kzt=balance,
        options=options,
    )


async def upgrade_ride(
    db: AsyncSession,
    ride_id: uuid.UUID,
    passenger_id: uuid.UUID,
    request: RideUpgradeRequest,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> Ride:
    """A repeat for the ride's current tariff returns it unchanged."""
    async with db.begin():
        ride = await lock_ride(db, ride_id)
        if ride is None or ride.passenger_id != passenger_id:
            raise RideNotFoundError
        if ride.tariff is request.tariff:
            return ride
        if ride.status is not RideStatus.SEARCHING:
            raise RideUpgradeUnavailableError(current_status=ride.status.value)
        if request.tariff not in _above(ride.tariff):
            raise TariffNotHigherError(current_tariff=ride.tariff.value)
        await require_account_access(db, passenger_id)
        quote = await db.get(RideQuote, ride.quote_id)
        if quote is None:
            raise RideNotFoundError
        now = clock.now()
        ride.tariff = request.tariff
        ride.amount_kzt = quote.amount_for(request.tariff)
        ride.updated_at = now
        if request.use_bonus:
            await bonus_records.spend_on(db, ride, now)
        payment = await payment_records.lock_payment(db, ride.id)
        if payment is not None:
            payment.amount_kzt = ride.amount_kzt - ride.bonus_kzt
            payment.updated_at = now
        await dispatch.revoke_pending_offers(db, ride.id, now)
        dispatch.restart_search(ride, now, policy)
        await db.flush()
    return await dispatch.start_search(db, ride_id, clock=clock, policy=policy)


def _above(tariff: Tariff) -> list[Tariff]:
    return list(TARIFFS[TARIFFS.index(tariff) + 1 :])
