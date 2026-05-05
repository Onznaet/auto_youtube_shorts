import feedparser
from bs4 import BeautifulSoup
import datetime
from sqlalchemy.orm import Session
from models import NewsItem, NewsStatus, RssSource

def parse_rss_and_save(db: Session, max_items: int = 20, project_id: int = 1):
    """
    Парсит все активные RSS ленты текущего проекта и сохраняет новые записи в базу данных.
    Возвращает количество добавленных новостей.
    """
    sources = db.query(RssSource).filter(RssSource.is_active == True, RssSource.project_id == project_id).all()
    if not sources:
        # Create default source for this project
        default_source = RssSource(name="Lenta.ru", url="https://lenta.ru/rss/news", project_id=project_id)
        db.add(default_source)
        db.commit()
        db.refresh(default_source)
        sources = [default_source]
        
    new_count = 0
    for source in sources:
        feed = feedparser.parse(source.url)
        
        for entry in feed.entries[:max_items]:
            existing_news = db.query(NewsItem).filter(NewsItem.link == entry.link, NewsItem.project_id == project_id).first()
            if existing_news:
                continue
                
            description = entry.description if hasattr(entry, 'description') else ""
            soup = BeautifulSoup(description, "html.parser")
            plain_text = soup.get_text(separator=" ", strip=True)
            
            pub_date = None
            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.datetime(*entry.published_parsed[:6])
                else:
                    pub_date = datetime.datetime.now()
            except Exception:
                pub_date = datetime.datetime.now()
                
            news_item = NewsItem(
                project_id=project_id,
                source_id=source.id,
                title=entry.title,
                link=entry.link,
                description=plain_text,
                pub_date=pub_date,
                status=NewsStatus.NEW.value
            )
            db.add(news_item)
            new_count += 1
            
    if new_count > 0:
        db.commit()
        
    return new_count
