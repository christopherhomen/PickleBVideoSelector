import re
import os
import shutil
import logging
import requests
import gdown
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import VIDEOS_DIR

logger = logging.getLogger("drive_service")
logging.basicConfig(level=logging.INFO)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"

def get_drive_service():
    """Returns an authorized Google Drive API client if service_account.json exists."""
    if not SERVICE_ACCOUNT_FILE.exists():
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            str(SERVICE_ACCOUNT_FILE),
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.warning(f"No se pudo inicializar Google Drive API: {e}")
        return None

def extract_drive_id(url: str) -> Optional[Dict[str, str]]:
    """Extract folder or file ID from Google Drive URL."""
    url = url.strip()
    
    # Check folder patterns
    folder_match = re.search(r"folders/([a-zA-Z0-9_-]+)", url)
    if folder_match:
        return {"type": "folder", "id": folder_match.group(1)}
    
    id_param = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if id_param:
        return {"type": "folder", "id": id_param.group(1)}
        
    # Check file patterns
    file_match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    if file_match:
        return {"type": "file", "id": file_match.group(1)}
        
    # Raw ID
    if re.match(r"^[a-zA-Z0-9_-]{15,}$", url):
        return {"type": "folder", "id": url}

    return None

def list_drive_folder_videos(url: str) -> List[Dict[str, str]]:
    """
    Scrapes the public Google Drive folder page to find ALL video files and their IDs.
    Returns list of dicts: [{"id": drive_id, "name": filename, "format": ext}]
    """
    parsed = extract_drive_id(url)
    if not parsed:
        raise ValueError("El enlace no tiene un formato válido de Google Drive.")

    if parsed["type"] == "file":
        return [{"id": parsed["id"], "name": f"drive_video_{parsed['id']}.mp4", "format": "MP4"}]

    folder_id = parsed["id"]
    service = get_drive_service()
    if service:
        try:
            logger.info(f"Escaneando carpeta con la Google Drive API oficial (ID: {folder_id})...")
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType, size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = results.get("files", [])
            api_videos = []
            for f in files:
                ext = Path(f["name"]).suffix.lower()
                if ext in VIDEO_EXTENSIONS or "video" in f.get("mimeType", ""):
                    api_videos.append({
                        "id": f["id"],
                        "name": f["name"],
                        "format": ext.replace(".", "").upper() or "MP4"
                    })
            if api_videos:
                logger.info(f"Drive API descubrió con éxito {len(api_videos)} videos en la carpeta.")
                return api_videos
        except Exception as e:
            logger.warning(f"Drive API list falló ({e}), continuando con raspador web...")

    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    logger.info(f"Escaneando carpeta de Google Drive: {folder_url}")

    try:
        r = requests.get(folder_url, headers=HEADERS, timeout=20)
        html = r.text
    except Exception as e:
        logger.error(f"Error accediendo a la carpeta de Drive: {e}")
        raise RuntimeError(f"No se pudo conectar a Google Drive: {e}")

    videos_found = []
    seen_ids = set()

    # Pattern 1: Match within window['_DRIVE_ivd'] or raw JS bootstrap arrays
    # Matches: [\"FILE_ID\",[\"FOLDER_ID\"],\"FILENAME.EXT\"
    pattern_js = r'(?:\\x22|")([a-zA-Z0-9_-]{25,})(?:\\x22|"),(?:\\x5b|\[)(?:\\x22|")[a-zA-Z0-9_-]+(?:\\x22|")(?:\\x5d|\]),(?:\\x22|")([^"\\]+?\.(?:mp4|mov|avi|webm|m4v))(?:\\x22|")'
    for m in re.finditer(pattern_js, html, re.IGNORECASE):
        file_id = m.group(1)
        name = m.group(2).strip()
        ext = Path(name).suffix.replace(".", "").upper()
        if file_id not in seen_ids:
            seen_ids.add(file_id)
            videos_found.append({"id": file_id, "name": name, "format": ext})

    # Pattern 2: HTML data-id & data-tooltip attributes
    pattern_html = r'data-id="([a-zA-Z0-9_-]{20,})"[^>]*?data-tooltip="([^"]+?\.(?:mp4|mov|avi|webm|m4v))'
    for m in re.finditer(pattern_html, html, re.IGNORECASE):
        file_id = m.group(1)
        name = m.group(2).strip()
        ext = Path(name).suffix.replace(".", "").upper()
        if file_id not in seen_ids:
            seen_ids.add(file_id)
            videos_found.append({"id": file_id, "name": name, "format": ext})

    # Pattern 3: Fallback generic ID followed by video name in page
    if not videos_found:
        pattern_fallback = r'\["([a-zA-Z0-9_-]{28,35})"[^\]]*?"([^"]+?\.(?:mp4|mov|avi|webm|m4v))"'
        for m in re.finditer(pattern_fallback, html, re.IGNORECASE):
            file_id = m.group(1)
            name = m.group(2).strip()
            ext = Path(name).suffix.replace(".", "").upper()
            if file_id not in seen_ids:
                seen_ids.add(file_id)
                videos_found.append({"id": file_id, "name": name, "format": ext})

    logger.info(f"Total videos descubiertos en la carpeta: {len(videos_found)}")
    return videos_found

def download_file_by_id(file_id: str, filename: str) -> Dict[str, Any]:
    """
    Downloads a single video file from Google Drive by its file ID.
    Returns file metadata dict.
    """
    clean_name = re.sub(r'[\\/*?:"<>|]', "", filename)
    dest_path = VIDEOS_DIR / clean_name
    
    # Avoid collision
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        stat = dest_path.stat()
        return {
            "filename": dest_path.name,
            "path": str(dest_path),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "format": dest_path.suffix.replace(".", "").upper()
        }

    logger.info(f"Descargando archivo {clean_name} (ID: {file_id})...")
    output = gdown.download(id=file_id, output=str(dest_path), quiet=False)
    
    if not output or not Path(output).exists() or Path(output).stat().st_size == 0:
        raise RuntimeError(f"Fallo al descargar el archivo {clean_name} desde Google Drive.")

    final_path = Path(output)
    stat = final_path.stat()
    return {
        "filename": final_path.name,
        "path": str(final_path),
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "format": final_path.suffix.replace(".", "").upper()
    }
