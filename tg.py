"""
Telegram Bot wrapper for XEI Device ID Tools — aiohttp edition (FIXED).
Rename your original script to `mlbb_core.py` in the same folder.
"""
from __future__ import annotations
import asyncio
import os
import time
import traceback
import json
import threading
from typing import Optional, List, Dict, Any

import aiohttp

# ==== Core imports ====
from mlbb_core import (
    _check_with_ban, _check_with_ban_single,
    _fetch_creation_date_only, check_ban_v2_async,
    send_session_kick, fetch_session_profile,
    fmt_timestamp_full, fmt_age, fmt_dur,
    gen_and_device, gen_ios_device,
    _fast_valid_check,  # needed by valid-only runner
)

# ==========================================
# Config
# ==========================================
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ALLOWED_USERS: set = set()
if os.environ.get("TG_ALLOWED_USERS"):
    ALLOWED_USERS = {int(x) for x in os.environ["TG_ALLOWED_USERS"].split(",") if x.strip().isdigit()}

RESULTS_DIR = "tg_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MAX_MSG_LEN = 3800
EDIT_INTERVAL = 2.0      # seconds between live edits
POLL_TIMEOUT = 30        # long-poll timeout

# ==========================================
# Telegram API Client
# ==========================================
class TG:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )

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

    async def send_message(self, chat_id: int, text: str, kb=None,
                           parse_mode: str = "MarkdownV2") -> Optional[int]:
        text = truncate(text)
        params: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if kb:
            params["reply_markup"] = kb
        res = await self._call("sendMessage", **params)
        if not res.get("ok"):
            # retry without markdown
            params.pop("parse_mode", None)
            res = await self._call("sendMessage", **params)
        if res.get("ok"):
            return res["result"]["message_id"]
        return None

    async def edit_message(self, chat_id: int, message_id: int, text: str,
                          kb=None, parse_mode: str = "MarkdownV2") -> bool:
        text = truncate(text)
        params: Dict[str, Any] = {
            "chat_id": chat_id, "message_id": message_id, "text": text,
        }
        if parse_mode:
            params["parse_mode"] = parse_mode
        if kb:
            params["reply_markup"] = kb
        res = await self._call("editMessageText", **params)
        if res.get("ok"):
            return True
        desc = (res.get("description") or "").lower()
        if "not modified" in desc:
            return True  # treat as success
        # retry without markdown
        if "parse" in desc or "entit" in desc:
            params.pop("parse_mode", None)
            res2 = await self._call("editMessageText", **params)
            return res2.get("ok", False)
        return False

    async def answer_callback(self, callback_id: str, text: str = ""):
        await self._call("answerCallbackQuery",
                         callback_query_id=callback_id, text=text)

    async def get_updates(self, offset: int = 0) -> list:
        res = await self._call(
            "getUpdates", offset=offset, timeout=POLL_TIMEOUT,
            allowed_updates=["message", "callback_query"]
        )
        if res.get("ok"):
            return res["result"]
        return []

    async def download_file(self, file_id: str) -> Optional[bytes]:
        res = await self._call("getFile", file_id=file_id)
        if not res.get("ok"):
            return None
        path = res["result"].get("file_path")
        if not path:
            return None
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
        try:
            async with self.session.get(url) as r:
                return await r.read()
        except Exception:
            return None

    async def send_document(self, chat_id: int, filepath: str,
                           filename: str, caption: str = "") -> bool:
        await self.start()
        try:
            with open(filepath, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("chat_id", str(chat_id))
                if caption:
                    form.add_field("caption", truncate(caption))
                    form.add_field("parse_mode", "MarkdownV2")
                form.add_field("document", f, filename=filename)
                async with self.session.post(
                    f"{self.base}/sendDocument", data=form
                ) as r:
                    res = await r.json()
                    return res.get("ok", False)
        except Exception:
            return False

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        res = await self._call("deleteMessage",
                              chat_id=chat_id, message_id=message_id)
        return res.get("ok", False)


TG_API = TG(BOT_TOKEN)


# ==========================================
# Helpers
# ==========================================
def md(text) -> str:
    if text is None:
        return "N/A"
    s = str(text)
    for ch in r'_*[]()~`>#+-=|{}.!':
        s = s.replace(ch, "\\" + ch)
    return s


def truncate(text: str, limit: int = MAX_MSG_LEN) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\\.\\.\\. \\(truncated\\)"


def progress_bar(current: int, total: int, width: int = 16) -> str:
    if total <= 0:
        return "░" * width
    ratio = min(max(current / total, 0), 1)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def authorized(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


# ==========================================
# Session
# ==========================================
class UserSession:
    def __init__(self):
        self.state = "idle"              # idle | waiting_input | running
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
    if key not in SESSIONS:
        SESSIONS[key] = UserSession()
    return SESSIONS[key]


# ==========================================
# Keyboards
# ==========================================
def kb_main():
    return {"inline_keyboard": [
        [{"text": "🔍 Bulk Check (Full)", "callback_data": "menu:bulk"}],
        [{"text": "⚡ Valid Only (FAST)", "callback_data": "menu:valid"}],
        [{"text": "🎯 Single Check", "callback_data": "menu:single"}],
        [{"text": "🔥 Bruteforce Kicker", "callback_data": "menu:brute"}],
        [{"text": "📅 Creation Date", "callback_data": "menu:createdate"}],
        [{"text": "🚫 Ban Check Only", "callback_data": "menu:bancheck"}],
        [{"text": "🎲 Generate Device IDs", "callback_data": "menu:gen"}],
        [{"text": "📊 Live Status", "callback_data": "menu:status"}],
    ]}


def kb_back():
    return {"inline_keyboard": [
        [{"text": "⬅️ Back to Menu", "callback_data": "menu:main"}]
    ]}


def kb_cancel():
    return {"inline_keyboard": [
        [{"text": "❌ Cancel", "callback_data": "menu:cancel"}]
    ]}


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
def render_menu() -> tuple:
    text = (
        "*🛠 XEI DEVICE ID TOOLS*\n"
        "_Made by Xei TG @xeiloves_\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Choose an option below:"
    )
    return text, kb_main()


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
    if not mid:
        return
    while True:
        if sess.task is None or sess.task.done():
            break
        now = time.time()
        if now - sess.last_edit >= EDIT_INTERVAL:
            await TG_API.edit_message(chat_id, mid, render_running(sess, title), kb_cancel())
            sess.last_edit = now
        await asyncio.sleep(0.5)

    # final
    elapsed = time.time() - sess.start_time if sess.start_time else 0
    speed = sess.processed / elapsed if elapsed > 0 else 0
    final = (
        f"✅ *{md(title)} — DONE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 `{sess.processed:,}/{sess.total:,}`\n"
        f"✅ *Valid:* `{sess.valid:,}`\n"
        f"❌ *Invalid:* `{sess.invalid:,}`\n"
        f"⏱ `{fmt_dur(elapsed)}`  ⚡ `{speed:.1f}/s`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Saved: `{RESULTS_DIR}/valid.txt`"
    )
    await TG_API.edit_message(chat_id, mid, final, kb_back())
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
        if sess.cancel_event.is_set():
            return
        try:
            res = await _check_with_ban(did, sem, bucket)
        except Exception:
            res = None
        async with lock:
            sess.processed += 1
            if res:
                sess.valid += 1
                try:
                    save_result(res)
                except Exception:
                    pass
            else:
                sess.invalid += 1

    tasks = [asyncio.create_task(worker(d)) for d in ids]
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()


async def run_valid_only(sess: UserSession, ids: List[str], concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    sess.total = len(ids)
    loop = asyncio.get_event_loop()

    async def worker(did):
        if sess.cancel_event.is_set():
            return
        async with sem:
            try:
                ok = await loop.run_in_executor(None, _fast_valid_check, did, 4.0)
            except Exception:
                ok = False
        async with lock:
            sess.processed += 1
            if ok:
                sess.valid += 1
                with open(os.path.join(RESULTS_DIR, "valid.txt"), "a") as f:
                    f.write(did + "\n")
            else:
                sess.invalid += 1

    tasks = [asyncio.create_task(worker(d)) for d in ids]
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()


# ==========================================
# Action executors
# ==========================================
async def start_bulk(chat_id: int, user_id: int, sess: UserSession,
                    real_action: str, ids: List[str], concurrency: int):
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

    mid = await TG_API.send_message(
        chat_id, render_running(sess, title), kb_cancel()
    )
    sess.status_msg_id = mid

    if real_action == "bulk_full":
        sess.task = asyncio.create_task(run_bulk_full(sess, ids, concurrency))
    else:
        sess.task = asyncio.create_task(run_valid_only(sess, ids, concurrency))

    sess.watcher = asyncio.create_task(live_watcher(sess, title, chat_id))


async def do_single_check(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "⏳ Checking device ID\\.\\.\\.")
    try:
        result = await _check_with_ban_single(did)
    except Exception as e:
        traceback.print_exc()
        if mid:
            await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return

    if not result:
        if mid:
            await TG_API.edit_message(chat_id, mid,
                "❌ Login failed\\. Device ID invalid or dead\\.", kb_back())
        return

    player = result.get("player")
    if not player:
        text = (
            "⚠️ *Account info unavailable*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Account: `{md(result.get('acc'))}`\n"
            f"🌐 Zone: `{md(result.get('zone'))}`\n"
            f"Ban: `{md(result.get('ban_info', {}).get('status', 'UNKNOWN'))}`"
        )
        if mid:
            await TG_API.edit_message(chat_id, mid, text, kb_back())
        return

    text = render_profile(player, did, result.get("acc"), result.get("zone"),
                         result.get("ban_info", {}))
    if mid:
        await TG_API.edit_message(chat_id, mid, text, kb_back())


async def do_createdate(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "📅 Fetching creation date\\.\\.\\.")
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: asyncio.run(_fetch_creation_date_only(did)))
    except Exception as e:
        traceback.print_exc()
        if mid:
            await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return

    if not result:
        if mid:
            await TG_API.edit_message(chat_id, mid,
                "❌ Login failed\\. Device ID invalid or dead\\.", kb_back())
        return

    ts = result.get("creation_ts", 0)
    if ts and ts > 1_451_577_600:
        date_str = fmt_timestamp_full(ts)
        age_str = fmt_age(ts)
    else:
        date_str = "N/A"
        age_str = "N/A"

    text = (
        "*📅 Creation Date*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 `{md(did[:40])}{'...' if len(did) > 40 else ''}`\n"
        f"🆔 Account: `{md(result.get('acc'))}`\n"
        f"🌐 Zone: `{md(result.get('zone'))}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Created: *{md(date_str)}*\n"
        f"🕰 Age: *{md(age_str)}*"
    )
    if mid:
        await TG_API.edit_message(chat_id, mid, text, kb_back())


async def do_bancheck(chat_id: int, did: str):
    mid = await TG_API.send_message(chat_id, "🚫 Checking ban status\\.\\.\\.")
    try:
        result = await check_ban_v2_async(did)
    except Exception as e:
        traceback.print_exc()
        if mid:
            await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return

    if not result:
        if mid:
            await TG_API.edit_message(chat_id, mid, "❌ Ban check failed\\.", kb_back())
        return

    status = result.get("status", "UNKNOWN")
    emoji = {"BANNED": "🔴", "NOT BANNED": "🟢"}.get(status, "🟡")
    text = (
        f"*{emoji} Ban Check*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 `{md(did[:40])}{'...' if len(did) > 40 else ''}`\n"
        f"🆔 Account: `{md(result.get('account_id'))}`\n"
        f"🌐 Zone: `{md(result.get('zone_id'))}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status: *{md(status)}*"
    )
    if status == "BANNED":
        text += (
            f"\n📝 Reason: `{md(result.get('reason', 'N/A'))}`"
            f"\n🔢 Code: `{md(result.get('ban_code', 'N/A'))}`"
            f"\n⏳ Duration: `{md(result.get('duration', 'N/A'))}`"
        )
    if mid:
        await TG_API.edit_message(chat_id, mid, text, kb_back())


async def do_generate(chat_id: int, sess: UserSession, gen_type: str, n: int):
    mid = await TG_API.send_message(
        chat_id, f"🎲 Generating `{n:,}` {md(gen_type)} IDs\\.\\.\\."
    )
    start = time.time()

    def generate_sync():
        out = []
        if gen_type == "and":
            for c in range(n):
                out.append(gen_and_device(c))
        elif gen_type == "ios":
            for c in range(n):
                out.append(gen_ios_device(c))
        else:
            for c in range(n):
                out.append(gen_and_device(c) if c % 2 == 0 else gen_ios_device(c))
        return out

    loop = asyncio.get_event_loop()
    lines = await loop.run_in_executor(None, generate_sync)
    elapsed = time.time() - start

    filename = f"generated_{gen_type}_{int(time.time())}.txt"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if mid:
        await TG_API.delete_message(chat_id, mid)

    await TG_API.send_document(
        chat_id, filepath, filename,
        caption=(
            f"🎲 *Generated {n:,} IDs*\n"
            f"📦 `{md(gen_type)}`  📁 `{size_mb:.2f} MB`  ⏱ `{elapsed:.2f}s`"
        )
    )
    await TG_API.send_message(chat_id, "✅ Done\\. Use menu to continue\\.",
                             kb_back())
    sess.state = "idle"
    sess.action = None


async def execute_brute(chat_id: int, sess: UserSession, count: int,
                       target: str):
    mid = await TG_API.send_message(
        chat_id,
        f"🔍 Verifying target\\.\\.\\.\n`{md(target[:40])}{'...' if len(target) > 40 else ''}`"
    )
    loop = asyncio.get_event_loop()
    try:
        profile = await loop.run_in_executor(None, fetch_session_profile, target)
    except Exception as e:
        traceback.print_exc()
        if mid:
            await TG_API.edit_message(chat_id, mid, f"❌ Error: `{md(str(e))}`", kb_back())
        return

    if not profile:
        if mid:
            await TG_API.edit_message(chat_id, mid,
                "❌ Device ID invalid or dead\\.", kb_back())
        return

    total = count
    sent = 0
    ok_count = 0
    latencies = []
    start = time.time()

    kick_mid = mid
    for i in range(total):
        try:
            ok, lat, _ = await loop.run_in_executor(None, send_session_kick, profile)
            latencies.append(lat)
            sent += 1
            if ok:
                ok_count += 1
        except Exception:
            sent += 1

        if (i % 5 == 0) or i == total - 1:
            elapsed = time.time() - start
            speed = sent / elapsed if elapsed > 0 else 0
            avg_lat = sum(latencies) / len(latencies) if latencies else 0
            if kick_mid:
                await TG_API.edit_message(
                    chat_id, kick_mid,
                    (
                        f"🔥 *Kicking {md(profile.get('nickname', 'N/A'))}*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"`{progress_bar(sent, total)}` *{sent/total*100:.0f}%*\n"
                        f"✅ OK: `{ok_count}`\n"
                        f"❌ Fail: `{sent - ok_count}`\n"
                        f"⚡ Speed: `{speed:.1f}/s`\n"
                        f"📡 Avg Lat: `{avg_lat:.0f}ms`"
                    ),
                    kb_cancel()
                )
        await asyncio.sleep(0.2)

    elapsed = time.time() - start
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    if kick_mid:
        await TG_API.edit_message(
            chat_id, kick_mid,
            (
                "✅ *Kicker Done*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 `{md(profile.get('nickname', 'N/A'))}`\n"
                f"🔁 Loops: `{sent}/{total}`\n"
                f"✅ Success: `{ok_count}`\n"
                f"❌ Fail: `{sent - ok_count}`\n"
                f"⏱ `{fmt_dur(elapsed)}`\n"
                f"📡 Avg Lat: `{avg_lat:.0f}ms`"
            ),
            kb_back()
        )


# ==========================================
# Update dispatcher
# ==========================================
async def handle_callback(cb: dict):
    cb_id = cb["id"]
    user_id = cb["from"]["id"]
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb.get("data", "")

    await TG_API.answer_callback(cb_id)

    if not authorized(user_id):
        await TG_API.edit_message(chat_id, msg_id, "⛔ Unauthorized.", kb_back())
        return

    sess = get_session(user_id, chat_id)
    sess.chat_id = chat_id

    if data == "menu:main":
        sess.state = "idle"
        sess.action = None
        text, kb = render_menu()
        await TG_API.edit_message(chat_id, msg_id, text, kb)
        return

    if data == "menu:cancel":
        if sess.cancel_event:
            sess.cancel_event.set()
        if sess.task and not sess.task.done():
            sess.task.cancel()
        sess.state = "idle"
        sess.action = None
        text, kb = render_menu()
        await TG_API.edit_message(chat_id, msg_id, text, kb)
        return

    if data == "menu:bulk":
        sess.state = "waiting_input"
        sess.action = "bulk_full"
        await TG_API.edit_message(
            chat_id, msg_id,
            (
                "🔍 *Bulk Check (Full)*\n\n"
                "Send a `.txt` file with Device IDs \\(one per line\\)\n"
                "or paste IDs \\(newline\\-separated\\)\\.\n\n"
                "Full info \\+ ban status\\. Slower\\."
            ),
            kb_back()
        )
        return

    if data == "menu:valid":
        sess.state = "waiting_input"
        sess.action = "valid_only"
        await TG_API.edit_message(
            chat_id, msg_id,
            (
                "⚡ *Valid Only (FAST)*\n\n"
                "Send a `.txt` file with Device IDs \\(one per line\\)\n"
                "or paste IDs \\(newline\\-separated\\)\\.\n\n"
                "Saves valid IDs only\\. Maximum speed\\."
            ),
            kb_back()
        )
        return

    if data == "menu:single":
        sess.state = "waiting_input"
        sess.action = "single"
        await TG_API.edit_message(
            chat_id, msg_id,
            "🎯 *Single Check*\n\nSend a single Device ID\\.",
            kb_back()
        )
        return

    if data == "menu:brute":
        sess.state = "waiting_input"
        sess.action = "brute_input"
        await TG_API.edit_message(
            chat_id, msg_id,
            "🔥 *Bruteforce Kicker*\n\nSend the target Device ID\\.",
            kb_back()
        )
        return

    if data == "menu:createdate":
        sess.state = "waiting_input"
        sess.action = "createdate"
        await TG_API.edit_message(
            chat_id, msg_id,
            "📅 *Creation Date*\n\nSend a single Device ID\\.",
            kb_back()
        )
        return

    if data == "menu:bancheck":
        sess.state = "waiting_input"
        sess.action = "bancheck"
        await TG_API.edit_message(
            chat_id, msg_id,
            "🚫 *Ban Check Only*\n\nSend a single Device ID\\.",
            kb_back()
        )
        return

    if data == "menu:gen":
        await TG_API.edit_message(
            chat_id, msg_id,
            "🎲 *Generate Device IDs*\n\nChoose format:",
            kb_gen_type()
        )
        return

    if data == "menu:status":
        if sess.state == "running" and sess.task and not sess.task.done():
            await TG_API.edit_message(
                chat_id, msg_id,
                render_running(sess, sess.title or "Live Status"),
                kb_cancel()
            )
        else:
            await TG_API.edit_message(
                chat_id, msg_id, "ℹ️ No task running\\.", kb_back()
            )
        return

    if data.startswith("gen:"):
        gt = data.split(":", 1)[1]
        sess.state = "waiting_input"
        sess.action = f"gen_count:{gt}"
        await TG_API.edit_message(
            chat_id, msg_id,
            f"🎲 *Generate {md(gt.upper())}*\n\nHow many? \\(e\\.g\\. `1000`, `10k`, `1m`\\)",
            kb_back()
        )
        return

    if data.startswith("brute:"):
        cnt = int(data.split(":", 1)[1])
        target = sess.extra.get("brute_target")
        if not target:
            await TG_API.edit_message(chat_id, msg_id,
                "❌ No target\\. Start over from menu\\.", kb_back())
            return
        sess.state = "running"
        await execute_brute(chat_id, sess, cnt, target)
        return


async def handle_message(msg: dict):
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]

    if not authorized(user_id):
        return

    sess = get_session(user_id, chat_id)
    sess.chat_id = chat_id
    text = (msg.get("text") or "").strip()

    # commands
    if text.startswith("/"):
        cmd = text.split()[0].lower()
        if cmd in ("/start", "/menu"):
            t, kb = render_menu()
            await TG_API.send_message(chat_id, t, kb)
            return
        if cmd == "/cancel":
            if sess.cancel_event:
                sess.cancel_event.set()
            if sess.task and not sess.task.done():
                sess.task.cancel()
            sess.state = "idle"
            sess.action = None
            t, kb = render_menu()
            await TG_API.send_message(chat_id, t, kb)
            return
        return

    if sess.state != "waiting_input":
        t, kb = render_menu()
        await TG_API.send_message(chat_id, t, kb)
        return

    action = sess.action or ""

    # ---------- BULK ----------
    if action in ("bulk_full", "valid_only"):
        ids: List[str] = []
        doc = msg.get("document")
        if doc:
            if not (doc.get("file_name") or "").lower().endswith(".txt"):
                await TG_API.send_message(chat_id,
                    "❌ Please send a `.txt` file\\.", kb_back())
                return
            raw = await TG_API.download_file(doc["file_id"])
            if raw is None:
                await TG_API.send_message(chat_id,
                    "❌ Could not download file\\.", kb_back())
                return
            content = raw.decode("utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line and len(line) >= 40 and not line.lower().endswith("none"):
                    ids.append(line)
        elif text:
            for line in text.splitlines():
                line = line.strip()
                if line and len(line) >= 40 and not line.lower().endswith("none"):
                    ids.append(line)

        if not ids:
            await TG_API.send_message(chat_id,
                "❌ No valid Device IDs found\\.", kb_back())
            return

        sess.extra["pending_ids"] = ids
        sess.action = f"run_concurrency:{action}"
        sess.state = "waiting_input"
        await TG_API.send_message(
            chat_id,
            f"📦 *Loaded {len(ids):,} IDs*\n\n"
            "Enter concurrency \\(default `200`, max `2000`\\):",
            kb_back()
        )
        return

    # ---------- CONCURRENCY ----------
    if action.startswith("run_concurrency:"):
        _, real_action = action.split(":", 1)
        ids = sess.extra.get("pending_ids") or []
        try:
            concurrency = int(text)
        except ValueError:
            concurrency = 200
        concurrency = max(1, min(2000, concurrency))
        sess.extra.pop("pending_ids", None)
        await start_bulk(chat_id, user_id, sess, real_action, ids, concurrency)
        return

    # ---------- SINGLE ----------
    if action == "single":
        sess.state = "idle"
        sess.action = None
        await do_single_check(chat_id, text)
        return

    if action == "createdate":
        sess.state = "idle"
        sess.action = None
        await do_createdate(chat_id, text)
        return

    if action == "bancheck":
        sess.state = "idle"
        sess.action = None
        await do_bancheck(chat_id, text)
        return

    if action == "brute_input":
        sess.extra["brute_target"] = text
        sess.state = "idle"
        await TG_API.send_message(
            chat_id,
            f"🎯 Target: `{md(text[:40])}{'...' if len(text) > 40 else ''}`\n\nChoose kick mode:",
            kb_brute_mode()
        )
        return

    # ---------- GENERATE ----------
    if action.startswith("gen_count:"):
        gt = action.split(":", 1)[1]
        raw = text.lower()
        try:
            if raw.endswith("k"):
                n = int(float(raw[:-1]) * 1000)
            elif raw.endswith("m"):
                n = int(float(raw[:-1]) * 1_000_000)
            else:
                n = int(raw)
        except ValueError:
            await TG_API.send_message(chat_id,
                "❌ Invalid number\\. Try `1000` or `10k`\\.", kb_back())
            return
        if n <= 0 or n > 5_000_000:
            await TG_API.send_message(chat_id,
                "❌ Range: 1 to 5,000,000\\.", kb_back())
            return
        sess.state = "idle"
        sess.action = None
        await do_generate(chat_id, sess, gt, n)
        return


# ==========================================
# Polling loop
# ==========================================
async def poll_loop():
    offset = 0
    print("✅ Bot polling started")
    while True:
        try:
            updates = await TG_API.get_updates(offset=offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    if "callback_query" in upd:
                        asyncio.create_task(handle_callback(upd["callback_query"]))
                    elif "message" in upd:
                        asyncio.create_task(handle_message(upd["message"]))
                except Exception:
                    traceback.print_exc()
        except asyncio.CancelledError:
            break
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(2)


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set TG_BOT_TOKEN env var.")
        return

    await TG_API.start()

    # Verify bot
    me = await TG_API._call("getMe")
    if not me.get("ok"):
        print(f"❌ Bot auth failed: {me.get('description')}")
        return
    print(f"✅ Logged in as @{me['result']['username']}")

    try:
        await poll_loop()
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    finally:
        await TG_API.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
