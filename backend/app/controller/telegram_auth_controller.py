from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    FloodWaitError,
    AuthKeyError,
    UserDeactivatedBanError,
    AuthKeyUnregisteredError,
)
import uuid
from typing import Dict
import json
from services.auth_ctx import user_ctx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram-auth", tags=["telegram-auth"])

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
# Default to /app/sessions if not set, but tests override this to /tmp/sessions
SESSION_DIR = Path(os.getenv("SESSION_DIR", "/app/sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# In-memory store for in-progress auth flows (single-process only)
setup_sessions: Dict[str, dict] = {}

_CLIENT_KWARGS = dict(
    device_model="Aether Web Client",
    system_version="1.0",
    app_version="1.0",
    lang_code="en",
    system_lang_code="en",
)


def _make_client(session=None) -> TelegramClient:
    return TelegramClient(session or StringSession(), API_ID, API_HASH, **_CLIENT_KWARGS)


class SetupRequest(BaseModel):
    phone: str
    session_name: str = "default"


class CodeRequest(BaseModel):
    setup_id: str
    code: str


class PasswordRequest(BaseModel):
    setup_id: str
    password: str


def save_string_session(session_name: str, session_string: str, user_info: dict = None, user_id: str = None):
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"

    data = {
        "session_string": session_string,
        "user_info": user_info,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_user_id": user_id,
    }
    with open(session_file, "w") as f:
        json.dump(data, f, indent=2)


def load_string_session(session_name: str, user_id: str = None) -> tuple:
    if user_id:
        session_file = SESSION_DIR / f"user_{user_id}" / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"

    if not session_file.exists():
        return None, None

    with open(session_file, "r") as f:
        data = json.load(f)

    if user_id and data.get("owner_user_id") != user_id:
        return None, None

    return data.get("session_string"), data.get("user_info")


async def _cleanup_setup(setup_id: str):
    """Disconnect and remove a pending setup session."""
    entry = setup_sessions.pop(setup_id, None)
    if entry:
        try:
            await entry["client"].disconnect()
        except Exception:
            pass


@router.get("/")
async def root():
    return {"status": "Telegram Session Setup API (StringSession)", "ready": True}


@router.get("/debug/app-status")
async def debug_app_status():
    """
    Check whether the API credentials are banned or rate-limited by Telegram.
    Does NOT require a phone number — useful for diagnosing silent auth failures.

    Possible responses:
    - app_banned: true  → API_ID/API_HASH is banned, create new app at my.telegram.org
    - flood_wait_seconds → IP or credentials are rate-limited, wait and retry
    - connected: true, app_banned: false → credentials are fine, issue is phone-level
    """
    client = _make_client()
    try:
        await client.connect()
        # get_me() returns None when unauthenticated but raises if the app is banned
        me = await client.get_me()
        dc_id = getattr(client.session, "dc_id", None)
        return {
            "connected": True,
            "app_banned": False,
            "authenticated": me is not None,
            "api_id": API_ID,
            "dc_id": dc_id,
        }
    except (AuthKeyError, AuthKeyUnregisteredError) as e:
        return {"connected": False, "app_banned": True, "reason": str(e)}
    except UserDeactivatedBanError as e:
        return {"connected": False, "app_banned": True, "reason": f"Account/app banned: {e}"}
    except FloodWaitError as e:
        return {"connected": True, "app_banned": False, "flood_wait_seconds": e.seconds}
    except Exception as e:
        logger.exception("debug_app_status failed")
        return {"connected": False, "app_banned": None, "reason": str(e)}
    finally:
        await client.disconnect()


@router.get("/sessions")
async def list_sessions(current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    user_dir = SESSION_DIR / f"user_{user_id}"

    if not user_dir.exists():
        return {"sessions": []}

    sessions = []
    for file in user_dir.glob("*.json"):
        session_name = file.stem
        session_string, user_info = load_string_session(session_name, user_id)
        if not session_string:
            sessions.append({"name": session_name, "file": file.name, "active": False, "error": "Invalid session data"})
            continue

        client = _make_client(StringSession(session_string))
        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                sessions.append({
                    "name": session_name,
                    "file": file.name,
                    "active": True,
                    "user": {
                        "id": me.id,
                        "username": me.username,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                    },
                })
            else:
                sessions.append({"name": session_name, "file": file.name, "active": False, "user_info": user_info})
        except Exception as e:
            sessions.append({"name": session_name, "file": file.name, "active": False, "error": str(e)})
        finally:
            await client.disconnect()

    return {"sessions": sessions}


@router.post("/setup/start")
async def start_setup(request: SetupRequest, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    setup_id = str(uuid.uuid4())

    session_file = SESSION_DIR / f"user_{user_id}" / f"{request.session_name}.json"
    if session_file.exists():
        raise HTTPException(status_code=400, detail=f"Session '{request.session_name}' already exists")

    client = _make_client()
    try:
        await client.connect()
        sent_code = await client.send_code_request(request.phone)
        logger.info("Code requested for setup_id=%s type=%s", setup_id, sent_code.type)

        setup_sessions[setup_id] = {
            "client": client,
            "phone": request.phone,
            "session_name": request.session_name,
            "phone_code_hash": sent_code.phone_code_hash,
            "step": "code_requested",
            "user_id": user_id,
        }

        return {
            "setup_id": setup_id,
            "message": f"Code sent to {request.phone}",
            "session_name": request.session_name,
            "type": str(sent_code.type),  # e.g. SentCodeTypeSms, SentCodeTypeApp
        }

    except FloodWaitError as e:
        await client.disconnect()
        raise HTTPException(status_code=429, detail=f"Telegram flood wait: retry after {e.seconds}s")
    except Exception as e:
        await client.disconnect()
        logger.exception("start_setup failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/setup/verify-code")
async def verify_code(request: CodeRequest, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])

    if request.setup_id not in setup_sessions:
        raise HTTPException(status_code=404, detail="Setup session not found")

    entry = setup_sessions[request.setup_id]
    if entry.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    client = entry["client"]

    try:
        await client.sign_in(
            phone=entry["phone"],
            code=request.code,
            phone_code_hash=entry["phone_code_hash"],
        )

        me = await client.get_me()
        session_string = client.session.save()
        user_info = {"id": me.id, "username": me.username, "first_name": me.first_name, "last_name": me.last_name}
        save_string_session(entry["session_name"], session_string, user_info, user_id)

        await _cleanup_setup(request.setup_id)

        return {
            "success": True,
            "message": f"Session '{entry['session_name']}' successfully created",
            "user": user_info,
            "session_string": session_string,
        }

    except SessionPasswordNeededError:
        # Keep client alive — password step still needs it
        entry["step"] = "password_required"
        return {"success": False, "requires_password": True, "message": "2FA password required"}
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    except FloodWaitError as e:
        await _cleanup_setup(request.setup_id)
        raise HTTPException(status_code=429, detail=f"Telegram flood wait: retry after {e.seconds}s")
    except Exception as e:
        await _cleanup_setup(request.setup_id)
        logger.exception("verify_code failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/setup/verify-password")
async def verify_password(request: PasswordRequest, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])

    if request.setup_id not in setup_sessions:
        raise HTTPException(status_code=404, detail="Setup session not found")

    entry = setup_sessions[request.setup_id]
    if entry.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    client = entry["client"]

    try:
        await client.sign_in(password=request.password)

        me = await client.get_me()
        session_string = client.session.save()
        user_info = {"id": me.id, "username": me.username, "first_name": me.first_name, "last_name": me.last_name}
        save_string_session(entry["session_name"], session_string, user_info, user_id)

        await _cleanup_setup(request.setup_id)

        return {
            "success": True,
            "message": f"Session '{entry['session_name']}' successfully created",
            "user": user_info,
            "session_string": session_string,
        }

    except FloodWaitError as e:
        await _cleanup_setup(request.setup_id)
        raise HTTPException(status_code=429, detail=f"Telegram flood wait: retry after {e.seconds}s")
    except Exception as e:
        await _cleanup_setup(request.setup_id)
        logger.exception("verify_password failed")
        raise HTTPException(status_code=400, detail="Invalid password")


@router.post("/setup/cancel/{setup_id}")
async def cancel_setup(setup_id: str, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])

    entry = setup_sessions.get(setup_id)
    if entry:
        if entry.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        await _cleanup_setup(setup_id)

    return {"message": "Setup cancelled"}


@router.get("/sessions/{session_name}/string")
async def get_session_string(session_name: str, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    session_string, user_info = load_string_session(session_name, user_id)

    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session_name": session_name, "session_string": session_string, "user_info": user_info}


@router.delete("/sessions/{session_name}")
async def delete_session(session_name: str, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    session_file = SESSION_DIR / f"user_{user_id}" / f"{session_name}.json"

    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_file.unlink()
    return {"message": f"Session '{session_name}' deleted"}


@router.post("/sessions/{session_name}/test")
async def test_session(session_name: str, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    session_string, _ = load_string_session(session_name, user_id)

    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")

    client = _make_client(StringSession(session_string))
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "valid": True,
                "user": {"id": me.id, "username": me.username, "first_name": me.first_name, "last_name": me.last_name},
            }
        return {"valid": False, "reason": "Not authorized"}
    except Exception as e:
        return {"valid": False, "reason": str(e)}
    finally:
        await client.disconnect()


@router.post("/sessions/from-string")
async def create_session_from_string(session_string: str, session_name: str, current_user=Depends(user_ctx)):
    user_id = str(current_user["id"])
    session_file = SESSION_DIR / f"user_{user_id}" / f"{session_name}.json"

    if session_file.exists():
        raise HTTPException(status_code=400, detail=f"Session '{session_name}' already exists")

    client = _make_client(StringSession(session_string))
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=400, detail="Session string is not authorized")

        me = await client.get_me()
        user_info = {"id": me.id, "username": me.username, "first_name": me.first_name, "last_name": me.last_name}
        save_string_session(session_name, session_string, user_info, user_id)

        return {"success": True, "message": f"Session '{session_name}' created from string", "user": user_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid session string: {e}")
    finally:
        await client.disconnect()
