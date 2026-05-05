import os
from services.llm_service import route_generation

def moderate_image(
    gemini_api_key: str, 
    gemini_models_str: str,
    groq_api_key: str,
    groq_models_str: str,
    openrouter_api_key: str,
    openrouter_models_str: str,
    rpm: int, 
    image_path: str, 
    query: str, 
    prompt: str
) -> tuple[bool, str]:
    """
    Отправляет картинку в AI Router для проверки на мусор/вотермарки.
    """
    if not gemini_api_key and not groq_api_key and not openrouter_api_key:
        print("[AI Модератор] Пропуск (не указан ни один API Key)")
        return True, "No API key"
        
    if not os.path.exists(image_path):
        return False, "File not found"
        
    formatted_prompt = prompt.replace("{query}", query)
    
    try:
        is_valid, reason = route_generation(
            task_type="vision",
            gemini_models_str=gemini_models_str,
            gemini_key=gemini_api_key,
            groq_models_str=groq_models_str,
            groq_key=groq_api_key,
            openrouter_models_str=openrouter_models_str,
            openrouter_key=openrouter_api_key,
            rpm=rpm,
            prompt=formatted_prompt,
            image_path=image_path
        )
        return is_valid, reason
    except Exception as e:
        print(f"[AI Модератор] Критическая ошибка: {e}")
        return True, f"Critical Error: {e}"
