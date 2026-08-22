import math
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int

    @classmethod
    def create(cls, *, page: int, page_size: int, total_items: int) -> "Pagination":
        return cls(page=page, page_size=page_size, total_items=total_items, total_pages=math.ceil(total_items / page_size) if total_items else 0)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: Pagination
