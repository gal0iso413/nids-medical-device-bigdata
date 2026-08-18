"""Request models for the fixed local Class 2 query contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ComparisonSelection(BaseModel):
    selection_type: Literal["item_group", "item_name"]
    item_group_id: str = Field(min_length=1, max_length=512)
    item_name_id: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_scope(self) -> "ComparisonSelection":
        if self.selection_type == "item_group" and self.item_name_id is not None:
            raise ValueError("item_group selection must not include item_name_id")
        if self.selection_type == "item_name" and self.item_name_id is None:
            raise ValueError("item_name selection requires item_name_id")
        return self


class ComparisonRequest(BaseModel):
    period_start: str = Field(pattern=r"^\d{6}$")
    period_end: str = Field(pattern=r"^\d{6}$")
    selections: list[ComparisonSelection] = Field(min_length=1, max_length=10)
