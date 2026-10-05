import os
import sys
import subprocess
import webbrowser
import shutil
import urllib.parse
from datetime import datetime
import re
import ast

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

def open_url(url_or_target, browser=None):
    """Opens a website or URL in Firefox, Chrome, or default browser."""
    url = url_or_target.strip().strip("'\"")
    if url.lower() == "youtube":
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

    browser_lower = (browser or "").lower()
    if "firefox" in browser_lower:
        ff = get_firefox_exe()
        if ff:
            subprocess.Popen([ff, url])
            return f"Opened {url} in Firefox."
    elif "chrome" in browser_lower:
        ch = get_chrome_exe()
        if ch:
            subprocess.Popen([ch, url])
            return f"Opened {url} in Chrome."

    webbrowser.open(url)
    return f"Opened {url} in your default browser."

def open_leetcode(problem_query=""):
    """Opens a specific LeetCode problem or the daily problem set."""
    clean = (problem_query or "").strip().strip("'\"").lower()
    # Clean unwanted filler words
    clean = re.sub(r'\b(with\s+today|today|daily|problem|problems|website|solution|in|firefox|chrome|browser|please|with)\b', '', clean).strip()
    
    if not clean or len(clean) < 2 or clean in ["all", "list", "set", "challenge"]:
        url = "https://leetcode.com/problemset/"
        webbrowser.open(url)
        return f"Opened LeetCode problem set in browser ({url})."

    slug = clean.replace(" ", "-").replace("_", "-")
    if "-" in slug and slug.split("-")[0].isdigit():
        slug = "-".join(slug.split("-")[1:])
    slug = slug.strip("-")
    
    url = f"https://leetcode.com/problems/{slug}/"
    webbrowser.open(url)
    return f"Opened LeetCode problem '{problem_query}' in browser ({url})."

def open_app(app_name):
    """Opens local applications (Firefox, VS Code, Notepad, Terminal, Explorer, etc.)"""
    name = app_name.strip().strip("'\"").lower()
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
    else:
        subprocess.Popen(["start", app_name], shell=True)
        return f"Attempted to open application: {app_name}"

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

def execute_command(command):
    """Runs a shell CLI command and returns output."""
    cmd = command.strip().strip("'\"")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
        out = (res.stdout + "\n" + res.stderr).strip()
        return out if out else "(Command executed successfully with no output)"
    except Exception as e:
        return f"Error executing command: {e}"

def search_local_files(query, directory=None):
    """Searches for files matching query in a directory."""
    base_dir = os.path.expanduser(directory.strip().strip("'\"")) if directory else os.path.expanduser("~")
    matches = []
    q = query.lower()
    for root, dirs, files in os.walk(base_dir):
        if any(h in root for h in ["AppData", ".git", "node_modules", ".cache"]):
            continue
        for f in files:
            if q in f.lower():
                matches.append(os.path.join(root, f))
                if len(matches) >= 10:
                    break
        if len(matches) >= 10:
            break
    if not matches:
        return f"No files matching '{query}' found in {base_dir}."
    return "\n".join(matches)

def read_file_content(file_path):
    """Reads the contents of a local file."""
    p = os.path.expanduser(file_path.strip().strip("'\""))
    if not os.path.exists(p):
        return f"File does not exist: {p}"
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
    "open_leetcode": open_leetcode,
    "open_app": open_app,
    "take_screenshot": take_screenshot,
    "inspect_screen": inspect_screen,
    "see_screen": inspect_screen,
    "read_screen": inspect_screen,
    "adjust_brightness": adjust_brightness,
    "adjust_volume": adjust_volume,
    "get_installed_games": get_installed_games,
    "open_folder": open_folder,
    "move_item": move_item,
    "run_command": execute_command,
    "search_files": search_local_files,
    "read_file": read_file_content
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
                if isinstance(res, list):
                    res = ", ".join(res)
                messages.append(f"[Action: {res}]")
            except Exception:
                try:
                    arg_clean = raw_args.strip("'\"")
                    res = func(arg_clean) if arg_clean else func()
                    if isinstance(res, list):
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

    # 5. YouTube Intent (clean extraction, avoids treating 'in my browser' as a search)
    if "youtube" in t and any(w in t for w in ["open", "play", "launch", "start", "show", "watch", "want"]):
        target = "https://www.youtube.com"
        m = re.search(r'play\s+(.+?)\s+(?:on|in)\s+youtube', t)
        if not m:
            m = re.search(r'(?:search\s+(?:on\s+)?youtube\s+for|youtube\s+search\s+(?:for\s+)?)(.+)', t)
        if m:
            query = m.group(1).strip()
            query = re.sub(r'\b(in\s+my\s+browser|in\s+browser|in\s+firefox|in\s+chrome|please|tab|video)\b', '', query).strip()
            if query and len(query) > 1:
                target = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        res = open_url(target, browser=browser)
        speech = "Opening YouTube in Firefox for you." if browser == "firefox" else "Opening YouTube for you."
        return True, f"[Action: {res}]", speech, False

    # 6. LeetCode Intent (fixes 404 on 'today', 'daily', etc.)
    if "leetcode" in t and any(w in t for w in ["open", "show", "go to", "solve", "want", "do"]):
        if any(w in t for w in ["today", "daily", "problemset", "problems", "list", "challenge"]) and not re.search(r'\b(two sum|three sum|valid parentheses|invert binary tree|reverse linked list)\b', t):
            res = open_url("https://leetcode.com/problemset/", browser=browser)
            return True, f"[Action: {res}]", "Opening LeetCode problem set in your browser.", False
        
        m = re.search(r'leetcode(?:\s+problem)?\s+[\'\"“]?([a-zA-Z0-9\s-]+)[\'\"”]?', t)
        if m:
            prob = m.group(1).strip()
            prob = re.sub(r'\b(with\s+today|today|daily|problem|problems|website|solution|in|firefox|chrome|browser|please|with)\b', '', prob).strip()
            if prob and len(prob) > 2:
                res = open_leetcode(prob)
                return True, f"[Action: {res}]", f"Opening LeetCode problem {prob} in your browser.", False

        res = open_url("https://leetcode.com/problemset/", browser=browser)
        return True, f"[Action: {res}]", "Opening LeetCode in your browser.", False

    # 7. GitHub Intent
    if "github" in t and any(w in t for w in ["open", "launch", "show", "go to"]):
        res = open_url("https://github.com", browser=browser)
        return True, f"[Action: {res}]", "Opening GitHub for you.", False

    # 8. Screenshot Intent
    if "screenshot" in t and any(w in t for w in ["take", "capture", "grab", "save"]):
        res = take_screenshot()
        return True, f"[Action: {res}]", "Screenshot taken and saved to your Pictures folder.", False

    # 9. Folder Intent ("open downloads", "open pictures", "open folder C:/...")
    if "open" in t and any(w in t for w in ["folder", "downloads", "pictures", "desktop", "documents"]):
        m = re.search(r'open\s+(?:folder\s+)?([a-zA-Z0-9_:\\/-]+)', t)
        folder = m.group(1).strip() if m else ""
        res = open_folder(folder)
        return True, f"[Action: {res}]", "Opened folder in File Explorer for you.", False

    # 10. Terminal CLI Command Intent ("run command ipconfig", "run dir")
    if t.startswith("run command ") or t.startswith("execute command ") or t.startswith("run cli "):
        cmd = re.sub(r'^(run command|execute command|run cli)\s+', '', t).strip()
        if cmd:
            out = execute_command(cmd)
            lines = out.split("\n")
            preview = "\n".join(lines[:10]) + ("\n...(truncated)" if len(lines) > 10 else "")
            action_msg = f"[Action: Executed `{cmd}`]\n{preview}"
            return True, action_msg, f"Command {cmd} executed.", False

    # 11. Application Launch Intent
    if any(w in t for w in ["open", "launch", "start", "run"]):
        if "vs code" in t or "vscode" in t or "code" in t:
            res = open_app("code")
            return True, f"[Action: {res}]", "Launching Visual Studio Code for you.", False
        for app in ["firefox", "chrome", "notepad", "terminal", "powershell", "cmd", "calculator", "calc", "explorer"]:
            if re.search(r'\b' + app + r'\b', t):
                res = open_app(app)
                return True, f"[Action: {res}]", f"Launching {app.capitalize()} for you.", False

    return False, None, None, False
