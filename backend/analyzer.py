import time
import json
import logging
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
import imageio_ffmpeg
from config import get_gemini_api_key, DATA_DIR
import database
from rally_detector import detect_active_rallies, anchor_and_refine_analysis

logger = logging.getLogger("analyzer")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT_TEMPLATE = """
Eres el Director Creativo de Contenido Viral y Analista Elite de Pickleball para las plataformas líderes en redes sociales (Instagram Reels, TikTok, YouTube Shorts y Facebook Reels).

TU OBJETIVO PRINCIPAL:
Transformar grabaciones brutas de Pickleball en contenido VIRAL DE ALTO IMPACTO (High Engagement) que maximice la retención de audiencia (Watch Time), dispare los comentarios (Debates/Controversia táctica) y logre miles de me gustas y compartidos.

METODOLOGÍA DE VIRALIDAD ALGORÍTMICA BASADA EN INVESTIGACIÓN:
1. EL GANCHO INICIAL (0 a 3 SEGUNDOS - HOOK DE RETENCIÓN):
   - El 80% del éxito en Reels/TikTok depende de los primeros 3 segundos.
   - El texto inicial DEBE generar curiosidad, tensión o anticipación (ej: "¡Espera la reacción a quemarropa en la cocina... ⚡😱", "Nadie esperaba lo que hizo en el segundo 4... 👀").
2. IDENTIFICACIÓN DE ARQUETIPOS VIRALES EN PICKLEBALL:
   Debes buscar e identificar si ocurren estos patrones virales de alta conversión:
   - "Firefight / Kitchen Hand Battle" (intercambio ultra rápido de voleas).
   - "Body Bag / Chest Tag" (pelotazo táctico cuerpo a cuerpo en la red).
   - "ATP (Around The Post)" (tiro magistral por fuera del poste).
   - "The Erne / Bert" (salto acrobático por fuera de la línea de cocina).
   - "Nasty Nelson" (saque intencional directo al cuerpo del rival no receptor).
   - "Scorpion / Tweener" (defensa o contraataque reflejo en posición baja).
   - "Miracle Reset" (salvada épica desde la línea de fondo).
   - "Kitchen Foot Fault Drama" (polémica si el pie tocó o invadió la cocina).
3. DISPARADOR DE ALGORITMO (CALL TO ACTION DE DEBATE EN COMENTARIOS):
   - Los algoritmos premian los videos con más comentarios. El CTA y el texto final DEBEN formular una pregunta divisiva o de opinión directa (ej: "¿Fue invasión de cocina o punto limpio? Comenta abajo 👇🎾", "¿Habrías alcanzado ese remate o te rendías? 👇").

REGLAS OBLIGATORIAS DE PRECISIÓN MILIMÉTRICA DE TIEMPOS:
1. PRECISIÓN TEMPORAL ABSOLUTA: Debes cronometrar con exactitud de segundo real cada acción. Cada fotograma del video tiene impreso un reloj digital TIMECODE (00:MM:SS:FF) en la esquina superior izquierda. El segundo de inicio ('start_time' y 'start_seconds') es el segundo EXACTO en que la paleta golpea la pelota en el saque o comienzo del rally. El segundo final ('end_time' y 'end_seconds') es el segundo EXACTO en que la pelota pica en el piso o se concluye el punto.
2. DISCRIMINACIÓN DE TIEMPO MUERTO: Si en un tramo de tiempo los jugadores están caminando, descansando, acomodándose o conversando, identifícalo explícitamente en 'mistakes_or_issues' y 'dead_time_cut_advice' para recortarlo. NUNCA ubiques una jugada clave en un momento sin pelota en juego.
3. COHERENCIA DE TOMAS EN CAPCUT: Las tomas del guion de CapCut deben coincidir exactamente con los segundos reales del rally destacado:
   - Toma 1 (Hook): Desde el saque o primera devolución hasta la subida a la cocina.
   - Toma 2 (Clímax): El intercambio rápido en la red (dinks/voleas).
   - Toma 3 (Desenlace): El remate ganador o error forzado + Congelado de imagen y Call to Action.

Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:
{
  "title": "Título corto, dinámico y periodístico del video",
  "people_count": 4,
  "players_description": "Descripción visual detallada: vestimenta, colores, gorras y roles de los jugadores y público",
  "game_format": "Dobles (2 vs 2) o Singles (1 vs 1)",
  "camera_setup": "Ubicación y ángulo de cámara (ej: Trasera fija a ras de cancha, Elevada, Lateral)",
  "video_quality": "Excelente / Buena / Regular",
  "audio_analysis": "Análisis del paisaje sonoro: golpes secos de paleta (pop), chirrido de suelas, cantos de puntos y ovaciones",
  "actions_summary": "Crónica cronológica precisa con marcas de tiempo (ej: 00:15-00:30) detallando saques, transiciones, dinks y remates",
  "pickleball_techniques": ["Dinks", "Saques", "Voleas de bloqueo", "Remates", "Third shot drops", "Speed-ups", "Resets"],
  "highlights": "La jugada maestra del video indicando minuto y segundo exacto",
  "mistakes_or_issues": "Marcas de tiempo exactas de momentos muertos o calentamiento que deben eliminarse antes de publicar",
  "point_outcome_reason": "Razón táctica exacta de cómo y por qué se ganó/perdió el punto clave (ej: Error no forzado en red, Falta en la cocina, Flotada regalada por mal dink, Remate inalcanzable)",
  "classification_tag": "⭐ Destacado para Redes / Reels",
  "decision_recommendation": "Recomendación editorial clara sobre qué hacer con este metraje",
  "confidence_score": 95,
  "viral_score": 96,
  "viral_archetypes": ["Firefight / Kitchen Hand Battle", "ATP (Around The Post)", "The Erne / Bert", "Body Bag / Chest Tag", "Nasty Nelson", "Scorpion / Tweener", "Miracle Reset", "Kitchen Foot Fault Drama"],
  "viral_clip": {
    "start_time": "01:48",
    "end_time": "02:04",
    "start_seconds": 108,
    "end_seconds": 124,
    "duration_seconds": 16,
    "hook_caption_es": "Espera a la batalla de manos en la cocina... ⚡😱",
    "hook_caption_en": "Wait for the fastest hand battle at the net... ⚡",
    "suggested_hashtags": ["#pickleball", "#kitchenbattle", "#dinking", "#pickleballhighlights", "#reels"],
    "dead_time_cut_advice": "Eliminar desde 00:00 hasta 01:47 (calentamiento y acomodo) para retención máxima del 100%"
  },
  "capcut_recommendation": {
    "title": "Recomendación de Edición en CapCut",
    "target_platforms": ["Instagram Reels", "TikTok", "YouTube Shorts", "Facebook Reels"],
    "aspect_ratio": "9:16 (Vertical)",
    "sound_suggestion": "Audio de tendencia enérgico o audio original amplificando el golpe seco 'pop' de la bola",
    "timeline_steps": [
      {
        "step_number": 1,
        "action": "Gancho Inicial (Hook)",
        "timestamp": "01:48 - 01:51",
        "duration": "3s",
        "on_screen_text": "¡Espera lo que pasa en la red! 😱👇",
        "on_screen_text_en": "Wait for what happens at the kitchen line! 😱👇",
        "text_style": "Fuente Sans Bold en amarillo/blanco con borde negro",
        "effect_or_transition": "Corte rápido al saque + Zoom suave hacia la bola",
        "capcut_tool": "Dividir + Texto > Plantillas + Zoom"
      },
      {
        "step_number": 2,
        "action": "Desarrollo / Rally intenso",
        "timestamp": "01:51 - 01:59",
        "duration": "8s",
        "on_screen_text": "¡Manos rápidas en la cocina! ⚡🔥",
        "on_screen_text_en": "Lightning fast hands at the kitchen line! ⚡🔥",
        "text_style": "Texto flotante superior sin tapar a los jugadores",
        "effect_or_transition": "Velocidad Curva (Curva > Montaje) para enfatizar cada volea",
        "capcut_tool": "Velocidad > Curva + Subtítulos automáticos"
      },
      {
        "step_number": 3,
        "action": "Desenlace / Remate y CTA",
        "timestamp": "01:59 - 02:04",
        "duration": "5s",
        "on_screen_text": "¿Fue falta en la cocina? Comenta abajo 👇🎾",
        "on_screen_text_en": "Clean volley or kitchen foot fault? Comment below 👇🎾",
        "text_style": "Sticker de flecha señalando + Texto CTA grande",
        "effect_or_transition": "Congelar fotograma (0.5s) al rematar + Efecto de sonido Whoosh",
        "capcut_tool": "Efectos de audio > Whoosh + Congelar"
      }
    ],
    "call_to_action": "¿Punto limpio o invasión de cocina? ¿Tú qué hubieras hecho? Comenta abajo 👇",
    "call_to_action_en": "Clean point or foot fault at the kitchen line? What would you do? Comment below 👇",
    "export_settings": "1080p, 60fps / 30fps, Tasa de bits recomendada, Relación 9:16"
  }
}
"""

def optimize_video_for_ai(input_path: Path) -> Path:
    """
    Compresses high-bitrate/heavy videos (like 4K/60fps iPhone MOV) to a 720p 24fps
    lightweight MP4 (~10-15MB) for ultra-fast cloud upload and processing.
    """
    size_mb = input_path.stat().st_size / (1024 * 1024)
    if size_mb < 25 and input_path.suffix.lower() == ".mp4":
        return input_path

    temp_dir = DATA_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    opt_path = temp_dir / f"opt_{input_path.stem}.mp4"
    if opt_path.exists():
        return opt_path

    logger.info(f"Optimizando video pesado {input_path.name} ({round(size_mb, 1)} MB)...")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    cmd = [
        ffmpeg, "-y",
        "-i", str(input_path),
        "-vf", "scale=-2:720,drawtext=text='%{pts\\:hms}':fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.8:x=20:y=20",
        "-r", "24",
        "-c:v", "libx264",
        "-crf", "26",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        str(opt_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    new_size_mb = opt_path.stat().st_size / (1024 * 1024)
    logger.info(f"Optimización completada: {round(size_mb, 1)} MB -> {round(new_size_mb, 1)} MB")
    return opt_path

def ensure_capcut_recommendation(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures analysis dictionary contains a comprehensive, step-by-step
    CapCut editing script for Reels, TikTok, Shorts and Facebook.
    """
    if not analysis:
        return analysis

    if "capcut_recommendation" in analysis and analysis["capcut_recommendation"].get("timeline_steps"):
        return analysis

    clip = analysis.get("viral_clip") or {}
    start_time = clip.get("start_time", "00:00")
    end_time = clip.get("end_time", "00:15")
    hook_es = clip.get("hook_caption_es") or "¡Espera lo que pasa en la red! 😱👇"

    def to_secs(ts_str: str) -> int:
        try:
            parts = ts_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0

    s_sec = clip.get("start_seconds") or to_secs(start_time)
    e_sec = clip.get("end_seconds") or to_secs(end_time)
    duration = max(6, e_sec - s_sec)

    step1_dur = max(2, min(4, duration // 3))
    step3_dur = max(2, min(5, duration // 4))
    step1_end = s_sec + step1_dur
    step2_end = max(step1_end + 2, e_sec - step3_dur)

    def format_ts(sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    analysis["capcut_recommendation"] = {
        "title": "Recomendación de Edición en CapCut",
        "target_platforms": ["Instagram Reels", "TikTok", "YouTube Shorts", "Facebook Reels"],
        "aspect_ratio": "9:16 (Vertical centrado en la acción)",
        "sound_suggestion": "Audio de tendencia rítmico en CapCut + Audio original al 150% para amplificar el 'pop' del impacto",
        "timeline_steps": [
            {
                "step_number": 1,
                "action": "Toma 1: Gancho Inicial (Hook de retención)",
                "timestamp": f"{format_ts(s_sec)} - {format_ts(step1_end)}",
                "duration": f"{step1_end - s_sec}s",
                "on_screen_text": hook_es,
                "text_style": "Fuente Sans Bold en amarillo/blanco con borde negro y fondo translúcido",
                "effect_or_transition": "Corte rápido al saque + Zoom suave (1.1x) hacia el jugador que golpea",
                "capcut_tool": "Herramienta 'Dividir' + 'Texto > Plantillas de texto' + Zoom de encuadre"
            },
            {
                "step_number": 2,
                "action": "Toma 2: Desarrollo y Batalla de Voleas (Clímax)",
                "timestamp": f"{format_ts(step1_end)} - {format_ts(step2_end)}",
                "duration": f"{step2_end - step1_end}s",
                "on_screen_text": "¡Manos de fuego en la cocina! ⚡🔥",
                "text_style": "Texto flotante centrado superior para no tapar los pies ni la cocina",
                "effect_or_transition": "Efecto de velocidad 'Curva > Montaje' (velocidad normal con leve cámara lenta 0.5x en el toque más rápido)",
                "capcut_tool": "Herramienta 'Velocidad > Curva' + Subtítulos automáticos con animación de rebote"
            },
            {
                "step_number": 3,
                "action": "Toma 3: Desenlace, Remate y Llamado a la Acción (CTA)",
                "timestamp": f"{format_ts(step2_end)} - {format_ts(e_sec)}",
                "duration": f"{e_sec - step2_end}s",
                "on_screen_text": "¿Punto legal o error en la red? Comenta 👇🎾",
                "text_style": "Sticker de flecha neón señalando la jugada + Texto de pregunta en rojo/blanco",
                "effect_or_transition": "Congelar fotograma (Freeze frame 0.5s) en el impacto final con efecto de sonido 'Whoosh / Impact'",
                "capcut_tool": "Efectos de audio > Transición 'Whoosh' + 'Congelar' + 'Stickers'"
            }
        ],
        "call_to_action": "¿Punto legal o invasión de cocina? ¿Tú qué hubieras hecho? Comenta abajo 👇",
        "export_settings": "Resolución: 1080p, Cuadros por segundo: 60 fps (o 30 fps), Tasa de bits: Recomendada, Códec: H.264"
    }
    return analysis

def analyze_video_file(video_id: str, custom_api_key: Optional[str] = None) -> Dict[str, Any]:
    video = database.get_video_by_id(video_id)
    if not video:
        raise ValueError(f"Video con ID {video_id} no encontrado.")

    api_key = custom_api_key or get_gemini_api_key()
    if not api_key:
        err = "No se ha configurado la API Key de Gemini."
        database.update_video_status(video_id, "failed", error=err, progress_step="⚠️ Falta API Key")
        raise ValueError(err)

    original_path = Path(video["path"])
    if not original_path.exists():
        err = f"El archivo local {original_path} no existe."
        database.update_video_status(video_id, "failed", error=err, progress_step="⚠️ Archivo no encontrado")
        raise FileNotFoundError(err)

    database.update_video_status(video_id, "processing", progress_step="⚡ Optimizando video para análisis ultrarrápido...")
    
    try:
        analysis_path = optimize_video_for_ai(original_path)
    except Exception as e:
        logger.warning(f"Fallo en optimización ffmpeg ({e}), usando archivo original...")
        analysis_path = original_path

    database.update_video_status(video_id, "processing", progress_step="☁️ Subiendo video a Google Gemini...")
    logger.info(f"Subiendo '{analysis_path.name}' a Gemini...")

    client = genai.Client(api_key=api_key)
    uploaded_file = None

    try:
        uploaded_file = client.files.upload(file=str(analysis_path))
        database.update_video_status(video_id, "processing", progress_step="🔄 Decodificando fotogramas en Google Cloud...")
        
        max_wait_seconds = 300
        start_time = time.time()
        while uploaded_file.state.name == "PROCESSING":
            if time.time() - start_time > max_wait_seconds:
                raise TimeoutError("Tiempo de espera agotado mientras Gemini indexaba el video.")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise RuntimeError(f"Error procesando video en Gemini: {getattr(uploaded_file, 'error', 'Error desconocido')}")

        # Step 1: Algorithmic detection of active rallies in this video
        database.update_video_status(video_id, "processing", progress_step="⏱️ Detectando jugadas y puntos activos con cronómetro...")
        detected_rallies = detect_active_rallies(analysis_path)
        rallies_summary = ", ".join([f"{r['start_time']} - {r['end_time']} ({r['duration_seconds']}s)" for r in detected_rallies])
        
        prompt_with_rallies = (
            f"{SYSTEM_PROMPT_TEMPLATE}\n\n"
            f"INFORMACIÓN CRONOMETRADA DE PISTA (AUDITORÍA FÍSICA DE TIEMPOS):\n"
            f"Se han detectado los siguientes tramos continuos de pelota en juego en este video: [{rallies_summary}].\n"
            f"Cada fotograma del video tiene impreso un reloj digital TIMECODE (00:MM:SS:FF) en la esquina superior izquierda.\n"
            f"Elige el tramo más espectacular y viral de entre los tramos detectados. "
            f"Asegúrate de que tus tiempos 'start_time' y 'end_time' comiencen exactamente con el saque y terminen con el clímax/remate de ese punto."
        )

        database.update_video_status(video_id, "processing", progress_step="👁️ La IA está examinando el juego y los jugadores...")

        # High-availability model hierarchy with persistent multi-pass fallback against 503 (demand spike) and 429 (quota)
        models_to_try = [
            "gemini-3.6-flash",           # Core next-gen multimodal model
            "gemini-3.5-flash-lite",      # Ultra fast, independent quota tier
            "gemini-flash-lite-latest",   # High-availability production alias
            "gemini-3.1-flash-lite",      # High-capacity fallback
            "gemini-3-flash-preview",     # Advanced preview tier
            "gemini-3.5-flash",           # High capacity tier
            "gemini-3.8-flash"            # Next-gen reasoning tier
        ]
        analysis_data = None
        last_error = None

        # Persistent multi-pass loop (up to 3 passes over all models to wait out Google's demand spike)
        for pass_num in range(3):
            for model_name in models_to_try:
                for attempt in range(2):
                    try:
                        logger.info(f"Consultando modelo {model_name} (Pasada {pass_num+1}, intento {attempt+1})...")
                        database.update_video_status(
                            video_id,
                            "processing",
                            progress_step=f"🧠 Evaluando táctica y viralidad con IA ({model_name})..."
                        )
                        res = client.models.generate_content(
                            model=model_name,
                            contents=[uploaded_file, prompt_with_rallies],
                            config=types.GenerateContentConfig(
                                temperature=0.2,
                                http_options=types.HttpOptions(timeout=240000)
                            )
                        )
                        raw = res.text.strip()
                        if raw.startswith("```json"): raw = raw[7:]
                        if raw.startswith("```"): raw = raw[3:]
                        if raw.endswith("```"): raw = raw[:-3]
                        analysis_data = json.loads(raw.strip())
                        analysis_data = anchor_and_refine_analysis(analysis_data, detected_rallies)
                        logger.info(f"Análisis completado con éxito usando {model_name}")
                        break
                    except Exception as e:
                        last_error = e
                        err_str = str(e)
                        logger.warning(f"Aviso con {model_name} intento {attempt+1}: {e}")
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            database.update_video_status(
                                video_id,
                                "processing",
                                progress_step="⏳ Cuota ocupada en este nodo, alternando a modelo de alta disponibilidad..."
                            )
                            time.sleep(2)
                            break  # Switch to next model on 429 quota exhaustion
                        elif "503" in err_str or "UNAVAILABLE" in err_str:
                            database.update_video_status(
                                video_id,
                                "processing",
                                progress_step=f"⏳ Servidores de Google congestionados (503). Pausa táctica y reintento en {5 * (attempt + 1)}s..."
                            )
                            time.sleep(5 * (attempt + 1))
                        else:
                            time.sleep(2)
                if analysis_data:
                    break
            if analysis_data:
                break
            
            if pass_num < 2:
                logger.info(f"Pasada {pass_num+1} finalizada sin respuesta de servidor. Esperando 8s antes del siguiente ciclo de disponibilidad...")
                database.update_video_status(
                    video_id,
                    "processing",
                    progress_step=f"⏳ Esperando liberación de cola de Google Cloud (pasada {pass_num+1}/3)..."
                )
                time.sleep(8)

        if not analysis_data:
            raise RuntimeError(f"No se pudo completar el análisis del video tras varios intentos: {last_error}")

        analysis_data = ensure_capcut_recommendation(analysis_data)
        database.update_video_status(video_id, "analyzed", analysis=analysis_data, progress_step="✓ Completado")
        return analysis_data

    except Exception as e:
        logger.error(f"Error durante el análisis del video {video_id}: {e}")
        database.update_video_status(video_id, "failed", error=str(e), progress_step="⚠️ Error")
        raise

    finally:
        if uploaded_file and hasattr(uploaded_file, "name"):
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
