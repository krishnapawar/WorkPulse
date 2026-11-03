"""
WorkPulse LAN Team Chat System
------------------------------
Zero-configuration peer-to-peer chat for teams on the same Wi-Fi or Local Area Network.
Features:
  - Automatic UDP broadcast & unicast peer discovery (no cloud server needed)
  - Real-time instant messaging across local subnet
  - Peer-to-peer high-speed LAN file sharing (any file size, any format)
  - Desktop system notifications (Linux notify-send / macOS / Windows) & In-App Toasts
  - Instant 'Share Today's Tasks' work update integration
  - Live colleague presence & customizable status (Available, Focus Mode, Lunch, etc.)
  - Enterprise manual IP connect fallback (for Wi-Fi APs with client isolation)
  - Persistent local chat history (SQLite with WAL mode) & unread notification badges
  - Modern, responsive desktop UI with crisp, high-DPI legible typography
"""

import os
import sys
import json
import time
import uuid
import socket
import select
import math
try:
    import sqlite3
    SQLITE_AVAILABLE = True
except (ImportError, Exception):
    sqlite3 = None
    SQLITE_AVAILABLE = False
import datetime
import threading
import collections
import subprocess
import urllib.request
import urllib.parse
import http.server
import re
import html
try:
    from storage_config import (
        is_android, get_storage_path, acquire_android_multicast_lock,
        release_android_multicast_lock, get_android_network_info,
        show_android_notification, DummyMessageBox, DummyFileDialog
    )
except Exception:
    def is_android(): return False
    def get_storage_path(fn): return fn
    def acquire_android_multicast_lock(): return None
    def release_android_multicast_lock(): pass
    def get_android_network_info(): return None, []
    def show_android_notification(t, m): return False
    class DummyMessageBox:
        @staticmethod
        def showerror(title="", message="", **kwargs): print(f"[{title}] {message}")
        @staticmethod
        def showinfo(title="", message="", **kwargs): print(f"[{title}] {message}")
        @staticmethod
        def showwarning(title="", message="", **kwargs): print(f"[{title}] {message}")
        @staticmethod
        def askyesno(title="", message="", **kwargs): return True
        @staticmethod
        def askokcancel(title="", message="", **kwargs): return True
    class DummyFileDialog:
        @staticmethod
        def askopenfilename(**kwargs): return ""
        @staticmethod
        def asksaveasfilename(**kwargs): return ""
        @staticmethod
        def askdirectory(**kwargs): return ""
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import tkinter.font as tkfont
    TK_AVAILABLE = True
except (ImportError, Exception):
    class DummyTk:
        class Toplevel: pass
        class Frame: pass
        class Tk: pass
        class Canvas: pass
        class Entry: pass
        class Text: pass
        class Label: pass
        class Button: pass
    tk = DummyTk()
    ttk = None
    messagebox = DummyMessageBox()
    filedialog = DummyFileDialog()
    tkfont = None
    TK_AVAILABLE = False
import shutil
import tempfile
import webbrowser
import mimetypes

# Default port for WorkPulse LAN Chat
DEFAULT_LAN_PORT = 45454
CHAT_DB_FILE = get_storage_path("chat_history.db")
LEGACY_JSON_FILE = get_storage_path("chat_history.json")
MAX_HISTORY_ITEMS = 500
BEACON_INTERVAL = 3.0  # seconds between heartbeat broadcasts
PEER_TIMEOUT = 10.0    # seconds before marking peer as offline

AVATAR_PALETTE = [
    "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#d97706",
    "#059669", "#0891b2", "#4f46e5", "#0284c7", "#16a34a"
]

STATUS_CHOICES = [
    ("🟢 Available", "Available", "🟢"),
    ("🟡 Focus Mode", "Focus Mode", "🟡"),
    ("🍱 Lunch Break", "Lunch Break", "🍱"),
    ("☕ Tea / Coffee Break", "Tea Break", "☕"),
    ("🔴 In a Meeting", "In Meeting", "🔴"),
    ("🌴 On Leave", "On Leave", "🌴"),
    ("⏳ Stepped Away", "Stepped Away", "⏳")
]


# ==============================================================================
# Modern Typography & System Font Engine
# ==============================================================================

_CACHED_FONT_FAMILY = None

def get_font_family():
    """
    Detects the best available modern sans-serif font family on the current OS.
    Prioritizes Roboto / DejaVu Sans on Linux, Segoe UI on Windows, and Helvetica on Mac.
    """
    global _CACHED_FONT_FAMILY
    if _CACHED_FONT_FAMILY is None:
        try:
            avail = set(tkfont.families())
            candidates = [
                "Roboto",         # Modern Linux / Android
                "DejaVu Sans",    # Linux standard
                "Noto Sans",      # Linux / Cross-platform
                "Ubuntu",         # Ubuntu Linux
                "Segoe UI",       # Windows standard
                "Helvetica Neue", # macOS standard
                "Arial",          # Universal
                "sans-serif"
            ]
            for c in candidates:
                if c in avail:
                    _CACHED_FONT_FAMILY = c
                    break
        except Exception:
            _CACHED_FONT_FAMILY = "sans-serif"
        if not _CACHED_FONT_FAMILY:
            _CACHED_FONT_FAMILY = "sans-serif"
    return _CACHED_FONT_FAMILY


def font_spec(size=11, weight="normal", slant="roman"):
    """Returns a font tuple with modern family and comfortable readable size."""
    fam = get_font_family()
    if slant != "roman":
        return (fam, size, weight, slant)
    if weight != "normal":
        return (fam, size, weight)
    return (fam, size)


# ==============================================================================
# Helper Utilities (Files, Icons, Shell, Notifications)
# ==============================================================================

def get_initials(name):
    """Generate 1-2 letter initials from a user's display name."""
    if not name:
        return "WP"
    parts = [p.strip() for p in name.split() if p.strip()]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper()
    return "WP"


def get_avatar_color(name):
    """Deterministic vibrant color derived from string hash."""
    if not name:
        return AVATAR_PALETTE[0]
    val = sum(ord(c) for c in name)
    return AVATAR_PALETTE[val % len(AVATAR_PALETTE)]


def get_file_icon(filename):
    """Returns an intuitive emoji icon representing the file extension."""
    if not filename:
        return "📁"
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"]:
        return "🖼️"
    elif ext in [".pdf"]:
        return "📕"
    elif ext in [".xls", ".xlsx", ".csv", ".tsv"]:
        return "📊"
    elif ext in [".doc", ".docx", ".odt", ".txt", ".rtf", ".md"]:
        return "📄"
    elif ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"]:
        return "📦"
    elif ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sh", ".c", ".cpp", ".java"]:
        return "💻"
    elif ext in [".mp3", ".wav", ".ogg", ".m4a", ".flac"]:
        return "🎵"
    elif ext in [".mp4", ".mkv", ".avi", ".mov", ".webm"]:
        return "🎬"
    return "📁"


def format_file_size(size_bytes):
    """Formats raw byte count into human-readable representation."""
    try:
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0 or unit == 'TB':
                return f"{size:.1f} {unit}" if unit != 'B' else f"{int(size)} B"
            size /= 1024.0
    except Exception:
        return "0 B"


def open_file_externally(filepath):
    """Cross-platform opening of a file using OS default viewer."""
    if not filepath or not os.path.exists(filepath):
        return False
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif sys.platform == "win32":
            os.startfile(filepath)
            return True
    except Exception as e:
        print(f"Error opening file {filepath}: {e}")
    return False


def show_in_file_manager(filepath):
    """Reveals the directory containing the file in the OS file manager."""
    if not filepath:
        return False
    folder = os.path.dirname(os.path.abspath(filepath))
    if not os.path.exists(folder):
        return False
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{os.path.abspath(filepath)}"')
            return True
    except Exception as e:
        print(f"Error revealing folder {folder}: {e}")
    return False


POPULAR_REACTIONS = ["👍", "❤️", "🚀", "🎉", "😂", "👀", "👏"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
SCREENSHOT_DIR = os.path.expanduser("~/.workpulse/screenshots")


def is_image_file(filename):
    """Checks whether the file has a recognizable image extension."""
    if not filename:
        return False
    _, ext = os.path.splitext(str(filename).lower())
    return ext in IMAGE_EXTENSIONS


def parse_code_blocks(text):
    """
    Parses a text message into sequential segments of standard text and fenced code blocks.
    Returns a list of tuples: [("text", str), ("code", lang_str, code_str), ...]
    """
    if not text or "```" not in text:
        return [("text", text or "")]
    pattern = re.compile(r"```([a-zA-Z0-9_\-\.\+\#]*)\n?(.*?)```", re.DOTALL)
    segments = []
    last_end = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_end:
            segments.append(("text", text[last_end:start]))
        lang = match.group(1).strip()
        code = match.group(2)
        segments.append(("code", lang, code))
        last_end = end
    if last_end < len(text):
        segments.append(("text", text[last_end:]))
    return segments if segments else [("text", text)]


def export_chat_history(messages, file_path, format_type="markdown", channel_name="# team-general"):
    """
    Exports a list of chat messages into a beautifully formatted Markdown (.md) or styled HTML (.html) file.
    """
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        if format_type == "markdown":
            lines = [
                f"# 💬 WorkPulse LAN Team Chat Export",
                f"- **Channel / Scope**: `{channel_name}`",
                f"- **Export Date**: {now_str}",
                f"- **Total Messages**: {len(messages)}",
                "",
                "---",
                ""
            ]
            for m in messages:
                sender = m.get("user_name", "Colleague")
                d_str = m.get("date_str", "")
                t_str = m.get("time_str", "")
                m_type = m.get("type", "chat")
                is_pinned = " 📌" if m.get("is_pinned") else ""
                lines.append(f"### [{d_str} {t_str}] **{sender}**{is_pinned}")

                reply_to = m.get("reply_to")
                if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                    rep_user = reply_to.get("user_name", "Colleague")
                    rep_txt = reply_to.get("text", "")
                    lines.append(f"> ↳ Quoting **{rep_user}**: {rep_txt}")
                    lines.append("")

                if m_type == "work_update":
                    lines.append(f"**📋 {m.get('title', 'Work Update')}** ({m.get('shift_str', '')})")
                    for t in m.get("tasks", []):
                        lines.append(f"- [{t.get('status', 'Completed')}] {t.get('title', 'Task')} ({t.get('hours', '')}h)")
                elif m_type == "file":
                    lines.append(f"📁 **Shared File**: `{m.get('file_name', 'File')}` ({m.get('file_size_str', '')})")
                    if m.get("caption"):
                        lines.append(f"_{m.get('caption')}_")
                elif m_type == "poll":
                    lines.append(f"🗳️ **POLL**: {m.get('title') or m.get('text')}")
                    for opt in m.get("tasks", []):
                        v_cnt = len(opt.get("votes", []))
                        voters = f" ({', '.join(opt['votes'])})" if v_cnt > 0 else ""
                        lines.append(f"- [ ] {opt.get('text')}: {v_cnt} votes{voters}")
                else:
                    lines.append(m.get("text", ""))

                rx = m.get("reactions") or {}
                if rx:
                    rx_str = " ".join([f"{e} {len(users)}" for e, users in rx.items()])
                    lines.append(f"_{rx_str}_")

                lines.append("")
                lines.append("---")
                lines.append("")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True

        elif format_type == "html":
            html_rows = []
            for m in messages:
                sender = html.escape(str(m.get("user_name", "Colleague")))
                av_col = m.get("avatar_color", "#2563eb")
                d_str = html.escape(str(m.get("date_str", "")))
                t_str = html.escape(str(m.get("time_str", "")))
                m_type = m.get("type", "chat")
                is_pinned_tag = '<span class="pinned-tag">📌 Pinned</span>' if m.get("is_pinned") else ''

                quote_html = ""
                reply_to = m.get("reply_to")
                if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                    r_u = html.escape(str(reply_to.get("user_name", "Colleague")))
                    r_t = html.escape(str(reply_to.get("text", "")))
                    quote_html = f'<div class="quote-box">↳ Replying to <b>{r_u}</b>: {r_t}</div>'

                body_html = ""
                if m_type == "work_update":
                    tasks_html = "".join([f"<li><b>[{html.escape(t.get('status',''))}]</b> {html.escape(t.get('title',''))} ({html.escape(str(t.get('hours','')))}h)</li>" for t in m.get("tasks", [])])
                    body_html = f'<div class="card-title">📋 {html.escape(m.get("title","Work Update"))}</div><div class="meta">{html.escape(m.get("shift_str",""))}</div><ul>{tasks_html}</ul>'
                elif m_type == "file":
                    cap = f'<p class="caption">{html.escape(m.get("caption",""))}</p>' if m.get("caption") else ''
                    body_html = f'<div class="file-card">📁 <b>{html.escape(m.get("file_name","File"))}</b> ({html.escape(str(m.get("file_size_str","")))}){cap}</div>'
                elif m_type == "poll":
                    opts_html = ""
                    total_v = sum(len(o.get("votes", [])) for o in m.get("tasks", []))
                    for opt in m.get("tasks", []):
                        v_cnt = len(opt.get("votes", []))
                        pct = int(v_cnt / total_v * 100) if total_v > 0 else 0
                        opts_html += f'<div class="poll-opt"><div class="poll-bar" style="width: {pct}%"></div><div class="poll-txt"><span>{html.escape(opt.get("text",""))}</span><span>{pct}% ({v_cnt})</span></div></div>'
                    body_html = f'<div class="card-title">🗳️ {html.escape(m.get("title") or m.get("text","Poll"))}</div>{opts_html}'
                else:
                    raw_txt = m.get("text", "")
                    segs = parse_code_blocks(raw_txt)
                    rendered_segs = []
                    for seg in segs:
                        if seg[0] == "code":
                            lang_tag = html.escape(seg[1].upper() if seg[1] else "CODE")
                            code_esc = html.escape(seg[2])
                            rendered_segs.append(f'<div class="code-block"><div class="code-head">💻 {lang_tag}</div><pre><code>{code_esc}</code></pre></div>')
                        else:
                            rendered_segs.append(f'<p>{html.escape(seg[1])}</p>')
                    body_html = "".join(rendered_segs)

                rx = m.get("reactions") or {}
                rx_html = ""
                if rx:
                    rx_pills = "".join([f'<span class="rx-pill">{e} {len(u)}</span>' for e, u in rx.items()])
                    rx_html = f'<div class="rx-box">{rx_pills}</div>'

                initials = sender[:2].upper()
                row = f"""
                <div class="msg-row">
                    <div class="avatar" style="background-color: {av_col};">{initials}</div>
                    <div class="msg-content">
                        <div class="msg-header">
                            <span class="user-name">{sender}</span>
                            <span class="timestamp">{d_str} {t_str}</span>
                            {is_pinned_tag}
                        </div>
                        {quote_html}
                        <div class="msg-body">{body_html}</div>
                        {rx_html}
                    </div>
                </div>
                """
                html_rows.append(row)

            full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>WorkPulse Chat Export - {html.escape(channel_name)}</title>
<style>
    body {{ background: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 24px; max-width: 860px; margin: 0 auto; }}
    h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 4px; }}
    .meta-bar {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid #334155; }}
    .msg-row {{ display: flex; gap: 12px; margin-bottom: 18px; }}
    .avatar {{ width: 36px; height: 36px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; flex-shrink: 0; }}
    .msg-content {{ flex-grow: 1; background: #1e293b; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; }}
    .msg-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
    .user-name {{ font-weight: bold; color: #ffffff; }}
    .timestamp {{ font-size: 11px; color: #94a3b8; }}
    .pinned-tag {{ font-size: 10px; font-weight: bold; background: #334155; color: #38bdf8; padding: 2px 6px; border-radius: 4px; }}
    .quote-box {{ background: #0f172a; border-left: 3px solid #38bdf8; padding: 6px 10px; font-size: 12px; color: #94a3b8; margin-bottom: 8px; border-radius: 0 4px 4px 0; }}
    .msg-body {{ font-size: 13px; line-height: 1.5; color: #e2e8f0; }}
    .msg-body p {{ margin: 4px 0; }}
    .code-block {{ background: #0b0f19; border: 1px solid #334155; border-radius: 6px; margin: 8px 0; overflow: hidden; }}
    .code-head {{ background: #111827; padding: 4px 8px; font-size: 11px; font-weight: bold; color: #38bdf8; }}
    pre {{ margin: 0; padding: 10px; font-family: monospace; font-size: 12px; color: #f1f5f9; overflow-x: auto; }}
    .poll-opt {{ position: relative; background: #334155; border-radius: 4px; height: 26px; margin: 6px 0; overflow: hidden; }}
    .poll-bar {{ position: absolute; height: 100%; background: #2563eb; opacity: 0.7; }}
    .poll-txt {{ position: relative; z-index: 1; display: flex; justify-content: space-between; padding: 4px 10px; font-size: 12px; color: #ffffff; }}
    .rx-box {{ display: flex; gap: 6px; margin-top: 8px; }}
    .rx-pill {{ background: #0f172a; border: 1px solid #334155; border-radius: 12px; padding: 2px 8px; font-size: 12px; }}
</style>
</head>
<body>
    <h1>💬 WorkPulse LAN Chat Export</h1>
    <div class="meta-bar">Channel: <b>{html.escape(channel_name)}</b> • Exported: {now_str} • Messages: {len(messages)}</div>
    {''.join(html_rows)}
</body>
</html>"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_html)
            return True
    except Exception as e:
        print(f"Error exporting chat history: {e}")
        return False


def grab_clipboard_image(dest_path):
    """
    Attempts to capture an image from the system clipboard and save it as a PNG file.
    Supports Linux (xclip / wl-paste), Windows (PowerShell), macOS (osascript),
    and optional PIL / Pillow if installed.
    Returns True if an image was successfully captured, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    except Exception:
        pass

    # 1. Linux xclip / wl-paste
    if sys.platform.startswith("linux"):
        # Check xclip first
        try:
            check_proc = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            targets = [t.strip() for t in check_proc.stdout.splitlines() if t.strip()]
            for img_t in ["image/png", "image/jpeg", "image/bmp"]:
                if img_t in targets:
                    with open(dest_path, "wb") as f_out:
                        subprocess.run(
                            ["xclip", "-selection", "clipboard", "-t", img_t, "-o"],
                            stdout=f_out,
                            stderr=subprocess.PIPE,
                            timeout=5
                        )
                    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                        return True
        except Exception:
            pass

        # Check Wayland wl-paste
        try:
            with open(dest_path, "wb") as f_out:
                subprocess.run(
                    ["wl-paste", "-t", "image/png"],
                    stdout=f_out,
                    stderr=subprocess.PIPE,
                    timeout=3
                )
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True
        except Exception:
            pass

    # 2. Windows PowerShell Clipboard
    elif sys.platform == "win32":
        try:
            abs_dest = os.path.abspath(dest_path).replace("\\", "\\\\")
            ps_script = (
                'Add-Type -AssemblyName System.Windows.Forms; '
                'Add-Type -AssemblyName System.Drawing; '
                'if ([System.Windows.Forms.Clipboard]::ContainsImage()) { '
                '$img = [System.Windows.Forms.Clipboard]::GetImage(); '
                f'$img.Save("{abs_dest}", [System.Drawing.Imaging.ImageFormat]::Png); '
                '$img.Dispose(); '
                'exit 0; '
                '} else { exit 1; }'
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            if res.returncode == 0 and os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True
        except Exception:
            pass

    # 3. macOS osascript
    elif sys.platform == "darwin":
        try:
            abs_dest = os.path.abspath(dest_path)
            cmd = [
                "osascript", "-e",
                f'set theFile to open for access POSIX file "{abs_dest}" with write permission\n'
                f'try\n'
                f'    write (the clipboard as «class PNGf») to theFile\n'
                f'    close access theFile\n'
                f'on error\n'
                f'    close access theFile\n'
                f'end try'
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True
        except Exception:
            pass

    # 4. Optional Pillow fallback if available in environment
    try:
        from PIL import ImageGrab
        im = ImageGrab.grabclipboard()
        if im is not None:
            im.save(dest_path, "PNG")
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True
    except Exception:
        pass

    return False


def create_tk_thumbnail(filepath, max_w=340, max_h=240):
    """
    Creates a downsampled tk.PhotoImage thumbnail for inline image previews.
    Uses native Tk 8.6+ PNG/GIF loading and subsample scaling.
    Returns tk.PhotoImage or None on failure.
    """
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        photo = tk.PhotoImage(file=filepath)
        w = photo.width()
        h = photo.height()
        if w <= 0 or h <= 0:
            return None
        if w > max_w or h > max_h:
            factor_w = max(1, int(math.ceil(w / max_w)))
            factor_h = max(1, int(math.ceil(h / max_h)))
            factor = max(factor_w, factor_h)
            if factor > 1:
                return photo.subsample(factor, factor)
        return photo
    except Exception:
        return None


def show_desktop_notification(title, message, app_name="WorkPulse"):
    """
    Shows a non-blocking desktop system notification.
    Uses notify-send on Linux, AppleScript on macOS, or PowerShell on Windows.
    """
    def _worker():
        try:
            if is_android():
                show_android_notification(title, message)
                return
            if sys.platform.startswith("linux"):
                subprocess.run(
                    ["notify-send", "-a", app_name, "-i", "mail-message-new", "-t", "5000", str(title), str(message)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            elif sys.platform == "darwin":
                esc_title = str(title).replace('"', '\\"')
                esc_msg = str(message).replace('"', '\\"')
                subprocess.run(
                    ["osascript", "-e", f'display notification "{esc_msg}" with title "{esc_title}" sound name "Glass"'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            elif sys.platform == "win32":
                ps_cmd = (
                    f'[reflection.assembly]::loadwithpartialname("System.Windows.Forms"); '
                    f'[reflection.assembly]::loadwithpartialname("System.Drawing"); '
                    f'$n = new-object system.windows.forms.notifyicon; '
                    f'$n.icon = [system.drawing.systemicons]::Information; '
                    f'$n.visible = $true; '
                    f'$n.showballoontip(5000, "{title}", "{message}", [system.windows.forms.tooltipicon]::Info)'
                )
                subprocess.run(["powershell", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="DesktopNotification").start()


_active_toasts = {}

class InAppToast:
    """Floating notification toast overlay inside a Tkinter window."""
    def __init__(self, master, title, message, icon="💬", on_click=None, duration_ms=4500):
        self.master = master
        self.on_click = on_click

        self.frame = tk.Frame(master, bg="#1e293b", bd=2, relief="ridge", padx=14, pady=10)

        # Header row
        hdr = tk.Frame(self.frame, bg="#1e293b")
        hdr.pack(fill=tk.X)

        lbl_icon = tk.Label(hdr, text=icon, font=font_spec(12), bg="#1e293b", fg="#38bdf8")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 6))

        lbl_title = tk.Label(hdr, text=title, font=font_spec(11, "bold"), bg="#1e293b", fg="#ffffff")
        lbl_title.pack(side=tk.LEFT)

        btn_close = tk.Label(hdr, text="✕", font=font_spec(10, "bold"), bg="#1e293b", fg="#94a3b8", cursor="hand2")
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Button-1>", lambda e: self.destroy())

        # Message body
        lbl_msg = tk.Label(
            self.frame,
            text=message,
            font=font_spec(11),
            bg="#1e293b",
            fg="#e2e8f0",
            wraplength=320,
            justify="left"
        )
        lbl_msg.pack(anchor="w", pady=(6, 8))

        if on_click:
            btn_act = tk.Button(
                self.frame,
                text="Open Chat 💬",
                font=font_spec(10, "bold"),
                bg="#2563eb",
                fg="white",
                activebackground="#1d4ed8",
                activeforeground="white",
                relief="flat",
                padx=10,
                pady=3,
                cursor="hand2",
                command=self._do_click
            )
            btn_act.pack(anchor="e")

        self.frame.bind("<Button-1>", self._do_click)
        lbl_msg.bind("<Button-1>", self._do_click)

        # Place neatly at top-right
        self.frame.place(relx=0.98, rely=0.03, anchor="ne")
        self.frame.lift()

        self.master.after(duration_ms, self.destroy)

    def _do_click(self, event=None):
        if self.on_click:
            self.on_click()
        self.destroy()

    def destroy(self):
        try:
            if hasattr(self, 'frame') and self.frame.winfo_exists():
                self.frame.destroy()
        except Exception:
            pass


def show_in_app_toast(master, title, message, icon="💬", on_click=None, duration_ms=4500):
    """Renders a floating notification card in the corner of master window."""
    try:
        if not master or not master.winfo_exists():
            return None
        win_id = id(master)
        if win_id in _active_toasts:
            try:
                _active_toasts[win_id].destroy()
            except Exception:
                pass
        t = InAppToast(master, title, message, icon=icon, on_click=on_click, duration_ms=duration_ms)
        _active_toasts[win_id] = t
        return t
    except Exception as e:
        print(f"Toast warning: {e}")
        return None


# Backward-compatible alias for in-app floating notifications
show_floating_toast = show_in_app_toast


def play_sound_alert(alert_type="message"):
    """
    Plays an audible chime for incoming messages, mentions, or file completions.
    Runs asynchronously on a background thread so UI never stutters.
    Works natively across Linux (pw-play, paplay, canberra-gtk-play), Windows (winsound), and macOS (afplay).
    """
    def _worker():
        try:
            if is_android():
                show_android_notification(title, message)
                return
            if sys.platform.startswith("linux"):
                sound_map = {
                    "mention": [
                        "/usr/share/sounds/freedesktop/stereo/bell.oga",
                        "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
                        "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"
                    ],
                    "complete": [
                        "/usr/share/sounds/freedesktop/stereo/complete.oga",
                        "/usr/share/sounds/freedesktop/stereo/device-added.oga",
                        "/usr/share/sounds/freedesktop/stereo/bell.oga"
                    ],
                    "message": [
                        "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga",
                        "/usr/share/sounds/freedesktop/stereo/message.oga",
                        "/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"
                    ]
                }
                candidates = sound_map.get(alert_type, sound_map["message"])
                sound_path = next((p for p in candidates if os.path.exists(p)), None)

                # 1. PipeWire pw-play
                if sound_path and shutil.which("pw-play"):
                    subprocess.run(["pw-play", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    return
                # 2. PulseAudio paplay
                if sound_path and shutil.which("paplay"):
                    subprocess.run(["paplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    return
                # 3. Canberra
                if shutil.which("canberra-gtk-play"):
                    c_id = "message-new-instant" if alert_type == "message" else ("complete" if alert_type == "complete" else "bell")
                    subprocess.run(["canberra-gtk-play", "-i", c_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    return

            elif sys.platform == "win32":
                import winsound
                if alert_type == "mention":
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                elif alert_type == "complete":
                    winsound.MessageBeep(winsound.MB_OK)
                else:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                return

            elif sys.platform == "darwin":
                sound_p = "/System/Library/Sounds/Glass.aiff"
                if os.path.exists(sound_p):
                    subprocess.run(["afplay", sound_p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    return
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="LANChat-AudioChime").start()


def choose_file_dialog(parent=None, title="Select File", filetypes=None, initialdir=None):
    """
    Opens a native modern file picker dialog.
    On Linux, uses zenity (if available) for a modern GTK file chooser with bookmarks & search.
    Gracefully falls back to tkinter filedialog.askopenfilename.
    """
    if sys.platform.startswith("linux") and shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", f"--title={title}"]
        if initialdir and os.path.exists(initialdir):
            cmd.append(f"--filename={os.path.abspath(initialdir)}/")
        if filetypes:
            for ft_name, ft_pattern in filetypes:
                pats = " ".join(ft_pattern.replace(";", " ").split())
                cmd.append(f"--file-filter={ft_name} | {pats}")
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if res.returncode == 0:
                selected = res.stdout.strip()
                if selected and os.path.exists(selected):
                    return selected
            return ""  # User cancelled
        except Exception:
            pass  # Fallback to tk dialog

    return filedialog.askopenfilename(
        parent=parent,
        title=title,
        filetypes=filetypes or [("All Files", "*.*")],
        initialdir=initialdir
    )


def choose_save_dialog(parent=None, title="Save File", default_name=None, filetypes=None, initialdir=None, defaultextension=None):
    """
    Opens a native modern save-file dialog.
    On Linux, uses zenity (if available) for a modern GTK save file chooser.
    Gracefully falls back to tkinter filedialog.asksaveasfilename.
    """
    if sys.platform.startswith("linux") and shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--save", "--confirm-overwrite", f"--title={title}"]
        target_dir = initialdir or os.path.expanduser("~")
        if default_name:
            init_path = os.path.join(target_dir, default_name)
            cmd.append(f"--filename={init_path}")
        elif initialdir and os.path.exists(initialdir):
            cmd.append(f"--filename={os.path.abspath(initialdir)}/")
        if filetypes:
            for ft_name, ft_pattern in filetypes:
                pats = " ".join(ft_pattern.replace(";", " ").split())
                cmd.append(f"--file-filter={ft_name} | {pats}")
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if res.returncode == 0:
                out = res.stdout.strip()
                if out:
                    if defaultextension and not out.endswith(defaultextension) and "." not in os.path.basename(out):
                        out += defaultextension
                    return out
            return ""  # User cancelled
        except Exception:
            pass

    return filedialog.asksaveasfilename(
        parent=parent,
        title=title,
        initialfile=default_name,
        filetypes=filetypes or [("All Files", "*.*")],
        initialdir=initialdir,
        defaultextension=defaultextension
    )


def center_window(window, parent=None, default_w=None, default_h=None, min_w=None, min_h=None):
    """Auto-adjust and center a window relative to its parent or screen, ensuring it fits cleanly on any display."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    req_w = window.winfo_reqwidth()
    req_h = window.winfo_reqheight()

    w = max(default_w or 0, req_w)
    h = max(default_h or 0, req_h)
    if min_w:
        w = max(w, min_w)
    if min_h:
        h = max(h, min_h)

    # Fallback bounds if still tiny
    w = max(w, 460)
    h = max(h, 240)

    # Clamp to screen boundary
    w = min(w, max(460, screen_w - 60))
    h = min(h, max(240, screen_h - 100))

    if min_w is not None or min_h is not None:
        actual_min_w = min(min_w or 460, w)
        actual_min_h = min(min_h or 240, h)
        window.minsize(actual_min_w, actual_min_h)

    if parent and parent.winfo_exists() and parent.winfo_viewable():
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
    else:
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)

    x = max(10, min(x, max(10, screen_w - w - 10)))
    y = max(10, min(y, max(10, screen_h - h - 50)))

    window.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")


def get_network_info():
    """
    Detects primary local IP and broadcast addresses for LAN communication.
    Works reliably across Android, Linux, Windows, and macOS.
    """
    local_ip = "127.0.0.1"
    hostname = socket.gethostname()
    broadcasts = {"255.255.255.255"}

    # 1. Android Wi-Fi network interface detection
    if is_android():
        try:
            a_ip, a_bcasts = get_android_network_info()
            if a_ip:
                local_ip = a_ip
                for b in a_bcasts:
                    broadcasts.add(b)
        except Exception:
            pass

    # 2. Standard socket route probing (tries public DNS then local gateways if offline)
    if local_ip == "127.0.0.1":
        for target_host in ("8.8.8.8", "192.168.1.1", "192.168.0.1", "10.0.0.1"):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((target_host, 80))
                ip_cand = s.getsockname()[0]
                s.close()
                if ip_cand and not ip_cand.startswith("127."):
                    local_ip = ip_cand
                    break
            except Exception:
                continue

    if local_ip == "127.0.0.1":
        try:
            ip_cand = socket.gethostbyname(hostname)
            if ip_cand and not ip_cand.startswith("127."):
                local_ip = ip_cand
        except Exception:
            pass

    # 3. Subnet broadcast address calculation
    parts = local_ip.split(".")
    if len(parts) == 4 and parts[0] != "127":
        subnet_bcast_24 = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        subnet_bcast_16 = f"{parts[0]}.{parts[1]}.255.255"
        broadcasts.add(subnet_bcast_24)
        broadcasts.add(subnet_bcast_16)

    # Note: avoid '<broadcast>' on Android/Linux to prevent socket.gaierror
    if not is_android() and sys.platform != "linux":
        broadcasts.add("<broadcast>")

    return local_ip, hostname, [b for b in broadcasts if b]


# ==============================================================================
# SQLite Chat Database Engine (With File Sharing Schema Support)
# ==============================================================================

class ChatDatabase:
    """
    High-performance, persistent SQLite database storage for WorkPulse LAN chat.
    Stores messages, work summaries, task breakdowns, file sharing transfers,
    timestamps, and metadata. Thread-safe with WAL mode enabled.
    """
    def __init__(self, db_path=CHAT_DB_FILE):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.use_sqlite = bool(SQLITE_AVAILABLE and sqlite3 is not None)
        self._json_fallback_file = LEGACY_JSON_FILE
        self._fallback_messages = []
        self._fallback_pinned = None

        if self.use_sqlite:
            try:
                self._init_db()
            except Exception as e:
                print(f"Notice: SQLite init failed ({e}), using JSON fallback for LAN chat.")
                self.use_sqlite = False
                self._load_fallback_json()
        else:
            self._load_fallback_json()

    def _load_fallback_json(self):
        if os.path.exists(self._json_fallback_file):
            try:
                with open(self._json_fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._fallback_messages = data
            except Exception:
                self._fallback_messages = []

    def _save_fallback_json(self):
        try:
            with open(self._json_fallback_file, "w", encoding="utf-8") as f:
                json.dump(self._fallback_messages[-MAX_HISTORY_ITEMS:], f, indent=2)
        except Exception as e:
            print(f"Error saving chat JSON fallback: {e}")

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        type TEXT NOT NULL DEFAULT 'chat',
                        sender_id TEXT,
                        user_name TEXT,
                        avatar_color TEXT,
                        text TEXT,
                        time_str TEXT,
                        timestamp REAL,
                        date_str TEXT,
                        is_me INTEGER DEFAULT 0,
                        title TEXT,
                        tasks_json TEXT,
                        shift_str TEXT,
                        total_hours TEXT,
                        file_name TEXT,
                        file_size TEXT,
                        file_id TEXT,
                        file_ip TEXT,
                        file_port INTEGER,
                        local_path TEXT,
                        is_image INTEGER DEFAULT 0,
                        reply_to_json TEXT,
                        reactions_json TEXT,
                        recipient_id TEXT DEFAULT '',
                        recipient_name TEXT DEFAULT '',
                        is_pinned INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pinned_announcements (
                        id TEXT PRIMARY KEY,
                        msg_id TEXT,
                        text TEXT,
                        user_name TEXT,
                        pinned_by TEXT,
                        timestamp REAL
                    );
                """)
                # Migrations for existing databases
                for col, col_type in [
                    ("file_name", "TEXT"),
                    ("file_size", "TEXT"),
                    ("file_id", "TEXT"),
                    ("file_ip", "TEXT"),
                    ("file_port", "INTEGER"),
                    ("local_path", "TEXT"),
                    ("is_image", "INTEGER DEFAULT 0"),
                    ("reply_to_json", "TEXT"),
                    ("reactions_json", "TEXT"),
                    ("recipient_id", "TEXT DEFAULT ''"),
                    ("recipient_name", "TEXT DEFAULT ''"),
                    ("is_pinned", "INTEGER DEFAULT 0")
                ]:
                    try:
                        conn.execute(f"ALTER TABLE chat_messages ADD COLUMN {col} {col_type};")
                    except Exception:
                        pass

                conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON chat_messages(timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_date ON chat_messages(date_str);")
                conn.commit()

            self._migrate_json_if_exists()

    def _migrate_json_if_exists(self):
        if os.path.exists(LEGACY_JSON_FILE):
            try:
                with open(LEGACY_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    with self._get_connection() as conn:
                        for m in data:
                            self._insert_row(conn, m)
                        conn.commit()
                try:
                    os.rename(LEGACY_JSON_FILE, LEGACY_JSON_FILE + ".bak")
                except Exception:
                    pass
            except Exception as e:
                print(f"Chat migration warning: {e}")

    def _insert_row(self, conn, m):
        m_id = m.get("id") or uuid.uuid4().hex[:12]
        m_type = m.get("type", "chat")
        sender_id = m.get("sender_id", "")
        user_name = m.get("user_name", "Colleague")
        avatar_color = m.get("avatar_color", AVATAR_PALETTE[0])
        text = m.get("text", "")
        time_str = m.get("time_str", "")
        timestamp = float(m.get("timestamp") or time.time())
        date_str = m.get("date_str") or datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        is_me = 1 if m.get("is_me") else 0
        title = m.get("title", "")
        tasks = m.get("tasks", [])
        tasks_json = json.dumps(tasks) if tasks else ""
        shift_str = m.get("shift_str", "")
        total_hours = str(m.get("total_hours", ""))
        file_name = m.get("file_name", "")
        file_size = str(m.get("file_size_str") or m.get("file_size") or "")
        file_id = m.get("file_id", "")
        file_ip = m.get("file_ip", "")
        file_port = int(m.get("file_port") or 0)
        local_path = m.get("local_path", "")
        is_image = 1 if m.get("is_image") else 0
        reply_to = m.get("reply_to")
        reply_to_json = json.dumps(reply_to) if reply_to else ""
        reactions = m.get("reactions") or {}
        reactions_json = json.dumps(reactions) if reactions else ""
        recipient_id = m.get("recipient_id", "")
        recipient_name = m.get("recipient_name", "")
        is_pinned = 1 if m.get("is_pinned") else 0

        conn.execute("""
            INSERT OR REPLACE INTO chat_messages (
                id, type, sender_id, user_name, avatar_color, text, time_str,
                timestamp, date_str, is_me, title, tasks_json, shift_str, total_hours,
                file_name, file_size, file_id, file_ip, file_port, local_path,
                is_image, reply_to_json, reactions_json, recipient_id, recipient_name, is_pinned
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m_id, m_type, sender_id, user_name, avatar_color, text, time_str,
            timestamp, date_str, is_me, title, tasks_json, shift_str, total_hours,
            file_name, file_size, file_id, file_ip, file_port, local_path,
            is_image, reply_to_json, reactions_json, recipient_id, recipient_name, is_pinned
        ))

    def save_message(self, msg_dict):
        """Persists a message dictionary into SQLite or JSON fallback."""
        with self.lock:
            if not self.use_sqlite:
                m_id = msg_dict.get("id")
                idx = next((i for i, m in enumerate(self._fallback_messages) if m.get("id") == m_id), None)
                if idx is not None:
                    self._fallback_messages[idx] = msg_dict
                else:
                    self._fallback_messages.append(msg_dict)
                self._save_fallback_json()
                return True
            try:
                with self._get_connection() as conn:
                    self._insert_row(conn, msg_dict)
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error saving chat to SQLite: {e}")
                return False

    def update_local_path(self, msg_id, local_path):
        """Updates local_path in database once a shared file finishes downloading."""
        with self.lock:
            if not self.use_sqlite:
                for m in self._fallback_messages:
                    if m.get("id") == msg_id:
                        m["local_path"] = local_path
                        break
                self._save_fallback_json()
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("UPDATE chat_messages SET local_path = ? WHERE id = ?", (local_path, msg_id))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error updating local path in SQLite: {e}")
                return False

    def update_reactions(self, msg_id, reactions):
        """Updates reactions_json in SQLite database for msg_id."""
        with self.lock:
            if not self.use_sqlite:
                for m in self._fallback_messages:
                    if m.get("id") == msg_id:
                        m["reactions"] = reactions
                        break
                self._save_fallback_json()
                return True
            try:
                reactions_json = json.dumps(reactions) if reactions else ""
                with self._get_connection() as conn:
                    conn.execute("UPDATE chat_messages SET reactions_json = ? WHERE id = ?", (reactions_json, msg_id))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error updating reactions in SQLite: {e}")
                return False

    def update_is_pinned(self, msg_id, is_pinned):
        """Updates is_pinned status for a message."""
        with self.lock:
            if not self.use_sqlite:
                for m in self._fallback_messages:
                    if m.get("id") == msg_id:
                        m["is_pinned"] = is_pinned
                        break
                self._save_fallback_json()
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("UPDATE chat_messages SET is_pinned = ? WHERE id = ?", (1 if is_pinned else 0, msg_id))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error updating is_pinned in SQLite: {e}")
                return False

    def update_poll_data(self, msg_id, options_list):
        """Updates tasks_json in SQLite for a poll message."""
        with self.lock:
            if not self.use_sqlite:
                for m in self._fallback_messages:
                    if m.get("id") == msg_id:
                        m["tasks"] = options_list
                        break
                self._save_fallback_json()
                return True
            try:
                tasks_json = json.dumps(options_list)
                with self._get_connection() as conn:
                    conn.execute("UPDATE chat_messages SET tasks_json = ? WHERE id = ?", (tasks_json, msg_id))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error updating poll data in SQLite: {e}")
                return False

    def load_pinned_announcement(self):
        """Loads latest pinned announcement from SQLite or fallback."""
        with self.lock:
            if not self.use_sqlite:
                return self._fallback_pinned
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("SELECT id, msg_id, text, user_name, pinned_by, timestamp FROM pinned_announcements ORDER BY timestamp DESC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        return {
                            "id": row["id"],
                            "msg_id": row["msg_id"],
                            "text": row["text"],
                            "user_name": row["user_name"],
                            "pinned_by": row["pinned_by"],
                            "timestamp": row["timestamp"]
                        }
            except Exception as e:
                print(f"Error loading pinned announcement: {e}")
        return None

    def save_pinned_announcement(self, pin_obj):
        """Saves a pinned announcement to SQLite or fallback."""
        with self.lock:
            if not self.use_sqlite:
                self._fallback_pinned = pin_obj
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM pinned_announcements;")
                    conn.execute("""
                        INSERT INTO pinned_announcements (id, msg_id, text, user_name, pinned_by, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        pin_obj.get("id") or uuid.uuid4().hex[:12],
                        pin_obj.get("msg_id", ""),
                        pin_obj.get("text", ""),
                        pin_obj.get("user_name", ""),
                        pin_obj.get("pinned_by", ""),
                        float(pin_obj.get("timestamp") or time.time())
                    ))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error saving pinned announcement: {e}")
                return False

    def clear_pinned_announcements(self):
        """Clears all pinned announcements from SQLite or fallback."""
        with self.lock:
            if not self.use_sqlite:
                self._fallback_pinned = None
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM pinned_announcements;")
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error clearing pinned announcements: {e}")
                return False

    def delete_message(self, msg_id):
        """Deletes a single message by ID from SQLite database or fallback."""
        with self.lock:
            if not self.use_sqlite:
                self._fallback_messages = [m for m in self._fallback_messages if m.get("id") != msg_id]
                self._save_fallback_json()
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM chat_messages WHERE id = ?", (msg_id,))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error deleting message from SQLite: {e}")
                return False

    def load_recent_messages(self, limit=MAX_HISTORY_ITEMS):
        """Loads last N messages from SQLite in chronological order."""
        with self.lock:
            if not self.use_sqlite:
                return list(self._fallback_messages[-limit:])
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT id, type, sender_id, user_name, avatar_color, text,
                               time_str, timestamp, date_str, is_me, title, tasks_json,
                               shift_str, total_hours, file_name, file_size, file_id,
                               file_ip, file_port, local_path, is_image, reply_to_json, reactions_json,
                               recipient_id, recipient_name, is_pinned
                        FROM (
                            SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT ?
                        ) ORDER BY timestamp ASC
                    """, (limit,))
                    rows = cursor.fetchall()
                    result = []
                    for r in rows:
                        tasks = []
                        if r["tasks_json"]:
                            try:
                                tasks = json.loads(r["tasks_json"])
                            except Exception:
                                tasks = []
                        reply_to = None
                        if "reply_to_json" in r.keys() and r["reply_to_json"]:
                            try:
                                reply_to = json.loads(r["reply_to_json"])
                            except Exception:
                                reply_to = None
                        reactions = {}
                        if "reactions_json" in r.keys() and r["reactions_json"]:
                            try:
                                reactions = json.loads(r["reactions_json"])
                            except Exception:
                                reactions = {}
                        is_image = bool(r["is_image"]) if "is_image" in r.keys() and r["is_image"] else False
                        recipient_id = r["recipient_id"] if "recipient_id" in r.keys() and r["recipient_id"] else ""
                        recipient_name = r["recipient_name"] if "recipient_name" in r.keys() and r["recipient_name"] else ""
                        is_pinned = bool(r["is_pinned"]) if "is_pinned" in r.keys() and r["is_pinned"] else False
                        result.append({
                            "v": 1,
                            "id": r["id"],
                            "type": r["type"],
                            "sender_id": r["sender_id"],
                            "user_name": r["user_name"],
                            "avatar_color": r["avatar_color"],
                            "text": r["text"],
                            "time_str": r["time_str"],
                            "timestamp": r["timestamp"],
                            "date_str": r["date_str"],
                            "is_me": bool(r["is_me"]),
                            "title": r["title"],
                            "tasks": tasks,
                            "shift_str": r["shift_str"],
                            "total_hours": r["total_hours"],
                            "file_name": r["file_name"] or "",
                            "file_size": r["file_size"] or "",
                            "file_size_str": r["file_size"] or "",
                            "file_id": r["file_id"] or "",
                            "file_ip": r["file_ip"] or "",
                            "file_port": r["file_port"] or 0,
                            "local_path": r["local_path"] or "",
                            "is_image": is_image,
                            "reply_to": reply_to,
                            "reactions": reactions,
                            "recipient_id": recipient_id,
                            "recipient_name": recipient_name,
                            "is_pinned": is_pinned
                        })
                    return result
            except Exception as e:
                print(f"Error loading chat from SQLite: {e}")
                return []

    def search_messages(self, query_str, limit=50):
        """Searches message texts, user names, or file names in SQLite or JSON fallback."""
        if not self.use_sqlite:
            q = query_str.lower().strip()
            with self.lock:
                res = [m for m in reversed(self._fallback_messages) if q in str(m.get("text", "")).lower() or q in str(m.get("user_name", "")).lower() or q in str(m.get("title", "")).lower() or q in str(m.get("file_name", "")).lower()]
                return res[:limit]
        q = f"%{query_str.strip()}%"
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT id, type, sender_id, user_name, avatar_color, text,
                               time_str, timestamp, date_str, is_me, title, tasks_json,
                               shift_str, total_hours, file_name, file_size, file_id,
                               file_ip, file_port, local_path, is_image, reply_to_json, reactions_json,
                               recipient_id, recipient_name, is_pinned
                        FROM chat_messages
                        WHERE text LIKE ? OR user_name LIKE ? OR title LIKE ? OR file_name LIKE ?
                        ORDER BY timestamp DESC LIMIT ?
                    """, (q, q, q, q, limit))
                    rows = cursor.fetchall()
                    result = []
                    for r in rows:
                        tasks = []
                        if r["tasks_json"]:
                            try:
                                tasks = json.loads(r["tasks_json"])
                            except Exception:
                                tasks = []
                        reply_to = None
                        if "reply_to_json" in r.keys() and r["reply_to_json"]:
                            try:
                                reply_to = json.loads(r["reply_to_json"])
                            except Exception:
                                reply_to = None
                        reactions = {}
                        if "reactions_json" in r.keys() and r["reactions_json"]:
                            try:
                                reactions = json.loads(r["reactions_json"])
                            except Exception:
                                reactions = {}
                        is_image = bool(r["is_image"]) if "is_image" in r.keys() and r["is_image"] else False
                        recipient_id = r["recipient_id"] if "recipient_id" in r.keys() and r["recipient_id"] else ""
                        recipient_name = r["recipient_name"] if "recipient_name" in r.keys() and r["recipient_name"] else ""
                        is_pinned = bool(r["is_pinned"]) if "is_pinned" in r.keys() and r["is_pinned"] else False
                        result.append({
                            "v": 1,
                            "id": r["id"],
                            "type": r["type"],
                            "sender_id": r["sender_id"],
                            "user_name": r["user_name"],
                            "avatar_color": r["avatar_color"],
                            "text": r["text"],
                            "time_str": r["time_str"],
                            "timestamp": r["timestamp"],
                            "date_str": r["date_str"],
                            "is_me": bool(r["is_me"]),
                            "title": r["title"],
                            "tasks": tasks,
                            "shift_str": r["shift_str"],
                            "total_hours": r["total_hours"],
                            "file_name": r["file_name"] or "",
                            "file_size": r["file_size"] or "",
                            "file_size_str": r["file_size"] or "",
                            "file_id": r["file_id"] or "",
                            "file_ip": r["file_ip"] or "",
                            "file_port": r["file_port"] or 0,
                            "local_path": r["local_path"] or "",
                            "is_image": is_image,
                            "reply_to": reply_to,
                            "reactions": reactions,
                            "recipient_id": recipient_id,
                            "recipient_name": recipient_name,
                            "is_pinned": is_pinned
                        })
                    return result
            except Exception as e:
                print(f"Error searching chat in SQLite: {e}")
                return []

    def get_message_count(self):
        """Returns total message count stored in SQLite or fallback."""
        with self.lock:
            if not self.use_sqlite:
                return len(self._fallback_messages)
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM chat_messages")
                    row = cursor.fetchone()
                    return row[0] if row else 0
            except Exception:
                return 0

    def clear_all(self):
        """Deletes all messages from SQLite database or fallback."""
        with self.lock:
            if not self.use_sqlite:
                self._fallback_messages.clear()
                self._save_fallback_json()
                return True
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM chat_messages;")
                    conn.commit()
                    try:
                        conn.execute("VACUUM;")
                    except Exception:
                        pass
                return True
            except Exception as e:
                print(f"Error clearing SQLite: {e}")
                return False


# ==============================================================================
# LAN Chat Networking & File Transfer Engine
# ==============================================================================

class LANChatEngine:
    """
    Manages background sockets, UDP broadcast discovery, peer tracking,
    built-in HTTP streaming server for LAN file sharing, and callbacks.
    """
    def __init__(self, user_name="Developer", port=DEFAULT_LAN_PORT,
                 on_message=None, on_peers_change=None, on_message_deleted=None,
                 on_reaction=None, on_pinned_change=None, on_poll_updated=None):
        self.user_name = user_name
        self.port = port
        self.on_message = on_message
        self.on_peers_change = on_peers_change
        self.on_message_deleted = on_message_deleted
        self.on_reaction = on_reaction
        self.on_pinned_change = on_pinned_change
        self.on_poll_updated = on_poll_updated

        self.user_id = uuid.uuid4().hex[:10]
        self.local_ip, self.hostname, self.broadcast_addrs = get_network_info()
        self.avatar_color = get_avatar_color(self.user_name)

        self.status = "Available"
        self.status_emoji = "🟢"
        self.status_note = ""

        # Peer storage: peer_id -> dict
        self.peers = {}
        self.custom_ips = set()

        # Deduplication ring buffer
        self.seen_packet_ids = collections.OrderedDict()

        # Threading control
        self.running = False
        self.rx_sock = None
        self.tx_sock = None
        self.rx_thread = None
        self.beacon_thread = None
        self.cleanup_thread = None
        self.lock = threading.Lock()

        # File Sharing Server state
        self.shared_files = {}  # file_id -> {"path": ..., "name": ..., "size": ...}
        self.file_server = None
        self.file_server_thread = None
        self.file_server_port = 0

        # SQLite Chat Database
        self.db = ChatDatabase(CHAT_DB_FILE)
        self.messages = []
        self.load_history()
        self.pinned_announcement = self.db.load_pinned_announcement()

    def start(self):
        """Starts socket listeners, file server, and discovery heartbeats."""
        if self.running:
            return
        self.running = True

        # Acquire Wi-Fi Multicast Lock on Android
        acquire_android_multicast_lock()

        # Refresh network info
        self.local_ip, self.hostname, self.broadcast_addrs = get_network_info()

        # 1. Start HTTP file transfer server on OS-assigned dynamic port
        self._start_file_server()

        # 2. Create receiving UDP socket
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except (AttributeError, OSError):
            pass
        try:
            self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        try:
            self.rx_sock.bind(("", self.port))
        except Exception:
            try:
                self.rx_sock.bind(("", 0))
                self.port = self.rx_sock.getsockname()[1]
            except Exception:
                pass

        self.rx_sock.settimeout(1.0)

        # 3. Create transmitting UDP socket with broadcast enabled
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # 4. Launch background threads
        self.rx_thread = threading.Thread(target=self._listen_loop, daemon=True, name="LANChat-Rx")
        self.beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True, name="LANChat-Beacon")
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="LANChat-Cleanup")

        self.rx_thread.start()
        self.beacon_thread.start()
        self.cleanup_thread.start()

        # Broadcast initial announcement beacon
        self._broadcast_beacon()

    def _start_file_server(self):
        """Launches lightweight, threaded HTTP file server for instant LAN downloads."""
        engine_ref = self

        class LANFileHTTPHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress console noise

            def do_HEAD(self):
                self._serve_file(is_head=True)

            def do_GET(self):
                self._serve_file(is_head=False)

            def _serve_file(self, is_head=False):
                parsed = urllib.parse.urlparse(self.path)
                parts = [p for p in parsed.path.split('/') if p]
                if len(parts) >= 2 and parts[0] == "files":
                    file_id = parts[1]
                    info = engine_ref.shared_files.get(file_id)
                    if info and os.path.exists(info["path"]):
                        fpath = info["path"]
                        fsize = os.path.getsize(fpath)
                        fname = info.get("name") or os.path.basename(fpath)
                        mime_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"

                        # Support HTTP Range requests (essential for smooth video streaming & scrub-bar seeking)
                        range_header = self.headers.get("Range")
                        if range_header and range_header.startswith("bytes="):
                            try:
                                r_spec = range_header.split("=")[1].strip()
                                s_str, e_str = r_spec.split("-")
                                start = int(s_str) if s_str else 0
                                end = int(e_str) if e_str else fsize - 1
                                end = min(end, fsize - 1)
                                length = end - start + 1

                                self.send_response(206)
                                self.send_header("Content-Type", mime_type)
                                self.send_header("Content-Range", f"bytes {start}-{end}/{fsize}")
                                self.send_header("Content-Length", str(length))
                                self.send_header("Accept-Ranges", "bytes")
                                self.send_header("Content-Disposition", f'inline; filename="{fname}"')
                                self.end_headers()

                                if not is_head:
                                    with open(fpath, "rb") as f:
                                        f.seek(start)
                                        rem = length
                                        while rem > 0:
                                            chunk = f.read(min(65536, rem))
                                            if not chunk:
                                                break
                                            self.wfile.write(chunk)
                                            rem -= len(chunk)
                                return
                            except (BrokenPipeError, ConnectionResetError):
                                return
                            except Exception:
                                pass

                        # Full content response
                        self.send_response(200)
                        self.send_header("Content-Type", mime_type)
                        self.send_header("Content-Length", str(fsize))
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Content-Disposition", f'inline; filename="{fname}"')
                        self.end_headers()

                        if not is_head:
                            try:
                                with open(fpath, "rb") as f:
                                    while True:
                                        chunk = f.read(65536)
                                        if not chunk:
                                            break
                                        self.wfile.write(chunk)
                            except (BrokenPipeError, ConnectionResetError):
                                pass
                        return
                self.send_response(404)
                self.end_headers()
                if not is_head:
                    self.wfile.write(b"File not found or transfer completed.")

        try:
            self.file_server = http.server.HTTPServer(("0.0.0.0", 0), LANFileHTTPHandler)
            self.file_server_port = self.file_server.server_port
            self.file_server_thread = threading.Thread(
                target=self.file_server.serve_forever,
                daemon=True,
                name="LANChat-FileServer"
            )
            self.file_server_thread.start()
        except Exception as e:
            print(f"Error starting file transfer server: {e}")

    def stop(self):
        """Gracefully announces departure and closes sockets and file server."""
        if not self.running:
            return
        self.running = False

        try:
            leave_pkt = {
                "v": 1,
                "id": uuid.uuid4().hex[:12],
                "type": "leave",
                "sender_id": self.user_id,
                "user_name": self.user_name
            }
            self._send_raw_packet(leave_pkt)
        except Exception:
            pass

        time.sleep(0.05)

        if self.file_server:
            try:
                self.file_server.shutdown()
                self.file_server.server_close()
            except Exception:
                pass

        if self.rx_sock:
            try:
                self.rx_sock.close()
            except Exception:
                pass

        if self.tx_sock:
            try:
                self.tx_sock.close()
            except Exception:
                pass

        try:
            release_android_multicast_lock()
        except Exception:
            pass

    def update_profile(self, user_name, status=None, status_emoji=None, status_note=None):
        """Updates user profile and broadcasts state change to peers."""
        with self.lock:
            self.user_name = user_name or self.user_name
            self.avatar_color = get_avatar_color(self.user_name)
            if status is not None:
                self.status = status
            if status_emoji is not None:
                self.status_emoji = status_emoji
            if status_note is not None:
                self.status_note = status_note

        pkt = {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "status_update",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "status": self.status,
            "status_emoji": self.status_emoji,
            "status_note": self.status_note,
            "avatar_color": self.avatar_color,
            "timestamp": time.time()
        }
        self._send_raw_packet(pkt)

    def add_custom_peer_ip(self, ip_str):
        """Adds a colleague's IP for networks where UDP broadcast is restricted."""
        clean_ip = ip_str.strip()
        if not clean_ip:
            return False
        with self.lock:
            self.custom_ips.add(clean_ip)

        pkt = self._build_beacon_packet(is_ack=False)
        try:
            data = json.dumps(pkt).encode("utf-8")
            self.tx_sock.sendto(data, (clean_ip, DEFAULT_LAN_PORT))
        except Exception:
            pass
        return True

    def send_chat_message(self, text, reply_to=None, recipient_id="", recipient_name=""):
        """Sends a team chat message or 1-on-1 private direct message."""
        clean_text = text.strip()
        if not clean_text:
            return None

        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        pkt_id = uuid.uuid4().hex[:12]

        msg_obj = {
            "v": 1,
            "id": pkt_id,
            "type": "chat",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "avatar_color": self.avatar_color,
            "text": clean_text,
            "time_str": time_str,
            "timestamp": time.time(),
            "is_me": True,
            "reply_to": reply_to,
            "reactions": {},
            "recipient_id": recipient_id or "",
            "recipient_name": recipient_name or "",
            "is_pinned": False
        }

        with self.lock:
            self._record_seen_packet(pkt_id)
            self.messages.append(msg_obj)
            self.save_history(msg_obj)

        self._send_raw_packet(msg_obj)

        if self.on_message:
            self.on_message(msg_obj)

        return msg_obj

    def send_file(self, file_path, is_image=False, reply_to=None, caption="", recipient_id="", recipient_name=""):
        """Broadcasts a shared file/screenshot across LAN or sends as private DM."""
        if not file_path or not os.path.isfile(file_path):
            return None

        file_path = os.path.abspath(file_path)
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_size_str = format_file_size(file_size)
        file_id = uuid.uuid4().hex[:12]
        pkt_id = uuid.uuid4().hex[:12]
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")

        if not is_image and is_image_file(file_name):
            is_image = True

        display_text = caption.strip() if caption.strip() else (f"Shared image: {file_name}" if is_image else f"Shared file: {file_name} ({file_size_str})")

        with self.lock:
            self.shared_files[file_id] = {
                "path": file_path,
                "name": file_name,
                "size": file_size
            }

        msg_obj = {
            "v": 1,
            "id": pkt_id,
            "type": "file",
            "is_image": is_image,
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "avatar_color": self.avatar_color,
            "file_id": file_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_size_str": file_size_str,
            "file_ip": self.local_ip,
            "file_port": self.file_server_port,
            "local_path": file_path,
            "text": display_text,
            "caption": caption.strip(),
            "time_str": time_str,
            "timestamp": time.time(),
            "is_me": True,
            "reply_to": reply_to,
            "reactions": {},
            "recipient_id": recipient_id or "",
            "recipient_name": recipient_name or "",
            "is_pinned": False
        }

        with self.lock:
            self._record_seen_packet(pkt_id)
            self.messages.append(msg_obj)
            self.save_history(msg_obj)

        self._send_raw_packet(msg_obj)

        if self.on_message:
            self.on_message(msg_obj)

        return msg_obj

    def pin_message(self, msg_id):
        """Pins a message as active team announcement and broadcasts to LAN."""
        target_msg = None
        with self.lock:
            for m in self.messages:
                if m.get("id") == msg_id:
                    target_msg = m
                    m["is_pinned"] = True
                    break
        if not target_msg:
            return False

        pin_obj = {
            "id": uuid.uuid4().hex[:12],
            "msg_id": msg_id,
            "text": target_msg.get("text") or target_msg.get("title") or target_msg.get("file_name") or "Announcement",
            "user_name": target_msg.get("user_name", "Team"),
            "pinned_by": self.user_name,
            "timestamp": time.time()
        }
        self.pinned_announcement = pin_obj
        self.db.save_pinned_announcement(pin_obj)
        self.db.update_is_pinned(msg_id, True)

        pkt = {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "pin_announcement",
            "action": "pin",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "pin_obj": pin_obj
        }
        self._send_raw_packet(pkt)
        if self.on_pinned_change:
            self.on_pinned_change(pin_obj)
        return True

    def unpin_announcement(self):
        """Unpins current team announcement and broadcasts to LAN."""
        prev_pin = self.pinned_announcement
        if prev_pin and prev_pin.get("msg_id"):
            msg_id = prev_pin["msg_id"]
            with self.lock:
                for m in self.messages:
                    if m.get("id") == msg_id:
                        m["is_pinned"] = False
                        break
            self.db.update_is_pinned(msg_id, False)

        self.pinned_announcement = None
        self.db.clear_pinned_announcements()

        pkt = {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "pin_announcement",
            "action": "unpin",
            "sender_id": self.user_id,
            "user_name": self.user_name
        }
        self._send_raw_packet(pkt)
        if self.on_pinned_change:
            self.on_pinned_change(None)
        return True

    def create_poll(self, question, options, recipient_id="", recipient_name=""):
        """Creates a new interactive LAN team poll and broadcasts it to peers."""
        poll_id = uuid.uuid4().hex[:12]
        opts = [{"id": f"opt_{i}", "text": opt.strip(), "votes": []} for i, opt in enumerate(options) if opt.strip()]
        if not opts:
            return None

        poll_msg = {
            "v": 1,
            "id": poll_id,
            "type": "poll",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "avatar_color": self.avatar_color,
            "text": question,
            "title": question,
            "tasks": opts,
            "time_str": datetime.datetime.now().strftime("%I:%M %p"),
            "timestamp": time.time(),
            "date_str": datetime.datetime.now().strftime("%Y-%m-%d"),
            "is_me": True,
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
            "reactions": {},
            "is_pinned": False,
        }

        self.db.save_message(poll_msg)
        with self.lock:
            self.messages.append(poll_msg)

        pkt = {
            "v": 1,
            "id": poll_id,
            "type": "poll",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "avatar_color": self.avatar_color,
            "question": question,
            "options": opts,
            "time_str": poll_msg["time_str"],
            "timestamp": poll_msg["timestamp"],
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
        }
        self._send_raw_packet(pkt)

        if self.on_message:
            self.on_message(poll_msg)
        return poll_msg

    def cast_poll_vote(self, poll_id, option_id):
        """Toggles/casts a vote for option_id in poll_id and broadcasts it."""
        target_poll = None
        with self.lock:
            for m in self.messages:
                if m.get("id") == poll_id:
                    target_poll = m
                    break

        if not target_poll:
            recent = self.db.load_recent_messages(limit=100)
            for m in recent:
                if m.get("id") == poll_id:
                    target_poll = m
                    with self.lock:
                        self.messages.append(target_poll)
                    break

        if not target_poll:
            return False

        opts = target_poll.get("tasks") or []
        user = self.user_name
        already_voted_this = False
        for opt in opts:
            if opt.get("id") == option_id and user in opt.get("votes", []):
                already_voted_this = True
                break

        for opt in opts:
            votes = opt.setdefault("votes", [])
            if user in votes:
                votes.remove(user)
            if not already_voted_this and opt.get("id") == option_id:
                votes.append(user)

        target_poll["tasks"] = opts
        self.db.update_poll_data(poll_id, opts)

        pkt = {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "poll_vote",
            "poll_id": poll_id,
            "option_id": option_id,
            "user_id": self.user_id,
            "user_name": user,
            "timestamp": time.time(),
        }
        self._send_raw_packet(pkt)

        if self.on_poll_updated:
            self.on_poll_updated(target_poll)
        return True

    def toggle_reaction(self, msg_id, emoji):
        """
        Toggles an emoji reaction from the current user on message msg_id.
        Updates SQLite and broadcasts reaction packet across LAN.
        """
        updated_reactions = None
        with self.lock:
            for m in self.messages:
                if m.get("id") == msg_id:
                    if "reactions" not in m or not isinstance(m["reactions"], dict):
                        m["reactions"] = {}
                    rx = m["reactions"]
                    users = rx.get(emoji, [])
                    if self.user_name in users:
                        users.remove(self.user_name)
                        if not users:
                            rx.pop(emoji, None)
                        else:
                            rx[emoji] = users
                    else:
                        users.append(self.user_name)
                        rx[emoji] = users
                    updated_reactions = dict(rx)
                    self.db.update_reactions(msg_id, updated_reactions)
                    break

        if updated_reactions is not None:
            pkt = {
                "v": 1,
                "id": uuid.uuid4().hex[:12],
                "type": "reaction",
                "sender_id": self.user_id,
                "user_name": self.user_name,
                "msg_id": msg_id,
                "emoji": emoji,
                "timestamp": time.time()
            }
            self._send_raw_packet(pkt)
            if self.on_reaction:
                self.on_reaction(msg_id, updated_reactions)

    def download_file(self, msg_obj, target_dir=None, custom_save_path=None,
                      on_progress=None, on_done=None, on_error=None, cancel_event=None):
        """Asynchronously streams a file from the sender's HTTP file server with speed calculation & cancellation."""
        def _worker():
            try:
                f_ip = msg_obj.get("file_ip") or msg_obj.get("sender_ip")
                f_port = msg_obj.get("file_port")
                f_id = msg_obj.get("file_id")
                f_name = msg_obj.get("file_name", "downloaded_file")
                if not f_ip or not f_port or not f_id:
                    raise ValueError("Connection details missing for this file.")

                if custom_save_path:
                    dest = custom_save_path
                else:
                    base_dir = target_dir or os.path.expanduser("~/Downloads/WorkPulse_Files")
                    os.makedirs(base_dir, exist_ok=True)
                    dest = os.path.join(base_dir, f_name)
                    base, ext = os.path.splitext(f_name)
                    idx = 1
                    while os.path.exists(dest):
                        dest = os.path.join(base_dir, f"{base}_{idx}{ext}")
                        idx += 1

                url = f"http://{f_ip}:{f_port}/files/{f_id}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=45) as resp:
                    total_bytes = int(resp.headers.get("Content-Length", 0))
                    read_bytes = 0
                    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
                    tmp_dest = dest + ".wp_part"
                    t_start = time.time()
                    last_calc_t = t_start
                    last_calc_b = 0
                    current_spd = 0.0

                    with open(tmp_dest, "wb") as f_out:
                        while True:
                            if cancel_event and cancel_event.is_set():
                                f_out.close()
                                if os.path.exists(tmp_dest):
                                    try:
                                        os.remove(tmp_dest)
                                    except Exception:
                                        pass
                                if on_error:
                                    on_error("Download cancelled by user.")
                                return

                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            read_bytes += len(chunk)

                            now_t = time.time()
                            if now_t - last_calc_t >= 0.2:
                                current_spd = (read_bytes - last_calc_b) / max(0.001, (now_t - last_calc_t))
                                last_calc_t = now_t
                                last_calc_b = read_bytes

                            eta_s = (total_bytes - read_bytes) / current_spd if current_spd > 0 and total_bytes > read_bytes else 0.0

                            if on_progress and total_bytes > 0:
                                try:
                                    on_progress(read_bytes, total_bytes, current_spd, eta_s)
                                except TypeError:
                                    on_progress(read_bytes, total_bytes)

                    if os.path.exists(dest):
                        os.remove(dest)
                    os.rename(tmp_dest, dest)

                # Persist downloaded path to SQLite
                self.db.update_local_path(msg_obj["id"], dest)
                msg_obj["local_path"] = dest

                with self.lock:
                    self.shared_files[f_id] = {"path": dest, "name": f_name, "size": read_bytes}

                if on_done:
                    on_done(dest)
            except Exception as e:
                if on_error:
                    on_error(str(e))

        threading.Thread(target=_worker, daemon=True, name="LANChat-FileDownload").start()

    def send_broadcast_message(self, text, **kwargs):
        """Sends a broadcast chat message to all peers (mobile compatibility alias)."""
        return self.send_chat_message(text, **kwargs)

    def send_work_update(self, title_or_date, date_str_or_tasks=None, tasks=None, shift_str="", total_hours=""):
        """Sends a structured Work Update card to the team."""
        # Handle flexible call signatures: (date_str, tasks) or (title, date_str, tasks, shift, hours)
        if tasks is None and isinstance(date_str_or_tasks, list):
            date_str = str(title_or_date)
            tasks = date_str_or_tasks
            title = "Daily Work Update"
        else:
            title = str(title_or_date or "Daily Work Update")
            date_str = str(date_str_or_tasks or datetime.date.today().strftime("%Y-%m-%d"))
            tasks = tasks or []
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        pkt_id = uuid.uuid4().hex[:12]

        msg_obj = {
            "v": 1,
            "id": pkt_id,
            "type": "work_update",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "avatar_color": self.avatar_color,
            "title": title or "Today's Work Summary",
            "date_str": date_str,
            "tasks": tasks,
            "shift_str": shift_str,
            "total_hours": total_hours,
            "time_str": time_str,
            "timestamp": time.time(),
            "is_me": True
        }

        with self.lock:
            self._record_seen_packet(pkt_id)
            self.messages.append(msg_obj)
            self.save_history(msg_obj)

        self._send_raw_packet(msg_obj)

        if self.on_message:
            self.on_message(msg_obj)

        return msg_obj

    def delete_message(self, msg_id, broadcast=True):
        """Removes message from local memory, SQLite database, and optionally broadcasts deletion across LAN."""
        if not msg_id:
            return False

        with self.lock:
            self.messages = [m for m in self.messages if m.get("id") != msg_id]

        self.db.delete_message(msg_id)

        if broadcast:
            del_pkt = {
                "v": 1,
                "id": uuid.uuid4().hex[:12],
                "type": "delete_message",
                "sender_id": self.user_id,
                "target_msg_id": msg_id,
                "timestamp": time.time()
            }
            self._send_raw_packet(del_pkt)

        if self.on_message_deleted:
            self.on_message_deleted(msg_id)

        return True

    def get_online_peers(self):
        """Returns sorted list of currently active online peers."""
        with self.lock:
            return sorted(self.peers.values(), key=lambda p: p["user_name"].lower())

    def clear_history(self):
        """Empties message history from memory and SQLite database."""
        with self.lock:
            self.messages = []
            self.db.clear_all()

    def load_history(self):
        """Loads previous chat history from SQLite database."""
        self.messages = self.db.load_recent_messages(limit=MAX_HISTORY_ITEMS)

    def save_history(self, msg_obj=None):
        """Persists chat history to SQLite database."""
        if msg_obj:
            self.db.save_message(msg_obj)
        elif self.messages:
            self.db.save_message(self.messages[-1])

    def search_history(self, query, limit=50):
        """Searches past chat messages in SQLite database."""
        return self.db.search_messages(query, limit=limit)

    def _build_beacon_packet(self, is_ack=False):
        return {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "beacon_ack" if is_ack else "beacon",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "hostname": self.hostname,
            "ip": self.local_ip,
            "port": self.port,
            "file_port": self.file_server_port,
            "status": self.status,
            "status_emoji": self.status_emoji,
            "status_note": self.status_note,
            "avatar_color": self.avatar_color,
            "timestamp": time.time()
        }

    def _broadcast_beacon(self):
        pkt = self._build_beacon_packet(is_ack=False)
        self._send_raw_packet(pkt)

    def _send_raw_packet(self, pkt_dict):
        try:
            data = json.dumps(pkt_dict).encode("utf-8")
        except Exception:
            return

        for bcast in self.broadcast_addrs:
            try:
                self.tx_sock.sendto(data, (bcast, DEFAULT_LAN_PORT))
            except Exception:
                pass

        with self.lock:
            peer_endpoints = [(p["ip"], p["port"]) for p in self.peers.values()]
            custom_targets = list(self.custom_ips)

        for ip, port in peer_endpoints:
            try:
                if ip and (ip != self.local_ip or port != self.port):
                    self.tx_sock.sendto(data, (ip, port))
            except Exception:
                pass

        for c_ip in custom_targets:
            try:
                self.tx_sock.sendto(data, (c_ip, DEFAULT_LAN_PORT))
            except Exception:
                pass

    def _record_seen_packet(self, pkt_id):
        if not pkt_id:
            return False
        if pkt_id in self.seen_packet_ids:
            return True
        self.seen_packet_ids[pkt_id] = time.time()
        if len(self.seen_packet_ids) > 2000:
            self.seen_packet_ids.popitem(last=False)
        return False

    def _listen_loop(self):
        """Continuously listens for incoming UDP packets on LAN."""
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                if not data:
                    continue
                try:
                    pkt = json.loads(data.decode("utf-8"))
                except Exception:
                    continue

                self._process_packet(pkt, addr)
            except (socket.timeout, select.error):
                continue
            except Exception:
                if not self.running:
                    break
                time.sleep(0.1)

    def _process_packet(self, pkt, addr):
        sender_id = pkt.get("sender_id")
        pkt_id = pkt.get("id")
        pkt_type = pkt.get("type")

        if sender_id == self.user_id:
            return

        with self.lock:
            if self._record_seen_packet(pkt_id):
                return

        peer_ip = pkt.get("ip") or addr[0]
        peer_port = pkt.get("port") or addr[1]

        if pkt_type in ("beacon", "beacon_ack"):
            is_new = False
            with self.lock:
                if sender_id not in self.peers:
                    is_new = True
                self.peers[sender_id] = {
                    "id": sender_id,
                    "user_name": pkt.get("user_name", "Colleague"),
                    "hostname": pkt.get("hostname", "Device"),
                    "ip": peer_ip,
                    "port": peer_port,
                    "file_port": pkt.get("file_port", 0),
                    "status": pkt.get("status", "Available"),
                    "status_emoji": pkt.get("status_emoji", "🟢"),
                    "status_note": pkt.get("status_note", ""),
                    "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                    "last_seen": time.time()
                }

            if is_new and pkt_type == "beacon":
                ack_pkt = self._build_beacon_packet(is_ack=True)
                try:
                    self._send_raw_packet(ack_pkt)
                except Exception:
                    pass

            if self.on_peers_change:
                self.on_peers_change(self.get_online_peers())

        elif pkt_type == "status_update":
            with self.lock:
                if sender_id in self.peers:
                    self.peers[sender_id]["status"] = pkt.get("status", "Available")
                    self.peers[sender_id]["status_emoji"] = pkt.get("status_emoji", "🟢")
                    self.peers[sender_id]["status_note"] = pkt.get("status_note", "")
                    self.peers[sender_id]["last_seen"] = time.time()
            if self.on_peers_change:
                self.on_peers_change(self.get_online_peers())

        elif pkt_type == "chat":
            recipient_id = pkt.get("recipient_id", "") or ""
            recipient_name = pkt.get("recipient_name", "") or ""
            if recipient_id and recipient_id != self.user_id:
                return

            text = pkt.get("text", "")
            my_tag = f"@{self.user_name.lower()}"
            is_mentioned = bool("@all" in text.lower() or "@team" in text.lower() or my_tag in text.lower())

            msg_obj = {
                "v": 1,
                "id": pkt_id,
                "type": "chat",
                "sender_id": sender_id,
                "user_name": pkt.get("user_name", "Colleague"),
                "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                "text": text,
                "time_str": pkt.get("time_str", datetime.datetime.now().strftime("%I:%M %p")),
                "timestamp": pkt.get("timestamp", time.time()),
                "is_me": False,
                "reply_to": pkt.get("reply_to"),
                "reactions": pkt.get("reactions") or {},
                "recipient_id": recipient_id,
                "recipient_name": recipient_name,
                "is_pinned": bool(pkt.get("is_pinned", False)),
                "mentioned_me": is_mentioned
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history(msg_obj)

            if recipient_id:
                notif_title = f"🔒 Direct Message • {msg_obj['user_name']}"
            elif is_mentioned:
                notif_title = f"🔔 Mentioned by {msg_obj['user_name']}"
            else:
                notif_title = f"WorkPulse LAN • {msg_obj['user_name']}"

            show_desktop_notification(
                title=notif_title,
                message=msg_obj["text"]
            )

            if self.on_message:
                self.on_message(msg_obj)

        elif pkt_type == "file":
            recipient_id = pkt.get("recipient_id", "") or ""
            recipient_name = pkt.get("recipient_name", "") or ""
            if recipient_id and recipient_id != self.user_id:
                return

            f_name = pkt.get("file_name", "shared_file")
            f_size = pkt.get("file_size", 0)
            f_size_str = pkt.get("file_size_str") or format_file_size(f_size)
            is_img = bool(pkt.get("is_image")) or is_image_file(f_name)
            caption = pkt.get("caption", "")

            my_tag = f"@{self.user_name.lower()}"
            is_mentioned = bool("@all" in caption.lower() or "@team" in caption.lower() or my_tag in caption.lower())

            msg_obj = {
                "v": 1,
                "id": pkt_id,
                "type": "file",
                "is_image": is_img,
                "sender_id": sender_id,
                "user_name": pkt.get("user_name", "Colleague"),
                "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                "file_id": pkt.get("file_id", ""),
                "file_name": f_name,
                "file_size": f_size,
                "file_size_str": f_size_str,
                "file_ip": pkt.get("file_ip") or peer_ip,
                "file_port": pkt.get("file_port", 0),
                "local_path": "",
                "text": pkt.get("text", f"Shared file: {f_name} ({f_size_str})"),
                "caption": caption,
                "time_str": pkt.get("time_str", datetime.datetime.now().strftime("%I:%M %p")),
                "timestamp": pkt.get("timestamp", time.time()),
                "is_me": False,
                "reply_to": pkt.get("reply_to"),
                "reactions": pkt.get("reactions") or {},
                "recipient_id": recipient_id,
                "recipient_name": recipient_name,
                "is_pinned": bool(pkt.get("is_pinned", False)),
                "mentioned_me": is_mentioned
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history(msg_obj)

            notif_msg = f"Shared photo: {f_name}" if is_img else f"Shared a file: {f_name} ({f_size_str})"
            if recipient_id:
                notif_title = f"🔒 Direct File • {msg_obj['user_name']}"
            elif is_mentioned:
                notif_title = f"🔔 Mentioned by {msg_obj['user_name']}"
            else:
                notif_title = f"WorkPulse LAN • {msg_obj['user_name']}"

            show_desktop_notification(
                title=notif_title,
                message=notif_msg
            )

            if self.on_message:
                self.on_message(msg_obj)

        elif pkt_type == "pin_announcement":
            action = pkt.get("action", "pin")
            if action == "pin":
                pin_obj = pkt.get("pin_obj")
                if pin_obj:
                    self.pinned_announcement = pin_obj
                    self.db.save_pinned_announcement(pin_obj)
                    if pin_obj.get("msg_id"):
                        with self.lock:
                            for m in self.messages:
                                if m.get("id") == pin_obj["msg_id"]:
                                    m["is_pinned"] = True
                        self.db.update_is_pinned(pin_obj["msg_id"], True)
                    if self.on_pinned_change:
                        self.on_pinned_change(pin_obj)
            elif action == "unpin":
                if self.pinned_announcement and self.pinned_announcement.get("msg_id"):
                    mid = self.pinned_announcement["msg_id"]
                    with self.lock:
                        for m in self.messages:
                            if m.get("id") == mid:
                                m["is_pinned"] = False
                    self.db.update_is_pinned(mid, False)
                self.pinned_announcement = None
                self.db.clear_pinned_announcements()
                if self.on_pinned_change:
                    self.on_pinned_change(None)

        elif pkt_type == "work_update":
            msg_obj = {
                "v": 1,
                "id": pkt_id,
                "type": "work_update",
                "sender_id": sender_id,
                "user_name": pkt.get("user_name", "Colleague"),
                "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                "title": pkt.get("title", "Work Update"),
                "date_str": pkt.get("date_str", ""),
                "tasks": pkt.get("tasks", []),
                "shift_str": pkt.get("shift_str", ""),
                "total_hours": pkt.get("total_hours", ""),
                "time_str": pkt.get("time_str", datetime.datetime.now().strftime("%I:%M %p")),
                "timestamp": pkt.get("timestamp", time.time()),
                "is_me": False,
                "reply_to": pkt.get("reply_to"),
                "reactions": pkt.get("reactions") or {}
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history(msg_obj)

            show_desktop_notification(
                title=f"WorkPulse LAN • {msg_obj['user_name']}",
                message=f"Shared Work Log: {msg_obj['title']}"
            )

            if self.on_message:
                self.on_message(msg_obj)

        elif pkt_type == "reaction":
            r_msg_id = pkt.get("msg_id")
            emoji = pkt.get("emoji")
            reactor = pkt.get("user_name", "Colleague")
            updated_reactions = None

            with self.lock:
                for m in self.messages:
                    if m.get("id") == r_msg_id:
                        if "reactions" not in m or not isinstance(m["reactions"], dict):
                            m["reactions"] = {}
                        rx = m["reactions"]
                        users = rx.get(emoji, [])
                        if reactor in users:
                            users.remove(reactor)
                            if not users:
                                rx.pop(emoji, None)
                            else:
                                rx[emoji] = users
                        else:
                            users.append(reactor)
                            rx[emoji] = users
                        updated_reactions = dict(rx)
                        self.db.update_reactions(r_msg_id, updated_reactions)
                        break

            if updated_reactions is not None and self.on_reaction:
                self.on_reaction(r_msg_id, updated_reactions)

        elif pkt_type == "delete_message":
            target_id = pkt.get("target_msg_id")
            if target_id:
                with self.lock:
                    self.messages = [m for m in self.messages if m.get("id") != target_id]
                self.db.delete_message(target_id)
                if self.on_message_deleted:
                    self.on_message_deleted(target_id)

        elif pkt_type == "poll":
            recipient_id = pkt.get("recipient_id", "") or ""
            recipient_name = pkt.get("recipient_name", "") or ""
            if recipient_id and recipient_id != self.user_id:
                return

            question = pkt.get("question", "Team Poll")
            options = pkt.get("options", [])

            msg_obj = {
                "v": 1,
                "id": pkt_id,
                "type": "poll",
                "sender_id": sender_id,
                "user_name": pkt.get("user_name", "Colleague"),
                "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                "text": question,
                "title": question,
                "tasks": options,
                "time_str": pkt.get("time_str", datetime.datetime.now().strftime("%I:%M %p")),
                "timestamp": pkt.get("timestamp", time.time()),
                "date_str": datetime.datetime.fromtimestamp(pkt.get("timestamp", time.time())).strftime("%Y-%m-%d"),
                "is_me": False,
                "recipient_id": recipient_id,
                "recipient_name": recipient_name,
                "reactions": {},
                "is_pinned": False,
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history(msg_obj)

            show_desktop_notification(
                title=f"🗳️ LAN Poll • {msg_obj['user_name']}",
                message=f"New Poll: {question}"
            )

            if self.on_message:
                self.on_message(msg_obj)

        elif pkt_type == "poll_vote":
            poll_id = pkt.get("poll_id")
            option_id = pkt.get("option_id")
            voter = pkt.get("user_name", "Colleague")

            target_poll = None
            with self.lock:
                for m in self.messages:
                    if m.get("id") == poll_id:
                        target_poll = m
                        break

            if not target_poll:
                recent = self.db.load_recent_messages(limit=100)
                for m in recent:
                    if m.get("id") == poll_id:
                        target_poll = m
                        with self.lock:
                            self.messages.append(target_poll)
                        break

            if target_poll:
                opts = target_poll.get("tasks") or []
                already_voted_this = False
                for opt in opts:
                    if opt.get("id") == option_id and voter in opt.get("votes", []):
                        already_voted_this = True
                        break

                for opt in opts:
                    votes = opt.setdefault("votes", [])
                    if voter in votes:
                        votes.remove(voter)
                    if not already_voted_this and opt.get("id") == option_id:
                        votes.append(voter)

                target_poll["tasks"] = opts
                self.db.update_poll_data(poll_id, opts)

                if self.on_poll_updated:
                    self.on_poll_updated(target_poll)

        elif pkt_type == "leave":
            with self.lock:
                if sender_id in self.peers:
                    del self.peers[sender_id]
            if self.on_peers_change:
                self.on_peers_change(self.get_online_peers())

    def _beacon_loop(self):
        while self.running:
            try:
                self._broadcast_beacon()
            except Exception:
                pass
            time.sleep(BEACON_INTERVAL)

    def _cleanup_loop(self):
        while self.running:
            time.sleep(2.0)
            now = time.time()
            expired = []
            with self.lock:
                for pid, pinfo in self.peers.items():
                    if now - pinfo["last_seen"] > PEER_TIMEOUT:
                        expired.append(pid)
                for pid in expired:
                    del self.peers[pid]

            if expired and self.on_peers_change:
                self.on_peers_change(self.get_online_peers())


# ==============================================================================
# LAN Team Chat Modern UI Dialog
# ==============================================================================

class LANChatDialog:
    """
    Modern desktop chat dialog with:
      - High-DPI readable typography & spacious modern UI layout
      - Split pane: Colleague Presence Sidebar + Real-Time Chat Stream
      - Interactive status changer (Available, Lunch, Focus, etc.)
      - High-speed peer-to-peer LAN File Sharing (any format/size)
      - Instant 'Share Today's Tasks' work update integration
      - Live desktop system notifications & in-app floating toasts
      - Colleague IP manual connect for enterprise/restricted Wi-Fi
    """
    def __init__(self, parent, engine, app_ref=None):
        self.parent = parent
        self.engine = engine
        self.app_ref = app_ref

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("WorkPulse - LAN Team Chat (Same Wi-Fi Network)")
        self.dialog.configure(bg="#0f172a")

        # Responsive window sizing & auto-center with comfortable dimensions
        center_window(self.dialog, parent, default_w=1080, default_h=720, min_w=860, min_h=560)

        # Message widget tracking for real-time deletion
        self.msg_widgets = {}
        self.active_reply = None
        self.pending_image = None
        self._photo_cache = {}
        self.reaction_containers = {}
        self.active_picker = None
        self.tooltip_window = None
        self.sound_muted = False

        # 1-on-1 Direct Message & Mentions Autocomplete state
        self.active_dm_peer = None
        self.unread_dms = {}
        self.mention_popup = None
        self.mention_listbox = None
        self.mention_candidates = []

        # In-Chat Quick Find (Ctrl+F) state
        self.find_matches = []
        self.find_index = -1

        self._build_header()
        self._build_body()
        self._populate_initial_data()

        # Wire engine callbacks to this dialog only after all UI widgets exist
        self.engine.on_message = self._on_engine_message
        self.engine.on_peers_change = self._on_engine_peers_change
        self.engine.on_message_deleted = self._on_engine_message_deleted
        self.engine.on_reaction = self._on_engine_reaction
        self.engine.on_pinned_change = self._on_engine_pinned_change
        self.engine.on_poll_updated = self._on_engine_poll_updated

        # Reset title on window focus
        def _on_focus(event):
            self.dialog.title("WorkPulse - LAN Team Chat (Same Wi-Fi Network)")
        self.dialog.bind("<FocusIn>", _on_focus)

        # Keyboard shortcuts
        def _on_escape(e):
            if hasattr(self, "find_bar") and self.find_bar.winfo_viewable():
                self._close_find_bar()
            elif self.mention_popup and self.mention_popup.winfo_exists():
                self._close_mention_popup()
            elif self.active_reply or self.pending_image:
                if self.active_reply:
                    self._cancel_reply()
                if self.pending_image:
                    self._cancel_pending_image()
            else:
                self.dialog.destroy()
        self.dialog.bind("<Escape>", _on_escape)
        self.dialog.bind("<Control-f>", lambda e: (self._toggle_find_bar(), "break")[1])
        self.dialog.bind("<Control-F>", lambda e: (self._toggle_find_bar(), "break")[1])

        # Clean-up on close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.engine.on_message_deleted = None
        self.engine.on_reaction = None
        self.engine.on_pinned_change = None
        self._close_mention_popup()
        if self.active_picker and self.active_picker.winfo_exists():
            try:
                self.active_picker.destroy()
            except Exception:
                pass
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass

        if self.app_ref and hasattr(self.app_ref, "_handle_background_lan_message"):
            self.engine.on_message = self.app_ref._handle_background_lan_message
            self.engine.on_peers_change = self.app_ref._handle_lan_peers_change
        else:
            self.engine.on_message = None
            self.engine.on_peers_change = None

        if self.app_ref and hasattr(self.app_ref, "chat_dialog"):
            self.app_ref.chat_dialog = None
        self.dialog.destroy()

    def _build_header(self):
        """Top branding & network status header bar."""
        header = tk.Frame(self.dialog, bg="#1e293b", padx=18, pady=12)
        header.pack(fill=tk.X, side=tk.TOP)

        # Right Action Buttons
        right_box = tk.Frame(header, bg="#1e293b")
        right_box.pack(side=tk.RIGHT)

        btn_search = tk.Button(
            right_box,
            text="🔍 Search",
            font=font_spec(11, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._prompt_search_dialog
        )
        btn_search.pack(side=tk.LEFT, padx=3)

        btn_add_ip = tk.Button(
            right_box,
            text="➕ Add IP",
            font=font_spec(11, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._prompt_add_colleague_ip
        )
        btn_add_ip.pack(side=tk.LEFT, padx=3)

        btn_clear = tk.Button(
            right_box,
            text="🧹 Clear",
            font=font_spec(11, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._clear_chat_history
        )
        btn_clear.pack(side=tk.LEFT, padx=3)

        self.btn_export = tk.Button(
            right_box,
            text="📥 Export",
            font=font_spec(11, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._prompt_export_chat
        )
        self.btn_export.pack(side=tk.LEFT, padx=3)

        self.btn_sound = tk.Button(
            right_box,
            text="🔔 Sound",
            font=font_spec(11, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._toggle_sound_mute
        )
        self.btn_sound.pack(side=tk.LEFT, padx=3)

        # Left branding
        left_box = tk.Frame(header, bg="#1e293b")
        left_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title_lbl = tk.Label(
            left_box,
            text="💬 LAN Team Chat",
            font=font_spec(16, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        )
        title_lbl.pack(anchor="w")

        file_port_str = f" • File Port: {self.engine.file_server_port}" if self.engine.file_server_port else ""
        net_text = f"🟢 Local Subnet • IP: {self.engine.local_ip}:{self.engine.port}{file_port_str} • 💾 SQLite Active"
        self.lbl_net_info = tk.Label(
            left_box,
            text=net_text,
            font=font_spec(11),
            fg="#94a3b8",
            bg="#1e293b"
        )
        self.lbl_net_info.pack(anchor="w", pady=(2, 0))

    def _build_body(self):
        """Split layout: Left Sidebar (Presence) + Right Area (Chat stream)."""
        body = tk.Frame(self.dialog, bg="#0f172a")
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        # ----------------- LEFT SIDEBAR: PEER PRESENCE -----------------
        sidebar = tk.Frame(body, bg="#1e293b", width=340, bd=1, relief="solid")
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar.pack_propagate(False)

        # My Profile Card
        my_card = tk.Frame(sidebar, bg="#334155", padx=10, pady=10)
        my_card.pack(fill=tk.X, padx=8, pady=8)

        my_top = tk.Frame(my_card, bg="#334155")
        my_top.pack(fill=tk.X)

        self.my_avatar_lbl = tk.Label(
            my_top,
            text=get_initials(self.engine.user_name),
            font=font_spec(11, "bold"),
            fg="#ffffff",
            bg=self.engine.avatar_color,
            width=3,
            height=1,
            relief="flat"
        )
        self.my_avatar_lbl.pack(side=tk.LEFT, padx=(0, 6))

        my_info = tk.Frame(my_top, bg="#334155")
        my_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        my_name_lbl = tk.Label(
            my_info,
            text=f"{self.engine.user_name} (You)",
            font=font_spec(12, "bold"),
            fg="#ffffff",
            bg="#334155",
            anchor="w"
        )
        my_name_lbl.pack(fill=tk.X, expand=True)

        # Status Dropdown
        status_frame = tk.Frame(my_card, bg="#334155")
        status_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(status_frame, text="My Status:", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#334155").pack(anchor="w")
        self.status_var = tk.StringVar(value=f"{self.engine.status_emoji} {self.engine.status}")
        self.combo_status = ttk.Combobox(
            status_frame,
            textvariable=self.status_var,
            values=[opt[0] for opt in STATUS_CHOICES],
            state="readonly",
            font=font_spec(11)
        )
        self.combo_status.pack(fill=tk.X, pady=(4, 0))
        self.combo_status.bind("<<ComboboxSelected>>", self._on_status_changed)

        # Custom Status Note Entry
        self.status_note_var = tk.StringVar(value=self.engine.status_note)
        self.entry_status_note = tk.Entry(
            status_frame,
            textvariable=self.status_note_var,
            font=font_spec(10),
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#ffffff",
            relief="flat",
            bd=3
        )
        self.entry_status_note.pack(fill=tk.X, pady=(5, 0), ipady=2)
        self.entry_status_note.bind("<Return>", self._on_status_note_submitted)
        self.entry_status_note.bind("<FocusOut>", self._on_status_note_submitted)

        # Channels Section Heading
        chan_header = tk.Frame(sidebar, bg="#1e293b", padx=10, pady=6)
        chan_header.pack(fill=tk.X)

        tk.Label(
            chan_header,
            text="CHANNELS",
            font=font_spec(10, "bold"),
            fg="#94a3b8",
            bg="#1e293b"
        ).pack(anchor="w")

        # Team Public Room Card
        self.card_public_room = tk.Frame(sidebar, bg="#2563eb", padx=10, pady=8, bd=1, relief="solid", cursor="hand2")
        self.card_public_room.pack(fill=tk.X, padx=8, pady=(0, 6))

        r_icon = tk.Label(self.card_public_room, text="🌐", font=font_spec(12), bg="#2563eb", fg="#ffffff", cursor="hand2")
        r_icon.pack(side=tk.LEFT, padx=(0, 6))
        self.lbl_public_name = tk.Label(self.card_public_room, text="# team-general", font=font_spec(11, "bold"), bg="#2563eb", fg="#ffffff", cursor="hand2")
        self.lbl_public_name.pack(side=tk.LEFT)

        self.card_public_room.bind("<Button-1>", lambda e: self._select_team_room())
        r_icon.bind("<Button-1>", lambda e: self._select_team_room())
        self.lbl_public_name.bind("<Button-1>", lambda e: self._select_team_room())

        # Online Peers Section Heading
        peer_header = tk.Frame(sidebar, bg="#1e293b", padx=10, pady=4)
        peer_header.pack(fill=tk.X)

        self.lbl_peer_count = tk.Label(
            peer_header,
            text="TEAM ON WI-FI (0)",
            font=font_spec(10, "bold"),
            fg="#94a3b8",
            bg="#1e293b",
            anchor="w"
        )
        self.lbl_peer_count.pack(fill=tk.X, expand=True)

        # Scrollable Peers Container
        peers_canvas_frame = tk.Frame(sidebar, bg="#1e293b")
        peers_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        self.peers_canvas = tk.Canvas(peers_canvas_frame, bg="#1e293b", highlightthickness=0)
        self.peers_scroll = ttk.Scrollbar(peers_canvas_frame, orient=tk.VERTICAL, command=self.peers_canvas.yview)
        self.peers_inner = tk.Frame(self.peers_canvas, bg="#1e293b")

        self.peers_canvas.configure(yscrollcommand=self.peers_scroll.set)
        self.peers_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.peers_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.peers_win = self.peers_canvas.create_window((0, 0), window=self.peers_inner, anchor="nw")

        def _on_peers_inner_cfg(event):
            self.peers_canvas.configure(scrollregion=self.peers_canvas.bbox("all"))
        self.peers_inner.bind("<Configure>", _on_peers_inner_cfg)

        def _on_peers_canvas_cfg(event):
            self.peers_canvas.itemconfig(self.peers_win, width=event.width)
        self.peers_canvas.bind("<Configure>", _on_peers_canvas_cfg)

        # ----------------- RIGHT CHAT STREAM -----------------
        chat_box = tk.Frame(body, bg="#1e293b", bd=1, relief="solid")
        chat_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Top Dynamic Room Bar
        self.room_bar = tk.Frame(chat_box, bg="#0f172a", padx=14, pady=8)
        self.room_bar.pack(fill=tk.X, side=tk.TOP)

        self.btn_back_to_room = tk.Button(
            self.room_bar,
            text="🌐 Back to Team Room",
            font=font_spec(10, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._select_team_room
        )
        # (Packed only when in DM)

        # Quick Find trigger button in room bar
        self.btn_quick_find = tk.Button(
            self.room_bar,
            text="🔍 Find (Ctrl+F)",
            font=font_spec(10, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._toggle_find_bar
        )
        self.btn_quick_find.pack(side=tk.RIGHT, padx=4)

        left_room_f = tk.Frame(self.room_bar, bg="#0f172a")
        left_room_f.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_room_title = tk.Label(
            left_room_f,
            text="# team-general",
            font=font_spec(13, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        )
        self.lbl_room_title.pack(side=tk.LEFT)

        self.lbl_room_sub = tk.Label(
            left_room_f,
            text="• Local Wi-Fi broadcast • Real-time across devices",
            font=font_spec(11),
            fg="#64748b",
            bg="#0f172a"
        )
        self.lbl_room_sub.pack(side=tk.LEFT, padx=8)

        # Top Pinned Announcement Banner (Under Room Bar)
        self.pin_banner = tk.Frame(chat_box, bg="#1e293b", bd=1, relief="solid", padx=12, pady=6)

        # Quick Find (Ctrl+F) In-Chat Search Bar
        self.find_bar = tk.Frame(chat_box, bg="#1e293b", bd=1, relief="solid", padx=10, pady=5)
        # (Packed dynamically above self.msg_canvas_box when active)

        lbl_f_icon = tk.Label(self.find_bar, text="🔍", font=font_spec(11), fg="#38bdf8", bg="#1e293b")
        lbl_f_icon.pack(side=tk.LEFT, padx=(0, 6))

        self.entry_find = tk.Entry(
            self.find_bar,
            font=font_spec(11),
            bg="#0f172a",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=3
        )
        self.entry_find.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)
        self.entry_find.bind("<KeyRelease>", self._on_find_key_release)
        self.entry_find.bind("<Return>", lambda e: self._find_next())
        self.entry_find.bind("<Shift-Return>", lambda e: self._find_prev())
        self.entry_find.bind("<Escape>", lambda e: (self._close_find_bar(), "break")[1])

        self.lbl_find_count = tk.Label(self.find_bar, text="0 matches", font=font_spec(10, "bold"), fg="#94a3b8", bg="#1e293b")
        self.lbl_find_count.pack(side=tk.LEFT, padx=(0, 8))

        btn_f_prev = tk.Button(
            self.find_bar,
            text="▲ Prev",
            font=font_spec(9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._find_prev
        )
        btn_f_prev.pack(side=tk.LEFT, padx=2)

        btn_f_next = tk.Button(
            self.find_bar,
            text="▼ Next",
            font=font_spec(9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._find_next
        )
        btn_f_next.pack(side=tk.LEFT, padx=2)

        btn_f_close = tk.Button(
            self.find_bar,
            text="✕",
            font=font_spec(10, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#f87171",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._close_find_bar
        )
        btn_f_close.pack(side=tk.LEFT, padx=(4, 0))

        # Scrollable Messages Canvas
        self.msg_canvas_box = tk.Frame(chat_box, bg="#0f172a")
        self.msg_canvas_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.msg_canvas = tk.Canvas(self.msg_canvas_box, bg="#0f172a", highlightthickness=0)
        self.msg_scroll = ttk.Scrollbar(self.msg_canvas_box, orient=tk.VERTICAL, command=self.msg_canvas.yview)
        self.msg_inner = tk.Frame(self.msg_canvas, bg="#0f172a")

        self.msg_canvas.configure(yscrollcommand=self.msg_scroll.set)
        self.msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.msg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.msg_win = self.msg_canvas.create_window((0, 0), window=self.msg_inner, anchor="nw")

        def _on_msg_inner_cfg(event):
            self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox("all"))
        self.msg_inner.bind("<Configure>", _on_msg_inner_cfg)

        def _on_msg_canvas_cfg(event):
            self.msg_canvas.itemconfig(self.msg_win, width=event.width)
        self.msg_canvas.bind("<Configure>", _on_msg_canvas_cfg)

        # Mousewheel scroll support
        def _on_mousewheel(event):
            if event.num == 4:
                self.msg_canvas.yview_scroll(-2, "units")
            elif event.num == 5:
                self.msg_canvas.yview_scroll(2, "units")
            elif event.delta:
                self.msg_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.msg_canvas.bind("<Button-4>", _on_mousewheel)
        self.msg_canvas.bind("<Button-5>", _on_mousewheel)
        self.msg_canvas.bind("<MouseWheel>", _on_mousewheel)

        # Bottom Dock Container (Holds Reply Bar, Pending Screenshot Bar, and Input Dock)
        self.bottom_dock_container = tk.Frame(chat_box, bg="#1e293b")
        self.bottom_dock_container.pack(fill=tk.X, side=tk.BOTTOM)

        # 1. Floating Quoted Reply Dock
        self.reply_dock = tk.Frame(self.bottom_dock_container, bg="#0f172a", bd=1, relief="solid", padx=12, pady=6)
        # (Packed only when replying)

        # 2. Floating Clipboard Screenshot Preview Dock
        self.clip_dock = tk.Frame(self.bottom_dock_container, bg="#0f172a", bd=1, relief="solid", padx=12, pady=6)
        # (Packed only when screenshot is attached)

        # 3. Main Input Dock
        input_dock = tk.Frame(self.bottom_dock_container, bg="#1e293b", padx=12, pady=10)
        input_dock.pack(fill=tk.X, side=tk.BOTTOM)

        # Send Button (Pack RIGHT first)
        btn_send = tk.Button(
            input_dock,
            text="✈️ Send",
            font=font_spec(11, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._send_message
        )
        btn_send.pack(side=tk.RIGHT, padx=(4, 0))

        # Share Today's Tasks Button
        btn_share_tasks = tk.Button(
            input_dock,
            text="📋 Share Tasks",
            font=font_spec(11, "bold"),
            bg="#8b5cf6",
            fg="white",
            activebackground="#7c3aed",
            activeforeground="white",
            relief="flat",
            padx=13,
            pady=6,
            cursor="hand2",
            command=self._share_today_tasks_to_chat
        )
        btn_share_tasks.pack(side=tk.RIGHT, padx=3)

        # Share File Button
        btn_share_file = tk.Button(
            input_dock,
            text="📎 File",
            font=font_spec(11, "bold"),
            bg="#0284c7",
            fg="white",
            activebackground="#0369a1",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._share_file_to_chat
        )
        btn_share_file.pack(side=tk.RIGHT, padx=3)

        # Paste Image / Screenshot Button
        btn_paste_img = tk.Button(
            input_dock,
            text="📷 Paste",
            font=font_spec(11, "bold"),
            bg="#059669",
            fg="white",
            activebackground="#047857",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._paste_clipboard_image
        )
        btn_paste_img.pack(side=tk.RIGHT, padx=3)

        # Team Poll Button
        btn_poll = tk.Button(
            input_dock,
            text="🗳️ Poll",
            font=font_spec(11, "bold"),
            bg="#f59e0b",
            fg="#0f172a",
            activebackground="#d97706",
            activeforeground="#0f172a",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._prompt_create_poll
        )
        btn_poll.pack(side=tk.RIGHT, padx=3)

        # Text input field with modern placeholder
        self.msg_placeholder = "💬 Type a message, @mention, or paste image (Ctrl+V)..."
        self._is_placeholder_active = True

        self.entry_msg = tk.Entry(
            input_dock,
            font=font_spec(11),
            bg="#334155",
            fg="#94a3b8",
            insertbackground="#ffffff",
            relief="flat",
            bd=5
        )
        self.entry_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.entry_msg.insert(0, self.msg_placeholder)

        self.entry_msg.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_msg.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_msg.bind("<Return>", self._on_entry_enter)
        self.entry_msg.bind("<KeyRelease>", self._on_entry_key_release)
        self.entry_msg.bind("<Up>", self._on_mention_up)
        self.entry_msg.bind("<Down>", self._on_mention_down)
        self.entry_msg.bind("<Tab>", self._on_mention_tab)
        self.entry_msg.bind("<Control-v>", self._on_clipboard_paste)
        self.entry_msg.bind("<Control-V>", self._on_clipboard_paste)
        self.entry_msg.bind("<Control-f>", lambda e: (self._toggle_find_bar(), "break")[1])
        self.entry_msg.bind("<Control-F>", lambda e: (self._toggle_find_bar(), "break")[1])

    def _on_entry_focus_in(self, event=None):
        if getattr(self, "_is_placeholder_active", False) or self.entry_msg.get() == self.msg_placeholder:
            self.entry_msg.delete(0, tk.END)
            self.entry_msg.config(fg="#ffffff")
            self._is_placeholder_active = False

    def _on_entry_focus_out(self, event=None):
        if not self.entry_msg.get().strip():
            self.entry_msg.delete(0, tk.END)
            self.entry_msg.insert(0, self.msg_placeholder)
            self.entry_msg.config(fg="#94a3b8")
            self._is_placeholder_active = True

    def _populate_initial_data(self):
        """Renders existing message history, online peers, and pinned banner."""
        self._render_pinned_banner()
        for msg in self.engine.messages:
            self._render_message_bubble(msg, scroll=False)

        self.dialog.after(100, lambda: self.msg_canvas.yview_moveto(1.0))
        self._refresh_peers_ui(self.engine.get_online_peers())

    # ---------- In-Chat Quick Find (Ctrl+F) Methods ----------

    def _extract_searchable_text(self, msg):
        """Extracts all human-readable text from a message object for full-text search."""
        if not isinstance(msg, dict):
            return ""
        parts = []
        for k in ("text", "caption", "title", "user_name", "file_name", "shift_str", "total_hours"):
            v = msg.get(k)
            if v:
                parts.append(str(v))
        tasks = msg.get("tasks")
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    parts.extend([str(t.get(k, "")) for k in ("title", "desc", "project", "task", "status") if t.get(k)])
                elif isinstance(t, str):
                    parts.append(t)
        question = msg.get("question")
        if question:
            parts.append(str(question))
        options = msg.get("options")
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict) and opt.get("text"):
                    parts.append(str(opt.get("text")))
        return " ".join(parts).lower()

    def _open_find_bar(self):
        """Opens and focuses the in-chat quick find bar."""
        if not hasattr(self, "find_bar"):
            return
        if not self.find_bar.winfo_viewable():
            self.find_bar.pack(before=self.msg_canvas_box, fill=tk.X, padx=8, pady=(0, 4))
        self.entry_find.focus_set()
        self.entry_find.select_range(0, tk.END)
        if self.entry_find.get().strip():
            self._run_find()

    def _close_find_bar(self):
        """Closes the find bar, clears match highlights, and restores input focus."""
        if not hasattr(self, "find_bar"):
            return
        if self.find_bar.winfo_viewable():
            self.find_bar.pack_forget()
        self._clear_find_highlights()
        self.find_matches = []
        self.find_index = -1
        try:
            self.entry_msg.focus_set()
        except Exception:
            pass

    def _toggle_find_bar(self):
        """Toggles find bar visibility."""
        if not hasattr(self, "find_bar"):
            return
        if self.find_bar.winfo_viewable():
            self._close_find_bar()
        else:
            self._open_find_bar()

    def _on_find_key_release(self, event=None):
        if event and event.keysym in ("Return", "Shift_L", "Shift_R", "Escape", "Up", "Down"):
            return
        self._run_find()

    def _run_find(self):
        """Searches all messages in the chat feed matching the search query."""
        if not hasattr(self, "entry_find"):
            return
        query = self.entry_find.get().strip().lower()
        self._clear_find_highlights()
        self.find_matches = []
        self.find_index = -1

        if not query:
            self.lbl_find_count.config(text="0 matches", fg="#94a3b8")
            return

        for child in self.msg_inner.winfo_children():
            msg = getattr(child, "_msg_data", None)
            if not msg:
                continue
            text = self._extract_searchable_text(msg)
            if query in text:
                self.find_matches.append(child)

        total = len(self.find_matches)
        if total == 0:
            self.lbl_find_count.config(text="No matches", fg="#ef4444")
        else:
            for w in self.find_matches:
                target = getattr(w, "_highlight_target", None) or w
                try:
                    target.config(highlightthickness=2, highlightbackground="#0284c7")
                except Exception:
                    pass
            self.find_index = total - 1
            self._update_active_match()

    def _update_active_match(self):
        """Highlights the active match with an amber glow and scrolls to it."""
        total = len(self.find_matches)
        if total == 0 or self.find_index < 0:
            return

        for i, w in enumerate(self.find_matches):
            target = getattr(w, "_highlight_target", None) or w
            try:
                if i == self.find_index:
                    target.config(highlightthickness=3, highlightbackground="#f59e0b")
                else:
                    target.config(highlightthickness=2, highlightbackground="#0284c7")
            except Exception:
                pass

        self.lbl_find_count.config(
            text=f"{self.find_index + 1} of {total}",
            fg="#f59e0b"
        )
        active_w = self.find_matches[self.find_index]
        self._scroll_to_message(active_w)

    def _find_next(self, event=None):
        if not self.find_matches:
            return "break"
        self.find_index = (self.find_index + 1) % len(self.find_matches)
        self._update_active_match()
        return "break"

    def _find_prev(self, event=None):
        if not self.find_matches:
            return "break"
        self.find_index = (self.find_index - 1) % len(self.find_matches)
        self._update_active_match()
        return "break"

    def _clear_find_highlights(self):
        for child in self.msg_inner.winfo_children():
            target = getattr(child, "_highlight_target", None) or child
            try:
                target.config(highlightthickness=0)
            except Exception:
                pass

    def _scroll_to_message(self, row_frame):
        """Smoothly scrolls the canvas so that row_frame is centered in view."""
        self.dialog.update_idletasks()
        try:
            total_h = self.msg_inner.winfo_height()
            if total_h <= 0:
                return
            y = row_frame.winfo_y()
            canvas_h = self.msg_canvas.winfo_height()
            target_y = max(0, y - canvas_h // 4)
            fraction = target_y / float(total_h)
            fraction = max(0.0, min(1.0, fraction))
            self.msg_canvas.yview_moveto(fraction)
        except Exception:
            pass

    # ---------- UI Action Handlers ----------

    def _on_clipboard_paste(self, event=None):
        """
        Intercepts Ctrl+V paste. If clipboard holds an image, grabs it, displays a preview chip,
        and halts default text paste so raw binary data isn't pasted.
        If no image on clipboard, allows standard text paste to happen normally.
        """
        temp_img_name = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        temp_img_path = os.path.join(SCREENSHOT_DIR, temp_img_name)
        if grab_clipboard_image(temp_img_path):
            self._set_pending_image(temp_img_path, temp_img_name)
            return "break"
        return None

    def _paste_clipboard_image(self):
        """Action handler for 📷 Paste button."""
        temp_img_name = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        temp_img_path = os.path.join(SCREENSHOT_DIR, temp_img_name)
        if grab_clipboard_image(temp_img_path):
            self._set_pending_image(temp_img_path, temp_img_name)
        else:
            messagebox.showinfo("Clipboard", "No image found on clipboard.\n\nTip: Take a screenshot (PrintScreen / Snipping Tool / flameshot) and press Ctrl+V here to share instantly with your team!", parent=self.dialog)

    def _set_pending_image(self, path, name):
        fsize = os.path.getsize(path)
        fsize_str = format_file_size(fsize)
        self.pending_image = {
            "path": path,
            "name": name,
            "size": fsize,
            "size_str": fsize_str
        }
        for w in self.clip_dock.winfo_children():
            w.destroy()

        left_f = tk.Frame(self.clip_dock, bg="#0f172a")
        left_f.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_icon = tk.Label(left_f, text="🖼️ Attached Screenshot:", font=font_spec(11, "bold"), fg="#38bdf8", bg="#0f172a")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 6))

        lbl_name = tk.Label(left_f, text=f"{name} ({fsize_str}) • Press Send or type an optional caption", font=font_spec(10), fg="#f1f5f9", bg="#0f172a")
        lbl_name.pack(side=tk.LEFT)

        btn_cancel = tk.Label(self.clip_dock, text="✕ Cancel", font=font_spec(10, "bold"), fg="#ef4444", bg="#0f172a", cursor="hand2")
        btn_cancel.pack(side=tk.RIGHT, padx=4)
        btn_cancel.bind("<Button-1>", lambda e: self._cancel_pending_image())

        self.clip_dock.pack(fill=tk.X, side=tk.TOP, pady=(4, 0))
        self.entry_msg.focus_set()

    def _cancel_pending_image(self):
        self.pending_image = None
        self.clip_dock.pack_forget()
        for w in self.clip_dock.winfo_children():
            w.destroy()

    def _start_reply(self, msg):
        sender = msg.get("user_name", "Colleague")
        msg_id = msg.get("id")
        raw_text = msg.get("text") or msg.get("file_name") or msg.get("title") or "Message"
        snippet = str(raw_text).replace("\n", " ").strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."

        self.active_reply = {
            "id": msg_id,
            "user_name": sender,
            "text": snippet
        }

        for w in self.reply_dock.winfo_children():
            w.destroy()

        stripe = tk.Frame(self.reply_dock, bg="#38bdf8", width=4)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        mid_f = tk.Frame(self.reply_dock, bg="#0f172a")
        mid_f.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_r_user = tk.Label(mid_f, text=f"Replying to {sender}", font=font_spec(11, "bold"), fg="#38bdf8", bg="#0f172a")
        lbl_r_user.pack(anchor="w")

        lbl_r_snip = tk.Label(mid_f, text=f'"{snippet}"', font=font_spec(10, slant="italic"), fg="#94a3b8", bg="#0f172a")
        lbl_r_snip.pack(anchor="w")

        btn_cancel = tk.Label(self.reply_dock, text="✕", font=font_spec(12, "bold"), fg="#ef4444", bg="#0f172a", cursor="hand2")
        btn_cancel.pack(side=tk.RIGHT, padx=6)
        btn_cancel.bind("<Button-1>", lambda e: self._cancel_reply())

        self.reply_dock.pack(fill=tk.X, side=tk.TOP, pady=(4, 0))
        self.entry_msg.focus_set()

    def _cancel_reply(self):
        self.active_reply = None
        self.reply_dock.pack_forget()
        for w in self.reply_dock.winfo_children():
            w.destroy()

    def _send_message(self):
        text = self.entry_msg.get().strip()
        if getattr(self, "_is_placeholder_active", False) or text == getattr(self, "msg_placeholder", ""):
            text = ""
        reply_to = self.active_reply

        recipient_id = self.active_dm_peer["id"] if self.active_dm_peer else ""
        recipient_name = self.active_dm_peer["user_name"] if self.active_dm_peer else ""

        if self.pending_image:
            img_info = self.pending_image
            caption = text
            self.entry_msg.delete(0, tk.END)
            self._cancel_pending_image()
            if reply_to:
                self._cancel_reply()
            self.engine.send_file(
                img_info["path"],
                is_image=True,
                reply_to=reply_to,
                caption=caption,
                recipient_id=recipient_id,
                recipient_name=recipient_name
            )
            return

        if not text:
            return

        self.entry_msg.delete(0, tk.END)
        if reply_to:
            self._cancel_reply()
        self.engine.send_chat_message(
            text,
            reply_to=reply_to,
            recipient_id=recipient_id,
            recipient_name=recipient_name
        )

    def _on_engine_reaction(self, msg_id, reactions):
        """Invoked by engine when an emoji reaction is toggled."""
        if not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        self.dialog.after(0, lambda: self._render_reaction_pills(msg_id, reactions))

    def _render_reaction_pills(self, msg_id, reactions):
        container = self.reaction_containers.get(msg_id)
        if not container or not container.winfo_exists():
            return

        for w in container.winfo_children():
            w.destroy()

        if not reactions or not isinstance(reactions, dict):
            return

        has_any = False
        for emoji, users in reactions.items():
            if not users or not isinstance(users, list):
                continue
            has_any = True
            count = len(users)
            has_me = self.engine.user_name in users
            bg_col = "#1e3a8a" if has_me else "#1e293b"
            fg_col = "#93c5fd" if has_me else "#cbd5e1"
            bd_col = "#3b82f6" if has_me else "#334155"

            pill = tk.Label(
                container,
                text=f"{emoji} {count}",
                font=font_spec(10, "bold"),
                bg=bg_col,
                fg=fg_col,
                padx=7,
                pady=2,
                relief="solid",
                bd=1,
                cursor="hand2"
            )
            pill.pack(side=tk.LEFT, padx=(0, 4), pady=2)

            reactor_names = ", ".join(users)
            tip_text = f"{emoji} Reacted by: {reactor_names}"
            pill.bind("<Enter>", lambda e, t=tip_text: self._show_tooltip(e, t))
            pill.bind("<Leave>", lambda e: self._hide_tooltip())
            pill.bind("<Button-1>", lambda e, mid=msg_id, em=emoji: self.engine.toggle_reaction(mid, em))

        if has_any:
            btn_add = tk.Label(
                container,
                text="➕",
                font=font_spec(9),
                bg="#1e293b",
                fg="#64748b",
                padx=5,
                pady=2,
                cursor="hand2",
                relief="solid",
                bd=1
            )
            btn_add.pack(side=tk.LEFT, padx=2, pady=2)
            btn_add.bind("<Enter>", lambda e, b=btn_add: b.config(fg="#94a3b8"))
            btn_add.bind("<Leave>", lambda e, b=btn_add: b.config(fg="#64748b"))
            btn_add.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

    def _show_reaction_picker(self, msg_id, anchor_widget):
        """Displays small borderless floating popup with popular reaction emojis."""
        if self.active_picker and self.active_picker.winfo_exists():
            self.active_picker.destroy()
            self.active_picker = None

        picker = tk.Toplevel(self.dialog)
        picker.overrideredirect(True)
        picker.attributes("-topmost", True)
        picker.configure(bg="#0f172a", bd=1, relief="solid")

        self.active_picker = picker

        p_inner = tk.Frame(picker, bg="#0f172a", padx=4, pady=4)
        p_inner.pack()

        for em in POPULAR_REACTIONS:
            lbl = tk.Label(
                p_inner,
                text=em,
                font=font_spec(13),
                bg="#0f172a",
                fg="#ffffff",
                padx=6,
                pady=3,
                cursor="hand2"
            )
            lbl.pack(side=tk.LEFT, padx=1)
            lbl.bind("<Enter>", lambda e, b=lbl: b.config(bg="#334155"))
            lbl.bind("<Leave>", lambda e, b=lbl: b.config(bg="#0f172a"))
            def _choose(event, chosen_emoji=em):
                picker.destroy()
                self.active_picker = None
                self.engine.toggle_reaction(msg_id, chosen_emoji)
            lbl.bind("<Button-1>", _choose)

        picker.update_idletasks()
        rx = anchor_widget.winfo_rootx()
        ry = anchor_widget.winfo_rooty() - picker.winfo_reqheight() - 4
        if ry < 10:
            ry = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
        picker.geometry(f"+{rx}+{ry}")

        def _on_focus_out(e):
            if picker.winfo_exists():
                picker.destroy()
                self.active_picker = None
        picker.bind("<FocusOut>", _on_focus_out)
        self.dialog.after(100, lambda: picker.focus_set())

    def _show_tooltip(self, event, text):
        self._hide_tooltip()
        tip = tk.Toplevel(self.dialog)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg="#334155", bd=1, relief="solid")
        lbl = tk.Label(tip, text=text, font=font_spec(10), bg="#334155", fg="#f8fafc", padx=8, pady=4)
        lbl.pack()
        tip.update_idletasks()
        x = event.x_root + 10
        y = event.y_root - tip.winfo_reqheight() - 5
        tip.geometry(f"+{x}+{y}")
        self.tooltip_window = tip

    def _hide_tooltip(self):
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _share_file_to_chat(self):
        """Prompts user to select any file and shares it across the LAN."""
        file_path = choose_file_dialog(
            parent=self.dialog,
            title="Select File to Share with Team",
            filetypes=[
                ("All Files", "*.*"),
                ("Documents (*.pdf, *.docx, *.txt, *.xlsx)", "*.pdf;*.docx;*.txt;*.xlsx;*.csv"),
                ("Images (*.png, *.jpg, *.jpeg, *.gif)", "*.png;*.jpg;*.jpeg;*.gif"),
                ("Archives (*.zip, *.rar, *.tar.gz)", "*.zip;*.rar;*.tar;*.gz;*.7z")
            ]
        )
        if not file_path:
            return

        try:
            sz = os.path.getsize(file_path)
            if sz > 1024 * 1024 * 1024:
                if not messagebox.askyesno("Large File", "This file is larger than 1 GB. Do you still want to share it across Wi-Fi?", parent=self.dialog):
                    return
        except Exception:
            pass

        recipient_id = self.active_dm_peer["id"] if self.active_dm_peer else ""
        recipient_name = self.active_dm_peer["user_name"] if self.active_dm_peer else ""
        self.engine.send_file(file_path, recipient_id=recipient_id, recipient_name=recipient_name)

    def _share_today_tasks_to_chat(self):
        """Grabs today's tasks from the active WorkPulse app and posts to chat."""
        if not self.app_ref:
            messagebox.showinfo("WorkPulse", "Active application reference not found.", parent=self.dialog)
            return

        data = self.app_ref.get_all_categorized_tasks()
        tasks_pool = data.get("today", [])
        if not tasks_pool:
            tasks_pool = data.get("month", [])

        if not tasks_pool:
            messagebox.showinfo("No Tasks", "No tasks found for today to share.", parent=self.dialog)
            return

        date_str = data.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))

        shift_str = ""
        if hasattr(self.app_ref, "get_current_day_timings"):
            timings = self.app_ref.get_current_day_timings(date_str)
            if timings.get("login") or timings.get("logout"):
                shift_str = f"Shift: {timings.get('login', '-')} to {timings.get('logout', '-')}"

        total_hours = 0.0
        for t in tasks_pool:
            try:
                total_hours += float(t.get("hours", 0) or 0)
            except Exception:
                pass

        total_hours_str = f"{total_hours:.1f} hrs"

        self.engine.send_work_update(
            title=f"Today's Work Log ({date_str})",
            date_str=date_str,
            tasks=tasks_pool[:12],
            shift_str=shift_str,
            total_hours=total_hours_str
        )

    def _on_status_changed(self, event=None):
        selected = self.status_var.get()
        status_text = "Available"
        status_emoji = "🟢"
        for opt in STATUS_CHOICES:
            if opt[0] == selected:
                status_text = opt[1]
                status_emoji = opt[2]
                break
        note = self.status_note_var.get().strip() if hasattr(self, "status_note_var") else ""
        self.engine.update_profile(self.engine.user_name, status=status_text, status_emoji=status_emoji, status_note=note)

    def _on_status_note_submitted(self, event=None):
        note = self.status_note_var.get().strip() if hasattr(self, "status_note_var") else ""
        selected = self.status_var.get()
        status_text = "Available"
        status_emoji = "🟢"
        for opt in STATUS_CHOICES:
            if opt[0] == selected:
                status_text = opt[1]
                status_emoji = opt[2]
                break
        self.engine.update_profile(self.engine.user_name, status=status_text, status_emoji=status_emoji, status_note=note)

    def _toggle_sound_mute(self):
        self.sound_muted = not getattr(self, "sound_muted", False)
        if hasattr(self, "btn_sound"):
            if self.sound_muted:
                self.btn_sound.config(text="🔕 Muted", bg="#7f1d1d")
            else:
                self.btn_sound.config(text="🔔 Sound", bg="#334155")
                play_sound_alert("message")

    def _prompt_add_colleague_ip(self):
        """Opens a modal to manually enter colleague's IP for isolated Wi-Fi."""
        prompt_win = tk.Toplevel(self.dialog)
        prompt_win.title("Add Colleague IP")
        prompt_win.configure(bg="#1e293b")
        prompt_win.resizable(True, True)

        tk.Label(
            prompt_win,
            text="Enter Colleague's IP Address:",
            font=font_spec(13, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        ).pack(anchor="w", padx=18, pady=(16, 4))

        tk.Label(
            prompt_win,
            text="Useful if Wi-Fi Access Point blocks UDP broadcast discovery.",
            font=font_spec(11),
            fg="#94a3b8",
            bg="#1e293b"
        ).pack(anchor="w", padx=18, pady=(0, 10))

        e_ip = tk.Entry(prompt_win, font=font_spec(12), bg="#334155", fg="#ffffff", insertbackground="#ffffff")
        e_ip.pack(fill=tk.X, padx=18, pady=4, ipady=4)
        e_ip.insert(0, "192.168.1.")
        e_ip.focus_set()

        btn_box = tk.Frame(prompt_win, bg="#1e293b")
        btn_box.pack(fill=tk.X, padx=18, pady=16)

        def _do_add():
            val = e_ip.get().strip()
            if val and val != "192.168.1.":
                self.engine.add_custom_peer_ip(val)
                messagebox.showinfo(
                    "Ping Sent",
                    f"Sent connection beacon to {val}.\nIf WorkPulse is open on that machine, they will appear in your colleague list!",
                    parent=prompt_win
                )
                prompt_win.destroy()

        e_ip.bind("<Return>", lambda e: _do_add())

        tk.Button(
            btn_box, text="Connect", font=font_spec(11, "bold"),
            bg="#2563eb", fg="white", relief="flat", padx=16, pady=5, cursor="hand2", command=_do_add
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_box, text="Cancel", font=font_spec(11),
            bg="#475569", fg="white", relief="flat", padx=12, pady=5, cursor="hand2", command=prompt_win.destroy
        ).pack(side=tk.RIGHT)

        center_window(prompt_win, self.dialog, default_w=480, default_h=240, min_w=440, min_h=210)

    def _clear_chat_history(self):
        if messagebox.askyesno("Clear Chat History", "Are you sure you want to clear your local chat history from SQLite?", parent=self.dialog):
            self.engine.clear_history()
            self.msg_widgets.clear()
            self.reaction_containers.clear()
            self.find_matches.clear()
            self.find_index = -1
            if hasattr(self, "find_bar") and self.find_bar.winfo_viewable():
                self.lbl_find_count.config(text="0 matches", fg="#94a3b8")
            for widget in self.msg_inner.winfo_children():
                widget.destroy()

    def _on_engine_message_deleted(self, target_msg_id):
        """Thread-safe UI callback to remove a deleted message from the feed."""
        if not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return

        def _ui_remove():
            if target_msg_id in self.msg_widgets:
                w = self.msg_widgets.pop(target_msg_id)
                if w in self.find_matches:
                    try:
                        self.find_matches.remove(w)
                    except ValueError:
                        pass
                    if hasattr(self, "find_bar") and self.find_bar.winfo_viewable() and hasattr(self, "entry_find") and self.entry_find.get().strip():
                        self._run_find()
                try:
                    w.destroy()
                except Exception:
                    pass
                self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox("all"))

        self.dialog.after(0, _ui_remove)

    def _prompt_delete_message(self, msg):
        """Allows deleting a message locally or broadcasting deletion across LAN."""
        msg_id = msg.get("id")
        if not msg_id:
            return
        is_me = msg.get("is_me", False)

        if is_me:
            win = tk.Toplevel(self.dialog)
            win.title("Delete Message")
            win.configure(bg="#1e293b")
            win.resizable(True, True)

            tk.Label(
                win,
                text="🗑️ Delete Message",
                font=font_spec(13, "bold"),
                fg="#ffffff",
                bg="#1e293b"
            ).pack(anchor="w", padx=20, pady=(16, 4))

            preview = msg.get("text") or msg.get("file_name") or msg.get("title") or "Message"
            if len(preview) > 42:
                preview = preview[:39] + "..."

            tk.Label(
                win,
                text=f"Delete \"{preview}\"?",
                font=font_spec(11),
                fg="#cbd5e1",
                bg="#1e293b"
            ).pack(anchor="w", padx=20, pady=(0, 14))

            btn_box = tk.Frame(win, bg="#1e293b")
            btn_box.pack(fill=tk.X, padx=20, pady=10)

            def _del_everyone():
                win.destroy()
                self.engine.delete_message(msg_id, broadcast=True)

            def _del_me():
                win.destroy()
                self.engine.delete_message(msg_id, broadcast=False)

            tk.Button(
                btn_box,
                text="🌐 Delete for Everyone",
                font=font_spec(10, "bold"),
                bg="#ef4444",
                fg="white",
                activebackground="#dc2626",
                activeforeground="white",
                relief="flat",
                padx=12,
                pady=5,
                cursor="hand2",
                command=_del_everyone
            ).pack(side=tk.LEFT, padx=(0, 6))

            tk.Button(
                btn_box,
                text="👤 Delete for Me",
                font=font_spec(10),
                bg="#334155",
                fg="#f8fafc",
                activebackground="#475569",
                activeforeground="#ffffff",
                relief="flat",
                padx=12,
                pady=5,
                cursor="hand2",
                command=_del_me
            ).pack(side=tk.LEFT, padx=(0, 6))

            tk.Button(
                btn_box,
                text="Cancel",
                font=font_spec(10),
                bg="#1e293b",
                fg="#94a3b8",
                relief="flat",
                padx=10,
                pady=5,
                cursor="hand2",
                command=win.destroy
            ).pack(side=tk.RIGHT)

            center_window(win, self.dialog, default_w=480, default_h=230, min_w=440, min_h=200)
        else:
            if messagebox.askyesno("Delete Message", "Delete this message from your chat history?", parent=self.dialog):
                self.engine.delete_message(msg_id, broadcast=False)

    def _prompt_search_dialog(self):
        """Opens modal dialog to search SQLite chat history."""
        search_win = tk.Toplevel(self.dialog)
        search_win.title("🔍 Search LAN Chat History (SQLite)")
        search_win.configure(bg="#0f172a")

        center_window(search_win, self.dialog, default_w=640, default_h=520, min_w=520, min_h=400)

        # Header
        top_bar = tk.Frame(search_win, bg="#1e293b", padx=16, pady=10)
        top_bar.pack(fill=tk.X)

        tk.Label(
            top_bar,
            text="🔍 Search Chat History (SQLite)",
            font=font_spec(14, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        ).pack(anchor="w")

        total_count = self.engine.db.get_message_count()
        lbl_info = tk.Label(
            top_bar,
            text=f"Indexed across {total_count} messages in {CHAT_DB_FILE}",
            font=font_spec(11),
            fg="#94a3b8",
            bg="#1e293b"
        )
        lbl_info.pack(anchor="w", pady=(2, 0))

        # Search Input
        input_bar = tk.Frame(search_win, bg="#0f172a", padx=16, pady=10)
        input_bar.pack(fill=tk.X)

        e_search = tk.Entry(
            input_bar,
            font=font_spec(12),
            bg="#1e293b",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=6
        )
        e_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=4)
        e_search.focus_set()

        # Results area
        results_frame = tk.Frame(search_win, bg="#0f172a", padx=14, pady=4)
        results_frame.pack(fill=tk.BOTH, expand=True)

        res_canvas = tk.Canvas(results_frame, bg="#0f172a", highlightthickness=0)
        res_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=res_canvas.yview)
        res_inner = tk.Frame(res_canvas, bg="#0f172a")

        res_canvas.configure(yscrollcommand=res_scroll.set)
        res_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        res_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        res_win = res_canvas.create_window((0, 0), window=res_inner, anchor="nw")

        def _on_inner_cfg(event):
            res_canvas.configure(scrollregion=res_canvas.bbox("all"))
        res_inner.bind("<Configure>", _on_inner_cfg)

        def _on_canvas_cfg(event):
            res_canvas.itemconfig(res_win, width=event.width)
        res_canvas.bind("<Configure>", _on_canvas_cfg)

        def _do_search(event=None):
            query = e_search.get().strip()
            for w in res_inner.winfo_children():
                w.destroy()

            if not query:
                tk.Label(
                    res_inner,
                    text="Type any keyword above to search through your SQLite chat history.",
                    font=font_spec(11),
                    fg="#64748b",
                    bg="#0f172a",
                    wraplength=480
                ).pack(anchor="w", padx=6, pady=24)
                return

            matches = self.engine.search_history(query, limit=50)
            if not matches:
                tk.Label(
                    res_inner,
                    text=f"No messages found matching '{query}'.",
                    font=font_spec(12, "bold"),
                    fg="#94a3b8",
                    bg="#0f172a"
                ).pack(pady=24)
                return

            tk.Label(
                res_inner,
                text=f"Found {len(matches)} matching message{'s' if len(matches) != 1 else ''}:",
                font=font_spec(11, "bold"),
                fg="#38bdf8",
                bg="#0f172a"
            ).pack(anchor="w", pady=(0, 8))

            for m in matches:
                card = tk.Frame(res_inner, bg="#1e293b", padx=12, pady=10, bd=1, relief="solid")
                card.pack(fill=tk.X, pady=4)

                header_f = tk.Frame(card, bg="#1e293b")
                header_f.pack(fill=tk.X)

                av = tk.Label(
                    header_f,
                    text=get_initials(m["user_name"]),
                    font=font_spec(10, "bold"),
                    fg="#ffffff",
                    bg=m.get("avatar_color", AVATAR_PALETTE[0]),
                    width=2,
                    height=1
                )
                av.pack(side=tk.LEFT, padx=(0, 6))

                tk.Label(
                    header_f,
                    text=m["user_name"],
                    font=font_spec(11, "bold"),
                    fg="#ffffff",
                    bg="#1e293b"
                ).pack(side=tk.LEFT)

                date_part = m.get("date_str") or ""
                time_part = m.get("time_str") or ""
                tk.Label(
                    header_f,
                    text=f"{date_part} {time_part}",
                    font=font_spec(10),
                    fg="#64748b",
                    bg="#1e293b"
                ).pack(side=tk.RIGHT)

                body_txt = m.get("text") or m.get("title") or m.get("file_name") or "Work Update"
                tk.Label(
                    card,
                    text=body_txt,
                    font=font_spec(12),
                    fg="#e2e8f0",
                    bg="#1e293b",
                    wraplength=560,
                    justify="left"
                ).pack(anchor="w", pady=(6, 0))

        e_search.bind("<KeyRelease>", _do_search)
        e_search.bind("<Return>", _do_search)

        btn_find = tk.Button(
            input_bar,
            text="Search",
            font=font_spec(11, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            padx=14,
            pady=5,
            cursor="hand2",
            command=_do_search
        )
        btn_find.pack(side=tk.RIGHT)

        _do_search()

    def _on_engine_poll_updated(self, poll_msg):
        """Thread-safe UI callback when a poll vote is recorded."""
        if not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        def _ui_update():
            mid = poll_msg.get("id")
            if mid in self.msg_widgets:
                old_w = self.msg_widgets.pop(mid)
                try:
                    old_w.destroy()
                except Exception:
                    pass
                self._render_message_bubble(poll_msg, scroll=False)
        self.dialog.after(0, _ui_update)

    def _prompt_create_poll(self):
        """Opens a modal to create a new team poll for the current room or DM."""
        win = tk.Toplevel(self.dialog)
        win.title("🗳️ Create LAN Team Poll")
        win.configure(bg="#1e293b")
        win.resizable(True, True)

        # Bottom buttons pinned to bottom so they are 100% guaranteed visible
        btn_box = tk.Frame(win, bg="#1e293b")
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, padx=22, pady=(12, 18))

        def _do_submit():
            q = e_q.get().strip()
            if not q:
                messagebox.showwarning("Incomplete", "Please enter a poll question.", parent=win)
                return
            cleaned = [e.get().strip() for e in option_entries if e.get().strip()]
            if len(cleaned) < 2:
                messagebox.showwarning("Incomplete", "Please enter at least 2 non-empty options.", parent=win)
                return
            recip_id = self.active_dm_peer["id"] if self.active_dm_peer else ""
            recip_name = self.active_dm_peer["user_name"] if self.active_dm_peer else ""
            self.engine.create_poll(q, cleaned, recipient_id=recip_id, recipient_name=recip_name)
            win.destroy()

        btn_submit = tk.Button(
            btn_box,
            text="🚀 Create & Broadcast Poll",
            font=font_spec(11, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=7,
            cursor="hand2",
            command=_do_submit
        )
        btn_submit.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(
            btn_box,
            text="Cancel",
            font=font_spec(11),
            bg="#475569",
            fg="white",
            activebackground="#334155",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            command=win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, padx=4)

        # Main Content Frame
        content = tk.Frame(win, bg="#1e293b")
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=22, pady=(18, 0))

        tk.Label(
            content,
            text="🗳️ Create Team Poll",
            font=font_spec(14, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        ).pack(anchor="w", pady=(0, 4))

        channel_desc = f"Direct Message with {self.active_dm_peer['user_name']}" if self.active_dm_peer else "# team-general (All Colleagues)"
        tk.Label(
            content,
            text=f"Broadcast to: {channel_desc}",
            font=font_spec(11),
            fg="#38bdf8",
            bg="#1e293b",
            wraplength=540,
            justify="left"
        ).pack(anchor="w", pady=(0, 12))

        # Question Entry
        tk.Label(content, text="Poll Question:", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#1e293b").pack(anchor="w", pady=(4, 2))
        e_q = tk.Entry(content, font=font_spec(12), bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", relief="flat", bd=5)
        e_q.pack(fill=tk.X, pady=(0, 10), ipady=3)
        e_q.focus_set()

        # Options Container
        tk.Label(content, text="Poll Options (2 to 5):", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#1e293b").pack(anchor="w", pady=(4, 2))
        opts_frame = tk.Frame(content, bg="#1e293b")
        opts_frame.pack(fill=tk.X, pady=(0, 6))

        option_entries = []

        def _add_option_row(default_txt=""):
            if len(option_entries) >= 5:
                return
            idx = len(option_entries) + 1
            row = tk.Frame(opts_frame, bg="#1e293b")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{idx}.", font=font_spec(11, "bold"), fg="#94a3b8", bg="#1e293b", width=2).pack(side=tk.LEFT)
            e = tk.Entry(row, font=font_spec(11), bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", relief="flat", bd=4)
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
            if default_txt:
                e.insert(0, default_txt)
            option_entries.append(e)

        _add_option_row("Yes 👍")
        _add_option_row("No 👎")

        btn_add_opt = tk.Button(
            content,
            text="+ Add Option",
            font=font_spec(10),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: _add_option_row()
        )
        btn_add_opt.pack(anchor="w", pady=(0, 12))

        # Dynamically size and center AFTER widgets exist
        center_window(win, self.dialog, default_w=620, default_h=540, min_w=560, min_h=480)

    def _prompt_export_chat(self):
        """Opens a modal to export chat history to Markdown (.md) or HTML (.html)."""
        win = tk.Toplevel(self.dialog)
        win.title("📥 Export Chat History")
        win.configure(bg="#1e293b")
        win.resizable(True, True)

        # Bottom buttons pinned to bottom
        btn_box = tk.Frame(win, bg="#1e293b")
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, padx=22, pady=(12, 18))

        # Main Content Frame
        content = tk.Frame(win, bg="#1e293b")
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=22, pady=(18, 0))

        tk.Label(
            content,
            text="📥 Export Chat History",
            font=font_spec(14, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            content,
            text="Export your local SQLite chat history for documentation, standups, or archive.",
            font=font_spec(10),
            fg="#94a3b8",
            bg="#1e293b",
            wraplength=540,
            justify="left"
        ).pack(anchor="w", pady=(0, 14))

        # Scope
        tk.Label(content, text="Export Scope:", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#1e293b").pack(anchor="w", pady=(4, 2))
        scope_var = tk.StringVar(value="channel")
        cur_chan = f"Current Channel ({self.active_dm_peer['user_name'] if self.active_dm_peer else '# team-general'})"
        tk.Radiobutton(content, text=cur_chan, variable=scope_var, value="channel", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)
        tk.Radiobutton(content, text="All Messages (Entire SQLite Database)", variable=scope_var, value="all", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)

        # Format
        tk.Label(content, text="File Format:", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#1e293b").pack(anchor="w", pady=(10, 2))
        fmt_var = tk.StringVar(value="markdown")
        tk.Radiobutton(content, text="Markdown (.md) — Perfect for GitHub, Notion & Slack notes", variable=fmt_var, value="markdown", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)
        tk.Radiobutton(content, text="Styled HTML (.html) — Standalone dark-mode web page", variable=fmt_var, value="html", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)

        # Time range
        tk.Label(content, text="Time Range:", font=font_spec(11, "bold"), fg="#cbd5e1", bg="#1e293b").pack(anchor="w", pady=(10, 2))
        range_var = tk.StringVar(value="all")
        tk.Radiobutton(content, text="All Time", variable=range_var, value="all", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)
        tk.Radiobutton(content, text="Today Only", variable=range_var, value="today", font=font_spec(11), bg="#1e293b", fg="#ffffff", selectcolor="#0f172a", activebackground="#1e293b", activeforeground="#ffffff").pack(anchor="w", padx=20)

        def _do_export():
            all_msgs = self.engine.db.load_recent_messages(limit=2000)
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")

            filtered = []
            for m in all_msgs:
                if range_var.get() == "today" and m.get("date_str") != today_str:
                    continue
                if scope_var.get() == "channel":
                    if not self._message_matches_current_view(m):
                        continue
                filtered.append(m)

            if not filtered:
                messagebox.showinfo("No Messages", "No messages match your selected export criteria.", parent=win)
                return

            chosen_fmt = fmt_var.get()
            ext = ".md" if chosen_fmt == "markdown" else ".html"
            filetypes = [("Markdown File", "*.md")] if chosen_fmt == "markdown" else [("HTML File", "*.html")]
            initial_name = f"workpulse_chat_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

            dest = choose_save_dialog(
                parent=win,
                title="Save Chat Export",
                default_name=initial_name,
                filetypes=filetypes,
                defaultextension=ext
            )
            if not dest:
                return

            chan_label = self.active_dm_peer["user_name"] if self.active_dm_peer else "# team-general"
            ok = export_chat_history(filtered, dest, format_type=chosen_fmt, channel_name=chan_label)
            if ok:
                win.destroy()
                if messagebox.askyesno("Export Successful", f"Chat exported successfully to:\n{dest}\n\nOpen file now?", parent=self.dialog):
                    open_file_externally(dest)
            else:
                messagebox.showerror("Export Failed", "Could not write export file.", parent=win)

        tk.Button(
            btn_box,
            text="💾 Save Export",
            font=font_spec(11, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=16,
            pady=7,
            cursor="hand2",
            command=_do_export
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_box,
            text="Cancel",
            font=font_spec(11),
            bg="#475569",
            fg="white",
            activebackground="#334155",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            command=win.destroy
        ).pack(side=tk.RIGHT, padx=4)

        # Dynamically size and center AFTER widgets exist
        center_window(win, self.dialog, default_w=640, default_h=560, min_w=580, min_h=500)

    # ---------- @Mentions Autocomplete Handlers ----------

    def _on_entry_key_release(self, event=None):
        if event and event.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
            return
        self._check_mention_autocomplete()

    def _check_mention_autocomplete(self):
        try:
            if getattr(self, "_is_placeholder_active", False):
                self._close_mention_popup()
                return
            cur_pos = self.entry_msg.index(tk.INSERT)
            full_txt = self.entry_msg.get()
            if full_txt == getattr(self, "msg_placeholder", ""):
                self._close_mention_popup()
                return
            txt_before = full_txt[:cur_pos]
            last_at = txt_before.rfind("@")
            if last_at == -1:
                self._close_mention_popup()
                return

            if last_at > 0 and not txt_before[last_at - 1].isspace():
                self._close_mention_popup()
                return

            query = txt_before[last_at + 1:]
            if any(c.isspace() for c in query):
                self._close_mention_popup()
                return

            self._show_mention_popup(query.lower())
        except Exception:
            self._close_mention_popup()

    def _show_mention_popup(self, query):
        candidates = []
        if "all".startswith(query) or not query:
            candidates.append({"tag": "all", "display": "@all (Notify whole team)", "icon": "📢"})
        if "team".startswith(query) or not query:
            candidates.append({"tag": "team", "display": "@team (All online peers)", "icon": "👥"})

        for p in self.engine.get_online_peers():
            u = p["user_name"]
            if query in u.lower():
                candidates.append({"tag": u, "display": f"@{u} ({p.get('status', 'Available')})", "icon": p.get("status_emoji", "🟢")})

        if not candidates:
            self._close_mention_popup()
            return

        self.mention_candidates = candidates

        if not self.mention_popup or not self.mention_popup.winfo_exists():
            self.mention_popup = tk.Toplevel(self.dialog)
            self.mention_popup.overrideredirect(True)
            self.mention_popup.attributes("-topmost", True)
            self.mention_popup.configure(bg="#0f172a", bd=1, relief="solid")

            self.mention_listbox = tk.Listbox(
                self.mention_popup,
                font=font_spec(11),
                bg="#1e293b",
                fg="#f8fafc",
                selectbackground="#2563eb",
                selectforeground="#ffffff",
                relief="flat",
                bd=0,
                highlightthickness=0,
                activestyle="none"
            )
            self.mention_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.mention_listbox.bind("<Button-1>", lambda e: self.dialog.after(10, self._apply_mention_selection))

        self.mention_listbox.delete(0, tk.END)
        for c in candidates:
            self.mention_listbox.insert(tk.END, f" {c['icon']} {c['display']}")
        self.mention_listbox.selection_set(0)

        self.entry_msg.update_idletasks()
        rx = self.entry_msg.winfo_rootx()
        req_h = min(len(candidates) * 26 + 8, 160)
        ry = self.entry_msg.winfo_rooty() - req_h - 4
        if ry < 10:
            ry = self.entry_msg.winfo_rooty() + self.entry_msg.winfo_height() + 4
        self.mention_popup.geometry(f"320x{req_h}+{rx}+{ry}")
        self.mention_popup.deiconify()

    def _close_mention_popup(self):
        if self.mention_popup and self.mention_popup.winfo_exists():
            self.mention_popup.destroy()
            self.mention_popup = None
            self.mention_listbox = None
            self.mention_candidates = []

    def _on_mention_up(self, event):
        if self.mention_popup and self.mention_popup.winfo_exists():
            cur = self.mention_listbox.curselection()
            idx = cur[0] if cur else 0
            if idx > 0:
                self.mention_listbox.selection_clear(0, tk.END)
                self.mention_listbox.selection_set(idx - 1)
                self.mention_listbox.see(idx - 1)
            return "break"
        return None

    def _on_mention_down(self, event):
        if self.mention_popup and self.mention_popup.winfo_exists():
            cur = self.mention_listbox.curselection()
            idx = cur[0] if cur else 0
            if idx < len(self.mention_candidates) - 1:
                self.mention_listbox.selection_clear(0, tk.END)
                self.mention_listbox.selection_set(idx + 1)
                self.mention_listbox.see(idx + 1)
            return "break"
        return None

    def _on_mention_tab(self, event):
        if self.mention_popup and self.mention_popup.winfo_exists():
            self._apply_mention_selection()
            return "break"
        return None

    def _on_entry_enter(self, event=None):
        if self.mention_popup and self.mention_popup.winfo_exists():
            self._apply_mention_selection()
            return "break"
        self._send_message()
        return "break"

    def _apply_mention_selection(self):
        if not self.mention_popup or not self.mention_popup.winfo_exists():
            return
        cur = self.mention_listbox.curselection()
        if not cur or cur[0] >= len(self.mention_candidates):
            self._close_mention_popup()
            return

        chosen = self.mention_candidates[cur[0]]["tag"]
        cur_pos = self.entry_msg.index(tk.INSERT)
        full_txt = self.entry_msg.get()
        txt_before = full_txt[:cur_pos]
        txt_after = full_txt[cur_pos:]
        last_at = txt_before.rfind("@")
        if last_at != -1:
            new_txt = txt_before[:last_at] + f"@{chosen} " + txt_after
            self.entry_msg.delete(0, tk.END)
            self.entry_msg.insert(0, new_txt)
            new_cursor_pos = last_at + len(chosen) + 2
            self.entry_msg.icursor(new_cursor_pos)

        self._close_mention_popup()
        self.entry_msg.focus_set()

    # ---------- Direct Message & Channel Switching ----------

    def _select_dm_peer(self, peer_dict):
        """Switches conversation context to 1-on-1 private direct message with peer."""
        self.active_dm_peer = peer_dict
        peer_id = peer_dict["id"]
        self.unread_dms.pop(peer_id, None)

        self.lbl_room_title.config(text=f"🔒 {peer_dict['user_name']}")
        host_str = f" • {peer_dict.get('hostname', 'Device')} ({peer_dict.get('ip', '')})" if peer_dict.get('ip') else ""
        self.lbl_room_sub.config(text=f"Direct 1-on-1 Chat{host_str}")
        self.btn_back_to_room.pack(side=tk.RIGHT, padx=4)

        self.card_public_room.config(bg="#1e293b")
        self.lbl_public_name.config(bg="#1e293b", fg="#94a3b8")

        self._refresh_peers_ui(self.engine.get_online_peers())
        self._refresh_chat_feed()

    def _select_team_room(self):
        """Switches conversation context back to the public team general room."""
        self.active_dm_peer = None
        self.lbl_room_title.config(text="# team-general")
        self.lbl_room_sub.config(text="• Local Wi-Fi broadcast • Real-time across devices")
        self.btn_back_to_room.pack_forget()

        self.card_public_room.config(bg="#2563eb")
        self.lbl_public_name.config(bg="#2563eb", fg="#ffffff")

        self._refresh_peers_ui(self.engine.get_online_peers())
        self._refresh_chat_feed()

    def _message_matches_current_view(self, msg):
        """Returns True if message belongs to current channel (Public room vs active DM peer)."""
        recipient_id = msg.get("recipient_id", "") or ""
        if self.active_dm_peer is None:
            # Public team room: only messages without recipient_id
            return not recipient_id
        else:
            target_peer_id = self.active_dm_peer["id"]
            is_me = msg.get("is_me", False)
            sender_id = msg.get("sender_id", "")
            if is_me and recipient_id == target_peer_id:
                return True
            if (not is_me) and sender_id == target_peer_id and recipient_id == self.engine.user_id:
                return True
            return False

    def _refresh_chat_feed(self):
        """Clears and re-renders messages belonging to currently active channel."""
        for w in self.msg_inner.winfo_children():
            w.destroy()
        self.msg_widgets.clear()
        self.reaction_containers.clear()
        self.find_matches = []
        self.find_index = -1

        for m in self.engine.messages:
            if self._message_matches_current_view(m):
                self._render_message_bubble(m, scroll=False)

        if hasattr(self, "find_bar") and self.find_bar.winfo_viewable() and hasattr(self, "entry_find") and self.entry_find.get().strip():
            self._run_find()

        self.dialog.after(50, lambda: self.msg_canvas.yview_moveto(1.0))

    # ---------- Pinned Announcements Handlers ----------

    def _render_pinned_banner(self, pin_obj=None):
        """Renders or updates the top pinned announcement banner under the room bar."""
        pin_obj = pin_obj or self.engine.pinned_announcement
        for w in self.pin_banner.winfo_children():
            w.destroy()

        if not pin_obj:
            self.pin_banner.pack_forget()
            return

        self.pin_banner.pack(fill=tk.X, side=tk.TOP, pady=(0, 6))

        p_left = tk.Frame(self.pin_banner, bg="#1e293b")
        p_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_pin_icon = tk.Label(p_left, text="📌 ANNOUNCEMENT:", font=font_spec(10, "bold"), fg="#38bdf8", bg="#1e293b")
        lbl_pin_icon.pack(side=tk.LEFT, padx=(0, 6))

        snip = pin_obj.get("text", "").replace("\n", " ")
        if len(snip) > 75:
            snip = snip[:72] + "..."
        by_user = pin_obj.get("user_name", "Team")
        lbl_txt = tk.Label(p_left, text=f'"{snip}" — {by_user}', font=font_spec(11), fg="#f8fafc", bg="#1e293b")
        lbl_txt.pack(side=tk.LEFT)

        btn_jump = tk.Button(
            self.pin_banner,
            text="🔍 Jump",
            font=font_spec(9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=lambda mid=pin_obj.get("msg_id"): self._jump_to_message(mid)
        )
        btn_jump.pack(side=tk.RIGHT, padx=4)

        btn_unpin = tk.Button(
            self.pin_banner,
            text="✕ Unpin",
            font=font_spec(9, "bold"),
            bg="#334155",
            fg="#ef4444",
            activebackground="#475569",
            activeforeground="#f87171",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._unpin_announcement
        )
        btn_unpin.pack(side=tk.RIGHT, padx=2)

    def _pin_message(self, msg_id):
        self.engine.pin_message(msg_id)
        self._render_pinned_banner(self.engine.pinned_announcement)

    def _unpin_announcement(self):
        self.engine.unpin_announcement()
        self._render_pinned_banner(None)

    def _jump_to_message(self, msg_id):
        if not msg_id:
            return
        w = self.msg_widgets.get(msg_id)
        if w and w.winfo_exists():
            try:
                inner_h = self.msg_inner.winfo_height()
                w_y = w.winfo_y()
                if inner_h > 0:
                    pos = max(0.0, min(1.0, w_y / float(inner_h)))
                    self.msg_canvas.yview_moveto(pos)
                    orig_bg = w.cget("bg")
                    w.config(bg="#1e3a8a")
                    self.dialog.after(800, lambda: w.config(bg=orig_bg) if w.winfo_exists() else None)
            except Exception:
                pass

    def _on_engine_pinned_change(self, pin_obj):
        """Invoked by engine when pinned announcement changes across LAN."""
        if not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        self.dialog.after(0, lambda: self._render_pinned_banner(pin_obj))

    # ---------- Thread-Safe Engine Callback Handlers ----------

    def _on_engine_message(self, msg_obj):
        """Invoked by background socket thread when a message is received."""
        if not hasattr(self, "msg_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return

        def _ui_update():
            sender_id = msg_obj.get("sender_id", "")
            is_dm = bool(msg_obj.get("recipient_id"))
            matches_view = self._message_matches_current_view(msg_obj)

            if matches_view:
                self._render_message_bubble(msg_obj, scroll=True)
            elif is_dm and sender_id:
                # Direct message from a colleague who is not currently active
                self.unread_dms[sender_id] = self.unread_dms.get(sender_id, 0) + 1
                self._refresh_peers_ui(self.engine.get_online_peers())

            # Trigger notification sound and in-app toast if from peer
            if not msg_obj.get("is_me", False):
                if not getattr(self, "sound_muted", False):
                    alert_k = "mention" if msg_obj.get("mentioned_me") else "message"
                    play_sound_alert(alert_k)

                sender = msg_obj.get("user_name", "Colleague")
                m_type = msg_obj.get("type", "chat")
                if is_dm:
                    icon = "🔒"
                    prefix = "[Direct Message] "
                elif msg_obj.get("mentioned_me"):
                    icon = "🔔"
                    prefix = "[Mentioned You] "
                elif m_type == "file":
                    icon = "📁"
                    prefix = ""
                elif m_type == "work_update":
                    icon = "📋"
                    prefix = ""
                elif m_type == "poll":
                    icon = "🗳️"
                    prefix = "[Team Poll] "
                else:
                    icon = "💬"
                    prefix = ""

                if m_type == "file":
                    preview = f"{prefix}Shared file: {msg_obj.get('file_name', 'Attachment')} ({msg_obj.get('file_size_str', '')})"
                elif m_type == "work_update":
                    preview = f"{prefix}Shared Work Log: {msg_obj.get('title', '')}"
                elif m_type == "poll":
                    preview = f"{prefix}{msg_obj.get('title') or msg_obj.get('text', 'New poll')}"
                else:
                    preview = f"{prefix}{msg_obj.get('text', 'New message')}"

                # Update dialog title to indicate unread message until focused
                self.dialog.title(f"{icon} (New Message) WorkPulse - LAN Team Chat")

                show_in_app_toast(
                    self.dialog,
                    f"{icon} {sender}",
                    preview,
                    icon=icon,
                    duration_ms=4500
                )

        self.dialog.after(0, _ui_update)

    def _on_engine_peers_change(self, peer_list):
        """Invoked when peers join, leave, or change status."""
        if not hasattr(self, "peers_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        self.dialog.after(0, lambda: self._refresh_peers_ui(peer_list))

    # ---------- Rendering Helpers ----------

    def _refresh_peers_ui(self, peers):
        """Rebuilds the online colleague cards in the left sidebar."""
        if not hasattr(self, "peers_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        for widget in self.peers_inner.winfo_children():
            widget.destroy()

        count = len(peers)
        self.lbl_peer_count.config(text=f"TEAM ON WI-FI ({count})")

        # Update public room card style
        if self.active_dm_peer is None:
            self.card_public_room.config(bg="#2563eb")
            self.lbl_public_name.config(bg="#2563eb", fg="#ffffff")
        else:
            self.card_public_room.config(bg="#1e293b")
            self.lbl_public_name.config(bg="#1e293b", fg="#94a3b8")

        if not peers:
            placeholder = tk.Frame(self.peers_inner, bg="#1e293b", padx=12, pady=18)
            placeholder.pack(fill=tk.X)

            tk.Label(
                placeholder,
                text="📡 Searching Wi-Fi...",
                font=font_spec(12, "bold"),
                fg="#cbd5e1",
                bg="#1e293b"
            ).pack(anchor="w")

            tk.Label(
                placeholder,
                text="Colleagues who open WorkPulse on this Wi-Fi will automatically connect here.\n\nTip: Click 'Add IP' above if your router isolates Wi-Fi clients.",
                font=font_spec(11),
                fg="#64748b",
                bg="#1e293b",
                justify="left",
                wraplength=260
            ).pack(anchor="w", pady=(6, 0))
            return

        for p in peers:
            is_active_dm = bool(self.active_dm_peer and self.active_dm_peer["id"] == p["id"])
            card_bg = "#1e3a8a" if is_active_dm else "#334155"

            p_card = tk.Frame(self.peers_inner, bg=card_bg, padx=10, pady=10, bd=1, relief="solid", cursor="hand2")
            p_card.pack(fill=tk.X, padx=4, pady=3)

            top = tk.Frame(p_card, bg=card_bg)
            top.pack(fill=tk.X)

            avatar = tk.Label(
                top,
                text=get_initials(p["user_name"]),
                font=font_spec(11, "bold"),
                fg="#ffffff",
                bg=p.get("avatar_color", AVATAR_PALETTE[0]),
                width=3,
                height=1,
                relief="flat",
                cursor="hand2"
            )
            avatar.pack(side=tk.LEFT, padx=(0, 8))

            info = tk.Frame(top, bg=card_bg)
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)

            name_row = tk.Frame(info, bg=card_bg)
            name_row.pack(fill=tk.X)

            name_lbl = tk.Label(
                name_row,
                text=p["user_name"],
                font=font_spec(12, "bold"),
                fg="#ffffff",
                bg=card_bg,
                cursor="hand2"
            )
            name_lbl.pack(side=tk.LEFT)

            unread_cnt = self.unread_dms.get(p["id"], 0)
            if unread_cnt > 0:
                badge = tk.Label(
                    name_row,
                    text=f" {unread_cnt} new ",
                    font=font_spec(9, "bold"),
                    fg="#ffffff",
                    bg="#ef4444",
                    padx=4,
                    pady=1
                )
                badge.pack(side=tk.RIGHT, padx=2)

            status_str = f"{p.get('status_emoji', '🟢')} {p.get('status', 'Available')}"
            status_lbl = tk.Label(
                info,
                text=status_str,
                font=font_spec(11),
                fg="#38bdf8",
                bg=card_bg,
                cursor="hand2"
            )
            status_lbl.pack(anchor="w")

            if p.get("status_note"):
                note_lbl = tk.Label(
                    info,
                    text=f'💬 "{p["status_note"]}"',
                    font=font_spec(10, slant="italic"),
                    fg="#cbd5e1",
                    bg=card_bg,
                    cursor="hand2",
                    wraplength=180,
                    justify="left"
                )
                note_lbl.pack(anchor="w")
                note_lbl.bind("<Button-1>", lambda e, pr=p: self._select_dm_peer(pr))

            ip_lbl = tk.Label(
                p_card,
                text=f"{p.get('hostname', 'Device')} • Click to DM 💬",
                font=font_spec(10),
                fg="#94a3b8",
                bg=card_bg,
                cursor="hand2"
            )
            ip_lbl.pack(anchor="w", pady=(4, 0))

            def _bind_dm_click(w, peer_obj=p):
                w.bind("<Button-1>", lambda e: self._select_dm_peer(peer_obj))

            _bind_dm_click(p_card)
            _bind_dm_click(top)
            _bind_dm_click(avatar)
            _bind_dm_click(info)
            _bind_dm_click(name_row)
            _bind_dm_click(name_lbl)
            _bind_dm_click(status_lbl)
            _bind_dm_click(ip_lbl)

    def _render_message_content(self, parent, text, bg_color, is_me=False):
        """
        Renders message text with rich code snippet blocks (syntax header + 1-click copy)
        or falls back to standard text wrap.
        """
        if not text:
            return
        segs = parse_code_blocks(text)
        if len(segs) == 1 and segs[0][0] == "text":
            tk.Label(
                parent,
                text=text,
                font=font_spec(12),
                fg="#ffffff",
                bg=bg_color,
                wraplength=540,
                justify="left"
            ).pack(anchor="w")
            return

        for seg in segs:
            if seg[0] == "text":
                txt = seg[1].strip("\n")
                if txt:
                    tk.Label(
                        parent,
                        text=txt,
                        font=font_spec(12),
                        fg="#ffffff",
                        bg=bg_color,
                        wraplength=540,
                        justify="left"
                    ).pack(anchor="w", pady=2)
            elif seg[0] == "code":
                lang = seg[1] or "CODE"
                code_body = seg[2].strip("\n")
                code_card = tk.Frame(parent, bg="#0b0f19", bd=1, relief="solid")
                code_card.pack(fill=tk.X, expand=True, pady=4)

                c_header = tk.Frame(code_card, bg="#111827", padx=8, pady=4)
                c_header.pack(fill=tk.X)

                tk.Label(
                    c_header,
                    text=f"💻 {lang.upper()}",
                    font=font_spec(9, "bold"),
                    fg="#38bdf8",
                    bg="#111827"
                ).pack(side=tk.LEFT)

                btn_copy = tk.Label(
                    c_header,
                    text="📋 Copy Code",
                    font=font_spec(9, "bold"),
                    fg="#94a3b8",
                    bg="#111827",
                    cursor="hand2"
                )
                btn_copy.pack(side=tk.RIGHT)

                def _do_copy(c_str=code_body, lbl=btn_copy):
                    try:
                        self.dialog.clipboard_clear()
                        self.dialog.clipboard_append(c_str)
                        lbl.config(text="✅ Copied!", fg="#10b981")
                        self.dialog.after(2000, lambda: lbl.config(text="📋 Copy Code", fg="#94a3b8"))
                    except Exception:
                        pass

                btn_copy.bind("<Button-1>", lambda e, fn=_do_copy: fn())
                btn_copy.bind("<Enter>", lambda e, b=btn_copy: b.config(fg="#ffffff"))
                btn_copy.bind("<Leave>", lambda e, b=btn_copy: b.config(fg="#94a3b8"))

                tk.Label(
                    code_card,
                    text=code_body,
                    font=("Courier", 10),
                    fg="#f1f5f9",
                    bg="#0b0f19",
                    justify="left",
                    anchor="w",
                    padx=10,
                    pady=8
                ).pack(fill=tk.X, expand=True)

    def _render_message_bubble(self, msg, scroll=True):
        """Renders chat messages, work updates, or shared file cards into the canvas."""
        if not hasattr(self, "msg_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        if not self._message_matches_current_view(msg):
            return

        m_type = msg.get("type", "chat")
        is_me = msg.get("is_me", False)
        sender = msg.get("user_name", "Colleague")
        time_str = msg.get("time_str", "")
        avatar_bg = msg.get("avatar_color", AVATAR_PALETTE[0])
        msg_id = msg.get("id") or uuid.uuid4().hex[:12]
        msg["id"] = msg_id

        recipient_id = msg.get("recipient_id", "") or ""
        is_dm = bool(recipient_id)
        is_pinned = bool(msg.get("is_pinned", False))
        text_content = msg.get("text", "") or msg.get("caption", "") or msg.get("title", "")
        my_tag = f"@{self.engine.user_name.lower()}"
        is_mentioned = bool(msg.get("mentioned_me") or "@all" in text_content.lower() or "@team" in text_content.lower() or my_tag in text_content.lower())

        row_frame = tk.Frame(self.msg_inner, bg="#0f172a")
        row_frame.pack(fill=tk.X, padx=12, pady=5)
        row_frame._msg_data = msg
        row_frame._highlight_target = None
        self.msg_widgets[msg_id] = row_frame

        def _bind_context_menu(target_w):
            def _popup(event):
                menu = tk.Menu(
                    self.dialog, tearoff=0, bg="#1e293b", fg="#ffffff",
                    activebackground="#2563eb", activeforeground="#ffffff",
                    font=font_spec(10)
                )
                menu.add_command(label="↩️ Reply", command=lambda: self._start_reply(msg))
                menu.add_command(label="😊 Add Reaction", command=lambda: self._show_reaction_picker(msg_id, target_w))
                menu.add_command(label="📌 Pin Announcement", command=lambda: self._pin_message(msg_id))
                copy_text = msg.get("text") or msg.get("file_name") or msg.get("title") or ""
                if copy_text:
                    def _copy():
                        self.dialog.clipboard_clear()
                        self.dialog.clipboard_append(copy_text)
                    menu.add_command(label="📋 Copy Text", command=_copy)
                menu.add_command(label="🗑️ Delete Message", command=lambda: self._prompt_delete_message(msg))
                menu.tk_popup(event.x_root, event.y_root)
            target_w.bind("<Button-3>", _popup)

        reply_to = msg.get("reply_to")

        if m_type == "work_update":
            # ----------------- WORK UPDATE CARD -----------------
            card = tk.Frame(row_frame, bg="#1e293b", bd=1, relief="solid", padx=14, pady=12)
            card.pack(fill=tk.X, padx=8, pady=4)
            row_frame._highlight_target = card

            c_header = tk.Frame(card, bg="#1e293b")
            c_header.pack(fill=tk.X, pady=(0, 8))

            av = tk.Label(
                c_header,
                text=get_initials(sender),
                font=font_spec(11, "bold"),
                fg="#ffffff",
                bg=avatar_bg,
                width=3,
                height=1
            )
            av.pack(side=tk.LEFT, padx=(0, 8))

            # Delete button (rightmost)
            btn_del = tk.Label(c_header, text="🗑️", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_del.pack(side=tk.RIGHT, padx=(4, 0))
            btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
            btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
            btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

            # React button
            btn_react = tk.Label(c_header, text="😊", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_react.pack(side=tk.RIGHT, padx=(4, 0))
            btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
            btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
            btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

            # Reply button
            btn_reply = tk.Label(c_header, text="↩️", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
            btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
            btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
            btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

            tk.Label(
                c_header,
                text=time_str,
                font=font_spec(10),
                fg="#64748b",
                bg="#1e293b"
            ).pack(side=tk.RIGHT)

            tk.Label(
                c_header,
                text=f"📋 {msg.get('title', 'Work Summary')} - {sender}",
                font=font_spec(13, "bold"),
                fg="#38bdf8",
                bg="#1e293b"
            ).pack(side=tk.LEFT)

            if is_pinned:
                tk.Label(c_header, text="📌 Pinned", font=font_spec(9, "bold"), bg="#334155", fg="#38bdf8", padx=5, pady=1).pack(side=tk.LEFT, padx=4)

            # Quoted reply preview if any
            if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                r_box = tk.Frame(card, bg="#0f172a", bd=1, relief="solid", padx=10, pady=5)
                r_box.pack(fill=tk.X, pady=(0, 8))
                tk.Label(r_box, text=f"↳ Replying to {reply_to.get('user_name', 'Colleague')}", font=font_spec(10, "bold"), fg="#38bdf8", bg="#0f172a").pack(anchor="w")
                if reply_to.get("text"):
                    tk.Label(r_box, text=reply_to["text"], font=font_spec(10, slant="italic"), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

            # Shift & Total Hours bar
            meta_box = tk.Frame(card, bg="#334155", padx=10, pady=6)
            meta_box.pack(fill=tk.X, pady=(0, 8))

            meta_parts = []
            if msg.get("shift_str"):
                meta_parts.append(msg["shift_str"])
            if msg.get("total_hours"):
                meta_parts.append(f"Total: {msg['total_hours']}")
            meta_text = "  |  ".join(meta_parts) if meta_parts else f"Date: {msg.get('date_str', '')}"

            tk.Label(
                meta_box,
                text=meta_text,
                font=font_spec(11, "bold"),
                fg="#f1f5f9",
                bg="#334155"
            ).pack(anchor="w")

            # Tasks List
            tasks = msg.get("tasks", [])
            for t in tasks:
                t_row = tk.Frame(card, bg="#1e293b")
                t_row.pack(fill=tk.X, pady=3)

                st = t.get("status", "Completed")
                st_color = "#10b981" if "Complete" in st else ("#f59e0b" if "Progress" in st else "#94a3b8")

                tk.Label(
                    t_row,
                    text=f"[{st}]",
                    font=font_spec(11, "bold"),
                    fg=st_color,
                    bg="#1e293b"
                ).pack(side=tk.LEFT, padx=(0, 8))

                title_txt = t.get("title", "Task")
                hours_txt = f"({t.get('hours')}h)" if t.get("hours") else ""
                tk.Label(
                    t_row,
                    text=f"{title_txt} {hours_txt}",
                    font=font_spec(12),
                    fg="#e2e8f0",
                    bg="#1e293b"
                ).pack(side=tk.LEFT, anchor="w")

            # Reactions pill container
            rx_frame = tk.Frame(card, bg="#1e293b")
            rx_frame.pack(fill=tk.X, pady=(8, 0))
            self.reaction_containers[msg_id] = rx_frame
            self._render_reaction_pills(msg_id, msg.get("reactions") or {})

            _bind_context_menu(card)
            _bind_context_menu(c_header)

        elif m_type == "poll":
            # ----------------- TEAM POLL CARD -----------------
            card = tk.Frame(row_frame, bg="#1e293b", bd=1, relief="solid", padx=14, pady=12)
            card.pack(fill=tk.X, padx=8, pady=4)
            row_frame._highlight_target = card

            c_header = tk.Frame(card, bg="#1e293b")
            c_header.pack(fill=tk.X, pady=(0, 8))

            av = tk.Label(
                c_header,
                text=get_initials(sender),
                font=font_spec(11, "bold"),
                fg="#ffffff",
                bg=avatar_bg,
                width=3,
                height=1
            )
            av.pack(side=tk.LEFT, padx=(0, 8))

            # Delete button (rightmost)
            btn_del = tk.Label(c_header, text="🗑️", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_del.pack(side=tk.RIGHT, padx=(4, 0))
            btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
            btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
            btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

            # React button
            btn_react = tk.Label(c_header, text="😊", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_react.pack(side=tk.RIGHT, padx=(4, 0))
            btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
            btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
            btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

            # Reply button
            btn_reply = tk.Label(c_header, text="↩️", font=font_spec(10), fg="#64748b", bg="#1e293b", cursor="hand2")
            btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
            btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
            btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
            btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

            tk.Label(
                c_header,
                text=time_str,
                font=font_spec(10),
                fg="#64748b",
                bg="#1e293b"
            ).pack(side=tk.RIGHT)

            tk.Label(
                c_header,
                text=f"🗳️ Team Poll • {sender}",
                font=font_spec(13, "bold"),
                fg="#f59e0b",
                bg="#1e293b"
            ).pack(side=tk.LEFT)

            if is_dm:
                tk.Label(c_header, text="🔒 DM", font=font_spec(9, "bold"), fg="#ffffff", bg="#0284c7", padx=5, pady=1).pack(side=tk.LEFT, padx=3)
            if is_pinned:
                tk.Label(c_header, text="📌 Pinned", font=font_spec(9, "bold"), bg="#334155", fg="#38bdf8", padx=5, pady=1).pack(side=tk.LEFT, padx=4)

            # Poll Question
            question_txt = msg.get("title") or msg.get("text") or "Team Poll"
            tk.Label(
                card,
                text=question_txt,
                font=font_spec(13, "bold"),
                fg="#f8fafc",
                bg="#1e293b",
                wraplength=520,
                justify="left"
            ).pack(anchor="w", pady=(0, 10))

            # Options
            options = msg.get("tasks") or []
            total_votes = sum(len(opt.get("votes", [])) for opt in options)

            for opt in options:
                opt_id = opt.get("id")
                opt_text = opt.get("text", "Option")
                votes = opt.get("votes", [])
                v_count = len(votes)
                pct = int((v_count / total_votes * 100)) if total_votes > 0 else 0
                has_my_vote = self.engine.user_name in votes

                opt_row = tk.Frame(card, bg="#334155", bd=1, relief="solid", cursor="hand2")
                opt_row.pack(fill=tk.X, pady=3)

                bar_bg = "#2563eb" if has_my_vote else "#1e3a8a"
                bar_f = tk.Frame(opt_row, bg=bar_bg, padx=10, pady=6, cursor="hand2")
                bar_f.pack(fill=tk.BOTH, expand=True)

                check_icon = "✅ " if has_my_vote else "⚪ "
                lbl_opt_txt = tk.Label(
                    bar_f,
                    text=f"{check_icon}{opt_text}",
                    font=font_spec(11, "bold" if has_my_vote else "normal"),
                    fg="#ffffff",
                    bg=bar_bg,
                    cursor="hand2"
                )
                lbl_opt_txt.pack(side=tk.LEFT)

                lbl_pct = tk.Label(
                    bar_f,
                    text=f"{pct}% ({v_count})",
                    font=font_spec(11, "bold"),
                    fg="#f1f5f9",
                    bg=bar_bg,
                    cursor="hand2"
                )
                lbl_pct.pack(side=tk.RIGHT)

                def _cast_vote(e, oid=opt_id, mid=msg_id):
                    self.engine.cast_poll_vote(mid, oid)

                opt_row.bind("<Button-1>", _cast_vote)
                bar_f.bind("<Button-1>", _cast_vote)
                lbl_opt_txt.bind("<Button-1>", _cast_vote)
                lbl_pct.bind("<Button-1>", _cast_vote)

            # Poll footer: total votes & voter list
            voters_list = []
            for opt in options:
                if opt.get("votes"):
                    voters_list.append(f"{opt.get('text')}: {', '.join(opt['votes'])}")

            voters_str = f" • Voters: {'; '.join(voters_list)}" if voters_list else ""
            tk.Label(
                card,
                text=f"Total: {total_votes} vote{'s' if total_votes != 1 else ''}{voters_str}",
                font=font_spec(10),
                fg="#94a3b8",
                bg="#1e293b",
                wraplength=520,
                justify="left"
            ).pack(anchor="w", pady=(8, 0))

            # Reactions pill container
            rx_frame = tk.Frame(card, bg="#1e293b")
            rx_frame.pack(fill=tk.X, pady=(6, 0))
            self.reaction_containers[msg_id] = rx_frame
            self._render_reaction_pills(msg_id, msg.get("reactions") or {})

            _bind_context_menu(card)
            _bind_context_menu(c_header)

        elif m_type == "file":
            # ----------------- FILE / INLINE IMAGE CARD -----------------
            f_name = msg.get("file_name", "Shared File")
            f_size_str = msg.get("file_size_str") or format_file_size(msg.get("file_size", 0))
            f_icon = get_file_icon(f_name)
            local_path = msg.get("local_path", "")
            has_local = bool(local_path and os.path.exists(local_path))
            is_image = bool(msg.get("is_image")) or is_image_file(f_name)
            caption = msg.get("caption", "")

            card_align = tk.RIGHT if is_me else tk.LEFT
            align_box = tk.Frame(row_frame, bg="#0f172a")
            align_box.pack(side=card_align, padx=4)

            top_info = tk.Frame(align_box, bg="#0f172a")
            top_info.pack(anchor="e" if is_me else "w", pady=(0, 3), fill=tk.X)

            if not is_me:
                av = tk.Label(
                    top_info,
                    text=get_initials(sender),
                    font=font_spec(10, "bold"),
                    fg="#ffffff",
                    bg=avatar_bg,
                    width=3,
                    height=1
                )
                av.pack(side=tk.LEFT, padx=(0, 6))
                tk.Label(
                    top_info,
                    text=f"{sender} • {time_str}",
                    font=font_spec(11, "bold"),
                    fg="#94a3b8",
                    bg="#0f172a"
                ).pack(side=tk.LEFT)

                if is_dm:
                    tk.Label(top_info, text="🔒 DM", font=font_spec(9, "bold"), fg="#ffffff", bg="#0284c7", padx=5, pady=1).pack(side=tk.LEFT, padx=3)
                if is_pinned:
                    tk.Label(top_info, text="📌 Pinned", font=font_spec(9, "bold"), fg="#38bdf8", bg="#334155", padx=5, pady=1).pack(side=tk.LEFT, padx=3)
                if is_mentioned:
                    tk.Label(top_info, text="🔔 Mentioned You", font=font_spec(9, "bold"), fg="#000000", bg="#f59e0b", padx=6, pady=1).pack(side=tk.LEFT, padx=3)

                btn_del = tk.Label(top_info, text="🗑️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_del.pack(side=tk.RIGHT, padx=(4, 0))
                btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
                btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
                btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

                btn_react = tk.Label(top_info, text="😊", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_react.pack(side=tk.RIGHT, padx=(4, 0))
                btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
                btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
                btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

                btn_reply = tk.Label(top_info, text="↩️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
                btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
                btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
                btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

            else:
                btn_del = tk.Label(top_info, text="🗑️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_del.pack(side=tk.RIGHT, padx=(4, 0))
                btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
                btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
                btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

                btn_react = tk.Label(top_info, text="😊", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_react.pack(side=tk.RIGHT, padx=(4, 0))
                btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
                btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
                btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

                btn_reply = tk.Label(top_info, text="↩️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
                btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
                btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
                btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

                tk.Label(
                    top_info,
                    text=f"You • {time_str}",
                    font=font_spec(10),
                    fg="#64748b",
                    bg="#0f172a"
                ).pack(side=tk.RIGHT)

                if is_dm:
                    tk.Label(top_info, text="🔒 DM", font=font_spec(9, "bold"), fg="#ffffff", bg="#0284c7", padx=5, pady=1).pack(side=tk.RIGHT, padx=3)
                if is_pinned:
                    tk.Label(top_info, text="📌 Pinned", font=font_spec(9, "bold"), fg="#38bdf8", bg="#334155", padx=5, pady=1).pack(side=tk.RIGHT, padx=3)

            card = tk.Frame(align_box, bg="#1e293b", bd=1, relief="solid", padx=14, pady=10)
            card.pack(anchor="e" if is_me else "w")
            row_frame._highlight_target = card

            # Quoted reply preview if any
            if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                r_box = tk.Frame(card, bg="#0f172a", bd=1, relief="solid", padx=8, pady=4)
                r_box.pack(anchor="w", fill=tk.X, pady=(0, 6))
                tk.Label(r_box, text=f"↳ Replying to {reply_to.get('user_name', 'Colleague')}", font=font_spec(10, "bold"), fg="#38bdf8", bg="#0f172a").pack(anchor="w")
                if reply_to.get("text"):
                    tk.Label(r_box, text=reply_to["text"], font=font_spec(10, slant="italic"), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

            content_box = tk.Frame(card, bg="#1e293b")
            content_box.pack(fill=tk.X)

            # Check if this is an image with an available local file
            rendered_image = False
            if is_image and has_local:
                thumb = create_tk_thumbnail(local_path, max_w=340, max_h=240)
                if thumb:
                    rendered_image = True
                    self._photo_cache[f"{msg_id}_img"] = thumb
                    lbl_thumb = tk.Label(content_box, image=thumb, bg="#1e293b", cursor="hand2")
                    lbl_thumb.pack(anchor="w", pady=(2, 6))
                    lbl_thumb.bind("<Button-1>", lambda e, p=local_path: open_file_externally(p))

                    if caption:
                        tk.Label(
                            content_box,
                            text=caption,
                            font=font_spec(12),
                            fg="#ffffff",
                            bg="#1e293b",
                            wraplength=380,
                            justify="left"
                        ).pack(anchor="w", pady=(0, 4))

                    lbl_meta = tk.Label(
                        content_box,
                        text=f"🖼️ {f_name} ({f_size_str}) • Click to view full size",
                        font=font_spec(10),
                        fg="#94a3b8",
                        bg="#1e293b"
                    )
                    lbl_meta.pack(anchor="w")

                    btn_box = tk.Frame(card, bg="#1e293b")
                    btn_box.pack(fill=tk.X, pady=(8, 0))

                    tk.Button(
                        btn_box,
                        text="📂 Open Image",
                        font=font_spec(11, "bold"),
                        bg="#2563eb",
                        fg="white",
                        activebackground="#1d4ed8",
                        activeforeground="white",
                        relief="flat",
                        padx=12,
                        pady=4,
                        cursor="hand2",
                        command=lambda p=local_path: open_file_externally(p)
                    ).pack(side=tk.LEFT, padx=3)

                    tk.Button(
                        btn_box,
                        text="📁 Show in Folder",
                        font=font_spec(11),
                        bg="#334155",
                        fg="#f1f5f9",
                        activebackground="#475569",
                        activeforeground="#ffffff",
                        relief="flat",
                        padx=12,
                        pady=4,
                        cursor="hand2",
                        command=lambda p=local_path: show_in_file_manager(p)
                    ).pack(side=tk.LEFT, padx=3)

            if not rendered_image:
                card_icon = "🖼️" if is_image else f_icon
                lbl_icon = tk.Label(content_box, text=card_icon, font=font_spec(24), bg="#1e293b")
                lbl_icon.pack(side=tk.LEFT, padx=(0, 12))

                info_box = tk.Frame(content_box, bg="#1e293b")
                info_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

                if caption:
                    lbl_caption = tk.Label(
                        info_box,
                        text=caption,
                        font=font_spec(12, "bold"),
                        fg="#ffffff",
                        bg="#1e293b",
                        wraplength=420,
                        justify="left"
                    )
                    lbl_caption.pack(anchor="w", pady=(0, 2))

                lbl_fname = tk.Label(
                    info_box,
                    text=f_name,
                    font=font_spec(11 if caption else 12, "bold" if not caption else "normal"),
                    fg="#e2e8f0" if caption else "#ffffff",
                    bg="#1e293b",
                    wraplength=420,
                    justify="left"
                )
                lbl_fname.pack(anchor="w")

                lbl_fmeta = tk.Label(
                    info_box,
                    text=f"{f_size_str} • {'Shared by you' if is_me else 'LAN Transfer'}",
                    font=font_spec(10),
                    fg="#94a3b8",
                    bg="#1e293b"
                )
                lbl_fmeta.pack(anchor="w", pady=(3, 0))

                btn_box = tk.Frame(card, bg="#1e293b")
                btn_box.pack(fill=tk.X, pady=(10, 0))

                if has_local or is_me:
                    target_p = local_path if (local_path and os.path.exists(local_path)) else ""

                    tk.Label(
                        btn_box,
                        text="✅ Saved",
                        font=font_spec(11, "bold"),
                        fg="#10b981",
                        bg="#1e293b"
                    ).pack(side=tk.LEFT, padx=(0, 8))

                    if target_p:
                        tk.Button(
                            btn_box,
                            text="📂 Open File",
                            font=font_spec(11, "bold"),
                            bg="#2563eb",
                            fg="white",
                            activebackground="#1d4ed8",
                            activeforeground="white",
                            relief="flat",
                            padx=12,
                            pady=4,
                            cursor="hand2",
                            command=lambda p=target_p: open_file_externally(p)
                        ).pack(side=tk.LEFT, padx=3)

                        tk.Button(
                            btn_box,
                            text="📁 Show in Folder",
                            font=font_spec(11),
                            bg="#334155",
                            fg="#f1f5f9",
                            activebackground="#475569",
                            activeforeground="#ffffff",
                            relief="flat",
                            padx=12,
                            pady=4,
                            cursor="hand2",
                            command=lambda p=target_p: show_in_file_manager(p)
                        ).pack(side=tk.LEFT, padx=3)
                else:
                    cancel_evt = threading.Event()
                    active_hud = [None]

                    ext = os.path.splitext(f_name)[1].lower()
                    is_media = ext in (
                        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".3gp", ".ts", ".ogv",
                        ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus"
                    )
                    is_browser_doc = ext in (".pdf", ".html", ".htm", ".svg", ".txt")
                    view_btn_text = "▶️ View" if is_media else "👁️ View"

                    def _start_download(custom_path=None, is_preview=False):
                        btn_view.pack_forget()
                        btn_dl.pack_forget()
                        btn_save_as.pack_forget()

                        hud_frame = tk.Frame(card, bg="#0f172a", bd=1, relief="solid", padx=10, pady=8)
                        hud_frame.pack(before=btn_box, fill=tk.X, pady=(4, 6))
                        active_hud[0] = hud_frame

                        top_stat = tk.Frame(hud_frame, bg="#0f172a")
                        top_stat.pack(fill=tk.X)

                        init_title = "👁️ Loading preview in memory..." if is_preview else "⏳ Connecting to peer..."
                        lbl_status = tk.Label(top_stat, text=init_title, font=font_spec(10, "bold"), fg="#38bdf8", bg="#0f172a")
                        lbl_status.pack(side=tk.LEFT)

                        lbl_speed = tk.Label(top_stat, text="", font=font_spec(10), fg="#94a3b8", bg="#0f172a")
                        lbl_speed.pack(side=tk.RIGHT)

                        # Custom smooth fill progress bar
                        prog_track = tk.Frame(hud_frame, bg="#334155", height=6)
                        prog_track.pack(fill=tk.X, pady=(6, 4))
                        prog_fill = tk.Frame(prog_track, bg="#2563eb", height=6, width=0)
                        prog_fill.place(x=0, y=0, relheight=1.0, width=0)

                        def _cancel_download():
                            cancel_evt.set()
                            if active_hud[0] and active_hud[0].winfo_exists():
                                active_hud[0].destroy()
                            if btn_cancel.winfo_exists():
                                btn_cancel.destroy()
                            btn_view.pack(side=tk.LEFT, padx=3)
                            btn_dl.pack(side=tk.LEFT, padx=3)
                            btn_save_as.pack(side=tk.LEFT, padx=3)
                            btn_view.config(state="normal")
                            btn_dl.config(state="normal")
                            btn_save_as.config(state="normal")

                        btn_cancel = tk.Button(
                            btn_box,
                            text="✕ Cancel",
                            font=font_spec(10, "bold"),
                            bg="#7f1d1d",
                            fg="#fca5a5",
                            activebackground="#991b1b",
                            activeforeground="#ffffff",
                            relief="flat",
                            padx=12,
                            pady=4,
                            cursor="hand2",
                            command=_cancel_download
                        )
                        btn_cancel.pack(side=tk.LEFT, padx=3)

                        def _on_prog(cur, tot, spd=0.0, eta=0.0):
                            pct = int((cur / tot) * 100) if tot > 0 else 0
                            cur_str = format_file_size(cur)
                            tot_str = format_file_size(tot)
                            spd_str = f"{format_file_size(spd)}/s" if spd > 0 else ""
                            eta_str = f"ETA: {int(eta)}s" if eta > 0 else ""
                            stat_sub = f"{spd_str}  {eta_str}".strip()

                            def _ui_p():
                                if not hud_frame.winfo_exists():
                                    return
                                prefix = "👁️ Preview:" if is_preview else "📥"
                                lbl_status.config(text=f"{prefix} {pct}% • {cur_str} / {tot_str}")
                                lbl_speed.config(text=stat_sub)
                                trk_w = prog_track.winfo_width()
                                if trk_w > 1 and tot > 0:
                                    prog_fill.place_configure(width=max(2, int((cur / tot) * trk_w)))
                            self.dialog.after(0, _ui_p)

                        def _on_finish(saved_path):
                            def _ui_done():
                                if active_hud[0] and active_hud[0].winfo_exists():
                                    active_hud[0].destroy()
                                if btn_cancel.winfo_exists():
                                    btn_cancel.destroy()

                                if not getattr(self, "sound_muted", False):
                                    play_sound_alert("complete")

                                if is_preview:
                                    btn_view.pack(side=tk.LEFT, padx=3)
                                    btn_dl.pack(side=tk.LEFT, padx=3)
                                    btn_save_as.pack(side=tk.LEFT, padx=3)
                                    btn_view.config(state="normal")
                                    btn_dl.config(state="normal")
                                    btn_save_as.config(state="normal")

                                    open_file_externally(saved_path)
                                    show_in_app_toast(
                                        self.dialog,
                                        title="Preview Ready",
                                        message=f"👁️ Opened '{f_name}' from temporary memory\n(No permanent disk space consumed)",
                                        icon="👁️",
                                        duration_ms=4000
                                    )
                                    return

                                f_sz = os.path.getsize(saved_path) if os.path.exists(saved_path) else 0
                                lbl_done = tk.Label(btn_box, text=f"✅ Saved ({format_file_size(f_sz)})", font=font_spec(10, "bold"), fg="#10b981", bg="#1e293b")
                                lbl_done.pack(side=tk.LEFT, padx=(0, 6))

                                # If image, attempt to load thumbnail right into card
                                if is_image:
                                    img_thumb = create_tk_thumbnail(saved_path, max_w=340, max_h=240)
                                    if img_thumb:
                                        self._photo_cache[f"{msg_id}_img"] = img_thumb
                                        lbl_img_prev = tk.Label(card, image=img_thumb, bg="#1e293b", cursor="hand2")
                                        lbl_img_prev.pack(before=btn_box, anchor="w", pady=(4, 6))
                                        lbl_img_prev.bind("<Button-1>", lambda e, p=saved_path: open_file_externally(p))

                                tk.Button(
                                    btn_box,
                                    text="📂 Open File",
                                    font=font_spec(11, "bold"),
                                    bg="#2563eb",
                                    fg="white",
                                    activebackground="#1d4ed8",
                                    activeforeground="white",
                                    relief="flat",
                                    padx=12,
                                    pady=4,
                                    cursor="hand2",
                                    command=lambda p=saved_path: open_file_externally(p)
                                ).pack(side=tk.LEFT, padx=3)

                                tk.Button(
                                    btn_box,
                                    text="📁 Show in Folder",
                                    font=font_spec(11),
                                    bg="#334155",
                                    fg="#f1f5f9",
                                    activebackground="#475569",
                                    activeforeground="#ffffff",
                                    relief="flat",
                                    padx=12,
                                    pady=4,
                                    cursor="hand2",
                                    command=lambda p=saved_path: show_in_file_manager(p)
                                ).pack(side=tk.LEFT, padx=3)
                            self.dialog.after(0, _ui_done)

                        def _on_err(err_msg):
                            def _ui_err():
                                if active_hud[0] and active_hud[0].winfo_exists():
                                    active_hud[0].destroy()
                                if btn_cancel.winfo_exists():
                                    btn_cancel.destroy()
                                btn_view.pack(side=tk.LEFT, padx=3)
                                btn_dl.pack(side=tk.LEFT, padx=3)
                                btn_save_as.pack(side=tk.LEFT, padx=3)
                                btn_view.config(state="normal")
                                btn_dl.config(state="normal")
                                btn_save_as.config(state="normal")
                                if "cancelled" not in err_msg.lower():
                                    messagebox.showerror("Transfer Error", f"Could not load or download file:\n{err_msg}", parent=self.dialog)
                            self.dialog.after(0, _ui_err)

                        target_dir = SCREENSHOT_DIR if is_image else None
                        self.engine.download_file(
                            msg,
                            target_dir=target_dir,
                            custom_save_path=custom_path,
                            on_progress=_on_prog,
                            on_done=_on_finish,
                            on_error=_on_err,
                            cancel_event=cancel_evt
                        )

                    def _view_file():
                        f_ip = msg.get("file_ip") or msg.get("sender_ip")
                        f_port = msg.get("file_port")
                        f_id = msg.get("file_id")
                        if not f_ip or not f_port or not f_id:
                            messagebox.showerror("View File", "Connection details missing for this peer file.", parent=self.dialog)
                            return

                        stream_url = f"http://{f_ip}:{f_port}/files/{f_id}/{urllib.parse.quote(f_name)}"

                        # 1. Video & Audio files: Direct streaming (zero permanent disk space!)
                        if is_media:
                            opened_stream = False
                            if sys.platform.startswith("linux"):
                                media_players = ["showtime", "vlc", "mpv", "celluloid", "totem", "ffplay"]
                                for player in media_players:
                                    if shutil.which(player):
                                        try:
                                            subprocess.Popen([player, stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                            opened_stream = True
                                            break
                                        except Exception:
                                            pass
                            elif sys.platform == "darwin":
                                try:
                                    subprocess.Popen(["open", stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    opened_stream = True
                                except Exception:
                                    pass
                            elif sys.platform == "win32":
                                try:
                                    os.startfile(stream_url)
                                    opened_stream = True
                                except Exception:
                                    pass

                            if not opened_stream:
                                try:
                                    webbrowser.open(stream_url)
                                    opened_stream = True
                                except Exception:
                                    pass

                            if opened_stream:
                                show_in_app_toast(
                                    self.dialog,
                                    title="Streaming Live Preview",
                                    message=f"▶️ Streaming '{f_name}' directly across Wi-Fi\n(Zero disk space consumed)",
                                    icon="▶️",
                                    duration_ms=4000
                                )
                                return

                        # 2. Browser viewable documents (PDF, HTML, SVG, TXT):
                        if is_browser_doc:
                            try:
                                webbrowser.open(stream_url)
                                show_in_app_toast(
                                    self.dialog,
                                    title="Opening Live Preview",
                                    message=f"👁️ Previewing '{f_name}' in browser\n(Zero disk space consumed)",
                                    icon="👁️",
                                    duration_ms=3500
                                )
                                return
                            except Exception:
                                pass

                        # 3. All other file types (images, office documents, archives, code):
                        # Preview via temporary RAM cache (/tmp/workpulse_preview/) - zero permanent disk storage!
                        preview_dir = os.path.join(tempfile.gettempdir(), "workpulse_preview")
                        os.makedirs(preview_dir, exist_ok=True)
                        temp_preview_path = os.path.join(preview_dir, f_name)

                        if os.path.exists(temp_preview_path) and os.path.getsize(temp_preview_path) > 0:
                            open_file_externally(temp_preview_path)
                            show_in_app_toast(
                                self.dialog,
                                title="Temporary Preview",
                                message=f"👁️ Opened '{f_name}' from temporary cache",
                                icon="👁️",
                                duration_ms=3000
                            )
                            return

                        _start_download(custom_path=temp_preview_path, is_preview=True)

                    def _prompt_save_as():
                        chosen = choose_save_dialog(
                            parent=self.dialog,
                            title="Save File As",
                            default_name=f_name
                        )
                        if chosen:
                            _start_download(custom_path=chosen, is_preview=False)

                    btn_view = tk.Button(
                        btn_box,
                        text=view_btn_text,
                        font=font_spec(11, "bold"),
                        bg="#0284c7",
                        fg="white",
                        activebackground="#0369a1",
                        activeforeground="white",
                        relief="flat",
                        padx=14,
                        pady=5,
                        cursor="hand2",
                        command=_view_file
                    )
                    btn_view.pack(side=tk.LEFT, padx=3)

                    btn_dl = tk.Button(
                        btn_box,
                        text="⬇️ Download",
                        font=font_spec(11, "bold"),
                        bg="#059669",
                        fg="white",
                        activebackground="#047857",
                        activeforeground="white",
                        relief="flat",
                        padx=14,
                        pady=5,
                        cursor="hand2",
                        command=lambda: _start_download(is_preview=False)
                    )
                    btn_dl.pack(side=tk.LEFT, padx=3)

                    btn_save_as = tk.Button(
                        btn_box,
                        text="💾 Save As...",
                        font=font_spec(11),
                        bg="#334155",
                        fg="#f1f5f9",
                        activebackground="#475569",
                        activeforeground="#ffffff",
                        relief="flat",
                        padx=12,
                        pady=5,
                        cursor="hand2",
                        command=_prompt_save_as
                    )
                    btn_save_as.pack(side=tk.LEFT, padx=3)

            # Reactions pill container
            rx_frame = tk.Frame(align_box, bg="#0f172a")
            rx_frame.pack(anchor="e" if is_me else "w", pady=(2, 0))
            self.reaction_containers[msg_id] = rx_frame
            self._render_reaction_pills(msg_id, msg.get("reactions") or {})

            _bind_context_menu(card)
            _bind_context_menu(content_box)

        else:
            # ----------------- STANDARD CHAT BUBBLE -----------------
            if is_me:
                align_box = tk.Frame(row_frame, bg="#0f172a")
                align_box.pack(side=tk.RIGHT, padx=4)

                bubble = tk.Frame(align_box, bg="#2563eb", padx=14, pady=8)
                bubble.pack(anchor="e")
                row_frame._highlight_target = bubble

                # Quoted reply preview if any
                if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                    r_box = tk.Frame(bubble, bg="#1e3a8a", bd=1, relief="solid", padx=8, pady=4)
                    r_box.pack(anchor="w", fill=tk.X, pady=(0, 6))
                    tk.Label(r_box, text=f"↳ Replying to {reply_to.get('user_name', 'Colleague')}", font=font_spec(10, "bold"), fg="#93c5fd", bg="#1e3a8a").pack(anchor="w")
                    if reply_to.get("text"):
                        tk.Label(r_box, text=reply_to["text"], font=font_spec(10, slant="italic"), fg="#cbd5e1", bg="#1e3a8a").pack(anchor="w")

                self._render_message_content(bubble, msg.get("text", ""), "#2563eb", is_me=True)

                time_box = tk.Frame(align_box, bg="#0f172a")
                time_box.pack(anchor="e", pady=(3, 0))

                btn_del = tk.Label(time_box, text="🗑️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_del.pack(side=tk.RIGHT, padx=(4, 0))
                btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
                btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
                btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

                btn_react = tk.Label(time_box, text="😊", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_react.pack(side=tk.RIGHT, padx=(4, 0))
                btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
                btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
                btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

                btn_reply = tk.Label(time_box, text="↩️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
                btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
                btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
                btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

                tk.Label(
                    time_box,
                    text=f"You • {time_str}",
                    font=font_spec(10),
                    fg="#64748b",
                    bg="#0f172a"
                ).pack(side=tk.RIGHT)

                if is_dm:
                    tk.Label(time_box, text="🔒 DM", font=font_spec(9, "bold"), fg="#ffffff", bg="#0284c7", padx=5, pady=1).pack(side=tk.RIGHT, padx=3)
                if is_pinned:
                    tk.Label(time_box, text="📌 Pinned", font=font_spec(9, "bold"), fg="#38bdf8", bg="#334155", padx=5, pady=1).pack(side=tk.RIGHT, padx=3)

                rx_box = tk.Frame(align_box, bg="#0f172a")
                rx_box.pack(anchor="e", pady=(2, 0))
                self.reaction_containers[msg_id] = rx_box
                self._render_reaction_pills(msg_id, msg.get("reactions") or {})

                _bind_context_menu(bubble)

            else:
                align_box = tk.Frame(row_frame, bg="#0f172a")
                align_box.pack(side=tk.LEFT, padx=4)

                top_info = tk.Frame(align_box, bg="#0f172a")
                top_info.pack(anchor="w", pady=(0, 3), fill=tk.X)

                av = tk.Label(
                    top_info,
                    text=get_initials(sender),
                    font=font_spec(10, "bold"),
                    fg="#ffffff",
                    bg=avatar_bg,
                    width=3,
                    height=1
                )
                av.pack(side=tk.LEFT, padx=(0, 6))

                tk.Label(
                    top_info,
                    text=f"{sender} • {time_str}",
                    font=font_spec(11, "bold"),
                    fg="#94a3b8",
                    bg="#0f172a"
                ).pack(side=tk.LEFT)

                if is_dm:
                    tk.Label(top_info, text="🔒 DM", font=font_spec(9, "bold"), fg="#ffffff", bg="#0284c7", padx=5, pady=1).pack(side=tk.LEFT, padx=3)
                if is_pinned:
                    tk.Label(top_info, text="📌 Pinned", font=font_spec(9, "bold"), fg="#38bdf8", bg="#334155", padx=5, pady=1).pack(side=tk.LEFT, padx=3)
                if is_mentioned:
                    tk.Label(top_info, text="🔔 Mentioned You", font=font_spec(9, "bold"), fg="#000000", bg="#f59e0b", padx=6, pady=1).pack(side=tk.LEFT, padx=3)

                btn_del = tk.Label(top_info, text="🗑️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_del.pack(side=tk.RIGHT, padx=(4, 0))
                btn_del.bind("<Enter>", lambda e, b=btn_del: b.config(fg="#ef4444"))
                btn_del.bind("<Leave>", lambda e, b=btn_del: b.config(fg="#64748b"))
                btn_del.bind("<Button-1>", lambda e, m=msg: self._prompt_delete_message(m))

                btn_react = tk.Label(top_info, text="😊", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_react.pack(side=tk.RIGHT, padx=(4, 0))
                btn_react.bind("<Enter>", lambda e, b=btn_react: b.config(fg="#f59e0b"))
                btn_react.bind("<Leave>", lambda e, b=btn_react: b.config(fg="#64748b"))
                btn_react.bind("<Button-1>", lambda e, mid=msg_id: self._show_reaction_picker(mid, e.widget))

                btn_reply = tk.Label(top_info, text="↩️", font=font_spec(10), fg="#64748b", bg="#0f172a", cursor="hand2")
                btn_reply.pack(side=tk.RIGHT, padx=(4, 0))
                btn_reply.bind("<Enter>", lambda e, b=btn_reply: b.config(fg="#38bdf8"))
                btn_reply.bind("<Leave>", lambda e, b=btn_reply: b.config(fg="#64748b"))
                btn_reply.bind("<Button-1>", lambda e, m=msg: self._start_reply(m))

                bubble_bg = "#1e3a5f" if is_mentioned else "#334155"
                bubble = tk.Frame(align_box, bg=bubble_bg, padx=14, pady=8, bd=1 if is_mentioned else 0, relief="solid")
                bubble.pack(anchor="w")
                row_frame._highlight_target = bubble

                # Quoted reply preview if any
                if reply_to and isinstance(reply_to, dict) and reply_to.get("user_name"):
                    r_box = tk.Frame(bubble, bg="#0f172a", bd=1, relief="solid", padx=8, pady=4)
                    r_box.pack(anchor="w", fill=tk.X, pady=(0, 6))
                    tk.Label(r_box, text=f"↳ Replying to {reply_to.get('user_name', 'Colleague')}", font=font_spec(10, "bold"), fg="#38bdf8", bg="#0f172a").pack(anchor="w")
                    if reply_to.get("text"):
                        tk.Label(r_box, text=reply_to["text"], font=font_spec(10, slant="italic"), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

                self._render_message_content(bubble, msg.get("text", ""), bubble_bg, is_me=False)

                rx_box = tk.Frame(align_box, bg="#0f172a")
                rx_box.pack(anchor="w", pady=(2, 0))
                self.reaction_containers[msg_id] = rx_box
                self._render_reaction_pills(msg_id, msg.get("reactions") or {})

                _bind_context_menu(bubble)

        if not getattr(row_frame, "_highlight_target", None):
            row_frame._highlight_target = row_frame

        if hasattr(self, "find_bar") and self.find_bar.winfo_viewable() and hasattr(self, "entry_find") and self.entry_find.get().strip():
            self._run_find()

        if scroll:
            self.dialog.update_idletasks()
            self.msg_canvas.yview_moveto(1.0)


# ==============================================================================
# Standalone Execution Entrypoint
# ==============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    engine = LANChatEngine(user_name=os.environ.get("USER", "Developer").capitalize())
    engine.start()
    dlg = LANChatDialog(root, engine)
    def _cleanup():
        engine.stop()
        root.destroy()
    dlg.dialog.protocol("WM_DELETE_WINDOW", _cleanup)
    root.mainloop()
