import time
import os
import shutil
import threading
import json
import traceback

from database import SessionLocal
import models
from services.config_service import ConfigService
from services.status_manager import set_status, get_current_model
from services.content_generator import generate_video_content
from services.image_search import download_images_for_task
from services.voice_generator import generate_voice
from services.video_assembler import assemble_video

# Locks for concurrency
media_assembly_lock = threading.Lock()

def update_idle_status_local(db_local):
    try:
        count = db_local.query(models.VideoTask).filter(models.VideoTask.status.in_(['GENERATING', 'ASSEMBLING'])).count()
        if count > 0:
            set_status(f"Ожидание очереди генерации... (Осталось задач: {count})")
        else:
            set_status("Ожидание задач...")
    except Exception:
        pass

def append_links_to_description(db_local, base_desc: str, source_url: str):
    config = ConfigService(db_local)
    social_link = config.get("social_link", "")
    
    final_desc = base_desc
    if social_link:
        final_desc += f"\n\nСоцсеть: {social_link}"
    if source_url:
        final_desc += f"\nИсточник: {source_url}"
    return final_desc

class PipelineManager:
    @staticmethod
    def run_text_generation(task_id: int, news_title: str, text_to_process: str, target_duration: int, image_count: int, project_id: int):
        db_local = SessionLocal()
        try:
            config = ConfigService(db_local, project_id)
            gemini_models_str = config.get("gemini_models", r"gemini-2.5-flash\ngemini-2.5-pro\ngemini-2.0-flash")
            groq_api_key = config.get("groq_api_key")
            groq_models_str = config.get("groq_models", r"llama-3.3-70b-versatile\nllama-3.1-8b-instant\nopenai/gpt-oss-120b\nopenai/gpt-oss-20b\nopenai/gpt-oss-safeguard-20b\nqwen/qwen3-32b")
            gemini_api_key = config.get("gemini_api_key")
            openrouter_api_key = config.get("openrouter_api_key")
            openrouter_models_str = config.get("openrouter_models", "")
            api_requests_per_minute = config.get_int("api_requests_per_minute", 3)

            cm = get_current_model()
            if "llama" in cm.lower() or "groq" in cm.lower() or "qwen" in cm.lower() or "gpt" in cm.lower():
                set_status("Генерация текста (Groq / OpenRouter)...")
            else:
                set_status("Генерация текста (Google)...")

            custom_prompt = config.get("system_prompt")

            llm_result = generate_video_content(
                gemini_api_key=gemini_api_key, 
                gemini_models_str=gemini_models_str,
                groq_api_key=groq_api_key,
                groq_models_str=groq_models_str,
                openrouter_api_key=openrouter_api_key,
                openrouter_models_str=openrouter_models_str,
                news_text=news_title + "\n\n" + text_to_process, 
                duration=target_duration,
                image_count=image_count,
                custom_prompt=custom_prompt,
                api_requests_per_minute=api_requests_per_minute
            )
            
            t_record = db_local.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
            if t_record:
                final_prompt = llm_result.voice_text
                if t_record.use_cta:
                    cta_text = config.get("cta_text")
                    if cta_text:
                        final_prompt += f"\n\n{cta_text}"
                
                t_record.prompt = final_prompt
                t_record.video_title = llm_result.video_title
                t_record.video_description = append_links_to_description(db_local, llm_result.video_description, t_record.source_url)
                t_record.video_tags = llm_result.video_tags
                t_record.image_keywords = ",".join(llm_result.image_keywords)
                t_record.status = "NEW"
                db_local.commit()
                
                time.sleep(3)
                update_idle_status_local(db_local)
                
        except Exception as e:
            traceback.print_exc()
            t_record = db_local.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
            if t_record:
                t_record.status = "ERROR"
                db_local.commit()
            set_status(f"Ошибка генерации: {e}")
        finally:
            db_local.close()

    @staticmethod
    def run_media_assembly(t_id: int):
        with media_assembly_lock:
            db_local = SessionLocal()
            try:
                local_task = db_local.query(models.VideoTask).filter(models.VideoTask.id == t_id).first()
                if not local_task: return
                
                local_keywords = [k.strip() for k in local_task.image_keywords.split(",") if k.strip()]
                run_id = f"{int(time.time())}"
                
                downloaded_paths = []
                if local_keywords:
                    downloaded_paths = download_images_for_task(t_id, local_keywords, run_id=run_id)
                    
                if not downloaded_paths:
                    set_status("Все картинки отбракованы или не найдены. Отмена генерации.")
                    local_task.status = 'PENDING'
                    db_local.commit()
                    return
                    
                config = ConfigService(db_local, local_task.project_id)
                
                voice_path = None
                if local_task.prompt:
                    actual_cta_text = config.get("cta_text") if local_task.use_cta else None
                    voice_path = generate_voice(t_id, local_task.prompt, local_task.voice, local_task.video_format, run_id=run_id, cta_text=actual_cta_text)
                    
                actual_music_path = None
                if local_task.background_music == "none":
                    actual_music_path = None
                elif local_task.background_music == "default" or not local_task.background_music:
                    actual_music_path = config.get("default_music_path")
                else:
                    actual_music_path = local_task.background_music
                    
                vol = local_task.music_volume if local_task.music_volume is not None else config.get_int("default_music_volume", 30)

                actual_watermark_path = None
                if local_task.watermark_path == "none":
                    actual_watermark_path = None
                elif local_task.watermark_path == "default" or not local_task.watermark_path:
                    actual_watermark_path = config.get("default_watermark_path")
                else:
                    actual_watermark_path = local_task.watermark_path

                video_path = None
                if downloaded_paths and voice_path:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(local_task.news.link).netloc.replace('www.', '').split('.')[0] if local_task.news and local_task.news.link else "unknown"
                    except:
                        domain = "unknown"
                    
                    format_name = "vertical" if local_task.video_format == "VERTICAL" else "standard"
                    custom_filename = f"{domain}_{format_name}_{run_id}.mp4"
                    
                    video_path = assemble_video(
                        task_id=t_id, 
                        image_paths=downloaded_paths, 
                        voice_path=voice_path, 
                        video_format=local_task.video_format,
                        music_path=actual_music_path,
                        music_volume=vol,
                        image_zoom=local_task.image_zoom if local_task.image_zoom is not None else 5,
                        watermark_path=actual_watermark_path,
                        run_id=run_id,
                        custom_filename=custom_filename
                    )
                    
                if video_path and os.path.exists(video_path):
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    final_save_path = os.path.join(base_dir, "media_cache", custom_filename)
                    shutil.move(video_path, final_save_path)
                    video_path = final_save_path
                    set_status(f"Видео сохранено в кэше.")
                    
                set_status(f"Задача {t_id} полностью завершена!")
                
                if video_path and os.path.exists(video_path):
                    local_task.video_path = video_path
                    local_task.status = 'READY'
                    db_local.commit()
            except Exception as e:
                traceback.print_exc()
                set_status(f"Сбой сборки: {str(e)[:50]}")
                local_task = db_local.query(models.VideoTask).filter(models.VideoTask.id == t_id).first()
                if local_task:
                    local_task.status = 'ERROR'
                    local_task.error_message = str(e)
                    db_local.commit()
            finally:
                db_local.close()
                time.sleep(3)
                update_idle_status_local(db_local)

pipeline_manager = PipelineManager()
