import os
import json
import time
import re
from typing import Dict, Any, List, Optional

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")

DEFAULT_MEMORY: Dict[str, Any] = {
    "user_name": "Shantosh",
    "facts": {
        "preferred_browser": "Firefox",
        "primary_os": "Windows 11"
    },
    "notes": []
}


def load_memory() -> Dict[str, Any]:
    """Loads memory.json from disk, creating default if missing."""
    if not os.path.exists(MEMORY_FILE):
        save_memory_data(DEFAULT_MEMORY)
        return DEFAULT_MEMORY.copy()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return DEFAULT_MEMORY.copy()
            if "facts" not in data:
                data["facts"] = {}
            if "notes" not in data:
                data["notes"] = []
            return data
    except Exception:
        return DEFAULT_MEMORY.copy()


def save_memory_data(data: Dict[str, Any]):
    """Persists dictionary to memory.json."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Warning] Failed to save memory.json: {e}")


def remember_fact_or_note(text: str) -> str:
    """Intelligently parses user input and stores it in facts or notes.
    Returns voice-friendly confirmation.
    """
    clean = text.strip().strip("'\".,?!")
    prefixes = [
        "remember that ", "remember ", "save that ", "save note ", "save this note ",
        "save this ", "note that ", "keep in mind that ", "don't forget that "
    ]
    extracted = clean
    for p in prefixes:
        if extracted.lower().startswith(p):
            extracted = extracted[len(p):].strip()
            break

    data = load_memory()

    # Check for name definition: "my name is Shantosh", "call me Shantosh"
    name_match = re.match(r'^(?:my\s+name\s+is|call\s+me)\s+([A-Za-z0-9_-]+)', extracted, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).capitalize()
        data["user_name"] = name
        save_memory_data(data)
        return f"Got it. I'll remember that your name is {name}."

    # Check for preference / key-value fact: "my favorite X is Y", "preferred browser is Firefox"
    pref_match = re.match(r'^(?:my\s+)?(favorite|preferred)\s+([a-zA-Z0-9_\s]+?)\s+(?:is|=|to\s+use)\s+(.+)$', extracted, re.IGNORECASE)
    if pref_match:
        kind = pref_match.group(1).lower()
        item = pref_match.group(2).strip().lower().replace(" ", "_")
        val = pref_match.group(3).strip()
        key = f"{kind}_{item}"
        data["facts"][key] = val
        save_memory_data(data)
        return f"Saved to memory: your {kind} {item.replace('_', ' ')} is {val}."

    # Check for general fact: "I am a ...", "I work on ...", "the project is ..."
    fact_match = re.match(r'^(?:i\s+(?:am|work\s+on|use|like)|the\s+project\s+is)\s+(.+)$', extracted, re.IGNORECASE)
    if fact_match:
        val = extracted
        key = re.sub(r'[^a-zA-Z0-9_]', '_', extracted[:30]).strip('_').lower()
        data["facts"][key] = val
        save_memory_data(data)
        return f"I've saved that fact to memory: {val}."

    # Otherwise, store as a timestamped note
    note_item = {
        "id": str(int(time.time())),
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "text": extracted
    }
    data["notes"].append(note_item)
    if len(data["notes"]) > 50:
        data["notes"] = data["notes"][-50:]
    save_memory_data(data)
    return f"Saved note: {extracted}."


def recall_memories(query: str = "") -> str:
    """Recalls saved facts and notes matching the query, or provides summary if empty."""
    data = load_memory()
    q = (query or "").strip().lower()

    facts = data.get("facts", {})
    notes = data.get("notes", [])
    user_name = data.get("user_name", "")

    # If general recall ("what do you know", "everything", "all", or blank)
    if not q or q in ("all", "everything", "what do you remember", "memories", "notes", "what do you know about me"):
        parts = []
        if user_name:
            parts.append(f"Your name is {user_name}.")
        if facts:
            fact_strs = [f"{k.replace('_', ' ')}: {v}" for k, v in list(facts.items())[:5]]
            parts.append("Saved preferences: " + ", ".join(fact_strs) + ".")
        if notes:
            recent_notes = [n["text"] for n in notes[-3:]]
            parts.append("Recent notes: " + "; ".join(recent_notes) + ".")
        if not parts:
            return "My memory is currently empty. You can tell me things to remember anytime."
        return "Here is what I have saved: " + " ".join(parts)

    # Search facts
    matched_facts = []
    for k, v in facts.items():
        if q in k.lower() or q in str(v).lower():
            matched_facts.append(f"{k.replace('_', ' ')}: {v}")

    # Search notes
    matched_notes = []
    for n in notes:
        if q in n.get("text", "").lower():
            matched_notes.append(n["text"])

    if "name" in q and user_name:
        return f"Your name is {user_name}."

    if not matched_facts and not matched_notes:
        return f"I don't have any saved memories matching '{query}'."

    res_parts = []
    if matched_facts:
        res_parts.append(", ".join(matched_facts))
    if matched_notes:
        res_parts.append("Notes: " + "; ".join(matched_notes))
    return "From memory: " + ". ".join(res_parts) + "."


def forget_memory(target: str) -> str:
    """Removes a fact or note from memory."""
    t = (target or "").strip().lower()
    data = load_memory()
    removed = False

    to_delete = [k for k in data.get("facts", {}) if t in k.lower() or t in str(data["facts"][k]).lower()]
    for k in to_delete:
        del data["facts"][k]
        removed = True

    orig_len = len(data.get("notes", []))
    data["notes"] = [n for n in data.get("notes", []) if t not in n.get("text", "").lower()]
    if len(data["notes"]) < orig_len:
        removed = True

    if removed:
        save_memory_data(data)
        return f"I've removed '{target}' from memory."
    return f"No memories found matching '{target}' to remove."


def get_memory_context_string() -> str:
    """Returns a compact context injection for the system prompt."""
    data = load_memory()
    parts = []
    if data.get("user_name"):
        parts.append(f"User: {data['user_name']}")
    facts = data.get("facts", {})
    for k, v in list(facts.items())[:8]:
        parts.append(f"{k.replace('_', ' ')}: {v}")
    notes = data.get("notes", [])
    if notes:
        recent = [n["text"] for n in notes[-2:]]
        parts.append("Recent notes: " + " | ".join(recent))
    if not parts:
        return ""
    return "[Saved User Memory & Preferences]: " + ", ".join(parts)


def delete_note_by_id(note_id: str) -> bool:
    """Deletes a single note by unique ID."""
    data = load_memory()
    notes = data.get("notes", [])
    new_notes = [n for n in notes if str(n.get("id")) != str(note_id)]
    if len(new_notes) < len(notes):
        data["notes"] = new_notes
        save_memory_data(data)
        return True
    return False


def delete_fact_by_key(fact_key: str) -> bool:
    """Deletes a single fact by key name."""
    data = load_memory()
    facts = data.get("facts", {})
    if fact_key in facts:
        del facts[fact_key]
        data["facts"] = facts
        save_memory_data(data)
        return True
    return False


def add_direct_note(note_text: str) -> Dict[str, Any]:
    """Adds a note directly without requiring voice parsing keywords."""
    data = load_memory()
    clean = note_text.strip()
    note_item = {
        "id": str(int(time.time())),
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "text": clean
    }
    data["notes"].append(note_item)
    if len(data["notes"]) > 60:
        data["notes"] = data["notes"][-60:]
    save_memory_data(data)
    return note_item


def add_direct_fact(key: str, value: str) -> bool:
    """Adds or updates a profile preference fact directly."""
    data = load_memory()
    k = re.sub(r'[^a-zA-Z0-9_]', '_', key.strip().lower())
    data["facts"][k] = value.strip()
    save_memory_data(data)
    return True
