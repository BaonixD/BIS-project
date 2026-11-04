from typing import Annotated

from fastapi import Depends, Request

from taxi_service.modules.geo.client import RoutingProvider


def get_routing_provider(request: Request) -> RoutingProvider:
    provider: RoutingProvider = request.app.state.routing_provider
    return provider


RoutingProviderDep = Annotated[RoutingProvider, Depends(get_routing_provider)]
