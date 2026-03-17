#!/usr/bin/env python3
"""
prepare_questions.py
Run once per language:  python prepare_questions.py nl
All files are now saved into the QUESTIONS/ folder.
"""

import sys
import re
import time
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from googletrans import Translator

if len(sys.argv) < 2:
    print("Usage: python prepare_questions.py <language_code>")
    print("Examples: en, nl, fr, de, es")
    sys.exit(1)

lang = sys.argv[1].lower()
print(f"Fetching English questions → preparing for {lang}...")

# Create folder
QUESTIONS_DIR = Path("QUESTIONS")
QUESTIONS_DIR.mkdir(exist_ok=True)

# Fetch
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
if lang == "en":
    for q in questions:
        q["translated"] = q["english"]
    print("English requested → no translation needed")
else:
    translator = Translator()
    for i, q in enumerate(questions):
        try:
            q["translated"] = translator.translate(q["english"], dest=lang).text
            time.sleep(0.35)
        except:
            q["translated"] = q["english"]
        if (i + 1) % 50 == 0:
            print(f"Translated {i+1}/1000")

# Save into QUESTIONS/
filename = QUESTIONS_DIR / f"questions_{lang}.json"
filename.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✅ Saved {len(questions)} questions to {filename}")
