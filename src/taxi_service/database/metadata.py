"""Complete ORM metadata for Alembic, assembled without starting the application.

Every module that defines ORM models must be imported here; Alembic compares
the database only with tables registered in ``target_metadata``. Importing
this module never connects to the database or creates schema.
"""

from taxi_service.database.base import Base
from taxi_service.modules.auth import models as auth_models
from taxi_service.modules.users import models as users_models

# Imported for their side effect: each model module registers its tables.
MODEL_MODULES = (auth_models, users_models)

target_metadata = Base.metadata
