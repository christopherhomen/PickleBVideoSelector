import json
import uuid
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from config import DB_FILE, VIDEOS_DIR

def load_db() -> Dict[str, Any]:
    if not DB_FILE.exists():
        initial = {"videos": {}, "updated_at": None}
        save_db(initial)
        return initial
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"videos": {}, "updated_at": None}

def save_db(data: Dict[str, Any]):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_video(filename: str, file_path: str, size_mb: float, fmt: str) -> Dict[str, Any]:
    db = load_db()
    
    # Check if video already exists by filename
    for vid_id, vid in db["videos"].items():
        if vid["filename"] == filename:
            # Update path if needed
            vid["path"] = file_path
            vid["size_mb"] = size_mb
            save_db(db)
            return vid

    video_id = str(uuid.uuid4())[:8]
    record = {
        "id": video_id,
        "filename": filename,
        "path": file_path,
        "size_mb": size_mb,
        "format": fmt,
        "status": "pending",  # pending, processing, analyzed, failed
        "error_message": None,
        "analysis": None
    }
    db["videos"][video_id] = record
    save_db(db)
    return record

def update_video_status(video_id: str, status: str, analysis: Optional[Dict] = None, error: Optional[str] = None, progress_step: Optional[str] = None):
    db = load_db()
    if video_id in db["videos"]:
        # If it already has an analysis and we try to set it to pending, preserve analyzed
        if db["videos"][video_id].get("analysis") and status == "pending":
            status = "analyzed"
            if not progress_step:
                progress_step = "✓ Completado"
        db["videos"][video_id]["status"] = status
        if progress_step is not None:
            db["videos"][video_id]["progress_step"] = progress_step
        if analysis is not None:
            db["videos"][video_id]["analysis"] = analysis
            db["videos"][video_id]["status"] = "analyzed"
        if error is not None:
            db["videos"][video_id]["error_message"] = error
        save_db(db)


def get_all_videos() -> List[Dict[str, Any]]:
    db = load_db()
    # Also verify local files still exist
    return list(db["videos"].values())

def get_video_by_id(video_id: str) -> Optional[Dict[str, Any]]:
    db = load_db()
    return db["videos"].get(video_id)

def delete_video(video_id: str) -> bool:
    db = load_db()
    if video_id in db["videos"]:
        vid = db["videos"][video_id]
        try:
            p = Path(vid["path"])
            if p.exists():
                os.remove(p)
        except Exception:
            pass
        del db["videos"][video_id]
        save_db(db)
        return True
    return False

def sync_local_videos():
    """Scans the videos directory and registers any existing files."""
    if not VIDEOS_DIR.exists():
        return
    for f in VIDEOS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"]:
            if f.name.startswith("opt_") or f.name.startswith("temp_") or "_opt" in f.name:
                continue
            stat = f.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            register_video(f.name, str(f), size_mb, f.suffix.replace(".", "").upper())
