from fastapi import APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import uuid
from typing import Dict
import asyncio
import json
from services.auth_ctx import user_ctx  # Ersetze mit deiner Auth-Implementierung

router = APIRouter(prefix="/telegram-auth", tags=["telegram-auth"])

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_DIR = Path("/app/sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Temporäre Sessions für Setup-Prozess
setup_sessions: Dict[str, dict] = {}

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
    """Speichere StringSession in JSON-Datei"""
    # User-spezifischer Ordner
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"
    
    data = {
        "session_string": session_string,
        "user_info": user_info,
        "created_at": asyncio.get_event_loop().time(),
        "owner_user_id": user_id  # Hinzugefügt für Sicherheit
    }
    with open(session_file, 'w') as f:
        json.dump(data, f, indent=2)

def load_string_session(session_name: str, user_id: str = None) -> tuple:
    """Lade StringSession aus JSON-Datei"""
    # User-spezifischer Pfad
    if user_id:
        user_dir = SESSION_DIR / f"user_{user_id}"
        session_file = user_dir / f"{session_name}.json"
    else:
        session_file = SESSION_DIR / f"{session_name}.json"
    
    if not session_file.exists():
        return None, None
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    # Sicherheitsprüfung wenn user_id gegeben
    if user_id and data.get("owner_user_id") != user_id:
        return None, None
    
    return data.get("session_string"), data.get("user_info")

@router.get("/")
async def root():
    return {"status": "Telegram Session Setup API (StringSession)", "ready": True}

@router.get("/sessions")
async def list_sessions(current_user = Depends(user_ctx)):
    """Liste alle verfügbaren Session-Dateien"""
    user_id = str(current_user["id"])  # Nur eigene Sessions
    user_dir = SESSION_DIR / f"user_{user_id}"
    
    if not user_dir.exists():
        return {"sessions": []}
    
    sessions = []
    for file in user_dir.glob("*.json"):
        session_name = file.stem
        try:
            session_string, user_info = load_string_session(session_name, user_id)
            if not session_string:
                sessions.append({
                    "name": session_name,
                    "file": file.name,
                    "active": False,
                    "error": "Invalid session data"
                })
                continue
            
            # Test session
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                # Aktuelle Benutzerinformationen abrufen
                me = await client.get_me()
                sessions.append({
                    "name": session_name,
                    "file": file.name,
                    "active": True,
                    "user": {
                        "id": me.id,
                        "username": me.username,
                        "first_name": me.first_name,
                        "last_name": me.last_name
                    }
                })
            else:
                sessions.append({
                    "name": session_name,
                    "file": file.name,
                    "active": False,
                    "user_info": user_info  # Gespeicherte Info anzeigen
                })
            
            await client.disconnect()
            
        except Exception as e:
            sessions.append({
                "name": session_name,
                "file": file.name,
                "active": False,
                "error": str(e)
            })
    
    return {"sessions": sessions}

@router.post("/setup/start")
async def start_setup(request: SetupRequest, current_user = Depends(user_ctx)):
    """Starte Session-Setup für eine Telefonnummer"""
    user_id = str(current_user["id"])
    setup_id = str(uuid.uuid4())

    user_dir = SESSION_DIR / f"user_{user_id}"
    session_file = user_dir / f"{request.session_name}.json"
    if session_file.exists():
        raise HTTPException(
            status_code=400, 
            detail=f"Session '{request.session_name}' already exists"
        )
    
    client = None
    try:
        # Client mit leerer StringSession erstellen
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        # Code anfordern
        sent_code = await client.send_code_request(request.phone)
        
        # Setup-Session speichern
        setup_sessions[setup_id] = {
            "client": client,
            "phone": request.phone,
            "session_name": request.session_name,
            "phone_code_hash": sent_code.phone_code_hash,
            "step": "code_requested",
            "user_id": user_id
        }
        
        return {
            "setup_id": setup_id,
            "message": f"2FA code sent to {request.phone}",
            "session_name": request.session_name
        }
        
    except Exception as e:
        if client:
            await client.disconnect()
        if setup_id in setup_sessions:
            del setup_sessions[setup_id]
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/setup/verify-code")
async def verify_code(request: CodeRequest, current_user = Depends(user_ctx)):
    """Verifiziere SMS-Code"""
    user_id = str(current_user["id"])
    
    if request.setup_id not in setup_sessions:
        raise HTTPException(status_code=404, detail="Setup session not found")
    
    session = setup_sessions[request.setup_id]
    
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    client = session["client"]
    
    try:
        await client.sign_in(
            phone=session["phone"],
            code=request.code,
            phone_code_hash=session["phone_code_hash"]
        )
        
        # Benutzerinformationen abrufen
        me = await client.get_me()
        
        # StringSession extrahieren
        session_string = client.session.save()
        
        # Session speichern
        user_info = {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name
        }
        save_string_session(session["session_name"], session_string, user_info, user_id)
        
        # Client disconnecten
        await client.disconnect()
        
        # Setup-Session entfernen
        del setup_sessions[request.setup_id]
        
        return {
            "success": True,
            "message": f"Session '{session['session_name']}' successfully created",
            "user": user_info,
            "session_string": session_string  # Optional: für direkten Zugriff
        }
        
    except SessionPasswordNeededError:
        session["step"] = "password_required"
        return {
            "success": False,
            "requires_password": True,
            "message": "Two-factor authentication required"
        }
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    except Exception as e:
        await client.disconnect()
        if request.setup_id in setup_sessions:
            del setup_sessions[request.setup_id]
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/setup/verify-password")
async def verify_password(request: PasswordRequest, current_user = Depends(user_ctx)):
    """Verifiziere 2FA-Passwort"""
    user_id = str(current_user["id"])
    
    if request.setup_id not in setup_sessions:
        raise HTTPException(status_code=404, detail="Setup session not found")
    
    session = setup_sessions[request.setup_id]
    
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    client = session["client"]
    
    try:
        await client.sign_in(password=request.password)
        
        me = await client.get_me()
        
        # StringSession extrahieren
        session_string = client.session.save()
        
        # Session speichern
        user_info = {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name
        }
        save_string_session(session["session_name"], session_string, user_info, user_id)
        
        # Client disconnecten
        await client.disconnect()
        
        # Setup-Session entfernen
        del setup_sessions[request.setup_id]
        
        return {
            "success": True,
            "message": f"Session '{session['session_name']}' successfully created",
            "user": user_info,
            "session_string": session_string  # Optional: für direkten Zugriff
        }
        
    except Exception as e:
        await client.disconnect()
        if request.setup_id in setup_sessions:
            del setup_sessions[request.setup_id]
        raise HTTPException(status_code=400, detail="Invalid password")

@router.get("/sessions/{session_name}/string")
async def get_session_string(session_name: str, current_user = Depends(user_ctx)):
    """Hole StringSession für eine Session"""
    user_id = str(current_user["id"])
    session_string, user_info = load_string_session(session_name, user_id)
    
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_name": session_name,
        "session_string": session_string,
        "user_info": user_info
    }

@router.delete("/sessions/{session_name}")
async def delete_session(session_name: str, current_user = Depends(user_ctx)):
    """Lösche eine Session-Datei"""
    user_id = str(current_user["id"])
    user_dir = SESSION_DIR / f"user_{user_id}"
    session_file = user_dir / f"{session_name}.json"
    
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_file.unlink()
    return {"message": f"Session '{session_name}' deleted"}

@router.post("/setup/cancel/{setup_id}")
async def cancel_setup(setup_id: str, current_user = Depends(user_ctx)):
    """Breche Setup-Prozess ab"""
    user_id = str(current_user["id"])
    
    if setup_id in setup_sessions:
        session = setup_sessions[setup_id]
        
        # Sicherheitsprüfung
        if session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        client = session["client"]
        await client.disconnect()
        del setup_sessions[setup_id]
    
    return {"message": "Setup cancelled"}

@router.post("/sessions/{session_name}/test")
async def test_session(session_name: str, current_user = Depends(user_ctx)):
    """Teste ob eine Session funktioniert"""
    user_id = str(current_user["id"])
    session_string, user_info = load_string_session(session_name, user_id)
    
    if not session_string:
        raise HTTPException(status_code=404, detail="Session not found")
    
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "valid": True,
                "user": {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "last_name": me.last_name
                }
            }
        else:
            return {"valid": False, "reason": "Not authorized"}
            
    except Exception as e:
        return {"valid": False, "reason": str(e)}
    finally:
        await client.disconnect()

@router.post("/sessions/from-string")
async def create_session_from_string(session_string: str, session_name: str, current_user = Depends(user_ctx)):
    """Erstelle Session aus StringSession"""
    user_id = str(current_user["id"])
    user_dir = SESSION_DIR / f"user_{user_id}"
    session_file = user_dir / f"{session_name}.json"
    
    if session_file.exists():
        raise HTTPException(
            status_code=400, 
            detail=f"Session '{session_name}' already exists"
        )
    
    try:
        # Test der StringSession
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            user_info = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name
            }
            
            # Session speichern
            save_string_session(session_name, session_string, user_info, user_id)
            
            await client.disconnect()
            
            return {
                "success": True,
                "message": f"Session '{session_name}' created from string",
                "user": user_info
            }
        else:
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session string is not authorized")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid session string: {str(e)}")