import os
import urllib.parse
import json
import requests
import uuid
import time
from services.config_service import ConfigService
import urllib.parse
from bs4 import BeautifulSoup
from services.status_manager import set_status

def search_images_bing(query: str, max_results: int = 5) -> list[str]:
    """
    Ищет картинки через Bing.
    Bing почти не имеет жестких лимитов и не выдает капчу так часто, как Яндекс.
    """
    set_status(f"Поиск картинок (Bing): {query}")
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', class_='iusc')
        images = []
        for link in links:
            if len(images) >= max_results:
                break
            try:
                m = json.loads(link.get('m', '{}'))
                if 'murl' in m:
                    images.append(m['murl'])
            except:
                continue
        return images
    except Exception as e:
        set_status(f"Ошибка при поиске картинок по запросу '{query}': {e}")
        return []

def search_images_yandex_cloud(query: str, folder_id: str, api_key: str, max_results: int = 5) -> list[str]:
    """
    Ищет картинки через официальный Yandex Cloud Search API.
    """
    set_status(f"Поиск картинок (Yandex Cloud): {query}")
    url = "https://searchapi.api.cloud.yandex.net/v2/image/search"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query
        },
        "folderId": folder_id,
        "docsOnPage": str(max_results)
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        images = []
        
        # Simple extraction using regex or xml parsing
        # For Yandex images XML, the direct image URL is usually inside <url>...</url>
        import xml.etree.ElementTree as ET
        import base64
        try:
            resp_json = r.json()
            if "rawData" not in resp_json:
                print(f"[YANDEX API ERROR] No rawData in response: {r.text[:1000]}")
                set_status("Ошибка Yandex API: неверный формат ответа")
                return []
                
            xml_text = base64.b64decode(resp_json["rawData"]).decode("utf-8")
            root = ET.fromstring(xml_text)
            
            # Проверим, нет ли ошибки в ответе
            error_elem = root.find(".//error")
            if error_elem is not None:
                print(f"[YANDEX API ERROR] Code: {error_elem.get('code')}, Message: {error_elem.text}")
                set_status(f"Ошибка Yandex API: {error_elem.text}")
                return []
                
            for doc in root.findall(".//doc"):
                url_elem = doc.find("url")
                if url_elem is not None and url_elem.text:
                    images.append(url_elem.text)
                    
            if not images:
                print("[YANDEX API NO IMAGES FOUND] Raw response:", r.text[:1000])
                
        except ET.ParseError:
            print("[YANDEX API PARSE ERROR] Raw response:", r.text[:1000])
            set_status(f"Ошибка парсинга XML Yandex для '{query}'")
            
        return images[:max_results]
    except Exception as e:
        set_status(f"Ошибка API Яндекс Картинок по запросу '{query}': {e}")
        return []

def download_images_for_task(task_id: int, keywords: list[str], output_dir: str = "media_cache", run_id: str = None) -> list[str]:
    """
    Ищет картинки по списку ключевых слов и скачивает их в папку задачи.
    Возвращает список путей к скачанным файлам.
    """
    from services.image_moderator import moderate_image
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder_name = f"task_{run_id}" if run_id else f"task_{task_id}"
    task_dir = os.path.join(base_dir, output_dir, folder_name)
    os.makedirs(task_dir, exist_ok=True)
    
    downloaded_paths = []
    keyword_mapping = []
    
    # Fetch global settings to see if Yandex is configured
    try:
        from database import SessionLocal
        import models
        db = SessionLocal()
        
        task = db.query(models.VideoTask).filter(models.VideoTask.id == task_id).first()
        project_id = task.project_id if task else 1
        
        config = ConfigService(db, project_id)
        yandex_api_key = config.get("yandex_api_key")
        yandex_folder_id = config.get("yandex_folder_id")
        gemini_api_key = config.get("gemini_api_key")
        gemini_models = config.get("gemini_models")
        groq_api_key = config.get("groq_api_key")
        groq_models = config.get("groq_models")
        openrouter_api_key = config.get("openrouter_api_key")
        openrouter_models = config.get("openrouter_models")
        
        mod_enabled = config.get_bool("image_moderator_enabled", False)
        mod_prompt = config.get("image_moderator_prompt", "")
        mod_rpm = config.get_int("image_moderator_rpm", 10)
        
        yandex_negative_keywords = config.get("yandex_negative_keywords", "")
        
        db.close()
    except Exception as e:
        print("Failed to fetch config:", e)
        yandex_api_key = None
        yandex_folder_id = None
        gemini_api_key = None
        gemini_models = "gemini-2.5-flash"
        groq_api_key = None
        groq_models = ""
        openrouter_api_key = None
        openrouter_models = ""
        mod_enabled = False
        mod_prompt = ""
        mod_rpm = 10
        yandex_negative_keywords = ""
        
    images_per_keyword = 15 if mod_enabled else 5 # Берем большой запас картинок, так как модератор может отбраковать многие
    
    neg_parts = [p.strip() for p in yandex_negative_keywords.split(',') if p.strip()]
    
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
            
        search_query = keyword
        if neg_parts:
            neg_string = " ".join([f"-{p}" if not p.startswith("-") else p for p in neg_parts])
            search_query = f"{keyword} {neg_string}"
            
        if yandex_api_key and yandex_folder_id:
            urls = search_images_yandex_cloud(search_query, yandex_folder_id, yandex_api_key, max_results=images_per_keyword)
            # Fallback to Bing if Yandex returns nothing (e.g., due to quota)
            if not urls:
                urls = search_images_bing(search_query, max_results=images_per_keyword)
        else:
            urls = search_images_bing(search_query, max_results=images_per_keyword)
        
        time.sleep(1) # Небольшая задержка для вежливости
        
        # Скачиваем картинки по одной и проверяем
        for url in urls:
            try:
                set_status(f"Скачивание картинки: {url[:60]}...")
                img_response = requests.get(url, timeout=5)
                if img_response.status_code == 200:
                    ext = url.split('.')[-1].split('?')[0]
                    if ext.lower() not in ['jpg', 'jpeg', 'png', 'webp']:
                        ext = 'jpg'
                    
                    filename = f"{uuid.uuid4().hex[:8]}.{ext}"
                    filepath = os.path.join(task_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(img_response.content)
                        
                    # AI-Модерация
                    if mod_enabled and mod_prompt and gemini_api_key:
                        set_status(f"Проверка картинки нейросетью: {keyword[:20]}...")
                        is_valid, reason = moderate_image(
                            gemini_api_key=gemini_api_key, 
                            gemini_models_str=gemini_models,
                            groq_api_key=groq_api_key,
                            groq_models_str=groq_models,
                            openrouter_api_key=openrouter_api_key,
                            openrouter_models_str=openrouter_models,
                            rpm=mod_rpm, 
                            image_path=filepath, 
                            query=keyword, 
                            prompt=mod_prompt
                        )
                        if not is_valid:
                            set_status(f"Картинка отбракована: {reason}")
                            print(f"[AI Модератор] ❌ ОТКЛОНЕНО ({keyword}): {reason}")
                            os.remove(filepath)
                            continue # Переходим к следующему URL
                        else:
                            print(f"[AI Модератор] ✅ ОДОБРЕНО ({keyword}): {reason}")
                            
                    downloaded_paths.append(filepath)
                    keyword_mapping.append({
                        "keyword": keyword,
                        "search_query": search_query,
                        "filename": filename
                    })
                    break # Успешно скачали и прошли модерацию, переходим к следующему ключу
            except Exception as e:
                set_status(f"Ошибка скачивания {url[:30]}: {str(e)[:50]}")
                
    set_status(f"Всего скачано {len(downloaded_paths)} картинок.")
    
    # Сохраняем маппинг ключевых слов и скачанных файлов
    if keyword_mapping:
        import json
        mapping_path = os.path.join(task_dir, "image_mapping.json")
        try:
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(keyword_mapping, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Не удалось сохранить маппинг: {e}")
            
    return downloaded_paths

if __name__ == "__main__":
    # Тестовый запуск
    urls = search_yandex_images("космос", 3)
    print("Найдено ссылок:", urls)
