from typing import Any

from sqlalchemy import ColumnElement, SQLColumnExpression, String, or_
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction


class FoldText(GenericFunction[str]):
    type = String()
    name = "lower"
    inherit_cache = True


@compiles(FoldText, "sqlite")
def _sqlite_fold(element: FoldText, compiler: Any, **kw: Any) -> str:
    return f"unicode_casefold({compiler.process(element.clauses, **kw)})"


def matches_text(query: str, *columns: SQLColumnExpression[Any]) -> ColumnElement[bool]:
    needle = query.strip().casefold()
    return or_(*(FoldText(column).contains(needle, autoescape=True) for column in columns))
