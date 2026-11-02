from typing import Annotated

from fastapi import Depends

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.rides.dispatch import DispatchService
from taxi_service.modules.rides.policy import DispatchPolicyDep


def get_dispatch_service(
    session: SessionDep, clock: ClockDep, policy: DispatchPolicyDep
) -> DispatchService:
    return DispatchService(session, clock, policy)


DispatchServiceDep = Annotated[DispatchService, Depends(get_dispatch_service)]
