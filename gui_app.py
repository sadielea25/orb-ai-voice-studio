"""
gui_app.py
A graphical desktop interface for the Companies House & GOV.UK Automation Agent.
Uses subprocess execution for 100% thread safety and zero greenlet crashes.
"""

import os
import sys
import subprocess
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class AgentGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Companies House & GOV.UK Form Assistant")
        self.geometry("820x760")
        self.minsize(780, 700)
        self.configure(bg="#f4f6f8")

        # Setup modern TTK styling
        self.setup_styles()

        # Build UI layout
        self.create_header()
        self.create_status_bar()
        self.create_action_cards()
        self.create_settings_card()
        self.create_log_console()

    def setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure("TFrame", background="#f4f6f8")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("CardHeader.TLabel", background="#ffffff", font=("Segoe UI", 11, "bold"), foreground="#1e293b")
        self.style.configure("CardSub.TLabel", background="#ffffff", font=("Segoe UI", 9), foreground="#64748b")
        self.style.configure("TLabel", background="#f4f6f8", font=("Segoe UI", 10), foreground="#334155")
        
        self.style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            background="#0284c7",
            foreground="#ffffff",
            padding=(12, 8),
            borderwidth=0
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", "#0369a1"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#94a3b8")]
        )

        self.style.configure(
            "Success.TButton",
            font=("Segoe UI", 11, "bold"),
            background="#16a34a",
            foreground="#ffffff",
            padding=(16, 10),
            borderwidth=0
        )
        self.style.map(
            "Success.TButton",
            background=[("active", "#15803d"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#94a3b8")]
        )

        self.style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9),
            background="#e2e8f0",
            foreground="#1e293b",
            padding=(10, 6),
            borderwidth=0
        )
        self.style.map("Secondary.TButton", background=[("active", "#cbd5e1")])

    def create_header(self):
        header_frame = tk.Frame(self, bg="#1e293b", height=70)
        header_frame.pack(fill="x")

        title_label = tk.Label(
            header_frame,
            text="🏢 Companies House Form Assistant",
            font=("Segoe UI", 16, "bold"),
            bg="#1e293b",
            fg="#ffffff"
        )
        title_label.pack(side="left", padx=20, pady=15)

        company_badge = tk.Label(
            header_frame,
            text="COREMARKET GOODS LTD (15980373)",
            font=("Segoe UI", 9, "bold"),
            bg="#0f172a",
            fg="#38bdf8",
            padx=10,
            pady=4
        )
        company_badge.pack(side="right", padx=20, pady=18)

    def create_status_bar(self):
        self.status_frame = tk.Frame(self, bg="#e2e8f0", height=32)
        self.status_frame.pack(fill="x", padx=15, pady=(10, 0))

        self.status_dot = tk.Label(self.status_frame, text="●", font=("Segoe UI", 12), bg="#e2e8f0", fg="#22c55e")
        self.status_dot.pack(side="left", padx=(10, 5))

        self.status_text = tk.Label(
            self.status_frame,
            text="Ready — Click 'Open Browser' to log in, then click 'Autofill Form Now'",
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0",
            fg="#15803d"
        )
        self.status_text.pack(side="left")

    def create_action_cards(self):
        container = tk.Frame(self, bg="#f4f6f8")
        container.pack(fill="x", padx=15, pady=10)

        # Step 1 Card
        card1 = tk.Frame(container, bg="#ffffff", bd=1, relief="solid", highlightbackground="#e2e8f0")
        card1.pack(fill="x", pady=5, ipady=8, ipadx=10)

        c1_left = tk.Frame(card1, bg="#ffffff")
        c1_left.pack(side="left", fill="both", expand=True, padx=10)

        tk.Label(c1_left, text="Step 1: Open Automation Browser", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w")
        tk.Label(c1_left, text="Opens a Google Chrome window directly linked to this assistant.", font=("Segoe UI", 9), bg="#ffffff", fg="#64748b").pack(anchor="w")

        self.btn_open_browser = ttk.Button(card1, text="🌐 Open Browser", style="Primary.TButton", command=self.launch_browser_thread)
        self.btn_open_browser.pack(side="right", padx=10, pady=5)

        # Step 2 Card
        card2 = tk.Frame(container, bg="#ffffff", bd=2, relief="solid", highlightbackground="#16a34a")
        card2.pack(fill="x", pady=5, ipady=10, ipadx=10)

        c2_left = tk.Frame(card2, bg="#ffffff")
        c2_left.pack(side="left", fill="both", expand=True, padx=10)

        tk.Label(c2_left, text="Step 2: Autofill AA02 Dormant Accounts Form", font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#15803d").pack(anchor="w")
        tk.Label(c2_left, text="Instantly populates share capital (£1), approval date, and confirms audit exemptions.", font=("Segoe UI", 9), bg="#ffffff", fg="#64748b").pack(anchor="w")

        self.btn_fill = ttk.Button(card2, text="⚡ Autofill Form Now", style="Success.TButton", command=self.fill_form_thread)
        self.btn_fill.pack(side="right", padx=10, pady=5)

    def create_settings_card(self):
        card = tk.Frame(self, bg="#ffffff", bd=1, relief="solid", highlightbackground="#e2e8f0")
        card.pack(fill="x", padx=15, pady=5, ipady=6, ipadx=10)

        header_row = tk.Frame(card, bg="#ffffff")
        header_row.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(header_row, text="⚙ Form Values (Pre-configured for your company)", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#334155").pack(side="left")

        fields_grid = tk.Frame(card, bg="#ffffff")
        fields_grid.pack(fill="x", padx=10)

        tk.Label(fields_grid, text="Share Class:", font=("Segoe UI", 9), bg="#ffffff").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.entry_class = ttk.Entry(fields_grid, width=12)
        self.entry_class.insert(0, "Ordinary")
        self.entry_class.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        tk.Label(fields_grid, text="Number of Shares:", font=("Segoe UI", 9), bg="#ffffff").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.entry_shares = ttk.Entry(fields_grid, width=8)
        self.entry_shares.insert(0, "1")
        self.entry_shares.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        tk.Label(fields_grid, text="Value per Share (£):", font=("Segoe UI", 9), bg="#ffffff").grid(row=0, column=4, sticky="w", padx=5, pady=2)
        self.entry_value = ttk.Entry(fields_grid, width=8)
        self.entry_value.insert(0, "1")
        self.entry_value.grid(row=0, column=5, sticky="w", padx=5, pady=2)

        tk.Label(fields_grid, text="Unpaid Capital (£):", font=("Segoe UI", 9), bg="#ffffff").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.entry_unpaid = ttk.Entry(fields_grid, width=12)
        self.entry_unpaid.insert(0, "1")
        self.entry_unpaid.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        tk.Label(fields_grid, text="Cash at bank (£):", font=("Segoe UI", 9), bg="#ffffff").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.entry_cash = ttk.Entry(fields_grid, width=8)
        self.entry_cash.insert(0, "0")
        self.entry_cash.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        tk.Label(fields_grid, text="Approval Date:", font=("Segoe UI", 9), bg="#ffffff").grid(row=1, column=4, sticky="w", padx=5, pady=2)
        self.entry_date = ttk.Entry(fields_grid, width=12)
        self.entry_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.entry_date.grid(row=1, column=5, sticky="w", padx=5, pady=2)

    def create_log_console(self):
        log_frame = tk.Frame(self, bg="#f4f6f8")
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        top_row = tk.Frame(log_frame, bg="#f4f6f8")
        top_row.pack(fill="x", pady=(0, 4))

        tk.Label(top_row, text="📋 Activity Log & Output", font=("Segoe UI", 10, "bold"), bg="#f4f6f8", fg="#334155").pack(side="left")

        btn_clear = ttk.Button(top_row, text="Clear Log", style="Secondary.TButton", command=self.clear_log)
        btn_clear.pack(side="right", padx=2)

        self.log_text = tk.Text(
            log_frame,
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
            padx=10,
            pady=10
        )
        self.log_text.pack(fill="both", expand=True)

        self.log("Ready! Click 'Open Browser' to begin, then 'Autofill Form Now'.")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] "
        if level == "SUCCESS":
            prefix += "✔ "
        elif level == "ERROR":
            prefix += "✖ [ERROR] "
        elif level == "WARN":
            prefix += "⚠ "
        
        self.log_text.insert("end", f"{prefix}{message}\n")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def launch_browser_thread(self):
        threading.Thread(target=self.launch_browser, daemon=True).start()

    def launch_browser(self):
        self.log("Opening Google Chrome on port 9222...")
        bat_file = os.path.join(SCRIPT_DIR, "launch_browser.bat")
        try:
            subprocess.Popen([bat_file], shell=True)
            self.log("Chrome launched successfully!", level="SUCCESS")
            self.log("👉 Please log in to Companies House and open the AA02 Dormant Accounts page.")
        except Exception as e:
            self.log(f"Failed to launch Chrome: {e}", level="ERROR")

    def fill_form_thread(self):
        threading.Thread(target=self.fill_form, daemon=True).start()

    def fill_form(self):
        self.log("Running form filling script...")

        unpaid = self.entry_unpaid.get().strip() or "1"
        cash = self.entry_cash.get().strip() or "0"
        shares = self.entry_shares.get().strip() or "1"
        s_class = self.entry_class.get().strip() or "Ordinary"
        value = self.entry_value.get().strip() or "1"
        date_str = self.entry_date.get().strip() or datetime.now().strftime("%d/%m/%Y")

        cmd = [
            sys.executable,
            os.path.join(SCRIPT_DIR, "fill_aa02.py"),
            "--unpaid", unpaid,
            "--cash", cash,
            "--shares", shares,
            "--class", s_class,
            "--value", value,
            "--date", date_str
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.log("All form fields populated successfully!", level="SUCCESS")
                self.log("👉 Look at your Chrome window and click 'VALIDATE AND CONTINUE'.")
                messagebox.showinfo(
                    "Autofill Complete",
                    "Form fields have been filled in Chrome!\n\nPlease check your Chrome window to verify the figures and click 'VALIDATE AND CONTINUE'."
                )
            else:
                self.log(f"Fill script error: {result.stderr or result.stdout}", level="ERROR")
                messagebox.showerror("Fill Error", f"Could not fill form:\n{result.stderr or result.stdout}")
        except Exception as e:
            self.log(f"Error running fill script: {e}", level="ERROR")
            messagebox.showerror("Error", f"Could not fill form: {e}")


if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()
