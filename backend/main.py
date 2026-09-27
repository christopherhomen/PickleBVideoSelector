import os
import io
import csv
import shutil
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Header, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

import subprocess
from config import get_gemini_api_key, set_gemini_api_key, VIDEOS_DIR, DATA_DIR
import database
import drive_service
import analyzer

app = FastAPI(title="Pickleball Video Scout & AI Vision Analyzer")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: scan local videos
@app.on_event("startup")
def startup_event():
    database.sync_local_videos()

class SettingsPayload(BaseModel):
    gemini_api_key: str

class DriveScanPayload(BaseModel):
    url: str
    gemini_api_key: Optional[str] = None
    auto_analyze: Optional[bool] = False

@app.get("/api/status")
def get_system_status():
    api_key = get_gemini_api_key()
    videos = database.get_all_videos()
    analyzed = [v for v in videos if v.get("status") == "analyzed"]
    return {
        "status": "ready",
        "has_api_key": bool(api_key),
        "api_key_masked": f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("Configurada" if api_key else ""),
        "total_videos": len(videos),
        "analyzed_videos": len(analyzed),
        "pending_videos": len(videos) - len(analyzed)
    }

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    key = payload.gemini_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="La API Key no puede estar vacía.")
    set_gemini_api_key(key)
    return {"message": "API Key guardada exitosamente."}

@app.get("/api/videos")
def list_videos():
    database.sync_local_videos()
    return database.get_all_videos()

def process_drive_batch_task(batch_items: List[Dict[str, Any]], auto_analyze: bool):
    """Background task to sequentially download and analyze all discovered Drive videos."""
    total = len(batch_items)
    for index, item in enumerate(batch_items, 1):
        db_id = item["db_id"]
        drive_id = item["drive_id"]
        filename = item["name"]
        
        try:
            database.update_video_status(
                db_id, 
                "processing", 
                progress_step=f"📥 Descargando video {index} de {total} desde Google Drive..."
            )
            downloaded = drive_service.download_file_by_id(drive_id, filename)
            
            # Update path and size in DB
            db = database.load_db()
            if db_id in db["videos"]:
                db["videos"][db_id]["path"] = downloaded["path"]
                db["videos"][db_id]["size_mb"] = downloaded["size_mb"]
                database.save_db(db)

            if auto_analyze:
                analyzer.analyze_video_file(db_id)
            else:
                db_now = database.load_db()
                if db_now["videos"].get(db_id, {}).get("analysis"):
                    database.update_video_status(db_id, "analyzed", progress_step="✓ Completado")
                else:
                    database.update_video_status(db_id, "pending", progress_step="✓ Descargado (listo para analizar)")
        except Exception as e:
            database.update_video_status(db_id, "failed", error=str(e), progress_step="⚠️ Error en descarga")

@app.post("/api/drive/scan")
def scan_google_drive(payload: DriveScanPayload, background_tasks: BackgroundTasks):
    """
    Discovers ALL videos in a Google Drive folder immediately, displays them in the UI,
    and downloads and analyzes them in the background.
    """
    if payload.gemini_api_key:
        set_gemini_api_key(payload.gemini_api_key.strip())

    try:
        discovered = drive_service.list_drive_folder_videos(payload.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not discovered:
        raise HTTPException(
            status_code=400,
            detail="No se encontraron videos en la carpeta de Google Drive. Verifica que la carpeta tenga permisos de 'Cualquiera con el enlace puede ver'."
        )

    batch_items = []
    registered_videos = []

    for item in discovered:
        # Check if file already exists locally
        clean_name = item["name"]
        local_path = VIDEOS_DIR / clean_name
        size_mb = round(local_path.stat().st_size / (1024 * 1024), 2) if local_path.exists() else 0.0

        reg = database.register_video(
            filename=clean_name,
            file_path=str(local_path),
            size_mb=size_mb,
            fmt=item["format"]
        )
        
        # If not analyzed yet, set pending/download step
        if reg.get("status") not in ["analyzed", "processing"]:
            step = "✓ Descargado" if local_path.exists() and size_mb > 0 else "⏳ En cola para descarga..."
            database.update_video_status(reg["id"], "pending", progress_step=step)

        registered_videos.append(reg)
        batch_items.append({
            "db_id": reg["id"],
            "drive_id": item["id"],
            "name": clean_name
        })

    # Start sequential background download & analysis
    background_tasks.add_task(process_drive_batch_task, batch_items, payload.auto_analyze)

    return {
        "message": f"¡Se encontraron {len(discovered)} videos en Google Drive! Descarga y análisis iniciados en vivo.",
        "count": len(discovered),
        "videos": registered_videos
    }

@app.post("/api/videos/upload")
async def upload_videos(
    files: List[UploadFile] = File(...),
    auto_analyze: bool = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Direct upload for local videos or drag-and-drop batch upload.
    """
    uploaded = []
    for file in files:
        safe_name = Path(file.filename).name
        dest_path = VIDEOS_DIR / safe_name
        
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        stat = dest_path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        fmt = dest_path.suffix.replace(".", "").upper()
        
        reg = database.register_video(safe_name, str(dest_path), size_mb, fmt)
        uploaded.append(reg)
        
        if auto_analyze:
            background_tasks.add_task(analyzer.analyze_video_file, reg["id"])

    return {
        "message": f"Se subieron {len(uploaded)} video(s) exitosamente.",
        "count": len(uploaded),
        "videos": uploaded
    }

@app.post("/api/videos/{video_id}/analyze")
def analyze_single_video(video_id: str, background_tasks: BackgroundTasks):
    video = database.get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado.")
    
    file_path = Path(video.get("path", ""))
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise HTTPException(
            status_code=400, 
            detail=f"El archivo '{video.get('filename')}' aún se está descargando desde Google Drive. Por favor espera a que finalice la descarga."
        )

    background_tasks.add_task(analyzer.analyze_video_file, video_id)
    return {"message": "Análisis iniciado en segundo plano.", "video_id": video_id}

@app.post("/api/videos/analyze-all")
def analyze_all_pending(background_tasks: BackgroundTasks):
    videos = database.get_all_videos()
    to_process = [
        v for v in videos 
        if v.get("status") in ["pending", "failed"] 
        and Path(v.get("path", "")).exists() 
        and Path(v.get("path", "")).stat().st_size > 0
    ]
    
    for v in to_process:
        background_tasks.add_task(analyzer.analyze_video_file, v["id"])
        
    return {
        "message": f"Se inició el análisis para {len(to_process)} video(s) descargados.",
        "count": len(to_process)
    }

@app.delete("/api/videos/{video_id}")
def delete_single_video(video_id: str):
    success = database.delete_video(video_id)
    if not success:
        raise HTTPException(status_code=404, detail="Video no encontrado.")
    return {"message": "Video eliminado correctamente."}

def get_streamable_video_path(original_path: Path) -> Path:
    """
    Returns a web-friendly faststart H.264 MP4 for smooth browser playback
    and instantaneous, zero-delay seeking without black screens or freezes.
    """
    if original_path.suffix.lower() == ".mp4" and original_path.stat().st_size < 30 * 1024 * 1024:
        return original_path

    temp_dir = DATA_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    web_mp4 = temp_dir / f"opt_{original_path.stem}.mp4"
    if web_mp4.exists() and web_mp4.stat().st_size > 1000:
        return web_mp4

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-i", str(original_path),
            "-vf", "scale=-2:720",
            "-r", "24",
            "-c:v", "libx264",
            "-crf", "26",
            "-preset", "ultrafast",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "96k",
            str(web_mp4)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return web_mp4
    except Exception as e:
        print(f"Error creating streamable mp4: {e}")
        return original_path

@app.get("/api/videos/{video_id}/stream")
def stream_video(video_id: str):
    """
    Streams the video with native HTTP 206 Partial Content support for smooth seeking in browsers.
    """
    video = database.get_video_by_id(video_id)
    if not video or not Path(video["path"]).exists():
        raise HTTPException(status_code=404, detail="Archivo de video no encontrado.")

    file_path = get_streamable_video_path(Path(video["path"]))
    content_type = "video/mp4" if file_path.suffix.lower() == ".mp4" else "video/quicktime"
    return FileResponse(file_path, media_type=content_type)

@app.get("/api/videos/{video_id}/cut")
def download_cut_clip(video_id: str, start_seconds: int = 0, end_seconds: int = 15):
    """
    Cuts the video between start_seconds and end_seconds using FFmpeg
    and returns a downloadable high-quality .mp4 clip ready for CapCut.
    """
    video = database.get_video_by_id(video_id)
    if not video or not Path(video["path"]).exists():
        raise HTTPException(status_code=404, detail="Archivo de video no encontrado.")

    original_path = Path(video["path"])
    start_sec = max(0, start_seconds)
    end_sec = max(start_sec + 3, end_seconds)
    duration = end_sec - start_sec

    temp_dir = DATA_DIR / "cuts"
    temp_dir.mkdir(parents=True, exist_ok=True)

    cut_filename = f"cut_{original_path.stem}_{start_sec}s_{end_sec}s.mp4"
    cut_file_path = temp_dir / cut_filename

    if not cut_file_path.exists() or cut_file_path.stat().st_size < 1000:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Tone-map iPhone 10-bit HLG/HDR (BT.2020) to vibrant Standard SDR (BT.709 yuv420p)
        vf_filter = "zscale=transfer=bt709:matrix=bt709:primaries=bt709,format=yuv420p,eq=saturation=1.12:contrast=1.04"
        
        cmd = [
            ffmpeg, "-y",
            "-avoid_negative_ts", "make_zero",
            "-ss", str(start_sec),
            "-i", str(original_path),
            "-t", str(duration),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-crf", "19",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(cut_file_path)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            # Fallback filter if zscale has an issue
            cmd[6] = "format=yuv420p"
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"Error recortando el video con FFmpeg: {e2}")

    download_name = f"PickleScout_{original_path.stem}_{start_sec}s_{end_sec}s.mp4"
    return FileResponse(
        cut_file_path,
        media_type="video/mp4",
        headers={"Content-Disposition": f"attachment; filename={download_name}"}
    )

@app.get("/api/export")
def export_results(export_format: str = "json"):
    videos = database.get_all_videos()
    
    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Archivo", "Tamaño (MB)", "Estado", "Título", "Jugadores",
            "Formato", "Categoría / Tag", "Recomendación y Decisión",
            "Resumen de Acciones", "Técnicas Pickleball", "Momentos Destacados", "Errores / Fallas"
        ])
        for v in videos:
            a = v.get("analysis") or {}
            writer.writerow([
                v["id"],
                v["filename"],
                v["size_mb"],
                v["status"],
                a.get("title", ""),
                a.get("people_count", ""),
                a.get("game_format", ""),
                a.get("classification_tag", ""),
                a.get("decision_recommendation", ""),
                a.get("actions_summary", ""),
                ", ".join(a.get("pickleball_techniques", [])),
                a.get("highlights", ""),
                a.get("mistakes_or_issues", "")
            ])
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=pickleball_analysis.csv"}
        )
    else:
        return JSONResponse(content=videos)

# Mount frontend dist if built
from fastapi.staticfiles import StaticFiles
from config import BASE_DIR
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

