import glob
import os
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from src.constants import THEME
from src.core.security import decrypt_password, encrypt_password
from src.data.uploader import GunsmokeClient
from src.ui.styles import create_button


class UploadTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager, fonts):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.config_manager = config_manager
        self.fonts = fonts
        self.client = GunsmokeClient()
        self.setup_ui()

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="Upload to Gunsmoke.app",
            font=self.fonts.heading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(pady=(0, 20))

        # Authentication card
        auth_frame = ctk.CTkFrame(
            main_frame,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        auth_frame.pack(fill=tk.X, pady=(0, 15))

        ctk.CTkLabel(
            auth_frame,
            text="Authentication & Upload",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, padx=15, pady=(15, 10))

        upload_config = self.config_manager.get("gunsmoke_app", {})
        saved_url = upload_config.get("api_url", "https://gunsmoke.app")
        default_env = (
            "Localhost (Development)"
            if "localhost" in saved_url
            else "Gunsmoke.app (Production)"
        )

        # Environment selector (ttk.Combobox styled via Custom.TCombobox)
        env_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        env_frame.pack(fill=tk.X, padx=15, pady=5)

        ctk.CTkLabel(
            env_frame,
            text="Environment:",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            width=120,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        self.api_env_var = tk.StringVar(value=default_env)
        env_dropdown = ttk.Combobox(
            env_frame,
            textvariable=self.api_env_var,
            values=["Gunsmoke.app (Production)", "Localhost (Development)"],
            state="readonly",
            width=30,
            style="Custom.TCombobox",
        )
        env_dropdown.pack(side=tk.LEFT, padx=(0, 10))

        # Username
        user_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        user_frame.pack(fill=tk.X, padx=15, pady=5)

        ctk.CTkLabel(
            user_frame,
            text="Username:",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            width=120,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        self.username_entry = ctk.CTkEntry(user_frame, font=self.fonts.mono)
        self.username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if upload_config.get("username"):
            self.username_entry.insert(0, upload_config.get("username"))

        # Password
        pass_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        pass_frame.pack(fill=tk.X, padx=15, pady=5)

        ctk.CTkLabel(
            pass_frame,
            text="Password:",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            width=120,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        self.password_entry = ctk.CTkEntry(pass_frame, font=self.fonts.mono, show="*")
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if upload_config.get("password_encrypted"):
            decrypted = decrypt_password(upload_config.get("password_encrypted"))
            if decrypted:
                self.password_entry.insert(0, decrypted)

        # Checkboxes
        checkbox_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        checkbox_frame.pack(fill=tk.X, padx=15, pady=5)

        self.save_creds_var = tk.BooleanVar(
            value=upload_config.get("save_credentials", False)
        )
        ctk.CTkCheckBox(
            checkbox_frame,
            text="Save credentials (encrypted)",
            variable=self.save_creds_var,
            font=self.fonts.body,
            text_color=THEME["text_primary"],
        ).pack(side=tk.LEFT, padx=(120, 20))

        self.remove_missing_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            checkbox_frame,
            text="Mark commanders not in CSV as left",
            variable=self.remove_missing_var,
            font=self.fonts.body,
            text_color=THEME["text_primary"],
        ).pack(side=tk.LEFT)

        # Guild info display
        self.guild_info_label = ctk.CTkLabel(
            auth_frame,
            text="",
            text_color=THEME["text_muted"],
            fg_color="transparent",
            font=self.fonts.body,
        )
        self.guild_info_label.pack(pady=(5, 5))

        # Buttons
        buttons_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        create_button(
            buttons_frame,
            "Verify Login & Permissions",
            self.verify_credentials,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT)

        create_button(
            buttons_frame,
            "Upload Last CSV",
            self.upload_last_csv,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.RIGHT)

        ctk.CTkLabel(
            auth_frame,
            text="Make sure latest results are saved to CSV in the Capture Data tab.",
            text_color=THEME["text_muted"],
            fg_color="transparent",
            font=self.fonts.caption,
        ).pack(pady=(0, 15))

        # Status panel
        status_frame = ctk.CTkFrame(
            main_frame,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        status_frame.pack(fill=tk.BOTH, expand=True)

        ctk.CTkLabel(
            status_frame,
            text="Upload Status",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, padx=15, pady=(15, 10))

        self.upload_status_text = ctk.CTkTextbox(
            status_frame,
            height=300,
            wrap=tk.WORD,
            font=self.fonts.mono,
            fg_color=THEME["bg_canvas"],
            text_color=THEME["text_primary"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.upload_status_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.log("Ready. Configure authentication and upload your CSV.")

    def log(self, msg):
        self.upload_status_text.insert(tk.END, msg + "\n")
        self.upload_status_text.see(tk.END)

    def _update_client_env(self):
        is_prod = "Production" in self.api_env_var.get()
        self.client.set_environment(is_prod)

    def verify_credentials(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self.log("[ERROR] Please enter username and password")
            return

        self._update_client_env()
        self.log(f"[INFO] Verifying credentials for '{username}'...")

        success, msg, data = self.client.verify_credentials(username, password)

        if success:
            guild_name = data.get("guild_name", "Unknown")
            role = data.get("role", "Unknown")
            self.log(f"[SUCCESS] Authenticated as {username}")
            self.log(f"[INFO] Guild: {guild_name}, Role: {role}")

            self.guild_info_label.configure(
                text=f"Authenticated | Guild: {guild_name} | Role: {role.capitalize()}",
                text_color=THEME["success"],
            )

            if self.save_creds_var.get():
                self.save_upload_config()
                self.log("[INFO] Credentials saved (encrypted)")
        else:
            self.log(f"[ERROR] Authentication failed: {msg}")
            self.guild_info_label.configure(
                text="Authentication failed",
                text_color=THEME["danger"],
            )

    def upload_last_csv(self):
        csv_files = glob.glob("./results/*.csv")
        if not csv_files:
            self.log("[ERROR] No CSV files found in ./results/ folder")
            self.log("[INFO] Please capture and save data first (Capture Data tab)")
            return

        latest_csv = max(csv_files, key=os.path.getmtime)

        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        remove_missing = self.remove_missing_var.get()

        if not username or not password:
            self.log("[ERROR] Please enter username and password")
            return

        self._update_client_env()
        self.log(f"\n[INFO] Uploading {os.path.basename(latest_csv)}...")

        success, msg, data = self.client.upload_file(
            latest_csv, username, password, remove_missing
        )

        if success:
            self.log(f"[SUCCESS] {msg}")
            self.log(
                f"[INFO] Processed: {data.get('total', 0)}, "
                f"Success: {data.get('success', 0)}, "
                f"Skipped: {data.get('skipped', 0)}"
            )

            if data.get("removed", 0) > 0:
                self.log(f"[INFO] Removed: {data.get('removed', 0)} commander(s)")

            errors = data.get("errors", [])
            if errors:
                self.log("[WARNING] Errors encountered:")
                for error in errors[:5]:
                    self.log(f"  - {error}")
                if len(errors) > 5:
                    self.log(f"  ... and {len(errors) - 5} more")

            if self.save_creds_var.get():
                self.save_upload_config()
        else:
            self.log(f"[ERROR] Upload failed: {msg}")

    def save_upload_config(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        save_creds = self.save_creds_var.get()

        gunsmoke_app_config = self.config_manager.get("gunsmoke_app", {})
        if not isinstance(gunsmoke_app_config, dict):
            gunsmoke_app_config = {}

        gunsmoke_app_config["api_url"] = self.client.api_url
        gunsmoke_app_config["save_credentials"] = save_creds

        if save_creds and username and password:
            gunsmoke_app_config["username"] = username
            gunsmoke_app_config["password_encrypted"] = encrypt_password(password)
        else:
            gunsmoke_app_config["username"] = ""
            gunsmoke_app_config["password_encrypted"] = ""

        self.config_manager.set("gunsmoke_app", gunsmoke_app_config)
