from typing import Annotated

from fastapi import Depends, Request

from taxi_service.modules.payments.config import PaymentSettings


def get_payment_settings(request: Request) -> PaymentSettings:
    settings: PaymentSettings = request.app.state.payment_settings
    return settings


PaymentSettingsDep = Annotated[PaymentSettings, Depends(get_payment_settings)]
