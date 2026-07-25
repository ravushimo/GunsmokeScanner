"""Gunsmoke leaderboard capture tab (PySide6)."""

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.scanner import safe_grab
from src.data.models import PlayerScore
from src.data.storage import save_to_csv
from src.ui.qt_util import call_soon
from src.ui.styles import (
    configure_stretch_table,
    create_button,
    stat_strip,
    toolbar_frame,
)

COLUMNS = ("Season", "IGN (Nickname)", "Single High Score", "Total Score")
FIELD_BY_COLUMN = ("season", "ign", "topscore", "totalscore")


def _make_label(text: str, font, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


class CaptureTab(QWidget):
    def __init__(self, parent, config_manager, ocr_processor, season_manager, fonts):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.season_num = season_manager.season_num
        self.season_manager = season_manager
        self.fonts = fonts

        # Internal data is dicts so we can edit cells in-place without
        # reconstructing PlayerScore instances on every keystroke.
        self.captured_data = []
        self.capture_count = 0
        self.is_capturing = False

        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 12)
        outer.setSpacing(8)

        ctrl_frame = toolbar_frame()
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 10, 12, 10)
        ctrl_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(
            create_button(
                None,
                "Capture (F9)",
                self.start_capture_thread,
                variant="primary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Set Season",
                self.set_season_dialog,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None, "Save to CSV", self.save_data, variant="featured", font=self.fonts.ui
            )
        )
        btn_row.addWidget(
            create_button(
                None, "Clear All", self.clear_all, variant="danger", font=self.fonts.ui
            )
        )
        btn_row.addStretch(1)
        ctrl_layout.addLayout(btn_row)
        outer.addWidget(ctrl_frame)

        stats_frame = stat_strip()
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        self.stats_label = _make_label(
            "Total Players: 0 | Captures: 0", self.fonts.body_medium, THEME["text_strong"]
        )
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(self.stats_label)
        outer.addWidget(stats_frame)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        configure_stretch_table(
            self.table, stretch=1, min_widths=[80, 250, 120, 120]
        )
        self.table.itemChanged.connect(self.on_item_changed)
        outer.addWidget(self.table, stretch=1)

        self.status_label = _make_label(
            "Ready. Press F9 to capture.", self.fonts.caption, THEME["text_muted"]
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(28)
        outer.addWidget(self.status_label)

    def set_season_dialog(self):
        current = self.season_num if self.season_num else 1
        new_season, ok = QInputDialog.getInt(
            self, "Override Season", "Enter season number:", current, 1, 999
        )
        if ok and new_season:
            self.season_num = new_season
            if hasattr(self.season_manager, "set_manual_season"):
                self.season_manager.set_manual_season(new_season)
            self.status_label.setText(f"Season set to {new_season}")

    def start_capture_thread(self, _checked=None):
        if self.is_capturing:
            return

        if self.season_num is None:
            QMessageBox.warning(
                self, "Season Not Set", "Please set the season number first!"
            )
            return

        self.is_capturing = True
        self.status_label.setText("Capturing... (Processing)")

        threading.Thread(target=self._capture_logic, daemon=True).start()

    def _capture_logic(self):
        try:
            batch = []
            rows = self.config_manager.get("rows", [])

            for row_config in rows:
                nick_img = safe_grab(row_config["nickname"])
                single_img = safe_grab(row_config["single_high"])
                total_img = safe_grab(row_config["total_score"])

                if nick_img is None:
                    continue

                nickname = self.ocr_processor.extract_text(
                    nick_img, is_number=False, config=self.config_manager.config
                )
                single_text = self.ocr_processor.extract_text(
                    single_img, is_number=True, config=self.config_manager.config
                )
                total_text = self.ocr_processor.extract_text(
                    total_img, is_number=True, config=self.config_manager.config
                )

                nickname = self.ocr_processor.clean_nickname(nickname)
                single_score = self.ocr_processor.clean_number(
                    single_text, is_single_score=True
                )
                total_score = self.ocr_processor.clean_number(total_text)

                min_nick_len = self.config_manager.get("validation", {}).get(
                    "min_nickname_length", 2
                )

                if len(nickname) >= min_nick_len:
                    batch.append(
                        PlayerScore(
                            season=self.season_num,
                            ign=nickname,
                            topscore=single_score,
                            totalscore=total_score,
                        )
                    )

            call_soon(lambda: self._on_capture_complete(batch))

        except Exception as e:
            print(f"Capture error: {e}")
            err = str(e)
            call_soon(lambda msg=err: self.status_label.setText(f"Error: {msg}"))
            self.is_capturing = False

    def _on_capture_complete(self, batch):
        self.capture_count += 1

        if batch and self.captured_data:
            recent = [p["ign"] for p in self.captured_data[-20:]]
            batch = [p for p in batch if p.ign not in recent]

        for p in batch:
            self.captured_data.append(p.to_dict())

        self.refresh_table()

        self.stats_label.setText(
            f"Total Players: {len(self.captured_data)} | Captures: {self.capture_count}"
        )
        self.status_label.setText(f"Captured {len(batch)} new players.")
        self.is_capturing = False

    def refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.captured_data))
        for row, player in enumerate(self.captured_data):
            values = (
                str(player["season"]),
                player["ign"],
                f"{player['topscore']:,}",
                f"{player['totalscore']:,}",
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col in (2, 3):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)

    def on_item_changed(self, item: QTableWidgetItem):
        """Native QTableWidget in-place editing replaces the old Tk cell-overlay hack."""
        row = item.row()
        col = item.column()
        if row >= len(self.captured_data):
            return

        field = FIELD_BY_COLUMN[col]
        new_val = item.text()
        try:
            if field in ("season", "topscore", "totalscore"):
                val = int(new_val.replace(",", ""))
            else:
                val = new_val
            self.captured_data[row][field] = val
        except ValueError:
            pass
        self.refresh_table()

    def clear_all(self):
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Delete all captured data?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.captured_data = []
            self.refresh_table()
            self.stats_label.setText("Total Players: 0 | Captures: 0")

    def save_data(self):
        if not self.captured_data:
            return

        dialog = QDialog(self.window())
        dialog.setWindowTitle("Save CSV - Optional Guild Rank")
        dialog.setFixedSize(420, 200)
        dialog.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(8)

        title = _make_label(
            "Add Guild Rank (Optional)", self.fonts.subheading, THEME["text_strong"]
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = _make_label(
            "Enter rank to include it in the file:", self.fonts.body, THEME["text_muted"]
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        entry = QLineEdit()
        entry.setFont(self.fonts.mono)
        entry.setFixedWidth(120)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry_row = QHBoxLayout()
        entry_row.addStretch(1)
        entry_row.addWidget(entry)
        entry_row.addStretch(1)
        layout.addLayout(entry_row)

        result_rank = [None]

        def on_update():
            rank = entry.text().strip()
            if rank:
                result_rank[0] = rank
            dialog.accept()

        def on_skip():
            dialog.reject()

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(
            create_button(
                None, "Update Rank (Enter)", on_update, variant="primary", font=self.fonts.ui
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "No, Just Save (Esc)",
                on_skip,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        entry.returnPressed.connect(on_update)
        entry.setFocus()

        dialog.exec()

        models = [PlayerScore(**d) for d in self.captured_data]
        filename = save_to_csv(models, self.season_num, guild_rank=result_rank[0])
        QMessageBox.information(self, "Saved", f"Data saved to {filename}")
