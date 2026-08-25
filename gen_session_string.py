#!/usr/bin/env python3
"""One-time helper: log in with phone/code and print a Telethon StringSession.

Run this LOCALLY (or anywhere interactive) once, then put the printed string
into the SESSION_STRING environment variable on Railway. The string IS your
login session — treat it like a password:

    python3 gen_session_string.py

Requires API_ID / API_HASH / PHONE_NUMBER in .env or environment.
"""
import sys

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import Config


def main():
    if not Config.API_ID or not Config.API_HASH:
        print("❌ API_ID / API_HASH در .env تنظیم نشده است.")
        sys.exit(1)

    # StringSession() with no args = brand-new in-memory session → forces a fresh login
    with TelegramClient(StringSession(), Config.API_ID, Config.API_HASH) as client:
        me = client.loop.run_until_complete(client.get_me())
        s = client.session.save()
        print()
        print("=" * 60)
        print(f"✅ لاگین موفق: {me.first_name} (@{me.username}) [ID: {me.id}]")
        print("=" * 60)
        print("SESSION_STRING تو (در Railway به‌عنوان متغیر محیطی ست کن):")
        print()
        print(s)
        print()
        print("⚠️ این رشته مثل پسوردت هست — جایی پخشش نکن.")
        print("   بعدش می‌تونی این فایل session لوکال رو پاک کنی.")


if __name__ == "__main__":
    main()
