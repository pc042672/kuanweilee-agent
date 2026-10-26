"""
FastAPI router for brand analysis endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import UserContext, get_current_user
from backend.config import get_config_manager
from backend.services import credentials as credentials_service

router = APIRouter(prefix="/api/brand", tags=["brand"], dependencies=[Depends(get_current_user)])


# ==================== REQUEST MODELS ====================

class BrandAnalyzeRequest(BaseModel):
    """Request model for brand analysis."""
    url: str
    save_to_ontology: bool = False


# ==================== BRAND ANALYZER ====================

@router.post("/analyze")
async def analyze_brand(
    request: BrandAnalyzeRequest, user: UserContext = Depends(get_current_user)
):
    """
    Analyze a brand website to extract brand identity information.

    Uses a headless browser to crawl the website and Gemini AI to analyze:
    - Brand name (English/Chinese)
    - Brand type (industry, niche, target audience)
    - Description (core value, key products, summary)
    - Visual style (colors, font style, overall vibe)
    - Marketing (hot keywords, hot products, promotion slogans)

    If save_to_ontology=true, the brand context will be saved as an entity.

    Returns 409 when the 'gemini' integration is not configured for the site.
    """
    creds = credentials_service.require_credentials(user.site_id, "gemini")
    try:
        from backend.tools.brand_analyzer import analyze_brand_async

        result = await analyze_brand_async(request.url, api_key=creds.get("api_key"))

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

        if request.save_to_ontology:
            from backend.services.brand_service import apply_ontology_save
            result = apply_ontology_save(result, get_config_manager())

        return result

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Brand analyzer dependencies not installed: {e}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
