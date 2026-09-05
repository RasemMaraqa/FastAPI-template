from fastapi import APIRouter

from app.dependencies.access import CurrentUser
from app.schemas.contracts import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def read_me(user: CurrentUser):
    return user
