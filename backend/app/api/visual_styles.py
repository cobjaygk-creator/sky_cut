from fastapi import APIRouter

from app.services.visual_style_catalog import list_visual_styles

router = APIRouter(tags=["visual-styles"])


@router.get("/visual-styles")
def get_visual_styles() -> list[dict]:
    return list_visual_styles()
