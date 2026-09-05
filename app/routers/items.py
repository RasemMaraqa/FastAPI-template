from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.dependencies.access import CurrentUser, DbSession
from app.models import Item
from app.schemas.contracts import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter(prefix="/items", tags=["Example items"])


def owned_item(db, item_id, user_id):
    # Filter by owner in SQL; knowing another user's ID must not grant access.
    item = db.scalar(select(Item).where(Item.id == item_id, Item.owner_id == user_id))
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


@router.post("", response_model=ItemResponse, status_code=201)
def create_item(body: ItemCreate, db: DbSession, user: CurrentUser):
    item = Item(**body.model_dump(), owner_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[ItemResponse])
def list_items(
    db: DbSession,
    user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return db.scalars(
        select(Item).where(Item.owner_id == user.id).order_by(Item.id).offset(offset).limit(limit)
    ).all()


@router.get("/{item_id}", response_model=ItemResponse)
def read_item(item_id: int, db: DbSession, user: CurrentUser):
    return owned_item(db, item_id, user.id)


@router.patch("/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, body: ItemUpdate, db: DbSession, user: CurrentUser):
    item = owned_item(db, item_id, user.id)
    # exclude_unset distinguishes omitted fields from an explicit description=null.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: DbSession, user: CurrentUser):
    db.delete(owned_item(db, item_id, user.id))
    db.commit()
    return Response(status_code=204)
