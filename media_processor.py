import io
import asyncio
from google.genai import types

try:  # stdlib on py<=3.12, removed in 3.13 — we have a magic-byte fallback
    import imghdr
except ImportError:  # pragma: no cover
    imghdr = None


class _ImgHdrShim:
    """Minimal imghdr replacement for Python 3.13+ (only what we need)."""
    @staticmethod
    def what(_, h=None):
        if not h or len(h) < 12:
            return None
        if h[:3] == b"\xff\xd8\xff":
            return "jpeg"
        if h[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
            return "webp"
        if h[:2] == b"BM":
            return "bmp"
        if h[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        return None


if imghdr is None:
    imghdr = _ImgHdrShim()


# --- image format sniffing ------------------------------------------------
def _sniff_image(data: bytes):
    if not data or len(data) < 24:
        return None

    kind = None
    try:
        kind = imghdr.what(None, h=data)  # 'jpeg', 'png', 'webp', ...
    except Exception:
        kind = None

    # Manual magic-byte checks (imghdr removed in Python 3.13)
    if kind is None:
        if data[:3] == b"\xff\xd8\xff":
            kind = "jpeg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            kind = "png"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            kind = "webp"
        elif data[:2] == b"BM":
            kind = "bmp"

    if kind is None:
        return None
    if kind == "jpg":
        kind = "jpeg"
    return f"image/{kind}"


class MediaProcessor:
    """
    Converts Telegram media (photos / voice notes / video notes) into Gemini-compatible parts.
    Photos:    downloaded bytes passed as inline image data (format auto-detected from magic bytes).
    Voice:     OGG/Opus bytes passed as inline audio (Gemini transcribes natively).
    Video:     MP4 bytes (video notes & videos) passed as inline video.
    Documents: small text/PDF files passed as inline data so the bot can read them.

    If the downloaded media turns out to be undecodable/empty, returns None so the
    caller degrades gracefully to a text-only reply instead of failing the whole request.
    """
    MAX_BYTES = 18 * 1024 * 1024  # keep inline payloads reasonable (~18MB)

    async def build_part(self, client, message) -> types.Part | None:
        """Downloads the media of `message` and returns a Gemini Part, or None."""
        try:
            media = getattr(message, "media", None)
            if not media:
                return None

            buf = io.BytesIO()

            # ---- Photo messages --------------------------------------------
            if getattr(message, "photo", None):
                await client.download_media(message, file=buf)
                data = buf.getvalue()
                mime = _sniff_image(data)
                if mime is None:
                    print(f"⚠️ Photo download invalid/empty ({len(data)} bytes); skipping image part")
                    return None
                return types.Part.from_bytes(data=data, mime_type=mime)

            # ---- Voice notes (ogg/opus) ------------------------------------
            voice = getattr(message, "voice", None)
            if voice:
                mime = getattr(voice, "mime_type", None) or "audio/ogg"
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                data = buf.getvalue()
                if len(data) < 64:
                    print(f"⚠️ Voice too small ({len(data)} bytes); skipping")
                    return None
                return types.Part.from_bytes(data=data, mime_type=mime)

            # ---- Generic audio (mp3 files etc.) ------------------------------
            audio = getattr(message, "audio", None)
            if audio:
                mime = getattr(audio, "mime_type", None) or "audio/mpeg"
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                data = buf.getvalue()
                if len(data) < 64:
                    print(f"⚠️ Audio too small ({len(data)} bytes); skipping")
                    return None
                return types.Part.from_bytes(data=data, mime_type=mime)

            # ---- Round video messages and regular videos (mp4) --------------
            video = getattr(message, "video", None) or getattr(message, "video_note", None)
            if video:
                mime = getattr(video, "mime_type", None) or "video/mp4"
                size = getattr(video, "size", 0) or 0
                if size > self.MAX_BYTES:
                    print(f"⚠️ Video too large ({size} bytes), skipping inline upload")
                    return None
                buf = io.BytesIO()
                await client.download_media(message, file=buf)
                data = buf.getvalue()
                if len(data) < 64:
                    print(f"⚠️ Video download empty; skipping")
                    return None
                return types.Part.from_bytes(data=data, mime_type=mime)

            # ---- Small text-like documents (.txt/.pdf/...) -------------------
            document = getattr(message, "document", None)
            if document:
                mime = getattr(document, "mime_type", "") or ""
                size = getattr(document, "size", 0) or 0
                readable = mime.startswith(("text/", "application/pdf"))
                if readable and 0 < size <= self.MAX_BYTES:
                    buf = io.BytesIO()
                    await client.download_media(message, file=buf)
                    data = buf.getvalue()
                    if not data:
                        return None
                    return types.Part.from_bytes(data=data, mime_type=mime)

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
        doc = getattr(message, "document", None)
        if doc:
            mime = getattr(doc, "mime_type", "") or ""
            return "یک فایل PDF" if mime == "application/pdf" else "یک فایل متنی"
        return "یک رسانه"

# Global singleton instance
media_processor = MediaProcessor()
