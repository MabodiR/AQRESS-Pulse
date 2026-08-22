from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.devices import router as devices_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.sensor_types import router as sensor_types_router
from app.api.v1.routes.sites import router as sites_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(sites_router)
api_router.include_router(devices_router)
api_router.include_router(sensor_types_router)
