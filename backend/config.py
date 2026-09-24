import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
DB_FILE = DATA_DIR / "analysis_db.json"
ENV_FILE = BASE_DIR / ".env"

# Ensure directories exist
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

def get_gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

def set_gemini_api_key(api_key: str):
    os.environ["GEMINI_API_KEY"] = api_key
    # Persist in .env
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = [l for l in f.readlines() if not l.startswith("GEMINI_API_KEY=") and not l.startswith("GOOGLE_API_KEY=")]
    lines.append(f"GEMINI_API_KEY={api_key}\n")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
