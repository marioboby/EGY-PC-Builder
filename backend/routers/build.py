from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request

from models import BuildRequest, BuildResponse
from config import SCRAPERS
from llm import generate_build_with_fallback

router = APIRouter(tags=["build"])


@router.post("/build", response_model=BuildResponse)
async def build(req: BuildRequest, request: Request):
    """
    Generate a PC build recommendation based on live cached prices.
    """
    try:
        result = await generate_build_with_fallback(
            providers = request.app.state.llm_providers,
            budget    = req.budget,
            use_case  = req.use_case,
            priority  = req.priority,
            notes     = req.notes,
            scrapers  = SCRAPERS,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
