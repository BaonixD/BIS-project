"""Complete ORM metadata for Alembic, assembled without starting the application.

Every module that defines ORM models must be imported here; Alembic compares
the database only with tables registered in ``target_metadata``. Importing
this module never connects to the database or creates schema.
"""

import taxi_service.modules.users.models  # noqa: F401  (registers the tables)
from taxi_service.database.base import Base

target_metadata = Base.metadata
