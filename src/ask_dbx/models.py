from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List


class Task(BaseModel):
    id: Optional[int] = Field(None, hidden=True)
    objective: str
    steps: List[str]
    documentation: Optional[str] = Field(None, hidden=True)
    state: Optional[str] = Field(None, hidden=True)

    def __repr__(self):
        return f"<Task {self.id}: {self.objective} ({self.state})>"
