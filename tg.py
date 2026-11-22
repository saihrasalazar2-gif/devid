"""
Telegram Bot with FORCE JOIN, CREDITS, and REFERRAL SYSTEM.
"""
from __future__ import annotations
import asyncio
import os
import time
import traceback
import sqlite3
import shutil
from typing import Optional, List, Dict, Any

import aiohttp

# ==== Core imports ====
from mlbb_core import (
    _check_with_ban, _check_with_ban_single,
    _fetch_creation_date_only, check_ban_v2_async,
    send_session_kick, fetch_session_profile,
    fmt_timestamp_full, fmt_age, fmt_dur,
    gen_and_device, gen_ios_device,
    _fast_valid_check,
)

# ==========================================
# Config & Tokens
# ==========================================
BOT_TOKEN = "9241586061:AAGm6Cbi4RnD64eCVEIwveQK-7WKVjX9ye0"
ADMIN_ID = 9071386675

CHANNEL_ID = "@nafaelmain1" 
CHANNEL_LINK = "https://t.me/nafaelmain1"

RESULTS_DIR = "tg_results"
os.makedirs(RESULTS_DIR, exist_ok=True)
DB_FILE = "bot_data.db"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MAX_MSG_LEN = 3800
EDIT_INTERVAL = 2.0
POLL_TIMEOUT = 30

# ==========================================
# Database Setup
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 5, referred_by INTEGER)''')
    conn.commit()
    conn.close()

def get_user(user_id: int) -> dict:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits, referred_by FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        row = (5, None)
    conn.close()
    return {"credits": row[0], "referred_by": row[1]}

def update_credits(user_id: int, amount: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_credit(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ? AND credits > 0", (user_id,))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

def set_referrer(user_id: int, referrer_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET referred_by = ? WHERE user_id = ? AND referred_by IS NULL", (referrer_id, user_id))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# Telegram API Client
# ==========================================
class TG:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _call(self, method: str, **params) -> dict:
        await self.start()
        try:
            async with self.session.post(f"{self.base}/{method}", json=params) as r:
                return await r.json()
        except Exception as e:
            return {"ok": False, "description": f"HTTP error: {e}"}

    async def send_message(self, chat_id: int, text: str, kb=None, parse_mode: str = "MarkdownV2") -> Optional[int]:
        text = truncate(text)
        params: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode: params["parse_mode"] = parse_mode
        if kb: params["reply_markup"] = kb
        res = await self._call("sendMessage", **params)
        if not res.get("ok"):
            params.pop("parse_mode", None)
            res = await self._call("sendMessage", **params)
        if res.get("ok"): return res["result"]["message_id"]
        return None

    async def edit_message(self, chat_id: int, message_id: int, text: str, kb=None, parse_mode: str = "MarkdownV2") -> bool:
        text = truncate(text)
        params: Dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode: params["parse_mode"] = parse_mode
        if kb: params["reply_markup"] = kb
        res = await self._call("editMessageText", **params)
        if res.get("ok"): return True
        desc = (res.get("description") or "").lower()
        if "not modified" in desc: return True
        if "parse" in desc or "entit" in desc:
            params.pop("parse_mode", None)
            res2 = await self._call("editMessageText", **params)
            return res2.get("ok", False)
        return False

    async def answer_callback(self, callback_id: str, text: str = "", show_alert: bool = False):
        await self._call("answerCallbackQuery", callback_query_id=callback_id, text=text, show_alert=show_alert)

    async def get_updates(self, offset: int = 0) -> list:
        res = await self._call("getUpdates", offset=offset, timeout=POLL_TIMEOUT, allowed_updates=["message", "callback_query"])
        return res.get("result", []) if res.get("ok") else []

    async def download_file(self, file_id: str) -> Optional[bytes]:
        res = await self._call("getFile", file_id=file_id)
        if not res.get("ok"): return None
        path = res["result"].get("file_path")
        if not path: return None
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
        try:
            async with self.session.get(url) as r:
                return await r.read()
        except: return None

    async def send_document(self, chat_id: int, filepath: str, filename: str, caption: str = "") -> bool:
        await self.start()
        try:
            with open(filepath, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("chat_id", str(chat_id))
                if caption:
                    form.add_field("caption", truncate(caption))
                    form.add_field("parse_mode", "MarkdownV2")
                form.add_field("document", f, filename=filename)
                async with self.session.post(f"{self.base}/sendDocument", data=form) as r:
                    return (await r.json()).get("ok", False)
        except: return False

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        res = await self._call("deleteMessage", chat_id=chat_id, message_id=message_id)
        return res.get("ok", False)

    async def check_join(self, user_id: int) -> bool:
        if not CHANNEL_ID or CHANNEL_ID == "@your_channel_username":
            return True
        res = await self._call("getChatMember", chat_id=CHANNEL_ID, user_id=user_id)
        if not res.get("ok"):
            print(f"Join check failed: {res.get('description')}")
            return False
        status = res["result"].get("status")
        return status in ["creator", "administrator", "member"]

TG_API = TG(BOT_TOKEN)

# ==========================================
# Helpers
# ==========================================
def md(text) -> str:
    if text is None: return "N/A"
    s = str(text)
    for ch in r'_*[]()~`>#+-=|{}.!': s = s.replace(ch, "\\" + ch)
    return s

def truncate(text: str, limit: int = MAX_MSG_LEN) -> str:
    if not text: return ""
    if len(text) <= limit: return text
    return text[: limit - 20] + "\n\\.\\.\\. \\(truncated\\)"

def progress_bar(current: int, total: int, width: int = 16) -> str:
    if total <= 0: return "░" * width
    ratio = min(max(current / total, 0), 1)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)

# ==========================================
# Session
# ==========================================
class UserSession:
    def __init__(self):
        self.state = "idle"
        self.action: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self.watcher: Optional[asyncio.Task] = None
        self.cancel_event: Optional[asyncio.Event] = None
        self.start_time = 0.0
        self.status_msg_id: Optional[int] = None
        self.chat_id: Optional[int] = None
        self.total = 0
        self.processed = 0
        self.valid = 0
        self.invalid = 0
        self.last_edit = 0.0
        self.title = ""
        self.extra: Dict[str, Any] = {}

SESSIONS: Dict[str, UserSession] = {}

def get_session(user_id: int, chat_id: int) -> UserSession:
    key = f"{user_id}:{chat_id}"
    if key not in SESSIONS: SESSIONS[key] = UserSession()
    return SESSIONS[key]

# ==========================================
# Keyboards
# ==========================================
def kb_join():
    return {"inline_keyboard": [
        [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
        [{"text": "✅ Verify Join", "callback_data": "verify_join"}]
    ]}

def kb_main(user_id: int):
    credits = get_user(user_id)["credits"]
    return {"inline_keyboard": [
        [{"text": "🔍 Bulk Check (1 credit)", "callback_data": "menu:bulk"}],
        [{"text": "⚡ Valid Only (1 credit)", "callback_data": "menu:valid"}],
        [{"text": "🎯 Single Check (1 credit)", "callback_data": "menu:single"}],
        [{"text": "🔥 Bruteforce Kicker (1 credit)", "callback_data": "menu:brute"}],
        [{"text": "📅 Creation Date (1 credit)", "callback_data": "menu:createdate"}],
        [{"text": "🚫 Ban Check Only (1 credit)", "callback_data": "menu:bancheck"}],
        [{"text": "🎲 Generate Device IDs (1 credit)", "callback_data": "menu:gen"}],
        [{"text": f"💳 Credits: {credits}", "callback_data": "menu:status"}],
        [{"text": "🎁 Referral Link", "callback_data": "menu:ref"}],
    ]}

def kb_back():
    return {"inline_keyboard": [[{"text": "⬅️ Back to Menu", "callback_data": "menu:main"}]]}

def kb_cancel():
    return {"inline_keyboard": [[{"text": "❌ Cancel", "callback_data": "menu:cancel"}]]}

def kb_gen_type():
    return {"inline_keyboard": [
        [{"text": "📱 Android (and_)", "callback_data": "gen:and"}],
        [{"text": "🍎 iOS (ios_)", "callback_data": "gen:ios"}],
        [{"text": "📦 Both Mixed", "callback_data": "gen:both"}],
        [{"text": "⬅️ Back", "callback_data": "menu:main"}],
    ]}

def kb_brute_mode():
    return {"inline_keyboard": [
        [{"text": "Single (1x)", "callback_data": "brute:1"}],
        [{"text": "Standard (10x)", "callback_data": "brute:10"}],
        [{"text": "Fast (50x)", "callback_data": "brute:50"}],
        [{"text": "Aggressive (100x)", "callback_data": "brute:100"}],
        [{"text": "⬅️ Back", "callback_data": "menu:main"}],
    ]}

# ==========================================
# Rendering
# ==========================================
def render_menu(user_id: int) -> tuple:
    credits = get_user(user_id)["credits"]
    text = (
        "*🛠 XEI DEVICE ID TOOLS*\n"
        "_Made by Xei TG @xeiloves_\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 *Your Credits:* `{credits}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Choose an option below \\(1 credit per use\\):"
    )
    return text, kb_main(user_id)

def render_running(s: UserSession, title: str) -> str:
    elapsed = time.time() - s.start_time if s.start_time else 0
    speed = s.processed / elapsed if elapsed > 0 else 0
    pct = (s.processed / s.total * 100) if s.total else 0
    eta = (s.total - s.processed) / speed if speed > 0 else 0
    bar = progress_bar(s.processed, s.total)
    return (
        f"*{md(title)}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"`{bar}` *{pct:.1f}%*\n"
        f"📦 `{s.processed:,}/{s.total:,}`\n"
        f"⚡ Speed: `{speed:.1f}/s`\n"
        f"⏱ Elapsed: `{fmt_dur(elapsed)}`\n"
        f"⏳ ETA: `{fmt_dur(eta)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Valid:* `{s.valid:,}`\n"
        f"❌ *Invalid:* `{s.invalid:,}`"
    )

def render_profile(player: dict, did: str, acc, zone, ban_info: dict = None) -> str:
    ban_info = ban_info or {}
    status = ban_info.get("status", "UNKNOWN")
    emoji = {"BANNED": "🔴", "NOT BANNED": "🟢"}.get(status, "🟡")
    lines = [
        "*👤 ACCOUNT PROFILE*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🔑 `{md(did[:40])}{'...' if len(did) > 40 else ''}`",
        f"🆔 Account: `{md(acc)}`",
        f"🌐 Zone: `{md(zone)}`",
        f"📛 Nickname: *{md(player.get('nickname', 'N/A'))}*",
        f"📊 Level: `{md(player.get('level', 0))}`",
        f"🏆 Rank: `{md(player.get('current_rank', 'N/A'))}`",
        f"🥇 Highest: `{md(player.get('high_rank', 'N/A'))}`",
        f"🎨 Skins: `{md(player.get('skin_count', 0))}`",
        f"⚔ Heroes: `{md(player.get('hero_count', 0))}`",
        f"🎮 Battles: `{md(player.get('total_battles', 0))}`",
        f"📈 WR: `{md(player.get('win_rate', 'N/A'))}`",
        f"💰 Collector: `{md(player.get('collector_tier', 'N/A'))}`",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 Created: `{md(player.get('creation_date', 'N/A'))}`",
        f"🕰 Age: `{md(player.get('creation_age', 'N/A'))}`",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{emoji} Ban: *{md(status)}*",
    ]
    if status == "BANNED":
        lines.append(f"📝 Reason: `{md(ban_info.get('reason', 'N/A'))}`")
        lines.append(f"⏳ Duration: `{md(ban_info.get('duration', 'N/A'))}`")
    return "\n".join(lines)

# ==========================================
# Live watcher
# ==========================================
async def live_watcher(sess: UserSession, title: str, chat_id: int):
    mid = sess.status_msg_id
    if not mid: return
    while True:
        if sess.task is None or sess.task.done(): break
        now = time.time()
        if now - sess.last_edit >= EDIT_INTERVAL:
            await TG_API.edit_message(chat_id, mid, render_running(sess, title), kb_cancel())
            sess.last_edit = now
        await asyncio.sleep(0.5)

    elapsed = time.time() - sess.start_time if sess.start_time else 0
    speed = sess.processed / elapsed if elapsed > 0 else 0
    final = (
        f"✅ *{md(title)} — DONE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 `{sess.processed:,}/{sess.total:,}`\n"
        f"✅ *Valid:* `{sess.valid:,}`\n"
        f"❌ *Invalid:* `{sess.invalid:,}`\n"
        f"⏱ `{fmt_dur(elapsed)}`  ⚡ `{speed:.1f}/s`"
    )
    await TG_API.edit_message(chat_id, mid, final, kb_back())

    valid_path = os.path.join(RESULTS_DIR, "valid.txt")
    if sess.valid > 0 and os.path.exists(valid_path) and os.path.getsize(valid_path) > 0:
        hits_filename = f"hits_{int(time.time())}.txt"
        hits_filepath = os.path.join(RESULTS_DIR, hits_filename)
        shutil.copy(valid_path, hits_filepath)
        await TG_API.send_document(chat_id, hits_filepath, hits_filename, caption=f"✅ *Hits Found!*\n📦 `{sess.valid:,}` valid IDs saved.")
        open(valid_path, "w").close() 
    else:
        await TG_API.send_message(chat_id, "⚠️ 0 hits found in this run\\.")

    sess.state = "idle"
    sess.action = None

# ==========================================
# Bulk runners
# ==========================================
async def run_bulk_full(sess: UserSession, ids: List[str], concurrency: int):
    from mlbb_core import _Bucket, save_result
    sem = asyncio.Semaphore(concurrency)
    bucket = _Bucket(1000)
    lock = asyncio.Lock()
    sess.total = len(ids)

    async def worker(did):
        if sess.cancel_event.is_set(): return
        try: res = await _check_with_ban(did, sem, bucket)
        except: res = None
        async with lock:
            sess.processed += 1
            if res:
                sess.valid += 1
                try: save_result(res)
                except: pass
            else: sess.invalid += 1

    tasks = [asyncio.create_task(worker(d)) for d in ids]
    try: await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for t in tasks:
            if not t.done(): t.cancel()

async def run_valid_only(sess: UserSession, ids: List[str], concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    sess.total = len(ids)
    loop = asyncio.get_event_loop()

    async def worker(did):
        if sess.cancel_event.is_set(): return
        async with sem:
            try: ok = await loop.run_in_executor(None, _fast_valid_check, did, 4.0)
            except: ok = False
        async with lock:
            sess.processed += 1
            if ok:
                sess.valid += 1
                with open(os.path.join(RESULTS_DIR, "valid.txt"), "a") as f:
                    f.write(did + "\n")
            else: sess.invalid += 1

    tasks = [asyncio.create_task(worker(d)) for d in ids]
    try: await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for t in tasks:
            if not t.done(): t.cancel()

# ==========================================
# Action executors
# ==========================================
async def start_bulk(chat_id: int, user_id: int, sess: UserSession, real_action: str, ids: List[str], concurrency: int):
    title = "Bulk Check (Full)" if real_action == "bulk_full" else "Valid Only (FAST)"
    sess.state = "running"
    sess.action = real_action
    sess.start_time = time.time()
    sess.processed = 0
    sess.valid = 0
    sess.invalid = 0
    sess.total = len(ids)
    sess.cancel_event = asyncio.Event()
    sess.last_edit = 0.0
    sess.chat_id = chat_id
    sess.title = title

    mid = await TG_API.send_message(chat_id, render_running(sess, title), kb_cancel())
    sess.status_msg_id = mid

    if real_action == "bulk_full": sess.task = asyncio.create_task(run_bulk_full(sess, ids, concurrency))
    else: sess.task = asyncio.create_task(run_valid_only(sess, ids, concurrency))

    sess.watcher = asyncio.create_task(live_watcher(sess, title, chat_id))

async def do_single_check(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "⏳ Checking device ID\\.\\.\\.")
    try: result = await _check_with_ban_single(did)
    except Exception as e:
        if mid: await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return
    if not result:
        if mid: await TG_API.edit_message(chat_id, mid, "❌ Login failed\\. Device ID invalid or dead\\.", kb_back())
        return
    player = result.get("player")
    if not player:
        text = f"⚠️ *Account info unavailable*\n🆔 Account: `{md(result.get('acc'))}`\n🌐 Zone: `{md(result.get('zone'))}`\nBan: `{md(result.get('ban_info', {}).get('status', 'UNKNOWN'))}`"
        if mid: await TG_API.edit_message(chat_id, mid, text, kb_back())
        return
    text = render_profile(player, did, result.get("acc"), result.get("zone"), result.get("ban_info", {}))
    if mid: await TG_API.edit_message(chat_id, mid, text, kb_back())

async def do_createdate(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "📅 Fetching creation date\\.\\.\\.")
    loop = asyncio.get_event_loop()
    try: result = await loop.run_in_executor(None, lambda: asyncio.run(_fetch_creation_date_only(did)))
    except Exception as e:
        if mid: await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return
    if not result:
        if mid: await TG_API.edit_message(chat_id, mid, "❌ Login failed\\. Device ID invalid or dead\\.", kb_back())
        return
    ts = result.get("creation_ts", 0)
    date_str, age_str = ("N/A", "N/A")
    if ts and ts > 1_451_577_600:
        date_str = fmt_timestamp_full(ts)
        age_str = fmt_age(ts)
    text = f"*📅 Creation Date*\n🔑 `{md(did[:40])}`\n🆔 Account: `{md(result.get('acc'))}`\n🌐 Zone: `{md(result.get('zone'))}`\n📅 Created: *{md(date_str)}*\n🕰 Age: *{md(age_str)}*"
    if mid: await TG_API.edit_message(chat_id, mid, text, kb_back())

async def do_bancheck(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "🚫 Checking ban status\\.\\.\\.")
    try: result = await check_ban_v2_async(did)
    except Exception a
