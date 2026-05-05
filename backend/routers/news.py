from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import models
from database import get_db
from services.rss_parser import parse_rss_and_save

router = APIRouter()

class SourceCreate(BaseModel):
    name: str
    url: str
    is_aggregator: bool = False

@router.post("/news/fetch")
def fetch_news(x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    """Принудительно запустить парсинг новостей"""
    added_count = parse_rss_and_save(db, project_id=x_project_id)
    
    # Save last update time
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    setting = db.query(models.GlobalSettings).filter(models.GlobalSettings.project_id == x_project_id, models.GlobalSettings.key == "last_rss_update").first()
    if setting:
        setting.value = now_str
    else:
        setting = models.GlobalSettings(project_id=x_project_id, key="last_rss_update", value=now_str)
        db.add(setting)
    db.commit()
    
    return {"status": "ok", "added": added_count, "last_update": now_str}

@router.get("/news")
def get_news(skip: int = 0, limit: int = 50, source_id: int = None, hide_processed: bool = False, x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    """Получить список новостей с пагинацией"""
    query = db.query(models.NewsItem).filter(models.NewsItem.project_id == x_project_id)
    if source_id:
        query = query.filter(models.NewsItem.source_id == source_id)
    if hide_processed:
        query = query.filter(models.NewsItem.status.notin_([models.NewsStatus.NEW.value, models.NewsStatus.PUBLISHED.value]))
    news = query.order_by(models.NewsItem.pub_date.desc()).offset(skip).limit(limit).all()
    total = query.count()
    
    result = []
    for item in news:
        tasks = db.query(models.VideoTask).filter(
            models.VideoTask.news_id == item.id
        ).all()
        formats = [t.video_format for t in tasks]
        queued_tasks = [{"format": t.video_format, "status": t.status} for t in tasks]
        
        # Вычисление динамического статуса
        computed_status = item.status
        if len(tasks) > 0:
            statuses = [t.status for t in tasks]
            if 'PUBLISHED' in statuses:
                computed_status = 'PUBLISHED'
            elif 'UPLOADING' in statuses:
                computed_status = 'UPLOADING'
            elif 'READY' in statuses:
                computed_status = 'READY'
            elif 'ASSEMBLING' in statuses or 'GENERATING' in statuses:
                computed_status = 'GENERATING'
            else:
                computed_status = 'IN_QUEUE'
        else:
            if item.status not in [models.NewsStatus.NEW.value, models.NewsStatus.PUBLISHED.value]:
                item.status = models.NewsStatus.NEW.value
                db.commit()
            computed_status = item.status
            
        result.append({
            "id": item.id,
            "title": item.title,
            "link": item.link,
            "pub_date": item.pub_date,
            "source": item.source,
            "status": computed_status,
            "queued_formats": formats,
            "queued_tasks": queued_tasks
        })
    return {"total": total, "items": result}

@router.get("/sources")
def get_sources(x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    sources = db.query(models.RssSource).filter(models.RssSource.project_id == x_project_id).all()
    
    result = []
    for s in sources:
        active_count = db.query(models.NewsItem.id).join(
            models.VideoTask, models.VideoTask.news_id == models.NewsItem.id
        ).filter(
            models.NewsItem.source_id == s.id,
            models.VideoTask.status != 'PUBLISHED'
        ).distinct().count()
        
        result.append({
            "id": s.id, 
            "name": s.name, 
            "url": s.url, 
            "is_active": s.is_active,
            "is_aggregator": s.is_aggregator,
            "active_count": active_count
        })
    return result

@router.post("/sources")
def create_source(payload: SourceCreate, x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    new_source = models.RssSource(name=payload.name, url=payload.url, project_id=x_project_id, is_aggregator=payload.is_aggregator)
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return {"id": new_source.id, "name": new_source.name, "url": new_source.url, "is_active": new_source.is_active, "is_aggregator": new_source.is_aggregator}

@router.put("/sources/{source_id}")
def update_source(source_id: int, payload: SourceCreate, x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    source = db.query(models.RssSource).filter(models.RssSource.id == source_id, models.RssSource.project_id == x_project_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source.name = payload.name
    source.url = payload.url
    source.is_aggregator = payload.is_aggregator
    db.commit()
    db.refresh(source)
    return {"id": source.id, "name": source.name, "url": source.url, "is_active": source.is_active, "is_aggregator": source.is_aggregator}

@router.delete("/sources/{source_id}")
def delete_source(source_id: int, x_project_id: int = Header(1, alias="X-Project-Id"), db: Session = Depends(get_db)):
    source = db.query(models.RssSource).filter(models.RssSource.id == source_id, models.RssSource.project_id == x_project_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete related VideoTasks first (to delete files)
    news_items = db.query(models.NewsItem).filter(models.NewsItem.source_id == source.id).all()
    news_ids = [n.id for n in news_items]
    if news_ids:
        tasks = db.query(models.VideoTask).filter(models.VideoTask.news_id.in_(news_ids)).all()
        for t in tasks:
            if t.video_path and os.path.exists(t.video_path):
                try:
                    os.remove(t.video_path)
                except:
                    pass
        db.query(models.VideoTask).filter(models.VideoTask.news_id.in_(news_ids)).delete(synchronize_session=False)
    
    # Delete NewsItems
    db.query(models.NewsItem).filter(models.NewsItem.source_id == source.id).delete(synchronize_session=False)
    
    db.delete(source)
    db.commit()
    return {"status": "ok"}
