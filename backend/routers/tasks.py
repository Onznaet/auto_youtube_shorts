from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import shutil
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models
from services.config_service import ConfigService
from services.rss_parser import parse_rss_and_save
from services.content_generator import generate_video_content, GenerationResult
from services.article_scraper import scrape_full_article
from services.image_search import download_images_for_task
from services.voice_generator import generate_voice
from services.video_assembler import assemble_video
from services.status_manager import get_status, set_status

def cleanup_temp_folder(video_path: str):
    if not video_path: return
    try:
        import shutil
        filename = os.path.basename(video_path)
        if "_" in filename and filename.endswith(".mp4"):
            run_id = filename.split("_")[-1].replace(".mp4", "")
            base_dir = os.path.dirname(video_path)
            task_dir = os.path.join(base_dir, f"task_{run_id}")
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning temp folder: {e}")

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
    from services.config_service import ConfigService
    config = ConfigService(db_local)
    social_link = config.get("social_link", "")
    
    final_desc = base_desc
    if social_link:
        final_desc += f"\n\nСоцсеть: {social_link}"
    if source_url:
        final_desc += f"\nИсточник: {source_url}"
    return final_desc

router = APIRouter()

# Setup CORS for Frontend


@router.post("/queue/add/{news_id}")
def add_to_queue(news_id: int, background_tasks: BackgroundTasks, format: str = "vertical", x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    news = db.query(models.NewsItem).filter(models.NewsItem.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
        
    actual_format = "VERTICAL" if format == "vertical" else "HORIZONTAL"
    
    existing = db.query(models.VideoTask).filter(models.VideoTask.news_id == news_id, models.VideoTask.video_format == actual_format).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Already in queue as {actual_format}")

    config = ConfigService(db, x_project_id)
    if not config.get("gemini_api_key"):
        raise HTTPException(status_code=400, detail="Gemini API Key is missing in Settings")
        
    try:
        if (not news.full_text or not news.source_url) and news.link:
            try:
                full_text, scraped_source_url = scrape_full_article(news.link, is_aggregator=(news.source.is_aggregator if news.source else False))
                if full_text:
                    news.full_text = full_text
                if scraped_source_url:
                    news.source_url = scraped_source_url
                db.commit()
            except Exception as e:
                print(f"Failed to scrape article: {e}")
                
        text_to_process = news.full_text if news.full_text else news.description
        
        # Get default music if any
        default_music_path = config.get("default_music_path")
        default_music_volume = config.get_int("default_music_volume", 30)
        default_image_zoom = config.get_int("default_image_zoom", 5)
        default_watermark_path = config.get("default_watermark_path")
        default_delete_temp_files = config.get_bool("default_delete_temp_files", True)
        
        target_duration = config.get_int("default_duration_vertical", 30) if format == "vertical" else config.get_int("default_duration_video", 90)
        target_speed = config.get_float("image_change_speed_vertical", 2.0) if format == "vertical" else config.get_float("image_change_speed_video", 5.0)
        
        # Увеличиваем плотность: +1 ключевое слово на каждые 30 секунд
        extra_keywords = int(target_duration / 30)
        image_count = max(3, min(30, int(target_duration / target_speed) + extra_keywords))
        
        voice = "female"
        if config.get_bool("alternate_voices"):
            last_task = db.query(models.VideoTask).filter(models.VideoTask.project_id == x_project_id).order_by(models.VideoTask.id.desc()).first()
            if last_task and last_task.voice:
                if last_task.voice == "female" or "Svetlana" in last_task.voice:
                    voice = "male"
                else:
                    voice = "female"
        
        default_platforms = []
        if config.get_bool("default_publish_youtube"): default_platforms.append("youtube")
        if config.get_bool("default_publish_telegram"): default_platforms.append("telegram")
        if config.get_bool("default_publish_vk"): default_platforms.append("vk")
        import json
        target_platforms_json = json.dumps(default_platforms)
        
        use_rewrite = config.get("rewrite_title", "true").lower() != "false"
        use_cta = config.get_bool("add_cta")
                    
        # Create placeholder task immediately
        task = models.VideoTask(project_id=x_project_id, 
            news_id=news.id,
            prompt="Ожидаем текст...",
            voice=voice,
            video_format=actual_format,
            duration=target_duration,
            video_title="Ожидаем текст...",
            video_description="Ожидаем текст...",
            video_tags="Ожидаем текст...",
            image_keywords="ожидаем, текст",
            background_music=default_music_path,
            music_volume=default_music_volume,
            image_zoom=default_image_zoom,
            watermark_path=default_watermark_path,
            source_url=news.source_url,
            delete_temp_files=default_delete_temp_files,
            target_platforms=target_platforms_json,
            use_rewrite=use_rewrite,
            use_cta=use_cta,
            status="GENERATING"
        )
        db.add(task)
        news.status = models.NewsStatus.IN_QUEUE.value
        db.commit()
        db.refresh(task)
        
        task_id = task.id
        news_title = news.title


        from services.pipeline_manager import pipeline_manager
        background_tasks.add_task(
            pipeline_manager.run_text_generation, 
            task_id, 
            news_title, 
            text_to_process, 
            target_duration, 
            image_count,
            x_project_id
        )
        
        # Clear status after a delay so user can read the error message if any
        def clear_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_status)
        return {"status": "ok", "task_id": task.id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        from services.status_manager import set_status
        set_status("Ошибка добавления в очередь!")
        
        def clear_error_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_error_status)
        raise HTTPException(status_code=500, detail=f"Ошибка нейросети: {str(e)}")

@router.get("/queue")
def get_queue(x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    tasks = db.query(models.VideoTask).join(models.NewsItem).filter(
        models.VideoTask.project_id == x_project_id,
        models.VideoTask.status.in_(['NEW', 'GENERATING', 'ASSEMBLING', 'ERROR'])
    ).order_by(models.VideoTask.news_id.desc(), models.VideoTask.created_at.desc()).all()
    
    result = []
    for task in tasks:
        result.append({
            "task_id": task.id,
            "news_title": task.news.title,
            "prompt": task.prompt,
            "video_title": task.video_title,
            "custom_title": task.custom_title,
            "video_description": task.video_description,
            "video_tags": task.video_tags,
            "image_keywords": task.image_keywords,
            "video_format": task.video_format,
            "duration": task.duration,
            "voice": task.voice,
            "background_music": task.background_music,
            "music_volume": task.music_volume,
            "image_zoom": task.image_zoom,
            "watermark_path": task.watermark_path,
            "source_url": task.source_url,
            "delete_temp_files": task.delete_temp_files,
            "news_link": task.news.link,
            "status": task.status,
            "target_platforms": task.target_platforms,
            "use_rewrite": task.use_rewrite,
            "use_cta": task.use_cta,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        })
    return result

@router.get("/ready")
def get_ready_videos(x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    tasks = db.query(models.VideoTask).join(models.NewsItem).filter(
        models.VideoTask.project_id == x_project_id,
        models.VideoTask.status.in_(['READY', 'UPLOADING'])
    ).order_by(models.VideoTask.updated_at.desc(), models.VideoTask.created_at.desc()).all()
    
    result = []
    for task in tasks:
        file_exists = False
        if task.video_path:
            file_exists = os.path.exists(task.video_path)
            
        result.append({
            "task_id": task.id,
            "news_title": task.news.title,
            "video_title": task.video_title,
            "custom_title": task.custom_title,
            "video_description": task.video_description,
            "video_tags": task.video_tags,
            "source_url": task.source_url,
            "video_format": task.video_format,
            "video_path": task.video_path,
            "file_exists": file_exists,
            "news_link": task.news.link,
            "status": task.status,
            "target_platforms": task.target_platforms,
            "use_rewrite": task.use_rewrite,
            "use_cta": task.use_cta
        })
    return result

@router.post("/ready/{task_id}/open")
def open_ready_video(task_id: int, db: Session = Depends(get_db)):
    import subprocess
    import platform
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task or not task.video_path or not os.path.exists(task.video_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        if platform.system() == 'Windows':
            os.startfile(task.video_path)
        elif platform.system() == 'Darwin':
            subprocess.call(['open', task.video_path])
        else:
            subprocess.call(['xdg-open', task.video_path])
        return {"status": "ok"}
    except Exception as e:
        print(f"Error opening file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queue/{task_id}")
def delete_queue_item(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    news_id = task.news_id
    if task.video_path and os.path.exists(task.video_path):
        try:
            cleanup_temp_folder(task.video_path)
            os.remove(task.video_path)
        except Exception as e:
            print(f"Failed to delete video file: {e}")
            
    db.delete(task)
    db.commit()
    
    # Revert news status back to NEW if no tasks left
    remaining = db.query(models.VideoTask).filter(models.VideoTask.news_id == news_id).count()
    if remaining == 0:
        news = db.query(models.NewsItem).filter(models.NewsItem.id == news_id).first()
        if news:
            news.status = models.NewsStatus.NEW.value
            db.commit()
            
    return {"status": "ok"}

@router.post("/queue/{task_id}/regenerate")
def regenerate_task_content(task_id: int, background_tasks: BackgroundTasks, duration: int = None, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task or not task.news:
        raise HTTPException(status_code=404, detail="Task or News not found")
        
    config = ConfigService(db, task.project_id)
    if not config.get("gemini_api_key"):
        raise HTTPException(status_code=400, detail="Gemini API Key missing in Settings")
        
    if duration is not None:
        task.duration = duration
        
    target_speed = config.get_float("image_change_speed_vertical", 2.0) if task.video_format == "VERTICAL" else config.get_float("image_change_speed_video", 5.0)
    image_count = max(3, min(20, int((task.duration or 30) / target_speed)))
        
    if not task.news.full_text and task.news.link:
        try:
            task.news.full_text, _ = scrape_full_article(task.news.link, is_aggregator=(task.news.source.is_aggregator if task.news.source else False))
            db.commit()
        except Exception as e:
            print(f"Failed to scrape article on regenerate: {e}")
            
    text_to_process = task.news.full_text if task.news.full_text else task.news.description
        
    try:
        models_str = config.get("gemini_models", "gemini-2.5-flash\ngemini-2.0-flash\ngemini-flash-latest")
        groq_api_key = config.get("groq_api_key")
        api_requests_per_minute = config.get_int("api_requests_per_minute", 3)
        custom_prompt = config.get("system_prompt")

        from services.status_manager import set_status, get_current_model
        cm = get_current_model()
        if cm == "Groq (llama-3.1-8b)":
            set_status("Перегенерация текста (Groq / Llama 3)...")
        else:
            set_status("Перегенерация текста (Gemini)...")

        llm_result = generate_video_content(
            gemini_api_key=config.get("gemini_api_key"), 
            gemini_models_str=models_str,
            groq_api_key=groq_api_key,
            groq_models_str=config.get("groq_models", "llama-3.1-8b-instant"),
            openrouter_api_key=config.get("openrouter_api_key"),
            openrouter_models_str=config.get("openrouter_models", "google/gemini-flash-1.5-8b"),
            news_text=task.news.title + "\n\n" + text_to_process, 
            duration=task.duration or 30,
            image_count=image_count,
            custom_prompt=custom_prompt,
            allow_mock=True,
            api_requests_per_minute=api_requests_per_minute
        )
        
        final_prompt = llm_result.voice_text
        if task.use_cta:
            cta_text = config.get("cta_text")
            if cta_text:
                final_prompt += f"\n\n{cta_text}"
                
        task.prompt = final_prompt
        task.video_title = llm_result.video_title
        task.video_description = append_links_to_description(db, llm_result.video_description, task.source_url)
        task.video_tags = llm_result.video_tags
        task.image_keywords = ",".join(llm_result.image_keywords)
        db.commit()
        
        def clear_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_status)
        
        is_mocked = "Лимит API" in task.video_title or "Сбой API" in task.video_title
        return {"status": "ok", "is_mocked": is_mocked}
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        def clear_error_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_error_status)
        
        from services.status_manager import set_status
        set_status("Ошибка перегенерации!")
        raise HTTPException(status_code=500, detail=f"Ошибка нейросети: {str(e)}")

@router.post("/queue/{task_id}/regenerate_field")
def regenerate_task_field(task_id: int, req: FieldRegenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task or not task.news:
        raise HTTPException(status_code=404, detail="Task or News not found")
        
    config = ConfigService(db, task.project_id)
    if not config.get("gemini_api_key"):
        raise HTTPException(status_code=400, detail="Gemini API Key missing in Settings")
        
    target_speed = config.get_float("image_change_speed_vertical", 2.0) if task.video_format == "VERTICAL" else config.get_float("image_change_speed_video", 5.0)
    image_count = max(3, min(20, int((task.duration or 30) / target_speed)))
    
    text_to_process = task.news.full_text if task.news.full_text else task.news.description
    
    try:
        from services.status_manager import set_status
        set_status(f"Перегенерация поля '{req.field}' для новости '{task.news.title}'...")
        models_str = config.get("gemini_models", "gemini-2.5-flash\ngemini-2.0-flash\ngemini-flash-latest")
        groq_api_key = config.get("groq_api_key")
        api_requests_per_minute = config.get_int("api_requests_per_minute", 3)
        custom_prompt = config.get("system_prompt")

        llm_result = generate_video_content(
            gemini_api_key=config.get("gemini_api_key"), 
            gemini_models_str=models_str,
            groq_api_key=groq_api_key,
            groq_models_str=config.get("groq_models", "llama-3.1-8b-instant"),
            openrouter_api_key=config.get("openrouter_api_key"),
            openrouter_models_str=config.get("openrouter_models", "google/gemini-flash-1.5-8b"),
            news_text=task.news.title + "\n\n" + text_to_process, 
            duration=task.duration or 30,
            image_count=image_count,
            custom_prompt=custom_prompt,
            allow_mock=True,
            api_requests_per_minute=api_requests_per_minute
        )
        
        if req.field == "prompt":
            final_prompt = llm_result.voice_text
            if task.use_cta:
                cta_text = config.get("cta_text")
                if cta_text:
                    final_prompt += f"\n\n{cta_text}"
            task.prompt = final_prompt
        elif req.field == "video_title":
            task.video_title = llm_result.video_title
        elif req.field == "video_description":
            task.video_description = append_links_to_description(db, llm_result.video_description, task.source_url)
        elif req.field == "video_tags":
            task.video_tags = llm_result.video_tags
        elif req.field == "image_keywords":
            task.image_keywords = ",".join(llm_result.image_keywords)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown field {req.field}")
            
        db.commit()
        
        def clear_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_status)
        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        def clear_error_status():
            import time
            time.sleep(5)
            update_idle_status()
            
        background_tasks.add_task(clear_error_status)
        
        from services.status_manager import set_status
        set_status("Ошибка перегенерации!")
        raise HTTPException(status_code=500, detail=f"Ошибка нейросети: {str(e)}")


@router.delete("/queue/by_news/{news_id}")
def delete_queue_item_by_news(news_id: int, format: str = "vertical", db: Session = Depends(get_db)):
    actual_format = "VERTICAL" if format == "vertical" else "HORIZONTAL"
    task = db.query(models.VideoTask).filter(models.VideoTask.news_id == news_id, models.VideoTask.video_format == actual_format).first()
    if not task:
        return {"status": "ok", "message": "Task not found"}
        
    if task.video_path and os.path.exists(task.video_path):
        try:
            os.remove(task.video_path)
        except Exception as e:
            print(f"Failed to delete video file: {e}")
            
    db.delete(task)
    db.commit()
    
    # Check if this was the last task for this news
    remaining = db.query(models.VideoTask).filter(models.VideoTask.news_id == news_id).count()
    if remaining == 0:
        news = db.query(models.NewsItem).filter(models.NewsItem.id == news_id).first()
        if news:
            news.status = models.NewsStatus.NEW.value
            db.commit()
            
    return {"status": "ok"}

@router.post("/queue/{task_id}/save")
def save_task_settings(task_id: int, req: TaskUpdateRequest, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if getattr(req, 'video_title', None) is not None: task.video_title = req.video_title
    if getattr(req, 'custom_title', None) is not None: task.custom_title = req.custom_title
    if req.prompt is not None: task.prompt = req.prompt
    if req.video_description is not None: task.video_description = req.video_description
    if req.video_tags is not None: task.video_tags = req.video_tags
    if req.image_keywords is not None: task.image_keywords = req.image_keywords
    if req.video_format is not None: task.video_format = req.video_format
    if req.voice is not None: task.voice = req.voice
    if req.background_music is not None: task.background_music = req.background_music
    if req.music_volume is not None: task.music_volume = req.music_volume
    if req.image_zoom is not None: task.image_zoom = req.image_zoom
    if req.watermark_path is not None: task.watermark_path = req.watermark_path
    if req.duration is not None: task.duration = req.duration
    if req.source_url is not None: task.source_url = req.source_url
    if req.delete_temp_files is not None: task.delete_temp_files = req.delete_temp_files
    if req.target_platforms is not None: task.target_platforms = req.target_platforms
    if req.use_rewrite is not None: task.use_rewrite = req.use_rewrite
    if req.use_cta is not None: task.use_cta = req.use_cta
    
    db.commit()
    return {"status": "ok"}

@router.post("/queue/{task_id}/generate_media")
def generate_task_media(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    keywords = [k.strip() for k in task.image_keywords.split(",") if k.strip()]
    if not keywords:
        return {"status": "ok", "message": "No keywords to search", "paths": []}
        
    task.status = 'ASSEMBLING'
    db.commit()

    from services.pipeline_manager import pipeline_manager
    background_tasks.add_task(pipeline_manager.run_media_assembly, task_id)
    return {"status": "ok"}

@router.post("/queue/{task_id}/upload")
def upload_to_youtube(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    
        
    task.status = 'UPLOADING'
    db.commit()

    from services.publish_service import publish_service
    background_tasks.add_task(publish_service.run_video_upload, task_id)
    return {"status": "ok"}

from pydantic import BaseModel
class ModelSetRequest(BaseModel):
    model: str

@router.get("/status")
def get_current_status(db: Session = Depends(get_db)):
    from services.status_manager import get_status, get_current_model, get_current_voice_engine
    from sqlalchemy import func
    
    config = ConfigService(db)
    gemini_str = config.get("gemini_models", "gemini-2.5-flash\ngemini-2.5-pro\ngemini-2.0-flash")
    groq_str = config.get("groq_models", "llama-3.3-70b-versatile\nllama-3.1-8b-instant\nopenai/gpt-oss-120b\nopenai/gpt-oss-20b\nopenai/gpt-oss-safeguard-20b\nqwen/qwen3-32b")
    openrouter_str = config.get("openrouter_models", "")
    voice_engines_str = config.get("voice_engines", "edge-tts\nyandex-speechkit")
    
    models_list = []
    models_list.extend([m.strip() for m in gemini_str.replace(',', '\n').split('\n') if m.strip()])
    models_list.extend([m.strip() for m in groq_str.replace(',', '\n').split('\n') if m.strip()])
    models_list.extend([m.strip() for m in openrouter_str.replace(',', '\n').split('\n') if m.strip()])
        
    voice_engines_list = [v.strip() for v in voice_engines_str.replace(',', '\n').split('\n') if v.strip()]
        
    last_task = db.query(func.max(models.VideoTask.updated_at)).scalar()
    last_task_c = db.query(func.max(models.VideoTask.created_at)).scalar()
    last_news_c = db.query(func.max(models.NewsItem.created_at)).scalar()
    
    t1 = last_task.timestamp() if last_task else 0
    t2 = last_task_c.timestamp() if last_task_c else 0
    t3 = last_news_c.timestamp() if last_news_c else 0
    last_update = max(t1, t2, t3)
        
    return {
        "status": get_status(), 
        "model": get_current_model(), 
        "available_models": models_list,
        "voice_engine": get_current_voice_engine(),
        "available_voice_engines": voice_engines_list,
        "last_update": last_update
    }

@router.post("/set_model")
def set_manual_model(req: ModelSetRequest):
    from services.status_manager import set_current_model
    set_current_model(req.model)
    return {"status": "ok"}

class VoiceEngineSetRequest(BaseModel):
    engine: str

@router.post("/set_voice_engine")
def set_manual_voice_engine(req: VoiceEngineSetRequest):
    from services.status_manager import set_current_voice_engine
    set_current_voice_engine(req.engine)
    return {"status": "ok"}

# --- Scheduler Status ---
import time
_scheduler_last_ping = 0

@router.post("/scheduler/ping")
def scheduler_ping():
    global _scheduler_last_ping
    _scheduler_last_ping = time.time()
    return {"status": "ok"}

@router.get("/scheduler/status")
def get_scheduler_status():
    global _scheduler_last_ping
    now = time.time()
    is_running = (now - _scheduler_last_ping) < 120 # considered offline if no ping in 2 mins
    return {
        "is_running": is_running,
        "last_ping": _scheduler_last_ping
    }
