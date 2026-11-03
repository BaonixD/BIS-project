from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from taxi_service.database.base import Base


def test_constraints_and_indexes_get_conventional_names() -> None:
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    Table("rider", metadata, Column("id", Integer, primary_key=True))
    ride = Table(
        "ride",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("rider_id", ForeignKey("rider.id"), nullable=False),
        Column("code", String(8), unique=True),
        Column("price", Integer, index=True),
        CheckConstraint("price >= 0", name="price_non_negative"),
    )

    ddl = str(CreateTable(ride).compile(dialect=sqlite.dialect()))
    [index] = ride.indexes
    index_ddl = str(CreateIndex(index).compile(dialect=sqlite.dialect()))

    assert "CONSTRAINT pk_ride PRIMARY KEY" in ddl
    assert "CONSTRAINT fk_ride_rider_id_rider FOREIGN KEY" in ddl
    assert "CONSTRAINT uq_ride_code UNIQUE" in ddl
    assert "CONSTRAINT ck_ride_price_non_negative CHECK" in ddl
    assert index_ddl.startswith("CREATE INDEX ix_ride_price ")
