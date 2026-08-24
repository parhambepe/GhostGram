import io
import asyncio
from google.genai import types

class MediaProcessor:
    """
    Converts Telegram media (photos / voice notes) into Gemini-compatible parts.
    Photos: downloaded bytes passed as inline image data.
    Voice:  OGG/Opus bytes passed as inline audio (Gemini transcribes natively).
    """
    IMAGE_MIME = {
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/webp": "image/webp",
        "image/heic": "image/heic",
    }
    AUDIO_MIME = {
        "audio/ogg": "audio/ogg",
        "audio/mpeg": "audio/mpeg",
        "audio/mp4": "audio/mp4",
        "audio/aac": "audio/aac",
        "audio/wav": "audio/wav",
    }

    async def build_part(self, client, message) -> types.Part | None:
        """Downloads the media of `message` and returns a Gemini Part, or None."""
        try:
            media = getattr(message, "media", None)
            if not media:
                return None

            # Photo messages
            if getattr(message, "photo", None):
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

            # Voice notes (ogg/opus) and round video messages
            voice = getattr(message, "voice", None)
            if voice:
                mime = getattr(voice, "mime_type", None) or "audio/ogg"
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                return types.Part.from_bytes(data=buf.getvalue(), mime_type=mime)

            # Generic audio (mp3 files etc.)
            audio = getattr(message, "audio", None)
            if audio:
                mime = getattr(audio, "mime_type", None) or "audio/mpeg"
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                return types.Part.from_bytes(data=buf.getvalue(), mime_type=mime)

            return None
        except Exception as e:
            print(f"⚠️ Media download failed: {e}")
            return None

    def describe_media(self, message) -> str:
        """Short Persian label of what kind of media this is (for prompts)."""
        if getattr(message, "photo", None):
            return "یک عکس"
        if getattr(message, "voice", None):
            return "یک پیام صوتی"
        if getattr(message, "audio", None):
            return "یک فایل صوتی"
        return "یک رسانه"

# Global singleton instance
media_processor = MediaProcessor()
