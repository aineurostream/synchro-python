import re
from abc import ABC, abstractmethod
from typing import Any, Generic, NoReturn, TypeVar, cast

from fastapi import HTTPException
from pydantic import BaseModel

from synchroagent.database.db import DatabaseConnection

ModelT = TypeVar("ModelT", bound=BaseModel)
ModelCreateT = TypeVar("ModelCreateT", bound=BaseModel)
ModelUpdateT = TypeVar("ModelUpdateT", bound=BaseModel)


class BaseRegistry(ABC, Generic[ModelT, ModelCreateT, ModelUpdateT]):
    def __init__(
        self,
        db_connection: DatabaseConnection,
        table_name: str,
        model_class: type[ModelT],
    ) -> None:
        self.db = db_connection
        self.table_name = self._validate_identifier(table_name, kind="table name")
        self.model_class = model_class

    @staticmethod
    def _validate_identifier(identifier: str, *, kind: str = "identifier") -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            msg = f"Invalid SQL {kind}: {identifier}"
            raise ValueError(msg)
        return identifier

    @abstractmethod
    def _row_to_model(self, row: dict[str, Any]) -> ModelT:
        pass

    @abstractmethod
    def model_to_dict(self, model: ModelT) -> dict[str, Any]:
        pass

    @abstractmethod
    def model_create_to_dict(self, model: ModelCreateT) -> dict[str, Any]:
        pass

    @abstractmethod
    def model_update_to_dict(self, model: ModelUpdateT) -> dict[str, Any]:
        pass

    def get_by_id(self, entity_id: int) -> ModelT | None:
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"  # noqa: S608
        results = self.db.execute(query, (entity_id,))
        return self._row_to_model(results[0]) if results else None

    def get_all(self) -> list[ModelT]:
        query = f"SELECT * FROM {self.table_name}"  # noqa: S608
        results = self.db.execute(query)
        return [self._row_to_model(row) for row in results]

    def create(self, entity: ModelCreateT) -> ModelT:
        data = self.model_create_to_dict(entity)

        if "id" in data:
            del data["id"]

        fields = [
            self._validate_identifier(field, kind="column name") for field in data
        ]
        placeholders = ", ".join(["?"] * len(fields))

        query = """
            INSERT INTO {} ({}) VALUES ({})
        """.format(self.table_name, ", ".join(fields), placeholders)  # noqa: S608

        values = tuple(data[field] for field in fields)

        insert_result = self.db.execute(query, values)
        entity_id = (
            insert_result[0]["last_insert_rowid"]
            if insert_result
            else self.db.get_last_row_id()
        )

        created = self.get_by_id(entity_id)
        if created is None:
            self.raise_not_found(entity_id)
        return created

    def update(self, entity_id: int, entity: ModelUpdateT) -> ModelT | None:
        if not self.exists(entity_id):
            return None

        data = self.model_update_to_dict(entity)
        if "id" in data:
            del data["id"]

        if not data:
            return self.get_by_id(entity_id)

        columns = [self._validate_identifier(key, kind="column name") for key in data]
        set_clause = ", ".join([f"{column} = ?" for column in columns])

        query = f"""
            UPDATE {self.table_name} SET {set_clause} WHERE id = ?
        """  # noqa: S608

        values = (*data.values(), entity_id)

        self.db.execute(query, values)
        return self.get_by_id(entity_id)

    def delete(self, entity_id: int) -> bool:
        if not self.exists(entity_id):
            return False

        query = f"DELETE FROM {self.table_name} WHERE id = ?"  # noqa: S608
        self.db.execute(query, (entity_id,))
        return not self.exists(entity_id)

    def exists(self, entity_id: int) -> bool:
        query = f"SELECT 1 FROM {self.table_name} WHERE id = ? LIMIT 1"  # noqa: S608
        results = self.db.execute(query, (entity_id,))
        return len(results) > 0

    def count(self) -> int:
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"  # noqa: S608
        results = self.db.execute(query)
        return cast("int", results[0]["count"]) if results else 0

    def filter(self, **kwargs: str | float | bool) -> list[ModelT]:
        if not kwargs:
            return self.get_all()

        columns = [self._validate_identifier(key, kind="column name") for key in kwargs]
        conditions = " AND ".join([f"{column} = ?" for column in columns])
        values = tuple(kwargs.values())

        query = f"SELECT * FROM {self.table_name} WHERE {conditions}"  # noqa: S608

        results = self.db.execute(query, values)

        return [self._row_to_model(row) for row in results]

    def raise_not_found(self, entity_id: int) -> NoReturn:
        msg = f"{self.model_class.__name__} with id {entity_id} not found"
        raise HTTPException(404, msg)
