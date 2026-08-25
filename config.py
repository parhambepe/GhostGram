import os
from dotenv import load_dotenv

load_dotenv()


def _data_dir() -> str:
    """Persistent storage dir (Railway volume mounted at /app/data, or DATA_DIR override)."""
    d = os.getenv("DATA_DIR")
    if d:
        d = d.rstrip("/")
        os.makedirs(d, exist_ok=True)
        return d
    if os.path.isdir("/app/data"):
        return "/app/data"
    return ""


def _state_path(name: str) -> str:
    d = _data_dir()
    return os.path.join(d, name) if d else name


class Config:
    API_ID = int(os.getenv("API_ID") or 0)
    API_HASH = os.getenv("API_HASH") or ""

    @staticmethod
    def _load_keys():
        keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
        if os.path.exists("apis.txt"):
            try:
                with open("apis.txt", "r", encoding="utf-8") as f:
                    file_keys = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    for k in file_keys:
                        if k not in keys:
                            keys.append(k)
            except Exception:
                pass
        return keys

    GEMINI_API_KEYS = _load_keys()
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite")
    SESSION_NAME = os.getenv("SESSION_NAME", "teleagent_session")
    # Railway/Cloud deployment: full Telethon session as a base64 string (takes priority over session file)
    SESSION_STRING = os.getenv("SESSION_STRING", "")
    OWNER_ID = int(os.getenv("OWNER_ID") or 0)

    # Persona display name used in group mention detection and prompts
    PERSONA_NAME = os.getenv("PERSONA_NAME", "شایان")

    # --- Persistent state files (survive restarts when DATA_DIR/volume is set) ---
    PAL_STATE_FILE = _state_path(os.getenv("PAL_STATE_FILE", "pal_state.json"))
    ASSISTANT_STATE_FILE = _state_path(os.getenv("ASSISTANT_STATE_FILE", "assistant_state.json"))
    MEMORY_STATE_FILE = _state_path(os.getenv("MEMORY_STATE_FILE", "memory_state.json"))
    REMINDERS_STATE_FILE = _state_path(os.getenv("REMINDERS_STATE_FILE", "reminders_state.json"))
    API_USAGE_FILE = _state_path(os.getenv("API_USAGE_FILE", "api_usage.json"))

    SHORT_TERM_MEMORY_LIMIT = int(os.getenv("SHORT_TERM_MEMORY_LIMIT", "30"))
    LONG_TERM_SUMMARY_INTERVAL = int(os.getenv("LONG_TERM_SUMMARY_INTERVAL", "30"))
    MAX_LONG_TERM_SUMMARY_CHARS = int(os.getenv("MAX_LONG_TERM_SUMMARY_CHARS", "600"))
    MAX_MESSAGE_SEGMENT_CHARS = int(os.getenv("MAX_MESSAGE_SEGMENT_CHARS", "200"))
    TYPING_SPEED_CPS = float(os.getenv("TYPING_SPEED_CPS", "18.0"))  # characters typed per second
    MIN_TYPING_DELAY = float(os.getenv("MIN_TYPING_DELAY", "1.5"))   # seconds
    MAX_TYPING_DELAY = float(os.getenv("MAX_TYPING_DELAY", "7.0"))   # seconds

    # Gemini hard timeout per key attempt (web-search grounded calls need longer)
    GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "15"))
    SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "45"))

    # Stealth feedback: command confirmations sent to Saved Messages and auto-deleted
    STEALTH_CONFIRM = os.getenv("STEALTH_CONFIRM", "1").lower() not in ("0", "false", "no")
    CONFIRM_AUTO_DELETE_SECONDS = float(os.getenv("CONFIRM_AUTO_DELETE_SECONDS", "10"))
    # Push engine/runtime errors to Saved Messages instead of dying silently in logs
    NOTIFY_ERRORS = os.getenv("NOTIFY_ERRORS", "1").lower() not in ("0", "false", "no")
