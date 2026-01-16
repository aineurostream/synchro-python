from abc import ABC, abstractmethod
from http.client import HTTPException
from typing import Any, Generic, NoReturn, TypeVar, cast

from pydantic import BaseModel

from synchroagent.database.db import DatabaseConnection

ModelT = TypeVar("ModelT", bound=BaseModel)
ModelCreateT = TypeVar("ModelCreateT", bound=BaseModel)
ModelUpdateT = TypeVar("ModelUpdateT", bound=BaseModel)


class BaseRegistry(Generic[ModelT, ModelCreateT, ModelUpdateT], ABC):
    def __init__(
        self,
        db_connection: DatabaseConnection,
        table_name: str,
        model_class: type[ModelT],
    ) -> None:
        self.db = db_connection
        self.table_name = table_name
        self.model_class = model_class

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
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self.db.execute(query, (entity_id,))
        return self._row_to_model(results[0]) if results else None

    def get_all(self) -> list[ModelT]:
        query = f"SELECT * FROM {self.table_name}"
        results = self.db.execute(query)
        return [self._row_to_model(row) for row in results]

    def create(self, entity: ModelCreateT) -> ModelT:
        data = self.model_create_to_dict(entity)

        if "id" in data:
            del data["id"]

        fields = list(data.keys())
        placeholders = ", ".join(["?"] * len(fields))

        query = """
            INSERT INTO {} ({}) VALUES ({})
        """.format(self.table_name, ", ".join(fields), placeholders)

        values = tuple(data[field] for field in fields)

        self.db.execute(query, values)
        entity_id = self.db.get_last_row_id()

        result = self.get_by_id(entity_id)
        if result is None:
            self.raise_not_found(entity_id)
        return result

    def update(self, entity_id: int, entity: ModelUpdateT) -> ModelT | None:
        if not self.exists(entity_id):
            return None

        data = self.model_update_to_dict(entity)
        if "id" in data:
            del data["id"]

        if not data:
            return self.get_by_id(entity_id)

        set_clause = ", ".join([f"{k} = ?" for k in data])

        query = f"""
            UPDATE {self.table_name} SET {set_clause} WHERE id = ?
        """

        values = (*data.values(), entity_id)

        self.db.execute(query, values)
        return self.get_by_id(entity_id)

    def delete(self, entity_id: int) -> bool:
        if not self.exists(entity_id):
            return False

        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        self.db.execute(query, (entity_id,))
        return not self.exists(entity_id)

    def exists(self, entity_id: int) -> bool:
        query = f"SELECT 1 FROM {self.table_name} WHERE id = ? LIMIT 1"
        results = self.db.execute(query, (entity_id,))
        return len(results) > 0

    def count(self) -> int:
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        results = self.db.execute(query)
        return cast(int, results[0]["count"]) if results else 0

    def filter(self, **kwargs: str | float | bool) -> list[ModelT]:
        if not kwargs:
            return self.get_all()

        conditions = " AND ".join([f"{k} = ?" for k in kwargs])
        values = tuple(kwargs.values())

        query = f"SELECT * FROM {self.table_name} WHERE {conditions}"

        results = self.db.execute(query, values)

        return [self._row_to_model(row) for row in results]

    def raise_not_found(self, entity_id: int) -> NoReturn:
        msg = f"{self.model_class.__name__} with id {entity_id} not found"
        raise HTTPException(404, msg)
