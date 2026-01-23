from fastapi import APIRouter

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/latest")
async def get_latest():
    # todo: implement this
    return {}
