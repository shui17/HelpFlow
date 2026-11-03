"""统一的分页和数据库 ID 边界。"""
from typing import Annotated
from fastapi import Path, Query

MAX_PAGE = 1_000_000
MAX_ID = 9_223_372_036_854_775_807
PageNumber = Annotated[int, Query(ge=1, le=MAX_PAGE)]
PageSize = Annotated[int, Query(ge=1, le=100)]
EntityId = Annotated[int, Path(gt=0, le=MAX_ID)]
BeforeId = Annotated[int | None, Query(gt=0, le=MAX_ID)]
