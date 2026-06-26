"""
Rec. 709 Finder desktop GUI.

PySide6 front-end for rec709_finder.py. Choose or drop a folder, video file,
After Effects project, or Premiere project; scan on a background thread; and
review non-Rec. 709 media first. Rec. 709 passes are hidden in a collapsible
section by default.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QRectF, QSettings, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec709_finder as finder


ICON_TEXT = "\U0001f3a8"


def resource_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def app_icon():
    icon_path = resource_path("icon.ico")
    if icon_path.is_file():
        return QIcon(str(icon_path))

    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    pad, radius = 14, 58
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(pad, pad, size - 2 * pad, size - 2 * pad), radius, radius)
    p.setPen(QPen(QColor("#dce4ee"), 3))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(pad + 2, pad + 2, size - 2 * pad - 4, size - 2 * pad - 4), radius, radius)

    font = QFont("Segoe UI Emoji")
    font.setPixelSize(144)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, ICON_TEXT)
    p.end()
    return QIcon(pm)


THEMES = {
    "light": {
        "window_top": "#dbe7f3",
        "window_bottom": "#eef2f6",
        "card": "#ffffff",
        "card_soft": "#f4f6f9",
        "text": "#1c2430",
        "text_muted": "#6b7585",
        "accent": "#1c2430",
        "accent_text": "#ffffff",
        "border": "#e3e8ef",
        "pass": "#1f9d57",
        "pass_bg": "#e7f6ee",
        "fail": "#d33a3a",
        "fail_bg": "#fbe9e9",
        "warn": "#b7791f",
        "warn_bg": "#fff4d6",
        "info": "#8a93a3",
        "info_bg": "#eef1f5",
        "ring_track": "#e3e8ef",
        "ring": "#d33a3a",
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
        "pass": "#5cf2a8",
        "pass_bg": "#124129",
        "fail": "#ff8c8c",
        "fail_bg": "#4c242a",
        "warn": "#fbd38d",
        "warn_bg": "#4a3415",
        "info": "#9aa6bd",
        "info_bg": "#222f4d",
        "ring_track": "#2a3858",
        "ring": "#ff8c8c",
    },
}


def build_stylesheet(t):
    return f"""
    QWidget {{
        color: {t['text']};
        font-family: 'Segoe UI', '.AppleSystemUIFont', 'Helvetica Neue', Arial, sans-serif;
        font-size: 14px;
    }}
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


class RingWidget(QWidget):
    def __init__(self, theme):
        super().__init__()
        self._value = 0.0
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

        arc = QPen(QColor(self._theme["ring"]), 10)
        arc.setCapStyle(Qt.RoundCap)
        p.setPen(arc)
        p.drawArc(rect, 90 * 16, -int(360 * 16 * self._value))

        p.setPen(QColor(self._theme["text"]))
        f = QFont(self.font())
        f.setPointSize(18)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, f"{int(round(self._value * 100))}%")
        p.end()


class ClickableFrame(QFrame):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class Badge(QLabel):
    def __init__(self, text, fg, bg):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border-radius: 10px;"
            f"padding: 3px 12px; font-weight: 700; font-size: 12px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


def soft_wrap_text(text):
    value = str(text)
    for char in ("\\", "/", "_", "-", "."):
        value = value.replace(char, char + "\u200b")
    return value


class ResultCard(QFrame):
    def __init__(self, result, theme, expanded=False):
        super().__init__()
        self.setObjectName("SoftCard")
        self._theme = theme
        self._expanded = False
        self.result = result

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        status = result["status"]
        fg, bg, label = self._badge_style(status)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.display_name = Path(result["path"]).name or result["path"]
        self.toggle_btn = QPushButton(self.display_name)
        self.toggle_btn.setObjectName("FileHeader")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setToolTip(result["path"])
        self.toggle_btn.clicked.connect(self._toggle)
        self.toggle_btn.setMinimumWidth(0)
        self.toggle_btn.setMaximumWidth(420)
        self.toggle_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        meta = QLabel(self._metadata_line())
        meta.setObjectName("Subtitle")
        meta.setMinimumWidth(110)
        meta.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        open_btn = QToolButton()
        open_btn.setText("Reveal")
        open_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        open_btn.setObjectName("Ghost")
        open_btn.setAttribute(Qt.WA_StyledBackground, True)
        open_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setToolTip("Reveal file in Explorer/Finder")
        open_btn.setEnabled(Path(result["path"]).is_file())
        open_btn.setMinimumWidth(82)
        open_btn.setMaximumWidth(104)
        open_btn.clicked.connect(self._open_file)
        header.addWidget(self.toggle_btn, 1)
        header.addWidget(meta)
        header.addWidget(open_btn)
        header.addWidget(Badge(label, fg, bg))
        outer.addLayout(header)

        self.details = QWidget()
        grid = QGridLayout(self.details)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        rows = self._detail_rows()
        for row, (name, value) in enumerate(rows):
            grid.addWidget(self._cell(name, bold=True), row, 0)
            grid.addWidget(self._cell(value), row, 1)
        grid.setColumnStretch(1, 1)
        self.details.setVisible(False)
        outer.addWidget(self.details)

        if expanded:
            self._toggle()
        else:
            self._set_header_text()

    def _badge_style(self, status):
        if status == "non_rec709":
            return self._theme["fail"], self._theme["fail_bg"], "NON-REC. 709"
        if status == "unknown":
            return self._theme["warn"], self._theme["warn_bg"], "UNKNOWN"
        if status in {"missing", "probe_error"}:
            return self._theme["fail"], self._theme["fail_bg"], "ERROR"
        return self._theme["pass"], self._theme["pass_bg"], "REC. 709"

    def _metadata_line(self):
        if not self.result.get("exists", True):
            return "Missing"
        if self.result["status"] == "probe_error":
            return "Probe error"
        size = ""
        if self.result.get("width") and self.result.get("height"):
            size = f"{self.result['width']}x{self.result['height']}"
        codec = self.result.get("codec_name", "")
        return " / ".join(part for part in (codec, size) if part)

    def _detail_rows(self):
        result = self.result
        rows = [
            ("Source", f"{result.get('source_type', '')} - {result.get('source', '')}"),
            ("Path", result.get("path", "")),
        ]
        if result.get("original_path"):
            rows.append(("Project reference", result["original_path"]))
        if result["status"] == "probe_error":
            rows.append(("Error", result.get("error", "")))
            return rows
        if result["status"] == "missing":
            rows.append(("Status", "Missing media"))
            return rows

        rows.extend(
            [
                ("Codec", result.get("codec_name", "")),
                ("Size", f"{result.get('width', '')}x{result.get('height', '')}"),
                ("Pixel format", result.get("pix_fmt", "")),
                ("Color primaries", result.get("color_primaries", "") or "unknown"),
                ("Color transfer", result.get("color_transfer", "") or "unknown"),
                ("Color space/matrix", result.get("color_space", "") or "unknown"),
                ("Color range", result.get("color_range", "") or "unknown"),
            ]
        )
        if result["status"] in {"non_rec709", "unknown"}:
            rows.append(("Finding", finder.format_finding_summary(result)))
        return rows

    def _cell(self, text, bold=False):
        lab = QLabel(soft_wrap_text(text))
        lab.setWordWrap(True)
        lab.setMinimumWidth(0)
        lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        if bold:
            lab.setStyleSheet("font-weight: 600;")
        else:
            lab.setStyleSheet(f"color: {self._theme['text_muted']};")
        return lab

    def _set_header_text(self):
        arrow = "v  " if self._expanded else ">  "
        self.toggle_btn.setText(arrow + self.display_name)

    def _toggle(self):
        self._expanded = not self._expanded
        self.details.setVisible(self._expanded)
        self._set_header_text()

    def _open_file(self):
        reveal_file(self.result["path"])


def reveal_file(path):
    media_path = Path(path)
    if not media_path.is_file():
        return

    if os.name == "nt":
        normalized = os.path.normpath(os.path.abspath(str(media_path)))
        subprocess.Popen(f'explorer.exe /select,"{normalized}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(media_path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(media_path.parent)))


class CollapsibleSection(QFrame):
    def __init__(self, title, theme, expanded=False):
        super().__init__()
        self.setObjectName("Card")
        self._expanded = expanded
        self._title = title
        self._theme = theme

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(12)

        self.header_btn = QPushButton()
        self.header_btn.setObjectName("FileHeader")
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle)
        outer.addWidget(self.header_btn)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        self.body.setVisible(expanded)
        outer.addWidget(self.body)
        self._sync_header()

    def add_widget(self, widget):
        self.body_layout.addWidget(widget)

    def toggle(self):
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)
        self._sync_header()

    def _sync_header(self):
        arrow = "v" if self._expanded else ">"
        self.header_btn.setText(f"{arrow}  {self._title}")


class ScanWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, target, include_unknown=False, max_depth=None):
        super().__init__()
        self.target = Path(target)
        self.include_unknown = include_unknown
        self.max_depth = max_depth

    def run(self):
        try:
            ffprobe = finder.find_ffprobe()
            if not ffprobe:
                raise RuntimeError(
                    "ffprobe was not found. Install FFmpeg and make sure ffprobe is on PATH."
                )
            references = finder.collect_references([self.target], max_depth=self.max_depth)
            if not references:
                self.finished_ok.emit([])
                return
            self.log.emit(f"Found {len(references)} video reference(s).")
            results = finder.scan_references(
                references,
                ffprobe,
                include_unknown=self.include_unknown,
                verbose=True,
                log=lambda message: self.log.emit(str(message)),
                progress=lambda done, total, current: self.progress.emit(done, total, current),
            )
            self.finished_ok.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        if app is not None and sys.platform != "darwin":
            app.setStyle("Fusion")
        self.setWindowTitle("Rec. 709 Finder")
        self.setWindowIcon(app_icon())
        self.resize(980, 760)
        self.setMinimumSize(980, 760)

        self.settings = QSettings("indie.io", "Rec. 709 Finder")
        saved = self.settings.value("theme", "light")
        self.theme_name = saved if saved in THEMES else "light"
        self.theme = THEMES[self.theme_name]
        self.selected_target = None
        self.worker = None
        self.last_results = None
        self._mode = "empty"

        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Rec. 709 Finder")
        title.setObjectName("Title")
        subtitle = QLabel("Find video references encoded outside standard Rec. 709")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.theme_btn = QToolButton()
        self.theme_btn.setText("Dark")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.theme_btn.setObjectName("IconToggle")
        self.theme_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.theme_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_btn, alignment=Qt.AlignTop)
        root.addLayout(header)

        self.source_card = QFrame()
        self.source_card.setObjectName("Card")
        self.source_card.setMinimumHeight(118)
        self.source_card.setMaximumHeight(132)
        sc = QVBoxLayout(self.source_card)
        sc.setContentsMargins(22, 20, 22, 20)
        sc.setSpacing(14)
        sc_label = QLabel("SOURCE")
        sc_label.setObjectName("SectionLabel")
        sc.addWidget(sc_label)

        row = QHBoxLayout()
        row.setSpacing(12)
        source_text = QVBoxLayout()
        source_text.setContentsMargins(0, 0, 0, 0)
        source_text.setSpacing(4)
        self.path_label = QLabel("Drop a folder, video, After Effects project, or Premiere project here.")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setWordWrap(True)
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.path_detail = QLabel("")
        self.path_detail.setObjectName("Subtitle")
        self.path_detail.setWordWrap(True)
        self.path_detail.setMaximumHeight(42)
        self.path_detail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.path_detail.setVisible(False)
        source_text.addWidget(self.path_label)
        source_text.addWidget(self.path_detail)
        row.addLayout(source_text, 1)

        choose_file = QToolButton()
        choose_file.setText("Choose file")
        choose_file.setToolButtonStyle(Qt.ToolButtonTextOnly)
        choose_file.setObjectName("Ghost")
        choose_file.setAttribute(Qt.WA_StyledBackground, True)
        choose_file.setAttribute(Qt.WA_MacShowFocusRect, False)
        choose_file.setCursor(Qt.PointingHandCursor)
        choose_file.clicked.connect(self._choose_file)
        row.addWidget(choose_file)

        choose_folder = QToolButton()
        choose_folder.setText("Choose folder")
        choose_folder.setToolButtonStyle(Qt.ToolButtonTextOnly)
        choose_folder.setObjectName("Ghost")
        choose_folder.setAttribute(Qt.WA_StyledBackground, True)
        choose_folder.setAttribute(Qt.WA_MacShowFocusRect, False)
        choose_folder.setCursor(Qt.PointingHandCursor)
        choose_folder.clicked.connect(self._choose_folder)
        row.addWidget(choose_folder)

        self.run_btn = QToolButton()
        self.run_btn.setText("Run scan")
        self.run_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.run_btn.setObjectName("Primary")
        self.run_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.run_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_scan)
        row.addWidget(self.run_btn)
        sc.addLayout(row)
        root.addWidget(self.source_card)

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
        self.summary_sub = QLabel("Run a scan to find color-space issues.")
        self.summary_sub.setObjectName("Subtitle")
        counts_box.addStretch(1)
        counts_box.addWidget(self.summary_title)
        counts_box.addWidget(self.summary_sub)
        counts_box.addStretch(1)
        sum_layout.addLayout(counts_box, 1)

        self.export_btn = QToolButton()
        self.export_btn.setText("Export report")
        self.export_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.export_btn.setObjectName("Ghost")
        self.export_btn.setAttribute(Qt.WA_StyledBackground, True)
        self.export_btn.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setVisible(False)
        sum_layout.addWidget(self.export_btn, alignment=Qt.AlignTop)
        self.summary_card.setVisible(False)
        root.addWidget(self.summary_card)

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

        self.log_bar = ClickableFrame()
        self.log_bar.setObjectName("LogBar")
        bar_row = QHBoxLayout(self.log_bar)
        bar_row.setContentsMargins(16, 11, 16, 11)
        bar_row.setSpacing(8)
        log_title = QLabel("Progress log")
        log_title.setObjectName("LogTitle")
        self.log_status = QLabel("- Idle")
        self.log_status.setObjectName("Subtitle")
        self.log_hint = QLabel("Show  ^")
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
        self.log_box.setPlaceholderText("Progress log will appear here...")
        self.log_box.setVisible(False)
        root.addWidget(self.log_box)

        self._show_empty()

    def _toggle_log(self):
        show = not self.log_box.isVisible()
        self.log_box.setVisible(show)
        self.log_hint.setText("Hide  v" if show else "Show  ^")

    def _apply_theme(self):
        self.theme = THEMES[self.theme_name]
        self.setStyleSheet(build_stylesheet(self.theme))
        self.theme_btn.setText("Light" if self.theme_name == "dark" else "Dark")
        self.ring.set_theme(self.theme)
        if self._mode == "results" and self.last_results is not None:
            self._render_results(self.last_results)
        elif self._mode == "ready":
            self._show_ready()

    def _toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.settings.setValue("theme", self.theme_name)
        self._apply_theme()

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select media or project",
            "",
            "Media and project files (*.aep *.aepx *.prproj *.mp4 *.mov *.mxf *.m4v *.avi *.mkv *.webm);;All files (*.*)",
        )
        if path:
            self._set_target(path)

    def _choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Select folder to scan")
        if directory:
            self._set_target(directory)

    def _set_target(self, target):
        self.selected_target = target
        path = Path(target)
        self.path_label.setText("Selected source")
        self.path_detail.setText(str(path))
        self.path_detail.setToolTip(str(path))
        self.path_detail.setVisible(True)
        self.run_btn.setEnabled(True)
        self._show_ready()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._set_target(path)
                break

    def _run_scan(self):
        if not self.selected_target:
            return
        if not finder.find_ffprobe():
            QMessageBox.critical(
                self,
                "FFprobe not found",
                "Could not find ffprobe. Install FFmpeg and make sure it is on your PATH.",
            )
            return

        self.log_box.clear()
        self.log_status.setText("- Running...")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.worker = ScanWorker(self.selected_target, include_unknown=False)
        self.worker.log.connect(self._on_log)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_log(self, message):
        self.log_box.appendPlainText(message)

    def _on_progress(self, done, total, current):
        if total:
            self.run_btn.setText(f"Running... {done}/{total}")

    def _on_failed(self, message):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run scan")
        self.log_status.setText("- Failed")
        QMessageBox.critical(self, "Scan failed", message)

    def _on_finished(self, results):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run scan")
        self.last_results = results
        self._render_results(results)

        counts = self._counts(results)
        self.log_status.setText(
            f"- Done - {counts.get('non_rec709', 0)} non-Rec. 709, "
            f"{counts.get('rec709', 0)} hidden Rec. 709"
        )

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _show_empty(self):
        self._mode = "empty"
        self.summary_card.setVisible(False)
        self._clear_results()

        zone = ClickableFrame()
        zone.setObjectName("DropZone")
        zone.clicked.connect(self._choose_file)
        layout = QVBoxLayout(zone)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addStretch(1)

        icon = QLabel(ICON_TEXT)
        icon.setObjectName("IconBox")
        icon.setFixedSize(76, 76)
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon, alignment=Qt.AlignHCenter)

        title = QLabel("No source selected")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        sub = QLabel("Choose or drop a folder, video, After Effects project, or Premiere project.")
        sub.setObjectName("Subtitle")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setMaximumWidth(460)
        sub.setMinimumHeight(44)
        sub.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        layout.addWidget(sub, 0, Qt.AlignHCenter)
        layout.addStretch(1)

        self.results_layout.addWidget(zone, 1)
        self.log_status.setText("- Idle")

    def _show_ready(self):
        if not self.selected_target:
            return
        self._mode = "ready"
        self.summary_card.setVisible(False)
        self._clear_results()

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Ready to scan")
        title.setObjectName("QueuedTitle")
        hint = QLabel("Click Run scan to check media color metadata.")
        hint.setObjectName("Subtitle")
        layout.addWidget(title)
        layout.addWidget(hint)

        row = QHBoxLayout()
        path = QLabel(str(self.selected_target))
        path.setWordWrap(True)
        chip = QLabel("Queued")
        chip.setObjectName("Chip")
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        row.addWidget(path, 1)
        row.addWidget(chip)
        layout.addLayout(row)

        self.results_layout.addWidget(card)
        self.results_layout.addStretch(1)
        self.log_status.setText("- Idle")

    def _render_results(self, results):
        self._mode = "results"
        self._clear_results()
        counts = self._counts(results)

        total = len(results)
        finding_statuses = {"non_rec709", "unknown"}
        error_statuses = {"missing", "probe_error"}
        findings = [result for result in results if result["status"] in finding_statuses]
        errors = [result for result in results if result["status"] in error_statuses]
        passes = [result for result in results if result["status"] == "rec709"]
        non_rec709 = counts.get("non_rec709", 0)

        self.summary_card.setVisible(True)
        self.export_btn.setVisible(bool(results))
        rate = (non_rec709 / total) if total else 0.0
        self.ring.set_value(rate)
        self.summary_title.setText(f"{non_rec709} non-Rec. 709 found")
        hidden_parts = [f"{len(passes)} Rec. 709"]
        if errors:
            hidden_parts.append(f"{len(errors)} video error(s)")
        self.summary_sub.setText(
            f"{total} reference(s) scanned - {', '.join(hidden_parts)} hidden by default"
        )

        if not results:
            self._add_empty_results("No video references found.")
            return

        if findings:
            for result in sorted(findings, key=lambda item: (item["status"], item["path"].lower())):
                self.results_layout.addWidget(ResultCard(result, self.theme, expanded=True))
        else:
            self._add_empty_results("No non-Rec. 709 media found.")

        if errors:
            section = CollapsibleSection(f"Hidden video errors ({len(errors)})", self.theme)
            for result in sorted(errors, key=lambda item: (item["status"], item["path"].lower())):
                section.add_widget(ResultCard(result, self.theme, expanded=False))
            self.results_layout.addWidget(section)

        if passes:
            section = CollapsibleSection(f"Hidden Rec. 709 videos ({len(passes)})", self.theme)
            for result in sorted(passes, key=lambda item: item["path"].lower()):
                section.add_widget(ResultCard(result, self.theme, expanded=False))
            self.results_layout.addWidget(section)

        self.results_layout.addStretch(1)

    def _add_empty_results(self, text):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel(text)
        title.setObjectName("QueuedTitle")
        layout.addWidget(title)
        self.results_layout.addWidget(card)

    def _export_report(self):
        if self.last_results is None or not self.selected_target:
            return
        start = Path(self.selected_target)
        default_dir = start if start.is_dir() else start.parent
        out, _ = QFileDialog.getSaveFileName(
            self,
            "Save Rec. 709 report",
            str(default_dir / "Rec709_Scan_Report.md"),
            "Markdown files (*.md);;All files (*.*)",
        )
        if not out:
            return
        try:
            finder.write_markdown_report(self.last_results, Path(out), compact=True)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Report exported", f"Saved report:\n{out}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def _counts(self, results):
        counts = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return counts


def _selftest(args):
    target = Path(args[0]) if args else Path.cwd()
    out = Path(args[1]) if len(args) > 1 else target / "rec709_gui_selftest.json"
    report = {
        "target": str(target),
        "ffprobe": finder.find_ffprobe(),
        "ok": False,
    }
    try:
        references = finder.collect_references([target], max_depth=None)
        results = finder.scan_references(
            references,
            report["ffprobe"],
            verbose=False,
        ) if report["ffprobe"] else []
        counts = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        report.update(
            {
                "ok": bool(report["ffprobe"]),
                "references": len(results),
                "counts": counts,
            }
        )
    except Exception as exc:
        report["error"] = str(exc)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return _selftest(sys.argv[2:])

    app = QApplication(sys.argv)
    app.setApplicationName("Rec. 709 Finder")
    app.setOrganizationName("indie.io")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
