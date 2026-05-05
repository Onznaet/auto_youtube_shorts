from fastapi import APIRouter, Depends, UploadFile, File, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import models
from database import get_db

router = APIRouter()

class SettingsUpdate(BaseModel):
    settings: dict

GLOBAL_KEYS = ["gemini_api_key", "groq_api_key", "gemini_models", "groq_models", "openrouter_api_key", "openrouter_models", "api_requests_per_minute", "yandex_api_key", "yandex_folder_id", "voice_api_key", "yandex_voice_male", "yandex_voice_female", "voice_engines"]

@router.get("/settings")
def get_settings(x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    project_settings = db.query(models.GlobalSettings).filter(models.GlobalSettings.project_id == x_project_id).all()
    global_settings = db.query(models.GlobalSettings).filter(models.GlobalSettings.project_id == None).all()
    
    result = {s.key: s.value for s in project_settings}
    result.update({s.key: s.value for s in global_settings})
    return result

@router.post("/settings")
def update_settings(payload: SettingsUpdate, x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    for k, v in payload.settings.items():
        if k in GLOBAL_KEYS:
            continue
            
        setting = db.query(models.GlobalSettings).filter(
            models.GlobalSettings.project_id == x_project_id,
            models.GlobalSettings.key == k
        ).first()
        
        if setting:
            setting.value = v
        else:
            new_setting = models.GlobalSettings(project_id=x_project_id, key=k, value=v)
            db.add(new_setting)
    db.commit()
    return {"status": "ok"}

@router.get("/system_settings")
def get_system_settings(db: Session = Depends(get_db)):
    global_settings = db.query(models.GlobalSettings).filter(models.GlobalSettings.project_id == None).all()
    return {s.key: s.value for s in global_settings}

@router.post("/system_settings")
def update_system_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    for k, v in payload.settings.items():
        if k in GLOBAL_KEYS:
            setting = db.query(models.GlobalSettings).filter(
                models.GlobalSettings.project_id == None,
                models.GlobalSettings.key == k
            ).first()
            if setting:
                setting.value = v
            else:
                new_setting = models.GlobalSettings(key=k, value=v)
                db.add(new_setting)
                db.flush()
                new_setting.project_id = None
    db.commit()
    return {"status": "ok"}

@router.post("/upload_music")
def upload_music(file: UploadFile = File(...)):
    os.makedirs("music", exist_ok=True)
    file_location = f"music/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    return {"status": "ok", "path": os.path.abspath(file_location)}

@router.post("/upload_watermark")
def upload_watermark(file: UploadFile = File(...)):
    os.makedirs("watermarks", exist_ok=True)
    file_location = f"watermarks/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    return {"status": "ok", "path": os.path.abspath(file_location)}

class ModelSetRequest(BaseModel):
    model: str

@router.post("/set_model")
def set_manual_model(req: ModelSetRequest):
    from services.status_manager import set_current_model
    set_current_model(req.model)
    return {"status": "ok"}

@router.post("/auth/youtube")
def start_youtube_auth(x_project_id: int = Header(1, alias="X-Project-Id")):
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "youtube_auth.py")
    import subprocess
    import sys
    subprocess.Popen([sys.executable, script_path, str(x_project_id)])
    return {"status": "started"}

@router.get("/auth/youtube")
def get_youtube_auth_status(x_project_id: int = Header(1, alias="X-Project-Id")):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profile_dir = os.path.join(base_dir, "profiles", f"project_{x_project_id}")
    cookies_file = os.path.join(profile_dir, "Default", "Network", "Cookies")
    cookies_file_fallback = os.path.join(profile_dir, "Default", "Cookies")
    
    is_authorized = os.path.exists(cookies_file) or os.path.exists(cookies_file_fallback)
    has_profile = os.path.exists(profile_dir) and len(os.listdir(profile_dir)) > 0
    
    return {
        "authorized": is_authorized,
        "details": {
            "has_profile": has_profile,
            "has_cookies": is_authorized
        }
    }
