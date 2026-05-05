import os
import time
import json
import base64
import requests
import threading
from google import genai
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from services.status_manager import get_current_model, set_current_model, set_status

# Глобальные блокировки для Rate Limiting
_last_api_request_time = 0
_api_request_lock = threading.Lock()

class GenerationResult(BaseModel):
    voice_text: str
    image_keywords: list[str]
    video_title: str
    video_description: str
    video_tags: str

class ModelCapabilities:
    def __init__(self, name: str, provider: str, can_text: bool, can_vision: bool, api_model_name: str):
        self.name = name
        self.provider = provider
        self.can_text = can_text
        self.can_vision = can_vision
        self.api_model_name = api_model_name

def parse_model_string(model_name: str, forced_provider: str) -> ModelCapabilities:
    """Определяет возможности модели по названию, используя заданного провайдера."""
    name_lower = model_name.lower()
    
    can_vision = False
    api_name = model_name
    
    if forced_provider == "google":
        can_vision = True
    elif forced_provider == "groq":
        # Groq currently does not support vision, even if name says vision
        can_vision = False
        if model_name == "Groq (llama-3.1-8b)":
            api_name = "llama-3.1-8b-instant"
    elif forced_provider == "openrouter":
        # OpenRouter usually supports vision for multimodal models, we'll assume it supports it if the name suggests it, or if it's a known vision model.
        if "vision" in name_lower or "4o" in name_lower or "claude-3" in name_lower or "gemini" in name_lower or "pixtral" in name_lower:
            can_vision = True
            
    return ModelCapabilities(
        name=model_name,
        provider=forced_provider,
        can_text=True,
        can_vision=can_vision,
        api_model_name=api_name
    )

def _enforce_rate_limit(rpm: int):
    global _last_api_request_time
    if rpm <= 0:
        return
    delay = 60.0 / rpm
    with _api_request_lock:
        now = time.time()
        time_since_last = now - _last_api_request_time
        if time_since_last < delay:
            sleep_time = delay - time_since_last
            print(f"[AI Router] Ожидание {sleep_time:.2f}с (лимит {rpm} RPM)...")
            time.sleep(sleep_time)
            _last_api_request_time = time.time()
        else:
            _last_api_request_time = now

def _call_google_text(api_key: str, model_cap: ModelCapabilities, prompt: str) -> GenerationResult:
    client = genai.Client(api_key=api_key)
    from google.genai import types
    response = client.models.generate_content(
        model=model_cap.api_model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GenerationResult,
            temperature=0.7,
        ),
    )
    data = json.loads(response.text)
    return GenerationResult(**data)

def _call_openai_compatible_text(api_key: str, model_cap: ModelCapabilities, prompt: str, base_url: str) -> GenerationResult:
    groq_prompt = f"{prompt}\n\nВАЖНО: Отвечай СТРОГО в формате JSON следующей структуры. Не пиши никаких вводных слов, только чистый JSON:\n"
    groq_prompt += '{\n  "voice_text": "Текст для озвучки",\n  "image_keywords": ["слово1", "слово2"],\n  "video_title": "Заголовок",\n  "video_description": "Описание",\n  "video_tags": "тег1, тег2"\n}'
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # OpenRouter specific headers
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "http://localhost:8000"
        headers["X-Title"] = "Auto Shorts"
        
    data = {
        "model": model_cap.api_model_name,
        "messages": [
            {"role": "system", "content": "Ты полезный ассистент, который всегда отвечает в формате JSON."},
            {"role": "user", "content": groq_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7
    }
    
    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code} - {response.text}")
        
    result = response.json()
    text = result["choices"][0]["message"]["content"]
    
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    
    parsed_data = json.loads(text.strip())
    return GenerationResult(**parsed_data)

def _call_google_vision(api_key: str, model_cap: ModelCapabilities, image_path: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    from PIL import Image
    img = Image.open(image_path)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
        
    response = client.models.generate_content(
        model=model_cap.api_model_name,
        contents=[prompt, img],
    )
    return response.text.strip().lower()

def _call_openai_compatible_vision(api_key: str, model_cap: ModelCapabilities, image_path: str, prompt: str, base_url: str) -> str:
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
    # Определяем MIME-тип
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/jpeg"
    if ext == ".png": mime_type = "image/png"
    elif ext == ".webp": mime_type = "image/webp"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "http://localhost:8000"
        headers["X-Title"] = "Auto Shorts"
        
    data = {
        "model": model_cap.api_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"}}
                ]
            }
        ],
        "temperature": 0.3
    }
    
    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code} - {response.text}")
        
    result = response.json()
    return result["choices"][0]["message"]["content"].strip().lower()


def route_generation(
    task_type: str, 
    gemini_models_str: str, gemini_key: str,
    groq_models_str: str, groq_key: str,
    openrouter_models_str: str, openrouter_key: str,
    rpm: int, prompt: str, image_path: str = None
) -> Any:
    """
    Универсальный шлюз (Router) для задач генерации текста и модерации картинок.
    task_type: "text" или "vision"
    """
    # 1. Формируем список моделей (Склеиваем строго: Google -> Groq -> OpenRouter)
    raw_models = []
    
    if gemini_models_str and gemini_key:
        for m in gemini_models_str.replace(',', '\n').split('\n'):
            if m.strip(): raw_models.append((m.strip(), "google"))
            
    if groq_models_str and groq_key:
        for m in groq_models_str.replace(',', '\n').split('\n'):
            if m.strip(): raw_models.append((m.strip(), "groq"))
            
    if openrouter_models_str and openrouter_key:
        for m in openrouter_models_str.replace(',', '\n').split('\n'):
            if m.strip(): raw_models.append((m.strip(), "openrouter"))
            
    # 2. Фильтруем модели по capabilities
    valid_models = []
    for m_name, provider in raw_models:
        cap = parse_model_string(m_name, provider)
        if task_type == "text" and not cap.can_text: continue
        if task_type == "vision" and not cap.can_vision: continue
        valid_models.append(cap)
        
    if not valid_models:
        raise Exception(f"В списке нет ни одной активной модели, поддерживающей задачу типа '{task_type}'")

    # 3. Определяем стартовую модель (из глобального стейта)
    current_global = get_current_model()
    start_index = 0
    for i, cap in enumerate(valid_models):
        if cap.name == current_global:
            start_index = i
            break
            
    last_error = None
    
    # 4. Ротация моделей
    for offset in range(len(valid_models)):
        idx = (start_index + offset) % len(valid_models)
        cap = valid_models[idx]
        
        # Обновляем UI
        set_current_model(cap.name)
        
        # Проверяем наличие ключа для провайдера
        if cap.provider == "google":
            active_key = gemini_key
            base_url = None
        elif cap.provider == "groq":
            active_key = groq_key
            base_url = "https://api.groq.com/openai/v1"
        else:
            active_key = openrouter_key
            base_url = "https://openrouter.ai/api/v1"
            
        if offset == 0:
            _enforce_rate_limit(rpm)
        
        try:
            if task_type == "text":
                if cap.provider == "google":
                    return _call_google_text(active_key, cap, prompt)
                else:
                    return _call_openai_compatible_text(active_key, cap, prompt, base_url)
                    
            elif task_type == "vision":
                if cap.provider == "google":
                    res = _call_google_vision(active_key, cap, image_path, prompt)
                else:
                    res = _call_openai_compatible_vision(active_key, cap, image_path, prompt, base_url)
                    
                if "да" in res or "yes" in res:
                    return True, res
                else:
                    return False, res
                    
        except Exception as e:
            error_str = str(e)
            last_error = e
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            reason = "Лимит" if is_rate_limit else "Ошибка"
            
            print(f"[AI Router] {reason} на {cap.name} ({error_str[:60]}). Пробуем следующую...")
            set_status(f"{reason} {cap.name}, переключаюсь...")
            
            if offset == len(valid_models) - 1:
                print(f"[AI Router] Все подходящие модели ({len(valid_models)} шт.) недоступны.")
                if task_type == "vision":
                    return True, "Rate limits exhausted on all models"
                raise Exception("Все модели недоступны: " + str(last_error))
            continue
            
    if task_type == "vision":
        return True, "No valid models executed"
    raise Exception("Не удалось сгенерировать текст: " + str(last_error))
