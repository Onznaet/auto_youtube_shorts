import os
import requests
from typing import Optional, Tuple

def upload_video_telegram(file_path: str, caption: str, bot_token: str, chat_id: str) -> Tuple[bool, Optional[str]]:
    """
    Загружает видео в Telegram через Bot API.
    Возвращает (Успех(bool), Сообщение об ошибке/результат(str)).
    """
    if not bot_token or not chat_id:
        return False, "Не указан токен бота или ID канала в настройках проекта."
        
    if not os.path.exists(file_path):
        return False, f"Файл не найден: {file_path}"
        
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    # Telegram API has a caption length limit of 1024 characters
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
        
    try:
        with open(file_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'HTML' # Optional: You can format tags with HTML if needed
            }
            
            # Use a longer timeout for uploading videos
            response = requests.post(url, files=files, data=data, timeout=300)
            
            result = response.json()
            if result.get("ok"):
                return True, "Успешно отправлено в Telegram"
            else:
                error_msg = result.get("description", "Неизвестная ошибка Telegram API")
                return False, f"Ошибка Telegram API: {error_msg}"
                
    except requests.exceptions.RequestException as e:
        return False, f"Сетевая ошибка при отправке в Telegram: {str(e)}"
    except Exception as e:
        return False, f"Внутренняя ошибка отправки в Telegram: {str(e)}"
