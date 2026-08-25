import io
import asyncio
from google.genai import types

class MediaProcessor:
    """
    Converts Telegram media (photos / voice notes / video notes) into Gemini-compatible parts.
    Photos:    downloaded bytes passed as inline image data.
    Voice:     OGG/Opus bytes passed as inline audio (Gemini transcribes natively).
    Video:     MP4 bytes (video notes & videos) passed as inline video.
    Documents: small text/code files passed as inline text so the bot can read them.
    """
    MAX_BYTES = 18 * 1024 * 1024  # keep inline payloads reasonable (~18MB)

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

            # Voice notes (ogg/opus)
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

            # Round video messages and regular videos (mp4)
            video = getattr(message, "video", None) or getattr(message, "video_note", None)
            if video:
                mime = getattr(video, "mime_type", None) or "video/mp4"
                size = getattr(video, "size", 0) or 0
                if size > self.MAX_BYTES:
                    print(f"⚠️ Video too large ({size} bytes), skipping inline upload")
                    return None
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                return types.Part.from_bytes(data=buf.getvalue(), mime_type=mime)

            # Small text-like documents (.txt/.pdf/.py/...) → readable content
            document = getattr(message, "document", None)
            if document:
                mime = getattr(document, "mime_type", "") or ""
                size = getattr(document, "size", 0) or 0
                readable = mime.startswith(("text/", "application/pdf"))
                if readable and 0 < size <= self.MAX_BYTES:
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
        if getattr(message, "video_note", None):
            return "یک ویدیو نوت (ویدئوی رابد)"
        if getattr(message, "video", None):
            return "یک ویدیو"
        if getattr(message, "document", None):
            doc = getattr(message, "document", None)
            mime = getattr(doc, "mime_type", "") or "" if doc else ""
            return "یک فایل PDF" if mime == "application/pdf" else "یک فایل متنی"
        return "یک رسانه"

# Global singleton instance
media_processor = MediaProcessor()
