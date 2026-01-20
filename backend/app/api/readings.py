from fastapi import APIRouter

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/latest")
async def get_latest():
    """Get latest sensor readings"""
    return {}
