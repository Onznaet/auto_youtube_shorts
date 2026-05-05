import threading
import json
import os
import time
import traceback

from database import SessionLocal
import models
from services.config_service import ConfigService
from services.status_manager import set_status
from services.youtube_playwright import upload_video_playwright
from services.publish_telegram import upload_video_telegram
from services.pipeline_manager import update_idle_status_local

youtube_upload_lock = threading.Lock()

class PublishService:
    @staticmethod
    def run_video_upload(task_id: int):
        with youtube_upload_lock:
            db_local = SessionLocal()
            try:
                local_task = db_local.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
                if not local_task or not local_task.video_path:
                    return
                
                # Default to youtube if nothing is selected
                try:
                    platforms = json.loads(local_task.target_platforms) if local_task.target_platforms else ["youtube"]
                except:
                    platforms = ["youtube"]
                    
                tags = " ".join([f"#{t.strip().replace(' ', '')}" for t in (local_task.video_tags or "").split(",") if t.strip()])
                full_desc = f"{local_task.video_description}\n\n{tags}"
                
                upload_errors = []
                
                if "telegram" in platforms:
                    set_status(f"Загрузка видео {task_id} в Telegram...")
                    config = ConfigService(db_local, local_task.project_id)
                    bot_token = config.get("telegram_bot_token", "")
                    channel_id = config.get("telegram_channel_id", "")
                    
                    success, msg = upload_video_telegram(
                        file_path=local_task.video_path,
                        caption=full_desc,
                        bot_token=bot_token,
                        chat_id=channel_id
                    )
                    if not success:
                        upload_errors.append(msg)
                
                if "youtube" in platforms:
                    set_status(f"Загрузка видео {task_id} на YouTube (Браузер)...")
                    try:
                        upload_video_playwright(
                            file_path=local_task.video_path,
                            title=(local_task.video_title if local_task.use_rewrite else (local_task.custom_title or local_task.news.title)) or "Shorts Video",
                            description=full_desc,
                            project_id=local_task.project_id
                        )
                    except Exception as e:
                        upload_errors.append(f"YouTube ошибка: {str(e)[:100]}")
                        
                if "vk" in platforms:
                    # VK is not fully implemented yet
                    upload_errors.append("ВКонтакте пока не поддерживается")
                
                if upload_errors:
                    raise Exception(" | ".join(upload_errors))

                set_status(f"Видео {task_id} успешно загружено на {', '.join(platforms)}!")
                news_id_to_check = local_task.news_id
                
                if local_task.video_path and os.path.exists(local_task.video_path):
                    try:
                        import shutil
                        filename = os.path.basename(local_task.video_path)
                        if "_" in filename and filename.endswith(".mp4"):
                            run_id = filename.split("_")[-1].replace(".mp4", "")
                            base_dir = os.path.dirname(local_task.video_path)
                            task_dir = os.path.join(base_dir, f"task_{run_id}")
                            if os.path.exists(task_dir):
                                shutil.rmtree(task_dir, ignore_errors=True)
                        os.remove(local_task.video_path)
                    except Exception as e:
                        print(f"Failed to delete video file after upload: {e}")
                        
                db_local.delete(local_task)
                db_local.commit()
                
                remaining = db_local.query(models.VideoTask).filter(models.VideoTask.news_id == news_id_to_check).count()
                if remaining == 0:
                    news_item = db_local.query(models.NewsItem).filter(models.NewsItem.id == news_id_to_check).first()
                    if news_item:
                        news_item.status = models.NewsStatus.PUBLISHED.value
                        db_local.commit()
                
            except Exception as e:
                traceback.print_exc()
                set_status(f"Ошибка загрузки: {str(e)[:100]}")
                local_task = db_local.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
                if local_task:
                    local_task.status = 'READY'
                    db_local.commit()
            finally:
                db_local.close()
                time.sleep(5)
                # Since update_idle_status needs its own session, we use the one from pipeline manager
                update_idle_status_local(SessionLocal())

publish_service = PublishService()
