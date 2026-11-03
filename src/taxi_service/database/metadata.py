from taxi_service.database.base import Base
from taxi_service.modules.auth import models as auth_models
from taxi_service.modules.drivers import models as drivers_models
from taxi_service.modules.payments import models as payments_models
from taxi_service.modules.rides import models as rides_models
from taxi_service.modules.users import models as users_models

# Every module with ORM models must be listed here for Alembic.
MODEL_MODULES = (auth_models, drivers_models, payments_models, rides_models, users_models)

target_metadata = Base.metadata
