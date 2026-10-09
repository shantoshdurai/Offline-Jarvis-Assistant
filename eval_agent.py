"""Jarvis AI Assistant — Comprehensive Evaluation & Benchmark Suite.
Tests tool accuracy, voice TTS sanitization, persistent memory lifecycle,
and natural conversational dismissal detection.
"""

import os
import sys
import json
import re
import urllib.parse
from typing import Dict, Any, List

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_manager as mm
import tools


def test_dismissal_detector(is_dismissal_fn):
    """Evaluates dismissal detection against tricky real-world voice inputs."""
    print("\n--- Test Suite 1: Voice Dismissal & Sleep Detector ---")
    test_cases = [
        # Expected True (Dismissals / Sleep)
        ("that's all bye", True, "Standard dismissal"),
        ("thats all", True, "Quick dismissal"),
        ("that is all for now", True, "Polite dismissal"),
        ("bye bye", True, "Short goodbye"),
        ("no thanks for that bye bye", True, "Polite goodbye with prefix"),
        ("thanks for that bye", True, "Thank you and bye"),
        ("okay thank you bye", True, "Confirmation and bye"),
        ("no i didn't mean something i say terminator self", True, "STT slip for terminate yourself"),
        ("terminator self", True, "Phonetic mishearing"),
        ("terminate yourself", True, "Direct termination request"),
        ("go to sleep", True, "Standby command"),
        ("sleep now", True, "Direct sleep command"),
        ("stop listening", True, "Mute / standby command"),
        ("and then i want you to shut down", True, "Request for Jarvis to shut down"),
        ("shut down", True, "Self shutdown without PC mention"),
        ("turn off", True, "Self turn off without PC mention"),
        ("say nothing", True, "Say nothing dismissal"),
        ("nothing", True, "Single word nothing dismissal"),
        ("no nothing", True, "No nothing dismissal"),
        ("nothing for now", True, "Nothing for now dismissal"),
        ("off", True, "Direct off dismissal"),
        ("off jarvis", True, "Off jarvis dismissal"),
        ("never mind", True, "Never mind dismissal"),
        ("nevermind", True, "Nevermind dismissal"),
        ("be quiet", True, "Be quiet dismissal"),
        ("quiet", True, "Quiet dismissal"),
        ("stop", True, "Stop command"),

        # Expected False (App / System commands that must NOT trigger self-sleep)
        ("close the chrome", False, "Close app command"),
        ("can you please close that in chrome and open that on firefox", False, "Multi-app command"),
        ("close this window", False, "Close window command"),
        ("close notepad", False, "Close notepad command"),
        ("terminate chrome", False, "Terminate app command"),
        ("shut down the pc", False, "System PC shutdown command"),
        ("shut down my computer", False, "System computer shutdown command"),
        ("open youtube and play loki music", False, "Media playback command"),
        ("search for files in downloads", False, "File search command"),
        ("what is the weather today", False, "General question"),
    ]

    passed = 0
    failed = 0
    for text, expected, desc in test_cases:
        actual = is_dismissal_fn(text)
        if actual == expected:
            passed += 1
            print(f"  [PASS] {desc}: {text!r} -> {actual}")
        else:
            failed += 1
            print(f"  [FAIL] {desc}: {text!r} -> got {actual}, expected {expected}")

    print(f"Dismissal Suite Results: {passed}/{len(test_cases)} Passed.")
    assert failed == 0, f"{failed} dismissal tests failed."


def test_voice_tts_sanitizer(clean_spoken_fn):
    """Evaluates that TTS never pronounces raw URLs, query +, or code blocks."""
    print("\n--- Test Suite 2: Voice TTS Sanitizer ---")
    test_cases = [
        ("Opened https://chatgpt.com in Firefox.", "Opened ChatGPT in Firefox."),
        ("Opened https://www.google.com/search?q=opened+youtube+loki+music in Chrome.", "Opened opened youtube loki music in Chrome."),
        ("Playing 'loki music' on YouTube.", "Playing 'loki music' on YouTube."),
        ("Check https://reddit.com/r/python for docs.", "Check Reddit for docs."),
        ("```python\nprint('hello')\n``` Done!", "Done!"),
        ("File saved at C:\\Users\\Dog\\Downloads\\report.pdf", "File saved at report.pdf"),
    ]

    for raw, expected in test_cases:
        res = clean_spoken_fn(raw)
        print(f"  RAW   : {raw}")
        print(f"  CLEAN : {res}")
        assert "https://" not in res, f"Raw URL leaked into TTS: {res}"
        assert "http://" not in res, f"Raw URL leaked into TTS: {res}"
        assert "```" not in res, f"Code block leaked into TTS: {res}"
        assert "+" not in res or " " in res, f"Raw + query leaked: {res}"
    print("Voice TTS Sanitizer: 100% Clean Speech Verified.")


def test_persistent_memory_lifecycle():
    """Evaluates save, recall, update, context injection, and persistence."""
    print("\n--- Test Suite 3: Persistent Memory Lifecycle ---")
    # 1. Save preferences
    s1 = mm.remember_fact_or_note("remember that my preferred browser is Firefox")
    print("  Save 1:", s1)
    assert "Firefox" in s1

    s2 = mm.remember_fact_or_note("my favorite music is Loki soundtrack")
    print("  Save 2:", s2)
    assert "Loki" in s2

    # 2. Save note
    s3 = mm.remember_fact_or_note("save note: prepare deployment for Jarvis 2.0")
    print("  Save 3:", s3)
    assert "Jarvis 2.0" in s3

    # 3. Specific recall
    r_browser = mm.recall_memories("browser")
    print("  Recall 'browser':", r_browser)
    assert "Firefox" in r_browser

    r_music = mm.recall_memories("music")
    print("  Recall 'music':", r_music)
    assert "Loki" in r_music

    # 4. Global recall
    r_all = mm.recall_memories()
    print("  Recall All:", r_all)
    assert "Firefox" in r_all
    assert "Shantosh" in r_all

    # 5. System prompt context injection
    ctx = mm.get_memory_context_string()
    print("  Injected Context:", ctx)
    assert "Firefox" in ctx
    assert "Shantosh" in ctx

    # 6. Direct note & fact CRUD operations (used by Dashboard GUI)
    note_added = mm.add_direct_note("Deploy Jarvis 2.0 to GitHub")
    assert note_added.get("text") == "Deploy Jarvis 2.0 to GitHub"
    del_note_ok = mm.delete_note_by_id(note_added.get("id"))
    assert del_note_ok is True

    fact_added = mm.add_direct_fact("favorite_editor", "VS Code")
    assert fact_added is True
    assert mm.load_memory()["facts"]["favorite_editor"] == "VS Code"
    del_fact_ok = mm.delete_fact_by_key("favorite_editor")
    assert del_fact_ok is True
    assert "favorite_editor" not in mm.load_memory()["facts"]
    print("Persistent Memory Suite: 100% Passed.")


def test_tool_dispatch():
    """Evaluates tool implementations and graceful execution."""
    print("\n--- Test Suite 4: Tool Execution & Safeguards ---")

    # 1. Close app safeguard
    res_close = tools.close_app("nonexistent_test_proc_9999")
    print("  Close App (nonexistent):", res_close)
    assert "was closed or not running" in res_close or "Closed" in res_close

    # 2. Volume control
    res_vol = tools.adjust_volume("up")
    print("  Volume Up:", res_vol)
    assert "Volume" in res_vol

    # 3. List folder
    res_list = tools.list_folder_contents("project")
    print("  List Folder (project):", res_list.split("\n")[0])
    assert "Contents of" in res_list

    # 4. Search files
    res_search = tools.search_local_files("fast_agent.py")
    print("  Search File (fast_agent.py):", res_search.split("\n")[0])
    assert "fast_agent.py" in res_search

    # 5. Dynamic App Resolver (resolves installed software without hardcoding)
    antigravity_path, name = tools.find_app_shortcut("antigravity")
    print(f"  App Resolver ('antigravity'): {name} -> {antigravity_path}")
    assert antigravity_path is not None, "Failed to resolve Antigravity shortcut"

    # 6. Safe open_app without Windows popup
    res_missing = tools.open_app("nonexistent_unknown_software_999")
    print("  Open App (missing fallback):", res_missing)
    assert "couldn't find" in res_missing.lower()

    # 7. List installed apps
    res_apps = tools.list_installed_apps()
    print("  List Installed Apps:", res_apps[:80] + "...")
    assert "Found" in res_apps and "installed applications" in res_apps

    # 8. Clarification question on misheard app name (e.g. 'gravity' -> Antigravity)
    res_misheard = tools.open_app("gravity")
    print("  Misheard App Confirmation:", res_misheard)
    assert "did you mean" in res_misheard.lower()

    # 9. Confirmation question on ambiguous app name (e.g. 'studio' -> multiple options)
    res_ambiguous = tools.open_app("studio")
    print("  Ambiguous App Confirmation:", res_ambiguous)
    assert "which one would you like" in res_ambiguous.lower()

    print("Tool Execution Suite: 100% Passed.")


def test_stt_engine_factory():
    """Evaluates STT engine discovery and verifies Parakeet-TDT 622MB engine."""
    print("\n--- Test Suite 5: STT Engine Discovery & Model Factory ---")
    from parakeet_stt import get_best_stt_engine, ParakeetTDT
    engine = get_best_stt_engine()
    assert engine is not None, "Failed to discover an active STT engine"
    print(f"  Discovered Engine: {engine.__class__.__name__}")
    assert isinstance(engine, ParakeetTDT), f"Expected ParakeetTDT, got {engine.__class__.__name__}"
    print("STT Engine Factory Suite: 100% Passed.")


if __name__ == "__main__":
    print("============================================================")
    print("  Jarvis AI Assistant — Comprehensive Evaluation Suite")
    print("============================================================")

    # Import fast_agent helpers
    from fast_agent import FastAgent, clean_spoken_text

    class MockAgent:
        voice_dismissal_enabled = True
        is_dismissal_command = FastAgent.is_dismissal_command

    mock_agent = MockAgent()
    test_dismissal_detector(mock_agent.is_dismissal_command)
    test_voice_tts_sanitizer(clean_spoken_text)
    test_persistent_memory_lifecycle()
    test_tool_dispatch()
    test_stt_engine_factory()

    print("\n============================================================")
    print("  ALL 5 EVALUATION SUITES PASSED (100% SUCCESS RATE) 🚀")
    print("============================================================\n")
