"""Translate native binding errors without hiding Python programming failures."""

from collections.abc import Sequence

from adapters.database.d1.bindings import (
    D1BindingError,
    D1Database,
    D1PreparedStatement,
    D1Value,
)


class NativeStatement:
    def __init__(
        self, statement: D1PreparedStatement, errors: tuple[type[Exception], ...]
    ) -> None:
        self.statement = statement
        self.errors = errors

    def bind(self, *values: D1Value) -> "NativeStatement":
        try:
            return NativeStatement(self.statement.bind(*values), self.errors)
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error

    async def first(self) -> object:
        try:
            return await self.statement.first()
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error

    async def all(self) -> object:
        try:
            return await self.statement.all()
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error

    async def run(self) -> object:
        try:
            return await self.statement.run()
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error


class NativeDatabase:
    def __init__(
        self, database: D1Database, errors: tuple[type[Exception], ...]
    ) -> None:
        self.database = database
        self.errors = errors

    def prepare(self, sql: str) -> NativeStatement:
        try:
            return NativeStatement(self.database.prepare(sql), self.errors)
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        native: list[D1PreparedStatement] = []
        for statement in statements:
            if not isinstance(statement, NativeStatement):
                raise TypeError("D1 statement belongs to another binding boundary")
            native.append(statement.statement)
        try:
            return await self.database.batch(native)
        except self.errors as error:
            raise D1BindingError("D1 binding unavailable") from error
