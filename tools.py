import os
import sys
import subprocess
import webbrowser
import shutil
import urllib.parse
from datetime import datetime

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

def open_leetcode(problem_query):
    """Opens a specific LeetCode problem or searches for it."""
    clean = problem_query.strip().strip("'\"").lower()
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
        import mss
        with mss.mss() as sct:
            sct.shot(output=filename)
        return f"Screenshot saved successfully to {filename}"
    except Exception:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(filename)
            return f"Screenshot saved successfully to {filename}"
        except Exception as e2:
            return f"Failed to take screenshot: {e2}"

def open_folder(folder_path):
    """Opens a folder in Windows File Explorer."""
    path = os.path.expanduser(folder_path.strip().strip("'\""))
    if not os.path.exists(path):
        return f"Folder does not exist: {path}"
    subprocess.Popen(["explorer.exe", os.path.normpath(path)])
    return f"Opened folder: {path}"

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
    """Runs a shell command and returns output."""
    cmd = command.strip().strip("'\"")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        out = (res.stdout + "\n" + res.stderr).strip()
        return out if out else "(Command executed successfully)"
    except Exception as e:
        return f"Error executing command: {e}"

import re
import ast

AVAILABLE_TOOLS = {
    "open_url": open_url,
    "open_leetcode": open_leetcode,
    "open_app": open_app,
    "take_screenshot": take_screenshot,
    "open_folder": open_folder,
    "move_item": move_item,
    "run_command": execute_command
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
                # Safely parse python arguments
                parsed_call = ast.parse(f"func({raw_args})").body[0].value
                args = [ast.literal_eval(a) for a in parsed_call.args]
                kwargs = {k.arg: ast.literal_eval(k.value) for k in parsed_call.keywords}
                res = func(*args, **kwargs)
                messages.append(f"[Action: {res}]")
            except Exception:
                try:
                    # Fallback for simple unquoted string
                    arg_clean = raw_args.strip("'\"")
                    res = func(arg_clean) if arg_clean else func()
                    messages.append(f"[Action: {res}]")
                except Exception as e:
                    messages.append(f"[Tool Error ({func_name}): {e}]")
        else:
            messages.append(f"[Tool Error: Unrecognized tool '{func_name}']")

    cleaned_text = re.sub(pattern, '', text).strip()
    return True, "\n".join(messages), cleaned_text

def detect_and_run_intent(text):
    """
    Directly inspects the user message for explicit tool requests
    (opening browsers, YouTube, LeetCode, software, screenshots)
    and executes them immediately without relying solely on LLM tag generation.
    Returns (handled: bool, action_msg: str, response_speech: str).
    """
    t = text.lower().strip()

    # Determine browser preference if requested
    browser = None
    if "firefox" in t:
        browser = "firefox"
    elif "chrome" in t:
        browser = "chrome"

    # 1. YouTube Intent
    if "youtube" in t and ("open" in t or "play" in t or "launch" in t or "start" in t):
        # Check if there is a specific search query on youtube
        m = re.search(r'(?:on|in|from)?\s*youtube\s*(?:for|search)?\s*(.*)', t)
        target = "https://www.youtube.com"
        if m and m.group(1).strip() and not any(w in m.group(1) for w in ["firefox", "chrome", "please", "tab"]):
            query = urllib.parse.quote(m.group(1).strip())
            target = f"https://www.youtube.com/results?search_query={query}"
        res = open_url(target, browser=browser)
        return True, f"[Action: {res}]", "Opening YouTube in Firefox for you." if browser == "firefox" else "Opening YouTube for you."

    # 2. LeetCode Intent
    if "leetcode" in t and ("open" in t or "show" in t or "go to" in t or "solve" in t):
        m = re.search(r'leetcode(?: problem)?\s*[\'"]?([a-zA-Z0-9\s-]+)[\'"]?', t)
        if m:
            prob = m.group(1).strip()
            if prob and not any(w in prob for w in ["tab", "problem", "website", "solution", "in", "firefox", "chrome"]):
                res = open_leetcode(prob)
                return True, f"[Action: {res}]", f"Opening LeetCode problem {prob} in your browser."
        res = open_url("https://leetcode.com/problemset/", browser=browser)
        return True, f"[Action: {res}]", "Opening LeetCode problem set in your browser."

    # 3. GitHub Intent
    if "github" in t and ("open" in t or "launch" in t or "show" in t):
        res = open_url("https://github.com", browser=browser)
        return True, f"[Action: {res}]", "Opening GitHub for you."

    # 4. Screenshot Intent
    if "screenshot" in t and ("take" in t or "capture" in t or "grab" in t or "save" in t):
        res = take_screenshot()
        return True, f"[Action: {res}]", "Screenshot taken and saved to your Pictures folder."

    # 5. Application Launch Intent
    if "open" in t or "launch" in t or "start" in t or "run" in t:
        if "vs code" in t or "vscode" in t or "code" in t:
            res = open_app("code")
            return True, f"[Action: {res}]", "Launching Visual Studio Code for you."
        for app in ["firefox", "chrome", "notepad", "terminal", "powershell", "cmd", "calculator", "calc", "explorer"]:
            if re.search(r'\b' + app + r'\b', t):
                res = open_app(app)
                return True, f"[Action: {res}]", f"Launching {app.capitalize()} for you."

    return False, None, None


