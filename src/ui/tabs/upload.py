import tkinter as tk
from tkinter import ttk
import os
import glob
from src.constants import THEME
from src.ui.styles import create_button
from src.core.security import encrypt_password, decrypt_password
from src.data.uploader import GunsmokeClient

class UploadTab(tk.Frame):
    def __init__(self, parent, config_manager):
        super().__init__(parent, bg=THEME['bg_dark'])
        self.config_manager = config_manager
        self.client = GunsmokeClient()
        self.setup_ui()
        
    def setup_ui(self):
        # Main container with padding
        main_frame = tk.Frame(self, bg=THEME['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="Upload to Gunsmoke.app",
                              font=("Segoe UI", 16, "bold"), bg=THEME['bg_dark'],
                              fg=THEME['text_primary'])
        title_label.pack(pady=(0, 20))
        
        # Authentication Card
        auth_frame = tk.Frame(main_frame, bg=THEME['bg_light'])
        auth_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(auth_frame, text="Authentication & Upload", font=("Segoe UI", 12, "bold"),
                bg=THEME['bg_light'], fg=THEME['text_primary']).pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # API Environment selector
        env_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        env_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(env_frame, text="Environment:", bg=THEME['bg_light'],
                fg=THEME['text_secondary'], font=("Segoe UI", 10), width=15, anchor=tk.W).pack(side=tk.LEFT)
        
        # Determine initial selection based on config or default
        upload_config = self.config_manager.get('gunsmoke_app', {})
        saved_url = upload_config.get('api_url', 'https://gunsmoke.app')
        default_env = 'Localhost (Development)' if 'localhost' in saved_url else 'Gunsmoke.app (Production)'
        
        self.api_env_var = tk.StringVar(value=default_env)
        env_dropdown = ttk.Combobox(env_frame, textvariable=self.api_env_var,
                                   values=['Gunsmoke.app (Production)', 'Localhost (Development)'],
                                   state='readonly', width=30)
        env_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        
        # Username
        user_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        user_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(user_frame, text="Username:", bg=THEME['bg_light'],
                fg=THEME['text_secondary'], font=("Segoe UI", 10), width=15, anchor=tk.W).pack(side=tk.LEFT)
        
        self.username_entry = tk.Entry(user_frame, bg=THEME['bg_medium'],
                                       fg=THEME['text_primary'], font=("Consolas", 10),
                                       insertbackground=THEME['accent_cyan'])
        self.username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        if upload_config.get('username'):
            self.username_entry.insert(0, upload_config.get('username'))
        
        # Password
        pass_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        pass_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(pass_frame, text="Password:", bg=THEME['bg_light'],
                fg=THEME['text_secondary'], font=("Segoe UI", 10), width=15, anchor=tk.W).pack(side=tk.LEFT)
        
        self.password_entry = tk.Entry(pass_frame, bg=THEME['bg_medium'], show="*",
                                       fg=THEME['text_primary'], font=("Consolas", 10),
                                       insertbackground=THEME['accent_cyan'])
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        if upload_config.get('password_encrypted'):
            decrypted = decrypt_password(upload_config.get('password_encrypted'))
            if decrypted:
                self.password_entry.insert(0, decrypted)
        
        # Checkboxes
        checkbox_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        checkbox_frame.pack(fill=tk.X, padx=15, pady=5)
        
        self.save_creds_var = tk.BooleanVar(value=upload_config.get('save_credentials', False))
        tk.Checkbutton(checkbox_frame, text="Save credentials (encrypted)",
                      variable=self.save_creds_var,
                      bg=THEME['bg_light'], fg=THEME['text_secondary'],
                      selectcolor=THEME['bg_dark'],
                      activebackground=THEME['bg_light'],
                      activeforeground=THEME['accent_cyan'],
                      font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(115, 20))
        
        self.remove_missing_var = tk.BooleanVar(value=False)
        tk.Checkbutton(checkbox_frame, text="Mark commanders not in CSV as left",
                      variable=self.remove_missing_var,
                      bg=THEME['bg_light'], fg=THEME['text_secondary'],
                      selectcolor=THEME['bg_dark'],
                      activebackground=THEME['bg_light'],
                      activeforeground=THEME['accent_cyan'],
                      font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        # Guild info display
        self.guild_info_label = tk.Label(auth_frame, text="", bg=THEME['bg_light'],
                                         fg=THEME['text_secondary'], font=("Segoe UI", 9))
        self.guild_info_label.pack(pady=(5, 5))
        
        # Buttons
        buttons_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        buttons_frame.pack(fill=tk.X, padx=15, pady=(5, 10))
        
        left_btn_frame = tk.Frame(buttons_frame, bg=THEME['bg_light'])
        left_btn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        create_button(left_btn_frame, "Verify Login & Permissions", 
                      self.verify_credentials, THEME['accent_cyan']).pack(side=tk.LEFT)
        
        right_btn_frame = tk.Frame(buttons_frame, bg=THEME['bg_light'])
        right_btn_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        create_button(right_btn_frame, "🚀 Upload Last CSV",
                      self.upload_last_csv, THEME['success']).pack(side=tk.RIGHT)
        
        # Info text
        info_frame = tk.Frame(auth_frame, bg=THEME['bg_light'])
        info_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        tk.Label(info_frame, text="ℹ Make sure latest results are saved to CSV file in Capture Data tab",
                bg=THEME['bg_light'], fg=THEME['text_muted'], 
                font=("Segoe UI", 9, "italic")).pack()
        
        # Status area
        status_frame = tk.Frame(main_frame, bg=THEME['bg_medium'])
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(status_frame, text="Upload Status", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_medium'], fg=THEME['text_primary']).pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        status_scroll = tk.Scrollbar(status_frame)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15))
        
        self.upload_status_text = tk.Text(status_frame, height=24, bg=THEME['bg_light'],
                                          fg=THEME['text_secondary'], font=("Consolas", 9),
                                          wrap=tk.WORD, yscrollcommand=status_scroll.set)
        self.upload_status_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        status_scroll.config(command=self.upload_status_text.yview)
        
        self.log("Ready. Configure authentication and upload your CSV.")

    def log(self, msg):
        self.upload_status_text.insert(tk.END, msg + "\n")
        self.upload_status_text.see(tk.END)

    def _update_client_env(self):
        is_prod = 'Production' in self.api_env_var.get()
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
            guild_name = data.get('guild_name', 'Unknown')
            role = data.get('role', 'Unknown')
            self.log(f"[SUCCESS] ✓ Authenticated as {username}")
            self.log(f"[INFO] Guild: {guild_name}, Role: {role}")
            
            self.guild_info_label.config(
                text=f"✓ Authenticated | Guild: {guild_name} | Role: {role.capitalize()}",
                fg=THEME['success']
            )
            
            if self.save_creds_var.get():
                self.save_upload_config()
                self.log("[INFO] Credentials saved (encrypted)")
        else:
            self.log(f"[ERROR] ✗ Authentication failed: {msg}")
            self.guild_info_label.config(text="✗ Authentication failed", fg=THEME['danger'])

    def upload_last_csv(self):
        # Find most recent CSV
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
        
        success, msg, data = self.client.upload_file(latest_csv, username, password, remove_missing)
        
        if success:
            self.log(f"[SUCCESS] ✓ {msg}")
            self.log(f"[INFO] Processed: {data.get('total', 0)}, Success: {data.get('success', 0)}, Skipped: {data.get('skipped', 0)}")
            
            if data.get('removed', 0) > 0:
                self.log(f"[INFO] Removed: {data.get('removed', 0)} commander(s)")
                
            errors = data.get('errors', [])
            if errors:
                self.log("[WARNING] Errors encountered:")
                for error in errors[:5]:
                    self.log(f"  - {error}")
                if len(errors) > 5:
                    self.log(f"  ... and {len(errors) - 5} more")
            
            if self.save_creds_var.get():
                self.save_upload_config()
        else:
            self.log(f"[ERROR] ✗ Upload failed: {msg}")

    def save_upload_config(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        save_creds = self.save_creds_var.get()
        
        gunsmoke_app_config = self.config_manager.get('gunsmoke_app', {})
        if not isinstance(gunsmoke_app_config, dict):
             gunsmoke_app_config = {}

        gunsmoke_app_config['api_url'] = self.client.api_url
        gunsmoke_app_config['save_credentials'] = save_creds
        
        if save_creds and username and password:
            gunsmoke_app_config['username'] = username
            gunsmoke_app_config['password_encrypted'] = encrypt_password(password)
        else:
            gunsmoke_app_config['username'] = ''
            gunsmoke_app_config['password_encrypted'] = ''
            
        self.config_manager.set('gunsmoke_app', gunsmoke_app_config)
