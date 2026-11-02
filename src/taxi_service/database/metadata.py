"""Complete ORM metadata for Alembic, assembled without starting the application.

Every module that defines ORM models must be imported here; Alembic compares
the database only with tables registered in ``target_metadata``. Importing
this module never connects to the database or creates schema.
"""

from taxi_service.database.base import Base

# Model modules are added as the tasks introduce them, for example:
# import taxi_service.modules.users.models

target_metadata = Base.metadata
