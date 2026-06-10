"""
Technical QC — desktop GUI.

A cross-platform (Windows + macOS) PySide6 front-end for technical_qc.py.
Pick a folder of delivered videos, run the QC pass on a background thread, and
review pass/fail results per file and per parameter without touching a terminal.

Run:
    python qc_gui.py

The visual language is inspired by the glassmorphic Figma mockups: soft gradient
backgrounds, rounded frosted cards, pill buttons, and a light/dark theme toggle.
"""

import json
import os
import sys

from PySide6.QtCore import Qt, QThread, Signal, QSize, QRectF, QSettings, QUrl
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QDesktopServices, QIcon, QPixmap, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolButton, QFrame, QScrollArea, QFileDialog, QPlainTextEdit, QSizePolicy,
    QGridLayout, QMessageBox,
)

# Make sure we can import the core module whether launched from this folder or
# elsewhere (e.g. a packaged build).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import technical_qc as qc


# --------------------------------------------------------------------------- #
# App icon — green rounded square + white checkmark, drawn at runtime so the
# window/taskbar icon works even when running from source (no asset file).
# --------------------------------------------------------------------------- #

def app_icon():
    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    pad, radius = 14, 58
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1f9d57"))
    p.drawRoundedRect(QRectF(pad, pad, size - 2 * pad, size - 2 * pad), radius, radius)

    pen = QPen(QColor("white"), 26)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(size * 0.30, size * 0.53)
    path.lineTo(size * 0.44, size * 0.68)
    path.lineTo(size * 0.72, size * 0.35)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #

THEMES = {
    "light": {
        "window_top": "#dbe7f3",
        "window_bottom": "#eef2f6",
        "card": "#ffffff",
        "card_soft": "#f4f6f9",
        "text": "#1c2430",
        "text_muted": "#6b7585",
        "accent": "#1c2430",          # dark pill buttons, like the mockups
        "accent_text": "#ffffff",
        "border": "#e3e8ef",
        "pass": "#1f9d57",
        "pass_bg": "#e7f6ee",
        "fail": "#d33a3a",
        "fail_bg": "#fbe9e9",
        "info": "#8a93a3",
        "info_bg": "#eef1f5",
        "ring_track": "#e3e8ef",
        "ring": "#1f9d57",            # pass-rate ring — green
    },
    "dark": {
        "window_top": "#0d1626",
        "window_bottom": "#16203a",
        "card": "#1b2742",
        "card_soft": "#222f4d",
        "text": "#eef2f8",
        "text_muted": "#9aa6bd",
        "accent": "#ffffff",
        "accent_text": "#10182a",
        "border": "#2a3858",
        "pass": "#5cf2a8",            # brighter for contrast on dark
        "pass_bg": "#124129",
        "fail": "#ff8c8c",            # brighter for contrast on dark
        "fail_bg": "#4c242a",
        "info": "#9aa6bd",
        "info_bg": "#222f4d",
        "ring_track": "#2a3858",
        "ring": "#3ddc92",            # pass-rate ring — green (brighter)
    },
}


def build_stylesheet(t):
    """
    Return a QSS string for the given theme palette dict.

    Designed for the Fusion style (forced at startup) so it renders identically
    on Windows and macOS. Two rules are load-bearing:
      * `QLabel { background: transparent; }` stops labels filling their
        background (the pale "bands" behind text under the native style).
      * Only cards/controls declare a background; everything else is
        transparent so the #Root gradient shows through cleanly.
    """
    return f"""
    QWidget {{
        color: {t['text']};
        font-family: 'Segoe UI', '.AppleSystemUIFont', 'Helvetica Neue', Arial, sans-serif;
        font-size: 14px;
    }}
    /* Default every container to transparent; cards opt back in below. */
    QLabel, QFrame, QWidget#Root, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QWidget#Root {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {t['window_top']}, stop:1 {t['window_bottom']});
    }}
    QFrame#Card {{
        background-color: {t['card']};
        border-radius: 20px;
        border: 1px solid {t['border']};
    }}
    QFrame#SoftCard {{
        background-color: {t['card_soft']};
        border-radius: 16px;
        border: 1px solid {t['border']};
    }}
    QLabel#Title {{
        font-size: 26px;
        font-weight: 700;
    }}
    QLabel#Subtitle {{
        color: {t['text_muted']};
        font-size: 14px;
    }}
    QLabel#SectionLabel {{
        color: {t['text_muted']};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QLabel#PathLabel {{
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#SummaryTitle {{
        font-size: 18px;
        font-weight: 700;
    }}
    QLabel#LogTitle {{
        font-size: 13px;
        font-weight: 600;
    }}
    /* QToolButton respects border-radius better than QPushButton on macOS */
    QPushButton, QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 20px;
    }}
    QPushButton#Primary, QToolButton#Primary {{
        background-color: {t['accent']};
        color: {t['accent_text']};
        border: 1px solid {t['accent']};
        border-style: solid;
        border-radius: 22px;
        padding: 12px 26px;
        font-weight: 600;
        font-size: 14px;
    }}
    QPushButton#Primary:disabled, QToolButton#Primary:disabled {{
        background-color: {t['border']};
        color: {t['text_muted']};
        border: 1px solid {t['border']};
        border-style: solid;
    }}
    QPushButton#Ghost, QToolButton#Ghost {{
        background-color: transparent;
        color: {t['text']};
        border: 1px solid {t['border']};
        border-style: solid;
        border-radius: 20px;
        padding: 12px 20px;
        font-weight: 600;
    }}
    QPushButton#Ghost:hover, QToolButton#Ghost:hover {{
        background-color: {t['card_soft']};
    }}
    QPushButton#IconToggle, QToolButton#IconToggle {{
        background-color: {t['card_soft']};
        border: 1px solid {t['border']};
        border-style: solid;
        border-radius: 18px;
        padding: 8px 14px;
        font-weight: 600;
    }}
    QPushButton#FileHeader {{
        background-color: transparent;
        border: none;
        text-align: left;
        padding: 4px 2px;
        font-size: 15px;
        font-weight: 600;
    }}
    QPlainTextEdit {{
        background-color: {t['card_soft']};
        border: 1px solid {t['border']};
        border-radius: 14px;
        padding: 10px;
        color: {t['text_muted']};
        font-family: 'Cascadia Mono', 'SF Mono', 'Consolas', monospace;
        font-size: 12px;
    }}
    QFrame#LogBar {{
        background-color: {t['card_soft']};
        border: 1px solid {t['border']};
        border-radius: 14px;
    }}
    QFrame#LogBar:hover {{
        border: 1px solid {t['text_muted']};
    }}
    /* Match the Source Folder section: all log-bar text at 12px. */
    QFrame#LogBar QLabel {{
        font-size: 12px;
    }}
    QFrame#DropZone {{
        background-color: {t['card_soft']};
        border: 2px dashed {t['border']};
        border-radius: 20px;
    }}
    QLabel#IconBox {{
        background-color: {t['card']};
        border: 1px solid {t['border']};
        border-radius: 20px;
        font-size: 34px;
        color: {t['text_muted']};
    }}
    QLabel#EmptyTitle {{
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#QueuedTitle {{
        font-size: 17px;
        font-weight: 700;
    }}
    QLabel#Chip {{
        color: {t['text_muted']};
        background-color: {t['card_soft']};
        border: 1px solid {t['border']};
        border-radius: 9px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['border']}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """


# --------------------------------------------------------------------------- #
# Small custom widgets
# --------------------------------------------------------------------------- #

class RingWidget(QWidget):
    """A circular progress ring showing the pass rate (like the Figma 35% ring)."""

    def __init__(self, theme):
        super().__init__()
        self._value = 0.0          # 0..1
        self._theme = theme
        self.setFixedSize(120, 120)

    def set_theme(self, theme):
        self._theme = theme
        self.update()

    def set_value(self, value):
        self._value = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(10, 10, self.width() - 20, self.height() - 20)

        track = QPen(QColor(self._theme["ring_track"]), 10)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.drawArc(rect, 0, 360 * 16)

        # Pass-rate ring — green (matching the Figma design).
        arc = QPen(QColor(self._theme["ring"]), 10)
        arc.setCapStyle(Qt.RoundCap)
        p.setPen(arc)
        # Start at 12 o'clock, go clockwise.
        p.drawArc(rect, 90 * 16, -int(360 * 16 * self._value))

        p.setPen(QColor(self._theme["text"]))
        f = QFont(self.font())
        f.setPointSize(18)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, f"{int(round(self._value * 100))}%")
        p.end()


class ClickableFrame(QFrame):
    """A QFrame that emits `clicked` on mouse press (used for the log bar / drop-zone)."""

    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class Badge(QLabel):
    """A small rounded status pill (PASS / FAIL / INFO)."""

    def __init__(self, text, fg, bg):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border-radius: 10px;"
            f"padding: 3px 12px; font-weight: 700; font-size: 12px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


class FileResultCard(QFrame):
    """A collapsible card for one file: header with status, expandable details."""

    def __init__(self, filename, items, theme, error=None):
        super().__init__()
        self.setObjectName("SoftCard")
        self._theme = theme
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        is_pass = error is None and all(i["status"] != "FAIL" for i in items)
        if error:
            fg, bg, label = theme["fail"], theme["fail_bg"], "ERROR"
        elif is_pass:
            fg, bg, label = theme["pass"], theme["pass_bg"], "PASS"
        else:
            fg, bg, label = theme["fail"], theme["fail_bg"], "FAIL"

        header = QHBoxLayout()
        header.setSpacing(10)
        self.toggle_btn = QPushButton(("▸  " if not error else "•  ") + filename)
        self.toggle_btn.setObjectName("FileHeader")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)

        badge = Badge(label, fg, bg)

        # Per-file count summary, e.g. "9/11 checks".
        if not error:
            passed = sum(1 for i in items if i["status"] == "PASS")
            total = sum(1 for i in items if i["status"] != "INFO")
            count = QLabel(f"{passed}/{total} checks")
            count.setObjectName("Subtitle")
        else:
            count = QLabel("")

        header.addWidget(self.toggle_btn, 1)
        header.addWidget(count)
        header.addWidget(badge)
        outer.addLayout(header)

        # Details (hidden until expanded).
        self.details = QWidget()
        d_layout = QVBoxLayout(self.details)
        d_layout.setContentsMargins(4, 4, 4, 4)
        d_layout.setSpacing(0)

        if error:
            err = QLabel(error)
            err.setWordWrap(True)
            err.setStyleSheet(f"color: {theme['fail']};")
            d_layout.addWidget(err)
        else:
            grid = QGridLayout()
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(6)
            heads = ["Parameter", "Expected", "Actual", ""]
            for col, h in enumerate(heads):
                lab = QLabel(h)
                lab.setObjectName("SectionLabel")
                grid.addWidget(lab, 0, col)
            for row, item in enumerate(items, start=1):
                grid.addWidget(self._cell(item["param"], bold=True), row, 0)
                grid.addWidget(self._cell(str(item["expected"])), row, 1)
                grid.addWidget(self._cell(str(item["actual"])), row, 2)
                grid.addWidget(self._status_mark(item["status"]), row, 3)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            d_layout.addLayout(grid)

        self.details.setVisible(False)
        outer.addWidget(self.details)

        # Auto-expand anything that isn't a clean pass — that's what you want to see.
        if not is_pass:
            self._toggle()

    def _cell(self, text, bold=False):
        lab = QLabel(text)
        lab.setWordWrap(True)
        if bold:
            lab.setStyleSheet("font-weight: 600;")
        else:
            lab.setStyleSheet(f"color: {self._theme['text_muted']};")
        return lab

    def _status_mark(self, status):
        if status == "PASS":
            return Badge("✓", self._theme["pass"], self._theme["pass_bg"])
        if status == "FAIL":
            return Badge("✕", self._theme["fail"], self._theme["fail_bg"])
        return Badge("i", self._theme["info"], self._theme["info_bg"])

    def _toggle(self):
        self._expanded = not self._expanded
        self.details.setVisible(self._expanded)
        text = self.toggle_btn.text()
        arrow = "▾  " if self._expanded else "▸  "
        if text[:3] in ("▸  ", "▾  "):
            self.toggle_btn.setText(arrow + text[3:])


# --------------------------------------------------------------------------- #
# Worker thread
# --------------------------------------------------------------------------- #

class QcWorker(QThread):
    """Runs the QC pass off the UI thread."""

    log = Signal(str)
    progress = Signal(int, int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, target_dir):
        super().__init__()
        self.target_dir = target_dir

    def run(self):
        try:
            result = qc.run_qc(
                self.target_dir,
                log=lambda m: self.log.emit(str(m)),
                progress=lambda d, tot, cur: self.progress.emit(d, tot, cur or ""),
                write_files=False,   # the GUI shows everything; export is on demand
            )
            self.finished_ok.emit(result)
        except Exception as e:  # surface any failure cleanly in the UI
            self.failed.emit(str(e))


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Force Fusion on Windows so the QSS renders properly
        # (the native windows11 style fights stylesheet backgrounds/borders).
        # On macOS, Fusion interferes with QPushButton border-radius, so use default.
        app = QApplication.instance()
        if app is not None and sys.platform != "darwin":
            app.setStyle("Fusion")
        self.setWindowTitle("Technical QC")
        self.setWindowIcon(app_icon())
        self.resize(960, 760)
        # Restore the last-used theme (defaults to light on first run).
        self.settings = QSettings("indie.io", "Technical QC")
        saved = self.settings.value("theme", "light")
        self.theme_name = saved if saved in THEMES else "light"
        self.theme = THEMES[self.theme_name]
        self.selected_dir = None
        self.worker = None
        self.last_result = None
        self._mode = "empty"          # empty | ready | results

        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme()

    # ---- UI construction -------------------------------------------------- #

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Technical QC")
        title.setObjectName("Title")
        subtitle = QLabel("Check delivered videos against their naming-convention specs")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.theme_btn = QToolButton()
        self.theme_btn.setText("☾  Dark")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.theme_btn.setObjectName("IconToggle")
        self.theme_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.theme_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_btn, alignment=Qt.AlignTop)
        root.addLayout(header)

        # Source card (folder picker)
        self.source_card = QFrame()
        self.source_card.setObjectName("Card")
        sc = QVBoxLayout(self.source_card)
        sc.setContentsMargins(22, 20, 22, 20)
        sc.setSpacing(14)
        sc_label = QLabel("SOURCE FOLDER")
        sc_label.setObjectName("SectionLabel")
        sc.addWidget(sc_label)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.path_label = QLabel("Drop a folder here, or choose one →")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setWordWrap(True)
        row.addWidget(self.path_label, 1)
        choose = QToolButton()
        choose.setText("Choose folder")
        choose.setToolButtonStyle(Qt.ToolButtonTextOnly)
        choose.setObjectName("Ghost")
        choose.setAttribute(Qt.WA_StyledBackground, True)
        choose.setAttribute(Qt.WA_MacShowFocusRect, False)
        choose.setCursor(Qt.PointingHandCursor)
        choose.clicked.connect(self._choose_folder)
        row.addWidget(choose)
        self.run_btn = QToolButton()
        self.run_btn.setText("Run QC")
        self.run_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.run_btn.setObjectName("Primary")
        self.run_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.run_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_qc)
        row.addWidget(self.run_btn)
        sc.addLayout(row)
        root.addWidget(self.source_card)

        # Summary card (ring + counts), hidden until first run
        self.summary_card = QFrame()
        self.summary_card.setObjectName("Card")
        sum_layout = QHBoxLayout(self.summary_card)
        sum_layout.setContentsMargins(22, 18, 22, 18)
        sum_layout.setSpacing(24)
        self.ring = RingWidget(self.theme)
        sum_layout.addWidget(self.ring)

        counts_box = QVBoxLayout()
        counts_box.setSpacing(4)
        self.summary_title = QLabel("No results yet")
        self.summary_title.setObjectName("SummaryTitle")
        self.summary_sub = QLabel("Run a QC pass to see pass / fail results.")
        self.summary_sub.setObjectName("Subtitle")
        counts_box.addStretch(1)
        counts_box.addWidget(self.summary_title)
        counts_box.addWidget(self.summary_sub)
        counts_box.addStretch(1)
        sum_layout.addLayout(counts_box, 1)

        self.open_report_btn = QToolButton()
        self.open_report_btn.setText("Export report")
        self.open_report_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.open_report_btn.setObjectName("Ghost")
        self.open_report_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.open_report_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.open_report_btn.setCursor(Qt.PointingHandCursor)
        self.open_report_btn.setToolTip(
            "Write specifications.md and QC_Report.md into the source folder"
        )
        self.open_report_btn.clicked.connect(self._export_report)
        self.open_report_btn.setVisible(False)
        sum_layout.addWidget(self.open_report_btn, alignment=Qt.AlignTop)
        self.summary_card.setVisible(False)
        root.addWidget(self.summary_card)

        # Results scroll area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 6, 0)
        self.results_layout.setSpacing(12)
        self.results_layout.addStretch(1)
        self.results_scroll.setWidget(self.results_container)
        root.addWidget(self.results_scroll, 1)

        # Collapsible log: a slim bar (always visible) + the box (hidden by default)
        self.log_bar = ClickableFrame()
        self.log_bar.setObjectName("LogBar")
        bar_row = QHBoxLayout(self.log_bar)
        bar_row.setContentsMargins(16, 11, 16, 11)
        bar_row.setSpacing(8)
        log_title = QLabel("Progress log")
        log_title.setObjectName("LogTitle")
        self.log_status = QLabel("· Idle")
        self.log_status.setObjectName("Subtitle")
        self.log_hint = QLabel("Show  ▴")
        self.log_hint.setObjectName("Subtitle")
        bar_row.addWidget(log_title)
        bar_row.addWidget(self.log_status)
        bar_row.addStretch(1)
        bar_row.addWidget(self.log_hint)
        self.log_bar.clicked.connect(self._toggle_log)
        root.addWidget(self.log_bar)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(150)
        self.log_box.setPlaceholderText("Progress log will appear here…")
        self.log_box.setVisible(False)  # hidden by default; open via the bar
        root.addWidget(self.log_box)

        # Start on the empty state (no folder chosen yet).
        self._show_empty()

    def _toggle_log(self):
        show = not self.log_box.isVisible()
        self.log_box.setVisible(show)
        self.log_hint.setText("Hide  ▾" if show else "Show  ▴")

    # ---- Theme ------------------------------------------------------------ #

    def _apply_theme(self):
        self.theme = THEMES[self.theme_name]
        t = self.theme
        # Single stylesheet on the window; the #Root gradient lives inside it.
        self.setStyleSheet(build_stylesheet(t))
        self.theme_btn.setText("☀  Light" if self.theme_name == "dark" else "☾  Dark")
        self.ring.set_theme(t)
        # Rebuild the current view so non-QSS colours (badges) follow the theme.
        if self._mode == "results" and self.last_result is not None:
            self._render_results(self.last_result)
        elif self._mode == "ready":
            self._show_ready()
        # Empty state is fully QSS-driven, so it updates automatically.

    def _toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.settings.setValue("theme", self.theme_name)  # remember for next launch
        self._apply_theme()

    # ---- Folder selection ------------------------------------------------- #

    def _choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Select folder of videos")
        if directory:
            self._set_folder(directory)

    def _set_folder(self, directory):
        self.selected_dir = directory
        count = len(qc.list_video_files(directory)) if os.path.isdir(directory) else 0
        self.path_label.setText(f"{directory}\n{count} video file(s) found")
        self.run_btn.setEnabled(count > 0)
        # Preview the queued files (Ready state) before running.
        if count > 0:
            self._show_ready()
        else:
            self._show_empty()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self._set_folder(path)
                break
            if os.path.isfile(path):
                self._set_folder(os.path.dirname(path))
                break

    # ---- Run -------------------------------------------------------------- #

    def _run_qc(self):
        if not self.selected_dir:
            return

        # Pre-flight: tools present?
        tools = qc.check_tools()
        missing = [k for k, v in tools.items() if not v]
        if missing:
            QMessageBox.critical(
                self, "FFmpeg not found",
                f"Could not find: {', '.join(missing)}.\n\n"
                + ("Install with Homebrew:  brew install ffmpeg"
                   if sys.platform == "darwin"
                   else "Install FFmpeg and make sure it is on your PATH."),
            )
            return

        self.log_box.clear()
        self.log_status.setText("· Running…")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running…")

        self.worker = QcWorker(self.selected_dir)
        self.worker.log.connect(self._on_log)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_log(self, message):
        self.log_box.appendPlainText(message)

    def _on_progress(self, done, total, current):
        if total:
            self.run_btn.setText(f"Running… {done}/{total}")

    def _on_failed(self, message):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run QC")
        self.log_status.setText("· Failed")
        QMessageBox.critical(self, "QC failed", message)

    def _on_finished(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run QC")
        self.last_result = result
        self._render_results(result)

        all_results = result["all_results"]
        total = len(all_results)
        passed = sum(
            1 for items in all_results.values()
            if isinstance(items, list) and all(i["status"] != "FAIL" for i in items)
        )
        self.log_status.setText(f"· Done — {passed} passed, {total - passed} failed")

    # ---- Results rendering ------------------------------------------------ #

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)   # detach now so it stops painting immediately
                w.deleteLater()

    # ---- Empty / Ready placeholder states --------------------------------- #

    def _show_empty(self):
        """No folder chosen yet — show a dashed drop-zone."""
        self._mode = "empty"
        self.summary_card.setVisible(False)
        self._clear_results()

        zone = ClickableFrame()
        zone.setObjectName("DropZone")
        zone.clicked.connect(self._choose_folder)
        v = QVBoxLayout(zone)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(14)
        v.addStretch(1)

        icon = QLabel("+")
        icon.setObjectName("IconBox")
        icon.setFixedSize(76, 76)
        icon.setAlignment(Qt.AlignCenter)
        v.addWidget(icon, alignment=Qt.AlignHCenter)

        title = QLabel("No folder selected")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title, alignment=Qt.AlignHCenter)

        sub = QLabel("Choose or drop a folder of .mp4 / .mov files to start a QC pass.")
        sub.setObjectName("Subtitle")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub, alignment=Qt.AlignHCenter)
        v.addStretch(1)

        self.results_layout.addWidget(zone, 1)
        self.log_status.setText("· Idle")

    def _show_ready(self):
        """Folder chosen, not run yet — preview the queued files."""
        if not self.selected_dir:
            return
        self._mode = "ready"
        self.summary_card.setVisible(False)
        self._clear_results()

        files = qc.list_video_files(self.selected_dir)
        card = QFrame()
        card.setObjectName("Card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(22, 20, 22, 20)
        cv.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel(f"{len(files)} file(s) queued for QC")
        title.setObjectName("QueuedTitle")
        hint = QLabel("Click Run QC to begin")
        hint.setObjectName("Subtitle")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(hint)
        cv.addLayout(head)

        for name in files:
            r = QHBoxLayout()
            r.setSpacing(12)
            fn = QLabel(name.replace(os.sep, "/"))  # show subfolder, fwd slashes
            fn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            chip = QLabel("Queued")
            chip.setObjectName("Chip")
            chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            r.addWidget(fn, 1)
            r.addWidget(chip)
            cv.addLayout(r)

        self.results_layout.addWidget(card)
        self.results_layout.addStretch(1)
        self.log_status.setText("· Idle")

    def _render_results(self, result):
        self._mode = "results"
        self._clear_results()
        all_results = result["all_results"]

        total = len(all_results)
        passed = 0
        for items in all_results.values():
            if isinstance(items, list) and all(i["status"] != "FAIL" for i in items):
                passed += 1
        failed = total - passed

        # Summary
        self.summary_card.setVisible(True)
        self.open_report_btn.setVisible(True)
        rate = (passed / total) if total else 0.0
        self.ring.set_value(rate)
        self.summary_title.setText(f"{passed} passed · {failed} failed")
        skipped = result.get("skipped", [])
        sub = f"{total} file(s) checked"
        if skipped:
            sub += f" · {len(skipped)} skipped (naming convention)"
        self.summary_sub.setText(sub)

        # Per-file cards (failures first)
        def sort_key(kv):
            name, items = kv
            if isinstance(items, dict):  # error
                return (0, name)
            is_pass = all(i["status"] != "FAIL" for i in items)
            return (2 if is_pass else 1, name)

        for name, items in sorted(all_results.items(), key=sort_key):
            display = name.replace(os.sep, "/")  # show subfolder, fwd slashes
            if isinstance(items, dict) and "error" in items:
                card = FileResultCard(display, [], self.theme, error=items["error"])
            else:
                card = FileResultCard(display, items, self.theme)
            self.results_layout.addWidget(card)

        # Skipped files note
        for name in skipped:
            note = QLabel(f"⤫  {name.replace(os.sep, '/')} — skipped (does not match naming convention)")
            note.setObjectName("Subtitle")
            self.results_layout.addWidget(note)

        # Keep cards top-aligned; the scroll area handles long lists.
        self.results_layout.addStretch(1)

    def _export_report(self):
        """Write the Markdown reports on demand (via technical_qc) and open them."""
        if not self.last_result or not self.selected_dir:
            return
        try:
            spec_path, report_path = qc.write_reports(
                self.selected_dir,
                self.last_result["spec_content"],
                self.last_result["report_content"],
            )
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(
            self, "Report exported",
            f"Saved into:\n{self.selected_dir}\n\n• specifications.md\n• QC_Report.md",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))


def _selftest(args):
    """
    Headless diagnostic: resolve ffmpeg/ffprobe, run QC on a folder, and write a
    JSON summary — no GUI. Useful for verifying a packaged build (incl. that its
    bundled FFmpeg works).

        Technical QC.exe --selftest <folder> [<output.json>]
    """
    folder = args[0] if args else os.getcwd()
    out = args[1] if len(args) > 1 else os.path.join(folder, "selftest.json")

    tools = qc.check_tools()
    report = {
        "frozen": bool(getattr(sys, "frozen", False)),
        "meipass": getattr(sys, "_MEIPASS", None),
        "ffmpeg": tools.get("ffmpeg"),
        "ffprobe": tools.get("ffprobe"),
        "folder": folder,
    }
    try:
        result = qc.run_qc(folder, log=lambda *_: None, write_files=False)
        all_results = result["all_results"]
        total = len(all_results)
        passed = sum(
            1 for items in all_results.values()
            if isinstance(items, list) and all(i["status"] != "FAIL" for i in items)
        )
        # Did the loudness step (which requires a working ffmpeg) actually run?
        loudness_ok = any(
            isinstance(items, list)
            and any(i["param"] == "Loudness" and i["actual"] not in ("Error", None)
                    for i in items)
            for items in all_results.values()
        )
        report.update({
            "ok": True, "files_checked": total, "passed": passed,
            "failed": total - passed, "skipped": len(result.get("skipped", [])),
            "loudness_measured": loudness_ok,
        })
    except Exception as e:
        report.update({"ok": False, "error": str(e)})

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return _selftest(sys.argv[2:])

    app = QApplication(sys.argv)
    app.setApplicationName("Technical QC")
    app.setOrganizationName("indie.io")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
