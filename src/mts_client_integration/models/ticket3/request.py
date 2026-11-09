"""Ticket 3.0 request envelope."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from ._generated import CorrelationId, Operation, OperatorId, Timestamp
from .content import ReqContent
from .operations import OPERATION_TO_CONTENT_TYPE


class Request(BaseModel):
    """Ticket 3.0 request envelope."""

    model_config = ConfigDict(extra="forbid")

    operatorId: OperatorId
    content: ReqContent
    correlationId: CorrelationId
    timestampUtc: Timestamp
    operation: Operation
    version: Literal["3.0"]

    @model_validator(mode="after")
    def operation_matches_content(self) -> Self:
        expected = OPERATION_TO_CONTENT_TYPE[self.operation]
        actual = self.content.type
        if actual != expected:
            msg = (
                f"operation {self.operation.value!r} requires "
                f"content.type {expected!r}, got {actual!r}"
            )
            raise ValueError(msg)
        return self
