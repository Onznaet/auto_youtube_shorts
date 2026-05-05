import os
import subprocess
from PIL import Image, ImageFilter
from services.status_manager import set_status
from tinytag import TinyTag
import imageio_ffmpeg

def resize_and_crop(image_path: str, target_width: int, target_height: int, output_path: str):
    """
    Эстетичная обработка:
    - Для Shorts (9:16) картинка не обрезается жестко, а масштабируется по ширине.
      Сверху и снизу добавляется размытый фон из этой же картинки (эффект TikTok/Shorts).
    - Для длинных видео (16:9) остается обрезка по центру, так как исходники обычно тоже 16:9.
    """
    img = Image.open(image_path).convert('RGB')
    
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height
    
    if abs(img_ratio - target_ratio) < 0.1:
        # Почти совпадает
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    elif target_width < target_height:
        # Формат Shorts (вертикальный). Применяем эффект размытого фона!
        # 1. Растягиваем и обрезаем для фона
        bg_height = target_height
        bg_width = int(bg_height * img_ratio)
        bg = img.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
        left = (bg_width - target_width) // 2
        bg = bg.crop((left, 0, left + target_width, target_height))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
        
        # 2. Подгоняем картинку целиком по ширине
        fg_width = target_width
        fg_height = int(fg_width / img_ratio)
        fg = img.resize((fg_width, fg_height), Image.Resampling.LANCZOS)
        
        # 3. Накладываем картинку по центру размытого фона
        top = (target_height - fg_height) // 2
        bg.paste(fg, (0, top))
        img = bg
    else:
        # Формат стандартного видео (горизонтальный)
        if img_ratio > target_ratio:
            new_height = target_height
            new_width = int(new_height * img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - target_width) // 2
            img = img.crop((left, 0, left + target_width, target_height))
        else:
            new_width = target_width
            new_height = int(new_width / img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            top = (new_height - target_height) // 2
            img = img.crop((0, top, target_width, top + target_height))
        
    img.save(output_path, "JPEG", quality=95)
    return output_path

def assemble_video(task_id: int, image_paths: list[str], voice_path: str, video_format: str, output_dir: str = "media_cache", music_path: str = None, music_volume: int = 30, image_zoom: int = 5, watermark_path: str = None, run_id: str = None, custom_filename: str = "final_video.mp4") -> str:
    """
    Склеивает скачанные картинки и сгенерированный голос в один .mp4 файл, используя FFMPEG напрямую!
    Поддерживает плавное увеличение (Ken Burns effect).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder_name = f"task_{run_id}" if run_id else f"task_{task_id}"
    task_dir = os.path.join(base_dir, output_dir, folder_name)
    processed_dir = os.path.join(task_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    
    output_video_path = os.path.join(task_dir, custom_filename)
    
    if "16:9" in video_format or "HORIZONTAL" in video_format:
        target_w, target_h = 1920, 1080
    else:
        target_w, target_h = 1080, 1920
        
    set_status("Подготовка аудио-дорожки...")
    audio_tag = TinyTag.get(voice_path)
    total_duration = audio_tag.duration
    
    if not image_paths:
        raise ValueError("Нет картинок для сборки видео!")
        
    duration_per_image = total_duration / len(image_paths)
    
    set_status(f"Обработка {len(image_paths)} картинок под формат {target_w}x{target_h}...")
    processed_paths = []
    
    for i, img_path in enumerate(image_paths):
        processed_path = os.path.join(processed_dir, f"frame_{i:03d}.jpg")
        try:
            # Чтобы не было дрожания пикселей при зуме (FFmpeg zoompan jitter bug),
            # мы подготавливаем картинки в двукратном разрешении!
            if image_zoom > 0:
                resize_and_crop(img_path, target_w * 2, target_h * 2, processed_path)
            else:
                resize_and_crop(img_path, target_w, target_h, processed_path)
            processed_paths.append(processed_path)
        except Exception as e:
            print(f"Ошибка обработки {img_path}: {e}")
            continue
            
    if not processed_paths:
        raise ValueError("Все картинки повреждены!")
        
    # Создаем файл списка для ffmpeg concat demuxer (нужен только если нет зума)
    images_txt_path = os.path.join(task_dir, "images.txt")
    with open(images_txt_path, "w", encoding="utf-8") as f:
        for i, p in enumerate(processed_paths):
            safe_path = p.replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
            if i == len(processed_paths) - 1:
                # Секретный фикс FFmpeg: добавляем пару секунд к последнему кадру
                f.write(f"duration {duration_per_image + 2.0}\n")
            else:
                f.write(f"duration {duration_per_image}\n")
        safe_path = processed_paths[-1].replace('\\', '/')
        f.write(f"file '{safe_path}'\n")
        
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-y"]
    filter_complex = []
    
    input_idx = 0
    has_watermark = watermark_path and os.path.exists(watermark_path)
    
    if image_zoom > 0:
        set_status(f"Сборка видео (эффект зума {image_zoom}%)...")
        zoom_factor = image_zoom / 100.0
        
        for i, p in enumerate(processed_paths):
            dur = duration_per_image + 2.0 if i == len(processed_paths) - 1 else duration_per_image
            cmd.extend(["-i", p])
            # Рендерим зум в 50fps в двойном разрешении,
            # Блендим соседние кадры (tmix) для натурального motion blur, понижаем до 25fps и сжимаем lanczos
            frames_50 = int(50 * dur)
            filter_complex.append(f"[{input_idx}:v]zoompan=z='1.0+(on/{frames_50})*{zoom_factor}':d={frames_50}:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s={target_w*2}x{target_h*2}:fps=50,tmix=frames=2,fps=25,scale={target_w}:{target_h}:flags=lanczos[v{input_idx}]")
            input_idx += 1
            
        concat_inputs = "".join([f"[v{i}]" for i in range(len(processed_paths))])
        filter_complex.append(f"{concat_inputs}concat=n={len(processed_paths)}:v=1:a=0[vout_base]")
    else:
        set_status("Сборка видео (статичные картинки)...")
        cmd.extend(["-f", "concat", "-safe", "0", "-i", images_txt_path])
        filter_complex.append(f"[{input_idx}:v]null[vout_base]")
        input_idx += 1
        
    voice_idx = input_idx
    cmd.extend(["-i", voice_path])
    input_idx += 1
    
    if music_path and os.path.exists(music_path):
        music_idx = input_idx
        # Ограничиваем длину зацикленной музыки длиной голоса + 2 сек, чтобы она не была бесконечной
        music_dur_limit = total_duration + 2.0
        cmd.extend(["-stream_loop", "-1", "-t", str(music_dur_limit), "-i", music_path])
        vol_float = max(0.0, min(1.0, music_volume / 100.0))
        # Плавно затухаем музыку за 2 секунды до конца
        filter_complex.append(f"[{voice_idx}:a]volume=2.0[a1];[{music_idx}:a]volume={vol_float},afade=t=out:st={total_duration}:d=2[a2];[a1][a2]amix=inputs=2:duration=longest:normalize=0[aout]")
        audio_map = "[aout]"
        input_idx += 1
    else:
        filter_complex.append(f"[{voice_idx}:a]volume=2.0[aout]")
        audio_map = "[aout]"
        
    if has_watermark:
        wm_idx = input_idx
        cmd.extend(["-loop", "1", "-i", watermark_path])
        # Накладываем вотермарку строго по центру. shortest=1 означает, что бесконечный loop закончится вместе с видео
        filter_complex.append(f"[vout_base][{wm_idx}:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:shortest=1[vout]")
        input_idx += 1
    else:
        filter_complex.append("[vout_base]null[vout]")
        
    cmd.extend([
        "-filter_complex", ";".join(filter_complex),
        "-map", "[vout]",
        "-map", audio_map,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        # Мы специально УДАЛИЛИ -shortest, так как он багованый и отрезает последние 4 секунды видео.
        # Теперь все потоки строго ограничены по длине программно!
        output_video_path
    ])
    
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    set_status("Видео успешно сгенерировано через FFmpeg!")
    return output_video_path
