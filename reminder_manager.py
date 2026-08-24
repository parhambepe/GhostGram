import asyncio
import json
import os
from datetime import datetime, timezone, timedelta

class ReminderManager:
    """
    Natural-language reminders.
    The AI parses a Persian instruction into JSON: {due_time: "YYYY-MM-DD HH:MM", text: "..."}
    (time in Iran local time). Reminders fire via a background loop and are
    delivered to the chat the reminder was created in.
    """
    def __init__(self, state_file="reminders_state.json"):
        self.state_file = state_file
        self.reminders = {}  # id -> {chat_id, due_ts, text, created}
        self._next_id = 1
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file) and os.path.getsize(self.state_file) > 0:
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("reminders", {})
                for k, v in items.items():
                    self.reminders[int(k)] = v
                self._next_id = int(data.get("next_id", 1))
            except Exception as e:
                print(f"⚠️ Error loading reminders: {e}")
                self.reminders = {}
                self._next_id = 1

    def save_state(self):
        try:
            tmp = f"{self.state_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"reminders": {str(k): v for k, v in self.reminders.items()},
                           "next_id": self._next_id}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.state_file)
        except Exception as e:
            print(f"⚠️ Error saving reminders: {e}")

    @staticmethod
    def _iran_tz():
        return timezone(timedelta(hours=3, minutes=30))

    def add_reminder(self, chat_id: int, due_local_dt: datetime, text: str) -> dict:
        """due_local_dt is Iran-local naive datetime → stored as UTC timestamp."""
        due_ts = due_local_dt.replace(tzinfo=self._iran_tz()).timestamp()
        rid = self._next_id
        self._next_id += 1
        self.reminders[rid] = {
            "chat_id": chat_id,
            "due_ts": due_ts,
            "text": text,
            "created": datetime.now(timezone.utc).timestamp(),
        }
        self.save_state()
        return self.reminders[rid]

    def list_pending(self, chat_id=None):
        now = datetime.now(timezone.utc).timestamp()
        out = [(rid, r) for rid, r in sorted(self.reminders.items())
               if r["due_ts"] > now and (chat_id is None or r["chat_id"] == chat_id)]
        return out

    def pop_due(self):
        """Returns and removes all reminders that are due."""
        now = datetime.now(timezone.utc).timestamp()
        due = [(rid, r) for rid, r in self.reminders.items() if r["due_ts"] <= now]
        result = []
        for rid, r in due:
            del self.reminders[rid]
            result.append(r)
        if result:
            self.save_state()
        return result

# Global singleton instance
reminder_manager = ReminderManager()
