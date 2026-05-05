import os
import edge_tts
import asyncio
import requests
from services.status_manager import set_status, get_current_voice_engine, set_current_voice_engine
from database import SessionLocal
from services.config_service import ConfigService

async def _generate_voice_async(text: str, voice: str, output_path: str, rate: str = '+0%'):
    """Асинхронная генерация голоса с помощью edge-tts"""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

def generate_voice(task_id: int, text: str, voice: str, video_format: str, output_dir: str = "media_cache", run_id: str = None, cta_text: str = None) -> str:
    """
    Генерирует голосовую озвучку для задачи и сохраняет в media_cache/task_{task_id}/voice.mp3.
    Возвращает абсолютный путь к файлу.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder_name = f"task_{run_id}" if run_id else f"task_{task_id}"
    task_dir = os.path.join(base_dir, output_dir, folder_name)
    os.makedirs(task_dir, exist_ok=True)
    
    output_path = os.path.join(task_dir, "voice.mp3")
    
    # Удаляем абзацы (энтеры)
    clean_text = text.replace('\n', ' ').replace('  ', ' ')
    
    is_shorts = "VERTICAL" in video_format
    rate = '+10%' if is_shorts else '+0%'
    
    # Извлекаем конфигурации
    db_local = SessionLocal()
    try:
        config = ConfigService(db_local)
        yandex_api_key = config.get("yandex_api_key")
        yandex_folder_id = config.get("yandex_folder_id")
        voice_engines_str = config.get("voice_engines", "edge-tts\nyandex-speechkit")
        yandex_male = config.get("yandex_voice_male", "filipp").strip().lower()
        yandex_female = config.get("yandex_voice_female", "alena").strip().lower()
        
        # Маппинг русских имен в английские идентификаторы API
        ru_to_en = {
            "кирилл": "kirill", "филипп": "filipp", "захар": "zahar", 
            "ермил": "ermil", "антон": "anton", "александр": "alexander", "мади": "madi_ru",
            "алена": "alena", "алёна": "alena", "джейн": "jane", 
            "омаж": "omazh", "даша": "dasha", "юля": "julia", "лера": "lera", 
            "марина": "marina", "маша": "masha"
        }
        yandex_male = ru_to_en.get(yandex_male, yandex_male)
        yandex_female = ru_to_en.get(yandex_female, yandex_female)
        
    finally:
        db_local.close()
        
    engines = [e.strip() for e in voice_engines_str.replace(',', '\n').split('\n') if e.strip()]
    if not engines:
        engines = ["edge-tts"]
        
    current_engine = get_current_voice_engine()
    if current_engine not in engines:
        current_engine = engines[0]
        set_current_voice_engine(current_engine)
        
    # Смещаем список чтобы начать с current_engine
    start_idx = engines.index(current_engine)
    engines_to_try = engines[start_idx:] + engines[:start_idx]
    
    last_error = None
    
    for engine in engines_to_try:
        set_current_voice_engine(engine)
        set_status(f"Генерация озвучки диктором {voice} (через {engine})...")
        
        try:
            if engine == "edge-tts":
                edge_text = clean_text
                if is_shorts:
                    # Алгоритм "плотного чтения" только для Shorts
                    text_to_process = edge_text
                    cta_suffix = ""
                    if cta_text:
                        clean_cta = cta_text.replace('\n', ' ').replace('  ', ' ').strip()
                        if clean_cta and edge_text.endswith(clean_cta):
                            main_part = edge_text[:-len(clean_cta)].strip()
                            if main_part.endswith(','): main_part = main_part[:-1] + '.'
                            elif not main_part.endswith('.'): main_part += '.'
                            text_to_process = main_part
                            cta_suffix = " " + clean_cta
                            
                    text_to_process = text_to_process.replace('.', ',')
                    words = text_to_process.split()
                    words_per_breath = 40
                    target_indices = [i for i in range(words_per_breath, len(words), words_per_breath)]
                    for target in target_indices:
                        best_idx = -1
                        for offset in range(15):
                            if target - offset >= 0 and words[target - offset].endswith(','):
                                best_idx = target - offset
                                break
                            if target + offset < len(words) and words[target + offset].endswith(','):
                                best_idx = target + offset
                                break
                        if best_idx != -1: words[best_idx] = words[best_idx][:-1] + '.'
                        else:
                            if words[target].endswith(','): words[target] = words[target][:-1] + '.'
                            else: words[target] = words[target] + '.'
                            
                    edge_text = ' '.join(words)
                    if edge_text.endswith(','): edge_text = edge_text[:-1] + '.'
                    elif not edge_text.endswith('.'): edge_text += '.'
                    if cta_suffix: edge_text += cta_suffix
                    
                is_male = voice == 'male' or 'Dmitry' in voice or 'Mael' in voice or 'Christopher' in voice or 'Guy' in voice or 'Eric' in voice
                edge_voice = 'ru-RU-DmitryNeural' if is_male else 'ru-RU-SvetlanaNeural'
                asyncio.run(_generate_voice_async(edge_text, edge_voice, output_path, rate=rate))
                set_status(f"Озвучка успешно сохранена (edge-tts)!")
                return output_path
                
            elif engine == "yandex-speechkit":
                if not yandex_api_key or not yandex_folder_id:
                    raise Exception("Для Yandex SpeechKit не указан API-ключ или Folder ID в настройках")
                
                # Голоса Яндекса из настроек (или по умолчанию)
                is_male = voice == 'male' or 'Dmitry' in voice or 'Mael' in voice or 'Christopher' in voice or 'Guy' in voice or 'Eric' in voice
                yandex_voice = yandex_male if is_male else yandex_female
                # Yandex rate не поддерживается в таком простом виде без SSML, но мы можем попытаться
                
                url = 'https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis'
                headers = {
                    'Authorization': f'Api-Key {yandex_api_key}',
                    'x-folder-id': yandex_folder_id,
                    'Content-Type': 'application/json'
                }
                data = {
                    "text": clean_text,
                    "unsafeMode": True,
                    "outputAudioSpec": {
                        "containerAudio": {"containerAudioType": "MP3"}
                    },
                    "hints": [
                        {"voice": yandex_voice}
                    ]
                }
                
                res = requests.post(url, headers=headers, json=data, stream=True, timeout=60)
                if res.status_code == 200:
                    import json
                    import base64
                    with open(output_path, "wb") as f:
                        for line in res.iter_lines():
                            if line:
                                chunk = json.loads(line)
                                if "result" in chunk:
                                    chunk = chunk["result"]
                                if "audioChunk" in chunk and "data" in chunk["audioChunk"]:
                                    f.write(base64.b64decode(chunk["audioChunk"]["data"]))
                    set_status(f"Озвучка успешно сохранена (yandex-speechkit v3)!")
                    return output_path
                else:
                    raise Exception(f"Ошибка API Яндекса: {res.text}")
                    
            else:
                raise Exception(f"Неизвестный движок озвучки: {engine}")
                
        except Exception as e:
            last_error = e
            print(f"Ошибка движка {engine}: {e}")
            set_status(f"Сбой {engine}, переключаемся на следующий... ({str(e)[:40]})")
            import time
            time.sleep(3) # Даем пользователю время прочитать ошибку в UI
            
    set_status(f"Все движки озвучки недоступны. Последняя ошибка: {str(last_error)[:50]}")
    raise last_error
