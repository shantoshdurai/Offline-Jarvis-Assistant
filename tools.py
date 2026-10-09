import time
import threading
import ctypes
import os
import sys
import subprocess
import webbrowser
import shutil
import urllib.parse
import urllib.request
import json
from datetime import datetime
import re
import ast
import difflib

FIREFOX_PATHS = [
    r"C:\Program Files\Mozilla Firefox\firefox.exe",
    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
]

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
]

def get_firefox_exe():
    for p in FIREFOX_PATHS:
        if os.path.exists(p):
            return p
    return None

def get_chrome_exe():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def _trigger_playback_after_delay():
    time.sleep(2.0)
    try:
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(ord('K'), 0, 0, 0)
        user32.keybd_event(ord('K'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(0xB3, 0, 0, 0)
        user32.keybd_event(0xB3, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass

def _schedule_autoplay_trigger():
    threading.Thread(target=_trigger_playback_after_delay, daemon=True).start()

def browser_control(action: str, tab_index: int = None, url: str = None) -> str:
    """Controls browser tabs, URL navigation, and media playback across Firefox, Chrome, and Edge."""
    action = (action or "").lower().strip()

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_TAB = 0x09
    VK_ESCAPE = 0x1B
    VK_F5 = 0x74

    def send_combo(*vks):
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    if action in ("play_pause", "play", "pause", "resume", "toggle_play"):
        user32.keybd_event(ord('K'), 0, 0, 0)
        user32.keybd_event(ord('K'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(0xB3, 0, 0, 0)
        user32.keybd_event(0xB3, 0, KEYEVENTF_KEYUP, 0)
        return "Playback started." if action in ("play", "resume") else "Playback toggled."

    elif action in ("next_tab", "switch_next_tab"):
        send_combo(VK_CONTROL, VK_TAB)
        return "Switched to next tab."

    elif action in ("previous_tab", "prev_tab", "switch_prev_tab"):
        send_combo(VK_CONTROL, VK_SHIFT, VK_TAB)
        return "Switched to previous tab."

    elif action in ("switch_tab", "go_to_tab"):
        idx = int(tab_index or 1)
        if idx < 1: idx = 1
        if idx > 9: idx = 9
        vk_num = 0x30 + idx
        send_combo(VK_CONTROL, vk_num)
        return f"Switched to tab {idx}."

    elif action in ("close_tab", "close_current_tab"):
        send_combo(VK_CONTROL, ord('W'))
        return "Closed active tab."

    elif action in ("reopen_tab", "undo_close_tab"):
        send_combo(VK_CONTROL, VK_SHIFT, ord('T'))
        return "Reopened closed tab."

    elif action in ("new_tab", "open_new_tab"):
        if url:
            open_url(url)
            return f"Opened {url} in new tab."
        send_combo(VK_CONTROL, ord('T'))
        return "Opened new tab."

    elif action in ("reload_tab", "refresh_tab", "refresh"):
        send_combo(VK_F5)
        return "Refreshed active tab."

    elif action in ("get_url", "read_url", "current_url"):
        send_combo(VK_CONTROL, ord('L'))
        time.sleep(0.08)
        send_combo(VK_CONTROL, ord('C'))
        time.sleep(0.08)
        send_combo(VK_ESCAPE)

        read_url = ""
        try:
            import win32clipboard, win32con
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                read_url = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception:
            pass

        if read_url and ("http://" in read_url or "https://" in read_url or "." in read_url):
            return f"Active tab URL is {read_url.strip()}."
        return "Could not read active tab URL."

    return f"Unknown browser action: '{action}'."

def play_video(query_or_target, browser=None):
    """Search for the top video on YouTube and immediately open and play it directly."""
    cleaned_query = query_or_target.strip().strip("'\"")
    for prefix in ["play ", "watch ", "listen to "]:
        if cleaned_query.lower().startswith(prefix):
            cleaned_query = cleaned_query[len(prefix):].strip()

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(cleaned_query)}"
    target_url = search_url
    try:
        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        vids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
        if vids:
            target_url = f"https://www.youtube.com/watch?v={vids[0]}&autoplay=1"
    except Exception:
        pass

    browser_lower = (browser or "").lower()
    if "firefox" in browser_lower:
        ff = get_firefox_exe()
        if ff:
            subprocess.Popen([ff, target_url])
            _schedule_autoplay_trigger()
            return f"Playing '{cleaned_query}' on YouTube in Firefox."
    elif "chrome" in browser_lower:
        ch = get_chrome_exe()
        if ch:
            subprocess.Popen([ch, target_url])
            _schedule_autoplay_trigger()
            return f"Playing '{cleaned_query}' on YouTube in Chrome."

    webbrowser.open(target_url)
    _schedule_autoplay_trigger()
    return f"Playing '{cleaned_query}' on YouTube."


def get_friendly_site_name(url: str, raw_target: str) -> str:
    """Extracts a clean, voice-friendly description of what was opened."""
    url_lower = url.lower()
    if "chatgpt.com" in url_lower:
        return "ChatGPT"
    elif "youtube.com" in url_lower:
        return "YouTube"
    elif "github.com" in url_lower:
        return "GitHub"
    elif "leetcode.com" in url_lower:
        return "LeetCode"
    elif "google.com/search?q=" in url_lower:
        q = urllib.parse.unquote(url.split("search_query=")[-1] if "search_query=" in url else url.split("q=")[-1])
        q = q.replace("+", " ").strip()
        return f"search for '{q}'"
    elif "reddit.com" in url_lower:
        return "Reddit"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "X"
    elif "wikipedia.org" in url_lower:
        return "Wikipedia"
    else:
        raw_clean = raw_target.replace("http://", "").replace("https://", "").replace("www.", "").strip("/")
        return raw_clean or "the webpage"

def open_url(url_or_target, browser=None):
    """Opens a website or URL in Firefox, Chrome, or default browser."""
    url = url_or_target.strip().strip("'\"")
    if "youtube.com/results?search_query=" in url:
        q = urllib.parse.unquote(url.split("search_query=")[-1])
        return play_video(q, browser=browser)
    elif url.lower().startswith("play "):
        return play_video(url[5:], browser=browser)
    elif url.lower() == "youtube":
        url = "https://www.youtube.com"
    elif url.lower() == "leetcode":
        url = "https://leetcode.com/problemset/"
    elif url.lower() == "github":
        url = "https://github.com"
    elif not url.startswith("http://") and not url.startswith("https://"):
        if "." in url and " " not in url:
            url = f"https://{url}"
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(url)}"

    friendly_name = get_friendly_site_name(url, url_or_target)
    browser_lower = (browser or "").lower()
    if "firefox" in browser_lower:
        ff = get_firefox_exe()
        if ff:
            subprocess.Popen([ff, url])
            return f"Opened {friendly_name} in Firefox."
    elif "chrome" in browser_lower:
        ch = get_chrome_exe()
        if ch:
            subprocess.Popen([ch, url])
            return f"Opened {friendly_name} in Chrome."

    webbrowser.open(url)
    return f"Opened {friendly_name}."

def get_leetcode_daily():
    """Queries LeetCode public GraphQL API for today's active coding challenge."""
    url = "https://leetcode.com/graphql"
    query = """
    query questionOfToday {
        activeDailyCodingChallengeQuestion {
            date
            link
            question {
                questionFrontendId
                title
                titleSlug
            }
        }
    }
    """
    body = json.dumps({"query": query}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            daily = data.get("data", {}).get("activeDailyCodingChallengeQuestion", {})
            q = daily.get("question", {})
            title = q.get("title")
            slug = q.get("titleSlug")
            return title, slug
    except Exception:
        return None, None

def check_leetcode_problem(slug):
    """Verifies whether a problem slug exists on LeetCode via GraphQL."""
    if not slug:
        return None
    url = "https://leetcode.com/graphql"
    query = """
    query questionTitle($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            questionFrontendId
            title
            titleSlug
        }
    }
    """
    body = json.dumps({
        "query": query,
        "variables": {"titleSlug": slug}
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            return data.get("data", {}).get("question")
    except Exception:
        return None

def open_leetcode(problem_query="", browser=None):
    """
    Intelligently opens a LeetCode problem, today's daily challenge,
    or falls back frankly to problem search if the exact link is uncertain.
    Returns (action_msg, speech_response).
    """
    t = (problem_query or "").strip().strip("'\"").lower()

    # 1. Daily Challenge Request
    if any(w in t for w in ["today", "daily", "challenge of today", "today's"]):
        title, slug = get_leetcode_daily()
        if slug and title:
            url = f"https://leetcode.com/problems/{slug}/"
            open_url(url, browser=browser)
            action = f"Opened today's LeetCode daily challenge: '{title}' ({url})"
            speech = f"I fetched today's LeetCode daily challenge for you: {title}. Opening it now in your browser."
            return action, speech
        else:
            url = "https://leetcode.com/problemset/"
            open_url(url, browser=browser)
            action = f"Opened LeetCode problem set ({url})"
            speech = "I opened the LeetCode problem set for you. I couldn't reach the daily challenge server right now, but today's problem is pinned at the top."
            return action, speech

    # Clean query of filler words
    clean = re.sub(r'^(hey\s+jarvis\s*,?\s*|jarvis\s*,?\s*)', '', t)
    clean = re.sub(r'^(can\s+you\s+)?(open|show|go\s+to|launch|give\s+me)\s+(leetcode\s+)?(problem\s+|question\s+)?', '', clean).strip()
    clean = re.sub(r'\b(on\s+leetcode|in\s+leetcode|from\s+leetcode|leetcode)\b', '', clean).strip()
    clean = re.sub(r'\b(in\s+my\s+browser|in\s+browser|in\s+firefox|in\s+chrome|please|for\s+me|website|solution)\b', '', clean).strip()
    clean = re.sub(r'^(for|about|with|the)\s+', '', clean).strip()
    clean = clean.strip('\'".,?! ')

    # 2. General / Empty -> open Problemset homepage
    if not clean or clean in ["all", "list", "set", "problemset", "problems", "home", "homepage"]:
        url = "https://leetcode.com/problemset/"
        open_url(url, browser=browser)
        action = f"Opened LeetCode problem set ({url})"
        speech = "Opening the LeetCode problem set homepage in your browser."
        return action, speech

    # 3. Form candidate slug
    candidate_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', clean).strip().replace(" ", "-").replace("_", "-")
    candidate_slug = re.sub(r'-+', '-', candidate_slug).lower()
    if "-" in candidate_slug and candidate_slug.split("-")[0].isdigit():
        candidate_slug = "-".join(candidate_slug.split("-")[1:])

    prob_info = check_leetcode_problem(candidate_slug) if candidate_slug else None
    if prob_info and prob_info.get("titleSlug"):
        title = prob_info.get("title")
        slug = prob_info.get("titleSlug")
        num = prob_info.get("questionFrontendId", "")
        url = f"https://leetcode.com/problems/{slug}/"
        open_url(url, browser=browser)
        action = f"Opened LeetCode problem '{title}' (#{num}) ({url})"
        speech = f"Opening LeetCode problem {title} in your browser."
        return action, speech
    else:
        # Frank fallback: do not guess a link that might 404! Open search and tell user frankly.
        search_url = f"https://leetcode.com/problemset/?search={urllib.parse.quote(clean)}"
        open_url(search_url, browser=browser)
        action = f"Opened LeetCode search for '{clean}' ({search_url})"
        speech = f"I opened the LeetCode search for {clean}. To be frank, I wasn't completely sure of the direct link, so I opened the search results so you can select the exact problem."
        return action, speech

_APPS_CACHE = None
_APPS_CACHE_TIME = 0.0

def get_installed_apps_catalog(force_refresh=False):
    """Discovers and caches installed applications across Windows Desktop and Start Menu."""
    global _APPS_CACHE, _APPS_CACHE_TIME
    import time
    if not force_refresh and _APPS_CACHE is not None and (time.time() - _APPS_CACHE_TIME < 120):
        return _APPS_CACHE

    search_dirs = [
        os.path.join(os.path.expanduser('~'), 'Desktop'),
        os.path.join(os.environ.get('PUBLIC', r'C:\Users\Public'), 'Desktop'),
        os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'), r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs'),
    ]

    apps = {}
    ignored_keywords = ('uninstall', 'remove', 'help', 'readme', 'documentation', 'install', 'update', 'settings')
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(('.lnk', '.exe', '.url')):
                        stem = os.path.splitext(f)[0]
                        stem_lower = stem.lower()
                        if any(bad in stem_lower for bad in ignored_keywords):
                            continue
                        norm_stem = re.sub(r'[^a-zA-Z0-9]', '', stem_lower)
                        if norm_stem and norm_stem not in apps:
                            apps[norm_stem] = {
                                "stem": stem,
                                "path": os.path.join(root, f),
                                "filename": f
                            }
        except Exception:
            continue

    _APPS_CACHE = apps
    _APPS_CACHE_TIME = time.time()
    return apps

def list_installed_apps(filter_query=""):
    """
    Returns a clean summary of installed software and applications on the PC.
    If filter_query is provided, filters applications matching the query.
    """
    catalog = get_installed_apps_catalog()
    q = (filter_query or "").strip().lower()

    items = list(catalog.values())
    if q:
        filtered = [it for it in items if q in it["stem"].lower()]
    else:
        # Filter down to prominent user applications (exclude small CLI helper scripts)
        filtered = [it for it in items if not it["stem"].lower().startswith(('activate-', 'accelerate-', 'cli-'))]

    names = sorted(list({it["stem"] for it in filtered}))
    if not names:
        return f"No installed applications found matching '{filter_query}'."

    sample = names[:15]
    res = f"Found {len(names)} installed applications on your PC: " + ", ".join(sample)
    if len(names) > 15:
        res += f", and {len(names) - 15} more."
    return res

def find_app_shortcut(app_name):
    """
    Dynamically discovers application shortcuts (.lnk, .url) and executables (.exe)
    across Windows Desktop, Start Menu, and AppData directories.
    Returns (path, display_name) or (None, None).
    """
    clean_query = (app_name or "").strip().lower()
    clean_query = re.sub(r'^(the|open|launch|run|start)\s+', '', clean_query)
    clean_query = re.sub(r'\s+(app|application|software|program|ide)$', '', clean_query).strip()
    norm_query = re.sub(r'[^a-zA-Z0-9]', '', clean_query)
    if not norm_query:
        return None, None

    catalog = get_installed_apps_catalog()

    # 1. Exact normalized match (e.g. 'antigravity' == 'antigravity')
    if norm_query in catalog:
        entry = catalog[norm_query]
        return entry["path"], entry["stem"]

    # 2. Query is prefix match (e.g. 'blender' matches 'blender52')
    for norm_stem, entry in catalog.items():
        if norm_stem.startswith(norm_query):
            return entry["path"], entry["stem"]

    return None, None

def open_app(app_name):
    """Opens local applications dynamically, asking clarification if misheard or ambiguous."""
    raw_name = (app_name or "").strip().strip("'\"")
    name = raw_name.lower()
    if not name:
        return "Please specify an application to open."

    # Built-in handlers for shell components and browsers
    if "firefox" in name:
        ff = get_firefox_exe()
        if ff:
            subprocess.Popen([ff])
            return "Launched Mozilla Firefox."
        subprocess.Popen(["start", "firefox"], shell=True)
        return "Launched Firefox."
    elif "chrome" in name:
        ch = get_chrome_exe()
        if ch:
            subprocess.Popen([ch])
            return "Launched Google Chrome."
        subprocess.Popen(["start", "chrome"], shell=True)
        return "Launched Chrome."
    elif "code" in name or "vscode" in name:
        target, title = find_app_shortcut("code")
        if target:
            try:
                os.startfile(target)
                return "Launched Visual Studio Code."
            except Exception:
                pass
        subprocess.Popen(["code"], shell=True)
        return "Launched Visual Studio Code."
    elif "notepad" in name:
        subprocess.Popen(["notepad.exe"])
        return "Launched Notepad."
    elif "terminal" in name or "powershell" in name:
        subprocess.Popen(["powershell.exe"])
        return "Launched PowerShell Terminal."
    elif "cmd" in name or "command prompt" in name:
        subprocess.Popen(["cmd.exe"])
        return "Launched Command Prompt."
    elif "calc" in name or "calculator" in name:
        subprocess.Popen(["calc.exe"])
        return "Launched Calculator."
    elif "explorer" in name or "files" in name or "folder" in name:
        subprocess.Popen(["explorer.exe"])
        return "Opened File Explorer."

    # Dynamic application shortcut & executable discovery
    target_path, display_title = find_app_shortcut(name)
    if target_path:
        try:
            os.startfile(target_path)
            return f"Launched {display_title}."
        except Exception as e:
            return f"Found {display_title} but could not launch it: {e}"

    # Check system PATH executable via shutil.which
    which_path = shutil.which(name) or shutil.which(f"{name}.exe")
    if which_path:
        try:
            subprocess.Popen([which_path])
            return f"Launched {os.path.splitext(os.path.basename(which_path))[0]}."
        except Exception as e:
            return f"Found {name} on PATH but failed to launch: {e}"

    # Ambiguity & Mishearing Detection: check installed applications catalog
    catalog = get_installed_apps_catalog()
    all_stems = [entry["stem"] for entry in catalog.values()]

    # Check substring matches (e.g. "studio" -> OBS Studio, Visual Studio Code, Android Studio)
    raw_sub = [s for s in all_stems if name in s.lower()]
    # Normalize variants (e.g. Antigravity and Antigravity IDE -> Antigravity)
    unique_sub = sorted(list({re.sub(r'\s+ide$', '', s, flags=re.IGNORECASE) for s in raw_sub}))

    if len(unique_sub) > 1 and len(unique_sub) <= 5:
        return f"I found multiple apps matching '{raw_name}': {', '.join(unique_sub[:3])}. Which one would you like to open?"
    elif len(unique_sub) == 1:
        return f"I couldn't find '{raw_name}'. Did you mean {unique_sub[0]}?"

    # Fuzzy match for misheard or typoed names (e.g. "claud", "diskord")
    close_matches = difflib.get_close_matches(raw_name, all_stems, n=3, cutoff=0.5)
    if not close_matches:
        close_matches = difflib.get_close_matches(name, [s.lower() for s in all_stems], n=3, cutoff=0.5)
        if close_matches:
            lower_to_stem = {s.lower(): s for s in all_stems}
            close_matches = [lower_to_stem.get(c, c) for c in close_matches]

    if close_matches:
        best = close_matches[0]
        return f"I couldn't find '{raw_name}'. Did you mean {best}?"

    return f"I couldn't find an installed application matching '{raw_name}'. You can ask me to list your installed applications."

def close_app(app_name):
    """Closes or terminates a running application, browser, or active window."""
    name = (app_name or "").strip().strip("'\"").lower()
    if not name:
        return "Please specify the application to close."

    targets = []
    display_name = app_name

    if "chrome" in name:
        targets = ["chrome.exe"]
        display_name = "Google Chrome"
    elif "firefox" in name:
        targets = ["firefox.exe"]
        display_name = "Mozilla Firefox"
    elif "edge" in name:
        targets = ["msedge.exe"]
        display_name = "Microsoft Edge"
    elif "code" in name or "vscode" in name:
        targets = ["Code.exe"]
        display_name = "Visual Studio Code"
    elif "notepad" in name:
        targets = ["notepad.exe"]
        display_name = "Notepad"
    elif "calc" in name or "calculator" in name:
        targets = ["CalculatorApp.exe", "calc.exe"]
        display_name = "Calculator"
    elif "spotify" in name:
        targets = ["Spotify.exe"]
        display_name = "Spotify"
    elif "blender" in name:
        targets = ["blender.exe"]
        display_name = "Blender"
    elif "terminal" in name or "powershell" in name:
        targets = ["WindowsTerminal.exe", "powershell.exe"]
        display_name = "Terminal"
    elif "cmd" in name or "command prompt" in name:
        targets = ["cmd.exe"]
        display_name = "Command Prompt"
    elif any(k in name for k in ("current", "active", "this window", "the window", "that window")):
        import ctypes
        VK_MENU = 0x12  # Alt
        VK_F4 = 0x73    # F4
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 2, 0)
        return "Closed the active window."
    else:
        proc = name if name.endswith(".exe") else f"{name}.exe"
        targets = [proc]
        display_name = app_name

    closed_any = False
    for exe in targets:
        try:
            res = subprocess.run(["taskkill", "/F", "/IM", exe, "/T"], capture_output=True, text=True)
            if res.returncode == 0:
                closed_any = True
        except Exception:
            pass

    if closed_any:
        return f"Closed {display_name}."
    return f"{display_name} was closed or not running."

def take_screenshot(filename=None):
    """Takes a desktop screenshot and saves it."""
    pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
    if not os.path.exists(pictures_dir):
        pictures_dir = "."
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(pictures_dir, f"screenshot_{timestamp}.png")
    else:
        filename = filename.strip().strip("'\"")
        if not os.path.isabs(filename):
            filename = os.path.join(pictures_dir, filename)

    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(filename)
        return f"Screenshot saved successfully to {filename}"
    except Exception:
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=filename)
            return f"Screenshot saved successfully to {filename}"
        except Exception as e2:
            return f"Failed to take screenshot: {e2}"

def inspect_screen():
    """
    Offline Vision: Captures the desktop and extracts on-screen text/code
    using Windows 10/11 native hardware-accelerated OCR.
    """
    try:
        from PIL import ImageGrab
        import io, asyncio
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
        
        async def do_ocr():
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(data)
            await writer.store_async()
            await writer.flush_async()
            stream.seek(0)
            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            engine = OcrEngine.try_create_from_user_profile_languages()
            res = await engine.recognize_async(software_bitmap)
            return "\n".join([line.text for line in res.lines if line.text.strip()])
            
        text = asyncio.run(do_ocr())
        return text.strip() if text.strip() else "(Screen appears to be blank or contains no readable text)"
    except Exception as e:
        return f"(Screen OCR error: {e})"

def adjust_brightness(action="increase", value=None):
    """Controls laptop screen brightness (increase, decrease, set)."""
    try:
        import screen_brightness_control as sbc
        curr = sbc.get_brightness()
        curr_val = curr[0] if isinstance(curr, list) and curr else 50
        
        if action == "set" and value is not None:
            new_val = max(0, min(100, int(value)))
            sbc.set_brightness(new_val)
            return f"Brightness set to {new_val}%."
        elif "inc" in action or "up" in action or "more" in action or "+" in action:
            new_val = min(100, curr_val + (int(value) if value else 15))
            sbc.set_brightness(new_val)
            return f"Brightness increased to {new_val}%."
        elif "dec" in action or "down" in action or "less" in action or "-" in action:
            new_val = max(0, curr_val - (int(value) if value else 15))
            sbc.set_brightness(new_val)
            return f"Brightness decreased to {new_val}%."
        else:
            return f"Current brightness is {curr_val}%."
    except Exception as e:
        return f"Failed to adjust brightness: {e}"

def adjust_volume(action="increase"):
    """Controls Windows master volume using native user32 keystrokes."""
    import ctypes
    if "up" in action or "inc" in action or "more" in action:
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
        return "Volume increased."
    elif "down" in action or "dec" in action or "less" in action:
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
        return "Volume decreased."
    elif "mute" in action or "unmute" in action:
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        return "Volume mute toggled."
    return "Volume command executed."

def get_installed_games():
    """Finds all games installed on this computer (Steam, Epic, Desktop shortcuts, Registry)."""
    games = set()
    # 1. Steam Common folder
    steam_dirs = [
        r"C:\Program Files (x86)\Steam\steamapps\common",
        r"C:\Program Files\Steam\steamapps\common",
        r"D:\SteamLibrary\steamapps\common",
        r"E:\SteamLibrary\steamapps\common",
    ]
    for s_dir in steam_dirs:
        if os.path.exists(s_dir):
            for f in os.listdir(s_dir):
                if os.path.isdir(os.path.join(s_dir, f)) and f.lower() not in ["steamworks shared", "steam controller configs"]:
                    games.add(f)

    # 2. Desktop shortcuts
    for d in [os.path.expanduser("~/Desktop"), r"C:\Users\Public\Desktop"]:
        if os.path.exists(d):
            for f in os.listdir(d):
                name_clean = f.replace(".lnk", "").replace(".url", "").strip()
                if any(k in name_clean.lower() for k in [
                    "roblox", "counter-strike", "cs", "forza", "gta", "valorant", "minecraft",
                    "steam", "game", "epic", "riot", "rdr", "red dead", "battlefield", "pubg",
                    "delta force", "goose", "arc raiders", "efootball", "yu-gi-oh", "beyond-all-reason"
                ]):
                    if not name_clean.lower().startswith("steam") and "controller" not in name_clean.lower():
                        games.add(name_clean)

    # 3. Windows Registry
    try:
        import winreg
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root, sub in keys:
            try:
                with winreg.OpenKey(root, sub) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            subname = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, subname) as appkey:
                                name, _ = winreg.QueryValueEx(appkey, "DisplayName")
                                if any(g in name.lower() for g in [
                                    "counter-strike", "forza", "roblox", "battlefield", "pubg",
                                    "red dead", "delta force", "beyond-all-reason", "minecraft",
                                    "untitled goose", "arc raiders", "efootball", "yu-gi-oh"
                                ]):
                                    clean = re.sub(r'\s*[\(\[].*?[\)\]]', '', name).strip()
                                    games.add(clean)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

    game_list = sorted(list(games))
    if not game_list:
        return ["Counter-Strike 2", "Roblox", "Forza Horizon 6"]
    return game_list

def open_folder(folder_path=""):
    """Opens a folder in Windows File Explorer."""
    path_str = (folder_path or "").strip().strip("'\"").lower()
    user_home = os.path.expanduser("~")
    
    if "download" in path_str:
        p = os.path.join(user_home, "Downloads")
    elif "picture" in path_str:
        p = os.path.join(user_home, "Pictures")
    elif "document" in path_str:
        p = os.path.join(user_home, "Documents")
    elif "desktop" in path_str:
        p = os.path.join(user_home, "Desktop")
    elif folder_path and folder_path.strip():
        p = os.path.expanduser(folder_path.strip().strip("'\""))
    else:
        p = user_home

    if not os.path.exists(p):
        return f"Folder does not exist: {p}"
    subprocess.Popen(["explorer.exe", os.path.normpath(p)])
    return f"Opened folder: {p}"

def move_item(source_path, dest_path):
    """Moves a file or folder from source to destination."""
    src = os.path.expanduser(source_path.strip().strip("'\""))
    dst = os.path.expanduser(dest_path.strip().strip("'\""))
    if not os.path.exists(src):
        return f"Source path does not exist: {src}"
    try:
        shutil.move(src, dst)
        return f"Moved successfully from {src} to {dst}"
    except Exception as e:
        return f"Failed to move item: {e}"

def resolve_folder_path(folder_name=""):
    """Resolves friendly folder names like 'downloads', 'desktop' or absolute paths."""
    raw = (folder_name or "").strip().strip("'\"").lower()
    user_home = os.path.expanduser("~")
    if "download" in raw or not raw:
        return os.path.join(user_home, "Downloads"), "Downloads"
    elif "desktop" in raw:
        return os.path.join(user_home, "Desktop"), "Desktop"
    elif "document" in raw:
        return os.path.join(user_home, "Documents"), "Documents"
    elif "picture" in raw or "photo" in raw:
        return os.path.join(user_home, "Pictures"), "Pictures"
    elif "music" in raw:
        return os.path.join(user_home, "Music"), "Music"
    elif "video" in raw:
        return os.path.join(user_home, "Videos"), "Videos"
    elif "project" in raw or "code" in raw or "repo" in raw:
        return os.getcwd(), "Current Project"
    elif folder_name and os.path.exists(os.path.expanduser(folder_name.strip("'\""))):
        p = os.path.expanduser(folder_name.strip("'\""))
        return p, os.path.basename(p) or p
    else:
        return os.path.join(user_home, "Downloads"), "Downloads"

def create_folder(folder_path=""):
    """Creates a new folder or directory."""
    raw = (folder_path or "").strip().strip("'\"")
    if not raw:
        return "Please specify a folder name or path to create."
    p = os.path.expanduser(raw)
    if not os.path.isabs(p):
        p = os.path.join(os.path.expanduser("~"), "Downloads", raw)
    try:
        os.makedirs(p, exist_ok=True)
        return f"Created folder '{os.path.basename(p)}' at {p}."
    except Exception as e:
        return f"Failed to create folder: {e}"

def organize_folder(folder_name="downloads"):
    """Automatically sorts and arranges loose files in a folder into categorized subfolders."""
    target_dir, display_name = resolve_folder_path(folder_name)
    if not os.path.exists(target_dir):
        return f"Directory does not exist: {target_dir}"

    categories = {
        "Images": {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff', '.raw'},
        "Videos": {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'},
        "Audio": {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus'},
        "Documents": {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.csv', '.rtf', '.epub', '.md'},
        "Archives": {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso', '.torrent'},
        "Installers": {'.exe', '.msi', '.dmg', '.apk', '.bat', '.cmd'},
        "3D & Creative": {'.blend', '.fbx', '.obj', '.stl', '.dae', '.psd', '.ai', '.kra', '.blend1'},
        "Code": {'.py', '.json', '.xml', '.yaml', '.yml', '.html', '.css', '.js', '.ts', '.cpp', '.c', '.h', '.java', '.sql', '.rs', '.go'},
    }

    ext_to_cat = {}
    for cat, exts in categories.items():
        for ext in exts:
            ext_to_cat[ext.lower()] = cat

    try:
        loose_files = []
        for item in os.listdir(target_dir):
            if item.startswith(".") or item.startswith("$") or item.lower() in ("desktop.ini", "thumbs.db"):
                continue
            full_item_path = os.path.join(target_dir, item)
            if os.path.isfile(full_item_path):
                loose_files.append(item)
    except Exception as e:
        return f"Error reading folder {target_dir}: {e}"

    if not loose_files:
        return f"No loose files found to organize in {display_name}. Everything is already organized into folders."

    moved_counts = {}
    for filename in loose_files:
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        cat = ext_to_cat.get(ext_lower, "Other")

        cat_dir = os.path.join(target_dir, cat)
        try:
            os.makedirs(cat_dir, exist_ok=True)
            src_path = os.path.join(target_dir, filename)
            dest_path = os.path.join(cat_dir, filename)

            if os.path.exists(dest_path):
                base_name, file_ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(cat_dir, f"{base_name}_{counter}{file_ext}")):
                    counter += 1
                dest_path = os.path.join(cat_dir, f"{base_name}_{counter}{file_ext}")

            shutil.move(src_path, dest_path)
            moved_counts[cat] = moved_counts.get(cat, 0) + 1
        except Exception as e:
            print(f"[Warning] Failed moving {filename}: {e}")

    total_moved = sum(moved_counts.values())
    if total_moved == 0:
        return f"No files were moved in {display_name}."

    breakdown = ", ".join([f"{cnt} {cat}" for cat, cnt in sorted(moved_counts.items(), key=lambda x: -x[1])])
    return f"Organized {total_moved} files in {display_name} into folders: {breakdown}."

def execute_command(command):
    """Runs a shell CLI command and returns output."""
    cmd = command.strip().strip("'\"")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
        out = (res.stdout + "\n" + res.stderr).strip()
        return out if out else "(Command executed successfully with no output)"
    except Exception as e:
        return f"Error executing command: {e}"

def list_folder_contents(folder_name="", max_items=15):
    """Lists files and folders inside common directories or a specified directory."""
    raw = (folder_name or "").strip().strip("'\"").lower()
    user_home = os.path.expanduser("~")
    
    if "download" in raw:
        target_dir = os.path.join(user_home, "Downloads")
        display_name = "Downloads"
    elif "desktop" in raw:
        target_dir = os.path.join(user_home, "Desktop")
        display_name = "Desktop"
    elif "document" in raw:
        target_dir = os.path.join(user_home, "Documents")
        display_name = "Documents"
    elif "picture" in raw or "photo" in raw:
        target_dir = os.path.join(user_home, "Pictures")
        display_name = "Pictures"
    elif "project" in raw or "code" in raw or "repo" in raw:
        target_dir = os.getcwd()
        display_name = "Current Project"
    elif folder_name and os.path.exists(os.path.expanduser(folder_name.strip("'\""))):
        target_dir = os.path.expanduser(folder_name.strip("'\""))
        display_name = target_dir
    else:
        target_dir = os.path.join(user_home, "Downloads")
        display_name = "Downloads"

    if not os.path.exists(target_dir):
        return f"Directory does not exist: {target_dir}"

    try:
        entries = []
        for item in os.listdir(target_dir):
            if item.startswith(".") or item.startswith("$"):
                continue
            full_path = os.path.join(target_dir, item)
            is_dir = os.path.isdir(full_path)
            try:
                mtime = os.path.getmtime(full_path)
                size_mb = os.path.getsize(full_path) / (1024 * 1024) if not is_dir else 0
                entries.append((item, is_dir, mtime, size_mb))
            except Exception:
                entries.append((item, is_dir, 0, 0))

        # Sort by modification time descending (most recent first)
        entries.sort(key=lambda x: x[2], reverse=True)
        
        lines = [f"Contents of {display_name} ({len(entries)} items total):"]
        for name, is_dir, mtime, size_mb in entries[:max_items]:
            kind = "[DIR] " if is_dir else "      "
            size_str = f"({size_mb:.1f} MB)" if not is_dir and size_mb >= 0.1 else ""
            lines.append(f"  {kind}{name} {size_str}".rstrip())
            
        if len(entries) > max_items:
            lines.append(f"  ... and {len(entries) - max_items} more items")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading folder {target_dir}: {e}"

def search_local_files(query, directory=None):
    """Searches for files matching query in local user and project directories."""
    q = query.strip().strip("'\"").lower()
    user_home = os.path.expanduser("~")
    
    if directory:
        search_dirs = [os.path.expanduser(directory.strip().strip("'\""))]
    else:
        # Check high-value user directories first for near-instant results
        search_dirs = [
            os.getcwd(),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Pictures")
        ]

    matches = []
    for base in search_dirs:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "AppData", "__pycache__", "venv", ".cache"]]
            for f in files:
                if q in f.lower():
                    matches.append(os.path.join(root, f))
                    if len(matches) >= 10:
                        break
            if len(matches) >= 10:
                break
        if len(matches) >= 10:
            break

    if not matches:
        return f"No files matching '{query}' found in common directories."
    return "\n".join(matches)

def read_file_content(file_path):
    """Reads the contents of a local file."""
    p = os.path.expanduser(file_path.strip().strip("'\""))
    if not os.path.exists(p):
        cwd_p = os.path.join(os.getcwd(), p)
        if os.path.exists(cwd_p):
            p = cwd_p
        else:
            matches = search_local_files(os.path.basename(p))
            first_match = matches.split("\n")[0] if matches and not matches.startswith("No files") else None
            if first_match and os.path.exists(first_match):
                p = first_match
            else:
                return f"File does not exist: {file_path}"
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            preview = "".join(lines[:100])
            if len(lines) > 100:
                preview += f"\n...(truncated, {len(lines)} total lines)"
            return preview
    except Exception as e:
        return f"Error reading file: {e}"

AVAILABLE_TOOLS = {
    "open_url": open_url,
    "play_video": play_video,
    "play_youtube": play_video,
    "open_leetcode": open_leetcode,
    "open_app": open_app,
    "close_app": close_app,
    "take_screenshot": take_screenshot,
    "inspect_screen": inspect_screen,
    "see_screen": inspect_screen,
    "read_screen": inspect_screen,
    "adjust_brightness": adjust_brightness,
    "adjust_volume": adjust_volume,
    "get_installed_games": get_installed_games,
    "open_folder": open_folder,
    "create_folder": create_folder,
    "organize_folder": organize_folder,
    "list_folder": list_folder_contents,
    "list_folder_contents": list_folder_contents,
    "search_files": search_local_files,
    "search_local_files": search_local_files,
    "read_file": read_file_content,
    "read_file_content": read_file_content,
    "move_item": move_item,
    "run_command": execute_command,
    "browser_control": browser_control
}

def parse_and_execute_tool(text):
    """
    Looks for <<TOOL: name(...)>> in the text, executes it,
    and returns (tool_found, execution_message, cleaned_text).
    """
    pattern = r'<<TOOL:\s*([a-zA-Z0-9_]+)\((.*?)\)\s*>>'
    matches = list(re.finditer(pattern, text))
    if not matches:
        return False, None, text

    messages = []
    for match in matches:
        func_name = match.group(1).strip()
        raw_args = match.group(2).strip()

        if func_name in AVAILABLE_TOOLS:
            func = AVAILABLE_TOOLS[func_name]
            try:
                parsed_call = ast.parse(f"func({raw_args})").body[0].value
                args = [ast.literal_eval(a) for a in parsed_call.args]
                kwargs = {k.arg: ast.literal_eval(k.value) for k in parsed_call.keywords}
                res = func(*args, **kwargs)
                if isinstance(res, tuple):
                    res = res[0]
                elif isinstance(res, list):
                    res = ", ".join(res)
                messages.append(f"[Action: {res}]")
            except Exception:
                try:
                    arg_clean = raw_args.strip("'\"")
                    res = func(arg_clean) if arg_clean else func()
                    if isinstance(res, tuple):
                        res = res[0]
                    elif isinstance(res, list):
                        res = ", ".join(res)
                    messages.append(f"[Action: {res}]")
                except Exception as e:
                    messages.append(f"[Tool Error ({func_name}): {e}]")
        else:
            messages.append(f"[Tool Error: Unrecognized tool '{func_name}']")

    cleaned_text = re.sub(pattern, '', text).strip()
    return True, "\n".join(messages), cleaned_text

def detect_and_run_intent(text):
    """
    Directly inspects the user message for explicit tool and action requests
    (screen vision, games, brightness, volume, YouTube, LeetCode, software, screenshots, CLI, folders)
    and executes them immediately without relying solely on LLM tag generation.
    Returns (handled: bool, action_msg: str, response_speech: str, needs_llm_analysis: bool).
    """
    t = text.lower().strip()

    # Browser preference
    browser = None
    if "firefox" in t:
        browser = "firefox"
    elif "chrome" in t:
        browser = "chrome"

    # 1. Vision / Screen Reading Intent ("Look at my screen", "What's on my screen")
    if any(p in t for p in ["look at my screen", "what is on my screen", "what's on my screen", "can you see my screen", "read my screen", "inspect my screen", "see my screen", "look at screen", "read the screen", "check my screen"]):
        screen_text = inspect_screen()
        lines = [l for l in screen_text.split("\n") if l.strip()]
        preview = " | ".join(lines[:3]) if lines else "Empty"
        if len(preview) > 100: preview = preview[:97] + "..."
        action_msg = f"[Action: Screen analyzed via Windows OCR ({len(lines)} lines detected: {preview})]"
        speech = "I have captured and read your screen. Let me analyze it for you."
        return True, action_msg, speech, True # Send to LLM with screen content

    # 2. Installed Games Intent ("What are the games I have in my computer?", "list my games")
    if any(k in t for k in ["games", "game installed", "installed games", "games i have", "my games", "what games"]):
        games = get_installed_games()
        preview = ", ".join(games[:8]) + (f" and {len(games)-8} more" if len(games) > 8 else "")
        action_msg = f"[Action: Found {len(games)} games installed on this computer: {', '.join(games)}]"
        speech = f"You have several games installed on your laptop, including {preview}."
        return True, action_msg, speech, False

    # 3. Brightness Control ("Can you increase the brightness?", "Set brightness to 80")
    if "brightness" in t:
        action = "increase"
        val = None
        if any(w in t for w in ["increase", "up", "more", "raise", "high", "brighten"]):
            action = "increase"
        elif any(w in t for w in ["decrease", "down", "lower", "less", "dim", "reduce"]):
            action = "decrease"
        m = re.search(r'(\d+)', t)
        if m:
            action = "set"
            val = int(m.group(1))
        res = adjust_brightness(action, val)
        return True, f"[Action: {res}]", res, False

    # 4. Volume Control ("Increase the volume", "mute")
    if "volume" in t or "sound" in t:
        if any(w in t for w in ["increase", "up", "more", "raise", "loud", "louder"]):
            res = adjust_volume("increase")
            return True, f"[Action: {res}]", "Increased volume for you.", False
        elif any(w in t for w in ["decrease", "down", "lower", "less", "quiet", "softer"]):
            res = adjust_volume("decrease")
            return True, f"[Action: {res}]", "Decreased volume for you.", False
        elif "mute" in t:
            res = adjust_volume("mute")
            return True, f"[Action: {res}]", "Toggled volume mute for you.", False

    # 4b. Browser Tab & Playback Control ("play it", "it is not playing", "resume", "pause", "next tab", "previous tab", "close tab", "what is the url")
    if any(p in t for p in ["it is not playing", "it's not playing", "not playing", "play the song", "play it", "resume the video", "pause the video", "pause the song", "resume playback", "toggle play"]):
        res = browser_control("play_pause")
        return True, f"[Action: {res}]", res, False

    if any(p in t for p in ["next tab", "switch to next tab", "go to next tab"]):
        res = browser_control("next_tab")
        return True, f"[Action: {res}]", res, False

    if any(p in t for p in ["previous tab", "prev tab", "switch to previous tab", "go to previous tab"]):
        res = browser_control("previous_tab")
        return True, f"[Action: {res}]", res, False

    if any(p in t for p in ["close this tab", "close the tab", "close active tab", "close tab"]):
        res = browser_control("close_tab")
        return True, f"[Action: {res}]", res, False

    if any(p in t for p in ["reopen tab", "undo close tab", "reopen closed tab"]):
        res = browser_control("reopen_tab")
        return True, f"[Action: {res}]", res, False

    if any(p in t for p in ["what is the url", "what's the url", "get url", "current url", "copy url", "read url"]):
        res = browser_control("get_url")
        return True, f"[Action: {res}]", res, False

    # 5. YouTube Intent (clean extraction, direct playback vs search, frank fallback)
    is_play_music = t.startswith("play ") and any(w in t for w in ["music", "song", "theme", "track", "audio", "video", "ost", "lofi", "beats", "remix"])
    if ("youtube" in t and any(w in t for w in ["open", "play", "launch", "start", "show", "watch", "want", "search"])) or is_play_music:
        clean = re.sub(r'^(hey\s+jarvis\s*,?\s*|jarvis\s*,?\s*)', '', t)
        m = re.search(r'play\s+(.+?)(?:\s+on|\s+in)?\s+youtube', clean)
        if not m:
            m = re.search(r'(?:search\s+(?:on\s+)?youtube\s+for|youtube\s+search\s+(?:for\s+)?)(.+)', clean)
        if not m:
            m = re.search(r'open\s+youtube(?:\s+(?:and|to)\s+(?:search|play))?\s+(.+)', clean)
        if not m and is_play_music:
            m = re.search(r'play\s+(.+)', clean)

        query = m.group(1).strip() if m else ""
        query = re.sub(r'\b(in\s+my\s+browser|in\s+browser|in\s+firefox|in\s+chrome|please|for\s+me|tab|video|videos)\b', '', query).strip()
        query = re.sub(r'^(for|about|with|the)\s+', '', query).strip()
        query = query.strip('\'".,?! ')

        if query in ["", "homepage", "app", "site", "website"]:
            res = open_url("https://www.youtube.com", browser=browser)
            speech = "Opening YouTube in Firefox for you." if browser == "firefox" else "Opening YouTube for you."
            return True, f"[Action: {res}]", speech, False
        elif query in ["something", "a video", "any video", "videos"]:
            res = open_url("https://www.youtube.com", browser=browser)
            speech = "I opened YouTube for you. To be frank, I wasn't sure what specific video or search you wanted, so I opened the homepage for you."
            return True, f"[Action: {res}]", speech, False
        else:
            if any(w in t for w in ["play", "watch", "listen", "song", "music", "theme", "track", "lofi"]):
                res = play_video(query, browser=browser)
                speech = f"Playing {query} on YouTube."
                return True, f"[Action: {res}]", speech, False
            else:
                target = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                res = open_url(target, browser=browser)
                speech = f"Searching YouTube for {query}."
                return True, f"[Action: Opened YouTube search for '{query}' ({target})]", speech, False

    # 6. LeetCode Intent (smart GraphQL daily resolver, slug verification, frank fallback)
    if "leetcode" in t and any(w in t for w in ["open", "show", "go to", "solve", "want", "do", "find", "challenge"]):
        action, speech = open_leetcode(t, browser=browser)
        return True, f"[Action: {action}]", speech, False

    # 7. System Files Permission / Access Confirmation
    if any(p in t for p in [
        "access to system files", "access to files", "access system files", "access my files",
        "can you access my files", "can you see my files", "why no access to system files",
        "why this model has no access to system files", "do you have access to local files",
        "do you have access to system files", "have access to files"
    ]):
        speech = "I do have direct access to your local system files, directories, and documents. I can search for files, read code, list folders like Downloads or Desktop, and execute terminal commands for you."
        action = "[Action: Confirmed full local file system access (search_files, read_file, list_folder_contents, open_folder, move_item, run_command)]"
        return True, action, speech, False

    # 8. List Folder Contents ("what files are in downloads", "list files in desktop")
    if any(w in t for w in ["what files", "list files", "show files", "what's in", "whats in", "what do i have in"]) and any(f in t for f in ["download", "desktop", "document", "picture", "folder", "project"]):
        m = re.search(r'(?:in|of)\s+([a-zA-Z0-9_\-\\/\s]+)', t)
        target = m.group(1).strip() if m else "downloads"
        res = list_folder_contents(target, max_items=12)
        preview_speech = f"Here are the files in your {target.strip().capitalize()} folder. I have displayed them on your screen."
        return True, f"[Action: Listed folder contents]\n{res}", preview_speech, False

    # 8b. Folder Organization Intent ("organize downloads", "arrange files in download folder", "sort files into folders")
    if any(w in t for w in ["organize", "arrange files", "sort files", "arrange them", "clean up downloads", "clean up folder"]) and any(f in t for f in ["download", "desktop", "document", "picture", "file", "folder", "them"]):
        target = "downloads"
        if "desktop" in t:
            target = "desktop"
        elif "document" in t:
            target = "documents"
        elif "picture" in t:
            target = "pictures"
        res = organize_folder(target)
        return True, f"[Action: {res}]", res, False

    # 8c. Create Folder Intent ("create folder work", "make a folder named projects")
    if any(p in t for p in ["create folder", "make a folder", "make folder", "create a folder"]):
        m = re.search(r'(?:create\s+(?:a\s+)?folder|make\s+(?:a\s+)?folder)(?:\s+named|\s+called)?\s+([a-zA-Z0-9_\-\\/\s]+)', t)
        if m:
            f_name = m.group(1).strip()
            res = create_folder(f_name)
            return True, f"[Action: {res}]", res, False

    # 9. Search Local Files ("search for file requirements.txt", "find file ...", "where is file ...")
    if any(t.startswith(prefix) for prefix in ["search for file ", "search file ", "find file ", "where is file ", "look for file ", "find the file "]):
        clean_q = re.sub(r'^(search for file|search file|find file|where is file|look for file|find the file)\s+', '', t).strip()
        clean_q = clean_q.strip('\'".,?! ')
        if clean_q:
            res = search_local_files(clean_q)
            speech = f"I searched for {clean_q} on your system. I have placed the matching files on your screen."
            return True, f"[Action: Searched for file '{clean_q}']\n{res}", speech, False

    # 10. Read File Content ("read file X", "show file X", "what is inside file X")
    if any(t.startswith(prefix) for prefix in ["read file ", "show file ", "view file ", "what is inside file ", "display file "]):
        file_target = re.sub(r'^(read file|show file|view file|what is inside file|display file)\s+', '', t).strip()
        file_target = file_target.strip('\'".,?! ')
        if file_target:
            res = read_file_content(file_target)
            speech = f"I have read {file_target} and placed its contents on your screen."
            return True, f"[Action: Read file '{file_target}']\n{res}", speech, False

    # 11. GitHub Intent
    if "github" in t and any(w in t for w in ["open", "launch", "show", "go to"]):
        res = open_url("https://github.com", browser=browser)
        return True, f"[Action: {res}]", "Opening GitHub for you.", False

    # 12. Screenshot Intent
    if "screenshot" in t and any(w in t for w in ["take", "capture", "grab", "save"]):
        res = take_screenshot()
        return True, f"[Action: {res}]", "Screenshot taken and saved to your Pictures folder.", False

    # 13. Folder Intent ("open downloads", "open pictures", "open folder C:/...")
    if "open" in t and any(w in t for w in ["folder", "downloads", "pictures", "desktop", "documents"]):
        m = re.search(r'open\s+(?:folder\s+)?([a-zA-Z0-9_:\\/-]+)', t)
        folder = m.group(1).strip() if m else ""
        res = open_folder(folder)
        return True, f"[Action: {res}]", "Opened folder in File Explorer for you.", False

    # 14. Terminal CLI Command Intent ("run command ipconfig", "run dir")
    if t.startswith("run command ") or t.startswith("execute command ") or t.startswith("run cli "):
        cmd = re.sub(r'^(run command|execute command|run cli)\s+', '', t).strip()
        if cmd:
            out = execute_command(cmd)
            lines = out.split("\n")
            preview = "\n".join(lines[:10]) + ("\n...(truncated)" if len(lines) > 10 else "")
            action_msg = f"[Action: Executed `{cmd}`]\n{preview}"
            return True, action_msg, f"Command {cmd} executed.", False

    # 15. Application Launch Intent
    if any(w in t for w in ["open", "launch", "start", "run"]):
        if "vs code" in t or "vscode" in t or "code" in t:
            res = open_app("code")
            return True, f"[Action: {res}]", "Launching Visual Studio Code for you.", False
        for app in ["firefox", "chrome", "notepad", "terminal", "powershell", "cmd", "calculator", "calc", "explorer"]:
            if re.search(r'\b' + app + r'\b', t):
                res = open_app(app)
                return True, f"[Action: {res}]", f"Launching {app.capitalize()} for you.", False

    return False, None, None, False
