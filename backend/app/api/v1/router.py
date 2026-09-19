from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_staff,
    auth,
    health,
    inventory,
    masters,
    members,
    pos,
    products,
    skus,
    transactions,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(pos.router, tags=["pos"])
api_router.include_router(admin_staff.router, tags=["admin"])
api_router.include_router(masters.router, tags=["masters"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(members.router, tags=["members"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(skus.router, tags=["skus"])
api_router.include_router(transactions.router, tags=["transactions"])
