import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import sandbox
import patcher
import os
import time
import difflib
import threading

# --- CONFIGURATION ---
DEFAULT_RETRIES = 10
THEME = {
    "bg": "#1e1e1e", "fg": "#d4d4d4", 
    "input_bg": "#252526", "success": "#4ec9b0", 
    "error": "#f44747", "diff_add": "#b5cea8", 
    "diff_sub": "#ce9178", "keyword": "#569cd6", 
    "string": "#ce9178", "comment": "#6a9955",
    "accent": "#007acc"
}

class AutoDebuggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DevForge: Local AI Auto-Debugger (With Editor)")
        self.root.geometry("1400x900")
        self.root.configure(bg=THEME["bg"])
        self.current_file_path = None

        self.setup_ui()

    def setup_ui(self):
        # 1. TOOLBAR
        toolbar = tk.Frame(self.root, bg="#333333", height=40)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        tk.Button(toolbar, text="📂 OPEN FILE", command=self.open_file, bg="#444", fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(toolbar, text="💾 SAVE FIXED", command=self.save_file, bg="#444", fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=5, pady=5)
        self.status_label = tk.Label(toolbar, text="System Ready", bg="#333333", fg="#aaa", font=("Consolas", 9))
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # 2. MAIN SPLIT VIEW
        main_frame = tk.Frame(self.root, bg=THEME["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- LEFT SIDE (Input) ---
        left_frame = tk.Frame(main_frame, bg=THEME["bg"])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tk.Label(left_frame, text="SOURCE CODE", bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w")
        self.input_area = scrolledtext.ScrolledText(left_frame, bg=THEME["input_bg"], fg=THEME["fg"], insertbackground="white", font=("Consolas", 10))
        self.input_area.pack(fill=tk.BOTH, expand=True)
        self.input_area.bind("<KeyRelease>", self.highlight_syntax_event)

        # --- RIGHT SIDE (Output + AI Refiner) ---
        right_frame = tk.Frame(main_frame, bg=THEME["bg"])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Output Area
        tk.Label(right_frame, text="REPAIRED CODE", bg=THEME["bg"], fg=THEME["success"]).pack(anchor="w")
        self.output_area = scrolledtext.ScrolledText(right_frame, bg=THEME["input_bg"], fg=THEME["fg"], insertbackground="white", font=("Consolas", 10))
        self.output_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # === NEW: AI INPUT BAR ===
        refine_frame = tk.Frame(right_frame, bg="#2d2d30", bd=1, relief=tk.SUNKEN)
        refine_frame.pack(fill=tk.X, pady=(0, 0))
        
        tk.Label(refine_frame, text="✨ AI Edit:", bg="#2d2d30", fg="#ffd700", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.refine_entry = tk.Entry(refine_frame, bg="#3e3e42", fg="white", insertbackground="white", relief=tk.FLAT, font=("Consolas", 10))
        self.refine_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.refine_entry.bind("<Return>", lambda e: self.start_refinement_thread()) # Enter key support

        self.btn_refine = tk.Button(refine_frame, text="APPLY", command=self.start_refinement_thread, 
                                    bg=THEME["accent"], fg="white", relief=tk.FLAT, font=("Segoe UI", 9, "bold"))
        self.btn_refine.pack(side=tk.RIGHT, padx=5, pady=5)
        # =========================

        # 3. CONTROLS (Bottom)
        control_frame = tk.Frame(self.root, bg=THEME["bg"])
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.progress = ttk.Progressbar(control_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        retry_frame = tk.Frame(control_frame, bg=THEME["bg"])
        retry_frame.pack(side=tk.RIGHT)
        tk.Label(retry_frame, text="Max Cycles:", bg=THEME["bg"], fg="#aaa").pack(side=tk.LEFT, padx=5)
        self.retry_spinner = tk.Spinbox(retry_frame, from_=1, to=100, width=5, bg="#333", fg="white", buttonbackground="#444")
        self.retry_spinner.delete(0, "end")
        self.retry_spinner.insert(0, DEFAULT_RETRIES)
        self.retry_spinner.pack(side=tk.LEFT, padx=5)

        self.btn_run = tk.Button(retry_frame, text="▶ START DEBUGGING", command=self.start_debugging_thread, 
                                 bg=THEME["accent"], fg="white", font=("Segoe UI", 11, "bold"), padx=10)
        self.btn_run.pack(side=tk.LEFT)

        # 4. LOGS
        tk.Label(self.root, text="SYSTEM LOGS", bg=THEME["bg"], fg="#569cd6").pack(anchor="w", padx=10)
        self.log_area = scrolledtext.ScrolledText(self.root, bg="#101010", fg=THEME["fg"], height=10, font=("Consolas", 9))
        self.log_area.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.configure_tags()

    def configure_tags(self):
        self.log_area.tag_config("success", foreground=THEME["success"])
        self.log_area.tag_config("error", foreground=THEME["error"])
        self.log_area.tag_config("diff_add", foreground=THEME["diff_add"], background="#0f291e")
        self.log_area.tag_config("diff_sub", foreground=THEME["diff_sub"], background="#2d1414")
        self.log_area.tag_config("info", foreground=THEME["fg"])
        self.log_area.tag_config("ai", foreground="#ffd700") # Gold for AI edits

        # Syntax tags
        self.input_area.tag_config("keyword", foreground=THEME["keyword"])
        self.input_area.tag_config("string", foreground=THEME["string"])
        self.input_area.tag_config("comment", foreground=THEME["comment"])

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py")])
        if path:
            self.current_file_path = path
            with open(path, "r") as f: content = f.read()
            self.input_area.delete("1.0", tk.END)
            self.input_area.insert(tk.END, content)
            self.status_label.config(text=f"Loaded: {os.path.basename(path)}")
            self.highlight_syntax()

    def save_file(self):
        content = self.output_area.get("1.0", tk.END)
        path = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python Files", "*.py")])
        if path:
            with open(path, "w") as f: f.write(content)
            messagebox.showinfo("Saved", "Fixed code saved successfully!")

    def highlight_syntax_event(self, event=None):
        self.highlight_syntax()

    def highlight_syntax(self):
        # Basic Regex Syntax Highlighting
        content = self.input_area.get("1.0", tk.END)
        for tag in ["keyword", "string", "comment"]:
            self.input_area.remove_tags(tag, "1.0", tk.END)
        
        keywords = r"\b(def|class|import|from|return|if|else|elif|while|for|try|except|print)\b"
        self._apply_tag(keywords, "keyword")
        strings = r"(\".*?\"|\'.*?\')"
        self._apply_tag(strings, "string")
        comments = r"(#.*)"
        self._apply_tag(comments, "comment")

    def _apply_tag(self, pattern, tag):
        count = tk.IntVar()
        start = "1.0"
        while True:
            pos = self.input_area.search(pattern, start, stopindex=tk.END, count=count, regexp=True)
            if not pos: break
            self.input_area.tag_add(tag, pos, f"{pos}+{count.get()}c")
            start = f"{pos}+{count.get()}c"

    def log(self, text, tag="info"):
        self.log_area.insert(tk.END, text, tag)
        self.log_area.see(tk.END)

    def generate_diff(self, original, modified):
        d = difflib.unified_diff(original.splitlines(), modified.splitlines(), lineterm='')
        return list(d)

    # --- NEW: AI REFINEMENT LOGIC ---
    def start_refinement_thread(self):
        t = threading.Thread(target=self.run_refinement)
        t.start()

    def run_refinement(self):
        instruction = self.refine_entry.get().strip()
        current_code = self.output_area.get("1.0", tk.END).strip()
        
        if not current_code:
            messagebox.showwarning("Error", "No code to refine! Run debugging first.")
            return
        if not instruction:
            return

        # UI Updates
        self.btn_refine.config(state=tk.DISABLED, text="Thinking...")
        self.status_label.config(text=f"AI is applying: '{instruction}'...")
        self.log(f"\n>>> USER INSTRUCTION: {instruction}\n", "ai")
        
        # Call Patcher
        new_code, reason = patcher.apply_user_instruction(current_code, instruction)
        
        # Show Diff
        diffs = self.generate_diff(current_code, new_code)
        if diffs:
            self.log(">>> DIFF:\n", "info")
            for line in diffs:
                if line.startswith("+"): self.log(line+"\n", "diff_add")
                elif line.startswith("-"): self.log(line+"\n", "diff_sub")
        else:
            self.log(">>> No changes made by AI.\n", "info")

        # Update Code Area
        self.output_area.delete("1.0", tk.END)
        self.output_area.insert(tk.END, new_code)
        
        # Reset UI
        self.btn_refine.config(state=tk.NORMAL, text="APPLY")
        self.status_label.config(text="Status: Ready")
        self.refine_entry.delete(0, tk.END)
    # --------------------------------

    def start_debugging_thread(self):
        t = threading.Thread(target=self.run_debugging)
        t.start()

    def run_debugging(self):
        current_code = self.input_area.get("1.0", tk.END).strip()
        if not current_code: 
            messagebox.showwarning("Empty", "Please enter code first.")
            return

        self.btn_run.config(state=tk.DISABLED, text="⏳ RUNNING...")
        try: max_retries = int(self.retry_spinner.get())
        except: max_retries = 10

        self.log_area.delete("1.0", tk.END)
        self.output_area.delete("1.0", tk.END)
        self.log(f">>> STARTING ENGINE (Cycles: {max_retries})...\n", "info")
        
        temp_filename = "temp_debug_target.py"
        self.progress["value"] = 0
        self.progress["maximum"] = max_retries
        success = False

        for attempt in range(1, max_retries + 1):
            self.progress["value"] = attempt
            self.log(f"--- CYCLE {attempt} ---\n", "info")
            
            with open(temp_filename, "w") as f: f.write(current_code)
            result = sandbox.run_code(temp_filename)
            
            if result["success"]:
                self.progress["value"] = max_retries
                self.log(">>> SUCCESS: Execution completed!\n", "success")
                if result["output"]: self.log(f"Output:\n{result['output']}\n", "info")
                self.output_area.delete("1.0", tk.END)
                self.output_area.insert(tk.END, current_code)
                self.status_label.config(text="Status: Fixed & Stable")
                success = True
                break 

            error_msg = result["error"].strip()
            short_err = error_msg.splitlines()[-1] if error_msg else "Crash"
            self.log(f">>> ERROR: {short_err}\n", "error")

            self.status_label.config(text="Status: Analyzing...")
            new_code, reason = patcher.analyze_and_fix(current_code, error_msg)
            
            if new_code.strip() == current_code.strip():
                new_code += f"\n# [AUTO-LOG] Stuck on: {short_err}"
            
            diffs = self.generate_diff(current_code, new_code)
            if diffs:
                self.log(f">>> FIX: {reason}\n", "success")
                self.log(">>> DIFF:\n", "info")
                for line in diffs:
                    if line.startswith("+"): self.log(line+"\n", "diff_add")
                    elif line.startswith("-"): self.log(line+"\n", "diff_sub")
            
            current_code = new_code
            self.output_area.delete("1.0", tk.END)
            self.output_area.insert(tk.END, current_code)
        
        if os.path.exists(temp_filename): os.remove(temp_filename)
        self.btn_run.config(state=tk.NORMAL, text="▶ START DEBUGGING")
        if not success: self.status_label.config(text="Status: Stopped (Unresolved)")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoDebuggerApp(root)
    root.mainloop()
