import json
from typing import Any
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.mqtt_auth_service import MqttAuthService

app = FastAPI(title="AQRESS Pulse MQTT Internal Service", docs_url=None, redoc_url=None, openapi_url=None)


async def _payload(request: Request) -> dict[str, Any]:
    raw = await request.body()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = parse_qs(raw.decode("utf-8", errors="replace"))
        return {key: values[0] for key, values in parsed.items() if values}


@app.get("/internal/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/internal/mqtt/authenticate")
async def authenticate(request: Request, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    payload = await _payload(request)
    return await MqttAuthService(session).authenticate(
        str(payload.get("username", "")), str(payload.get("password", ""))
    )


@app.post("/internal/mqtt/authorize")
async def authorize(request: Request, session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    payload = await _payload(request)
    return await MqttAuthService(session).authorize(
        str(payload.get("username", "")),
        str(payload.get("action", "")),
        str(payload.get("topic", "")),
    )
