#!/usr/bin/env python3
"""Logic tests for GhostGram new features (no network / no telethon import)."""
import sys, json, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reminder_parser import reminder_parser
from datetime import datetime

print("=== ReminderParser tests ===")
now = reminder_parser._iran_now()

cases = [
    ("ساعت 21 به علی بگو تماس بگیره", True),
    ("فردا ساعت 9:30 جلسه یادت باشه", True),
    ("تا ۲ ساعت دیگه دارو بخور", True),
    ("30 دقیقه دیگه بیا", True),
    ("پس فردا ساعت 8 صبح بیدارم کن", True),  # پس‌فردا handled by ساعت branch? check
    ("یه چیزی کاملاً نامربوط بدون زمان", False),
]
for text, expect_ok in cases:
    due, rem = reminder_parser.parse(text)
    ok = (due is not None)
    status = "✅" if ok == expect_ok else "❌"
    print(f"{status} '{text[:40]}' → parsed={ok} expected={expect_ok} | due={due} | rem={str(rem)[:40]}")

# Sanity: 'ساعت X' must be in the future
due, _ = reminder_parser.parse("ساعت 23:45 تست")
if due:
    assert due > now, "due must be future"
    print("✅ future-time invariant holds")
# 'تا 2 ساعت دیگه' ≈ now+2h (tolerance 5 min)
due, _ = reminder_parser.parse("تا ۲ ساعت دیگه دارو بخور")
delta_min = (due - now).total_seconds() / 60
assert abs(delta_min - 120) < 5, f"expected ~120min got {delta_min}"
print(f"✅ relative time OK ({delta_min:.1f} min)")

print()
print("=== APIUsageTracker persistence test ===")
os.chdir(tempfile.mkdtemp())
import api_tracker as _api_tracker_mod
api_tracker = _api_tracker_mod.api_tracker
key = "TESTKEY123"
api_tracker.record_usage(key)
api_tracker.record_error(key); api_tracker.record_error(key); api_tracker.record_error(key)
assert key in api_tracker.banned_until, "should be banned after 3 errors"
on_disk = json.load(open("api_usage.json"))
assert "_bans" in on_disk and key in on_disk["_bans"], "ban must be persisted"
print("✅ ban persisted to disk:", list(on_disk["_bans"].keys()))
assert api_tracker.is_key_available(key) is False, "banned key must be unavailable"
print("✅ banned key correctly unavailable")
# simulate restart: fresh instance reads the ban
api_tracker2 = _api_tracker_mod.APIUsageTracker(filename="api_usage.json")
assert key in api_tracker2.banned_until, "ban must survive restart"
assert api_tracker2.is_key_available(key) is False
print("✅ ban survives restart (fresh instance)")
# daily usage persisted too
today_key_data = on_disk.get(key)
assert today_key_data and today_key_data["count"] >= 1
print(f"✅ usage persisted: {today_key_data}")

print()
print("ALL LOGIC TESTS PASSED 🎉")
