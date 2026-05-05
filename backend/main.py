from fastapi import FastAPI, Depends, BackgroundTasks, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import shutil
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models
from services.rss_parser import parse_rss_and_save
from services.content_generator import generate_video_content, GenerationResult
from services.article_scraper import scrape_full_article
from services.image_search import download_images_for_task
from services.voice_generator import generate_voice
from services.video_assembler import assemble_video
from services.status_manager import get_status, set_status

class TaskUpdateRequest(BaseModel):
    prompt: str | None = None
    video_title: str | None = None
    custom_title: str | None = None
    video_description: str | None = None
    video_tags: str | None = None
    image_keywords: str | None = None
    video_format: str | None = None
    voice: str | None = None
    background_music: str | None = None
    music_volume: int | None = None
    image_zoom: int | None = None
    watermark_path: str | None = None
    duration: int | None = None
    source_url: str | None = None
    delete_temp_files: bool | None = None
    target_platforms: str | None = None
    use_rewrite: bool | None = None
    use_cta: bool | None = None

class FieldRegenerateRequest(BaseModel):
    field: str
from fastapi import HTTPException

# Create tables
Base.metadata.create_all(bind=engine)

def update_idle_status():
    from database import SessionLocal
    import models
    from services.status_manager import set_status
    db_local = SessionLocal()
    try:
        count = db_local.query(models.VideoTask).filter(models.VideoTask.status.in_(['GENERATING', 'ASSEMBLING'])).count()
        if count > 0:
            set_status(f"Ожидание очереди генерации... (Осталось задач: {count})")
        else:
            set_status("Ожидание задач...")
    finally:
        db_local.close()

def append_links_to_description(db_local, base_desc: str, source_url: str):
    import models
    social_link_setting = db_local.query(models.GlobalSettings).filter(models.GlobalSettings.key == "social_link").first()
    social_link = social_link_setting.value if social_link_setting and social_link_setting.value else ""
    
    final_desc = base_desc
    if social_link:
        final_desc += f"\n\nСоцсеть: {social_link}"
    if source_url:
        final_desc += f"\nИсточник: {source_url}"
    return final_desc

app = FastAPI(title="Auto YouTube Shorts API")

# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def load_default_config():
    import json
    import os
    config_path = os.path.join(os.path.dirname(__file__), "default_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                defaults = json.load(f)
            
            db = next(get_db())
            for k, v in defaults.items():
                setting = db.query(models.GlobalSettings).filter(models.GlobalSettings.key == k).first()
                if not setting:
                    new_setting = models.GlobalSettings(key=k, value=v)
                    db.add(new_setting)
            db.commit()
        except Exception as e:
            print(f"Failed to load default config: {e}")


from routers import projects, news, settings, tasks

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(news.router, prefix="/api", tags=["news"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
