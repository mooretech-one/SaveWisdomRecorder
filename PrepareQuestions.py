#!/usr/bin/env python3
"""
prepare_questions.py
Run once per language:  python prepare_questions.py Dutch

Now uses the FULL official googletrans language list (108+ languages).
Accepts full names, native names, or 2-letter codes.
OUTPUT FILE ALWAYS uses the country code → questions_nl.json (GUI compatibility guaranteed)
"""

import sys
import re
import time
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from googletrans import Translator, LANGCODES, LANGUAGES

if len(sys.argv) < 2:
    print("Usage: python prepare_questions.py <language>")
    print("Examples: Dutch, French, German, Spanish, Nederlands, nl, fr, de, es")
    print("          Vietnamese, Thai, Indonesian, Hebrew, Simplified Chinese, etc.")
    sys.exit(1)

# ====================== FULL DYNAMIC LANGUAGE RESOLUTION ======================
user_input = sys.argv[1].strip()
key = user_input.lower().strip()

# 1. Direct 2-letter code
if len(key) == 2 and key.isalpha() and key in LANGUAGES:
    lang_code = key
    display_name = LANGUAGES[key].title()

# 2. Exact name from googletrans.LANGCODES
elif key in LANGCODES:
    lang_code = LANGCODES[key]
    display_name = user_input.title()

# 3. Smart cleaned matching (handles "Simplified Chinese", "Brazilian Portuguese", etc.)
else:
    clean_key = key.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    name_to_code = {
        name.lower().replace(" ", "").replace("-", "").replace("(", "").replace(")", ""): code
        for code, name in LANGUAGES.items()
    }
    if clean_key in name_to_code:
        lang_code = name_to_code[clean_key]
        display_name = user_input.title()
    else:
        # Extra common aliases not perfectly covered by cleaning
        extra = {
            "chinese": "zh-cn",
            "mandarin": "zh-cn",
            "cantonese": "zh-tw",
            "brazilian": "pt",
            "portuguese brazil": "pt",
            "farsi": "fa",
            "persian": "fa",
            "hebrew": "iw",
        }
        extra_key = clean_key
        if extra_key in extra:
            lang_code = extra[extra_key]
            display_name = user_input.title()
        else:
            print(f"❌ Unknown language: '{user_input}'")
            print("Supported examples: English, Dutch, French, German, Spanish, Vietnamese, Thai,")
            print("Indonesian, Hebrew, Ukrainian, Hindi, Japanese, Korean, Chinese (Simplified), etc.")
            print("Or use any 2-letter code like nl, vi, th, id, iw...")
            sys.exit(1)

print(f"Preparing questions for {display_name} → code: {lang_code}...")

# Create folder
QUESTIONS_DIR = Path("QUESTIONS")
QUESTIONS_DIR.mkdir(exist_ok=True)

# === IMPORTANT: Output filename ALWAYS uses the country code ===
filename = QUESTIONS_DIR / f"questions_{lang_code}.json"

# Ask before overwriting
if filename.exists():
    response = input(f"⚠️  File '{filename.name}' already exists.\n"
                     f"Do you want to re-translate and overwrite it? (y/n): ").strip().lower()

    if response not in ('y', 'yes'):
        print("✅ Operation cancelled – existing file was left unchanged.")
        sys.exit(0)
    else:
        print("Overwriting with fresh translation...")

# Fetch English questions
print("Fetching English questions from savewisdom.org...")
resp = requests.get("https://savewisdom.org/the-1000-word-save-wisdom-questions/", timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")
questions = []
for p in soup.find_all("p"):
    text = p.get_text().strip()
    match = re.match(r"^(\d{1,4})\.\s*(.+)$", text)
    if match:
        questions.append({
            "number": int(match.group(1)),
            "english": match.group(2).strip(),
            "translated": ""
        })

# Translate (skip for English)
if lang_code == "en":
    for q in questions:
        q["translated"] = q["english"]
    print("English requested → no translation needed")
else:
    translator = Translator()
    print(f"Starting translation to {display_name} (code: {lang_code}) — this may take a minute...")
    for i, q in enumerate(questions):
        try:
            q["translated"] = translator.translate(q["english"], dest=lang_code).text
            time.sleep(0.35)
        except Exception:
            print(f"⚠️  Translation failed for question {i+1} → using English fallback")
            q["translated"] = q["english"]
        if (i + 1) % 50 == 0:
            print(f"Translated {i + 1}/1000")

# Save (filename uses country code only)
filename.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✅ Saved {len(questions)} questions to {filename}")
print(f"   Language: {display_name} (file: questions_{lang_code}.json)")
