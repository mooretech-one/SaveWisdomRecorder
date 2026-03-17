#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import random
import threading
import time
from datetime import datetime
import numpy as np

import sounddevice as sd
from scipy.io import wavfile
from pydub import AudioSegment

# ------------------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------------------
FONT_SIZE = 24
NEON_GREEN = "#00FF41"
DARK_BG = "#000000"
RECORDINGS_BASE = Path("RECORDINGS")
QUESTIONS_DIR = Path("QUESTIONS")
CONFIG_PATH = Path("config.json")

# ------------------------------------------------------------------------------
# CONFIG MANAGER
# ------------------------------------------------------------------------------
class ConfigManager:
    @staticmethod
    def load():
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    return json.load(f)
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
        if len(segment) > 500:
            trimmed = segment[:-500]
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

        style = ttk.Style(self)
        style.configure("Neon.TCombobox", fieldbackground="#000000", background="#000000",
                        foreground="#00FF41", padding=16, arrowsize=36)
        style.map("Neon.TCombobox", background=[("readonly", "#000000")],
                  fieldbackground=[("readonly", "#000000")], arrowsize=[("readonly", 36)])

        self.title("Save Wisdom Recorder")

        self.option_add('*TCombobox*Listbox.background', "#000000")
        self.option_add('*TCombobox*Listbox.foreground', "#00FF41")
        self.option_add('*TCombobox*Listbox.selectBackground', "#003300")
        self.option_add('*TCombobox*Listbox.selectForeground', "#00FF41")
        self.option_add('*TCombobox*Listbox.font', ("Courier", FONT_SIZE))

        self.configure(bg=DARK_BG)
        self.minsize(950, 700)
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

        if self.config.get("last_user") and self.config["last_user"] in self.config.get("users", {}):
            self.name_combo.set(self.config["last_user"])
            self._on_name_selected()

        self._reset_ui_state()

    def _build_ui(self):
        top = tk.Frame(self, bg=DARK_BG)
        top.pack(fill="x", padx=20, pady=(25, 25))

        tk.Label(top, text="NAME:", bg=DARK_BG, fg=NEON_GREEN, font=("Courier", FONT_SIZE + 2, "bold")).pack(side="left")
        self.name_combo = ttk.Combobox(top, width=32, height=24, style="Neon.TCombobox", font=("Courier", FONT_SIZE))
        self.name_combo.pack(side="left", padx=12, pady=24)
        self.name_combo.bind("<<ComboboxSelected>>", self._on_name_selected)
        self.name_combo.bind("<KeyRelease>", self._on_name_key_release)

        tk.Label(top, text="LANGUAGE:", bg=DARK_BG, fg=NEON_GREEN, font=("Courier", FONT_SIZE + 2, "bold")).pack(side="left", padx=(30, 8))
        self.lang_combo = ttk.Combobox(top, state="readonly", style="Neon.TCombobox", width=18, height=24, font=("Courier", FONT_SIZE))
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)

        self.select_btn = tk.Button(top, text="Select", bg=DARK_BG, fg=NEON_GREEN,
                                    font=("Courier", FONT_SIZE, "bold"), command=self._on_select_clicked,
                                    activebackground=DARK_BG, activeforeground=NEON_GREEN,
                                    disabledforeground=NEON_GREEN, highlightbackground=DARK_BG, height=2, padx=44)
        self.select_btn.pack(side="left", padx=22)

        qnum = tk.Frame(self, bg=DARK_BG)
        qnum.pack(fill="x", padx=20, pady=32)
        tk.Label(qnum, text="QUESTION:", bg=DARK_BG, fg=NEON_GREEN, font=("Courier", FONT_SIZE + 2, "bold")).pack(side="left")
        self.q_number_label = tk.Label(qnum, text="0000", bg=DARK_BG, fg=NEON_GREEN,
                                       font=("Courier", FONT_SIZE + 6, "bold"), width=6, relief="ridge")
        self.q_number_label.pack(side="left", padx=15)

        self.question_box = tk.Label(self, text="", bg=DARK_BG, fg=NEON_GREEN,
                                     font=("Courier", 36), wraplength=950, justify="left",
                                     relief="ridge", bd=5, height=10, padx=25, pady=50, anchor="center")
        self.question_box.pack(fill="both", expand=True, padx=20, pady=22)

        btns = tk.Frame(self, bg=DARK_BG)
        btns.pack(fill="x", padx=20, pady=22)

        self.next_btn = tk.Button(btns, text="Next Question", bg=DARK_BG, fg=NEON_GREEN,
                                  font=("Courier", FONT_SIZE, "bold"), command=self.next_question, state="disabled",
                                  activebackground=DARK_BG, activeforeground=NEON_GREEN,
                                  disabledforeground=NEON_GREEN, highlightbackground=DARK_BG,
                                  width=18, height=2, pady=22)
        self.next_btn.pack(side="left", padx=8)

        self.random_btn = tk.Button(btns, text="Random Question", bg=DARK_BG, fg=NEON_GREEN,
                                    font=("Courier", FONT_SIZE, "bold"), command=self.random_question, state="disabled",
                                    activebackground=DARK_BG, activeforeground=NEON_GREEN,
                                    disabledforeground=NEON_GREEN, highlightbackground=DARK_BG,
                                    width=18, height=2, pady=22)
        self.random_btn.pack(side="left", padx=8)

        tk.Label(btns, text="     ", bg=DARK_BG).pack(side="left")

        self.rec_btn = tk.Button(btns, text="🎤 Record", bg=DARK_BG, fg=NEON_GREEN,
                                 font=("Courier", FONT_SIZE, "bold"), command=self.start_recording, state="disabled",
                                 activebackground=DARK_BG, activeforeground=NEON_GREEN,
                                 disabledforeground=NEON_GREEN, highlightbackground=DARK_BG,
                                 width=12, height=2, pady=22)
        self.rec_btn.pack(side="left", padx=8)

        self.stop_btn = tk.Button(btns, text="⏹ Stop", bg=DARK_BG, fg=NEON_GREEN,
                                  font=("Courier", FONT_SIZE, "bold"), command=self.stop_recording, state="disabled",
                                  activebackground=DARK_BG, activeforeground=NEON_GREEN,
                                  disabledforeground=NEON_GREEN, highlightbackground=DARK_BG,
                                  width=12, height=2, pady=22)
        self.stop_btn.pack(side="left", padx=8)

        level_frame = tk.Frame(self, bg=DARK_BG)
        level_frame.pack(fill="x", padx=20, pady=22)
        tk.Label(level_frame, text="LEVEL:", bg=DARK_BG, fg=NEON_GREEN, font=("Courier", FONT_SIZE)).pack(side="left")
        self.level_canvas = tk.Canvas(level_frame, width=620, height=30, bg="#001100", highlightthickness=3, highlightbackground=NEON_GREEN)
        self.level_canvas.pack(side="left", padx=10)
        self.level_canvas.create_line(620, 5, 620, 25, fill="#003300", width=2)

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(self, textvariable=self.status_var, bg=DARK_BG, fg=NEON_GREEN,
                                   font=("Courier", FONT_SIZE), relief="sunken", anchor="w")
        self.status_bar.pack(fill="x", side="bottom", padx=20, pady=22)

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

    # === NEW HELPER: cleans the highlight on BOTH comboboxes (works for readonly language too) ===
    def _deselect_comboboxes(self):
        self.after(10, lambda: self.name_combo.selection_clear())
        self.after(10, lambda: self.lang_combo.selection_clear())

    def _reset_ui_state(self):
        if self.is_recording_ui:
            self.stop_recording(advance=False)

        self.current_question = None
        self.question_box.config(text="")
        self.q_number_label.config(text="0000")
        self.next_btn.config(state="disabled")
        self.random_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Click Select to choose user and language")
        self.ready = False

    def _on_name_selected(self, event=None):
        name = self.name_combo.get().strip()
        if name:
            users = self.config.get("users", {})
            if name in users:
                self.lang_combo.set(users[name])
            else:
                self.lang_combo.set("English")
        self._reset_ui_state()
        self._deselect_comboboxes()          # ← now cleans BOTH

    def _on_name_key_release(self, event=None):
        self._reset_ui_state()

    def _on_lang_changed(self, event=None):
        self._reset_ui_state()
        self._deselect_comboboxes()          # ← now works for language too!

    def _on_select_clicked(self):
        name = self.name_combo.get().strip()
        lang = self.lang_combo.get()

        if not name or not lang:
            messagebox.showwarning("Missing info", "Please enter a name and choose a language")
            return

        self.config.setdefault("users", {})[name] = lang
        self.config["last_user"] = name
        ConfigManager.save(self.config)

        self.name_combo["values"] = sorted(self.config["users"].keys())

        filename = QUESTIONS_DIR / f"questions_{lang}.json"
        try:
            with open(filename, encoding="utf-8") as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Missing file", f"{filename} not found.")
            return

        self.folder = RECORDINGS_BASE / name
        self.folder.mkdir(parents=True, exist_ok=True)

        self.answers_path = self.folder / "answers.json"
        if self.answers_path.exists():
            with open(self.answers_path, encoding="utf-8") as f:
                self.answers = json.load(f).get("answers", {})
        else:
            self.answers = {}

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
            self.status_var.set(f"Question {self.current_question['number']:04d} (unanswered)")
        else:
            self._show_congratulations()

    def _save_answers(self):
        data = {"answers": self.answers}
        with open(self.answers_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
            self.status_var.set("🎤 RECORDING... Speak now!")

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
        width = int(level * 620)
        self.level_canvas.delete("bar")
        self.level_canvas.create_rectangle(0, 5, width, 25, fill=NEON_GREEN, tags="bar")
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
