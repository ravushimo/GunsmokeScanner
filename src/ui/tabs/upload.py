"""Gunsmoke.app upload tab (PySide6)."""

import glob
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.security import decrypt_password, encrypt_password
from src.data.uploader import GunsmokeClient
from src.ui.styles import create_button, section_frame


def _make_label(text: str, font, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


class UploadTab(QWidget):
    def __init__(self, parent, config_manager, fonts):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.config_manager = config_manager
        self.fonts = fonts
        self.client = GunsmokeClient()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = _make_label(
            "Upload to Gunsmoke.app", self.fonts.heading, THEME["text_strong"]
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Authentication section
        auth_frame = section_frame()
        auth_layout = QVBoxLayout(auth_frame)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        auth_layout.setSpacing(8)

        auth_layout.addWidget(
            _make_label(
                "Authentication & Upload", self.fonts.subheading, THEME["text_strong"]
            )
        )

        upload_config = self.config_manager.get("gunsmoke_app", {})
        saved_url = upload_config.get("api_url", "https://gunsmoke.app")
        default_env = (
            "Localhost (Development)"
            if "localhost" in saved_url
            else "Gunsmoke.app (Production)"
        )

        # Environment selector
        env_row = QHBoxLayout()
        env_label = _make_label("Environment:", self.fonts.body, THEME["text_muted"])
        env_label.setFixedWidth(120)
        env_row.addWidget(env_label)
        self.api_env_combo = QComboBox()
        self.api_env_combo.addItems(
            ["Gunsmoke.app (Production)", "Localhost (Development)"]
        )
        self.api_env_combo.setCurrentText(default_env)
        env_row.addWidget(self.api_env_combo, 1)
        auth_layout.addLayout(env_row)

        # Username
        user_row = QHBoxLayout()
        user_label = _make_label("Username:", self.fonts.body, THEME["text_muted"])
        user_label.setFixedWidth(120)
        user_row.addWidget(user_label)
        self.username_entry = QLineEdit()
        self.username_entry.setFont(self.fonts.mono)
        if upload_config.get("username"):
            self.username_entry.setText(upload_config.get("username"))
        user_row.addWidget(self.username_entry, 1)
        auth_layout.addLayout(user_row)

        # Password
        pass_row = QHBoxLayout()
        pass_label = _make_label("Password:", self.fonts.body, THEME["text_muted"])
        pass_label.setFixedWidth(120)
        pass_row.addWidget(pass_label)
        self.password_entry = QLineEdit()
        self.password_entry.setFont(self.fonts.mono)
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        if upload_config.get("password_encrypted"):
            decrypted = decrypt_password(upload_config.get("password_encrypted"))
            if decrypted:
                self.password_entry.setText(decrypted)
        pass_row.addWidget(self.password_entry, 1)
        auth_layout.addLayout(pass_row)

        # Checkboxes
        checkbox_row = QHBoxLayout()
        checkbox_row.addSpacing(120)
        self.save_creds_check = QCheckBox("Save credentials (encrypted)")
        self.save_creds_check.setFont(self.fonts.body)
        self.save_creds_check.setChecked(upload_config.get("save_credentials", False))
        checkbox_row.addWidget(self.save_creds_check)
        checkbox_row.addSpacing(20)
        self.remove_missing_check = QCheckBox("Mark commanders not in CSV as left")
        self.remove_missing_check.setFont(self.fonts.body)
        checkbox_row.addWidget(self.remove_missing_check)
        checkbox_row.addStretch(1)
        auth_layout.addLayout(checkbox_row)

        # Guild info display
        self.guild_info_label = _make_label("", self.fonts.body, THEME["text_muted"])
        self.guild_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auth_layout.addWidget(self.guild_info_label)

        # Buttons
        buttons_row = QHBoxLayout()
        buttons_row.addWidget(
            create_button(
                None,
                "Verify Login & Permissions",
                self.verify_credentials,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        buttons_row.addStretch(1)
        buttons_row.addWidget(
            create_button(
                None,
                "Upload Last CSV",
                self.upload_last_csv,
                variant="primary",
                font=self.fonts.ui,
            )
        )
        auth_layout.addLayout(buttons_row)

        note = _make_label(
            "Make sure latest results are saved to CSV in the Capture Data tab.",
            self.fonts.caption,
            THEME["text_muted"],
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auth_layout.addWidget(note)

        main_layout.addWidget(auth_frame)

        # Status section
        status_frame = section_frame()
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)

        status_layout.addWidget(
            _make_label("Upload Status", self.fonts.subheading, THEME["text_strong"])
        )

        self.upload_status_text = QPlainTextEdit()
        self.upload_status_text.setReadOnly(True)
        self.upload_status_text.setFont(self.fonts.mono)
        self.upload_status_text.setMinimumHeight(300)
        status_layout.addWidget(self.upload_status_text)

        main_layout.addWidget(status_frame, 1)

        self.log("Ready. Configure authentication and upload your CSV.")

    def log(self, msg):
        self.upload_status_text.appendPlainText(msg)

    def _update_client_env(self):
        is_prod = "Production" in self.api_env_combo.currentText()
        self.client.set_environment(is_prod)

    def verify_credentials(self):
        username = self.username_entry.text().strip()
        password = self.password_entry.text()

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

            self.guild_info_label.setText(
                f"Authenticated | Guild: {guild_name} | Role: {role.capitalize()}"
            )
            self.guild_info_label.setStyleSheet(
                f"color: {THEME['success']}; background: transparent;"
            )

            if self.save_creds_check.isChecked():
                self.save_upload_config()
                self.log("[INFO] Credentials saved (encrypted)")
        else:
            self.log(f"[ERROR] Authentication failed: {msg}")
            self.guild_info_label.setText("Authentication failed")
            self.guild_info_label.setStyleSheet(
                f"color: {THEME['danger']}; background: transparent;"
            )

    def upload_last_csv(self):
        csv_files = glob.glob("./results/*.csv")
        if not csv_files:
            self.log("[ERROR] No CSV files found in ./results/ folder")
            self.log("[INFO] Please capture and save data first (Capture Data tab)")
            return

        latest_csv = max(csv_files, key=os.path.getmtime)

        username = self.username_entry.text().strip()
        password = self.password_entry.text()
        remove_missing = self.remove_missing_check.isChecked()

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

            if self.save_creds_check.isChecked():
                self.save_upload_config()
        else:
            self.log(f"[ERROR] Upload failed: {msg}")

    def save_upload_config(self):
        username = self.username_entry.text().strip()
        password = self.password_entry.text()
        save_creds = self.save_creds_check.isChecked()

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
