#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import random
import threading
import time
from datetime import datetime
import numpy as np
import sys
import os
import sounddevice as sd
from scipy.io import wavfile
from pydub import AudioSegment

# ------------------------------------------------------------------------------
# RESOURCE PATH HELPER (FIXES LINUX + BUNDLED EXECUTABLE PATHS)
# ------------------------------------------------------------------------------
def resource_path(relative_path: str) -> Path:
    if getattr(sys, 'frozen', False):
        # Bundled executable: everything is next to SaveWisdomRecorder.exe
        base_path = Path(os.path.dirname(sys.executable))
    else:
        # Normal Python run
        base_path = Path(os.path.dirname(os.path.abspath(__file__)))
    return base_path / relative_path


# ------------------------------------------------------------------------------
# CONSTANTS (ALL SIZES NOW ~2/3 OF ORIGINAL)
# ------------------------------------------------------------------------------
FONT_SIZE = 16
TEXT_COLOR = "#00FF41"
BG_COLOR = "#000000"

RECORDINGS_BASE = resource_path("RECORDINGS")
QUESTIONS_DIR   = resource_path("QUESTIONS")
CONFIG_PATH     = resource_path("config.json")

# ------------------------------------------------------------------------------
# CONFIG MANAGER (with migration + answered count storage)
# ------------------------------------------------------------------------------
class ConfigManager:
    @staticmethod
    def load():
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                    # Migrate old config format
                    if "users" in data:
                        for name, value in list(data["users"].items()):
                            if isinstance(value, str):
                                data["users"][name] = {"language": value, "answered": 0}
                    return data
            except Exception:
                pass
        return {"users": {}, "last_user": ""}

    @staticmethod
    def save(data):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------------------
# AUDIO RECORDER
# ------------------------------------------------------------------------------
class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.output_path = None
        self.current_level = 0.0

    def start(self, number: int, folder: Path) -> bool:
        if self.is_recording: return False
        self.frames = []
        self.is_recording = True
        self.current_level = 0.0
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_path = folder / f"{number:04d}_{ts}.mp3"
        threading.Thread(target=self._record_loop, daemon=True).start()
        return True

    def _record_loop(self):
        def cb(indata, frames, time, status):
            if self.is_recording:
                self.frames.append(indata.copy())
                max_val = np.max(np.abs(indata)) if len(indata) > 0 else 0
                self.current_level = min(1.0, max_val * 30)
        with sd.InputStream(samplerate=44100, channels=1, callback=cb):
            while self.is_recording:
                sd.sleep(40)
        self._save_mp3()

    def stop(self) -> str | None:
        if not self.is_recording: return None
        self.is_recording = False
        self.current_level = 0.0
        time.sleep(0.3)
        return self.output_path.name if self.output_path else None

    def _save_mp3(self):
        if not self.frames:
            return
        audio = np.concatenate(self.frames)
        wav = self.output_path.with_suffix(".wav")
        wavfile.write(str(wav), 44100, audio.astype(np.float32))

        segment = AudioSegment.from_wav(str(wav))
        if len(segment) > 200:
            trimmed = segment[:-200]
        else:
            trimmed = segment

        trimmed.export(str(self.output_path), format="mp3", bitrate="192k")
        wav.unlink(missing_ok=True)


# ------------------------------------------------------------------------------
# MAIN GUI
# ------------------------------------------------------------------------------
class SaveWisdomApp(tk.Tk):
    def __init__(self):
        super().__init__()

        RECORDINGS_BASE.mkdir(parents=True, exist_ok=True)

        style = ttk.Style(self)
        style.configure("Neon.TCombobox", fieldbackground=BG_COLOR, background=BG_COLOR,
                        foreground=TEXT_COLOR, padding=11, arrowsize=24)
        style.map("Neon.TCombobox", background=[("readonly", BG_COLOR)],
                  fieldbackground=[("readonly", BG_COLOR)], arrowsize=[("readonly", 24)])

        self.title("Save Wisdom Recorder")

        self.option_add('*TCombobox*Listbox.background', BG_COLOR)
        self.option_add('*TCombobox*Listbox.foreground', TEXT_COLOR)
        self.option_add('*TCombobox*Listbox.selectBackground', BG_COLOR)
        self.option_add('*TCombobox*Listbox.selectForeground', TEXT_COLOR)
        self.option_add('*TCombobox*Listbox.font', ("Courier", FONT_SIZE))

        self.configure(bg=BG_COLOR)
        self.minsize(633, 467)
        self.update_idletasks()
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}")

        self.config = ConfigManager.load()
        self.questions = []
        self.answers = {}
        self.current_question = None
        self.recorder = AudioRecorder()
        self.folder = None
        self.ready = False
        self.is_recording_ui = False

        self._build_ui()
        self._scan_available_languages()

        self.name_combo["values"] = sorted(self.config.get("users", {}).keys())

        # Auto-load last user (percentage shows correctly)
        last_user = self.config.get("last_user")
        if last_user and last_user in self.config.get("users", {}):
            self.name_combo.set(last_user)
            user_data = self.config["users"][last_user]
            lang = user_data.get("language") if isinstance(user_data, dict) else user_data
            self.lang_combo.set(lang)
            self.after(100, self._on_select_clicked)

        self._reset_ui_state()

    def _build_ui(self):
        top = tk.Frame(self, bg=BG_COLOR)
        top.pack(fill="x", padx=13, pady=(17, 17))

        tk.Label(top, text="NAME:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Courier", FONT_SIZE + 1, "bold")).pack(side="left")
        self.name_combo = ttk.Combobox(top, width=32, height=16, style="Neon.TCombobox", font=("Courier", FONT_SIZE))
        self.name_combo.pack(side="left", padx=8, pady=16)
        self.name_combo.bind("<<ComboboxSelected>>", self._on_name_selected)
        self.name_combo.bind("<KeyRelease>", self._on_name_key_release)

        tk.Label(top, text="LANGUAGE:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Courier", FONT_SIZE + 1, "bold")).pack(side="left", padx=(20, 5))
        self.lang_combo = ttk.Combobox(top, state="readonly", style="Neon.TCombobox", width=6, height=16, font=("Courier", FONT_SIZE))
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)

        self.select_btn = tk.Button(top, text="Select", bg=BG_COLOR, fg=TEXT_COLOR,
                                    font=("Courier", FONT_SIZE, "bold"), command=self._on_select_clicked,
                                    activebackground=BG_COLOR, activeforeground=TEXT_COLOR,
                                    disabledforeground=TEXT_COLOR, highlightbackground=BG_COLOR, height=2, padx=29)
        self.select_btn.pack(side="left", padx=15)

        qnum = tk.Frame(self, bg=BG_COLOR)
        qnum.pack(fill="x", padx=13, pady=21)
        tk.Label(qnum, text="QUESTION:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Courier", FONT_SIZE + 1, "bold")).pack(side="left")
        self.q_number_label = tk.Label(qnum, text="0000", bg=BG_COLOR, fg=TEXT_COLOR,
                                       font=("Courier", FONT_SIZE + 4, "bold"), width=6, relief="ridge")
        self.q_number_label.pack(side="left", padx=10)

        self.question_box = tk.Label(self, text="", bg=BG_COLOR, fg=TEXT_COLOR,
                                     font=("Courier", 24), wraplength=1067, justify="left",
                                     relief="ridge", bd=3, height=5, padx=17, pady=33, anchor="center")
        self.question_box.pack(fill="both", expand=True, padx=13, pady=15)

        btns = tk.Frame(self, bg=BG_COLOR)
        btns.pack(fill="x", padx=13, pady=15)

        self.random_btn = tk.Button(btns, text="Random", bg=BG_COLOR, fg=TEXT_COLOR,
                                    font=("Courier", FONT_SIZE, "bold"), command=self.random_question, state="disabled",
                                    activebackground=BG_COLOR, activeforeground=TEXT_COLOR,
                                    disabledforeground=TEXT_COLOR, highlightbackground=BG_COLOR,
                                    width=12, height=2, pady=15)
        self.random_btn.pack(side="left", padx=5)

        self.next_btn = tk.Button(btns, text="Next", bg=BG_COLOR, fg=TEXT_COLOR,
                                  font=("Courier", FONT_SIZE, "bold"), command=self.next_question, state="disabled",
                                  activebackground=BG_COLOR, activeforeground=TEXT_COLOR,
                                  disabledforeground=TEXT_COLOR, highlightbackground=BG_COLOR,
                                  width=12, height=2, pady=15)
        self.next_btn.pack(side="left", padx=5)

        tk.Label(btns, text="     ", bg=BG_COLOR).pack(side="left")

        self.rec_btn = tk.Button(btns, text="🎤 Record", bg=BG_COLOR, fg=TEXT_COLOR,
                                 font=("Courier", FONT_SIZE, "bold"), command=self.start_recording, state="disabled",
                                 activebackground=BG_COLOR, activeforeground=TEXT_COLOR,
                                 disabledforeground=TEXT_COLOR, highlightbackground=BG_COLOR,
                                 width=12, height=2, pady=15)
        self.rec_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(btns, text="⏹ Stop", bg=BG_COLOR, fg=TEXT_COLOR,
                                  font=("Courier", FONT_SIZE, "bold"), command=self.stop_recording, state="disabled",
                                  activebackground=BG_COLOR, activeforeground=TEXT_COLOR,
                                  disabledforeground=TEXT_COLOR, highlightbackground=BG_COLOR,
                                  width=12, height=2, pady=15)
        self.stop_btn.pack(side="left", padx=5)

        level_frame = tk.Frame(self, bg=BG_COLOR)
        level_frame.pack(fill="x", padx=13, pady=15)

        tk.Label(level_frame, text="LEVEL:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Courier", FONT_SIZE)).pack(side="left")
        self.level_canvas = tk.Canvas(level_frame, width=413, height=20, bg=BG_COLOR, highlightthickness=2, highlightbackground=TEXT_COLOR)
        self.level_canvas.pack(side="left", padx=7)
        self.level_canvas.create_line(413, 3, 413, 17, fill=TEXT_COLOR, width=2)

        tk.Label(level_frame, text="     ", bg=BG_COLOR).pack(side="left")
        tk.Label(level_frame, text="ANSWERED:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Courier", FONT_SIZE)).pack(side="left", padx=(20, 7))
        self.progress_canvas = tk.Canvas(level_frame, width=413, height=20, bg=BG_COLOR, highlightthickness=2, highlightbackground=TEXT_COLOR)
        self.progress_canvas.pack(side="left", padx=7)
        self.progress_canvas.create_line(413, 3, 413, 17, fill=TEXT_COLOR, width=2)

        self.percent_label = tk.Label(level_frame, text="0%", bg=BG_COLOR, fg=TEXT_COLOR,
                                      font=("Courier", FONT_SIZE, "bold"), width=6)
        self.percent_label.pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(self, textvariable=self.status_var, bg=BG_COLOR, fg=TEXT_COLOR,
                                   font=("Courier", FONT_SIZE), relief="sunken", anchor="w")
        self.status_bar.pack(fill="x", side="bottom", padx=13, pady=15)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _scan_available_languages(self):
        if not QUESTIONS_DIR.exists():
            self.question_box.config(text="No QUESTIONS/ folder found!\nRun prepare_questions.py first.")
            return
        files = list(QUESTIONS_DIR.glob("questions_*.json"))
        if not files:
            self.question_box.config(text="No questions_XX.json files found!")
            return
        langs = [f.stem.replace("questions_", "") for f in files]
        self.lang_combo["values"] = sorted(langs)

    def _deselect_comboboxes(self):
        self.after(10, lambda: self.name_combo.selection_clear())
        self.after(10, lambda: self.lang_combo.selection_clear())

    def _reset_ui_state(self):
        """Reset everything INCLUDING loaded questions/answers so the percentage bar goes to 0% immediately when name/language changes."""
        if self.is_recording_ui:
            self.stop_recording(advance=False)

        self.questions = []          # ← CRITICAL: clear so bar shows 0%
        self.answers = {}            # ← CRITICAL: clear so bar shows 0%
        self.current_question = None
        self.question_box.config(text="")
        self.q_number_label.config(text="0000")
        self.next_btn.config(state="disabled")
        self.random_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Click Select to choose user and language")
        self.ready = False
        self._update_progress_bar()  # now guaranteed 0%

    def _on_name_selected(self, event=None):
        name = self.name_combo.get().strip()
        if name:
            users = self.config.get("users", {})
            user_data = users.get(name, "")
            lang = user_data.get("language") if isinstance(user_data, dict) else user_data
            self.lang_combo.set(lang or "English")
        self._reset_ui_state()
        self._deselect_comboboxes()

    def _on_name_key_release(self, event=None):
        self._reset_ui_state()

    def _on_lang_changed(self, event=None):
        self._reset_ui_state()
        self._deselect_comboboxes()

    def _update_progress_bar(self):
        """Neon percentage bar – shows 0% when no user selected, real % only after Select."""
        if not hasattr(self, "progress_canvas") or not self.questions:
            self.progress_canvas.delete("bar")
            self.percent_label.config(text="0%")
            return

        total = len(self.questions)
        answered = len(self.answers)
        perc = int((answered / total) * 100) if total > 0 else 0
        width = int(perc / 100 * 413)

        self.progress_canvas.delete("bar")
        self.progress_canvas.create_rectangle(0, 3, width, 17, fill=TEXT_COLOR, tags="bar")
        self.percent_label.config(text=f"{perc}%")

    def _on_select_clicked(self):
        name = self.name_combo.get().strip()
        lang = self.lang_combo.get()

        if not name or not lang:
            self.status_var.set("Missing info, Please enter a name and choose a language")
            return

        # Ensure config format
        users = self.config.setdefault("users", {})
        if name not in users or not isinstance(users[name], dict):
            users[name] = {"language": lang, "answered": 0}
        else:
            users[name]["language"] = lang
        self.config["last_user"] = name
        ConfigManager.save(self.config)

        self.name_combo["values"] = sorted(self.config["users"].keys())

        filename = QUESTIONS_DIR / f"questions_{lang}.json"
        try:
            with open(filename, encoding="utf-8") as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            self.status_var.set("Questions file not found!")
            return

        self.folder = RECORDINGS_BASE / name
        self.folder.mkdir(parents=True, exist_ok=True)

        self.answers_path = self.folder / "answers.json"
        if self.answers_path.exists():
            with open(self.answers_path, encoding="utf-8") as f:
                self.answers = json.load(f).get("answers", {})
        else:
            self.answers = {}

        # Cache answered count
        users[name]["answered"] = len(self.answers)
        ConfigManager.save(self.config)

        unanswered = [q for q in self.questions if str(q["number"]) not in self.answers]
        if unanswered:
            self.current_question = min(unanswered, key=lambda q: q["number"])
            self.q_number_label.config(text=f"{self.current_question['number']:04d}")
            self.question_box.config(text=self.current_question["translated"])
            self.ready = True
            self.next_btn.config(state="normal")
            self.random_btn.config(state="normal")
            self.rec_btn.config(state="normal")
            self.stop_btn.config(state="normal")
            self.status_var.set(f"Click Record to answer, Random or Next for another question")
        else:
            self._show_congratulations()

        # Show REAL percentage for this user
        self._update_progress_bar()

    def _save_answers(self):
        data = {"answers": self.answers}
        with open(self.answers_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Update cached count
        name = self.name_combo.get().strip()
        if name in self.config.get("users", {}):
            self.config["users"][name]["answered"] = len(self.answers)
            ConfigManager.save(self.config)

    def _show_congratulations(self):
        self.question_box.config(text="🎉 Congratulations!\n\nYou have answered all 1000 questions!\n\nYour wisdom is now safely recorded.")
        self.next_btn.config(state="disabled")
        self.random_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_var.set("All questions answered!")

    def next_question(self):
        if self.is_recording_ui:
            self.stop_recording(advance=False)

        if not self.current_question: return
        current_num = self.current_question["number"]
        unanswered = [q for q in self.questions if str(q["number"]) not in self.answers and q["number"] > current_num]
        if unanswered:
            self.current_question = min(unanswered, key=lambda q: q["number"])
        else:
            self.current_question = min([q for q in self.questions if str(q["number"]) not in self.answers],
                                      key=lambda q: q["number"], default=None)
        if self.current_question:
            self._display_current()
        else:
            self._show_congratulations()

    def random_question(self):
        if self.is_recording_ui:
            self.stop_recording(advance=False)

        unanswered = [q for q in self.questions if str(q["number"]) not in self.answers]
        if unanswered:
            self.current_question = random.choice(unanswered)
            self._display_current()
        else:
            self._show_congratulations()

    def _display_current(self):
        self.q_number_label.config(text=f"{self.current_question['number']:04d}")
        self.question_box.config(text=self.current_question["translated"])
        self.status_var.set(f"Question {self.current_question['number']:04d}")

    def start_recording(self):
        if not self.current_question: return
        if self.recorder.start(self.current_question["number"], self.folder):
            self.rec_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.is_recording_ui = True
            self._update_level_bar()
            self.status_var.set("🎤 RECORDING... Speak now! Clicking Stop, Random, or Next will store your answer")

    def stop_recording(self, advance=True):
        filename = self.recorder.stop()
        if filename and self.current_question:
            num_str = str(self.current_question["number"])
            self.answers[num_str] = {
                "file": filename,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_answers()
            self.status_var.set(f"✅ Saved: {filename}")

            self._update_progress_bar()

            if advance:
                self.next_question()

        self.is_recording_ui = False
        self.level_canvas.delete("bar")
        self.stop_btn.config(state="disabled")
        self.rec_btn.config(state="normal")

    def _update_level_bar(self):
        if not self.is_recording_ui:
            return
        level = self.recorder.current_level
        width = int(level * 413)
        self.level_canvas.delete("bar")
        self.level_canvas.create_rectangle(0, 3, width, 17, fill=TEXT_COLOR, tags="bar")
        self.after(40, self._update_level_bar)

    def _on_close(self):
        current_name = self.name_combo.get().strip()
        if current_name and current_name in self.config.get("users", {}):
            self.config["last_user"] = current_name
            ConfigManager.save(self.config)
        self.destroy()


if __name__ == "__main__":
    try:
        AudioSegment.converter = "ffmpeg"
    except Exception:
        print("WARNING: ffmpeg not found")

    SaveWisdomApp().mainloop()
