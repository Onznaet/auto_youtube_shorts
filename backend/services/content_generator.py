import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from services.status_manager import set_status, get_current_model, set_current_model
from services.llm_service import route_generation, GenerationResult
import time
import threading

def generate_video_content(
    gemini_api_key: str, 
    gemini_models_str: str,
    groq_api_key: str,
    groq_models_str: str,
    openrouter_api_key: str,
    openrouter_models_str: str,
    news_text: str, 
    duration: int = 30, 
    custom_prompt: str = None, 
    image_count: int = 5, 
    allow_mock: bool = True, 
    api_requests_per_minute: int = 3
) -> GenerationResult:
    """Генерирует голос, теги, SEO и ключевые слова для видео"""
    
    if not gemini_api_key and not groq_api_key and not openrouter_api_key:
        raise ValueError("Не указан ни один API Key для ИИ")

    base_prompt = f"""
    Ты профессиональный сценарист для YouTube. Твоя задача обработать следующую новость.
    Сделай выжимку самого главного и интересного для озвучки ролика.
    ВАЖНО: Твоя задача — объективно и нейтрально пересказать новость, убрав любые манипуляции, кликбейт и оценочные суждения автора статьи. Излагай только факты.
    ВАЖНО: Ориентировочная длительность ролика должна составлять {duration} секунд.
    Постарайся написать текст такой длины, чтобы при нормальном темпе чтения (около 2 слов в секунду) диктор уложился ровно в это время.
    Если запрошенная длительность большая (более 60 секунд), добавляй больше подробностей из текста, контекста и аналитики, чтобы текста хватило. Если текста новости мало, добавь нейтральную историческую справку по теме.
    ВАЖНО: Текст для озвучки, заголовок и описание должны быть СТРОГО на РУССКОМ языке.
    Сгенерируй кликбейтный заголовок, краткое описание ролика (1-2 предложения), а также большой список тегов (не менее 15 штук) через запятую. Хештеги добавь в конец описания. Теги и хештеги строго на русском.
    ВАЖНО: Выдели ровно {image_count} ключевых слов (или словосочетаний) для поиска картинок. Они также должны быть на РУССКОМ языке. Эти слова должны соответствовать хронологии текста, чтобы картинки менялись в тему по мере рассказа.
    """
    
    if custom_prompt:
        try:
            base_prompt = custom_prompt.replace("{duration}", str(duration)).replace("{image_count}", str(image_count))
        except Exception:
            base_prompt = custom_prompt
            
    prompt = f"{base_prompt}\n\nНОВОСТЬ:\n{news_text}"

    try:
        result = route_generation(
            task_type="text",
            gemini_models_str=gemini_models_str,
            gemini_key=gemini_api_key,
            groq_models_str=groq_models_str,
            groq_key=groq_api_key,
            openrouter_models_str=openrouter_models_str,
            openrouter_key=openrouter_api_key,
            rpm=api_requests_per_minute,
            prompt=prompt
        )
        set_status("Успешная генерация!")
        return result
    except Exception as e:
        last_error = e
        if allow_mock:
            print(f"⚠️ Ошибка генерации. Используем заглушку... ({str(last_error)})")
            return GenerationResult(
                voice_text=f"Привет! Это тестовое сгенерированное видео на {duration} секунд. Нейросеть не смогла выдать правильный ответ, скорее всего из-за слишком большой длительности или лимита запросов. Но мы всё равно можем проверить, как работает склейка картинок и музыки!",
                image_keywords=["абстракция", "технологии", "ошибка", "фон", "заглушка"],
                video_title="Тестовое Видео (Сбой API План Б)",
                video_description="Это видео создано автоматически в режиме заглушки.",
                video_tags="тест, автоматизация, сбой"
            )
        raise last_error
