"""Stealth feedback + error notification helpers.

Confirmations of stealth commands are sent to Saved Messages (the owner's own
chat) and auto-deleted after a few seconds, so nothing is left behind in the
target chat while the owner still gets clear feedback.

Engine/runtime errors are pushed to Saved Messages too, so a headless Railway
deployment never fails silently.
"""
import asyncio
from datetime import datetime

from config import Config


class Notifier:
    def __init__(self):
        self.client = None
        self._my_id = None
        self._sem = asyncio.Semaphore(1)

    def bind(self, client, me):
        """Called once at startup with the live Telethon client and `me`."""
        self.client = client
        self._my_id = me.id if me else Config.OWNER_ID

    @property
    def ready(self) -> bool:
        return self.client is not None and bool(self._my_id)

    async def _send(self, text: str, auto_delete: bool = False):
        client = self.client
        if not self.ready or not client or not text:
            return
        try:
            msg = await client.send_message("me", text)
            if auto_delete and Config.CONFIRM_AUTO_DELETE_SECONDS > 0:
                async def _rm():
                    await asyncio.sleep(Config.CONFIRM_AUTO_DELETE_SECONDS)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                asyncio.create_task(_rm())
        except Exception as e:
            print(f"⚠️ Notifier failed: {e}")

    async def confirm(self, text: str):
        """Short confirmation; auto-deleted from Saved Messages."""
        if not Config.STEALTH_CONFIRM:
            return
        async with self._sem:
            await self._send(text, auto_delete=True)

    async def error(self, where: str, detail: str):
        """Persistent error report to Saved Messages (rate-limited per minute)."""
        if not Config.NOTIFY_ERRORS:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        async with self._sem:
            await self._send(f"🚨 GhostGram خطا [{where}] @{ts}:\n{detail[:500]}", auto_delete=False)


# Global singleton instance
notifier = Notifier()
