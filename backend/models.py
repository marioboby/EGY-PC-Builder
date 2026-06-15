# models.py
from pydantic import BaseModel, Field
from typing import Literal

class BuildRequest(BaseModel):
    budget:   int   = Field(..., gt=0, description="Budget in EGP")
    use_case: str   = Field(..., description="e.g. gaming-1080p, content-creation")
    priority: str   = Field(..., description="e.g. value, performance, future-proof")
    notes:    str   = Field("", description="Any extra preferences")

class Product(BaseModel):
    category:        str
    name:            str
    price_egp:       int
    notes:           str
    egprices_search: str
    store:           str | None = None

class BuildResponse(BaseModel):
    summary:           str
    feasibility:       Literal["feasible", "tight", "infeasible"]
    feasibility_note:  str
    total_estimated:   int
    parts:             list[Product]
    alternatives:      list[dict]
    tips:              list[str]
    upgrade_path:      str