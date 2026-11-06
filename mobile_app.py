"""
WorkPulse - Android Mobile Application Interface (Kivy)
Mobile-optimized UI designed for Android touchscreens with high-DPI scaling,
full LAN Team Chat integration, Daily Work Manager, and Reminder Scheduler.
"""

import os
import sys
import datetime
import time
import json
import threading
import uuid
import shutil
import urllib.parse
import webbrowser
import subprocess

# Ensure local dir is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Ensure KIVY_HOME is writable in all environments
if "KIVY_HOME" not in os.environ:
    try:
        test_dir = os.path.expanduser("~/.kivy")
        os.makedirs(test_dir, exist_ok=True)
    except Exception:
        os.environ["KIVY_HOME"] = "/tmp/.kivy"

try:
    from kivy.app import App  # type: ignore
    from kivy.uix.boxlayout import BoxLayout  # type: ignore
    from kivy.uix.gridlayout import GridLayout  # type: ignore
    from kivy.uix.scrollview import ScrollView  # type: ignore
    from kivy.uix.label import Label  # type: ignore
    from kivy.uix.textinput import TextInput  # type: ignore
    from kivy.uix.button import Button  # type: ignore
    from kivy.uix.spinner import Spinner  # type: ignore
    from kivy.uix.popup import Popup  # type: ignore
    from kivy.uix.filechooser import FileChooserListView  # type: ignore
    from kivy.uix.image import Image  # type: ignore
    from kivy.uix.widget import Widget  # type: ignore
    from kivy.graphics import Color, RoundedRectangle, Line, Rectangle  # type: ignore
    from kivy.clock import Clock  # type: ignore
    from kivy.metrics import dp, sp  # type: ignore
    try:
        from kivy.core.clipboard import Clipboard  # type: ignore
    except Exception:
        Clipboard = None
    from kivy.core.window import Window  # type: ignore
    from kivy.utils import get_color_from_hex, platform  # type: ignore
    KIVY_AVAILABLE = True
except (ImportError, Exception):
    KIVY_AVAILABLE = False
    platform = 'linux'
    App = object
    BoxLayout = GridLayout = ScrollView = Label = TextInput = Button = Spinner = Popup = Window = Clock = Image = Widget = object
    Color = RoundedRectangle = Line = Rectangle = object
    Clipboard = None

    def dp(x):  # type: ignore
        return x

    def sp(x):  # type: ignore
        return x

    def get_color_from_hex(hex_str):  # type: ignore
        return (1, 1, 1, 1)

class RoundedCard(BoxLayout if KIVY_AVAILABLE else object):
    """Modern mobile container widget with rounded corners and custom background color."""
    def __init__(self, bg_hex="#1e293b", radius=None, border_hex=None, **kwargs):
        super().__init__(**kwargs)
        if not KIVY_AVAILABLE or not hasattr(self, 'canvas'):
            return
        self.radius_val = radius or [dp(12), dp(12), dp(12), dp(12)]
        self.border_hex = border_hex
        with self.canvas.before:
            self._c_color = Color(*get_color_from_hex(bg_hex))
            self._c_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius_val)
            if border_hex:
                self._c_bcolor = Color(*get_color_from_hex(border_hex))
                self._c_line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, self.radius_val[0]], width=dp(1))
            else:
                self._c_line = None
        self.bind(pos=self._update_card_canvas, size=self._update_card_canvas)

    def _update_card_canvas(self, *args):
        if hasattr(self, '_c_rect'):
            self._c_rect.pos = self.pos
            self._c_rect.size = self.size
        if hasattr(self, '_c_line') and self._c_line:
            self._c_line.rounded_rectangle = [self.x, self.y, self.width, self.height, self.radius_val[0]]

    def set_bg_color(self, hex_code):
        if hasattr(self, '_c_color'):
            self._c_color.rgba = get_color_from_hex(hex_code)

def safe_escape_markup(text):
    """Escapes Kivy markup tags to prevent markup parsing errors with user text."""
    if not isinstance(text, str):
        text = str(text or "")
    return text.replace("[", "&bl;").replace("]", "&br;")

try:
    from storage_config import (
        is_android, get_storage_path, get_storage_dir,
        acquire_android_multicast_lock, show_android_notification,
        get_or_create_device_id, get_persistent_user_id
    )
except Exception:
    def is_android(): return False
    def get_storage_path(fn): return fn
    def get_storage_dir(): return os.path.dirname(os.path.abspath(__file__))
    def acquire_android_multicast_lock(): return None
    def show_android_notification(t, m): return False
    def get_or_create_device_id(): return "dev_local_fallback"
    def get_persistent_user_id(u="Developer"):
        import re
        c = re.sub(r'[^a-zA-Z0-9]', '', (u or 'user').lower())[:10] or 'user'
        return f"{c}_dev_local_fallback"

NOTES_FILE = get_storage_path("notes.json")

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Error loading notes: {e}")
    return []

def save_notes(notes):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving notes: {e}")
        return False

# Import backend business logic
try:
    from app import (
        save_work_update, load_settings, save_settings,
        calculate_net_working_hours, format_human_time,
        get_daily_timings, save_daily_timings,
        format_date_only, FILE, sync_google_sheet_month,
        fetch_google_sheet_month, save_fetched_rows_to_excel,
        fetch_and_load_month_data, init_file,
        get_available_months, load_month_records, delete_work_update,
        STANDARD_HOLIDAYS_2026, send_webhook_message, send_data_api_webhook,
        ping_google_sheet, sync_month_holidays_and_weekly_offs, DEFAULT_SETTINGS,
        get_google_apps_script_code, sync_google_sheet_notes,
        fetch_google_sheet_notes, is_google_sheet_configured
    )
except Exception as e:
    print(f"Warning: app.py import: {e}")

if 'is_google_sheet_configured' not in globals():
    def is_google_sheet_configured(s=None):
        if not s and 'load_settings' in globals():
            s = load_settings()
        u = ((s or {}).get("gsheet_webapp_url") or "").strip()
        return bool(u and (u.startswith("http://") or u.startswith("https://")))

if 'get_google_apps_script_code' not in globals():
    def get_google_apps_script_code():
        for d in [os.path.dirname(os.path.abspath(__file__)), os.getcwd(), "."]:
            p = os.path.join(d, "google_apps_script.js")
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        c = f.read()
                        if len(c) > 500:
                            return c
                except Exception:
                    pass
        return """/**
 * WorkPulse - Google Sheets Sync Integration (Google Apps Script)
 * Extensions > Apps Script -> Paste -> Deploy as Web App (Access: Anyone)
 */
function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(20000);
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var defaultHeaders = ["ID","Date","Project / Module","Task Title","Work Description","Hours Spent","Status","Remarks","Login Time","Logout Time","Lunch Break","Tea Break","Logged At"];
    if (data.action === "ping") {
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Connected to Google Sheet: '" + ss.getName() + "'",
        sheetTitle: ss.getName(),
        sheets: ss.getSheets().map(function(s) { return s.getName(); })
      })).setMimeType(ContentService.MimeType.JSON);
    }
    if (data.action === "fetch_month" || data.action === "fetch_sheet") {
      var sName = data.sheet_name || "Work Logs";
      var s = ss.getSheetByName(sName);
      if (!s) return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "Tab not found" })).setMimeType(ContentService.MimeType.JSON);
      var lRow = s.getLastRow(), lCol = s.getLastColumn();
      var hds = (lRow >= 1 && lCol >= 1) ? s.getRange(1, 1, 1, lCol).getDisplayValues()[0] : defaultHeaders;
      var rows = (lRow >= 2 && lCol >= 1) ? s.getRange(2, 1, lRow - 1, lCol).getDisplayValues().filter(function(r){ return r.some(function(c){ return c !== ""; }); }) : [];
      return ContentService.createTextOutput(JSON.stringify({ status: "success", sheet_name: sName, sheetTitle: ss.getName(), headers: hds, rows: rows })).setMimeType(ContentService.MimeType.JSON);
    }
    if (data.action === "sync_month" || data.action === "sync_sheet") {
      var sName = data.sheet_name || "Work Logs";
      var s = ss.getSheetByName(sName) || ss.insertSheet(sName);
      var hd = data.headers || defaultHeaders;
      var rows = data.rows || [];
      s.clearContents();
      if (hd.length) s.getRange(1, 1, 1, hd.length).setValues([hd]).setBackground("#1F4E79").setFontColor("#FFFFFF").setFontWeight("bold");
      if (rows.length) s.getRange(2, 1, rows.length, hd.length).setValues(rows);
      return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "Synced " + rows.length + " rows to tab '" + sName + "'", updatedRows: rows.length, sheetTitle: ss.getName() })).setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "Unknown action" })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ContentService.createTextOutput(JSON.stringify({ status: "online", sheetTitle: ss.getName(), sheets: ss.getSheets().map(function(s) { return s.getName(); }) })).setMimeType(ContentService.MimeType.JSON);
}"""

try:
    from reminder_scheduler import (
        ReminderSchedulerEngine, load_all_settings, save_all_settings,
        add_custom_reminder, delete_custom_reminder, toggle_custom_reminder_status,
        snooze_custom_reminder, format_minutes_to_time, parse_time_minutes
    )
except Exception as e:
    print(f"Warning: reminder_scheduler import: {e}")

try:
    from lan_chat import (
        LANChatEngine, get_network_info, get_avatar_color, get_initials, format_file_size,
        get_file_icon, is_image_file
    )
except Exception as e:
    print(f"Warning: lan_chat import: {e}")
    LANChatEngine = None
    get_network_info = None
    get_avatar_color = None
    get_initials = None
    def format_file_size(b): return f"{b} B"
    def get_file_icon(fn): return "[FILE]"
    def is_image_file(fn): return False


class WorkPulseMobileApp(App if KIVY_AVAILABLE else object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = load_settings() if 'load_settings' in globals() else {}
        self.chat_engine = None
        self.unread_chat_count = 0
        self.rendered_msg_ids = set()
        self.current_tab = "work"
        self.downloaded_files = {}
        self.active_dm_peer = None
        self.current_hist_filter = "All"
        self.hist_filter_buttons = {}

    def build(self):
        self.title = "WorkPulse - Mobile"
        if KIVY_AVAILABLE and platform not in ('android', 'ios') and hasattr(Window, 'size'):
            try:
                Window.size = (412, 850)
            except Exception:
                pass
        if KIVY_AVAILABLE and hasattr(Window, 'clearcolor'):
            Window.clearcolor = get_color_from_hex("#0f172a")

        # Soft keyboard setup: pan view above on-screen keyboard
        if KIVY_AVAILABLE and hasattr(Window, 'softinput_mode'):
            try:
                Window.softinput_mode = "below_target"
            except Exception:
                pass
        if KIVY_AVAILABLE and Window:
            try:
                Window.bind(on_keyboard_height=self._on_keyboard_height)
            except Exception:
                pass

        self.settings = load_settings() if 'load_settings' in globals() else {}
        self.chat_engine = None
        self.unread_chat_count = 0
        self.rendered_msg_ids = set()
        self.current_tab = "work"
        self.downloaded_files = {}  # Cache of local files: {file_id: local_file_path}
        self.active_dm_peer = None  # None = Public Room, or peer dict when in 1-on-1 DM
        self.current_hist_filter = "All"
        self.hist_filter_buttons = {}

        # Main Root Container
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # 1. Top Header App Bar (Sleek Card with subtle bottom radius)
        header = RoundedCard(
            bg_hex="#0b1120",
            radius=[0, 0, dp(12), dp(12)],
            orientation='horizontal',
            size_hint_y=None,
            height=dp(52),
            padding=[dp(12), dp(6), dp(12), dp(6)],
            spacing=dp(8)
        )
        
        lbl_app = Label(
            text="[b]WorkPulse[/b] [color=#38bdf8]Mobile[/color]",
            markup=True,
            font_size='17sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.48,
            halign='left',
            valign='middle'
        )
        lbl_app.bind(size=lbl_app.setter('text_size'))
        header.add_widget(lbl_app)

        self.btn_online_chip = Button(
            text="Online",
            font_size='11sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#064e3b"),
            color=get_color_from_hex("#34d399")
        )
        self.btn_online_chip.bind(on_release=self.open_online_team_popup)
        header.add_widget(self.btn_online_chip)

        btn_settings = Button(
            text="Settings",
            font_size='11sp',
            bold=True,
            size_hint_x=0.24,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=(1, 1, 1, 1)
        )
        btn_settings.bind(on_release=self.open_settings_popup)
        header.add_widget(btn_settings)
        root.add_widget(header)

        # 2. Modern 5-Tab Segmented Navigation Bar
        nav_tabs = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(46),
            padding=[dp(6), dp(4), dp(6), dp(6)],
            spacing=dp(4)
        )
        
        self.btn_tab_work = Button(
            text="Log Work",
            font_size='12sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        self.btn_tab_work.bind(on_release=lambda x: self.switch_tab("work"))
        nav_tabs.add_widget(self.btn_tab_work)

        self.btn_tab_updates = Button(
            text="Updates",
            font_size='12sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#94a3b8")
        )
        self.btn_tab_updates.bind(on_release=lambda x: self.switch_tab("updates"))
        nav_tabs.add_widget(self.btn_tab_updates)

        self.btn_tab_notes = Button(
            text="Notes",
            font_size='12sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#94a3b8")
        )
        self.btn_tab_notes.bind(on_release=lambda x: self.switch_tab("notes"))
        nav_tabs.add_widget(self.btn_tab_notes)

        self.btn_tab_chat = Button(
            text="Chat",
            font_size='12sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#94a3b8")
        )
        self.btn_tab_chat.bind(on_release=lambda x: self.switch_tab("chat"))
        nav_tabs.add_widget(self.btn_tab_chat)

        self.btn_tab_remind = Button(
            text="Alerts",
            font_size='12sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#94a3b8")
        )
        self.btn_tab_remind.bind(on_release=lambda x: self.switch_tab("remind"))
        nav_tabs.add_widget(self.btn_tab_remind)

        root.add_widget(nav_tabs)

        # 3. Dynamic Screen Content Area
        self.content_container = BoxLayout(orientation='vertical', size_hint=(1, 1))
        root.add_widget(self.content_container)

        # Build individual tab views
        self.view_work = self.build_work_view()
        self.view_updates = self.build_history_view()
        self.view_notes = self.build_notes_view()
        self.view_chat = self.build_chat_view()
        self.view_remind = self.build_reminders_view()

        # Display default tab
        self.content_container.add_widget(self.view_work)

        # Initialize background LAN Chat Engine
        self.init_lan_chat_engine()

        return root

    def _on_keyboard_height(self, window, height):
        if hasattr(self, 'chat_scroll') and self.chat_scroll and height > 0:
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

    def _on_chat_input_focus(self, instance, value):
        if value and hasattr(self, 'chat_scroll') and self.chat_scroll:
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.1)
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.3)

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.content_container.clear_widgets()

        # Reset button styling
        for btn in (self.btn_tab_work, self.btn_tab_updates, self.btn_tab_notes, self.btn_tab_chat, self.btn_tab_remind):
            btn.background_color = get_color_from_hex("#1e293b")
            btn.color = get_color_from_hex("#94a3b8")

        if tab_name == "work":
            self.btn_tab_work.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_work.color = (1, 1, 1, 1)
            self.content_container.add_widget(self.view_work)
        elif tab_name == "updates":
            self.btn_tab_updates.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_updates.color = (1, 1, 1, 1)
            self.content_container.add_widget(self.view_updates)
            self.refresh_history_list()
        elif tab_name == "notes":
            self.btn_tab_notes.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_notes.color = (1, 1, 1, 1)
            self.content_container.add_widget(self.view_notes)
            self.refresh_notes_list()
        elif tab_name == "chat":
            self.btn_tab_chat.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_chat.color = (1, 1, 1, 1)
            self.unread_chat_count = 0
            self.btn_tab_chat.text = "Chat"
            self.content_container.add_widget(self.view_chat)
            self.refresh_chat_messages_ui()
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.1)
        elif tab_name == "remind":
            self.btn_tab_remind.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_remind.color = (1, 1, 1, 1)
            self.content_container.add_widget(self.view_remind)
            self.refresh_reminders_list()

    # =========================================================================
    # TAB 1: WORK UPDATE FORM VIEW
    # =========================================================================
    def build_work_view(self):
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        form = GridLayout(cols=1, spacing=dp(12), padding=[dp(12), dp(10), dp(12), dp(24)], size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # Card 1: Task Details & Progress
        card_task = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(12), dp(10), dp(12), dp(12)])
        card_task.bind(minimum_height=card_task.setter('height'))

        card_task.add_widget(self._create_field_label("Date (YYYY-MM-DD):"))
        date_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        self.in_date = TextInput(
            text=today_str,
            multiline=False,
            font_size='15sp',
            size_hint_x=0.72,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        btn_today = Button(
            text="Today",
            font_size='13sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_today.bind(on_release=lambda x: self.set_today())
        date_row.add_widget(self.in_date)
        date_row.add_widget(btn_today)
        card_task.add_widget(date_row)

        card_task.add_widget(self._create_field_label("Project / Module:"))
        self.in_proj = TextInput(
            text="General Work",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        card_task.add_widget(self.in_proj)

        card_task.add_widget(self._create_field_label("Task Title:"))
        self.in_title = TextInput(
            hint_text="e.g. Bug fixes, feature development",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(12)]
        )
        card_task.add_widget(self.in_title)

        card_task.add_widget(self._create_field_label("Hours & Status:"))
        h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        self.in_hours = TextInput(
            hint_text="Hours (e.g. 8.0)",
            multiline=False,
            font_size='15sp',
            size_hint_x=0.48,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(12)]
        )
        self.sp_status = Spinner(
            text='Completed',
            values=('Completed', 'In Progress', 'Pending', 'Leave', 'Weekly Off', 'Holiday'),
            font_size='14sp',
            size_hint_x=0.52,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        h_row.add_widget(self.in_hours)
        h_row.add_widget(self.sp_status)
        card_task.add_widget(h_row)
        form.add_widget(card_task)

        # Card 2: Shift Timings
        card_shift = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(12), dp(10), dp(12), dp(12)])
        card_shift.bind(minimum_height=card_shift.setter('height'))

        card_shift.add_widget(self._create_field_label("Shift Timings (Login - Logout):"))
        t_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        self.in_login = TextInput(
            hint_text="10:30 AM",
            text=self.settings.get("default_login_time", "10:30 AM"),
            multiline=False,
            font_size='15sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        self.in_logout = TextInput(
            hint_text="07:30 PM",
            text=self.settings.get("default_logout_time", "07:30 PM"),
            multiline=False,
            font_size='15sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        t_row.add_widget(self.in_login)
        t_row.add_widget(self.in_logout)
        card_shift.add_widget(t_row)
        form.add_widget(card_shift)

        # Card 3: Work Description & Notes
        card_desc = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(12), dp(10), dp(12), dp(12)])
        card_desc.bind(minimum_height=card_desc.setter('height'))

        card_desc.add_widget(self._create_field_label("Work Description / Notes:"))
        self.in_desc = TextInput(
            hint_text="Enter detailed work notes, achievements, blockers...",
            multiline=True,
            font_size='14sp',
            size_hint_y=None,
            height=dp(96),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        card_desc.add_widget(self.in_desc)
        form.add_widget(card_desc)

        # Primary Action: Save Work Update
        btn_save = Button(
            text="Save Work Update",
            font_size='16sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        )
        btn_save.bind(on_release=self.on_save)
        form.add_widget(btn_save)

        # Secondary Actions (Row 1)
        row_act1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        btn_copy = Button(
            text="Copy Standup",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_copy.bind(on_release=self.copy_standup)
        row_act1.add_widget(btn_copy)

        btn_clear = Button(
            text="Clear Form",
            font_size='14sp',
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_clear.bind(on_release=self.clear_form)
        row_act1.add_widget(btn_clear)
        form.add_widget(row_act1)

        # Secondary Actions (Row 2: Google Sheets)
        row_act2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        btn_sync = Button(
            text="Sync G-Sheet",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        btn_sync.bind(on_release=self.sync_gsheet)
        row_act2.add_widget(btn_sync)

        btn_fetch = Button(
            text="Fetch G-Sheet",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#6366f1"),
            color=(1, 1, 1, 1)
        )
        btn_fetch.bind(on_release=self.fetch_gsheet)
        row_act2.add_widget(btn_fetch)
        form.add_widget(row_act2)

        scroll.add_widget(form)
        return scroll

    def _create_field_label(self, text):
        lbl = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size='12sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_y=None,
            height=dp(22),
            halign='left',
            valign='middle'
        )
        lbl.bind(size=lbl.setter('text_size'))
        return lbl

    # =========================================================================
    # TAB 2: MY UPDATES / WORK LOGS HISTORY VIEW (MODERN MOBILE UI)
    # =========================================================================
    def build_history_view(self):
        root = BoxLayout(orientation='vertical', padding=[dp(8), dp(6), dp(8), dp(6)], spacing=dp(6))

        # 1. Top Bar: Month Selector + Sync G-Sheet + Refresh
        top_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        months = get_available_months() if 'get_available_months' in globals() else []
        current_m = datetime.datetime.now().strftime("%B %Y")
        if not months:
            months = [current_m]
        elif current_m not in months:
            months.insert(0, current_m)

        self.sp_hist_month = Spinner(
            text=current_m,
            values=tuple(months),
            font_size='13sp',
            bold=True,
            size_hint_x=0.52,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=(1, 1, 1, 1)
        )
        self.sp_hist_month.bind(text=lambda s, val: self.refresh_history_list())
        top_row.add_widget(self.sp_hist_month)

        self.btn_hist_sync = Button(
            text="Sync Sheet",
            font_size='11sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        self.btn_hist_sync.bind(on_release=lambda x: self._on_hist_sync_clicked())
        top_row.add_widget(self.btn_hist_sync)

        btn_refresh = Button(
            text="Refresh",
            font_size='11sp',
            bold=True,
            size_hint_x=0.23,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_refresh.bind(on_release=lambda x: self.refresh_history_list())
        top_row.add_widget(btn_refresh)
        root.add_widget(top_row)

        # 2. Executive 3-Card KPI Dashboard Strip
        kpi_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(52), spacing=dp(6))
        
        # KPI Card 1: Total Tasks
        self.card_kpi_tasks = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.33, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_tasks_val = Label(text="0", font_size='16sp', bold=True, color=(1, 1, 1, 1), halign='center', valign='middle')
        self.lbl_kpi_tasks_val.bind(size=self.lbl_kpi_tasks_val.setter('text_size'))
        lbl_kpi_tasks_sub = Label(text="Total Logs", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_tasks_sub.bind(size=lbl_kpi_tasks_sub.setter('text_size'))
        self.card_kpi_tasks.add_widget(self.lbl_kpi_tasks_val)
        self.card_kpi_tasks.add_widget(lbl_kpi_tasks_sub)
        kpi_row.add_widget(self.card_kpi_tasks)

        # KPI Card 2: Total Hours
        self.card_kpi_hours = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.34, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_hours_val = Label(text="0.0h", font_size='16sp', bold=True, color=get_color_from_hex("#34d399"), halign='center', valign='middle')
        self.lbl_kpi_hours_val.bind(size=self.lbl_kpi_hours_val.setter('text_size'))
        lbl_kpi_hours_sub = Label(text="Work Hours", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_hours_sub.bind(size=lbl_kpi_hours_sub.setter('text_size'))
        self.card_kpi_hours.add_widget(self.lbl_kpi_hours_val)
        self.card_kpi_hours.add_widget(lbl_kpi_hours_sub)
        kpi_row.add_widget(self.card_kpi_hours)

        # KPI Card 3: Completed / Status
        self.card_kpi_status = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.33, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_status_val = Label(text="0 Done", font_size='16sp', bold=True, color=get_color_from_hex("#38bdf8"), halign='center', valign='middle')
        self.lbl_kpi_status_val.bind(size=self.lbl_kpi_status_val.setter('text_size'))
        lbl_kpi_status_sub = Label(text="Completed", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_status_sub.bind(size=lbl_kpi_status_sub.setter('text_size'))
        self.card_kpi_status.add_widget(self.lbl_kpi_status_val)
        self.card_kpi_status.add_widget(lbl_kpi_status_sub)
        kpi_row.add_widget(self.card_kpi_status)

        root.add_widget(kpi_row)

        # 3. Horizontal Scrollable Filter Chips
        self.current_hist_filter = "All"
        self.hist_filter_buttons = {}
        chip_scroll = ScrollView(size_hint_y=None, height=dp(30), do_scroll_x=True, do_scroll_y=False, bar_width=0)
        self.hist_chip_box = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(30), spacing=dp(6), padding=[dp(2), 0, dp(2), 0])
        self.hist_chip_box.bind(minimum_width=self.hist_chip_box.setter('width'))
        chip_scroll.add_widget(self.hist_chip_box)
        root.add_widget(chip_scroll)

        # 4. Search Bar with Instant Clear Button
        search_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(6))
        self.in_hist_search = TextInput(
            hint_text="Search tasks, projects, notes...",
            multiline=False,
            font_size='13sp',
            size_hint_x=0.78,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        self.in_hist_search.bind(text=lambda s, val: self._on_hist_search_changed(val))
        search_box.add_widget(self.in_hist_search)

        self.btn_clear_hist_search = Button(
            text="Clear",
            font_size='11sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1),
            opacity=0,
            disabled=True
        )
        self.btn_clear_hist_search.bind(on_release=lambda x: self._clear_hist_search())
        search_box.add_widget(self.btn_clear_hist_search)
        root.add_widget(search_box)

        # 5. Updates List ScrollView
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(3), scroll_type=['content'])
        self.hist_list_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4), 0, dp(12)])
        self.hist_list_layout.bind(minimum_height=self.hist_list_layout.setter('height'))
        scroll.add_widget(self.hist_list_layout)
        root.add_widget(scroll)

        return root

    def _on_hist_search_changed(self, val):
        if hasattr(self, 'btn_clear_hist_search') and self.btn_clear_hist_search:
            has_text = bool(val.strip())
            self.btn_clear_hist_search.opacity = 1 if has_text else 0
            self.btn_clear_hist_search.disabled = not has_text
        self.refresh_history_list()

    def _clear_hist_search(self):
        if hasattr(self, 'in_hist_search') and self.in_hist_search:
            self.in_hist_search.text = ""

    def _on_hist_sync_clicked(self):
        if not hasattr(self, 'sp_hist_month'):
            return
        target_m = self.sp_hist_month.text
        if hasattr(self, 'btn_hist_sync') and self.btn_hist_sync:
            self.btn_hist_sync.text = "Syncing..."
            self.btn_hist_sync.disabled = True

        def _worker():
            msg = ""
            try:
                if 'sync_google_sheet_month' in globals():
                    ok, data, code = sync_google_sheet_month(target_m)
                    if ok:
                        cnt = data.get("updatedRows", "") if isinstance(data, dict) else ""
                        msg = f"Synced {cnt} rows to Google Sheet ('{target_m}') successfully!"
                    else:
                        err = data if isinstance(data, str) else (data.get("message", "Error") if isinstance(data, dict) else "Error")
                        msg = f"Sync failed: {err}"
                else:
                    msg = "Google Sheet sync module not available."
            except Exception as e:
                msg = f"Error during sync: {e}"

            def _done(dt):
                if hasattr(self, 'btn_hist_sync') and self.btn_hist_sync:
                    self.btn_hist_sync.text = "Sync Sheet"
                    self.btn_hist_sync.disabled = False
                self.show_popup("Sheet Sync", msg)
                self.refresh_history_list()

            Clock.schedule_once(_done, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def refresh_history_list(self):
        if not hasattr(self, 'hist_list_layout') or not self.hist_list_layout:
            return
        self.hist_list_layout.clear_widgets()

        if 'get_available_months' in globals() and hasattr(self, 'sp_hist_month'):
            months = get_available_months()
            if months and tuple(months) != self.sp_hist_month.values:
                cur = self.sp_hist_month.text
                self.sp_hist_month.values = tuple(months)
                if cur in months:
                    self.sp_hist_month.text = cur
                elif months:
                    self.sp_hist_month.text = months[0]

        target_m = self.sp_hist_month.text if hasattr(self, 'sp_hist_month') else datetime.datetime.now().strftime("%B %Y")
        records = load_month_records(target_m) if 'load_month_records' in globals() else []

        search_q = self.in_hist_search.text.strip().lower() if hasattr(self, 'in_hist_search') else ""
        tot_hours = 0.0
        comp_cnt = 0
        inp_cnt = 0
        rest_cnt = 0
        projects_set = []

        # Tally metrics across whole month
        for r in records:
            p_val = str(r[2] or "").strip()
            if p_val and p_val not in projects_set and p_val.lower() not in ("weekly off", "holiday"):
                projects_set.append(p_val)
            st_val = str(r[6] or "").strip().lower()
            h_val = str(r[5] or "0").replace("h", "").strip()
            try:
                tot_hours += float(h_val)
            except Exception:
                pass
            if st_val == "completed":
                comp_cnt += 1
            elif st_val == "in progress":
                inp_cnt += 1
            elif st_val in ("weekly off", "holiday", "leave") or "weekly off" in p_val.lower() or "holiday" in p_val.lower():
                rest_cnt += 1

        # Update KPI Cards
        if hasattr(self, 'lbl_kpi_tasks_val') and self.lbl_kpi_tasks_val:
            self.lbl_kpi_tasks_val.text = str(len(records))
        if hasattr(self, 'lbl_kpi_hours_val') and self.lbl_kpi_hours_val:
            self.lbl_kpi_hours_val.text = f"{tot_hours:.1f}h"
        if hasattr(self, 'lbl_kpi_status_val') and self.lbl_kpi_status_val:
            self.lbl_kpi_status_val.text = f"{comp_cnt} Done"

        # Dynamically build filter chips ribbon
        categories = [
            ("All", f"All ({len(records)})"),
            ("Completed", f"Done ({comp_cnt})"),
        ]
        if inp_cnt > 0:
            categories.append(("In Progress", f"In Progress ({inp_cnt})"))
        if rest_cnt > 0:
            categories.append(("Rest / Off", f"Rest / Off ({rest_cnt})"))
        for pj in projects_set[:4]:
            categories.append((pj, pj))

        if hasattr(self, 'hist_chip_box') and self.hist_chip_box:
            self.hist_chip_box.clear_widgets()
            self.hist_filter_buttons = {}
            for cat_key, cat_label in categories:
                is_active = (getattr(self, 'current_hist_filter', 'All') == cat_key)
                btn_chip = Button(
                    text=cat_label,
                    font_size='11sp',
                    bold=True,
                    size_hint_x=None,
                    width=dp(len(cat_label) * 8 + 22),
                    background_normal='',
                    background_color=get_color_from_hex("#2563eb" if is_active else "#1e293b"),
                    color=(1, 1, 1, 1) if is_active else get_color_from_hex("#94a3b8")
                )
                def _on_filter_click(b, k=cat_key):
                    self.current_hist_filter = k
                    self.refresh_history_list()
                btn_chip.bind(on_release=_on_filter_click)
                self.hist_filter_buttons[cat_key] = btn_chip
                self.hist_chip_box.add_widget(btn_chip)

        # Filter the records list
        active_f = getattr(self, 'current_hist_filter', 'All')
        filtered = []
        for r in records:
            t_title = str(r[3] or "")
            t_proj = str(r[2] or "")
            t_status = str(r[6] or "")
            t_desc = str(r[4] or "")
            st_lower = t_status.lower()
            pj_lower = t_proj.lower()

            if active_f == "Completed" and st_lower != "completed":
                continue
            elif active_f == "In Progress" and st_lower != "in progress":
                continue
            elif active_f == "Rest / Off" and not (st_lower in ("weekly off", "holiday", "leave") or "weekly off" in pj_lower or "holiday" in pj_lower):
                continue
            elif active_f != "All" and active_f not in ("Completed", "In Progress", "Rest / Off"):
                if active_f.lower() != t_proj.strip().lower():
                    continue

            if search_q:
                combined = f"{t_title} {t_proj} {t_status} {t_desc} {str(r[1] or '')}".lower()
                if search_q not in combined:
                    continue

            filtered.append(r)

        if not filtered:
            msg = "No work updates matching filter." if (search_q or active_f != "All") else f"No updates logged for {target_m}.\nUse 'Log Work' tab to save tasks!"
            empty_card = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], border_hex="#334155", orientation='vertical', size_hint_y=None, height=dp(100), padding=[dp(16), dp(16)])
            lbl = Label(text=msg, font_size='13sp', color=get_color_from_hex("#64748b"), halign='center', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            empty_card.add_widget(lbl)
            self.hist_list_layout.add_widget(empty_card)
            return

        for r in filtered:
            card = self._create_history_card(r, target_m)
            self.hist_list_layout.add_widget(card)

    def _create_history_card(self, r, sheet_name):
        rec_id = r[0]
        date_v = str(r[1] or "")
        proj_v = str(r[2] or "General Work")
        title_v = str(r[3] or "Untitled Task")
        desc_v = str(r[4] or "")
        hours_v = str(r[5] or "0").replace("h", "").strip()
        status_v = str(r[6] or "Completed")
        login_v = str(r[8] or "")
        logout_v = str(r[9] or "")

        is_rest = (status_v.lower() in ("weekly off", "weekend", "holiday") or "weekly off" in proj_v.lower() or "holiday" in proj_v.lower())

        if is_rest:
            card = RoundedCard(
                bg_hex="#0e1726",
                radius=[dp(12), dp(12), dp(12), dp(12)],
                border_hex="#1e3a8a" if "weekly off" in status_v.lower() else "#7c2d12",
                orientation='vertical',
                size_hint_y=None,
                padding=[dp(12), dp(10), dp(12), dp(10)],
                spacing=dp(6)
            )
            card.bind(minimum_height=card.setter('height'))

            row_top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(24), spacing=dp(8))
            lbl_date = Label(text=f"[b]{date_v}[/b]", markup=True, font_size='12sp', color=get_color_from_hex("#38bdf8"), size_hint_x=0.5, halign='left', valign='middle')
            lbl_date.bind(size=lbl_date.setter('text_size'))
            row_top.add_widget(lbl_date)

            tag_c = "#3b82f6" if "weekly off" in status_v.lower() else "#f97316"
            lbl_tag = Label(text=f"[b]{status_v}[/b]", markup=True, font_size='11sp', color=get_color_from_hex(tag_c), size_hint_x=0.5, halign='right', valign='middle')
            lbl_tag.bind(size=lbl_tag.setter('text_size'))
            row_top.add_widget(lbl_tag)
            card.add_widget(row_top)

            row_mid = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(24), spacing=dp(8))
            lbl_title = Label(text=f"[b]{safe_escape_markup(title_v)}[/b]", markup=True, font_size='14sp', color=get_color_from_hex("#94a3b8"), size_hint_x=0.8, halign='left', valign='middle')
            lbl_title.bind(size=lbl_title.setter('text_size'))
            row_mid.add_widget(lbl_title)

            lbl_h = Label(text="0h", font_size='12sp', color=get_color_from_hex("#64748b"), size_hint_x=0.2, halign='right', valign='middle')
            lbl_h.bind(size=lbl_h.setter('text_size'))
            row_mid.add_widget(lbl_h)
            card.add_widget(row_mid)

            row_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(8))
            btn_view = Button(text="View Details", font_size='11sp', bold=True, size_hint_x=0.75, background_normal='', background_color=get_color_from_hex("#1e293b"), color=get_color_from_hex("#38bdf8"))
            btn_view.bind(on_release=lambda x, rec=r: self.view_update_details(rec, sheet_name))
            row_acts.add_widget(btn_view)

            btn_del = Button(text="Delete", font_size='11sp', bold=True, size_hint_x=0.25, background_normal='', background_color=get_color_from_hex("#7f1d1d"), color=get_color_from_hex("#f87171"))
            btn_del.bind(on_release=lambda x, rid=rec_id, sm=sheet_name: self.delete_update_item(rid, sm))
            row_acts.add_widget(btn_del)
            card.add_widget(row_acts)

            return card

        # Regular Work Task Card
        card = RoundedCard(
            bg_hex="#162238",
            radius=[dp(12), dp(12), dp(12), dp(12)],
            border_hex="#334155",
            orientation='vertical',
            size_hint_y=None,
            padding=[dp(12), dp(10), dp(12), dp(10)],
            spacing=dp(6)
        )
        card.bind(minimum_height=card.setter('height'))

        # Row 1: Date & Project Pill
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(22), spacing=dp(8))
        lbl_date = Label(
            text=f"[b]{date_v}[/b]",
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.42,
            halign='left',
            valign='middle'
        )
        lbl_date.bind(size=lbl_date.setter('text_size'))
        row1.add_widget(lbl_date)

        lbl_proj = Label(
            text=f"[b]{safe_escape_markup(proj_v)}[/b]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex("#c084fc"),
            size_hint_x=0.58,
            halign='right',
            valign='middle'
        )
        lbl_proj.bind(size=lbl_proj.setter('text_size'))
        row1.add_widget(lbl_proj)
        card.add_widget(row1)

        # Row 2: Task Title (left) & Hours Badge (right)
        row2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(26), spacing=dp(8))
        lbl_title = Label(
            text=f"[b]{safe_escape_markup(title_v)}[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.76,
            halign='left',
            valign='middle'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        row2.add_widget(lbl_title)

        lbl_hours = Label(
            text=f"[b]{hours_v}h[/b]",
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#34d399"),
            size_hint_x=0.24,
            halign='right',
            valign='middle'
        )
        lbl_hours.bind(size=lbl_hours.setter('text_size'))
        row2.add_widget(lbl_hours)
        card.add_widget(row2)

        # Row 3: Shift Timings & Status Badge
        row3 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(20), spacing=dp(8))
        shift_txt = f"{login_v} - {logout_v}" if (login_v or logout_v) else "Shift: Standard"
        lbl_shift = Label(
            text=f"Shift: {shift_txt}",
            font_size='11sp',
            color=get_color_from_hex("#94a3b8"),
            size_hint_x=0.62,
            halign='left',
            valign='middle'
        )
        lbl_shift.bind(size=lbl_shift.setter('text_size'))
        row3.add_widget(lbl_shift)

        st_colors = {
            "completed": "#10b981",
            "in progress": "#f59e0b",
            "pending": "#eab308",
            "leave": "#ec4899",
            "weekly off": "#3b82f6",
            "holiday": "#f97316"
        }
        st_c = st_colors.get(status_v.lower(), "#94a3b8")
        lbl_st = Label(
            text=f"[b]{status_v}[/b]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex(st_c),
            size_hint_x=0.38,
            halign='right',
            valign='middle'
        )
        lbl_st.bind(size=lbl_st.setter('text_size'))
        row3.add_widget(lbl_st)
        card.add_widget(row3)

        # Row 4: Clean Description Inset Box
        if desc_v:
            desc_sub = (desc_v[:110] + "...") if len(desc_v) > 110 else desc_v
            desc_card = RoundedCard(
                bg_hex="#0b1322",
                radius=[dp(6), dp(6), dp(6), dp(6)],
                size_hint_y=None,
                height=dp(38),
                padding=[dp(8), dp(4), dp(8), dp(4)]
            )
            lbl_desc = Label(
                text=safe_escape_markup(desc_sub),
                font_size='11sp',
                color=get_color_from_hex("#94a3b8"),
                halign='left',
                valign='middle'
            )
            lbl_desc.bind(size=lbl_desc.setter('text_size'))
            desc_card.add_widget(lbl_desc)
            card.add_widget(desc_card)

        # Row 5: Sleek 4-Action Button Ribbon
        row_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
        
        btn_view = Button(
            text="View Details",
            font_size='11sp',
            bold=True,
            size_hint_x=0.44,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#38bdf8")
        )
        btn_view.bind(on_release=lambda x, rec=r: self.view_update_details(rec, sheet_name))
        row_acts.add_widget(btn_view)

        btn_copy = Button(
            text="Copy",
            font_size='11sp',
            bold=True,
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        def _quick_copy(b, rec=r):
            self._copy_work_record_to_clipboard(rec, b)
        btn_copy.bind(on_release=_quick_copy)
        row_acts.add_widget(btn_copy)

        btn_edit = Button(
            text="Edit",
            font_size='11sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=(1, 1, 1, 1)
        )
        btn_edit.bind(on_release=lambda x, rec=r: self.open_edit_work_update_dialog(rec, sheet_name))
        row_acts.add_widget(btn_edit)

        btn_del = Button(
            text="Del",
            font_size='11sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#7f1d1d"),
            color=get_color_from_hex("#f87171")
        )
        btn_del.bind(on_release=lambda x, rid=rec_id, sm=sheet_name: self.delete_update_item(rid, sm))
        row_acts.add_widget(btn_del)
        card.add_widget(row_acts)

        return card

    def _copy_work_record_to_clipboard(self, r, btn=None):
        date_v = str(r[1] or "")
        proj_v = str(r[2] or "")
        title_v = str(r[3] or "")
        desc_v = str(r[4] or "")
        hours_v = str(r[5] or "0").replace("h", "").strip()
        status_v = str(r[6] or "")
        login_v = str(r[8] or "")
        logout_v = str(r[9] or "")

        clip_text = (
            f"Work Update - {date_v}\n"
            f"* Task: {title_v} ({hours_v}h) [{status_v}]\n"
            f"* Project: {proj_v}\n"
            f"* Shift: {login_v} - {logout_v}\n\n"
            f"{desc_v}"
        )
        if Clipboard is not None:
            try:
                Clipboard.copy(clip_text)
            except Exception:
                pass

        if btn:
            orig = btn.text
            btn.text = "Copied!"
            Clock.schedule_once(lambda dt: setattr(btn, 'text', orig), 1.5)
        else:
            self.show_popup("Copied", "Work update copied to clipboard!")

    def view_update_details(self, r, sheet_name=None):
        d_v = str(r[1] or "")
        p_v = str(r[2] or "")
        t_v = str(r[3] or "")
        desc_v = str(r[4] or "No description provided.")
        h_v = str(r[5] or "0").replace("h", "").strip()
        st_v = str(r[6] or "Completed")
        rem_v = str(r[7] or "")
        login_v = str(r[8] or "")
        logout_v = str(r[9] or "")
        lunch_v = str(r[10] or "")
        tea_v = str(r[11] or "")
        created_v = str(r[12] or "")

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.94, 0.88),
            auto_dismiss=True
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # 1. Header Bar: Title + Close [X] Button
        hdr_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(8))
        lbl_head = Label(
            text="[b]Work Update Details[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.86,
            halign='left',
            valign='middle'
        )
        lbl_head.bind(size=lbl_head.setter('text_size'))
        hdr_row.add_widget(lbl_head)

        btn_close_x = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_close_x.bind(on_release=popup.dismiss)
        hdr_row.add_widget(btn_close_x)
        modal.add_widget(hdr_row)

        # 2. Meta Pills Ribbon: Date, Project, Hours, Status
        pills_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(26), spacing=dp(6))
        
        lbl_date_pill = Label(
            text=f"[b]{d_v}[/b]",
            markup=True,
            font_size='12sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.35,
            halign='left',
            valign='middle'
        )
        lbl_date_pill.bind(size=lbl_date_pill.setter('text_size'))
        pills_row.add_widget(lbl_date_pill)

        lbl_proj_pill = Label(
            text=f"[b]{safe_escape_markup(p_v)}[/b]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex("#c084fc"),
            size_hint_x=0.65,
            halign='right',
            valign='middle'
        )
        lbl_proj_pill.bind(size=lbl_proj_pill.setter('text_size'))
        pills_row.add_widget(lbl_proj_pill)
        modal.add_widget(pills_row)

        # Row 2b: Hours Badge + Status Badge + Shift Timings
        sub_pills = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(6))
        
        badge_hours = RoundedCard(bg_hex="#064e3b", radius=[dp(6), dp(6), dp(6), dp(6)], size_hint_x=0.28, padding=[dp(4), dp(2)])
        lbl_bh = Label(text=f"[b]{h_v} hrs[/b]", markup=True, font_size='12sp', color=get_color_from_hex("#34d399"), halign='center', valign='middle')
        lbl_bh.bind(size=lbl_bh.setter('text_size'))
        badge_hours.add_widget(lbl_bh)
        sub_pills.add_widget(badge_hours)

        st_colors = {
            "completed": ("#065f46", "#10b981"),
            "in progress": ("#78350f", "#f59e0b"),
            "pending": ("#713f12", "#eab308"),
            "leave": ("#831843", "#ec4899"),
            "weekly off": ("#1e3a8a", "#60a5fa"),
            "holiday": ("#7c2d12", "#fb923c")
        }
        bg_c, tx_c = st_colors.get(st_v.lower(), ("#1e293b", "#94a3b8"))
        badge_st = RoundedCard(bg_hex=bg_c, radius=[dp(6), dp(6), dp(6), dp(6)], size_hint_x=0.34, padding=[dp(4), dp(2)])
        lbl_bs = Label(text=f"[b]{st_v}[/b]", markup=True, font_size='11sp', color=get_color_from_hex(tx_c), halign='center', valign='middle')
        lbl_bs.bind(size=lbl_bs.setter('text_size'))
        badge_st.add_widget(lbl_bs)
        sub_pills.add_widget(badge_st)

        shift_str = f"{login_v} - {logout_v}" if (login_v or logout_v) else "Standard"
        lbl_shift_info = Label(text=f"Shift: {shift_str}", font_size='11sp', color=get_color_from_hex("#94a3b8"), size_hint_x=0.38, halign='right', valign='middle')
        lbl_shift_info.bind(size=lbl_shift_info.setter('text_size'))
        sub_pills.add_widget(lbl_shift_info)
        modal.add_widget(sub_pills)

        # 3. Task Title Card
        card_t = RoundedCard(bg_hex="#162238", radius=[dp(8), dp(8), dp(8), dp(8)], size_hint_y=None, padding=[dp(10), dp(8)], spacing=dp(2))
        card_t.bind(minimum_height=card_t.setter('height'))
        lbl_title_disp = Label(
            text=f"[b]{safe_escape_markup(t_v)}[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_y=None,
            halign='left',
            valign='top'
        )
        lbl_title_disp.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        lbl_title_disp.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(24), ts[1])))
        card_t.add_widget(lbl_title_disp)
        modal.add_widget(card_t)

        # 4. Scrollable Description / Notes Card
        modal.add_widget(Label(text="[b]Description & Work Notes:[/b]", markup=True, font_size='12sp', color=get_color_from_hex("#38bdf8"), size_hint_y=None, height=dp(20), halign='left'))
        
        desc_card = RoundedCard(
            bg_hex="#131e33",
            radius=[dp(10), dp(10), dp(10), dp(10)],
            border_hex="#1e293b",
            orientation='vertical',
            size_hint=(1, 1),
            padding=[dp(10), dp(8)]
        )
        scroll_desc = ScrollView(size_hint=(1, 1), scroll_type=['content'], bar_width=dp(3))
        
        # Build formatted display text
        body_text = safe_escape_markup(desc_v)
        if rem_v:
            body_text += f"\n\n[b][color=#f59e0b]Remarks:[/color][/b]\n{safe_escape_markup(rem_v)}"
        if lunch_v or tea_v:
            b_list = []
            if lunch_v: b_list.append(f"Lunch: {lunch_v}")
            if tea_v: b_list.append(f"Tea: {tea_v}")
            body_text += f"\n\n[color=#94a3b8]Breaks: {' | '.join(b_list)}[/color]"
        if created_v:
            body_text += f"\n\n[color=#64748b]Logged timestamp: {created_v}[/color]"

        lbl_desc_body = Label(
            text=body_text,
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#e2e8f0"),
            size_hint_y=None,
            halign='left',
            valign='top'
        )
        lbl_desc_body.bind(width=lambda s, w: s.setter('text_size')(s, (w - dp(10), None)))
        lbl_desc_body.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(40), ts[1] + dp(10))))
        scroll_desc.add_widget(lbl_desc_body)
        desc_card.add_widget(scroll_desc)
        modal.add_widget(desc_card)

        # 5. Bottom Action Ribbon: Copy, Edit, Delete, Close
        btn_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        btn_copy = Button(
            text="Copy Notes",
            font_size='12sp',
            bold=True,
            size_hint_x=0.32,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_copy.bind(on_release=lambda x: self._copy_work_record_to_clipboard(r, btn_copy))
        btn_bar.add_widget(btn_copy)

        btn_edit = Button(
            text="Edit Task",
            font_size='12sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=(1, 1, 1, 1)
        )
        def _on_edit_click(x):
            popup.dismiss()
            self.open_edit_work_update_dialog(r, sheet_name)
        btn_edit.bind(on_release=_on_edit_click)
        btn_bar.add_widget(btn_edit)

        btn_del = Button(
            text="Delete",
            font_size='12sp',
            bold=True,
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        def _on_del_click(x):
            popup.dismiss()
            self.delete_update_item(r[0], sheet_name)
        btn_del.bind(on_release=_on_del_click)
        btn_bar.add_widget(btn_del)

        btn_close = Button(
            text="Close",
            font_size='12sp',
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_close.bind(on_release=popup.dismiss)
        btn_bar.add_widget(btn_close)

        modal.add_widget(btn_bar)
        popup.content = modal
        popup.open()

    def open_edit_work_update_dialog(self, r, sheet_name=None):
        rec_id = r[0]
        cur_date = str(r[1] or "")
        cur_proj = str(r[2] or "General Work")
        cur_title = str(r[3] or "")
        cur_desc = str(r[4] or "")
        cur_hours = str(r[5] or "").replace("h", "").strip()
        cur_status = str(r[6] or "Completed")
        cur_rem = str(r[7] or "")
        cur_login = str(r[8] or "")
        cur_logout = str(r[9] or "")

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.94, 0.92),
            auto_dismiss=False
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # Header
        hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(8))
        lbl_head = Label(
            text="[b]Edit Work Update[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.86,
            halign='left',
            valign='middle'
        )
        lbl_head.bind(size=lbl_head.setter('text_size'))
        hdr.add_widget(lbl_head)

        btn_x = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_x.bind(on_release=popup.dismiss)
        hdr.add_widget(btn_x)
        modal.add_widget(hdr)

        # Scrollable form container
        scroll = ScrollView(size_hint=(1, 1), scroll_type=['content'], bar_width=dp(3))
        form = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4), 0, dp(8)])
        form.bind(minimum_height=form.setter('height'))

        # Field 1: Date & Today Button
        form.add_widget(self._create_field_label("Date (YYYY-MM-DD):"))
        d_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        in_date = TextInput(
            text=cur_date,
            multiline=False,
            font_size='14sp',
            size_hint_x=0.74,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        btn_set_today = Button(
            text="Today",
            font_size='12sp',
            bold=True,
            size_hint_x=0.26,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_set_today.bind(on_release=lambda x: setattr(in_date, 'text', datetime.date.today().strftime("%Y-%m-%d")))
        d_row.add_widget(in_date)
        d_row.add_widget(btn_set_today)
        form.add_widget(d_row)

        # Field 2: Project / Module
        form.add_widget(self._create_field_label("Project / Module:"))
        in_proj = TextInput(
            text=cur_proj,
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(42),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        form.add_widget(in_proj)

        # Field 3: Task Title
        form.add_widget(self._create_field_label("Task Title:"))
        in_title = TextInput(
            text=cur_title,
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(42),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        form.add_widget(in_title)

        # Field 4: Hours & Status
        form.add_widget(self._create_field_label("Hours & Status:"))
        h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        in_hours = TextInput(
            text=cur_hours,
            hint_text="e.g. 8.0",
            multiline=False,
            font_size='14sp',
            size_hint_x=0.45,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        sp_stat = Spinner(
            text=cur_status if cur_status in ('Completed', 'In Progress', 'Pending', 'Leave', 'Weekly Off', 'Holiday') else 'Completed',
            values=('Completed', 'In Progress', 'Pending', 'Leave', 'Weekly Off', 'Holiday'),
            font_size='13sp',
            size_hint_x=0.55,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        h_row.add_widget(in_hours)
        h_row.add_widget(sp_stat)
        form.add_widget(h_row)

        # Field 5: Shift Timings (Login - Logout)
        form.add_widget(self._create_field_label("Shift Timings (Login - Logout):"))
        t_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        in_login = TextInput(
            text=cur_login,
            hint_text="10:30 AM",
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        in_logout = TextInput(
            text=cur_logout,
            hint_text="07:30 PM",
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        t_row.add_widget(in_login)
        t_row.add_widget(in_logout)
        form.add_widget(t_row)

        # Field 6: Work Description
        form.add_widget(self._create_field_label("Work Description / Notes:"))
        in_desc = TextInput(
            text=cur_desc,
            hint_text="Enter task description...",
            multiline=True,
            font_size='13sp',
            size_hint_y=None,
            height=dp(110),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        form.add_widget(in_desc)

        scroll.add_widget(form)
        modal.add_widget(scroll)

        # Bottom Action Buttons
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        
        btn_save = Button(
            text="Save Changes",
            font_size='14sp',
            bold=True,
            size_hint_x=0.6,
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1)
        )
        def _do_save_edit(x):
            new_date = in_date.text.strip()
            new_proj = in_proj.text.strip() or "General Work"
            new_title = in_title.text.strip()
            new_desc = in_desc.text.strip()
            new_hours = in_hours.text.strip()
            new_st = sp_stat.text.strip()
            new_login = in_login.text.strip()
            new_logout = in_logout.text.strip()

            if not new_title:
                self.show_popup("Error", "Please enter a Task Title.")
                return

            if 'save_work_update' in globals():
                ok = save_work_update(
                    new_date, new_proj, new_title, new_desc, new_hours, new_st, cur_rem,
                    login_time=new_login, logout_time=new_logout, record_id=rec_id
                )
                if ok is not False:
                    popup.dismiss()
                    self.show_popup("Success", "Work update updated successfully!")
                    self.refresh_history_list()
                    # Trigger background Google Sheet auto sync if configured
                    settings = load_settings() if 'load_settings' in globals() else {}
                    if settings.get("gsheet_auto_sync", False) and settings.get("gsheet_webapp_url"):
                        try:
                            dt = datetime.datetime.strptime(new_date, "%Y-%m-%d")
                            m_name = dt.strftime("%B %Y")
                        except Exception:
                            m_name = datetime.datetime.now().strftime("%B %Y")
                        threading.Thread(target=lambda: sync_google_sheet_month(m_name), daemon=True).start()
                else:
                    self.show_popup("Error", "Failed to update record in Excel file.")
            else:
                self.show_popup("Error", "Save engine not loaded.")

        btn_save.bind(on_release=_do_save_edit)
        btn_row.add_widget(btn_save)

        btn_cancel = Button(
            text="Cancel",
            font_size='14sp',
            size_hint_x=0.4,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_cancel)

        modal.add_widget(btn_row)
        popup.content = modal
        popup.open()

    def delete_update_item(self, record_id, sheet_name):
        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.88, 0.38),
            auto_dismiss=True
        )

        modal = RoundedCard(
            bg_hex="#0f172a",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#ef4444",
            orientation='vertical',
            padding=[dp(16), dp(14), dp(16), dp(14)],
            spacing=dp(10)
        )

        lbl_head = Label(
            text="[b]Confirm Deletion[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#ef4444"),
            size_hint_y=None,
            height=dp(28),
            halign='center',
            valign='middle'
        )
        lbl_head.bind(size=lbl_head.setter('text_size'))
        modal.add_widget(lbl_head)

        lbl_body = Label(
            text="Are you sure you want to delete this work update?\nThis action cannot be undone.",
            font_size='13sp',
            color=get_color_from_hex("#cbd5e1"),
            size_hint=(1, 1),
            halign='center',
            valign='middle'
        )
        lbl_body.bind(size=lbl_body.setter('text_size'))
        modal.add_widget(lbl_body)

        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        
        btn_confirm = Button(
            text="Delete",
            font_size='14sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        def _do_del(x):
            popup.dismiss()
            if 'delete_work_update' in globals():
                ok = delete_work_update(record_id, sheet_name)
                if ok:
                    self.refresh_history_list()
                    self.show_popup("Deleted", "Task record removed successfully!")
                else:
                    self.show_popup("Error", "Could not delete record.")
        btn_confirm.bind(on_release=_do_del)
        btn_row.add_widget(btn_confirm)

        btn_cancel = Button(
            text="Cancel",
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_cancel)

        modal.add_widget(btn_row)
        popup.content = modal
        popup.open()

    # =========================================================================
    # TAB 3: WORK & PERSONAL NOTES VIEW (MODERN MOBILE UI)
    # =========================================================================
    def build_notes_view(self):
        root = BoxLayout(orientation='vertical', padding=[dp(8), dp(6), dp(8), dp(6)], spacing=dp(6))

        # 1. Top Bar: Search Input + Cloud Sync + New Note Button
        top_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        self.in_notes_search = TextInput(
            hint_text="Search notes by title, tag, or content...",
            multiline=False,
            font_size='13sp',
            size_hint_x=0.52,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        self.in_notes_search.bind(text=lambda s, val: self._on_notes_search_changed(val))
        top_row.add_widget(self.in_notes_search)

        btn_cloud_sync = Button(
            text="Cloud Sync",
            font_size='11sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_cloud_sync.bind(on_release=lambda x: self.open_notes_cloud_sync_dialog())
        top_row.add_widget(btn_cloud_sync)

        btn_add_note = Button(
            text="+ Note",
            font_size='13sp',
            bold=True,
            size_hint_x=0.23,
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1)
        )
        btn_add_note.bind(on_release=lambda x: self.open_note_editor(None))
        top_row.add_widget(btn_add_note)
        root.add_widget(top_row)

        # 2. Executive 3-Card KPI Dashboard Strip for Notes
        kpi_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(52), spacing=dp(6))
        
        self.card_kpi_notes_total = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.33, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_notes_val = Label(text="0", font_size='16sp', bold=True, color=(1, 1, 1, 1), halign='center', valign='middle')
        self.lbl_kpi_notes_val.bind(size=self.lbl_kpi_notes_val.setter('text_size'))
        lbl_kpi_notes_sub = Label(text="Total Notes", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_notes_sub.bind(size=lbl_kpi_notes_sub.setter('text_size'))
        self.card_kpi_notes_total.add_widget(self.lbl_kpi_notes_val)
        self.card_kpi_notes_total.add_widget(lbl_kpi_notes_sub)
        kpi_row.add_widget(self.card_kpi_notes_total)

        self.card_kpi_notes_todos = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.34, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_todos_val = Label(text="0/0", font_size='16sp', bold=True, color=get_color_from_hex("#34d399"), halign='center', valign='middle')
        self.lbl_kpi_todos_val.bind(size=self.lbl_kpi_todos_val.setter('text_size'))
        lbl_kpi_todos_sub = Label(text="Checklist Done", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_todos_sub.bind(size=lbl_kpi_todos_sub.setter('text_size'))
        self.card_kpi_notes_todos.add_widget(self.lbl_kpi_todos_val)
        self.card_kpi_notes_todos.add_widget(lbl_kpi_todos_sub)
        kpi_row.add_widget(self.card_kpi_notes_todos)

        self.card_kpi_notes_pinned = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#334155", orientation='vertical', size_hint_x=0.33, padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(1))
        self.lbl_kpi_pinned_val = Label(text="0", font_size='16sp', bold=True, color=get_color_from_hex("#f59e0b"), halign='center', valign='middle')
        self.lbl_kpi_pinned_val.bind(size=self.lbl_kpi_pinned_val.setter('text_size'))
        lbl_kpi_pinned_sub = Label(text="Pinned", font_size='10sp', color=get_color_from_hex("#94a3b8"), halign='center', valign='middle')
        lbl_kpi_pinned_sub.bind(size=lbl_kpi_pinned_sub.setter('text_size'))
        self.card_kpi_notes_pinned.add_widget(self.lbl_kpi_pinned_val)
        self.card_kpi_notes_pinned.add_widget(lbl_kpi_pinned_sub)
        kpi_row.add_widget(self.card_kpi_notes_pinned)

        root.add_widget(kpi_row)

        # 3. Quick 1-Tap Template Action Ribbon
        tpl_scroll = ScrollView(size_hint_y=None, height=dp(30), do_scroll_x=True, do_scroll_y=False, bar_width=0)
        tpl_box = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(30), spacing=dp(6), padding=[dp(2), 0, dp(2), 0])
        tpl_box.bind(minimum_width=tpl_box.setter('width'))

        templates = [
            ("+ Checklist", "Todo", "Checklist: ", "- [ ] Item 1\n- [ ] Item 2\n- [ ] Item 3", "#10b981"),
            ("+ Meeting", "Meeting", "Meeting: ", "Agenda:\n- \n\nKey Decisions:\n- \n\nAction Items:\n- [ ] ", "#8b5cf6"),
            ("+ Standup", "Work", f"Standup - {datetime.date.today().strftime('%b %d')}", "Today Goals:\n- \n\nCompleted:\n- \n\nBlockers:\n- None", "#2563eb"),
            ("+ Idea", "Ideas", "Idea: ", "Problem / Context:\n\nProposed Solution:\n\nNext Steps:\n- [ ] ", "#f59e0b"),
            ("+ Urgent", "Urgent", "URGENT: ", "Action Required:\n- \nDeadline:\nAssigned To:", "#ef4444")
        ]

        for t_label, t_tag, t_title, t_content, t_color in templates:
            b_tpl = Button(
                text=t_label,
                font_size='11sp',
                bold=True,
                size_hint_x=None,
                width=dp(len(t_label) * 8 + 24),
                background_normal='',
                background_color=get_color_from_hex(t_color),
                color=(1, 1, 1, 1)
            )
            def _launch_tpl(b, tg=t_tag, tt=t_title, tc=t_content):
                self.open_note_editor(None, initial_title=tt, initial_content=tc, initial_tag=tg)
            b_tpl.bind(on_release=_launch_tpl)
            tpl_box.add_widget(b_tpl)
        tpl_scroll.add_widget(tpl_box)
        root.add_widget(tpl_scroll)

        # 4. Category Filter Bar with Live Counts
        self.current_note_filter = "All"
        cat_scroll = ScrollView(size_hint_y=None, height=dp(32), do_scroll_x=True, do_scroll_y=False, bar_width=0)
        self.cat_box = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(32), spacing=dp(6), padding=[dp(2), 0, dp(2), 0])
        self.cat_box.bind(minimum_width=self.cat_box.setter('width'))
        self.note_categories = ["All", "Work", "Meeting", "Ideas", "Todo", "Urgent", "Personal"]
        self.cat_buttons = {}
        for cat in self.note_categories:
            btn_cat = Button(
                text=cat,
                font_size='11sp',
                bold=True,
                size_hint_x=None,
                width=dp(70) if len(cat) > 4 else dp(55),
                background_normal='',
                background_color=get_color_from_hex("#2563eb" if cat == "All" else "#1e293b"),
                color=(1, 1, 1, 1) if cat == "All" else get_color_from_hex("#94a3b8")
            )
            btn_cat.bind(on_release=lambda x, c=cat: self._set_note_filter(c))
            self.cat_buttons[cat] = btn_cat
            self.cat_box.add_widget(btn_cat)
        cat_scroll.add_widget(self.cat_box)
        root.add_widget(cat_scroll)

        # 5. Search Bar Clear Action Row (hidden when empty)
        self.btn_clear_notes_search = Button(
            text="Clear Search Query",
            font_size='10sp',
            bold=True,
            size_hint_y=None,
            height=dp(24),
            opacity=0,
            disabled=True,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        self.btn_clear_notes_search.bind(on_release=lambda x: self._clear_notes_search())
        root.add_widget(self.btn_clear_notes_search)

        # 6. Notes List ScrollView
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(3), scroll_type=['content'])
        self.notes_list_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4), 0, dp(12)])
        self.notes_list_layout.bind(minimum_height=self.notes_list_layout.setter('height'))
        scroll.add_widget(self.notes_list_layout)
        root.add_widget(scroll)

        return root

    def _on_notes_search_changed(self, val):
        if hasattr(self, 'btn_clear_notes_search') and self.btn_clear_notes_search:
            has_text = bool(val.strip())
            self.btn_clear_notes_search.opacity = 1 if has_text else 0
            self.btn_clear_notes_search.disabled = not has_text
            self.btn_clear_notes_search.height = dp(24) if has_text else dp(0)
        self.refresh_notes_list()

    def _clear_notes_search(self):
        if hasattr(self, 'in_notes_search') and self.in_notes_search:
            self.in_notes_search.text = ""

    def _set_note_filter(self, cat):
        self.current_note_filter = cat
        for c, btn in self.cat_buttons.items():
            if c == cat:
                btn.background_color = get_color_from_hex("#2563eb")
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = get_color_from_hex("#1e293b")
                btn.color = get_color_from_hex("#94a3b8")
        self.refresh_notes_list()

    def refresh_notes_list(self):
        if not hasattr(self, 'notes_list_layout') or not self.notes_list_layout:
            return
        self.notes_list_layout.clear_widgets()

        notes = load_notes() if 'load_notes' in globals() else []

        search_q = self.in_notes_search.text.strip().lower() if hasattr(self, 'in_notes_search') and self.in_notes_search else ""
        cur_filter = getattr(self, 'current_note_filter', 'All')

        # Calculate metrics for KPI strip
        cat_counts = {c: 0 for c in getattr(self, 'note_categories', ["All"])}
        cat_counts["All"] = len(notes)
        pinned_cnt = 0
        total_checklist_tasks = 0
        done_checklist_tasks = 0

        for n in notes:
            t = str(n.get("tag", "Work")).title()
            if t in cat_counts:
                cat_counts[t] += 1
            if n.get("is_pinned", False):
                pinned_cnt += 1
            
            # Count checklist stats
            c_text = n.get("content", "")
            for line in c_text.splitlines():
                ls = line.strip()
                if ls.startswith("- [ ]") or ls.startswith("[ ]"):
                    total_checklist_tasks += 1
                elif ls.startswith("- [x]") or ls.startswith("- [X]") or ls.startswith("[x]") or ls.startswith("[X]"):
                    total_checklist_tasks += 1
                    done_checklist_tasks += 1

        # Update KPI Cards
        if hasattr(self, 'lbl_kpi_notes_val') and self.lbl_kpi_notes_val:
            self.lbl_kpi_notes_val.text = str(len(notes))
        if hasattr(self, 'lbl_kpi_todos_val') and self.lbl_kpi_todos_val:
            self.lbl_kpi_todos_val.text = f"{done_checklist_tasks}/{total_checklist_tasks}" if total_checklist_tasks > 0 else "0/0"
        if hasattr(self, 'lbl_kpi_pinned_val') and self.lbl_kpi_pinned_val:
            self.lbl_kpi_pinned_val.text = str(pinned_cnt)

        # Update category buttons text & width
        for c, btn in getattr(self, 'cat_buttons', {}).items():
            cnt = cat_counts.get(c, 0)
            btn.text = f"{c} ({cnt})"
            btn.width = dp(max(60, len(btn.text) * 8 + 20))

        filtered = []
        for n in notes:
            n_title = str(n.get("title", "")).lower()
            n_content = str(n.get("content", "")).lower()
            n_tag = str(n.get("tag", "Work"))

            if cur_filter != "All" and n_tag.lower() != cur_filter.lower():
                continue

            if search_q and (search_q not in n_title and search_q not in n_content and search_q not in n_tag.lower()):
                continue

            filtered.append(n)

        # Sort: pinned notes first, then latest updated/created
        filtered.sort(key=lambda x: (not x.get("is_pinned", False), x.get("updated_at", x.get("created_at", ""))), reverse=False)

        if not filtered:
            empty_card = RoundedCard(
                bg_hex="#131e33",
                radius=[dp(12), dp(12), dp(12), dp(12)],
                border_hex="#334155",
                orientation='vertical',
                size_hint_y=None,
                height=dp(160),
                padding=[dp(16), dp(16), dp(16), dp(16)],
                spacing=dp(8)
            )
            lbl_e_title = Label(
                text="[b]No Notes Found[/b]" if search_q else "[b]No Notes Yet[/b]",
                markup=True,
                font_size='15sp',
                color=get_color_from_hex("#38bdf8"),
                size_hint_y=None,
                height=dp(24),
                halign='center'
            )
            empty_card.add_widget(lbl_e_title)

            sub_msg = f"No notes match '{search_q}'. Tap 'Clear Search' to view all notes." if search_q else "Capture quick standup drafts, meeting minutes, sprint tasks, or checklists."
            lbl_e_sub = Label(
                text=sub_msg,
                font_size='12sp',
                color=get_color_from_hex("#94a3b8"),
                size_hint_y=None,
                height=dp(40),
                halign='center'
            )
            def _bind_es(lbl, *args):
                lbl.text_size = (lbl.width - dp(20), None)
            lbl_e_sub.bind(width=_bind_es)
            empty_card.add_widget(lbl_e_sub)

            btn_e_create = Button(
                text="+ Create First Note",
                font_size='13sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(180), dp(38)),
                pos_hint={'center_x': 0.5},
                background_normal='',
                background_color=get_color_from_hex("#10b981"),
                color=(1, 1, 1, 1)
            )
            btn_e_create.bind(on_release=lambda x: self.open_note_editor(None))
            empty_card.add_widget(btn_e_create)
            self.notes_list_layout.add_widget(empty_card)
            return

        for n in filtered:
            card = self._create_note_card(n)
            self.notes_list_layout.add_widget(card)

    def _create_note_card(self, note):
        note_id = note.get("id")
        title = note.get("title", "Untitled Note")
        content = note.get("content", "")
        tag = note.get("tag", "Work")
        is_pinned = note.get("is_pinned", False)
        time_str = note.get("updated_at") or note.get("created_at") or ""

        tag_colors = {
            "work": "#3b82f6",
            "meeting": "#8b5cf6",
            "ideas": "#f59e0b",
            "todo": "#10b981",
            "urgent": "#ef4444",
            "personal": "#ec4899"
        }
        accent_color = tag_colors.get(tag.lower(), "#64748b")

        card = RoundedCard(
            bg_hex="#162238",
            radius=[dp(12), dp(12), dp(12), dp(12)],
            border_hex="#f59e0b" if is_pinned else "#334155",
            orientation='vertical',
            size_hint_y=None,
            padding=[dp(12), dp(10), dp(12), dp(10)],
            spacing=dp(6)
        )
        card.bind(minimum_height=card.setter('height'))

        # Header Row: [PIN] Badge + Title + Category Pill
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(26), spacing=dp(6))
        
        pin_prefix = "[color=#f59e0b][b][PIN][/b][/color] " if is_pinned else ""
        lbl_title = Label(
            text=f"{pin_prefix}[b]{safe_escape_markup(title)}[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.72,
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='right'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        row1.add_widget(lbl_title)

        lbl_tag_pill = Label(
            text=f"[b]{safe_escape_markup(tag.upper())}[/b]",
            markup=True,
            font_size='10sp',
            color=get_color_from_hex(accent_color),
            size_hint_x=0.28,
            halign='right',
            valign='middle'
        )
        lbl_tag_pill.bind(size=lbl_tag_pill.setter('text_size'))
        row1.add_widget(lbl_tag_pill)
        card.add_widget(row1)

        # Check for checklist progress
        c_lines = content.strip().splitlines() if content else []
        chk_total = 0
        chk_done = 0
        for l in c_lines:
            ls = l.strip()
            if ls.startswith("- [ ]") or ls.startswith("[ ]"):
                chk_total += 1
            elif ls.startswith("- [x]") or ls.startswith("- [X]") or ls.startswith("[x]") or ls.startswith("[X]"):
                chk_total += 1
                chk_done += 1

        if chk_total > 0:
            pct = int((chk_done / chk_total) * 100) if chk_total else 0
            prog_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(20), spacing=dp(6))
            lbl_prog = Label(
                text=f"[b][x] {chk_done}/{chk_total} Tasks Completed ({pct}%)[/b]",
                markup=True,
                font_size='11sp',
                color=get_color_from_hex("#34d399" if chk_done == chk_total else "#38bdf8"),
                size_hint_x=0.75,
                halign='left',
                valign='middle'
            )
            lbl_prog.bind(size=lbl_prog.setter('text_size'))
            prog_row.add_widget(lbl_prog)
            card.add_widget(prog_row)

        # Content Snippet Preview inside Dark Inset Box
        preview_text = "\n".join(c_lines[:3]) if len(c_lines) > 3 else content.strip()
        if len(c_lines) > 3 or len(content) > 140:
            preview_text = (preview_text[:130] + "...") if len(preview_text) > 130 else (preview_text + "\n...")

        if preview_text:
            desc_card = RoundedCard(
                bg_hex="#0b1322",
                radius=[dp(6), dp(6), dp(6), dp(6)],
                size_hint_y=None,
                height=dp(42),
                padding=[dp(8), dp(4), dp(8), dp(4)]
            )
            lbl_desc = Label(
                text=safe_escape_markup(preview_text),
                font_size='11sp',
                color=get_color_from_hex("#94a3b8"),
                halign='left',
                valign='middle'
            )
            lbl_desc.bind(size=lbl_desc.setter('text_size'))
            desc_card.add_widget(lbl_desc)
            card.add_widget(desc_card)

        # Bottom Action Ribbon: Open, Copy, Edit, Pin, Share, Del
        row_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(5))
        
        btn_open = Button(
            text="Open",
            font_size='11sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#38bdf8")
        )
        btn_open.bind(on_release=lambda x, n=note: self.view_note_details(n))
        row_acts.add_widget(btn_open)

        btn_copy = Button(
            text="Copy",
            font_size='11sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        def _quick_copy(x, n=note):
            txt = f"{n.get('title', '')}\n\n{n.get('content', '')}".strip()
            if Clipboard is not None:
                try:
                    Clipboard.copy(txt)
                except Exception:
                    pass
            self.show_popup("Copied", f"Note '{n.get('title', 'Note')}' copied to clipboard!")
        btn_copy.bind(on_release=_quick_copy)
        row_acts.add_widget(btn_copy)

        btn_edit = Button(
            text="Edit",
            font_size='11sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=(1, 1, 1, 1)
        )
        btn_edit.bind(on_release=lambda x, n=note: self.open_note_editor(n))
        row_acts.add_widget(btn_edit)

        btn_pin = Button(
            text="Unpin" if is_pinned else "Pin",
            font_size='11sp',
            bold=True,
            size_hint_x=0.16,
            background_normal='',
            background_color=get_color_from_hex("#f59e0b" if is_pinned else "#334155"),
            color=(1, 1, 1, 1)
        )
        btn_pin.bind(on_release=lambda x, nid=note_id: self.toggle_note_pin(nid))
        row_acts.add_widget(btn_pin)

        btn_share = Button(
            text="Share",
            font_size='11sp',
            bold=True,
            size_hint_x=0.16,
            background_normal='',
            background_color=get_color_from_hex("#8b5cf6"),
            color=(1, 1, 1, 1)
        )
        btn_share.bind(on_release=lambda x, n=note: self.share_note_dialog(n))
        row_acts.add_widget(btn_share)

        btn_del = Button(
            text="Del",
            font_size='11sp',
            bold=True,
            size_hint_x=0.14,
            background_normal='',
            background_color=get_color_from_hex("#7f1d1d"),
            color=get_color_from_hex("#f87171")
        )
        btn_del.bind(on_release=lambda x, nid=note_id: self.delete_note_item(nid))
        row_acts.add_widget(btn_del)

        card.add_widget(row_acts)
        return card

    # =========================================================================
    # FULL NOTE DETAILS & INTERACTIVE CHECKLIST READER
    # =========================================================================
    def view_note_details(self, note):
        note_id = note.get("id")
        title = note.get("title", "Untitled Note")
        content = note.get("content", "")
        tag = note.get("tag", "Work")
        is_pinned = note.get("is_pinned", False)
        time_str = note.get("updated_at") or note.get("created_at") or ""

        tag_colors = {
            "work": "#3b82f6",
            "meeting": "#8b5cf6",
            "ideas": "#f59e0b",
            "todo": "#10b981",
            "urgent": "#ef4444",
            "personal": "#ec4899"
        }
        accent_color = tag_colors.get(tag.lower(), "#64748b")

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.94, 0.88),
            auto_dismiss=True
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # 1. Header Bar: Tag Badge + Pinned + Close [X]
        hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(8))
        
        lbl_tag_badge = Label(
            text=f"[b]{tag.upper()}[/b]",
            markup=True,
            font_size='12sp',
            color=get_color_from_hex(accent_color),
            size_hint_x=0.30,
            halign='left',
            valign='middle'
        )
        lbl_tag_badge.bind(size=lbl_tag_badge.setter('text_size'))
        hdr.add_widget(lbl_tag_badge)

        pin_str = "[color=#f59e0b][b][PINNED][/b][/color]  " if is_pinned else ""
        lbl_time_hdr = Label(
            text=f"{pin_str}{time_str}",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex("#94a3b8"),
            size_hint_x=0.56,
            halign='right',
            valign='middle'
        )
        lbl_time_hdr.bind(size=lbl_time_hdr.setter('text_size'))
        hdr.add_widget(lbl_time_hdr)

        btn_x = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_x.bind(on_release=popup.dismiss)
        hdr.add_widget(btn_x)
        modal.add_widget(hdr)

        # 2. Large Note Title
        card_t = RoundedCard(bg_hex="#162238", radius=[dp(8), dp(8), dp(8), dp(8)], size_hint_y=None, padding=[dp(10), dp(8)], spacing=dp(2))
        card_t.bind(minimum_height=card_t.setter('height'))
        lbl_title_disp = Label(
            text=f"[b]{safe_escape_markup(title)}[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_y=None,
            halign='left',
            valign='top'
        )
        lbl_title_disp.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        lbl_title_disp.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(26), ts[1])))
        card_t.add_widget(lbl_title_disp)
        modal.add_widget(card_t)

        # 3. Interactive Checklist and Formatted Content Container
        scroll_content = ScrollView(size_hint=(1, 1), scroll_type=['content'], bar_width=dp(3))
        content_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(8)])
        content_box.bind(minimum_height=content_box.setter('height'))

        # Parse lines for interactive checklist items
        lines = content.splitlines() if content else []
        has_chk = any(l.strip().startswith(("- [ ]", "- [x]", "- [X]", "[ ]", "[x]", "[X]")) for l in lines)

        if has_chk:
            chk_box = RoundedCard(bg_hex="#131e33", radius=[dp(8), dp(8), dp(8), dp(8)], orientation='vertical', size_hint_y=None, spacing=dp(4), padding=[dp(8), dp(6)])
            chk_box.bind(minimum_height=chk_box.setter('height'))
            
            lbl_chk_header = Label(text="[b]Interactive Checklist (Tap to toggle):[/b]", markup=True, font_size='12sp', color=get_color_from_hex("#38bdf8"), size_hint_y=None, height=dp(22), halign='left')
            lbl_chk_header.bind(size=lbl_chk_header.setter('text_size'))
            chk_box.add_widget(lbl_chk_header)

            non_chk_lines = []

            for l_idx, line in enumerate(lines):
                ls = line.strip()
                is_todo = ls.startswith(("- [ ]", "[ ]"))
                is_done = ls.startswith(("- [x]", "- [X]", "[x]", "[X]"))

                if is_todo or is_done:
                    # Extract item text
                    if ls.startswith("- [ ]") or ls.startswith("- [x]") or ls.startswith("- [X]"):
                        item_text = ls[5:].strip()
                    else:
                        item_text = ls[3:].strip()

                    row_chk = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
                    
                    btn_toggle = Button(
                        text="[X]" if is_done else "[ ]",
                        font_size='13sp',
                        bold=True,
                        size_hint_x=None,
                        width=dp(38),
                        background_normal='',
                        background_color=get_color_from_hex("#10b981" if is_done else "#334155"),
                        color=(1, 1, 1, 1)
                    )
                    
                    lbl_item = Label(
                        text=f"[color=#64748b]{safe_escape_markup(item_text)}[/color]" if is_done else f"[color=#f8fafc]{safe_escape_markup(item_text)}[/color]",
                        markup=True,
                        font_size='13sp',
                        size_hint_x=0.88,
                        halign='left',
                        valign='middle'
                    )
                    lbl_item.bind(size=lbl_item.setter('text_size'))

                    def _make_toggle(idx=l_idx, done=is_done):
                        def _handler(b):
                            popup.dismiss()
                            self.toggle_note_checklist_item(note_id, idx, done)
                        return _handler

                    btn_toggle.bind(on_release=_make_toggle(l_idx, is_done))
                    row_chk.add_widget(btn_toggle)
                    row_chk.add_widget(lbl_item)
                    chk_box.add_widget(row_chk)
                else:
                    if line.strip():
                        non_chk_lines.append(line)

            content_box.add_widget(chk_box)

            if non_chk_lines:
                lbl_extra = Label(
                    text=safe_escape_markup("\n".join(non_chk_lines)),
                    markup=True,
                    font_size='13sp',
                    color=get_color_from_hex("#cbd5e1"),
                    size_hint_y=None,
                    halign='left',
                    valign='top'
                )
                lbl_extra.bind(width=lambda s, w: s.setter('text_size')(s, (w - dp(10), None)))
                lbl_extra.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(30), ts[1] + dp(10))))
                content_box.add_widget(lbl_extra)
        else:
            # Full formatted text reader card
            card_body = RoundedCard(bg_hex="#131e33", radius=[dp(10), dp(10), dp(10), dp(10)], border_hex="#1e293b", size_hint_y=None, padding=[dp(10), dp(8)])
            card_body.bind(minimum_height=card_body.setter('height'))
            
            lbl_body = Label(
                text=safe_escape_markup(content or "No notes content."),
                markup=True,
                font_size='13sp',
                color=get_color_from_hex("#e2e8f0"),
                size_hint_y=None,
                halign='left',
                valign='top'
            )
            lbl_body.bind(width=lambda s, w: s.setter('text_size')(s, (w - dp(10), None)))
            lbl_body.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(60), ts[1] + dp(12))))
            card_body.add_widget(lbl_body)
            content_box.add_widget(card_body)

        scroll_content.add_widget(content_box)
        modal.add_widget(scroll_content)

        # 4. Action Ribbon at bottom
        btn_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        btn_copy = Button(
            text="Copy",
            font_size='12sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        def _cp(b):
            txt = f"{title}\n\n{content}".strip()
            if Clipboard is not None:
                try:
                    Clipboard.copy(txt)
                except Exception:
                    pass
            b.text = "Copied!"
            Clock.schedule_once(lambda dt: setattr(b, 'text', "Copy"), 1.5)
        btn_copy.bind(on_release=_cp)
        btn_bar.add_widget(btn_copy)

        btn_edit = Button(
            text="Edit Note",
            font_size='12sp',
            bold=True,
            size_hint_x=0.26,
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=(1, 1, 1, 1)
        )
        def _ed(b):
            popup.dismiss()
            self.open_note_editor(note)
        btn_edit.bind(on_release=_ed)
        btn_bar.add_widget(btn_edit)

        btn_share = Button(
            text="Share",
            font_size='12sp',
            bold=True,
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#8b5cf6"),
            color=(1, 1, 1, 1)
        )
        def _sh(b):
            popup.dismiss()
            self.share_note_dialog(note)
        btn_share.bind(on_release=_sh)
        btn_bar.add_widget(btn_share)

        btn_pin_act = Button(
            text="Unpin" if is_pinned else "Pin",
            font_size='12sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#f59e0b" if is_pinned else "#334155"),
            color=(1, 1, 1, 1)
        )
        def _pn(b):
            popup.dismiss()
            self.toggle_note_pin(note_id)
        btn_pin_act.bind(on_release=_pn)
        btn_bar.add_widget(btn_pin_act)

        btn_close = Button(
            text="Close",
            font_size='12sp',
            size_hint_x=0.14,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_close.bind(on_release=popup.dismiss)
        btn_bar.add_widget(btn_close)

        modal.add_widget(btn_bar)
        popup.content = modal
        popup.open()

    def toggle_note_checklist_item(self, note_id, line_idx, is_currently_done):
        notes = load_notes() if 'load_notes' in globals() else []
        target_note = None
        for n in notes:
            if n.get("id") == note_id:
                target_note = n
                break
        if not target_note:
            return

        lines = target_note.get("content", "").splitlines()
        if 0 <= line_idx < len(lines):
            orig_line = lines[line_idx]
            if is_currently_done:
                # Turn into unchecked: - [ ]
                lines[line_idx] = orig_line.replace("- [x]", "- [ ]").replace("- [X]", "- [ ]").replace("[x]", "[ ]").replace("[X]", "[ ]")
            else:
                # Turn into checked: - [x]
                lines[line_idx] = orig_line.replace("- [ ]", "- [x]").replace("[ ]", "[x]")

            target_note["content"] = "\n".join(lines)
            target_note["updated_at"] = datetime.datetime.now().strftime("%b %d, %I:%M %p")

            if 'save_notes' in globals():
                save_notes(notes)

            self.refresh_notes_list()
            self.auto_sync_notes_to_gsheet()
            self.view_note_details(target_note)

    # =========================================================================
    # NOTE EDITOR MODAL WITH RICH QUICK FORMATTING TOOLS
    # =========================================================================
    def open_note_editor(self, note=None, initial_title="", initial_content="", initial_tag="Work", initial_pin=False):
        is_edit = note is not None
        note_id = note.get("id") if is_edit else uuid.uuid4().hex[:10]
        curr_tag = [note.get("tag", initial_tag) if is_edit else initial_tag]
        curr_pin = [note.get("is_pinned", initial_pin) if is_edit else initial_pin]

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.94, 0.92),
            auto_dismiss=False
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # Title Bar with ASCII 'X' Close button
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(8))
        lbl_modal_title = Label(
            text=f"[b]{'Edit Note' if is_edit else 'Create New Note'}[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.86,
            halign='left',
            valign='middle'
        )
        lbl_modal_title.bind(size=lbl_modal_title.setter('text_size'))
        title_bar.add_widget(lbl_modal_title)

        btn_close = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_close.bind(on_release=popup.dismiss)
        title_bar.add_widget(btn_close)
        modal.add_widget(title_bar)

        # Scrollable form container
        form_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(3), scroll_type=['content'])
        form_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(2), dp(2), dp(2), dp(6)])
        form_box.bind(minimum_height=form_box.setter('height'))

        # Title Input
        form_box.add_widget(self._create_field_label("Note Title:"))
        in_title = TextInput(
            text=note.get("title", "") if is_edit else initial_title,
            hint_text="e.g. Sprint Tasks, Standup Agenda, Client Feedback",
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(42),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        form_box.add_widget(in_title)

        # Category Chips (1-tap selection)
        form_box.add_widget(self._create_field_label("Category Tag:"))
        cat_scroll_ed = ScrollView(size_hint_y=None, height=dp(34), do_scroll_x=True, do_scroll_y=False, bar_width=0)
        cat_box_ed = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(34), spacing=dp(6))
        cat_box_ed.bind(minimum_width=cat_box_ed.setter('width'))

        cat_colors = {
            "Work": "#2563eb",
            "Meeting": "#8b5cf6",
            "Ideas": "#f59e0b",
            "Todo": "#10b981",
            "Urgent": "#ef4444",
            "Personal": "#ec4899"
        }
        ed_cat_btns = []
        for c_name, c_hex in cat_colors.items():
            b_c = Button(
                text=c_name,
                font_size='11sp',
                bold=True,
                size_hint_x=None,
                width=dp(max(60, len(c_name) * 8 + 20)),
                background_normal='',
                background_color=get_color_from_hex(c_hex if curr_tag[0].lower() == c_name.lower() else "#334155"),
                color=(1, 1, 1, 1)
            )
            def _pick_cat(b, name=c_name):
                curr_tag[0] = name
                for btn_obj, btn_name, btn_hex in ed_cat_btns:
                    btn_obj.background_color = get_color_from_hex(btn_hex if curr_tag[0] == btn_name else "#334155")
            b_c.bind(on_release=_pick_cat)
            ed_cat_btns.append((b_c, c_name, c_hex))
            cat_box_ed.add_widget(b_c)
        cat_scroll_ed.add_widget(cat_box_ed)
        form_box.add_widget(cat_scroll_ed)

        # Quick Formatting & Insert Toolbar
        form_box.add_widget(self._create_field_label("Insert Formatting Shortcuts:"))
        tool_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
        
        btn_pin_tog = Button(
            text=f"Pin: {'YES' if curr_pin[0] else 'NO'}",
            font_size='11sp',
            bold=True,
            size_hint_x=0.24,
            background_normal='',
            background_color=get_color_from_hex("#f59e0b" if curr_pin[0] else "#334155"),
            color=(1, 1, 1, 1)
        )
        def _toggle_pin_in_modal(b):
            curr_pin[0] = not curr_pin[0]
            btn_pin_tog.text = f"Pin: {'YES' if curr_pin[0] else 'NO'}"
            btn_pin_tog.background_color = get_color_from_hex("#f59e0b" if curr_pin[0] else "#334155")
        btn_pin_tog.bind(on_release=_toggle_pin_in_modal)
        tool_row.add_widget(btn_pin_tog)

        btn_ins_chk = Button(
            text="+ [ ] Todo",
            font_size='11sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#0f766e"),
            color=(1, 1, 1, 1)
        )
        def _ins_chk(b):
            prefix = "\n- [ ] " if in_content.text and not in_content.text.endswith("\n") else "- [ ] "
            in_content.text += prefix
        btn_ins_chk.bind(on_release=_ins_chk)
        tool_row.add_widget(btn_ins_chk)

        btn_ins_bullet = Button(
            text="+ Bullet",
            font_size='11sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#4338ca"),
            color=(1, 1, 1, 1)
        )
        def _ins_bullet(b):
            prefix = "\n* " if in_content.text and not in_content.text.endswith("\n") else "* "
            in_content.text += prefix
        btn_ins_bullet.bind(on_release=_ins_bullet)
        tool_row.add_widget(btn_ins_bullet)

        btn_ins_time = Button(
            text="+ Time",
            font_size='11sp',
            bold=True,
            size_hint_x=0.26,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        def _ins_time(b):
            t_now = datetime.datetime.now().strftime("[%I:%M %p] ")
            in_content.text += ("\n" + t_now if in_content.text and not in_content.text.endswith("\n") else t_now)
        btn_ins_time.bind(on_release=_ins_time)
        tool_row.add_widget(btn_ins_time)
        form_box.add_widget(tool_row)

        # Content Input
        form_box.add_widget(self._create_field_label("Note Details / Content:"))
        in_content = TextInput(
            text=note.get("content", "") if is_edit else initial_content,
            hint_text="Type or paste your notes, checklist, meeting points...",
            multiline=True,
            font_size='13sp',
            size_hint_y=None,
            height=dp(170),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        form_box.add_widget(in_content)

        # Word / Char Counter
        lbl_stats = Label(
            text="0 words | 0 chars",
            font_size='11sp',
            color=get_color_from_hex("#64748b"),
            size_hint_y=None,
            height=dp(18),
            halign='right'
        )
        def _update_stats(inst, val):
            words = len(val.split()) if val.strip() else 0
            chars = len(val)
            lbl_stats.text = f"{words} words | {chars} chars"
        in_content.bind(text=_update_stats)
        _update_stats(None, in_content.text)
        form_box.add_widget(lbl_stats)

        form_scroll.add_widget(form_box)
        modal.add_widget(form_scroll)

        # Bottom Action Bar
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(6))

        def _do_save_note(x):
            t_val = in_title.text.strip()
            c_val = in_content.text.strip()
            tag_val = curr_tag[0]
            pin_val = curr_pin[0]

            if not t_val and not c_val:
                self.show_popup("Notice", "Please enter a note title or content.")
                return

            if not t_val:
                t_val = (c_val[:30] + "...") if len(c_val) > 30 else c_val

            notes = load_notes() if 'load_notes' in globals() else []
            now_str = datetime.datetime.now().strftime("%b %d, %I:%M %p")

            if is_edit:
                for n in notes:
                    if n.get("id") == note_id:
                        n["title"] = t_val
                        n["content"] = c_val
                        n["tag"] = tag_val
                        n["is_pinned"] = pin_val
                        n["updated_at"] = now_str
                        break
            else:
                new_n = {
                    "id": note_id,
                    "title": t_val,
                    "content": c_val,
                    "tag": tag_val,
                    "is_pinned": pin_val,
                    "created_at": now_str,
                    "updated_at": now_str
                }
                notes.insert(0, new_n)

            if 'save_notes' in globals():
                save_notes(notes)

            popup.dismiss()
            self.refresh_notes_list()
            self.auto_sync_notes_to_gsheet()
            self.show_popup("Success", f"Note '{t_val}' saved!")

        btn_save = Button(
            text="Save Note",
            font_size='13sp',
            bold=True,
            size_hint_x=0.45,
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1)
        )
        btn_save.bind(on_release=_do_save_note)
        btn_row.add_widget(btn_save)

        btn_copy = Button(
            text="Copy",
            font_size='13sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        def _do_copy(x):
            txt = f"{in_title.text.strip()}\n\n{in_content.text.strip()}"
            if Clipboard is not None:
                try:
                    Clipboard.copy(txt)
                    self.show_popup("Copied", "Note text copied to clipboard!")
                except Exception:
                    pass
        btn_copy.bind(on_release=_do_copy)
        btn_row.add_widget(btn_copy)

        btn_cancel = Button(
            text="Cancel",
            font_size='13sp',
            size_hint_x=0.30,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_cancel)

        modal.add_widget(btn_row)
        popup.content = modal
        popup.open()

    def share_note_dialog(self, note):
        title = note.get("title", "Note")
        tag = note.get("tag", "Work")
        content = note.get("content", "")
        full_text = f"[{tag.upper()}] {title}\n\n{content}".strip()

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.88, 0.52),
            auto_dismiss=True
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # Header
        hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(8))
        lbl_info = Label(
            text=f"Share '[b]{safe_escape_markup(title)}[/b]'",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.86,
            halign='left',
            valign='middle'
        )
        lbl_info.bind(size=lbl_info.setter('text_size'))
        hdr.add_widget(lbl_info)

        btn_x = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_x.bind(on_release=popup.dismiss)
        hdr.add_widget(btn_x)
        modal.add_widget(hdr)

        # Option 1: LAN Team Chat
        btn_lan = Button(
            text="Broadcast to LAN Team Chat",
            font_size='12sp',
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        def _share_lan(x):
            popup.dismiss()
            self.share_note_to_chat(note)
        btn_lan.bind(on_release=_share_lan)
        modal.add_widget(btn_lan)

        # Option 2: Share to Android Apps (WhatsApp, Email, etc.)
        btn_system = Button(
            text="Share to Other Apps (WhatsApp, Mail, etc.)",
            font_size='12sp',
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex("#8b5cf6"),
            color=(1, 1, 1, 1)
        )
        def _share_sys(x):
            popup.dismiss()
            self.share_note_to_system(note)
        btn_system.bind(on_release=_share_sys)
        modal.add_widget(btn_system)

        # Option 3: Save & Sync to Google Sheet
        btn_gs = Button(
            text="Save & Sync to Google Sheet ('Notes')",
            font_size='12sp',
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        def _share_gs(x):
            popup.dismiss()
            if not is_google_sheet_configured():
                self.show_popup("Notice", "Please configure Google Sheet Web App URL in Settings first.")
                return
            def _thread_sgs():
                ok, data, code = sync_google_sheet_notes(notes=load_notes())
                def _res_sgs(dt):
                    if ok:
                        self.show_popup("Google Sheet", f"Note '{title}' saved and synchronized to Google Sheet tab 'Notes'!")
                    else:
                        err = data if isinstance(data, str) else str(data)
                        self.show_popup("Sync Failed", f"Failed to sync with Google Sheet:\n\n{err}")
                Clock.schedule_once(_res_sgs, 0)
            threading.Thread(target=_thread_sgs, daemon=True).start()
        btn_gs.bind(on_release=_share_gs)
        modal.add_widget(btn_gs)

        # Option 4: Copy
        btn_cp = Button(
            text="Copy Note to Clipboard",
            font_size='12sp',
            size_hint_y=None,
            height=dp(36),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        def _do_cp(x):
            popup.dismiss()
            if Clipboard is not None:
                try:
                    Clipboard.copy(full_text)
                except Exception:
                    pass
            self.show_popup("Copied", "Full note copied to clipboard!")
        btn_cp.bind(on_release=_do_cp)
        modal.add_widget(btn_cp)

        popup.content = modal
        popup.open()

    def share_note_to_system(self, note):
        title = note.get("title", "Note")
        tag = note.get("tag", "Work")
        content = note.get("content", "")
        share_body = f"[{tag.upper()}] {title}\n\n{content}".strip()

        if is_android():
            try:
                from jnius import autoclass, cast
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                String = autoclass('java.lang.String')

                send_intent = Intent(Intent.ACTION_SEND)
                send_intent.setType("text/plain")
                send_intent.putExtra(Intent.EXTRA_SUBJECT, cast('java.lang.CharSequence', String(title)))
                send_intent.putExtra(Intent.EXTRA_TEXT, cast('java.lang.CharSequence', String(share_body)))

                chooser = Intent.createChooser(send_intent, cast('java.lang.CharSequence', String("Share Note via...")))
                PythonActivity.mActivity.startActivity(chooser)
                return
            except Exception as e:
                print(f"Android system share error: {e}")

        if Clipboard is not None:
            try:
                Clipboard.copy(share_body)
                self.show_popup("Copied to Clipboard", "Note copied! You can paste it into WhatsApp, Gmail, or Slack.")
            except Exception:
                pass

    def share_note_to_chat(self, note):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat is not initialized.")
            return

        title = note.get("title", "")
        tag = note.get("tag", "Work")
        content = note.get("content", "")

        msg = f"[NOTE] [b]{title}[/b]  ([color=#38bdf8]{tag}[/color])\n{content}"
        try:
            if hasattr(self.chat_engine, "send_chat_message"):
                self.chat_engine.send_chat_message(msg)
            elif hasattr(self.chat_engine, "send_broadcast_message"):
                self.chat_engine.send_broadcast_message(msg)
            self.show_popup("Note Shared", f"Note '{title}' shared with the LAN team!")
        except Exception as e:
            self.show_popup("Error", f"Failed to share note: {e}")

    def toggle_note_pin(self, note_id):
        notes = load_notes() if 'load_notes' in globals() else []
        for n in notes:
            if n.get("id") == note_id:
                n["is_pinned"] = not n.get("is_pinned", False)
                break
        if 'save_notes' in globals():
            save_notes(notes)
        self.refresh_notes_list()
        self.auto_sync_notes_to_gsheet()

    def delete_note_item(self, note_id):
        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.88, 0.38),
            auto_dismiss=True
        )

        modal = RoundedCard(
            bg_hex="#0f172a",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#ef4444",
            orientation='vertical',
            padding=[dp(16), dp(14), dp(16), dp(14)],
            spacing=dp(10)
        )

        lbl_head = Label(
            text="[b]Confirm Deletion[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#ef4444"),
            size_hint_y=None,
            height=dp(28),
            halign='center',
            valign='middle'
        )
        lbl_head.bind(size=lbl_head.setter('text_size'))
        modal.add_widget(lbl_head)

        lbl_body = Label(
            text="Are you sure you want to delete this note?\nThis will remove it from your storage and Google Sheet.",
            font_size='13sp',
            color=get_color_from_hex("#cbd5e1"),
            size_hint=(1, 1),
            halign='center',
            valign='middle'
        )
        lbl_body.bind(size=lbl_body.setter('text_size'))
        modal.add_widget(lbl_body)

        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        
        btn_confirm = Button(
            text="Delete",
            font_size='14sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        def _do_del(x):
            popup.dismiss()
            notes = load_notes() if 'load_notes' in globals() else []
            updated = [n for n in notes if n.get("id") != note_id]
            if 'save_notes' in globals():
                save_notes(updated)
            self.refresh_notes_list()
            self.auto_sync_notes_to_gsheet()
            self.show_popup("Deleted", "Note removed successfully!")

        btn_confirm.bind(on_release=_do_del)
        btn_row.add_widget(btn_confirm)

        btn_cancel = Button(
            text="Cancel",
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_cancel)

        modal.add_widget(btn_row)
        popup.content = modal
        popup.open()

    def auto_sync_notes_to_gsheet(self):
        """Silently synchronizes local notes to Google Sheet tab 'Notes' in background if configured."""
        try:
            settings = load_settings() if 'load_settings' in globals() else {}
            if not is_google_sheet_configured(settings):
                return
            if not settings.get("gsheet_auto_sync", True):
                return

            current_notes = load_notes() if 'load_notes' in globals() else []

            def _bg_sync():
                try:
                    if 'sync_google_sheet_notes' in globals():
                        ok, data, code = sync_google_sheet_notes(notes=current_notes)
                        if ok:
                            print(f"[WorkPulse Notes] Successfully auto-synced {len(current_notes)} notes to Google Sheet.")
                        else:
                            print(f"[WorkPulse Notes] Auto-sync notes response: {data}")
                except Exception as ex:
                    print(f"[WorkPulse Notes] Auto-sync error: {ex}")

            threading.Thread(target=_bg_sync, daemon=True).start()
        except Exception as e:
            print(f"[WorkPulse Notes] Could not dispatch auto-sync: {e}")

    def open_notes_cloud_sync_dialog(self):
        """Opens the Google Sheet synchronization dashboard for WorkPulse Notes."""
        settings = load_settings() if 'load_settings' in globals() else {}
        is_conf = is_google_sheet_configured(settings)

        popup = Popup(
            title="",
            separator_height=0,
            background='',
            background_color=(0, 0, 0, 0.76),
            size_hint=(0.92, 0.60),
            auto_dismiss=False
        )

        modal = RoundedCard(
            bg_hex="#0b132b",
            radius=[dp(16), dp(16), dp(16), dp(16)],
            border_hex="#334155",
            orientation='vertical',
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(8)
        )

        # Title Row
        t_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
        lbl_t = Label(
            text="[b]Google Sheet Cloud Sync (Notes)[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.86,
            halign='left',
            valign='middle'
        )
        lbl_t.bind(size=lbl_t.setter('text_size'))
        t_row.add_widget(lbl_t)

        btn_c = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint_x=None,
            width=dp(34),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_c.bind(on_release=popup.dismiss)
        t_row.add_widget(btn_c)
        modal.add_widget(t_row)

        # Status Banner
        status_txt = "[color=#10b981]Status: Connected to Google Sheet ('Notes' Tab)[/color]" if is_conf else "[color=#f87171]Status: Google Sheet URL not configured[/color]"
        lbl_st = Label(
            text=status_txt,
            markup=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24),
            halign='left'
        )
        lbl_st.bind(size=lbl_st.setter('text_size'))
        modal.add_widget(lbl_st)

        # Push Button
        local_n = load_notes() if 'load_notes' in globals() else []
        btn_push = Button(
            text=f"Push Notes to Google Sheet ({len(local_n)} Notes)",
            font_size='13sp',
            bold=True,
            size_hint_y=None,
            height=dp(42),
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1)
        )
        def _do_push(b):
            if not is_conf:
                self.show_popup("Notice", "Please configure your Google Sheet Web App URL in Settings first.")
                return
            b.text = "Pushing Notes..."
            b.disabled = True
            def _thread_p():
                ok, data, code = sync_google_sheet_notes(notes=load_notes())
                def _done(dt):
                    b.text = f"Push Notes to Google Sheet ({len(load_notes())} Notes)"
                    b.disabled = False
                    if ok:
                        cnt = data.get("updatedRows", len(load_notes())) if isinstance(data, dict) else len(load_notes())
                        self.show_popup("Sync Successful", f"Successfully synced {cnt} notes to Google Sheet tab 'Notes'!")
                    else:
                        err = data if isinstance(data, str) else str(data)
                        self.show_popup("Sync Failed", f"Could not sync notes to Google Sheet:\n\n{err}")
                Clock.schedule_once(_done, 0)
            threading.Thread(target=_thread_p, daemon=True).start()
        btn_push.bind(on_release=_do_push)
        modal.add_widget(btn_push)

        # Fetch Button
        btn_fetch = Button(
            text="Fetch & Merge Notes from Google Sheet",
            font_size='13sp',
            bold=True,
            size_hint_y=None,
            height=dp(42),
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        def _do_fetch(b):
            if not is_conf:
                self.show_popup("Notice", "Please configure your Google Sheet Web App URL in Settings first.")
                return
            b.text = "Fetching Notes..."
            b.disabled = True
            def _thread_f():
                ok, fetched_list, msg = fetch_google_sheet_notes()
                def _done_f(dt):
                    b.text = "Fetch & Merge Notes from Google Sheet"
                    b.disabled = False
                    if ok and fetched_list:
                        cur_list = load_notes() if 'load_notes' in globals() else []
                        id_map = {n.get("id"): idx for idx, n in enumerate(cur_list)}
                        added = 0
                        updated = 0
                        for fn in fetched_list:
                            if fn.get("id") in id_map:
                                cur_list[id_map[fn.get("id")]] = fn
                                updated += 1
                            else:
                                cur_list.append(fn)
                                added += 1
                        if 'save_notes' in globals():
                            save_notes(cur_list)
                        self.refresh_notes_list()
                        btn_push.text = f"Push Notes to Google Sheet ({len(cur_list)} Notes)"
                        self.show_popup("Fetch Complete", f"Successfully synced from Google Sheet:\n- {added} new notes added\n- {updated} notes updated")
                    elif ok:
                        self.show_popup("Notice", "Connected to Google Sheet, but no notes were found in tab 'Notes'.")
                    else:
                        self.show_popup("Fetch Failed", f"Could not fetch notes:\n\n{msg}")
                Clock.schedule_once(_done_f, 0)
            threading.Thread(target=_thread_f, daemon=True).start()
        btn_fetch.bind(on_release=_do_fetch)
        modal.add_widget(btn_fetch)

        # Auto-Sync on Save Toggle
        auto_val = [settings.get("gsheet_auto_sync", True)]
        btn_auto = Button(
            text=f"Auto-Sync on Note Save: {'ON' if auto_val[0] else 'OFF'}",
            font_size='12sp',
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex("#059669" if auto_val[0] else "#475569"),
            color=(1, 1, 1, 1)
        )
        def _toggle_auto(b):
            auto_val[0] = not auto_val[0]
            settings["gsheet_auto_sync"] = auto_val[0]
            if 'save_settings' in globals():
                save_settings(settings)
            b.text = f"Auto-Sync on Note Save: {'ON' if auto_val[0] else 'OFF'}"
            b.background_color = get_color_from_hex("#059669" if auto_val[0] else "#475569")
        btn_auto.bind(on_release=_toggle_auto)
        modal.add_widget(btn_auto)

        # Open Settings Button (if needed)
        if not is_conf:
            btn_cfg = Button(
                text="Configure Sheet URL in Settings",
                font_size='11sp',
                size_hint_y=None,
                height=dp(34),
                background_normal='',
                background_color=get_color_from_hex("#7c3aed"),
                color=(1, 1, 1, 1)
            )
            def _open_cfg(b):
                popup.dismiss()
                self.open_settings_popup()
            btn_cfg.bind(on_release=_open_cfg)
            modal.add_widget(btn_cfg)

        popup.content = modal
        popup.open()

    # =========================================================================
    # TAB 4: LAN TEAM CHAT VIEW
    # =========================================================================
    def build_chat_view(self):
        container = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # 1. Chat Header Context Bar
        self.chat_top_bar = RoundedCard(
            bg_hex="#131e33",
            radius=[dp(8), dp(8), dp(8), dp(8)],
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            padding=[dp(8), dp(4), dp(8), dp(4)],
            spacing=dp(6)
        )

        # Back to Public Button (only visible in DM mode)
        self.btn_dm_back = Button(
            text="< Public",
            font_size='11sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(0), dp(34)),
            opacity=0,
            disabled=True,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        self.btn_dm_back.bind(on_release=lambda x: self.switch_to_dm(None))
        self.chat_top_bar.add_widget(self.btn_dm_back)

        # Channel info column (Title + Subtitle)
        chan_col = BoxLayout(orientation='vertical', size_hint_x=1, spacing=dp(1))
        self.lbl_channel_title = Label(
            text="[b]# Public Team Room[/b]",
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_y=None,
            height=dp(18),
            halign='left',
            valign='middle'
        )
        self.lbl_channel_title.bind(size=self.lbl_channel_title.setter('text_size'))
        chan_col.add_widget(self.lbl_channel_title)

        self.lbl_chat_status = Label(
            text="Connecting to LAN...",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_y=None,
            height=dp(16),
            halign='left',
            valign='middle'
        )
        self.lbl_chat_status.bind(size=self.lbl_chat_status.setter('text_size'))
        chan_col.add_widget(self.lbl_chat_status)
        self.chat_top_bar.add_widget(chan_col)

        # Quick action: Send File button
        btn_top_file = Button(
            text="+ File",
            font_size='11sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(58), dp(34)),
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        btn_top_file.bind(on_release=self.open_file_picker_popup)
        self.chat_top_bar.add_widget(btn_top_file)

        # Quick action: Online Team Members button
        self.btn_team_ctrl = Button(
            text="Team (0)",
            font_size='11sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(68), dp(34)),
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        self.btn_team_ctrl.bind(on_release=self.open_online_team_popup)
        self.chat_top_bar.add_widget(self.btn_team_ctrl)

        container.add_widget(self.chat_top_bar)

        # 2. Horizontal Colleague & Quick-Action Ribbon
        self.team_strip_scroll = ScrollView(size_hint_y=None, height=dp(38), do_scroll_x=True, do_scroll_y=False)
        self.team_strip_layout = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(38), spacing=dp(6), padding=[dp(8), dp(3), dp(8), dp(3)])
        self.team_strip_layout.bind(minimum_width=self.team_strip_layout.setter('width'))
        self.team_strip_scroll.add_widget(self.team_strip_layout)
        container.add_widget(self.team_strip_scroll)

        # 3. Chat Message Stream ScrollView
        self.chat_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.chat_list_layout = GridLayout(cols=1, spacing=dp(10), padding=[dp(8), dp(8), dp(8), dp(8)], size_hint_y=None)
        self.chat_list_layout.bind(minimum_height=self.chat_list_layout.setter('height'))
        self.chat_scroll.add_widget(self.chat_list_layout)
        container.add_widget(self.chat_scroll)

        # 4. Chat Input Bottom Bar (with soft-keyboard lift support)
        self.chat_input_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(54), padding=[dp(6), dp(4), dp(6), dp(6)], spacing=dp(6))
        
        btn_attach = Button(
            text="+ File",
            font_size='12sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_attach.bind(on_release=self.open_file_picker_popup)
        self.chat_input_bar.add_widget(btn_attach)

        self.in_chat_msg = TextInput(
            hint_text="Type a message to team...",
            multiline=False,
            font_size='15sp',
            size_hint_x=0.64,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(12), dp(12)]
        )
        self.in_chat_msg.bind(on_text_validate=self.send_chat_message)
        self.in_chat_msg.bind(focus=self._on_chat_input_focus)
        self.chat_input_bar.add_widget(self.in_chat_msg)

        btn_send = Button(
            text="Send",
            font_size='15sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_send.bind(on_release=self.send_chat_message)
        self.chat_input_bar.add_widget(btn_send)

        container.add_widget(self.chat_input_bar)
        return container

    def init_lan_chat_engine(self):
        if not LANChatEngine:
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = "LAN Chat unavailable"
            return

        settings = getattr(self, 'settings', None) or (load_settings() if 'load_settings' in globals() else {})
        user_name = settings.get("user_name", "Developer")
        device_id = get_or_create_device_id()
        user_id = get_persistent_user_id(user_name)
        try:
            self.chat_engine = LANChatEngine(
                user_name=user_name,
                user_id=user_id,
                device_id=device_id,
                on_message=self._on_lan_message_received,
                on_peers_change=self._on_lan_peers_changed
            )
            self.chat_engine.start()
            self._update_network_status_labels()
        except Exception as e:
            print(f"Error starting LAN Chat Engine on mobile: {e}")
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = f"LAN Init Error: {e}"

    def rescan_lan_network(self, *args):
        if self.chat_engine:
            try:
                self.chat_engine.stop()
            except Exception:
                pass
            self.chat_engine = None
        self.init_lan_chat_engine()
        self.show_popup("Network Refreshed", "Rescanned local Wi-Fi interfaces and sent discovery beacon.")

    def _on_lan_message_received(self, msg_dict):
        if KIVY_AVAILABLE and Clock:
            Clock.schedule_once(lambda dt: self._handle_new_incoming_message(msg_dict), 0)

    def _on_lan_peers_changed(self, peers_dict):
        if KIVY_AVAILABLE and Clock:
            Clock.schedule_once(lambda dt: self._update_network_status_labels(), 0)

    def _handle_new_incoming_message(self, msg_dict):
        r_id = msg_dict.get("recipient_id", "")
        s_id = msg_dict.get("sender_id", "")
        r_name = (msg_dict.get("recipient_name") or "").strip().lower()
        s_name = (msg_dict.get("user_name") or "").strip().lower()

        my_id = self.chat_engine.user_id if self.chat_engine else ""
        my_dev = getattr(self.chat_engine, "device_id", "") if self.chat_engine else ""
        my_name = (self.chat_engine.user_name if self.chat_engine else "").strip().lower()

        is_relevant = False
        if self.active_dm_peer:
            target_id = self.active_dm_peer.get("id", "")
            target_dev = self.active_dm_peer.get("device_id", "")
            target_name = (self.active_dm_peer.get("user_name") or "").strip().lower()

            if (r_id == target_id and s_id == my_id) or (r_id == my_id and s_id == target_id):
                is_relevant = True
            elif target_dev and ((r_id.endswith(target_dev) and s_id == my_id) or (s_id.endswith(target_dev) and r_id == my_id)):
                is_relevant = True
            elif target_name and ((s_name == target_name and (r_name == my_name or not r_name)) or (s_name == my_name and r_name == target_name)):
                is_relevant = True
        else:
            if not r_id:
                is_relevant = True

        if is_relevant:
            if self.current_tab != "chat":
                self.unread_chat_count += 1
                self.btn_tab_chat.text = f"Chat [{self.unread_chat_count}]"
            else:
                self.add_message_bubble(msg_dict)
                Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

    def switch_to_dm(self, peer=None):
        """Switches between Public Team Room and 1-on-1 Private Direct Message."""
        self.active_dm_peer = peer
        if peer:
            p_name = peer.get('user_name', 'Colleague')
            p_ip = peer.get('ip', '')
            if hasattr(self, 'lbl_channel_title'):
                self.lbl_channel_title.text = f"[b]{safe_escape_markup(p_name)}[/b]"
            if hasattr(self, 'lbl_chat_status'):
                self.lbl_chat_status.text = f"[color=#34d399]Online[/color] | {p_ip}"
            if hasattr(self, 'btn_dm_back'):
                self.btn_dm_back.width = dp(68)
                self.btn_dm_back.opacity = 1
                self.btn_dm_back.disabled = False
            if hasattr(self, 'in_chat_msg') and self.in_chat_msg:
                self.in_chat_msg.hint_text = f"Message {p_name} (Private)..."
        else:
            if hasattr(self, 'lbl_channel_title'):
                self.lbl_channel_title.text = "[b]# Public Team Room[/b]"
            if hasattr(self, 'btn_dm_back'):
                self.btn_dm_back.width = dp(0)
                self.btn_dm_back.opacity = 0
                self.btn_dm_back.disabled = True
            if hasattr(self, 'in_chat_msg') and self.in_chat_msg:
                self.in_chat_msg.hint_text = "Type a message to team..."

        self._update_network_status_labels()
        self.refresh_chat_messages_ui()

    def _update_network_status_labels(self):
        if not self.chat_engine:
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = "Offline"
            if hasattr(self, 'btn_online_chip') and self.btn_online_chip:
                self.btn_online_chip.text = "Offline"
            return

        ip = self.chat_engine.local_ip
        peer_cnt = len(self.chat_engine.peers)

        if not self.active_dm_peer:
            peer_txt = f"{peer_cnt} Online" if peer_cnt > 0 else "0 Online"
            if hasattr(self, 'lbl_channel_title'):
                self.lbl_channel_title.text = "[b]# Public Team Room[/b]"
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = f"[color=#34d399]*[/color] {peer_txt} | IP: {ip}"
        else:
            p_name = self.active_dm_peer.get('user_name', 'Colleague')
            p_ip = self.active_dm_peer.get('ip', '')
            if hasattr(self, 'lbl_channel_title'):
                self.lbl_channel_title.text = f"[b]{safe_escape_markup(p_name)}[/b]"
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = f"[color=#34d399]Online[/color] | {p_ip}"

        chip_txt = f"{peer_cnt} Online" if peer_cnt > 0 else f"{ip}"
        if hasattr(self, 'btn_online_chip') and self.btn_online_chip:
            self.btn_online_chip.text = chip_txt

        if hasattr(self, 'btn_team_ctrl') and self.btn_team_ctrl:
            self.btn_team_ctrl.text = f"Team ({peer_cnt})"

        # Rebuild Active Team Strip (Peers + Quick Action Chips in horizontal ribbon)
        if hasattr(self, 'team_strip_layout') and self.team_strip_layout:
            self.team_strip_layout.clear_widgets()

            b_all = Button(
                text="# Public Room",
                font_size='11sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(96), dp(32)),
                background_normal='',
                background_color=get_color_from_hex("#2563eb" if self.active_dm_peer is None else "#1e293b"),
                color=(1, 1, 1, 1)
            )
            b_all.bind(on_release=lambda x: self.switch_to_dm(None))
            self.team_strip_layout.add_widget(b_all)

            # Online peers
            rendered_contact_names = set()
            for peer in self.chat_engine.peers.values():
                p_name = peer.get("user_name", "Peer")
                p_id = peer.get("id")
                p_dev = peer.get("device_id", p_id)
                rendered_contact_names.add(p_name.strip().lower())
                is_active = bool(self.active_dm_peer and (
                    self.active_dm_peer.get("id") == p_id or
                    (p_dev and self.active_dm_peer.get("device_id") == p_dev) or
                    self.active_dm_peer.get("user_name", "").lower() == p_name.lower()
                ))
                b_peer = Button(
                    text=f"[b]{p_name}[/b]",
                    markup=True,
                    font_size='11sp',
                    size_hint=(None, None),
                    size=(dp(max(90, len(p_name)*8 + 36)), dp(32)),
                    background_normal='',
                    background_color=get_color_from_hex("#059669" if is_active else "#1e293b"),
                    color=get_color_from_hex("#ffffff" if is_active else "#34d399")
                )
                b_peer.bind(on_release=lambda x, p=peer: self.switch_to_dm(p))
                self.team_strip_layout.add_widget(b_peer)

            # Known contacts from previous chat history who might be offline
            my_n = (self.chat_engine.user_name if self.chat_engine else "").strip().lower()
            known_contacts = {}
            for m in reversed(self.chat_engine.messages):
                rn = (m.get("recipient_name") or "").strip()
                rid = m.get("recipient_id") or ""
                sn = (m.get("user_name") or "").strip()
                sid = m.get("sender_id") or ""
                sdev = m.get("device_id", sid)
                
                if rid and rn and sn:
                    if sn.lower() == my_n and rn.lower() != my_n:
                        if rn.lower() not in known_contacts:
                            known_contacts[rn.lower()] = {"id": rid, "device_id": sdev, "user_name": rn, "ip": m.get("file_ip", "")}
                    elif rn.lower() == my_n and sn.lower() != my_n:
                        if sn.lower() not in known_contacts:
                            known_contacts[sn.lower()] = {"id": sid, "device_id": sdev, "user_name": sn, "ip": m.get("file_ip", "")}

            for kn_lower, kn_peer in known_contacts.items():
                if kn_lower in rendered_contact_names:
                    continue
                kn_name = kn_peer.get("user_name", "Peer")
                is_active = bool(self.active_dm_peer and (
                    self.active_dm_peer.get("id") == kn_peer.get("id") or
                    self.active_dm_peer.get("user_name", "").lower() == kn_name.lower()
                ))
                b_kn = Button(
                    text=f"{kn_name} (Off)",
                    font_size='11sp',
                    bold=True,
                    size_hint=(None, None),
                    size=(dp(max(100, len(kn_name)*8 + 48)), dp(32)),
                    background_normal='',
                    background_color=get_color_from_hex("#059669" if is_active else "#334155"),
                    color=get_color_from_hex("#ffffff" if is_active else "#94a3b8")
                )
                b_kn.bind(on_release=lambda x, p=kn_peer: self.switch_to_dm(p))
                self.team_strip_layout.add_widget(b_kn)

            # Quick Action Chips in ribbon
            b_tasks = Button(
                text="Tasks",
                font_size='11sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(64), dp(32)),
                background_normal='',
                background_color=get_color_from_hex("#8b5cf6"),
                color=(1, 1, 1, 1)
            )
            b_tasks.bind(on_release=self.share_today_tasks_to_chat)
            self.team_strip_layout.add_widget(b_tasks)

            b_add_ip = Button(
                text="+ IP",
                font_size='11sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(54), dp(32)),
                background_normal='',
                background_color=get_color_from_hex("#334155"),
                color=(1, 1, 1, 1)
            )
            b_add_ip.bind(on_release=self.open_custom_ip_popup)
            self.team_strip_layout.add_widget(b_add_ip)

            b_rescan = Button(
                text="Rescan",
                font_size='11sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(68), dp(32)),
                background_normal='',
                background_color=get_color_from_hex("#0284c7"),
                color=(1, 1, 1, 1)
            )
            b_rescan.bind(on_release=self.rescan_lan_network)
            self.team_strip_layout.add_widget(b_rescan)

    def open_online_team_popup(self, *args):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat is not initialized.")
            return

        peers = list(self.chat_engine.peers.values())
        my_name = self.chat_engine.user_name
        my_ip = self.chat_engine.local_ip
        count = len(peers)

        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        lbl_head = Label(
            text=f"[b]Online Team Members ({count} Online)[/b]",
            markup=True,
            font_size='15sp',
            size_hint_y=None,
            height=dp(26),
            color=get_color_from_hex("#38bdf8")
        )
        content.add_widget(lbl_head)

        # Your device card
        my_card = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), padding=[dp(8), dp(4), dp(8), dp(4)], spacing=dp(8))
        lbl_my_avatar = Button(
            text="YOU",
            font_size='11sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1),
            disabled=True,
            disabled_color=(1, 1, 1, 1)
        )
        my_card.add_widget(lbl_my_avatar)

        my_info = BoxLayout(orientation='vertical', size_hint_x=1, spacing=dp(1))
        lbl_my_name = Label(
            text=f"[b]{safe_escape_markup(my_name)} (You)[/b]",
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_y=None,
            height=dp(18),
            halign='left',
            valign='middle'
        )
        lbl_my_name.bind(size=lbl_my_name.setter('text_size'))
        my_info.add_widget(lbl_my_name)

        lbl_my_sub = Label(
            text=f"IP: {my_ip} | [color=#34d399]Host / Online[/color]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex("#94a3b8"),
            size_hint_y=None,
            height=dp(16),
            halign='left',
            valign='middle'
        )
        lbl_my_sub.bind(size=lbl_my_sub.setter('text_size'))
        my_info.add_widget(lbl_my_sub)
        my_card.add_widget(my_info)
        content.add_widget(my_card)

        # Scrollable Peers List
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        peers_layout = GridLayout(cols=1, spacing=dp(8), padding=[dp(4), dp(4)], size_hint_y=None)
        peers_layout.bind(minimum_height=peers_layout.setter('height'))

        popup = Popup(title="LAN Team Members", content=content, size_hint=(0.95, 0.85))

        if not peers:
            lbl_empty = Label(
                text="No colleagues found on this Wi-Fi network yet.\n\nTips:\n- Ensure phones/PCs are connected to same Wi-Fi or Hotspot.\n- Check firewall or tap '+ Add IP' if on another subnet.\n- Tap 'Rescan' to broadcast discovery beacon.",
                font_size='12sp',
                color=get_color_from_hex("#94a3b8"),
                size_hint_y=None,
                height=dp(110),
                halign='center'
            )
            peers_layout.add_widget(lbl_empty)
        else:
            for peer in peers:
                p_name = peer.get("user_name", "Colleague")
                p_ip = peer.get("ip", "")
                p_host = peer.get("hostname", "Device")
                p_color = peer.get("avatar_color", "#059669")
                initials = get_initials(p_name) if 'get_initials' in globals() else p_name[:2].upper()

                card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(84), padding=[dp(8), dp(6), dp(8), dp(6)], spacing=dp(6))

                row_top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(8))
                
                av_btn = Button(
                    text=f"[b]{initials}[/b]",
                    markup=True,
                    font_size='12sp',
                    bold=True,
                    size_hint=(None, None),
                    size=(dp(34), dp(34)),
                    background_normal='',
                    background_color=get_color_from_hex(p_color if (isinstance(p_color, str) and p_color.startswith('#')) else "#059669"),
                    color=(1, 1, 1, 1),
                    disabled=True,
                    disabled_color=(1, 1, 1, 1)
                )
                row_top.add_widget(av_btn)

                p_info = BoxLayout(orientation='vertical', size_hint_x=1, spacing=dp(1))
                lbl_pn = Label(
                    text=f"[b]{safe_escape_markup(p_name)}[/b]",
                    markup=True,
                    font_size='13sp',
                    color=get_color_from_hex("#f8fafc"),
                    size_hint_y=None,
                    height=dp(18),
                    halign='left',
                    valign='middle'
                )
                lbl_pn.bind(size=lbl_pn.setter('text_size'))
                p_info.add_widget(lbl_pn)

                lbl_ps = Label(
                    text=f"IP: {p_ip} | [color=#34d399]Online[/color] ({p_host})",
                    markup=True,
                    font_size='11sp',
                    color=get_color_from_hex("#94a3b8"),
                    size_hint_y=None,
                    height=dp(16),
                    halign='left',
                    valign='middle'
                )
                lbl_ps.bind(size=lbl_ps.setter('text_size'))
                p_info.add_widget(lbl_ps)
                row_top.add_widget(p_info)
                card.add_widget(row_top)

                btn_actions = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(6))
                
                btn_dm = Button(
                    text="Private DM",
                    font_size='11sp',
                    bold=True,
                    size_hint_x=0.5,
                    background_normal='',
                    background_color=get_color_from_hex("#2563eb"),
                    color=(1, 1, 1, 1)
                )
                def _do_dm(x, target_peer=peer):
                    popup.dismiss()
                    self.switch_to_dm(target_peer)
                btn_dm.bind(on_release=_do_dm)
                btn_actions.add_widget(btn_dm)

                btn_send_p = Button(
                    text="Send File",
                    font_size='11sp',
                    bold=True,
                    size_hint_x=0.5,
                    background_normal='',
                    background_color=get_color_from_hex("#059669"),
                    color=(1, 1, 1, 1)
                )
                def _do_send_to_peer(x, target_peer=peer):
                    popup.dismiss()
                    self.switch_to_dm(target_peer)
                    self.open_file_picker_popup()
                btn_send_p.bind(on_release=_do_send_to_peer)
                btn_actions.add_widget(btn_send_p)

                card.add_widget(btn_actions)
                peers_layout.add_widget(card)

        scroll.add_widget(peers_layout)
        content.add_widget(scroll)

        # Bottom Controls
        bottom_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        btn_add = Button(
            text="+ Add IP",
            font_size='12sp',
            bold=True,
            size_hint_x=0.35,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        def _go_add_ip(x):
            popup.dismiss()
            self.open_custom_ip_popup()
        btn_add.bind(on_release=_go_add_ip)
        bottom_bar.add_widget(btn_add)

        btn_res = Button(
            text="Rescan",
            font_size='12sp',
            bold=True,
            size_hint_x=0.35,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        def _go_rescan(x):
            popup.dismiss()
            self.rescan_lan_network()
        btn_res.bind(on_release=_go_rescan)
        bottom_bar.add_widget(btn_res)

        btn_close = Button(
            text="Close",
            font_size='12sp',
            size_hint_x=0.3,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_close.bind(on_release=popup.dismiss)
        bottom_bar.add_widget(btn_close)

        content.add_widget(bottom_bar)
        popup.open()

    def refresh_chat_messages_ui(self):
        if not self.chat_engine:
            return
        self.chat_list_layout.clear_widgets()
        self.rendered_msg_ids.clear()

        filtered_msgs = []
        if self.active_dm_peer:
            peer_id = self.active_dm_peer.get("id", "")
            peer_dev = self.active_dm_peer.get("device_id", "")
            peer_name = (self.active_dm_peer.get("user_name") or "").strip().lower()
            my_id = self.chat_engine.user_id if self.chat_engine else ""
            my_dev = getattr(self.chat_engine, "device_id", "") if self.chat_engine else ""
            my_name = (self.chat_engine.user_name if self.chat_engine else "").strip().lower()

            for msg in self.chat_engine.messages:
                r_id = msg.get("recipient_id", "")
                s_id = msg.get("sender_id", "")
                r_name = (msg.get("recipient_name") or "").strip().lower()
                s_name = (msg.get("user_name") or "").strip().lower()
                is_me_msg = bool(msg.get("is_me") or (my_id and s_id == my_id) or (my_name and s_name == my_name))

                # Check if this message belongs to this DM
                if (r_id and (r_id == peer_id or (peer_dev and r_id.endswith(peer_dev)))) and (s_id == my_id or is_me_msg):
                    filtered_msgs.append(msg)
                elif (s_id and (s_id == peer_id or (peer_dev and s_id.endswith(peer_dev)))) and (r_id == my_id or not r_id or r_name == my_name):
                    filtered_msgs.append(msg)
                elif r_name and peer_name and (
                    (is_me_msg and r_name == peer_name) or
                    ((not is_me_msg) and s_name == peer_name and (r_name == my_name or not r_name))
                ):
                    filtered_msgs.append(msg)
        else:
            for msg in self.chat_engine.messages:
                if not msg.get("recipient_id"):
                    filtered_msgs.append(msg)

        for msg in filtered_msgs[-60:]:
            self.add_message_bubble(msg)

    def get_file_type_badge(self, filename):
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        if ext in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.webm', '.flv'):
            return {"label": "VIDEO", "color": "#8b5cf6", "icon_txt": "VID"}
        elif ext in ('.mp3', '.wav', '.m4a', '.ogg', '.opus', '.flac', '.aac'):
            return {"label": "AUDIO", "color": "#06b6d4", "icon_txt": "AUD"}
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
            return {"label": "IMAGE", "color": "#f59e0b", "icon_txt": "IMG"}
        elif ext in ('.pdf',):
            return {"label": "PDF", "color": "#ef4444", "icon_txt": "PDF"}
        elif ext in ('.xls', '.xlsx', '.csv'):
            return {"label": "EXCEL", "color": "#10b981", "icon_txt": "XLS"}
        elif ext in ('.doc', '.docx', '.txt', '.rtf', '.odt', '.md'):
            return {"label": "DOC", "color": "#2563eb", "icon_txt": "DOC"}
        elif ext in ('.zip', '.rar', '.7z', '.tar', '.gz'):
            return {"label": "ZIP", "color": "#6366f1", "icon_txt": "ZIP"}
        elif ext in ('.apk',):
            return {"label": "APK", "color": "#14b8a6", "icon_txt": "APK"}
        elif ext in ('.py', '.js', '.json', '.xml', '.html', '.css', '.sh', '.c', '.cpp'):
            return {"label": "CODE", "color": "#38bdf8", "icon_txt": "CODE"}
        return {"label": "FILE", "color": "#64748b", "icon_txt": "FILE"}

    def add_message_bubble(self, msg):
        msg_id = msg.get("id")
        if msg_id:
            if msg_id in self.rendered_msg_ids:
                return
            self.rendered_msg_ids.add(msg_id)

        my_id = self.chat_engine.user_id if self.chat_engine else ""
        my_name = (self.chat_engine.user_name if self.chat_engine else "").strip().lower()
        msg_sender = (msg.get("user_name") or "").strip().lower()
        msg_sid = msg.get("sender_id", "")

        is_me = bool(
            msg.get("is_me", False) or
            (my_id and msg_sid == my_id) or
            (my_name and msg_sender == my_name and not msg.get("recipient_id")) or
            (my_name and msg_sender == my_name and msg.get("recipient_id") and msg.get("recipient_name", "").strip().lower() != my_name)
        )
        msg_type = msg.get("type", "text")
        sender = safe_escape_markup(msg.get("user_name", "Anonymous"))
        time_s = safe_escape_markup(msg.get("time_str", ""))

        row = BoxLayout(orientation='horizontal', size_hint_y=None, spacing=dp(4), padding=[dp(4), dp(2), dp(4), dp(2)])

        bubble_bg = "#1e3a8a" if is_me else "#1e293b"
        bubble_radius = [dp(14), dp(14), dp(3), dp(14)] if is_me else [dp(14), dp(14), dp(14), dp(3)]

        bubble = RoundedCard(
            bg_hex=bubble_bg,
            radius=bubble_radius,
            orientation='vertical',
            size_hint_x=0.85,
            size_hint_y=None,
            padding=[dp(10), dp(8), dp(10), dp(8)],
            spacing=dp(4)
        )

        # Header Row: Sender Name on left, Timestamp on right
        header_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(18), spacing=dp(4))
        sender_color = "#93c5fd" if is_me else "#38bdf8"
        lbl_sender = Label(
            text=f"[b]{'You' if is_me else sender}[/b]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex(sender_color),
            size_hint_x=0.65,
            halign='left',
            valign='middle'
        )
        lbl_sender.bind(size=lbl_sender.setter('text_size'))
        header_row.add_widget(lbl_sender)

        lbl_time = Label(
            text=time_s,
            font_size='10sp',
            color=get_color_from_hex("#94a3b8"),
            size_hint_x=0.35,
            halign='right',
            valign='middle'
        )
        lbl_time.bind(size=lbl_time.setter('text_size'))
        header_row.add_widget(lbl_time)
        bubble.add_widget(header_row)

        if msg_type == "work_update":
            title = safe_escape_markup(msg.get("title", "Daily Work Update"))
            tasks = msg.get("tasks", [])
            task_lines = "\n".join([f"- {safe_escape_markup(t.get('title', ''))} ({safe_escape_markup(t.get('hours', ''))}h)" for t in tasks[:4]])

            card = RoundedCard(
                bg_hex="#0b1120",
                radius=[dp(8), dp(8), dp(8), dp(8)],
                orientation='vertical',
                size_hint_y=None,
                spacing=dp(4),
                padding=[dp(8), dp(6), dp(8), dp(6)]
            )
            lbl_w_title = Label(
                text=f"[b]{title}[/b]",
                markup=True,
                font_size='12sp',
                color=get_color_from_hex("#38bdf8"),
                size_hint_y=None,
                height=dp(18),
                halign='left',
                valign='middle'
            )
            lbl_w_title.bind(size=lbl_w_title.setter('text_size'))
            card.add_widget(lbl_w_title)

            lbl_tasks = Label(
                text=task_lines or "- No task details provided",
                font_size='12sp',
                color=get_color_from_hex("#e2e8f0"),
                size_hint_y=None,
                height=dp(max(24, len(tasks[:4]) * 18)),
                halign='left',
                valign='middle'
            )
            lbl_tasks.bind(size=lbl_tasks.setter('text_size'))
            card.add_widget(lbl_tasks)

            card_h = dp(18) + lbl_tasks.height + dp(12)
            card.height = card_h
            bubble.add_widget(card)

            bubble.height = header_row.height + card_h + dp(16)
            row.height = bubble.height + dp(4)

        elif msg_type == "file":
            fn = msg.get("file_name", "Shared File")
            fn_safe = safe_escape_markup(fn)
            fs_str = safe_escape_markup(msg.get("file_size_str") or format_file_size(msg.get("file_size", 0)))
            caption = safe_escape_markup(msg.get("caption", "").strip())
            file_id = msg.get("file_id", "")
            is_image = msg.get("is_image", False) or (is_image_file(fn) if 'is_image_file' in globals() else False)

            local_p = self.get_file_local_path(msg)
            has_local = bool(local_p and os.path.isfile(local_p))

            card = RoundedCard(
                bg_hex="#0b1120",
                radius=[dp(8), dp(8), dp(8), dp(8)],
                orientation='vertical',
                size_hint_y=None,
                spacing=dp(6),
                padding=[dp(8), dp(6), dp(8), dp(6)]
            )

            top_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(8))
            badge_info = self.get_file_type_badge(fn)
            lbl_badge = Button(
                text=f"[b]{badge_info['icon_txt']}[/b]",
                markup=True,
                font_size='10sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(40), dp(36)),
                background_normal='',
                background_color=get_color_from_hex(badge_info['color']),
                color=(1, 1, 1, 1),
                disabled=True,
                disabled_color=(1, 1, 1, 1)
            )
            top_box.add_widget(lbl_badge)

            info_col = BoxLayout(orientation='vertical', size_hint_x=1, spacing=dp(1))
            lbl_name = Label(
                text=f"[b]{fn_safe}[/b]",
                markup=True,
                font_size='13sp',
                color=get_color_from_hex("#f8fafc"),
                size_hint_y=None,
                height=dp(18),
                halign='left',
                valign='middle',
                shorten=True,
                shorten_from='right'
            )
            lbl_name.bind(size=lbl_name.setter('text_size'))
            info_col.add_widget(lbl_name)

            sub_txt = f"{fs_str} | Shared by you" if is_me else f"{fs_str} | LAN Transfer"
            if has_local:
                sub_txt = f"[color=#10b981][b]SAVED[/b][/color]  [color=#94a3b8]{fs_str}[/color]"
            lbl_meta = Label(
                text=sub_txt,
                markup=True,
                font_size='11sp',
                color=get_color_from_hex("#94a3b8"),
                size_hint_y=None,
                height=dp(16),
                halign='left',
                valign='middle'
            )
            lbl_meta.bind(size=lbl_meta.setter('text_size'))
            info_col.add_widget(lbl_meta)
            top_box.add_widget(info_col)
            card.add_widget(top_box)

            if caption:
                lbl_cap = Label(
                    text=f"[i]{caption}[/i]",
                    markup=True,
                    font_size='11sp',
                    color=get_color_from_hex("#cbd5e1"),
                    size_hint_y=None,
                    height=dp(18),
                    halign='left',
                    valign='middle'
                )
                lbl_cap.bind(size=lbl_cap.setter('text_size'))
                card.add_widget(lbl_cap)

            if is_image and has_local and Image is not None and Image is not object:
                try:
                    img_w = Image(source=local_p, size_hint_y=None, height=dp(140), allow_stretch=True, keep_ratio=True)
                    card.add_widget(img_w)
                except Exception:
                    pass

            # Buttons Row - Dual buttons side-by-side
            btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(6))
            ext_l = os.path.splitext(fn)[1].lower()
            is_video = ext_l in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.webm', '.ts', '.m4v')
            is_audio = ext_l in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.opus')
            is_img = ext_l in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')

            if is_video:
                view_txt = "PLAY VIDEO"
            elif is_audio:
                view_txt = "PLAY AUDIO"
            elif is_img:
                view_txt = "VIEW IMAGE"
            else:
                view_txt = "OPEN / VIEW"

            btn_view = Button(
                text=view_txt,
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#8b5cf6" if is_video or is_audio else "#0284c7"),
                color=(1, 1, 1, 1)
            )
            btn_dl = Button(
                text="DOWNLOAD" if not has_local else "RE-DOWNLOAD",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#059669"),
                color=(1, 1, 1, 1)
            )

            def _start_view(btn_inst, m=msg, r=btn_row, meta=lbl_meta):
                self.stream_or_play_file(m, btn_row=r, meta_lbl=meta)

            def _start_download(btn_inst, m=msg, r=btn_row, meta=lbl_meta):
                btn_dl.disabled = True
                btn_dl.text = "Downloading..."
                self.download_and_handle_file(m, is_preview=False, on_complete_open=False, btn_row=r, meta_lbl=meta)

            btn_view.bind(on_release=_start_view)
            btn_dl.bind(on_release=_start_download)
            btn_row.add_widget(btn_view)
            btn_row.add_widget(btn_dl)
            card.add_widget(btn_row)

            c_height = dp(38) + dp(38) + dp(14)
            if caption:
                c_height += dp(20)
            if is_image and has_local and Image is not None and Image is not object:
                c_height += dp(146)
            card.height = c_height
            bubble.add_widget(card)

            bubble.height = header_row.height + c_height + dp(16)
            row.height = bubble.height + dp(4)

        else:
            body_text = msg.get("text", "")
            content_lbl = Label(
                text=body_text,
                font_size='14sp',
                color=get_color_from_hex("#f8fafc"),
                size_hint_y=None,
                halign='left',
                valign='top'
            )
            def _bind_txt(lbl, *args):
                lbl.text_size = (lbl.width, None)
                lbl.texture_update()
                lbl.height = max(dp(22), lbl.texture_size[1] + dp(4))
                bubble.height = header_row.height + lbl.height + dp(14)
                row.height = bubble.height + dp(4)
            content_lbl.bind(width=_bind_txt)
            content_lbl.height = dp(24)
            bubble.add_widget(content_lbl)

            bubble.height = header_row.height + content_lbl.height + dp(14)
            row.height = bubble.height + dp(4)

        if is_me:
            row.add_widget(Widget(size_hint_x=0.15))
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            row.add_widget(Widget(size_hint_x=0.15))

        self.chat_list_layout.add_widget(row)

    def scroll_chat_to_bottom(self):
        if hasattr(self, 'chat_scroll') and self.chat_scroll:
            self.chat_scroll.scroll_y = 0

    def send_chat_message(self, *args):
        text = self.in_chat_msg.text.strip()
        if not text:
            return
        if self.chat_engine:
            r_id = self.active_dm_peer.get("id", "") if self.active_dm_peer else ""
            r_name = self.active_dm_peer.get("user_name", "") if self.active_dm_peer else ""
            if hasattr(self.chat_engine, "send_chat_message"):
                self.chat_engine.send_chat_message(text, recipient_id=r_id, recipient_name=r_name)
            elif hasattr(self.chat_engine, "send_broadcast_message"):
                self.chat_engine.send_broadcast_message(text)
            self.in_chat_msg.text = ""
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

    def open_file_picker_popup(self, *args):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat is not initialized.")
            return

        if is_android():
            launched = self.launch_android_native_picker()
            if launched:
                return

        # Fallback for desktop or if native picker could not launch
        self._open_in_app_file_chooser()

    def launch_android_native_picker(self):
        try:
            from jnius import autoclass, cast
            from android.activity import bind as android_activity_bind, unbind as android_activity_unbind
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            String = autoclass('java.lang.String')

            REQ_CODE = 9021

            def _on_activity_result(req_code, res_code, intent_data):
                if req_code == REQ_CODE:
                    try:
                        android_activity_unbind(on_activity_result=_on_activity_result)
                    except Exception:
                        pass
                    if intent_data is not None and res_code == -1:  # Activity.RESULT_OK == -1
                        uri = intent_data.getData()
                        if uri is not None:
                            local_path = self._copy_android_uri_to_cache(uri)
                            if local_path and os.path.isfile(local_path):
                                Clock.schedule_once(lambda dt: self._send_picked_file(local_path), 0)

            self._picker_result_callback = _on_activity_result
            android_activity_bind(on_activity_result=_on_activity_result)

            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("*/*")
            intent.addCategory(Intent.CATEGORY_OPENABLE)

            activity = PythonActivity.mActivity
            try:
                title_cs = cast('java.lang.CharSequence', String("Select File to Share"))
                chooser = Intent.createChooser(intent, title_cs)
                activity.startActivityForResult(chooser, REQ_CODE)
            except Exception:
                activity.startActivityForResult(intent, REQ_CODE)
            return True
        except Exception as e:
            print(f"Android native file chooser note: {e}")
            return False

    def _copy_android_uri_to_cache(self, uri):
        try:
            import mimetypes
            import shutil
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            cr = activity.getContentResolver()

            filename = ""
            try:
                OpenableColumns = autoclass('android.provider.OpenableColumns')
                cursor = cr.query(uri, None, None, None, None)
                if cursor and cursor.moveToFirst():
                    idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if idx >= 0:
                        filename = cursor.getString(idx)
                    cursor.close()
            except Exception as e:
                print(f"Query filename error: {e}")

            if not filename:
                ext = ""
                try:
                    mime = cr.getType(uri)
                    if mime:
                        ext = mimetypes.guess_extension(mime) or ""
                except Exception:
                    pass
                filename = f"shared_{int(time.time())}{ext}"

            cache_dir = activity.getCacheDir().getAbsolutePath()
            dest_path = os.path.join(cache_dir, filename)

            # High-performance POSIX file descriptor stream copy
            copied = False
            try:
                pfd = cr.openFileDescriptor(uri, "r")
                if pfd is not None:
                    fd = pfd.getFd()
                    with open(fd, "rb", closefd=False) as f_in:
                        with open(dest_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    pfd.close()
                    copied = True
            except Exception as e_pfd:
                print(f"ParcelFileDescriptor copy note: {e_pfd}")

            # Java stream fallback via FileUtils
            if not copied:
                try:
                    FileUtils = autoclass('android.os.FileUtils')
                    File = autoclass('java.io.File')
                    FileOutputStream = autoclass('java.io.FileOutputStream')
                    in_stream = cr.openInputStream(uri)
                    if in_stream is not None:
                        out_stream = FileOutputStream(File(dest_path))
                        FileUtils.copy(in_stream, out_stream)
                        out_stream.close()
                        in_stream.close()
                        copied = True
                except Exception as e_fu:
                    print(f"FileUtils stream copy note: {e_fu}")

            if copied and os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
                return dest_path
        except Exception as e:
            print(f"Error copying uri to cache: {e}")
        return None

    def _send_picked_file(self, file_path, caption=""):
        if not file_path or not os.path.isfile(file_path):
            self.show_popup("Error", "Selected file could not be read.")
            return
        if self.chat_engine:
            try:
                msg_obj = self.chat_engine.send_file(file_path, caption=caption)
                if msg_obj:
                    fn = os.path.basename(file_path)
                    f_id = msg_obj.get("file_id")
                    if f_id:
                        self.downloaded_files[f_id] = file_path
                    self.show_popup("File Shared", f"File '{fn}' broadcast to LAN team!")
                    Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)
                else:
                    self.show_popup("Error", "Could not send file.")
            except Exception as e:
                self.show_popup("Error", f"File sending failed: {e}")

    def _open_in_app_file_chooser(self):
        # Quick directory resolver
        start_dir = "/sdcard/Download" if (is_android() and os.path.isdir("/sdcard/Download")) else os.path.expanduser("~")
        for d in ("/sdcard/Download", "/storage/emulated/0/Download", os.path.expanduser("~/Downloads"), "/sdcard"):
            if os.path.isdir(d):
                start_dir = d
                break

        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        # Top Button: Launch Android Native System Picker
        if is_android():
            btn_system_picker = Button(
                text="Open System Files / Gallery App",
                font_size='13sp',
                bold=True,
                size_hint_y=None,
                height=dp(42),
                background_normal='',
                background_color=get_color_from_hex("#0284c7"),
                color=(1, 1, 1, 1)
            )
            content.add_widget(btn_system_picker)

        # Directory Path Bar & Up Navigation Button
        path_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
        btn_up = Button(
            text="Up Folder",
            font_size='12sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        path_bar.add_widget(btn_up)

        lbl_path = Label(
            text=f"Folder: {start_dir}",
            font_size='11sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.75,
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='left'
        )
        lbl_path.bind(size=lbl_path.setter('text_size'))
        path_bar.add_widget(lbl_path)
        content.add_widget(path_bar)

        # Quick Navigation Shortcuts
        nav_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(4))
        shortcuts = [
            ("Downloads", "/sdcard/Download" if is_android() else os.path.expanduser("~/Downloads")),
            ("Storage", "/sdcard" if is_android() else os.path.expanduser("~")),
            ("Photos", "/sdcard/DCIM" if is_android() else os.path.expanduser("~/Pictures")),
            ("Docs", "/sdcard/Documents" if is_android() else os.path.expanduser("~/Documents"))
        ]

        filechooser = FileChooserListView(
            path=start_dir,
            size_hint=(1, 1)
        )

        for name, p in shortcuts:
            if os.path.isdir(p):
                b = Button(
                    text=name,
                    font_size='11sp',
                    background_normal='',
                    background_color=get_color_from_hex("#334155"),
                    color=(1, 1, 1, 1)
                )
                def _do_nav(btn_inst, target_path=p):
                    filechooser.path = target_path
                    filechooser.selection = []
                    lbl_path.text = f"Folder: {target_path}"
                    lbl_selected.text = "Tap a folder to open, or tap a file to select."
                    btn_send.text = "Send File"
                    btn_send.background_color = get_color_from_hex("#059669")
                b.bind(on_release=_do_nav)
                nav_row.add_widget(b)
        content.add_widget(nav_row)

        content.add_widget(filechooser)

        # Status / Selected item indicator
        lbl_selected = Label(
            text="Tap any folder to enter. Tap a file to select.",
            markup=True,
            font_size='11sp',
            size_hint_y=None,
            height=dp(24),
            color=get_color_from_hex("#94a3b8"),
            halign='left',
            valign='middle'
        )
        lbl_selected.bind(size=lbl_selected.setter('text_size'))
        content.add_widget(lbl_selected)

        # Bottom Buttons
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="Share File with Team", content=content, size_hint=(0.96, 0.88))

        if is_android():
            def _on_system_picker_click(x):
                popup.dismiss()
                self.launch_android_native_picker()
            btn_system_picker.bind(on_release=_on_system_picker_click)

        def _go_up_dir(x):
            cur = os.path.abspath(filechooser.path)
            parent = os.path.dirname(cur)
            if parent and parent != cur and os.path.isdir(parent):
                filechooser.path = parent
                filechooser.selection = []
                lbl_path.text = f"Folder: {parent}"
                lbl_selected.text = "Tap a folder to open, or tap a file to select."
                btn_send.text = "Send File"
                btn_send.background_color = get_color_from_hex("#059669")

        btn_up.bind(on_release=_go_up_dir)

        # SINGLE TAP TO ENTER DIRECTORY OR SELECT FILE
        def _on_selection_change(chooser, selection):
            if not selection:
                return
            target = selection[0]
            if os.path.isdir(target):
                # Tapped on directory (like 'resumes', 'statement', etc.): OPEN IT IMMEDIATELY!
                if chooser.path != target:
                    chooser.path = target
                    chooser.selection = []
                    lbl_path.text = f"Folder: {target}"
                    lbl_selected.text = f"Inside: [b]{os.path.basename(target)}[/b]. Tap a file to select."
                    btn_send.text = "Send File"
                    btn_send.background_color = get_color_from_hex("#059669")
            elif os.path.isfile(target):
                fn = os.path.basename(target)
                try:
                    sz_str = format_file_size(os.path.getsize(target))
                except Exception:
                    sz_str = ""
                b_info = self.get_file_type_badge(fn)
                lbl_selected.text = f"[{b_info['icon_txt']}] Selected: [b]{safe_escape_markup(fn)}[/b] ({sz_str})"
                btn_send.text = f"Send [{b_info['icon_txt']}] '{fn[:14]}...'" if len(fn) > 14 else f"Send [{b_info['icon_txt']}] '{fn}'"
                btn_send.background_color = get_color_from_hex("#10b981")

        filechooser.bind(selection=_on_selection_change)

        # Optional Caption Input
        in_caption = TextInput(
            hint_text="Optional caption / message with file...",
            multiline=False,
            font_size='12sp',
            size_hint_y=None,
            height=dp(36),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(8), dp(8)]
        )
        content.add_widget(in_caption)

        def _do_send_file(x):
            sel = filechooser.selection
            if not sel or not os.path.isfile(sel[0]):
                self.show_popup("Notice", "Please tap on a file to select it before sending.")
                return
            chosen_file = sel[0]
            cap_text = in_caption.text.strip()
            popup.dismiss()
            self._send_picked_file(chosen_file, caption=cap_text)

        btn_send = Button(
            text="Send File",
            font_size='13sp',
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            bold=True
        )
        btn_send.bind(on_release=_do_send_file)

        btn_cancel = Button(
            text="Cancel",
            font_size='13sp',
            background_normal='',
            background_color=get_color_from_hex("#475569")
        )
        btn_cancel.bind(on_release=popup.dismiss)

        btn_row.add_widget(btn_send)
        btn_row.add_widget(btn_cancel)
        content.add_widget(btn_row)

        popup.open()

    def get_best_download_dir(self):
        if is_android():
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                Environment = autoclass('android.os.Environment')
                ext_dir = activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                if ext_dir and ext_dir.exists():
                    return ext_dir.getAbsolutePath()
            except Exception:
                pass
            for d in ("/sdcard/Download", "/storage/emulated/0/Download"):
                if os.path.isdir(d):
                    try:
                        test_p = os.path.join(d, ".wp_test")
                        with open(test_p, "w") as f:
                            f.write("1")
                        os.remove(test_p)
                        return d
                    except Exception:
                        pass
        dl = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(dl, exist_ok=True)
            return dl
        except Exception:
            return get_storage_path("downloads")

    def get_preview_cache_dir(self):
        if is_android():
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                cache_dir = PythonActivity.mActivity.getCacheDir().getAbsolutePath()
                if cache_dir and os.path.isdir(cache_dir):
                    return cache_dir
            except Exception:
                pass
        base_dir = get_storage_dir() if 'get_storage_dir' in globals() else os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(base_dir, "cache")
        try:
            os.makedirs(p, exist_ok=True)
            return p
        except Exception:
            return self.get_best_download_dir()

    def get_file_local_path(self, msg):
        """Finds if a shared file exists locally on this phone/device."""
        # 1. Direct saved_path on msg
        p = msg.get("saved_path")
        if p and os.path.isfile(p):
            return p
        # 2. Sender's local_path (if sent by this device)
        p = msg.get("local_path")
        if p and os.path.isfile(p):
            return p
        # 3. downloaded_files dictionary
        fid = msg.get("file_id")
        if fid and hasattr(self, 'downloaded_files') and fid in self.downloaded_files:
            p = self.downloaded_files[fid]
            if p and os.path.isfile(p):
                return p
        # 4. Check best download dir (e.g. /sdcard/Download)
        fn = msg.get("file_name")
        if fn:
            dl_p = os.path.join(self.get_best_download_dir(), fn)
            if os.path.isfile(dl_p):
                return dl_p
            # 5. Check preview cache dir
            c_p = os.path.join(self.get_preview_cache_dir(), fn)
            if os.path.isfile(c_p):
                return c_p
        return None

    def open_file_externally(self, filepath):
        """Opens any file in its default external viewer on Android or Desktop."""
        if filepath and (filepath.startswith("http://") or filepath.startswith("https://")):
            return self.open_stream_url(filepath, os.path.basename(filepath))

        if not filepath or not os.path.isfile(filepath):
            self.show_popup("Notice", "File not found on this device.")
            return False

        if is_android():
            try:
                from jnius import autoclass, cast
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                File = autoclass('java.io.File')
                String = autoclass('java.lang.String')

                # Disable StrictMode death on file exposure so all apps can read the file
                try:
                    StrictMode = autoclass('android.os.StrictMode')
                    VmPolicyBuilder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                    StrictMode.setVmPolicy(VmPolicyBuilder().build())
                except Exception:
                    pass

                file_obj = File(filepath)
                uri = Uri.fromFile(file_obj)

                import mimetypes
                mime_type, _ = mimetypes.guess_type(filepath)
                if not mime_type:
                    ext = os.path.splitext(filepath)[1].lower()
                    mime_map = {
                        '.apk': 'application/vnd.android.package-archive',
                        '.pdf': 'application/pdf',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.webp': 'image/webp',
                        '.gif': 'image/gif',
                        '.mp4': 'video/mp4',
                        '.mkv': 'video/x-matroska',
                        '.mov': 'video/quicktime',
                        '.avi': 'video/x-msvideo',
                        '.3gp': 'video/3gpp',
                        '.mp3': 'audio/mpeg',
                        '.wav': 'audio/wav',
                        '.m4a': 'audio/mp4',
                        '.ogg': 'audio/ogg',
                        '.opus': 'audio/opus',
                        '.doc': 'application/msword',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.xls': 'application/vnd.ms-excel',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.ppt': 'application/vnd.ms-powerpoint',
                        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        '.txt': 'text/plain',
                        '.csv': 'text/csv',
                        '.json': 'application/json',
                        '.zip': 'application/zip',
                        '.rar': 'application/x-rar-compressed',
                        '.7z': 'application/x-7z-compressed',
                    }
                    mime_type = mime_map.get(ext, '*/*')

                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(uri, mime_type)
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

                try:
                    title_cs = cast('java.lang.CharSequence', String(f"Open '{os.path.basename(filepath)}' with"))
                    chooser = Intent.createChooser(intent, title_cs)
                    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    activity.startActivity(chooser)
                except Exception:
                    activity.startActivity(intent)
                return True
            except Exception as e:
                print(f"Android open_file error: {e}")
                self.show_popup("Notice", f"Could not open file viewer: {e}")
                return False
        else:
            # Desktop Linux / Mac / Windows
            try:
                import subprocess
                if sys.platform.startswith('linux'):
                    subprocess.Popen(['xdg-open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                elif sys.platform == 'win32':
                    os.startfile(filepath)
                    return True
            except Exception as e:
                print(f"Desktop open error: {e}")
                self.show_popup("Notice", f"Could not open file: {e}")
            return False

    def open_stream_url(self, stream_url, file_name, is_media=True):
        """Streams media or viewable files live over LAN without requiring prior download."""
        if not stream_url:
            return False

        ext_l = os.path.splitext(file_name)[1].lower()
        is_video = ext_l in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.webm', '.ts', '.m4v')
        is_audio = ext_l in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.opus')

        if is_android():
            try:
                from jnius import autoclass, cast
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                String = autoclass('java.lang.String')

                uri = Uri.parse(stream_url)
                intent = Intent(Intent.ACTION_VIEW)

                if is_video:
                    mime = "video/*"
                elif is_audio:
                    mime = "audio/*"
                elif ext_l == '.pdf':
                    mime = "application/pdf"
                elif ext_l in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                    mime = "image/*"
                else:
                    mime = "*/*"

                intent.setDataAndType(uri, mime)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

                try:
                    title_cs = cast('java.lang.CharSequence', String(f"Play / Stream '{file_name}' with"))
                    chooser = Intent.createChooser(intent, title_cs)
                    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    activity.startActivity(chooser)
                except Exception:
                    activity.startActivity(intent)
                return True
            except Exception as e:
                print(f"Android stream error: {e}")
                try:
                    webbrowser.open(stream_url)
                    return True
                except Exception:
                    pass
                return False
        else:
            # Desktop Linux / Mac / Windows (Simulator / Desktop mode)
            if sys.platform.startswith('linux'):
                if is_media:
                    media_players = ["vlc", "mpv", "celluloid", "totem", "ffplay"]
                    for player in media_players:
                        if shutil.which(player):
                            try:
                                subprocess.Popen([player, stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                return True
                            except Exception:
                                pass
                try:
                    subprocess.Popen(['xdg-open', stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    pass
            elif sys.platform == 'darwin':
                try:
                    subprocess.Popen(["open", stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    pass
            elif sys.platform == 'win32':
                try:
                    os.startfile(stream_url)
                    return True
                except Exception:
                    pass

            try:
                webbrowser.open(stream_url)
                return True
            except Exception:
                pass
            return False

    def stream_or_play_file(self, msg, btn_row=None, meta_lbl=None):
        """Handles Play/View action: streams video/audio/docs live over LAN, or opens if local."""
        file_name = msg.get("file_name", "file")
        file_id = msg.get("file_id", "")
        file_ip = msg.get("file_ip") or msg.get("sender_ip")
        file_port = msg.get("file_port")

        # Fallback to peer IP / file_port from active peers if missing in msg
        if (not file_ip or not file_port) and hasattr(self, 'chat_engine') and self.chat_engine:
            s_id = msg.get("sender_id")
            if s_id and s_id in self.chat_engine.peers:
                peer_info = self.chat_engine.peers[s_id]
                if not file_ip:
                    file_ip = peer_info.get("ip")
                if not file_port:
                    file_port = peer_info.get("file_port")

        # 1. If file is already downloaded or stored locally, open local copy immediately
        local_p = msg.get("saved_path") or msg.get("local_path") or self.downloaded_files.get(file_id)
        if local_p and os.path.isfile(local_p):
            self.open_file_externally(local_p)
            return

        ext_l = os.path.splitext(file_name)[1].lower()
        is_video = ext_l in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.webm', '.ts', '.m4v')
        is_audio = ext_l in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.opus')
        is_media = is_video or is_audio
        is_browser_doc = ext_l in ('.pdf', '.html', '.htm', '.svg', '.txt', '.json', '.xml', '.py', '.log', '.jpg', '.jpeg', '.png')

        # 2. If it's a streamable file and we have the peer's connection info, STREAM LIVE!
        if (is_media or is_browser_doc) and file_ip and file_port and file_id:
            encoded_name = urllib.parse.quote(file_name)
            stream_url = f"http://{file_ip}:{file_port}/files/{file_id}/{encoded_name}"
            
            opened = self.open_stream_url(stream_url, file_name, is_media=is_media)
            if opened:
                label_txt = "video stream" if is_video else ("audio stream" if is_audio else "live preview")
                self.show_popup("Live Streaming", f"Opening {label_txt} directly across LAN:\n\n'{file_name}'\n\nPlaying live without taking up local storage space!")
                return

        # 3. For non-streamable formats or if streaming couldn't launch, download to preview cache
        if btn_row:
            for child in btn_row.children:
                child.disabled = True
            if len(btn_row.children) > 1:
                btn_row.children[1].text = "Loading..."
        self.download_and_handle_file(msg, is_preview=True, on_complete_open=True, btn_row=btn_row, meta_lbl=meta_lbl)

    def download_and_handle_file(self, msg, is_preview=False, on_complete_open=False, btn_row=None, meta_lbl=None):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat engine is not active.")
            return

        file_name = msg.get("file_name", "downloaded_file")
        file_id = msg.get("file_id", "")
        target_dir = self.get_preview_cache_dir() if is_preview else self.get_best_download_dir()

        def _on_progress(cur, tot, spd=0.0, eta=0.0):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            cur_s = format_file_size(cur)
            def _update_ui(dt):
                if btn_row and len(btn_row.children) > 0:
                    prefix = "Loading" if is_preview else "Saving"
                    btn = btn_row.children[0] if not is_preview else btn_row.children[-1]
                    btn.text = f"{prefix} {pct}% ({cur_s})"
            Clock.schedule_once(_update_ui, 0)

        def _on_done(saved_path):
            def _finish_ui(dt):
                if file_id:
                    self.downloaded_files[file_id] = saved_path
                msg["saved_path"] = saved_path
                msg["local_path"] = saved_path

                if meta_lbl:
                    f_sz = os.path.getsize(saved_path) if os.path.isfile(saved_path) else msg.get("file_size", 0)
                    meta_lbl.text = f"[color=#10b981][b]SAVED[/b][/color]  [color=#94a3b8]{format_file_size(f_sz)}[/color]"

                if btn_row:
                    btn_row.clear_widgets()
                    ext_l = os.path.splitext(file_name)[1].lower()
                    is_v = ext_l in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.webm', '.ts', '.m4v')
                    is_a = ext_l in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.opus')
                    v_txt = "PLAY VIDEO" if is_v else ("PLAY AUDIO" if is_a else "OPEN FILE")

                    btn_open = Button(
                        text=v_txt,
                        font_size='12sp',
                        bold=True,
                        size_hint_x=0.5,
                        background_normal='',
                        background_color=get_color_from_hex("#8b5cf6" if is_v or is_a else "#0284c7"),
                        color=(1, 1, 1, 1)
                    )
                    btn_open.bind(on_release=lambda x, p=saved_path: self.open_file_externally(p))

                    btn_redl = Button(
                        text="RE-DOWNLOAD",
                        font_size='12sp',
                        bold=True,
                        size_hint_x=0.5,
                        background_normal='',
                        background_color=get_color_from_hex("#059669"),
                        color=(1, 1, 1, 1)
                    )
                    def _do_redl(x):
                        btn_redl.disabled = True
                        btn_redl.text = "Downloading..."
                        self.download_and_handle_file(msg, is_preview=False, on_complete_open=False, btn_row=btn_row, meta_lbl=meta_lbl)
                    btn_redl.bind(on_release=_do_redl)

                    btn_row.add_widget(btn_open)
                    btn_row.add_widget(btn_redl)

                if on_complete_open:
                    self.open_file_externally(saved_path)
                else:
                    self.show_popup("Download Complete", f"File saved successfully!\n\n'{file_name}'\n\nLocation:\n{saved_path}")

            Clock.schedule_once(_finish_ui, 0)

        def _on_err(err_msg):
            def _err_ui(dt):
                if btn_row:
                    for child in btn_row.children:
                        child.disabled = False
                        if "view" in child.text.lower() or "play" in child.text.lower():
                            child.text = "VIEW / PLAY"
                        else:
                            child.text = "DOWNLOAD"
                self.show_popup("Download Failed", f"Could not load '{file_name}':\n{err_msg}")
            Clock.schedule_once(_err_ui, 0)

        self.chat_engine.download_file(
            msg,
            target_dir=target_dir,
            on_progress=_on_progress,
            on_done=_on_done,
            on_error=_on_err
        )

    def download_chat_file(self, msg):
        self.download_and_handle_file(msg, is_preview=False, on_complete_open=False)

    def share_today_tasks_to_chat(self, *args):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat is not initialized.")
            return

        date_v = self.in_date.text.strip() if hasattr(self, 'in_date') else datetime.date.today().strftime("%Y-%m-%d")
        title_v = self.in_title.text.strip() if hasattr(self, 'in_title') else ""
        desc_v = self.in_desc.text.strip() if hasattr(self, 'in_desc') else ""
        hours_v = self.in_hours.text.strip() if hasattr(self, 'in_hours') else ""

        tasks = []
        if title_v:
            tasks.append({
                "title": title_v,
                "desc": desc_v,
                "hours": hours_v or "8.0",
                "status": "Completed",
                "project": self.in_proj.text.strip() if hasattr(self, 'in_proj') else "General Work"
            })
        else:
            tasks.append({
                "title": "Daily Standup Progress",
                "desc": "Active daily tasks logged via WorkPulse Mobile",
                "hours": "8.0",
                "status": "In Progress",
                "project": "WorkPulse"
            })

        shift_str = ""
        if hasattr(self, 'in_login') and hasattr(self, 'in_logout'):
            shift_str = f"{self.in_login.text.strip()} - {self.in_logout.text.strip()}"
        total_h = f"{hours_v}h" if hours_v else "8.0h"

        self.chat_engine.send_work_update(
            title_or_date=title_v or "Daily Standup Progress",
            date_str_or_tasks=date_v,
            tasks=tasks,
            shift_str=shift_str,
            total_hours=total_h
        )
        self.refresh_chat_messages_ui()
        Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)
        self.show_popup("Shared", "Today's work progress shared with LAN team!")

    def open_custom_ip_popup(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        content.add_widget(Label(text="Enter colleague's IP address on this Wi-Fi:", font_size='13sp', color=(1, 1, 1, 1)))
        
        in_ip = TextInput(
            hint_text="e.g. 192.168.1.45",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1)
        )
        content.add_widget(in_ip)

        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="Connect to Peer IP", content=content, size_hint=(0.85, 0.35))

        def _do_connect(x):
            ip_val = in_ip.text.strip()
            if ip_val and self.chat_engine:
                self.chat_engine.add_custom_ip(ip_val)
                popup.dismiss()
                self._update_network_status_labels()
                self.show_popup("Connected", f"Target IP {ip_val} added to broadcast list!")
            else:
                popup.dismiss()

        btn_ok = Button(text="Connect", background_color=get_color_from_hex("#2563eb"), bold=True)
        btn_ok.bind(on_release=_do_connect)
        btn_cancel = Button(text="Cancel", background_color=get_color_from_hex("#475569"))
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_ok)
        btn_row.add_widget(btn_cancel)
        content.add_widget(btn_row)

        popup.open()

    # =========================================================================
    # TAB 3: REMINDERS & SCHEDULE VIEW
    # =========================================================================
    def build_reminders_view(self):
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content = GridLayout(cols=1, spacing=dp(12), padding=[dp(12), dp(10), dp(12), dp(24)], size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # Card 1: Presets
        card_presets = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(12), dp(10), dp(12), dp(12)])
        card_presets.bind(minimum_height=card_presets.setter('height'))

        card_presets.add_widget(self._create_field_label("1-Click Quick Presets:"))
        row_p1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        presets = [("10m", 10), ("15m", 15), ("30m", 30), ("1h", 60), ("2h", 120)]
        for lbl, mins in presets:
            btn_p = Button(text=lbl, font_size='13sp', background_normal='', background_color=get_color_from_hex("#0284c7"), color=(1, 1, 1, 1), bold=True)
            btn_p.bind(on_release=lambda x, m=mins: self.apply_preset_mins(m))
            row_p1.add_widget(btn_p)
        card_presets.add_widget(row_p1)

        card_presets.add_widget(self._create_field_label("Shift Reminders:"))
        row_p2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        shift_presets = [("10:00 AM", "10:00 AM"), ("01:00 PM", "01:00 PM"), ("04:30 PM", "04:30 PM"), ("07:00 PM", "07:00 PM")]
        for lbl, t_v in shift_presets:
            btn_s = Button(text=lbl, font_size='13sp', background_normal='', background_color=get_color_from_hex("#d97706"), color=(1, 1, 1, 1), bold=True)
            btn_s.bind(on_release=lambda x, t=t_v: self.apply_preset_time(t))
            row_p2.add_widget(btn_s)
        card_presets.add_widget(row_p2)
        content.add_widget(card_presets)

        # Card 2: Schedule Custom Reminder Form
        card_form = RoundedCard(bg_hex="#131e33", radius=[dp(12), dp(12), dp(12), dp(12)], orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(12), dp(10), dp(12), dp(12)])
        card_form.bind(minimum_height=card_form.setter('height'))

        card_form.add_widget(self._create_field_label("Schedule Custom Reminder:"))
        self.in_rem_title = TextInput(
            hint_text="Reminder title (e.g. Client Call, Submit Update)",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        card_form.add_widget(self.in_rem_title)

        row_dt = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(6))
        today_s = datetime.date.today().strftime("%Y-%m-%d")
        self.in_rem_date = TextInput(
            text=today_s,
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        def_mins = (datetime.datetime.now().hour * 60 + datetime.datetime.now().minute + 30) % 1440
        def_t = format_minutes_to_time(def_mins) if 'format_minutes_to_time' in globals() else "10:30 AM"
        self.in_rem_time = TextInput(
            text=def_t,
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        row_dt.add_widget(self.in_rem_date)
        row_dt.add_widget(self.in_rem_time)
        card_form.add_widget(row_dt)

        row_rep_btn = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(6))
        self.sp_repeat = Spinner(
            text='Once (No Repeat)',
            values=('Once (No Repeat)', 'Daily', 'Weekdays', 'Weekly'),
            font_size='13sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_add_rem = Button(
            text="Save Schedule",
            font_size='14sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#16a34a"),
            color=(1, 1, 1, 1)
        )
        btn_add_rem.bind(on_release=self.save_schedule)
        row_rep_btn.add_widget(self.sp_repeat)
        row_rep_btn.add_widget(btn_add_rem)
        card_form.add_widget(row_rep_btn)
        content.add_widget(card_form)

        # Daily Shift Alerts Quick Toggle
        content.add_widget(self._create_field_label("Daily Shift Alerts (Login, Breaks, Standup):"))
        settings = load_all_settings() if 'load_all_settings' in globals() else {}
        is_daily_on = settings.get("daily_shift_reminders_enabled", True)
        self.btn_toggle_daily = Button(
            text=f"Daily Shift Alerts: {'ACTIVE' if is_daily_on else 'PAUSED'} (Tap to toggle)",
            font_size='14sp',
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#0f766e" if is_daily_on else "#475569"),
            color=(1, 1, 1, 1),
            bold=True
        )
        self.btn_toggle_daily.bind(on_release=self.toggle_daily_alerts)
        content.add_widget(self.btn_toggle_daily)

        # Immediate Test Alert Button
        btn_test_alert = Button(
            text="Test Alert Now (Ringtone & Notification)",
            font_size='14sp',
            bold=True,
            size_hint_y=None,
            height=dp(46),
            background_normal='',
            background_color=get_color_from_hex("#7c3aed"),
            color=(1, 1, 1, 1)
        )
        btn_test_alert.bind(on_release=self.test_alert_now)
        content.add_widget(btn_test_alert)

        # Active Scheduled Reminders List
        content.add_widget(self._create_field_label("Active Schedules:"))
        self.rem_list_box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.rem_list_box.bind(minimum_height=self.rem_list_box.setter('height'))
        content.add_widget(self.rem_list_box)
        self.refresh_reminders_list()

        scroll.add_widget(content)
        return scroll

    def test_alert_now(self, *args):
        title = "WorkPulse Reminder Test"
        msg = "Chime, notification and popup alert test! Your schedules are functioning properly."
        if show_android_notification:
            try:
                show_android_notification(title, msg)
            except Exception as e:
                print(f"Test alert note: {e}")
        self.show_reminder_alert(title, msg, item_type="custom", reminder_id=None)

    def apply_preset_mins(self, minutes):
        target = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        self.in_rem_date.text = target.strftime("%Y-%m-%d")
        self.in_rem_time.text = target.strftime("%I:%M %p")
        if not self.in_rem_title.text.strip():
            self.in_rem_title.text = f"Quick Reminder ({minutes}m)"

    def apply_preset_time(self, time_val):
        self.in_rem_date.text = datetime.date.today().strftime("%Y-%m-%d")
        self.in_rem_time.text = time_val
        if not self.in_rem_title.text.strip():
            self.in_rem_title.text = f"Shift Reminder ({time_val})"

    def save_schedule(self, *args):
        title = self.in_rem_title.text.strip()
        date_v = self.in_rem_date.text.strip()
        time_v = self.in_rem_time.text.strip()
        rep_val = self.sp_repeat.text

        rep_map = {
            "Once (No Repeat)": "none",
            "Daily": "daily",
            "Weekdays": "weekdays",
            "Weekly": "weekly"
        }
        repeat = rep_map.get(rep_val, "none")

        if not title:
            title = f"Reminder ({time_v})"
            self.in_rem_title.text = title

        if 'add_custom_reminder' in globals():
            try:
                add_custom_reminder(title, date_v, time_v, repeat=repeat)
                self.in_rem_title.text = ""
                self.refresh_reminders_list()
                self.show_popup("Scheduled", f"Reminder '{title}' scheduled for {date_v} {time_v}!")
            except Exception as e:
                self.show_popup("Error", f"Failed to save reminder: {e}")
        else:
            self.show_popup("Error", "Schedule engine is not loaded.")

    def toggle_daily_alerts(self, *args):
        if 'load_all_settings' in globals() and 'save_all_settings' in globals():
            settings = load_all_settings()
            new_val = not settings.get("daily_shift_reminders_enabled", True)
            settings["daily_shift_reminders_enabled"] = new_val
            save_all_settings(settings)
            self.btn_toggle_daily.text = f"Daily Shift Alerts: {'ACTIVE' if new_val else 'PAUSED'} (Tap to toggle)"
            self.btn_toggle_daily.background_color = get_color_from_hex("#0f766e" if new_val else "#475569")

    def refresh_reminders_list(self):
        if not hasattr(self, 'rem_list_box') or not self.rem_list_box:
            return
        self.rem_list_box.clear_widgets()
        if 'load_all_settings' not in globals():
            return
        settings = load_all_settings()
        reminders = settings.get("custom_reminders", [])

        if not reminders:
            lbl = Label(text="No scheduled reminders yet.", font_size='13sp', size_hint_y=None, height=dp(30), color=get_color_from_hex("#64748b"))
            self.rem_list_box.add_widget(lbl)
            return

        for r in reversed(reminders[-8:]):
            st = r.get("status", "pending")
            row = RoundedCard(bg_hex="#1e293b", radius=[dp(8), dp(8), dp(8), dp(8)], orientation='horizontal', size_hint_y=None, height=dp(44), padding=[dp(8), dp(4), dp(8), dp(4)], spacing=dp(6))

            status_badge = "[OK]" if st == "completed" else "[Pending]"
            lbl = Label(
                text=f"{status_badge} [b]{r.get('title')}[/b]  {r.get('datetime', '')}",
                markup=True,
                font_size='13sp',
                size_hint_x=0.7,
                halign='left',
                valign='middle',
                color=get_color_from_hex("#f8fafc" if st == "pending" else "#94a3b8")
            )
            lbl.bind(size=lbl.setter('text_size'))
            row.add_widget(lbl)

            r_id = r.get("id")
            btn_done = Button(
                text="Done" if st == "pending" else "Undo",
                font_size='12sp',
                size_hint_x=0.15,
                background_normal='',
                background_color=get_color_from_hex("#0284c7"),
                bold=True
            )
            btn_done.bind(on_release=lambda x, rid=r_id: self._toggle_status(rid))
            row.add_widget(btn_done)

            btn_del = Button(
                text="Del",
                font_size='12sp',
                size_hint_x=0.15,
                background_normal='',
                background_color=get_color_from_hex("#dc2626"),
                bold=True
            )
            btn_del.bind(on_release=lambda x, rid=r_id: self._delete_item(rid))
            row.add_widget(btn_del)

            self.rem_list_box.add_widget(row)

    def _toggle_status(self, rem_id):
        if 'toggle_custom_reminder_status' in globals():
            toggle_custom_reminder_status(rem_id)
            self.refresh_reminders_list()

    def _delete_item(self, rem_id):
        if 'delete_custom_reminder' in globals():
            delete_custom_reminder(rem_id)
            self.refresh_reminders_list()

    def copy_apps_script_to_clipboard(self):
        code = get_google_apps_script_code() if 'get_google_apps_script_code' in globals() else ""
        if Clipboard is not None:
            try:
                Clipboard.copy(code)
            except Exception as e:
                print(f"Clipboard copy note: {e}")
        self.show_popup(
            "Code Copied",
            "Google Apps Script code copied to clipboard!\n\n"
            "Next steps:\n"
            "1. Open your Google Sheet in browser.\n"
            "2. Tap Extensions -> Apps Script.\n"
            "3. Paste the code and click Save.\n"
            "4. Deploy -> New deployment -> type: Web app.\n"
            "5. Set 'Who has access' to 'Anyone'.\n"
            "6. Copy the Web app URL and paste it into WorkPulse!"
        )

    def open_apps_script_guide_popup(self):
        guide_box = BoxLayout(orientation='vertical', padding=[dp(8), dp(6), dp(8), dp(8)], spacing=dp(8))

        # Title Bar with ASCII 'X' Close button
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(8))
        lbl_title = Label(
            text="[b]Google Sheets Setup Guide (30s)[/b]",
            markup=True,
            font_size='14sp',
            color=get_color_from_hex("#34d399"),
            size_hint_x=0.88,
            halign='left',
            valign='middle'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        title_bar.add_widget(lbl_title)

        btn_close = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(30), dp(30)),
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        title_bar.add_widget(btn_close)
        guide_box.add_widget(title_bar)

        # Scrollable Guide Content (clean, zero scrollbar clutter)
        guide_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=0,
            bar_color=[0, 0, 0, 0],
            bar_inactive_color=[0, 0, 0, 0],
            scroll_type=['content']
        )
        guide_content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(4), dp(4), dp(4), dp(6)])
        guide_content.bind(minimum_height=guide_content.setter('height'))

        steps = [
            ("Step 1: Open Google Sheet", "Create a new spreadsheet or open an existing one in your browser at sheets.google.com."),
            ("Step 2: Open Apps Script Editor", "In the top menu bar, tap Extensions > Apps Script."),
            ("Step 3: Paste WorkPulse Script", "Delete any sample code in the editor, tap 'Copy Apps Script Code' below, paste it into Code.gs, and tap Save (or Ctrl+S)."),
            ("Step 4: Deploy as Web App", "In the top right, tap Deploy > New deployment.\n- Type: Select 'Web app'\n- Execute as: 'Me (<your email>)'\n- Who has access: 'Anyone'\n- Tap Deploy and authorize access.\n- Copy the Web App URL (ends with /exec) and paste it into WorkPulse!")
        ]

        for s_title, s_desc in steps:
            card = RoundedCard(bg_hex="#0b1120", radius=[dp(6), dp(6), dp(6), dp(6)], orientation='vertical', size_hint_y=None, padding=[dp(8), dp(6), dp(8), dp(6)], spacing=dp(2))
            lbl_st = Label(text=f"[b]{s_title}[/b]", markup=True, font_size='12sp', color=get_color_from_hex("#38bdf8"), size_hint_y=None, height=dp(20), halign='left', valign='middle')
            lbl_st.bind(size=lbl_st.setter('text_size'))
            card.add_widget(lbl_st)

            lbl_sd = Label(text=s_desc, font_size='11sp', color=get_color_from_hex("#cbd5e1"), size_hint_y=None, halign='left', valign='top')
            def _bind_sd(lbl, *args):
                lbl.text_size = (lbl.width, None)
                lbl.texture_update()
                lbl.height = max(dp(22), lbl.texture_size[1] + dp(4))
                lbl.parent.height = dp(24) + lbl.height + dp(12)
            lbl_sd.bind(width=_bind_sd)
            lbl_sd.height = dp(44)
            card.add_widget(lbl_sd)
            card.height = dp(24) + dp(44) + dp(12)
            guide_content.add_widget(card)

        guide_scroll.add_widget(guide_content)
        guide_box.add_widget(guide_scroll)

        # Bottom Action Bar
        act_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
        btn_copy_in_guide = Button(
            text="Copy Apps Script Code",
            font_size='12sp',
            bold=True,
            size_hint_x=0.65,
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        btn_copy_in_guide.bind(on_release=lambda x: self.copy_apps_script_to_clipboard())
        act_bar.add_widget(btn_copy_in_guide)

        btn_got_it = Button(
            text="Got It!",
            font_size='12sp',
            bold=True,
            size_hint_x=0.35,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        act_bar.add_widget(btn_got_it)
        guide_box.add_widget(act_bar)

        popup = Popup(
            title="",
            separator_height=0,
            content=guide_box,
            size_hint=(0.94, 0.88),
            auto_dismiss=False
        )
        btn_close.bind(on_release=popup.dismiss)
        btn_got_it.bind(on_release=popup.dismiss)
        popup.open()

    # =========================================================================
    # SETTINGS MODAL DIALOG
    # =========================================================================
    def open_settings_popup(self, *args):
        settings = load_all_settings() if 'load_all_settings' in globals() else (load_settings() if 'load_settings' in globals() else {})
        holidays_list = list(settings.get("holidays", STANDARD_HOLIDAYS_2026 if 'STANDARD_HOLIDAYS_2026' in globals() else []))
        weekly_offs = set(settings.get("weekly_offs", ["Sunday"]))

        # Mutable state for toggles and options
        state = {
            "platform": str(settings.get("webhook_type", "Microsoft Teams")),
            "prompt_team_share": bool(settings.get("prompt_team_share_on_save", True)),
            "auto_copy": bool(settings.get("auto_copy_on_save", True)),
            "sec_fourth_sat": bool(settings.get("second_fourth_saturday", False)),
            "api_edit": bool(settings.get("data_api_sync_on_edit", True)),
            "api_create": bool(settings.get("data_api_sync_on_create", True)),
            "api_delete": bool(settings.get("data_api_sync_on_delete", True)),
            "gsheet_sync": bool(settings.get("gsheet_auto_sync", True)),
            "gsheet_fetch": bool(settings.get("gsheet_fetch_priority", True)),
            "rem_enabled": bool(settings.get("reminders_enabled", True)),
            "rem_sound": bool(settings.get("reminder_sound", True)),
            "rem_notify": bool(settings.get("reminder_desktop_notify", True)),
            "rem_daily": bool(settings.get("daily_shift_reminders_enabled", True)),
            "rem_skip": bool(settings.get("remind_skip_weekends_holidays", True)),
        }

        # Root modal container
        root_box = BoxLayout(orientation='vertical', padding=[dp(8), dp(6), dp(8), dp(8)], spacing=dp(6))

        # Title bar with Close 'X' (ASCII safe, no tofu glyph)
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(8))
        lbl_modal_title = Label(
            text="[b]Work Logger Settings & Configuration[/b]",
            markup=True,
            font_size='14sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.88,
            halign='left',
            valign='middle'
        )
        lbl_modal_title.bind(size=lbl_modal_title.setter('text_size'))
        title_bar.add_widget(lbl_modal_title)

        btn_close_x = Button(
            text="X",
            font_size='13sp',
            bold=True,
            size_hint=(None, None),
            size=(dp(30), dp(30)),
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        title_bar.add_widget(btn_close_x)
        root_box.add_widget(title_bar)

        # Tab Navigation Bar (Single Row: all 5 tabs visible at once, NO horizontal scroll)
        tab_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(4))
        root_box.add_widget(tab_bar)

        # Content Area (Zero scrollbar clutter)
        content_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=0,
            bar_color=[0, 0, 0, 0],
            bar_inactive_color=[0, 0, 0, 0],
            scroll_type=['content']
        )
        root_box.add_widget(content_scroll)

        # Helper to create inputs with consistent dark styling
        def _make_input(val="", hint="", multiline=False, height_dp=36):
            return TextInput(
                text=str(val),
                hint_text=hint,
                multiline=multiline,
                font_size='13sp',
                size_hint_y=None,
                height=dp(height_dp),
                background_normal='',
                background_color=get_color_from_hex("#1e293b"),
                foreground_color=(1, 1, 1, 1),
                hint_text_color=get_color_from_hex("#64748b"),
                padding=[dp(8), dp(8)]
            )

        # Helper to create toggle buttons
        def _make_toggle(label_prefix, key, on_color="#059669", off_color="#334155", on_text="ON", off_text="OFF", height_dp=34):
            btn = Button(
                text=f"{label_prefix}: {on_text if state[key] else off_text}",
                font_size='11sp',
                bold=True,
                size_hint_y=None,
                height=dp(height_dp),
                background_normal='',
                background_color=get_color_from_hex(on_color if state[key] else off_color),
                color=(1, 1, 1, 1)
            )
            def _toggle(b):
                state[key] = not state[key]
                b.text = f"{label_prefix}: {on_text if state[key] else off_text}"
                b.background_color = get_color_from_hex(on_color if state[key] else off_color)
            btn.bind(on_release=_toggle)
            return btn

        # Persistent Input widgets across tab switches
        # Tab 1: General & Shifts
        in_user_name = _make_input(settings.get("user_name", "Developer"), "Your Name / Handle")
        in_def_proj = _make_input(settings.get("default_project", "General Work"), "Default Project")
        in_login_t = _make_input(settings.get("default_login_time", "10:00 AM"), "10:00 AM")
        in_logout_t = _make_input(settings.get("default_logout_time", "07:30 PM"), "07:30 PM")
        in_lunch = _make_input(settings.get("default_lunch_break", "01:00 PM - 02:00 PM"), "Lunch Break")
        in_tea = _make_input(settings.get("default_tea_break", "04:30 PM - 04:45 PM"), "Tea Break")
        in_webhook_url = _make_input(settings.get("webhook_url", ""), "https://outlook.office.com/webhook/...")

        # Tab 2: Holidays
        in_hol_date = _make_input(datetime.date.today().strftime("%Y-%m-%d"), "YYYY-MM-DD")
        in_hol_name = _make_input("", "Holiday Name (e.g. Diwali, Eid)")

        # Tab 3: Data API
        in_api_url = _make_input(settings.get("data_api_url", ""), "https://api.yourcompany.com/v1/work-updates")
        in_api_token = _make_input(settings.get("data_api_token", ""), "Bearer token or secret key")

        # Tab 4: Google Sheet
        in_gsheet_url = _make_input(settings.get("gsheet_webapp_url", ""), "https://script.google.com/macros/s/.../exec")

        # ---------------- TAB DEFINITIONS (Single Row Compact Headers) ----------------
        tab_names = [
            ("General", "#2563eb"),
            ("Holidays", "#0284c7"),
            ("Data API", "#0f766e"),
            ("Sheets", "#059669"),
            ("Alerts", "#7c3aed")
        ]
        tab_buttons = []
        active_tab_idx = [0]

        # Builders for each tab (Created once as cached page layouts to prevent re-parenting exceptions)
        def _build_general_tab():
            page = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(6)])
            page.bind(minimum_height=page.setter('height'))

            page.add_widget(self._create_field_label("User Identity & Default Project:"))
            row_id = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            row_id.add_widget(in_user_name)
            row_id.add_widget(in_def_proj)
            page.add_widget(row_id)

            page.add_widget(self._create_field_label("Default Shift (Login - Logout):"))
            row_s1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            row_s1.add_widget(in_login_t)
            row_s1.add_widget(in_logout_t)
            page.add_widget(row_s1)

            page.add_widget(self._create_field_label("Default Breaks (Lunch & Tea):"))
            row_s2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            row_s2.add_widget(in_lunch)
            row_s2.add_widget(in_tea)
            page.add_widget(row_s2)

            page.add_widget(self._create_field_label("Team Notification Platform:"))
            row_plat = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(4))
            platforms = ["Microsoft Teams", "Slack / Discord", "Custom Webhook"]
            plat_btns = []
            for p in platforms:
                p_label = "Teams" if p == "Microsoft Teams" else ("Slack" if "Slack" in p else "Custom")
                p_btn = Button(
                    text=p_label,
                    font_size='11sp',
                    bold=True,
                    background_normal='',
                    background_color=get_color_from_hex("#2563eb" if state["platform"] == p else "#334155"),
                    color=(1, 1, 1, 1)
                )
                def _sel_plat(b, target=p):
                    state["platform"] = target
                    for pb, name in plat_btns:
                        pb.background_color = get_color_from_hex("#2563eb" if state["platform"] == name else "#334155")
                p_btn.bind(on_release=_sel_plat)
                plat_btns.append((p_btn, p))
                row_plat.add_widget(p_btn)
            page.add_widget(row_plat)

            page.add_widget(self._create_field_label("Incoming Webhook URL:"))
            page.add_widget(in_webhook_url)

            btn_test_wh = Button(
                text="Send Test Webhook Message",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(36),
                background_normal='',
                background_color=get_color_from_hex("#0284c7"),
                color=(1, 1, 1, 1)
            )
            def _do_test_wh(b):
                wh_url = in_webhook_url.text.strip()
                if not wh_url:
                    self.show_popup("Notice", "Please enter an Incoming Webhook URL first.")
                    return
                b.text = "Sending Test..."
                b.disabled = True
                def _thread_wh():
                    wh_type = state.get("platform", "Microsoft Teams")
                    test_msg = f"Test message from WorkPulse Mobile ({in_user_name.text.strip() or 'Developer'}). Webhook connection verified!"
                    if 'send_webhook_message' in globals():
                        ok, res = send_webhook_message(wh_url, test_msg, webhook_type=wh_type)
                        def _res(dt):
                            b.text = "Send Test Webhook Message"
                            b.disabled = False
                            if ok:
                                self.show_popup("Webhook Success", "Test notification posted successfully!")
                            else:
                                self.show_popup("Webhook Failed", f"Could not post message:\n\n{res}")
                        Clock.schedule_once(_res, 0)
                    else:
                        def _err(dt):
                            b.text = "Send Test Webhook Message"
                            b.disabled = False
                            self.show_popup("Notice", "Webhook sender function not loaded.")
                        Clock.schedule_once(_err, 0)
                threading.Thread(target=_thread_wh, daemon=True).start()
            btn_test_wh.bind(on_release=_do_test_wh)
            page.add_widget(btn_test_wh)

            page.add_widget(self._create_field_label("Automation Preferences:"))
            row_togs = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
            row_togs.add_widget(_make_toggle("Share on Save", "prompt_team_share", on_color="#059669"))
            row_togs.add_widget(_make_toggle("Auto-Copy", "auto_copy", on_color="#0284c7"))
            page.add_widget(row_togs)
            return page

        def _build_holidays_tab():
            page = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(6)])
            page.bind(minimum_height=page.setter('height'))

            page.add_widget(self._create_field_label("1. Weekly Off Days (Weekends):"))
            row_days = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(4))
            day_map = [("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"), ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday"), ("Sun", "Sunday")]
            for short_d, full_d in day_map:
                d_btn = Button(
                    text=short_d,
                    font_size='11sp',
                    bold=True,
                    background_normal='',
                    background_color=get_color_from_hex("#2563eb" if full_d in weekly_offs else "#334155"),
                    color=(1, 1, 1, 1)
                )
                def _tog_day(b, fd=full_d):
                    if fd in weekly_offs:
                        weekly_offs.remove(fd)
                        b.background_color = get_color_from_hex("#334155")
                    else:
                        weekly_offs.add(fd)
                        b.background_color = get_color_from_hex("#2563eb")
                d_btn.bind(on_release=_tog_day)
                row_days.add_widget(d_btn)
            page.add_widget(row_days)

            page.add_widget(_make_toggle("Include 2nd & 4th Saturday", "sec_fourth_sat", on_color="#0f766e", on_text="YES", off_text="NO"))

            page.add_widget(self._create_field_label("2. Company & National Holidays:"))
            row_date = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            row_date.add_widget(in_hol_date)
            btn_today = Button(
                text="Today",
                font_size='12sp',
                bold=True,
                size_hint_x=None,
                width=dp(60),
                background_normal='',
                background_color=get_color_from_hex("#475569")
            )
            btn_today.bind(on_release=lambda x: setattr(in_hol_date, 'text', datetime.date.today().strftime("%Y-%m-%d")))
            row_date.add_widget(btn_today)

            btn_add_hol = Button(
                text="+ Add",
                font_size='12sp',
                bold=True,
                size_hint_x=None,
                width=dp(60),
                background_normal='',
                background_color=get_color_from_hex("#2563eb")
            )
            row_date.add_widget(btn_add_hol)
            page.add_widget(row_date)

            page.add_widget(in_hol_name)

            row_h_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            btn_load_ind = Button(
                text="Load Indian Holidays",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#d97706")
            )
            btn_sync_sheet = Button(
                text="Sync to Sheet",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#7c3aed")
            )
            def _do_sync_sheet(b):
                if 'sync_month_holidays_and_weekly_offs' in globals():
                    try:
                        h_c, o_c, s_n = sync_month_holidays_and_weekly_offs(getattr(self, 'current_month', None))
                        self.show_popup("Sync Complete", f"Sheet '{s_n}' updated:\n- Added Holidays: {h_c}\n- Added Weekly Offs: {o_c}")
                    except Exception as ex:
                        self.show_popup("Error", f"Failed to sync to sheet: {ex}")
                else:
                    self.show_popup("Notice", "Sheet sync function not available.")
            btn_sync_sheet.bind(on_release=_do_sync_sheet)
            row_h_acts.add_widget(btn_load_ind)
            row_h_acts.add_widget(btn_sync_sheet)
            page.add_widget(row_h_acts)

            # Holidays dynamic list container
            hol_list_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
            hol_list_box.bind(minimum_height=hol_list_box.setter('height'))

            def _refresh_hol_ui():
                hol_list_box.clear_widgets()
                lbl_h_count.text = f"[b]Configured Holidays ({len(holidays_list)}):[/b]"
                sorted_h = sorted(holidays_list, key=lambda x: x.get("date", ""))
                for h in sorted_h:
                    d_str = h.get("date", "")
                    n_str = h.get("name", "")
                    try:
                        d_obj = datetime.datetime.strptime(d_str, "%Y-%m-%d")
                        w_day = d_obj.strftime("%A")
                    except Exception:
                        w_day = "-"
                    h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))

                    lbl_info = Label(
                        text=f"[b]{d_str}[/b] | [color=#94a3b8]{w_day[:3]}[/color]  [color=#38bdf8]{safe_escape_markup(n_str)}[/color]",
                        markup=True,
                        font_size='11sp',
                        size_hint_x=0.82,
                        halign='left',
                        valign='middle'
                    )
                    lbl_info.bind(size=lbl_info.setter('text_size'))
                    h_row.add_widget(lbl_info)

                    btn_del = Button(
                        text="Del",
                        font_size='11sp',
                        bold=True,
                        size_hint_x=None,
                        width=dp(44),
                        background_normal='',
                        background_color=get_color_from_hex("#ef4444")
                    )
                    def _do_del_h(b, date_key=d_str):
                        holidays_list[:] = [item for item in holidays_list if item.get("date") != date_key]
                        _refresh_hol_ui()
                    btn_del.bind(on_release=_do_del_h)
                    h_row.add_widget(btn_del)
                    hol_list_box.add_widget(h_row)

            def _do_add_hol(b):
                d_val = format_date_only(in_hol_date.text.strip())
                n_val = in_hol_name.text.strip()
                if not d_val or not n_val:
                    self.show_popup("Notice", "Please enter a valid Date (YYYY-MM-DD) and Holiday Name.")
                    return
                try:
                    datetime.datetime.strptime(d_val, "%Y-%m-%d")
                except ValueError:
                    self.show_popup("Notice", "Date must be YYYY-MM-DD (e.g. 2026-10-02).")
                    return
                for h in holidays_list:
                    if h.get("date") == d_val:
                        h["name"] = n_val
                        in_hol_name.text = ""
                        _refresh_hol_ui()
                        self.show_popup("Updated", f"Updated holiday for {d_val}.")
                        return
                holidays_list.append({"date": d_val, "name": n_val})
                in_hol_name.text = ""
                _refresh_hol_ui()

            def _do_load_indian(b):
                if 'STANDARD_HOLIDAYS_2026' in globals():
                    existing = {h.get("date") for h in holidays_list}
                    added = 0
                    for sh in STANDARD_HOLIDAYS_2026:
                        if sh.get("date") not in existing:
                            holidays_list.append(sh.copy())
                            added += 1
                    _refresh_hol_ui()
                    self.show_popup("Holidays Loaded", f"Loaded {added} standard Indian holidays for 2026!")

            btn_add_hol.bind(on_release=_do_add_hol)
            btn_load_ind.bind(on_release=_do_load_indian)

            lbl_h_count = Label(
                text=f"[b]Configured Holidays ({len(holidays_list)}):[/b]",
                markup=True,
                font_size='12sp',
                color=get_color_from_hex("#38bdf8"),
                size_hint_y=None,
                height=dp(24),
                halign='left',
                valign='middle'
            )
            lbl_h_count.bind(size=lbl_h_count.setter('text_size'))
            page.add_widget(lbl_h_count)
            page.add_widget(hol_list_box)
            _refresh_hol_ui()
            return page

        def _build_data_api_tab():
            page = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(6)])
            page.bind(minimum_height=page.setter('height'))

            page.add_widget(self._create_field_label("API / Webhook URL Endpoint:"))
            page.add_widget(in_api_url)

            page.add_widget(self._create_field_label("Bearer Token / Secret API Key:"))
            page.add_widget(in_api_token)

            btn_test_api = Button(
                text="Send Test Ping to API",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(40),
                background_normal='',
                background_color=get_color_from_hex("#0284c7")
            )
            def _do_test_api(b):
                u = in_api_url.text.strip()
                if not u:
                    self.show_popup("Notice", "Please enter an API URL first.")
                    return
                b.text = "Pinging API..."
                b.disabled = True
                def _thread_api():
                    tok = in_api_token.text.strip()
                    payload = {
                        "event": "test_ping",
                        "action": "ping",
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user_name": in_user_name.text.strip() or "Developer",
                        "message": "Connection test from WorkPulse Mobile",
                        "client_version": "2.0"
                    }
                    if 'send_data_api_webhook' in globals():
                        ok, msg, code = send_data_api_webhook(payload, api_url=u, auth_token=tok)
                        def _res(dt):
                            b.text = "Send Test Ping to API"
                            b.disabled = False
                            self.show_popup("API Connection Result", f"{'SUCCESS' if ok else 'FAILED'}\n\n- Code: {code}\n- Response:\n{msg}")
                        Clock.schedule_once(_res, 0)
                    else:
                        def _err(dt):
                            b.text = "Send Test Ping to API"
                            b.disabled = False
                            self.show_popup("Notice", "Data API sender function not found.")
                        Clock.schedule_once(_err, 0)
                threading.Thread(target=_thread_api, daemon=True).start()
            btn_test_api.bind(on_release=_do_test_api)
            page.add_widget(btn_test_api)

            page.add_widget(self._create_field_label("Automatic Real-Time Webhook Triggers:"))
            row_trig = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(4))
            row_trig.add_widget(_make_toggle("Edit", "api_edit", on_color="#059669"))
            row_trig.add_widget(_make_toggle("Create", "api_create", on_color="#0284c7"))
            row_trig.add_widget(_make_toggle("Delete", "api_delete", on_color="#ef4444"))
            page.add_widget(row_trig)
            return page

        def _build_gsheet_tab():
            page = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(6)])
            page.bind(minimum_height=page.setter('height'))

            page.add_widget(self._create_field_label("Google Sheet Web App URL:"))
            page.add_widget(in_gsheet_url)

            btn_test_gs = Button(
                text="Test Sheet Connection",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(36),
                background_normal='',
                background_color=get_color_from_hex("#0284c7")
            )
            def _do_test_gs(b):
                u = in_gsheet_url.text.strip()
                if not u:
                    self.show_popup("Notice", "Please enter a Google Sheet Web App URL first.")
                    return
                b.text = "Connecting..."
                b.disabled = True
                def _thread_gs():
                    if 'ping_google_sheet' in globals():
                        ok, data = ping_google_sheet(u)
                        def _res(dt):
                            b.text = "Test Sheet Connection"
                            b.disabled = False
                            if ok:
                                title = data.get("title", "Google Sheet") if isinstance(data, dict) else "Connected"
                                self.show_popup("Connection Successful", f"Connected to Google Sheet!\n\nSpreadsheet: '{title}'")
                            else:
                                err = data if isinstance(data, str) else str(data)
                                self.show_popup("Connection Failed", f"Could not reach Google Sheet:\n\n{err}")
                        Clock.schedule_once(_res, 0)
                    else:
                        def _err(dt):
                            b.text = "Test Sheet Connection"
                            b.disabled = False
                            self.show_popup("Notice", "Google Sheet ping function not found.")
                        Clock.schedule_once(_err, 0)
                threading.Thread(target=_thread_gs, daemon=True).start()
            btn_test_gs.bind(on_release=_do_test_gs)
            page.add_widget(btn_test_gs)

            # Direct Action Tools matching Desktop Synchronizer
            row_script_tools = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            btn_copy_code = Button(
                text="Copy Apps Script Code",
                font_size='11sp',
                bold=True,
                size_hint_x=0.52,
                background_normal='',
                background_color=get_color_from_hex("#059669"),
                color=(1, 1, 1, 1)
            )
            btn_copy_code.bind(on_release=lambda x: self.copy_apps_script_to_clipboard())
            row_script_tools.add_widget(btn_copy_code)

            btn_guide = Button(
                text="How to Setup (Guide)",
                font_size='11sp',
                bold=True,
                size_hint_x=0.48,
                background_normal='',
                background_color=get_color_from_hex("#334155"),
                color=(1, 1, 1, 1)
            )
            btn_guide.bind(on_release=lambda x: self.open_apps_script_guide_popup())
            row_script_tools.add_widget(btn_guide)
            page.add_widget(row_script_tools)

            page.add_widget(self._create_field_label("Synchronization Preferences:"))
            row_gs_togs = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
            row_gs_togs.add_widget(_make_toggle("Auto-Sync on Save", "gsheet_sync", on_color="#059669"))
            row_gs_togs.add_widget(_make_toggle("Fetch Priority", "gsheet_fetch", on_color="#0284c7"))
            page.add_widget(row_gs_togs)

            # Direct sync & fetch buttons
            row_gs_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            btn_sync_now = Button(
                text="Sync Month Now",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#059669")
            )
            def _do_sync_now(b):
                u = in_gsheet_url.text.strip()
                if not u:
                    self.show_popup("Notice", "Please configure Google Sheet Web App URL first.")
                    return
                b.text = "Syncing..."
                b.disabled = True
                def _thread_sync():
                    if 'sync_google_sheet_month' in globals():
                        ok, msg = sync_google_sheet_month(getattr(self, 'current_month', None), webapp_url=u)
                        def _res(dt):
                            b.text = "Sync Month Now"
                            b.disabled = False
                            self.show_popup("Sheet Sync", f"{'SUCCESS' if ok else 'FAILED'}:\n\n{msg}")
                        Clock.schedule_once(_res, 0)
                threading.Thread(target=_thread_sync, daemon=True).start()
            btn_sync_now.bind(on_release=_do_sync_now)
            row_gs_acts.add_widget(btn_sync_now)

            btn_fetch_now = Button(
                text="Fetch from Sheet",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#2563eb")
            )
            def _do_fetch_now(b):
                if hasattr(self, 'fetch_google_sheet_data_async'):
                    self.fetch_google_sheet_data_async()
                    self.show_popup("Fetching Data", "Fetching latest records from Google Sheet in background...")
            btn_fetch_now.bind(on_release=_do_fetch_now)
            row_gs_acts.add_widget(btn_fetch_now)
            page.add_widget(row_gs_acts)

            # Direct Notes sync & fetch row
            row_notes_gs_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(6))
            btn_sync_notes_now = Button(
                text="Sync Notes to Sheet",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#4338ca"),
                color=(1, 1, 1, 1)
            )
            def _do_sync_notes_now(b):
                u = in_gsheet_url.text.strip()
                if not u:
                    self.show_popup("Notice", "Please configure Google Sheet Web App URL first.")
                    return
                b.text = "Syncing..."
                b.disabled = True
                def _thread_sync_n():
                    if 'sync_google_sheet_notes' in globals():
                        ok, data, code = sync_google_sheet_notes(notes=load_notes(), webapp_url=u)
                        def _res_n(dt):
                            b.text = "Sync Notes to Sheet"
                            b.disabled = False
                            if ok:
                                cnt = data.get("updatedRows", "") if isinstance(data, dict) else ""
                                self.show_popup("Notes Synced", f"Successfully synchronized {cnt} notes to Google Sheet tab 'Notes'!")
                            else:
                                err = data if isinstance(data, str) else str(data)
                                self.show_popup("Sync Failed", f"Failed to sync notes:\n\n{err}")
                        Clock.schedule_once(_res_n, 0)
                threading.Thread(target=_thread_sync_n, daemon=True).start()
            btn_sync_notes_now.bind(on_release=_do_sync_notes_now)
            row_notes_gs_acts.add_widget(btn_sync_notes_now)

            btn_fetch_notes_now = Button(
                text="Fetch Notes from Sheet",
                font_size='11sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#6366f1"),
                color=(1, 1, 1, 1)
            )
            def _do_fetch_notes_now(b):
                u = in_gsheet_url.text.strip()
                if not u:
                    self.show_popup("Notice", "Please configure Google Sheet Web App URL first.")
                    return
                b.text = "Fetching..."
                b.disabled = True
                def _thread_fetch_n():
                    if 'fetch_google_sheet_notes' in globals():
                        ok, n_list, msg = fetch_google_sheet_notes(webapp_url=u)
                        def _res_fn(dt):
                            b.text = "Fetch Notes from Sheet"
                            b.disabled = False
                            if ok and n_list:
                                local_notes = load_notes() if 'load_notes' in globals() else []
                                existing_ids = {n.get("id"): idx for idx, n in enumerate(local_notes)}
                                for fn in n_list:
                                    if fn.get("id") in existing_ids:
                                        local_notes[existing_ids[fn.get("id")]] = fn
                                    else:
                                        local_notes.append(fn)
                                if 'save_notes' in globals():
                                    save_notes(local_notes)
                                self.refresh_notes_list()
                                self.show_popup("Notes Fetched", f"Successfully fetched and merged {len(n_list)} notes from Google Sheet!")
                            elif ok:
                                self.show_popup("Notes Fetched", "Connected to 'Notes' tab, but no notes rows were found.")
                            else:
                                self.show_popup("Fetch Failed", f"Failed to fetch notes:\n\n{msg}")
                        Clock.schedule_once(_res_fn, 0)
                threading.Thread(target=_thread_fetch_n, daemon=True).start()
            btn_fetch_notes_now.bind(on_release=_do_fetch_notes_now)
            row_notes_gs_acts.add_widget(btn_fetch_notes_now)
            page.add_widget(row_notes_gs_acts)
            return page

        def _build_reminders_tab():
            page = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(4), dp(4), dp(4), dp(6)])
            page.bind(minimum_height=page.setter('height'))

            page.add_widget(self._create_field_label("Scheduler System Controls:"))
            row_r1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
            row_r1.add_widget(_make_toggle("System Reminders", "rem_enabled", on_color="#2563eb", on_text="ON", off_text="OFF"))
            row_r1.add_widget(_make_toggle("Sound Chime", "rem_sound", on_color="#7c3aed"))
            page.add_widget(row_r1)

            row_r2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(6))
            row_r2.add_widget(_make_toggle("Notifications", "rem_notify", on_color="#059669"))
            row_r2.add_widget(_make_toggle("Daily Shift Alerts", "rem_daily", on_color="#0f766e"))
            page.add_widget(row_r2)

            page.add_widget(_make_toggle("Skip Alerts on Weekends & Holidays", "rem_skip", on_color="#d97706", on_text="YES", off_text="NO"))

            btn_test_alert = Button(
                text="Test Alert Now (Ringtone & Notification)",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(38),
                background_normal='',
                background_color=get_color_from_hex("#7c3aed")
            )
            btn_test_alert.bind(on_release=lambda x: self.test_alert_now())
            page.add_widget(btn_test_alert)
            return page

        tab_pages = [
            _build_general_tab(),
            _build_holidays_tab(),
            _build_data_api_tab(),
            _build_gsheet_tab(),
            _build_reminders_tab()
        ]

        def _switch_tab(idx):
            active_tab_idx[0] = idx
            for i, b in enumerate(tab_buttons):
                if i == idx:
                    b.background_color = get_color_from_hex(tab_names[i][1])
                    b.color = (1, 1, 1, 1)
                else:
                    b.background_color = get_color_from_hex("#1e293b")
                    b.color = get_color_from_hex("#94a3b8")
            content_scroll.clear_widgets()
            content_scroll.add_widget(tab_pages[idx])
            content_scroll.scroll_y = 1.0

        for idx, (t_name, t_color) in enumerate(tab_names):
            t_btn = Button(
                text=t_name,
                font_size='11sp',
                bold=True,
                size_hint_x=0.20,
                background_normal='',
                background_color=get_color_from_hex(t_color if idx == 0 else "#1e293b"),
                color=(1, 1, 1, 1) if idx == 0 else get_color_from_hex("#94a3b8")
            )
            def _on_tab_click(b, i=idx):
                _switch_tab(i)
            t_btn.bind(on_release=_on_tab_click)
            tab_buttons.append(t_btn)
            tab_bar.add_widget(t_btn)

        # Bottom Action Bar
        bottom_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        
        btn_cancel = Button(
            text="Cancel",
            font_size='13sp',
            size_hint_x=0.35,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        bottom_bar.add_widget(btn_cancel)

        btn_save = Button(
            text="Save All Settings",
            font_size='14sp',
            bold=True,
            size_hint_x=0.65,
            background_normal='',
            background_color=get_color_from_hex("#16a34a"),
            color=(1, 1, 1, 1)
        )
        bottom_bar.add_widget(btn_save)
        root_box.add_widget(bottom_bar)

        popup = Popup(
            title="",
            separator_height=0,
            content=root_box,
            size_hint=(0.96, 0.94),
            auto_dismiss=False
        )
        btn_close_x.bind(on_release=popup.dismiss)
        btn_cancel.bind(on_release=popup.dismiss)

        def _do_save_all(b):
            new_name = in_user_name.text.strip() or "Developer"
            new_proj = in_def_proj.text.strip() or "General Work"
            new_login = in_login_t.text.strip() or "10:00 AM"
            new_logout = in_logout_t.text.strip() or "07:30 PM"
            new_lunch = in_lunch.text.strip() or "01:00 PM - 02:00 PM"
            new_tea = in_tea.text.strip() or "04:30 PM - 04:45 PM"
            new_wh_url = in_webhook_url.text.strip()
            new_api_url = in_api_url.text.strip()
            new_api_token = in_api_token.text.strip()
            new_gs_url = in_gsheet_url.text.strip()

            settings.update({
                "user_name": new_name,
                "default_project": new_proj,
                "default_login_time": new_login,
                "default_logout_time": new_logout,
                "default_lunch_break": new_lunch,
                "default_tea_break": new_tea,
                "webhook_type": state["platform"],
                "webhook_url": new_wh_url,
                "prompt_team_share_on_save": state["prompt_team_share"],
                "auto_copy_on_save": state["auto_copy"],
                "weekly_offs": list(weekly_offs),
                "second_fourth_saturday": state["sec_fourth_sat"],
                "holidays": holidays_list,
                "data_api_url": new_api_url,
                "data_api_token": new_api_token,
                "data_api_sync_on_edit": state["api_edit"],
                "data_api_sync_on_create": state["api_create"],
                "data_api_sync_on_delete": state["api_delete"],
                "gsheet_webapp_url": new_gs_url,
                "gsheet_auto_sync": state["gsheet_sync"],
                "gsheet_fetch_priority": state["gsheet_fetch"],
                "reminders_enabled": state["rem_enabled"],
                "reminder_sound": state["rem_sound"],
                "reminder_desktop_notify": state["rem_notify"],
                "daily_shift_reminders_enabled": state["rem_daily"],
                "remind_skip_weekends_holidays": state["rem_skip"],
            })

            if 'save_all_settings' in globals():
                save_all_settings(settings)
            elif 'save_settings' in globals():
                save_settings(settings)

            self.settings = settings
            if self.chat_engine:
                self.chat_engine.user_name = new_name
                if hasattr(self.chat_engine, 'update_profile'):
                    self.chat_engine.update_profile(new_name)

            # Update default values in Work Update form
            if hasattr(self, 'in_proj') and self.in_proj:
                if not self.in_proj.text.strip() or self.in_proj.text.strip() == "General Work":
                    self.in_proj.text = new_proj
            if hasattr(self, 'in_login') and self.in_login:
                if not self.in_login.text.strip():
                    self.in_login.text = new_login
            if hasattr(self, 'in_logout') and self.in_logout:
                if not self.in_logout.text.strip():
                    self.in_logout.text = new_logout

            popup.dismiss()
            self.show_popup("Settings Saved", "All WorkPulse settings and shift configurations have been saved successfully!")

        btn_save.bind(on_release=_do_save_all)

        # Initial render of Tab 0 (General & Shifts)
        _switch_tab(0)
        popup.open()

    # =========================================================================
    # FORM ACTIONS & INTEGRATIONS
    # =========================================================================
    def set_today(self):
        self.in_date.text = datetime.date.today().strftime("%Y-%m-%d")

    def clear_form(self, *args):
        self.in_title.text = ""
        self.in_desc.text = ""
        self.in_hours.text = ""

    def on_save(self, *args):
        date_v = self.in_date.text.strip()
        proj_v = self.in_proj.text.strip() or "General Work"
        title_v = self.in_title.text.strip()
        desc_v = self.in_desc.text.strip()
        hours_v = self.in_hours.text.strip()
        status_v = self.sp_status.text.strip()
        login_v = self.in_login.text.strip()
        logout_v = self.in_logout.text.strip()

        if not title_v:
            self.show_popup("Error", "Please enter a Task Title.")
            return

        try:
            if 'save_work_update' in globals():
                ok = save_work_update(
                    date_v, proj_v, title_v, desc_v, hours_v, status_v, "",
                    login_time=login_v, logout_time=logout_v
                )
                if ok is not False:
                    fname = os.path.basename(FILE) if 'FILE' in globals() else "data.xlsx"
                    self.show_popup("Success", f"Task saved to {fname}!")
                    self.clear_form()
                    if hasattr(self, 'refresh_history_list'):
                        self.refresh_history_list()
                else:
                    self.show_popup("Error", "Could not save task update. Please verify storage.")

                # Background Google Sheet auto-sync if configured
                settings = load_settings() if 'load_settings' in globals() else {}
                if settings.get("gsheet_auto_sync", False) and settings.get("gsheet_webapp_url"):
                    try:
                        dt = datetime.datetime.strptime(date_v, "%Y-%m-%d")
                        m_name = dt.strftime("%B %Y")
                    except Exception:
                        m_name = datetime.datetime.now().strftime("%B %Y")
                    threading.Thread(target=lambda: sync_google_sheet_month(m_name), daemon=True).start()
            else:
                self.show_popup("Error", "Work update engine is not loaded.")
        except Exception as e:
            self.show_popup("Error", f"Failed to save: {e}")

    def copy_standup(self, *args):
        title_v = self.in_title.text.strip() or "Task completed"
        hours_v = f" ({self.in_hours.text.strip()}h)" if self.in_hours.text.strip() else ""
        date_v = self.in_date.text.strip()
        desc_v = self.in_desc.text.strip()
        text = f"Work Log - {date_v}\n* {title_v}{hours_v}\n{desc_v}"
        if Clipboard is not None:
            try:
                Clipboard.copy(text)
            except Exception:
                pass
        self.show_popup("Copied", "Standup update copied to clipboard!")

    def sync_gsheet(self, *args):
        if 'sync_google_sheet_month' not in globals():
            self.show_popup("Error", "Google Sheet sync module not loaded.")
            return

        settings = load_settings() if 'load_settings' in globals() else {}
        url = settings.get("gsheet_webapp_url", "").strip()
        if not url:
            self.show_popup("Setup Required", "Please configure your Google Sheet Web App URL in settings.json.")
            return

        try:
            date_str = self.in_date.text.strip()
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            month_name = dt.strftime("%B %Y")
        except Exception:
            month_name = datetime.datetime.now().strftime("%B %Y")

        def _do_sync():
            ok, data, code = sync_google_sheet_month(month_name)
            if ok:
                cnt = data.get("updatedRows", "") if isinstance(data, dict) else ""
                msg = f"Synced {cnt} rows to Google Sheet ('{month_name}') successfully!"
                Clock.schedule_once(lambda dt: self.show_popup("Sync Complete", msg), 0)
            else:
                msg = data if isinstance(data, str) else data.get("message", "Error")
                Clock.schedule_once(lambda dt: self.show_popup("Sync Failed", f"Failed to sync: {msg}"), 0)

        threading.Thread(target=_do_sync, daemon=True).start()

    def fetch_gsheet(self, *args):
        if 'fetch_google_sheet_month' not in globals():
            self.show_popup("Error", "Google Sheet fetch module not loaded.")
            return

        settings = load_settings() if 'load_settings' in globals() else {}
        url = settings.get("gsheet_webapp_url", "").strip()
        if not url:
            self.show_popup("Setup Required", "Please configure your Google Sheet Web App URL in settings.json.")
            return

        try:
            date_str = self.in_date.text.strip()
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            month_name = dt.strftime("%B %Y")
        except Exception:
            month_name = datetime.datetime.now().strftime("%B %Y")

        def _do_fetch():
            ok, data, code = fetch_google_sheet_month(month_name)
            if ok and isinstance(data, dict):
                rows = data.get("rows", [])
                if 'save_fetched_rows_to_excel' in globals():
                    save_fetched_rows_to_excel(month_name, data.get("headers"), rows)
                Clock.schedule_once(lambda dt: self.show_popup("Fetch Complete", f"Fetched {len(rows)} records from Google Sheet ('{month_name}') and synchronized with local system!"), 0)
            else:
                msg = data if isinstance(data, str) else (data.get("message", "Error") if isinstance(data, dict) else "Error")
                Clock.schedule_once(lambda dt: self.show_popup("Fetch Notice", f"Google Sheet unavailable:\n{msg}\nUsing local system records."), 0)

        threading.Thread(target=_do_fetch, daemon=True).start()

    def show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        lbl = Label(text=str(msg), font_size='14sp', color=(1, 1, 1, 1), halign='center', valign='middle')
        lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w - dp(24), None)))
        content.add_widget(lbl)
        btn = Button(text="OK", font_size='14sp', size_hint_y=None, height=dp(44), background_normal='', background_color=get_color_from_hex("#2563eb"))
        popup = Popup(title=str(title), content=content, size_hint=(0.85, 0.38))
        btn.bind(on_release=popup.dismiss)
        content.add_widget(btn)
        popup.open()

    def on_start(self):
        # 1. Initialize local Excel database file
        if 'init_file' in globals():
            try:
                init_file()
            except Exception as e:
                print(f"init_file note: {e}")

        # 2. Request Android runtime permissions on Android
        if is_android():
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.INTERNET,
                    Permission.ACCESS_NETWORK_STATE,
                    Permission.ACCESS_WIFI_STATE,
                    Permission.CHANGE_WIFI_MULTICAST_STATE,
                    Permission.POST_NOTIFICATIONS,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ])
            except Exception as e:
                print(f"Notice: Android permissions: {e}")

        # 3. Auto-fetch Google Sheet on startup if configured
        settings = load_settings() if 'load_settings' in globals() else {}
        if settings.get("gsheet_fetch_priority", True) and settings.get("gsheet_webapp_url"):
            month_name = datetime.datetime.now().strftime("%B %Y")
            def _auto_fetch():
                try:
                    if 'fetch_google_sheet_month' in globals() and 'save_fetched_rows_to_excel' in globals():
                        ok, data, code = fetch_google_sheet_month(month_name)
                        if ok and isinstance(data, dict):
                            rows = data.get("rows", [])
                            save_fetched_rows_to_excel(month_name, data.get("headers"), rows)
                except Exception:
                    pass
            threading.Thread(target=_auto_fetch, daemon=True).start()

        # Start Mobile Reminder Scheduler Engine
        if 'ReminderSchedulerEngine' in globals():
            def _on_mobile_trigger(item_type, title, message, reminder_id):
                if show_android_notification:
                    try:
                        show_android_notification(title, message)
                    except Exception as e:
                        print(f"Android notification: {e}")
                if KIVY_AVAILABLE and Clock:
                    Clock.schedule_once(lambda dt: self.show_reminder_alert(title, message, item_type, reminder_id))
            self.reminder_engine = ReminderSchedulerEngine(on_trigger_callback=_on_mobile_trigger)
            try:
                self.reminder_engine.start()
            except Exception as e:
                print(f"Error starting mobile reminder engine: {e}")

    def on_stop(self):
        if hasattr(self, 'reminder_engine') and self.reminder_engine:
            try:
                self.reminder_engine.stop()
            except Exception:
                pass
        if hasattr(self, 'chat_engine') and self.chat_engine:
            try:
                self.chat_engine.stop()
            except Exception:
                pass

    def show_reminder_alert(self, title, msg, item_type="custom", reminder_id=None):
        if not KIVY_AVAILABLE:
            return
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        esc_title = safe_escape_markup(title)
        esc_msg = safe_escape_markup(msg)
        lbl = Label(text=f"[b]{esc_title}[/b]\n\n{esc_msg}", markup=True, font_size='15sp', color=(1, 1, 1, 1), halign='center')
        lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w - dp(24), None)))
        content.add_widget(lbl)

        b_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(6))
        popup = Popup(title="WorkPulse Reminder Alert", content=content, size_hint=(0.88, 0.42), auto_dismiss=False)

        if item_type == "work_update":
            btn_act = Button(text="Fill Update", background_normal='', background_color=get_color_from_hex("#8b5cf6"), bold=True)
            def _go_fill(x):
                popup.dismiss()
                self.switch_tab("work")
                self.in_title.focus = True
            btn_act.bind(on_release=_go_fill)
            b_row.add_widget(btn_act)
        elif item_type == "login":
            btn_act = Button(text="Set Login", background_normal='', background_color=get_color_from_hex("#0284c7"), bold=True)
            def _set_log(x):
                popup.dismiss()
                self.switch_tab("work")
                self.in_login.text = datetime.datetime.now().strftime("%I:%M %p")
            btn_act.bind(on_release=_set_log)
            b_row.add_widget(btn_act)

        btn_snooze = Button(text="Snooze 10m", background_normal='', background_color=get_color_from_hex("#334155"), bold=True)
        def _do_snooze(x):
            popup.dismiss()
            if hasattr(self, 'reminder_engine') and self.reminder_engine:
                self.reminder_engine.snooze_runtime_reminder(title, msg, minutes=10, item_type=item_type, reminder_id=reminder_id)
        btn_snooze.bind(on_release=_do_snooze)
        b_row.add_widget(btn_snooze)

        btn_done = Button(text="Done", background_normal='', background_color=get_color_from_hex("#16a34a"), bold=True)
        def _do_done(x):
            popup.dismiss()
            if item_type == "custom" and reminder_id and 'toggle_custom_reminder_status' in globals():
                toggle_custom_reminder_status(reminder_id, "completed")
        btn_done.bind(on_release=_do_done)
        b_row.add_widget(btn_done)

        content.add_widget(b_row)
        popup.open()


if __name__ == "__main__":
    if KIVY_AVAILABLE:
        WorkPulseMobileApp().run()
    else:
        print("Kivy is not installed. To run mobile UI on desktop, run: pip install kivy")
