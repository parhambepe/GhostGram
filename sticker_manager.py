import os
import json
import asyncio
from config import Config


class StickerManager:
    """
    Teaches the bot what stickers mean and lets it use them naturally.

    Storage (stickers_state.json in DATA_DIR):
      stickers: { file_unique_id: {emoji, meaning, set_name, chat_hint} }
      pool:     ordered list of file_unique_ids the bot may send

    Flow:
      - Owner replies to a sticker with `!استیکر <meaning>` -> taught & added to pool.
      - When anyone sends a taught sticker, history/prompt shows its meaning.
      - Pal/auto-engage JSON replies may include "sticker": true; the engine then
        asks the model to pick the best taught sticker for the context.
    """

    def __init__(self, state_file=None):
        self.state_file = state_file or Config.STICKERS_STATE_FILE
        self.stickers = {}   # file_unique_id -> dict
        self.pool = []       # ordered ids the bot may send
        self.load_state()

    # ---------------- persistence ----------------
    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.stickers = data.get("stickers", {}) or {}
                self.pool = data.get("pool", []) or []
        except Exception:
            self.stickers = {}
            self.pool = []

    def save_state(self):
        try:
            tmp = f"{self.state_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"stickers": self.stickers, "pool": self.pool}, f, ensure_ascii=False)
            os.replace(tmp, self.state_file)
        except Exception:
            pass

    # ---------------- helpers ----------------
    @staticmethod
    def sticker_info(message):
        """Extract (file_unique_id, emoji) from a sticker message. Returns (None, None) if not a sticker."""
        doc = getattr(message, "sticker", None)
        if doc is None:
            return None, None
        emoji = ""
        mime = getattr(doc, "mime_type", "") or ""
        animated = bool(getattr(doc, "animated", False))
        video = mime == "video/webm"
        for attr in (getattr(doc, "attributes", None) or []):
            attr_name = type(attr).__name__
            if attr_name == "DocumentAttributeSticker" or hasattr(attr, "alt") and hasattr(attr, "stickerset"):
                emoji = getattr(attr, "alt", "") or ""
                break
        kind = "tgs" if animated else ("webm" if video else "webp")
        return getattr(doc, "file_unique_id", None), {"emoji": emoji, "kind": kind}

    def teach(self, message, meaning: str):
        """Teach the meaning of the sticker in `message`. Returns True if newly taught."""
        fid, info = self.sticker_info(message)
        if not fid or not meaning.strip():
            return False
        existed = fid in self.stickers
        entry = self.stickers.get(fid, {})
        entry.update({
            "emoji": info["emoji"] or entry.get("emoji", ""),
            "kind": info["kind"],
            "meaning": meaning.strip()[:300],
        })
        self.stickers[fid] = entry
        if fid not in self.pool:
            self.pool.append(fid)
            if len(self.pool) > 40:  # keep the sendable pool bounded
                oldest = self.pool.pop(0)
                # stay consistent: only forget from pool, keep knowledge
                pass
        self.save_state()
        return not existed

    def unteach(self, message):
        """Remove a sticker from the sendable pool (knowledge kept). Returns removed meaning or None."""
        fid, _ = self.sticker_info(message)
        if not fid or fid not in self.pool:
            return None
        self.pool.remove(fid)
        meaning = self.stickers.get(fid, {}).get("meaning")
        self.save_state()
        return meaning or "؟"

    def describe_for_prompt(self, message):
        """If this message carries a KNOWN sticker, return a prompt annotation string."""
        fid, info = self.sticker_info(message)
        if not fid:
            return None
        known = self.stickers.get(fid)
        emoji = (known or {}).get("emoji") or (info["emoji"] if info else "")
        if known:
            return f"استیکر {emoji} ({known['meaning']})"
        return f"استیکر {emoji}".strip()

    def list_known(self, limit: int = 15):
        """Short human-readable listing of taught stickers."""
        lines = []
        for i, fid in enumerate(self.pool[:limit], 1):
            s = self.stickers.get(fid, {})
            lines.append(f"{i}. {s.get('emoji','🙂')} — {s.get('meaning','')[:80]}")
        extra = len(self.pool) - limit
        if extra > 0:
            lines.append(f"... و {extra} مورد دیگر")
        return "\n".join(lines) if lines else None

    def pick_best(self, client, hint_text: str):
        """
        Pick the taught sticker whose meaning best matches hint_text using simple
        keyword overlap scoring (no AI call needed). Returns a cached Telethon Document or None.
        """
        best_id, best_score = None, 0
        hint = (hint_text or "").strip()
        for fid in self.pool:
            entry = self.stickers.get(fid) or {}
            meaning = (entry.get("meaning") or "").strip()
            emoji = (entry.get("emoji") or "").strip()
            if not meaning:
                continue
            score = 0
            m_words = {w for w in meaning.split() if len(w) >= 3}
            h_words = {w for w in hint.split() if len(w) >= 3}
            score += len(m_words & h_words) * 2
            if emoji and emoji in hint:
                score += 1
            if score > best_score:
                best_score, best_id = score, fid
        if best_id is None and self.pool:
            # no textual match: fall back to most recently taught
            best_id = self.pool[-1]
        return self._resolve_document(client, best_id)

    async def resolve_document_async(self, client, fid):
        """Async resolution of a stored short id into a sendable Document ref."""
        return await asyncio.get_event_loop().run_in_executor(None, self._resolve_document, client, fid)

    def _resolve_document(self, client, fid):
        """Resolve file_unique_id back to a cached Document (populated by remember_document)."""
        if not fid:
            return None
        cache = getattr(client, "_gg_sticker_docs", None)
        if cache:
            return cache.get(fid)
        return None

    def remember_document(self, client, message):
        """Cache the actual Document of a sticker message so we can re-send it later."""
        doc = getattr(message, "sticker", None)
        if doc is None:
            return
        fid = getattr(doc, "file_unique_id", None)
        if not fid:
            return
        cache = getattr(client, "_gg_sticker_docs", None)
        if cache is None:
            cache = {}
            setattr(client, "_gg_sticker_docs", cache)
        cache[fid] = doc


# Global singleton
sticker_manager = StickerManager()
