import re
import json
from datetime import datetime, timezone, timedelta
from reminder_manager import reminder_manager

class ReminderParser:
    """
    Parses Persian natural-language time expressions into an absolute datetime.
    Deterministic patterns first (fast, no API cost); falls back to the AI for complex cases.
    All times are Iran local (UTC+3:30).
    """

    MONTHS = {
        "فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4, "مرداد": 5, "شهریور": 6,
        "مهر": 7, "آبان": 8, "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12,
    }
    # Persian + Arabic-Indic digits → Latin
    DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

    @staticmethod
    def _iran_now():
        return datetime.now(timezone(timedelta(hours=3, minutes=30)))

    @staticmethod
    def _normalize(text: str) -> str:
        return text.translate(ReminderParser.DIGIT_MAP).strip()

    def parse(self, text: str):
        """
        Returns (due_local_naive_datetime, remaining_text) or (None, None) if unparseable.
        Tries deterministic Persian patterns; caller can fall back to AI parsing.
        """
        text = self._normalize(text)
        now = self._iran_now()
        
        def with_time(base_day, hour, minute, rem):
            due = base_day.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if due <= now:  # time already passed today → assume tomorrow
                due += timedelta(days=1)
            return due, rem

        # "ساعت 9:30" / "ساعت ۲۱" (+ optional فردا/پس‌فردا)
        m = re.search(r"(فردا|پس\s*فردا)?\s*(?:ساعت|ساعِت)\s+(\d{1,2})(?::(\d{2}))?", text)
        if m:
            day_shift = 0
            if m.group(1):
                day_shift = 2 if "پس" in m.group(1) else 1
            hour = min(int(m.group(2)), 23)
            minute = int(m.group(3)) if m.group(3) else 0
            base = (now + timedelta(days=day_shift)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if base <= now and day_shift == 0:
                base += timedelta(days=1)
            rem = text[m.end():].strip(" ،,.") or "یادآوری"
            return base, rem

        # "تا X دقیقه/ساعت دیگر"
        m = re.search(r"(\d+)\s*(دقیقه|ساعت)\s*(دیگه|دیگر|بعد)", text)
        if m:
            n = int(m.group(1))
            delta = timedelta(minutes=n) if m.group(2) == "دقیقه" else timedelta(hours=n)
            return now + delta, text[m.end():].strip(" ،,.") or "یادآوری"

        # "X دقیقه/ساعت دیگه یادم بنداز ..." (number before unit)
        m = re.search(r"(?:تا\s*)?(\d+)\s*(ثانیه|دقیقه|ساعت|روز|هفته)\b", text)
        if m:
            n = int(m.group(1))
            mult = {"ثانیه": 1, "دقیقه": 60, "ساعت": 3600, "روز": 86400, "هفته": 604800}[m.group(2)]
            return now + timedelta(seconds=n * mult), text[m.end():].strip(" ،,.") or "یادآوری"

        # "فردا ساعت ۵" already covered above; bare "فردا" → tomorrow 09:00
        if re.search(r"\bfarda\b|فردا", text):
            base = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            return base, text

        return None, None

# Global singleton instance
reminder_parser = ReminderParser()

AI_PARSE_PROMPT = """جمله کاربر برای ساخت یک یادآور است:
«{text}»

زمان فعلی ایران: {now}

وظیفه: زمان و متن یادآور را استخراج کن. خروجی فقط JSON باشد:
{{
  "due_time": "YYYY-MM-DD HH:MM",   // زمان مورد نظر به وقت محلی ایران، 24 ساعته
  "text": "<متن کوتاه یادآور>"
}}
اگر زمان مبهم یا گذشته بود، نزدیک‌ترین زمان منطقی آینده را انتخاب کن."""

def extract_json_block(s):
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
