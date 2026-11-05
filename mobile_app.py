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

# Ensure local dir is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

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
    from kivy.clock import Clock  # type: ignore
    from kivy.metrics import dp, sp  # type: ignore
    try:
        from kivy.core.clipboard import Clipboard  # type: ignore
    except Exception:
        Clipboard = None
    from kivy.core.window import Window  # type: ignore
    from kivy.utils import get_color_from_hex  # type: ignore
    KIVY_AVAILABLE = True
except (ImportError, Exception):
    KIVY_AVAILABLE = False
    App = object
    BoxLayout = GridLayout = ScrollView = Label = TextInput = Button = Spinner = Popup = Window = Clock = Image = object
    Clipboard = None

    def dp(x):  # type: ignore
        return x

    def sp(x):  # type: ignore
        return x

    def get_color_from_hex(hex_str):  # type: ignore
        return (1, 1, 1, 1)

def safe_escape_markup(text):
    """Escapes Kivy markup tags to prevent markup parsing errors with user text."""
    if not isinstance(text, str):
        text = str(text or "")
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")

try:
    from storage_config import is_android, get_storage_path, acquire_android_multicast_lock, show_android_notification
except Exception:
    def is_android(): return False
    def get_storage_path(fn): return fn
    def acquire_android_multicast_lock(): return None
    def show_android_notification(t, m): return False

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
        ping_google_sheet, sync_month_holidays_and_weekly_offs, DEFAULT_SETTINGS
    )
except Exception as e:
    print(f"Warning: app.py import: {e}")

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
    def build(self):
        self.title = "WorkPulse - Mobile"
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

        # Main Root Container
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # 1. Top Header App Bar
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=[dp(10), dp(4), dp(10), dp(4)], spacing=dp(6))
        
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
            size_hint_x=0.30,
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
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_settings.bind(on_release=self.open_settings_popup)
        header.add_widget(btn_settings)
        root.add_widget(header)

        # 2. Modern 5-Tab Navigation Bar
        nav_tabs = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), padding=[dp(2), 0, dp(2), dp(4)], spacing=dp(3))
        
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
        form = GridLayout(cols=1, spacing=dp(10), padding=[dp(12), dp(8), dp(12), dp(20)], size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # Date & Today row
        form.add_widget(self._create_field_label("Date (YYYY-MM-DD):"))
        date_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
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
            font_size='14sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_today.bind(on_release=lambda x: self.set_today())
        date_row.add_widget(self.in_date)
        date_row.add_widget(btn_today)
        form.add_widget(date_row)

        # Project / Module
        form.add_widget(self._create_field_label("Project / Module:"))
        self.in_proj = TextInput(
            text="General Work",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(48),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(12)]
        )
        form.add_widget(self.in_proj)

        # Task Title
        form.add_widget(self._create_field_label("Task Title:"))
        self.in_title = TextInput(
            hint_text="e.g. Bug fixes, feature development",
            multiline=False,
            font_size='15sp',
            size_hint_y=None,
            height=dp(48),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(12)]
        )
        form.add_widget(self.in_title)

        # Hours & Status row
        form.add_widget(self._create_field_label("Hours & Status:"))
        h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
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
        form.add_widget(h_row)

        # Shift timings (Login - Logout)
        form.add_widget(self._create_field_label("Shift Timings (Login - Logout):"))
        t_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
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
        form.add_widget(t_row)

        # Work Description / Notes
        form.add_widget(self._create_field_label("Work Description / Notes:"))
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
        form.add_widget(self.in_desc)

        # Spacing divider
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(4)))

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

        # Secondary Actions Grid (Row 1)
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

        # Secondary Actions Grid (Row 2: Google Sheets)
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
            font_size='13sp',
            color=get_color_from_hex("#94a3b8"),
            size_hint_y=None,
            height=dp(26),
            halign='left',
            valign='middle'
        )
        lbl.bind(size=lbl.setter('text_size'))
        return lbl

    # =========================================================================
    # TAB 2: MY UPDATES / WORK LOGS HISTORY VIEW
    # =========================================================================
    def build_history_view(self):
        root = BoxLayout(orientation='vertical', padding=[dp(10), dp(6), dp(10), dp(10)], spacing=dp(8))

        # Top Control Row: Month Selector & Refresh
        top_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        
        months = get_available_months() if 'get_available_months' in globals() else []
        current_m = datetime.datetime.now().strftime("%B %Y")
        if not months:
            months = [current_m]
        elif current_m not in months:
            months.insert(0, current_m)

        self.sp_hist_month = Spinner(
            text=current_m,
            values=tuple(months),
            font_size='14sp',
            size_hint_x=0.72,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=(1, 1, 1, 1)
        )
        self.sp_hist_month.bind(text=lambda s, val: self.refresh_history_list())
        top_row.add_widget(self.sp_hist_month)

        btn_refresh = Button(
            text="Refresh",
            font_size='13sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_refresh.bind(on_release=lambda x: self.refresh_history_list())
        top_row.add_widget(btn_refresh)
        root.add_widget(top_row)

        # Summary Bar
        self.lbl_hist_stats = Label(
            text="Loading summary...",
            font_size='13sp',
            size_hint_y=None,
            height=dp(26),
            color=get_color_from_hex("#38bdf8"),
            halign='left',
            valign='middle'
        )
        self.lbl_hist_stats.bind(size=self.lbl_hist_stats.setter('text_size'))
        root.add_widget(self.lbl_hist_stats)

        # Search Bar
        self.in_hist_search = TextInput(
            hint_text="Search by task, project, status...",
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(10)]
        )
        self.in_hist_search.bind(text=lambda s, val: self.refresh_history_list())
        root.add_widget(self.in_hist_search)

        # Updates List ScrollView
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.hist_list_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4), 0, dp(12)])
        self.hist_list_layout.bind(minimum_height=self.hist_list_layout.setter('height'))
        scroll.add_widget(self.hist_list_layout)
        root.add_widget(scroll)

        return root

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
        filtered = []
        tot_hours = 0.0
        comp_cnt = 0

        for r in records:
            t_title = str(r[3] or "")
            t_proj = str(r[2] or "")
            t_status = str(r[6] or "")
            t_desc = str(r[4] or "")
            t_hours_s = str(r[5] or "0").replace("h", "").strip()
            try:
                tot_hours += float(t_hours_s)
            except Exception:
                pass
            if t_status.lower() == "completed":
                comp_cnt += 1

            if not search_q or search_q in t_title.lower() or search_q in t_proj.lower() or search_q in t_status.lower() or search_q in t_desc.lower():
                filtered.append(r)

        if hasattr(self, 'lbl_hist_stats'):
            self.lbl_hist_stats.text = f"{len(records)} Tasks  |  {tot_hours:.1f} Total Hours  |  {comp_cnt} Completed"

        if not filtered:
            msg = "No work updates matching filter." if search_q else f"No updates logged for {target_m}.\nUse 'Log Work' tab to save tasks!"
            lbl = Label(text=msg, font_size='14sp', color=get_color_from_hex("#64748b"), size_hint_y=None, height=dp(60), halign='center')
            self.hist_list_layout.add_widget(lbl)
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
        hours_v = str(r[5] or "0")
        status_v = str(r[6] or "Completed")
        login_v = str(r[8] or "")
        logout_v = str(r[9] or "")

        card = BoxLayout(orientation='vertical', size_hint_y=None, padding=[dp(12), dp(10), dp(12), dp(10)], spacing=dp(5))
        card.height = dp(144) if desc_v else dp(116)

        # Row 1: Date & Project Pill
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(22), spacing=dp(8))
        lbl_date = Label(
            text=f"[b]{date_v}[/b]",
            markup=True,
            font_size='13sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.45,
            halign='left',
            valign='middle'
        )
        lbl_date.bind(size=lbl_date.setter('text_size'))
        row1.add_widget(lbl_date)

        lbl_proj = Label(
            text=f"[b]{safe_escape_markup(proj_v)}[/b]",
            markup=True,
            font_size='12sp',
            color=get_color_from_hex("#c084fc"),
            size_hint_x=0.55,
            halign='right',
            valign='middle'
        )
        lbl_proj.bind(size=lbl_proj.setter('text_size'))
        row1.add_widget(lbl_proj)
        card.add_widget(row1)

        # Row 2: Title & Hours Badge
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
            font_size='14sp',
            color=get_color_from_hex("#34d399"),
            size_hint_x=0.24,
            halign='right',
            valign='middle'
        )
        lbl_hours.bind(size=lbl_hours.setter('text_size'))
        row2.add_widget(lbl_hours)
        card.add_widget(row2)

        # Row 3: Shift Timings & Status Badge
        row3 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(22), spacing=dp(8))
        shift_txt = f"{login_v} - {logout_v}" if (login_v or logout_v) else "Shift: Standard"
        lbl_shift = Label(
            text=f"Shift: {shift_txt}",
            font_size='12sp',
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
            font_size='12sp',
            color=get_color_from_hex(st_c),
            size_hint_x=0.38,
            halign='right',
            valign='middle'
        )
        lbl_st.bind(size=lbl_st.setter('text_size'))
        row3.add_widget(lbl_st)
        card.add_widget(row3)

        # Row 4: Description preview
        if desc_v:
            desc_sub = (desc_v[:80] + "...") if len(desc_v) > 80 else desc_v
            lbl_desc = Label(
                text=safe_escape_markup(desc_sub),
                font_size='12sp',
                color=get_color_from_hex("#64748b"),
                size_hint_y=None,
                height=dp(20),
                halign='left',
                valign='middle'
            )
            lbl_desc.bind(size=lbl_desc.setter('text_size'))
            card.add_widget(lbl_desc)

        # Row 5: Action Buttons (View Details, Delete)
        row_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
        btn_view = Button(
            text="View Details",
            font_size='12sp',
            bold=True,
            size_hint_x=0.6,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_view.bind(on_release=lambda x, rec=r: self.view_update_details(rec))
        row_acts.add_widget(btn_view)

        btn_del = Button(
            text="Delete",
            font_size='12sp',
            bold=True,
            size_hint_x=0.4,
            background_normal='',
            background_color=get_color_from_hex("#dc2626"),
            color=(1, 1, 1, 1)
        )
        btn_del.bind(on_release=lambda x, rid=rec_id, sm=sheet_name: self.delete_update_item(rid, sm))
        row_acts.add_widget(btn_del)
        card.add_widget(row_acts)

        return card

    def view_update_details(self, r):
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(8))
        
        d_v = str(r[1] or "")
        p_v = str(r[2] or "")
        t_v = str(r[3] or "")
        desc_v = str(r[4] or "No description provided.")
        h_v = str(r[5] or "")
        st_v = str(r[6] or "")
        rem_v = str(r[7] or "")
        login_v = str(r[8] or "")
        logout_v = str(r[9] or "")
        created_v = str(r[12] or "")

        details_text = (
            f"[b]Task:[/b] {safe_escape_markup(t_v)}\n"
            f"[b]Date:[/b] {d_v}   |   [b]Project:[/b] {safe_escape_markup(p_v)}\n"
            f"[b]Hours:[/b] {h_v}h   |   [b]Status:[/b] {st_v}\n"
            f"[b]Timings:[/b] {login_v} - {logout_v}\n"
            f"[b]Logged At:[/b] {created_v}\n\n"
            f"[b]Description / Notes:[/b]\n{safe_escape_markup(desc_v)}"
        )
        if rem_v:
            details_text += f"\n\n[b]Remarks:[/b] {safe_escape_markup(rem_v)}"

        lbl = Label(
            text=details_text,
            markup=True,
            font_size='13sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(lbl)
        content.add_widget(scroll)

        btn_ok = Button(text="Close", font_size='14sp', size_hint_y=None, height=dp(42), background_normal='', background_color=get_color_from_hex("#2563eb"))
        popup = Popup(title="Work Update Details", content=content, size_hint=(0.88, 0.65))
        btn_ok.bind(on_release=popup.dismiss)
        content.add_widget(btn_ok)
        popup.open()

    def delete_update_item(self, record_id, sheet_name):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        content.add_widget(Label(text="Are you sure you want to delete this work update?", font_size='14sp', color=(1, 1, 1, 1), halign='center'))
        
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="Confirm Deletion", content=content, size_hint=(0.85, 0.35))
        
        def _do_del(x):
            popup.dismiss()
            if 'delete_work_update' in globals():
                ok = delete_work_update(record_id, sheet_name)
                if ok:
                    self.refresh_history_list()
                    self.show_popup("Deleted", "Task record removed successfully!")
                else:
                    self.show_popup("Error", "Could not delete record.")
        
        btn_confirm = Button(text="Delete", background_color=get_color_from_hex("#dc2626"), bold=True)
        btn_confirm.bind(on_release=_do_del)
        btn_cancel = Button(text="Cancel", background_color=get_color_from_hex("#475569"))
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_confirm)
        btn_row.add_widget(btn_cancel)
        content.add_widget(btn_row)
        
        popup.open()

    # =========================================================================
    # TAB 3: WORK & PERSONAL NOTES VIEW
    # =========================================================================
    def build_notes_view(self):
        root = BoxLayout(orientation='vertical', padding=[dp(10), dp(6), dp(10), dp(6)], spacing=dp(8))

        # Top Bar: Search Input + New Note Button
        top_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(6))
        self.in_notes_search = TextInput(
            hint_text="Search notes by title, tag, or content...",
            multiline=False,
            font_size='13sp',
            size_hint_x=0.72,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(11)]
        )
        self.in_notes_search.bind(text=lambda s, val: self.refresh_notes_list())
        top_row.add_widget(self.in_notes_search)

        btn_add_note = Button(
            text="+ Note",
            font_size='13sp',
            bold=True,
            size_hint_x=0.28,
            background_normal='',
            background_color=get_color_from_hex("#10b981"),
            color=(1, 1, 1, 1)
        )
        btn_add_note.bind(on_release=lambda x: self.open_note_editor(None))
        top_row.add_widget(btn_add_note)
        root.add_widget(top_row)

        # Category Filter Bar (All, Work, Meeting, Ideas, Todo, Urgent, Personal)
        self.current_note_filter = "All"
        cat_scroll = ScrollView(size_hint_y=None, height=dp(34), do_scroll_x=True, do_scroll_y=False)
        self.cat_box = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(34), spacing=dp(6))
        self.cat_box.bind(minimum_width=self.cat_box.setter('width'))
        categories = ["All", "Work", "Meeting", "Ideas", "Todo", "Urgent", "Personal"]
        self.cat_buttons = {}
        for cat in categories:
            btn_cat = Button(
                text=cat,
                font_size='12sp',
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

        # Notes List ScrollView
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.notes_list_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4), 0, dp(12)])
        self.notes_list_layout.bind(minimum_height=self.notes_list_layout.setter('height'))
        scroll.add_widget(self.notes_list_layout)
        root.add_widget(scroll)

        return root

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

        # Sort: pinned notes first, then latest
        filtered.sort(key=lambda x: (not x.get("is_pinned", False), x.get("updated_at", x.get("created_at", ""))), reverse=False)

        if not filtered:
            msg = "No notes matching your search." if search_q else "No notes yet.\nTap '+ Note' above to capture quick thoughts, sprint memos, or meeting tasks!"
            lbl = Label(text=msg, font_size='13sp', color=get_color_from_hex("#64748b"), size_hint_y=None, height=dp(70), halign='center')
            self.notes_list_layout.add_widget(lbl)
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

        card = BoxLayout(orientation='vertical', size_hint_y=None, padding=[dp(12), dp(10), dp(12), dp(10)], spacing=dp(6))
        card.height = dp(132) if content else dp(96)

        # Row 1: Pin icon + Title + Tag Badge
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(24), spacing=dp(6))
        
        pin_prefix = "[color=#f59e0b][PIN] [/color]" if is_pinned else ""
        lbl_title = Label(
            text=f"{pin_prefix}[b]{safe_escape_markup(title)}[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.72,
            halign='left',
            valign='middle'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        row1.add_widget(lbl_title)

        tag_colors = {
            "work": "#3b82f6",
            "meeting": "#8b5cf6",
            "ideas": "#f59e0b",
            "todo": "#10b981",
            "urgent": "#ef4444",
            "personal": "#ec4899"
        }
        tag_c = tag_colors.get(tag.lower(), "#64748b")
        lbl_tag = Label(
            text=f"[b]{safe_escape_markup(tag)}[/b]",
            markup=True,
            font_size='11sp',
            color=get_color_from_hex(tag_c),
            size_hint_x=0.28,
            halign='right',
            valign='middle'
        )
        lbl_tag.bind(size=lbl_tag.setter('text_size'))
        row1.add_widget(lbl_tag)
        card.add_widget(row1)

        # Row 2: Content snippet preview
        if content:
            snippet = (content[:95] + "...") if len(content) > 95 else content
            lbl_cnt = Label(
                text=safe_escape_markup(snippet),
                font_size='13sp',
                color=get_color_from_hex("#cbd5e1"),
                size_hint_y=None,
                height=dp(30),
                halign='left',
                valign='top'
            )
            lbl_cnt.bind(size=lbl_cnt.setter('text_size'))
            card.add_widget(lbl_cnt)

        # Row 3: Action Buttons (Edit, Share, Pin, Delete)
        row_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
        
        lbl_time = Label(
            text=time_str,
            font_size='10sp',
            color=get_color_from_hex("#64748b"),
            size_hint_x=0.32,
            halign='left',
            valign='middle'
        )
        lbl_time.bind(size=lbl_time.setter('text_size'))
        row_acts.add_widget(lbl_time)

        btn_edit = Button(text="Edit", font_size='11sp', bold=True, size_hint_x=0.18, background_normal='', background_color=get_color_from_hex("#334155"))
        btn_edit.bind(on_release=lambda x, n=note: self.open_note_editor(n))
        row_acts.add_widget(btn_edit)

        btn_share = Button(text="Share", font_size='11sp', bold=True, size_hint_x=0.20, background_normal='', background_color=get_color_from_hex("#8b5cf6"))
        btn_share.bind(on_release=lambda x, n=note: self.share_note_to_chat(n))
        row_acts.add_widget(btn_share)

        btn_pin = Button(text="Unpin" if is_pinned else "Pin", font_size='11sp', bold=True, size_hint_x=0.16, background_normal='', background_color=get_color_from_hex("#0284c7"))
        btn_pin.bind(on_release=lambda x, nid=note_id: self.toggle_note_pin(nid))
        row_acts.add_widget(btn_pin)

        btn_del = Button(text="Del", font_size='11sp', bold=True, size_hint_x=0.14, background_normal='', background_color=get_color_from_hex("#dc2626"))
        btn_del.bind(on_release=lambda x, nid=note_id: self.delete_note_item(nid))
        row_acts.add_widget(btn_del)

        card.add_widget(row_acts)
        return card

    def open_note_editor(self, note=None):
        is_edit = note is not None
        note_id = note.get("id") if is_edit else uuid.uuid4().hex[:10]

        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        content.add_widget(self._create_field_label("Note Title:"))
        in_title = TextInput(
            text=note.get("title", "") if is_edit else "",
            hint_text="e.g. Sprint Tasks, Client Feedback, Standup Agenda",
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        content.add_widget(in_title)

        row_tag = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
        row_tag.add_widget(Label(text="Category:", font_size='13sp', color=(1, 1, 1, 1), size_hint_x=0.35, halign='left', valign='middle'))
        sp_tag = Spinner(
            text=note.get("tag", "Work") if is_edit else "Work",
            values=('Work', 'Meeting', 'Ideas', 'Todo', 'Urgent', 'Personal'),
            font_size='13sp',
            size_hint_x=0.65,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        row_tag.add_widget(sp_tag)
        content.add_widget(row_tag)

        content.add_widget(self._create_field_label("Note Details / Content:"))
        in_content = TextInput(
            text=note.get("content", "") if is_edit else "",
            hint_text="Type or paste your notes here...",
            multiline=True,
            font_size='13sp',
            size_hint_y=None,
            height=dp(170),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)]
        )
        content.add_widget(in_content)

        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(6))
        popup = Popup(title="Edit Note" if is_edit else "Create New Note", content=content, size_hint=(0.92, 0.75))

        def _do_save_note(x):
            t_val = in_title.text.strip()
            c_val = in_content.text.strip()
            tag_val = sp_tag.text

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
                        n["updated_at"] = now_str
                        break
            else:
                new_n = {
                    "id": note_id,
                    "title": t_val,
                    "content": c_val,
                    "tag": tag_val,
                    "is_pinned": False,
                    "created_at": now_str,
                    "updated_at": now_str
                }
                notes.insert(0, new_n)

            if 'save_notes' in globals():
                save_notes(notes)

            popup.dismiss()
            self.refresh_notes_list()

        btn_save = Button(text="Save Note", font_size='14sp', bold=True, background_normal='', background_color=get_color_from_hex("#10b981"))
        btn_save.bind(on_release=_do_save_note)
        btn_row.add_widget(btn_save)

        if Clipboard is not None:
            btn_copy = Button(text="Copy", font_size='13sp', bold=True, background_normal='', background_color=get_color_from_hex("#0284c7"))
            def _do_copy(x):
                txt = f"{in_title.text.strip()}\n\n{in_content.text.strip()}"
                try:
                    Clipboard.copy(txt)
                    self.show_popup("Copied", "Note text copied to clipboard!")
                except Exception:
                    pass
            btn_copy.bind(on_release=_do_copy)
            btn_row.add_widget(btn_copy)

        btn_cancel = Button(text="Cancel", font_size='13sp', background_normal='', background_color=get_color_from_hex("#475569"))
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_cancel)

        content.add_widget(btn_row)
        popup.open()

    def share_note_to_chat(self, note):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat is not initialized.")
            return

        title = note.get("title", "")
        tag = note.get("tag", "Work")
        content = note.get("content", "")

        msg = f"[NOTE] [b]Shared Note: {title}[/b]  ([color=#38bdf8]{tag}[/color])\n{content}"
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

    def delete_note_item(self, note_id):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        content.add_widget(Label(text="Are you sure you want to delete this note?", font_size='14sp', color=(1, 1, 1, 1), halign='center'))
        
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="Confirm Deletion", content=content, size_hint=(0.85, 0.35))

        def _do_del(x):
            popup.dismiss()
            notes = load_notes() if 'load_notes' in globals() else []
            updated = [n for n in notes if n.get("id") != note_id]
            if 'save_notes' in globals():
                save_notes(updated)
            self.refresh_notes_list()

        btn_confirm = Button(text="Delete", background_color=get_color_from_hex("#dc2626"), bold=True)
        btn_confirm.bind(on_release=_do_del)
        btn_cancel = Button(text="Cancel", background_color=get_color_from_hex("#475569"))
        btn_cancel.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_confirm)
        btn_row.add_widget(btn_cancel)
        content.add_widget(btn_row)
        popup.open()

    # =========================================================================
    # TAB 4: LAN TEAM CHAT VIEW
    # =========================================================================
    def build_chat_view(self):
        container = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # Chat Header Status Card
        chat_top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=[dp(6), dp(4), dp(6), dp(4)], spacing=dp(4))
        
        self.lbl_chat_status = Label(
            text="Connecting to LAN...",
            font_size='11sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.24,
            halign='left',
            valign='middle'
        )
        self.lbl_chat_status.bind(size=self.lbl_chat_status.setter('text_size'))
        chat_top.add_widget(self.lbl_chat_status)

        self.btn_team_ctrl = Button(
            text="Team (0)",
            font_size='11sp',
            bold=True,
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        self.btn_team_ctrl.bind(on_release=self.open_online_team_popup)
        chat_top.add_widget(self.btn_team_ctrl)

        btn_share_file = Button(
            text="Send File",
            font_size='11sp',
            bold=True,
            size_hint_x=0.20,
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        btn_share_file.bind(on_release=self.open_file_picker_popup)
        chat_top.add_widget(btn_share_file)

        btn_share_task = Button(
            text="Tasks",
            font_size='11sp',
            bold=True,
            size_hint_x=0.14,
            background_normal='',
            background_color=get_color_from_hex("#8b5cf6"),
            color=(1, 1, 1, 1)
        )
        btn_share_task.bind(on_release=self.share_today_tasks_to_chat)
        chat_top.add_widget(btn_share_task)

        btn_add_ip = Button(
            text="+ IP",
            font_size='11sp',
            bold=True,
            size_hint_x=0.10,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_add_ip.bind(on_release=self.open_custom_ip_popup)
        chat_top.add_widget(btn_add_ip)

        btn_rescan = Button(
            text="Rescan",
            font_size='11sp',
            bold=True,
            size_hint_x=0.12,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_rescan.bind(on_release=self.rescan_lan_network)
        chat_top.add_widget(btn_rescan)

        container.add_widget(chat_top)

        # Active Team Strip (Horizontal Scroll of Online Members)
        self.team_strip_scroll = ScrollView(size_hint_y=None, height=dp(36), do_scroll_x=True, do_scroll_y=False)
        self.team_strip_layout = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(36), spacing=dp(6), padding=[dp(8), dp(2), dp(8), dp(4)])
        self.team_strip_layout.bind(minimum_width=self.team_strip_layout.setter('width'))
        self.team_strip_scroll.add_widget(self.team_strip_layout)
        container.add_widget(self.team_strip_scroll)

        # DM Status Banner (hidden by default, shows when inside 1-on-1 private chat)
        self.dm_banner_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(0), opacity=0, padding=[dp(8), dp(4)], spacing=dp(6))
        self.dm_banner_lbl = Label(
            text="Private Chat",
            font_size='12sp',
            bold=True,
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.75,
            halign='left',
            valign='middle'
        )
        self.dm_banner_lbl.bind(size=self.dm_banner_lbl.setter('text_size'))
        self.dm_banner_layout.add_widget(self.dm_banner_lbl)

        btn_exit_dm = Button(
            text="✕ Public Room",
            font_size='11sp',
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_exit_dm.bind(on_release=lambda x: self.switch_to_dm(None))
        self.dm_banner_layout.add_widget(btn_exit_dm)
        container.add_widget(self.dm_banner_layout)

        # Chat Message Stream ScrollView
        self.chat_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.chat_list_layout = GridLayout(cols=1, spacing=dp(8), padding=[dp(10), dp(8), dp(10), dp(8)], size_hint_y=None)
        self.chat_list_layout.bind(minimum_height=self.chat_list_layout.setter('height'))
        self.chat_scroll.add_widget(self.chat_list_layout)
        container.add_widget(self.chat_scroll)

        # Chat Input Bottom Bar (with soft-keyboard lift support)
        self.chat_input_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(54), padding=[dp(6), dp(4), dp(6), dp(6)], spacing=dp(6))
        
        btn_attach = Button(
            text="+ File",
            font_size='12sp',
            bold=True,
            size_hint_x=0.16,
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
            size_hint_x=0.66,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(12)]
        )
        self.in_chat_msg.bind(on_text_validate=self.send_chat_message)
        self.in_chat_msg.bind(focus=self._on_chat_input_focus)
        self.chat_input_bar.add_widget(self.in_chat_msg)

        btn_send = Button(
            text="Send",
            font_size='15sp',
            bold=True,
            size_hint_x=0.20,
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

        user_name = self.settings.get("user_name", "Mobile User")
        try:
            self.chat_engine = LANChatEngine(
                user_name=user_name,
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
        my_id = self.chat_engine.user_id if self.chat_engine else ""

        is_relevant = False
        if self.active_dm_peer:
            target_id = self.active_dm_peer.get("id")
            if (r_id == target_id and s_id == my_id) or (r_id == my_id and s_id == target_id):
                is_relevant = True
        else:
            if not r_id:
                is_relevant = True

        if is_relevant:
            if self.current_tab != "chat":
                self.unread_chat_count += 1
                self.btn_tab_chat.text = f"Team Chat ({self.unread_chat_count})"
            else:
                self.add_message_bubble(msg_dict)
                Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

    def switch_to_dm(self, peer=None):
        """Switches between Public Team Room and 1-on-1 Private Direct Message."""
        self.active_dm_peer = peer
        if hasattr(self, 'dm_banner_layout'):
            if peer:
                p_name = peer.get('user_name', 'Colleague')
                p_ip = peer.get('ip', '')
                self.dm_banner_lbl.text = f"Private Chat with {p_name} ({p_ip})"
                self.dm_banner_layout.height = dp(34)
                self.dm_banner_layout.opacity = 1
                if hasattr(self, 'in_chat_msg') and self.in_chat_msg:
                    self.in_chat_msg.hint_text = f"Message {p_name} (Private)..."
            else:
                self.dm_banner_layout.height = dp(0)
                self.dm_banner_layout.opacity = 0
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
        txt = f"IP: {ip} | Peers: {peer_cnt}"
        if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
            self.lbl_chat_status.text = txt

        chip_txt = f"{peer_cnt} Online" if peer_cnt > 0 else f"{ip}"
        if hasattr(self, 'btn_online_chip') and self.btn_online_chip:
            self.btn_online_chip.text = chip_txt

        if hasattr(self, 'btn_team_ctrl') and self.btn_team_ctrl:
            self.btn_team_ctrl.text = f"Team ({peer_cnt})"

        # Rebuild Active Team Strip
        if hasattr(self, 'team_strip_layout') and self.team_strip_layout:
            self.team_strip_layout.clear_widgets()

            b_all = Button(
                text="Public Room",
                font_size='11sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(96), dp(30)),
                background_normal='',
                background_color=get_color_from_hex("#2563eb" if self.active_dm_peer is None else "#334155"),
                color=(1, 1, 1, 1)
            )
            b_all.bind(on_release=lambda x: self.switch_to_dm(None))
            self.team_strip_layout.add_widget(b_all)

            for peer in self.chat_engine.peers.values():
                p_name = peer.get("user_name", "Peer")
                p_ip = peer.get("ip", "")
                is_active = bool(self.active_dm_peer and self.active_dm_peer.get("id") == peer.get("id"))
                b_peer = Button(
                    text=f"● {p_name} ({p_ip})",
                    font_size='11sp',
                    bold=True,
                    size_hint=(None, None),
                    size=(dp(max(110, len(p_name)*8 + 80)), dp(30)),
                    background_normal='',
                    background_color=get_color_from_hex("#059669" if is_active else "#1e293b"),
                    color=get_color_from_hex("#ffffff" if is_active else "#34d399")
                )
                b_peer.bind(on_release=lambda x, p=peer: self.switch_to_dm(p))
                self.team_strip_layout.add_widget(b_peer)

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
            text=f"IP: {my_ip} • [color=#34d399]Host / Online[/color]",
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
                text="No colleagues found on this Wi-Fi network yet.\n\nTips:\n• Ensure phones/PCs are connected to same Wi-Fi or Hotspot.\n• Check firewall or tap '+ Add IP' if on another subnet.\n• Tap 'Rescan' to broadcast discovery beacon.",
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
                    text=f"IP: {p_ip} • [color=#34d399]Online[/color] ({p_host})",
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
            peer_id = self.active_dm_peer.get("id")
            my_id = self.chat_engine.user_id
            for msg in self.chat_engine.messages:
                r_id = msg.get("recipient_id", "")
                s_id = msg.get("sender_id", "")
                if (r_id == peer_id and s_id == my_id) or (r_id == my_id and s_id == peer_id):
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

        is_me = msg.get("is_me", False) or (self.chat_engine and msg.get("sender_id") == self.chat_engine.user_id)
        msg_type = msg.get("type", "text")
        sender = safe_escape_markup(msg.get("user_name", "Anonymous"))
        time_s = safe_escape_markup(msg.get("time_str", ""))

        bubble = BoxLayout(orientation='vertical', size_hint_y=None, padding=dp(8), spacing=dp(4))
        
        # Sender & Time Header
        header_color = "#38bdf8" if is_me else "#f59e0b"
        sender_lbl = Label(
            text=f"[color={header_color}][b]{sender}[/b][/color]  [color=#64748b]{time_s}[/color]",
            markup=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(18),
            halign='right' if is_me else 'left'
        )
        sender_lbl.bind(size=sender_lbl.setter('text_size'))
        bubble.add_widget(sender_lbl)

        # Message Content
        use_markup = False
        btn_action = None
        if msg_type == "work_update":
            title = safe_escape_markup(msg.get("title", "Daily Work Update"))
            tasks = msg.get("tasks", [])
            task_lines = "\n".join([f"• {safe_escape_markup(t.get('title', ''))} ({safe_escape_markup(t.get('hours', ''))}h)" for t in tasks[:3]])
            body_text = f"[b]{title}[/b]\n{task_lines}"
            body_color = "#e2e8f0"
            use_markup = True
        elif msg_type == "file":
            fn = msg.get("file_name", "Shared File")
            fn_safe = safe_escape_markup(fn)
            fs_str = safe_escape_markup(msg.get("file_size_str") or format_file_size(msg.get("file_size", 0)))
            caption = safe_escape_markup(msg.get("caption", "").strip())
            file_id = msg.get("file_id", "")
            is_image = msg.get("is_image", False) or (is_image_file(fn) if 'is_image_file' in globals() else False)

            local_p = self.get_file_local_path(msg)
            has_local = bool(local_p and os.path.isfile(local_p))

            # Desktop-style File Card widget container
            card = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[dp(10), dp(8), dp(10), dp(8)])

            # Row 1: File Type Badge + File Name & Metadata
            top_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
            
            badge_info = self.get_file_type_badge(fn)
            lbl_badge = Button(
                text=f"[b]{badge_info['icon_txt']}[/b]",
                markup=True,
                font_size='10sp',
                bold=True,
                size_hint=(None, None),
                size=(dp(42), dp(36)),
                background_normal='',
                background_color=get_color_from_hex(badge_info['color']),
                color=(1, 1, 1, 1),
                disabled=True,
                disabled_color=(1, 1, 1, 1)
            )
            top_box.add_widget(lbl_badge)

            info_col = BoxLayout(orientation='vertical', size_hint_x=1, spacing=dp(2))
            lbl_name = Label(
                text=f"[b]{fn_safe}[/b]",
                markup=True,
                font_size='13sp',
                color=get_color_from_hex("#f8fafc"),
                size_hint_y=None,
                height=dp(20),
                halign='left',
                valign='middle',
                shorten=True,
                shorten_from='right'
            )
            lbl_name.bind(size=lbl_name.setter('text_size'))
            info_col.add_widget(lbl_name)

            sub_txt = f"{fs_str} • Shared by you" if is_me else f"{fs_str} • LAN Transfer"
            if has_local:
                sub_txt = f"[color=#10b981][b]SAVED[/b][/color]  [color=#94a3b8]{fs_str}[/color]"
            lbl_meta = Label(
                text=sub_txt,
                markup=True,
                font_size='11sp',
                color=get_color_from_hex("#94a3b8"),
                size_hint_y=None,
                height=dp(18),
                halign='left',
                valign='middle'
            )
            lbl_meta.bind(size=lbl_meta.setter('text_size'))
            info_col.add_widget(lbl_meta)
            top_box.add_widget(info_col)
            card.add_widget(top_box)

            # Optional Caption
            if caption:
                lbl_cap = Label(
                    text=f"[i]{caption}[/i]",
                    markup=True,
                    font_size='12sp',
                    color=get_color_from_hex("#cbd5e1"),
                    size_hint_y=None,
                    height=dp(20),
                    halign='left',
                    valign='middle'
                )
                lbl_cap.bind(size=lbl_cap.setter('text_size'))
                card.add_widget(lbl_cap)

            # Local Image Preview if already downloaded
            if is_image and has_local and Image is not None and Image is not object:
                try:
                    img_w = Image(source=local_p, size_hint_y=None, height=dp(150), allow_stretch=True, keep_ratio=True)
                    card.add_widget(img_w)
                except Exception:
                    pass

            # Buttons Row
            btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(8))
            
            if has_local:
                btn_open = Button(
                    text="VIEW / OPEN FILE",
                    font_size='13sp',
                    bold=True,
                    size_hint_x=1,
                    background_normal='',
                    background_color=get_color_from_hex("#0284c7"),
                    color=(1, 1, 1, 1)
                )
                btn_open.bind(on_release=lambda x, p=local_p: self.open_file_externally(p))
                btn_row.add_widget(btn_open)
            else:
                ext_l = os.path.splitext(fn)[1].lower()
                is_media = ext_l in ('.mp4', '.mkv', '.avi', '.mov', '.3gp', '.mp3', '.wav', '.m4a', '.ogg', '.flac')
                view_txt = "PLAY VIDEO" if ext_l in ('.mp4', '.mkv', '.avi', '.mov') else ("PLAY AUDIO" if is_media else "VIEW FILE")

                btn_view = Button(
                    text=view_txt,
                    font_size='12sp',
                    bold=True,
                    size_hint_x=0.48,
                    background_normal='',
                    background_color=get_color_from_hex("#8b5cf6"),
                    color=(1, 1, 1, 1)
                )
                btn_dl = Button(
                    text="DOWNLOAD",
                    font_size='12sp',
                    bold=True,
                    size_hint_x=0.52,
                    background_normal='',
                    background_color=get_color_from_hex("#059669"),
                    color=(1, 1, 1, 1)
                )

                def _start_view(btn_inst, m=msg, r=btn_row, meta=lbl_meta):
                    btn_view.disabled = True
                    btn_dl.disabled = True
                    btn_view.text = "Loading..."
                    self.download_and_handle_file(m, is_preview=True, on_complete_open=True, btn_row=r, meta_lbl=meta)

                def _start_download(btn_inst, m=msg, r=btn_row, meta=lbl_meta):
                    btn_view.disabled = True
                    btn_dl.disabled = True
                    btn_dl.text = "Downloading..."
                    self.download_and_handle_file(m, is_preview=False, on_complete_open=False, btn_row=r, meta_lbl=meta)

                btn_view.bind(on_release=_start_view)
                btn_dl.bind(on_release=_start_download)
                btn_row.add_widget(btn_view)
                btn_row.add_widget(btn_dl)

            card.add_widget(btn_row)

            # Compute Card & Bubble Height
            c_height = dp(42) + dp(38) + dp(14)
            if caption:
                c_height += dp(22)
            if is_image and has_local and Image is not None and Image is not object:
                c_height += dp(156)
            card.height = c_height

            bubble.add_widget(card)
            bubble.height = dp(24) + c_height + dp(8)
            self.chat_list_layout.add_widget(bubble)
            return
        else:
            body_text = msg.get("text", "")
            body_color = "#ffffff"
            use_markup = False

        content_lbl = Label(
            text=body_text,
            markup=use_markup,
            font_size='14sp',
            color=get_color_from_hex(body_color),
            size_hint_y=None,
            halign='right' if is_me else 'left'
        )
        content_lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        content_lbl.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(24), ts[1])))
        bubble.add_widget(content_lbl)

        if btn_action:
            bubble.add_widget(btn_action)
            bubble.height = dp(24) + content_lbl.height + dp(40)
        else:
            bubble.height = dp(24) + content_lbl.height + dp(10)
        self.chat_list_layout.add_widget(bubble)

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
        p = os.path.join(get_storage_dir(), "cache")
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
                    btn_open = Button(
                        text="VIEW / OPEN FILE",
                        font_size='13sp',
                        bold=True,
                        size_hint_x=1,
                        background_normal='',
                        background_color=get_color_from_hex("#0284c7"),
                        color=(1, 1, 1, 1)
                    )
                    btn_open.bind(on_release=lambda x, p=saved_path: self.open_file_externally(p))
                    btn_row.add_widget(btn_open)

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
        content = GridLayout(cols=1, spacing=dp(10), padding=[dp(12), dp(8), dp(12), dp(20)], size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # Quick Presets
        content.add_widget(self._create_field_label("1-Click Quick Presets:"))
        row_p1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        presets = [("10m", 10), ("15m", 15), ("30m", 30), ("1h", 60), ("2h", 120)]
        for lbl, mins in presets:
            btn_p = Button(text=lbl, font_size='13sp', background_normal='', background_color=get_color_from_hex("#0284c7"), color=(1, 1, 1, 1), bold=True)
            btn_p.bind(on_release=lambda x, m=mins: self.apply_preset_mins(m))
            row_p1.add_widget(btn_p)
        content.add_widget(row_p1)

        # Shift Presets
        content.add_widget(self._create_field_label("Shift Reminders:"))
        row_p2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        shift_presets = [("10:00 AM", "10:00 AM"), ("01:00 PM", "01:00 PM"), ("04:30 PM", "04:30 PM"), ("07:00 PM", "07:00 PM")]
        for lbl, t_v in shift_presets:
            btn_s = Button(text=lbl, font_size='13sp', background_normal='', background_color=get_color_from_hex("#d97706"), color=(1, 1, 1, 1), bold=True)
            btn_s.bind(on_release=lambda x, t=t_v: self.apply_preset_time(t))
            row_p2.add_widget(btn_s)
        content.add_widget(row_p2)

        # Schedule Custom Reminder Form
        content.add_widget(self._create_field_label("Schedule Custom Reminder:"))
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
        content.add_widget(self.in_rem_title)

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
        content.add_widget(row_dt)

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
        content.add_widget(row_rep_btn)

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
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))

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

        # Title bar with Close 'X'
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36), spacing=dp(8))
        lbl_modal_title = Label(
            text="[b]Work Logger & Shift Configuration[/b]",
            markup=True,
            font_size='15sp',
            color=get_color_from_hex("#38bdf8"),
            halign='left',
            valign='middle'
        )
        lbl_modal_title.bind(size=lbl_modal_title.setter('text_size'))
        title_bar.add_widget(lbl_modal_title)

        btn_close_x = Button(
            text="✕",
            font_size='14sp',
            bold=True,
            size_hint_x=None,
            width=dp(36),
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        title_bar.add_widget(btn_close_x)
        root_box.add_widget(title_bar)

        # Tab Navigation Bar (Horizontal ScrollView)
        tab_scroll = ScrollView(size_hint=(1, None), height=dp(40), do_scroll_x=True, do_scroll_y=False)
        tab_bar = BoxLayout(orientation='horizontal', size_hint_x=None, height=dp(38), spacing=dp(6))
        tab_bar.bind(minimum_width=tab_bar.setter('width'))
        tab_scroll.add_widget(tab_bar)
        root_box.add_widget(tab_scroll)

        # Content ScrollView & Container
        content_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content_container = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), padding=[dp(4), dp(4), dp(4), dp(10)])
        content_container.bind(minimum_height=content_container.setter('height'))
        content_scroll.add_widget(content_container)
        root_box.add_widget(content_scroll)

        # Helper to create inputs with consistent dark styling
        def _make_input(val="", hint="", multiline=False, height_dp=42):
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
                padding=[dp(10), dp(10)]
            )

        # Helper to create toggle buttons
        def _make_toggle(label_prefix, key, on_color="#059669", off_color="#334155", on_text="ON", off_text="OFF"):
            btn = Button(
                text=f"{label_prefix}: {on_text if state[key] else off_text}",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(40),
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

        # ---------------- TAB DEFINITIONS ----------------
        tab_names = [
            ("General & Shifts", "#2563eb"),
            ("Weekly Off & Holidays", "#0284c7"),
            ("Data API / Webhook", "#0f766e"),
            ("Google Sheet", "#059669"),
            ("Reminders & Schedule", "#7c3aed")
        ]
        tab_buttons = []
        active_tab_idx = [0]

        # Builders for each tab
        def _build_general_tab():
            content_container.clear_widgets()

            content_container.add_widget(self._create_field_label("Your Name / Handle (Identity in LAN Chat):"))
            content_container.add_widget(in_user_name)

            content_container.add_widget(self._create_field_label("Default Project:"))
            content_container.add_widget(in_def_proj)

            content_container.add_widget(self._create_field_label("Default Shift (Login - Logout):"))
            row_s1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
            row_s1.add_widget(in_login_t)
            row_s1.add_widget(in_logout_t)
            content_container.add_widget(row_s1)

            content_container.add_widget(self._create_field_label("Default Breaks (Lunch & Tea):"))
            row_s2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
            row_s2.add_widget(in_lunch)
            row_s2.add_widget(in_tea)
            content_container.add_widget(row_s2)

            content_container.add_widget(self._create_field_label("Team Notification Platform:"))
            row_plat = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(5))
            platforms = ["Microsoft Teams", "Slack / Discord", "Custom Webhook"]
            plat_btns = []
            for p in platforms:
                p_btn = Button(
                    text=p.split()[0] if p != "Slack / Discord" else "Slack/Disc",
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
            content_container.add_widget(row_plat)

            content_container.add_widget(self._create_field_label("Incoming Webhook URL:"))
            content_container.add_widget(in_webhook_url)

            # Webhook test button
            btn_test_wh = Button(
                text="Send Test Webhook Message",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(38),
                background_normal='',
                background_color=get_color_from_hex("#0284c7"),
                color=(1, 1, 1, 1)
            )
            def _do_test_wh(b):
                wh_url = in_webhook_url.text.strip()
                if not wh_url:
                    self.show_popup("Notice", "Please enter an Incoming Webhook URL first.")
                    return
                b.text = "Sending test..."
                b.disabled = True
                def _thread_wh():
                    if 'send_webhook_message' in globals():
                        ok, msg = send_webhook_message(wh_url, "Test message from WorkPulse Mobile! Webhook connection verified successfully.", state["platform"])
                        def _res(dt):
                            b.text = "Send Test Webhook Message"
                            b.disabled = False
                            self.show_popup("Webhook Test", f"{'SUCCESS' if ok else 'FAILED'}:\n\n{msg}")
                        Clock.schedule_once(_res, 0)
                    else:
                        def _err(dt):
                            b.text = "Send Test Webhook Message"
                            b.disabled = False
                            self.show_popup("Notice", "Webhook module not available.")
                        Clock.schedule_once(_err, 0)
                threading.Thread(target=_thread_wh, daemon=True).start()
            btn_test_wh.bind(on_release=_do_test_wh)
            content_container.add_widget(btn_test_wh)

            content_container.add_widget(self._create_field_label("Automation Preferences:"))
            content_container.add_widget(_make_toggle("Open Team Share on Save", "prompt_team_share", on_color="#059669"))
            content_container.add_widget(_make_toggle("Auto-copy Markdown Summary on Save", "auto_copy", on_color="#0284c7"))

        def _build_holidays_tab():
            content_container.clear_widgets()

            content_container.add_widget(self._create_field_label("1. Weekly Off Days (Weekends):"))
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
            content_container.add_widget(row_days)

            content_container.add_widget(_make_toggle("Include 2nd & 4th Saturday", "sec_fourth_sat", on_color="#0f766e", on_text="YES", off_text="NO"))

            content_container.add_widget(self._create_field_label("2. Company & National Holidays:"))
            row_date = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
            row_date.add_widget(in_hol_date)
            btn_today = Button(
                text="Today",
                font_size='12sp',
                bold=True,
                size_hint_x=None,
                width=dp(68),
                background_normal='',
                background_color=get_color_from_hex("#475569")
            )
            btn_today.bind(on_release=lambda x: setattr(in_hol_date, 'text', datetime.date.today().strftime("%Y-%m-%d")))
            row_date.add_widget(btn_today)
            content_container.add_widget(row_date)

            content_container.add_widget(in_hol_name)

            row_h_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(6))
            btn_add_hol = Button(
                text="+ Add Holiday",
                font_size='12sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#2563eb")
            )
            btn_load_ind = Button(
                text="Load Indian Holidays",
                font_size='12sp',
                bold=True,
                size_hint_x=0.5,
                background_normal='',
                background_color=get_color_from_hex("#d97706")
            )
            row_h_acts.add_widget(btn_add_hol)
            row_h_acts.add_widget(btn_load_ind)
            content_container.add_widget(row_h_acts)

            # Holidays dynamic list container
            hol_list_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
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
                    h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))

                    lbl_info = Label(
                        text=f"[b]{d_str}[/b] • [color=#94a3b8]{w_day}[/color]  [color=#38bdf8]{safe_escape_markup(n_str)}[/color]",
                        markup=True,
                        font_size='12sp',
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
                        width=dp(48),
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
                font_size='13sp',
                color=get_color_from_hex("#38bdf8"),
                size_hint_y=None,
                height=dp(26),
                halign='left',
                valign='middle'
            )
            lbl_h_count.bind(size=lbl_h_count.setter('text_size'))
            content_container.add_widget(lbl_h_count)
            content_container.add_widget(hol_list_box)

            # Sync to monthly sheet action
            btn_sync_sheet = Button(
                text="Sync Holidays & Weekly Offs to Sheet",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(40),
                background_normal='',
                background_color=get_color_from_hex("#7c3aed")
            )
            def _do_sync_sheet(b):
                if 'sync_month_holidays_and_weekly_offs' in globals():
                    try:
                        h_c, o_c, s_n = sync_month_holidays_and_weekly_offs(getattr(self, 'current_month', None))
                        self.show_popup("Sync Complete", f"Sheet '{s_n}' updated:\n• Added Holidays: {h_c}\n• Added Weekly Offs: {o_c}")
                    except Exception as ex:
                        self.show_popup("Error", f"Failed to sync to sheet: {ex}")
                else:
                    self.show_popup("Notice", "Sheet sync function not available.")
            btn_sync_sheet.bind(on_release=_do_sync_sheet)
            content_container.add_widget(btn_sync_sheet)

            _refresh_hol_ui()

        def _build_data_api_tab():
            content_container.clear_widgets()

            content_container.add_widget(self._create_field_label("API / Webhook URL Endpoint:"))
            content_container.add_widget(in_api_url)

            content_container.add_widget(self._create_field_label("Bearer Token / Secret API Key:"))
            content_container.add_widget(in_api_token)

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
                            self.show_popup("API Connection Result", f"{'SUCCESS' if ok else 'FAILED'}\n\n• Code: {code}\n• Response:\n{msg}")
                        Clock.schedule_once(_res, 0)
                    else:
                        def _err(dt):
                            b.text = "Send Test Ping to API"
                            b.disabled = False
                            self.show_popup("Notice", "Data API sender function not found.")
                        Clock.schedule_once(_err, 0)
                threading.Thread(target=_thread_api, daemon=True).start()
            btn_test_api.bind(on_release=_do_test_api)
            content_container.add_widget(btn_test_api)

            content_container.add_widget(self._create_field_label("Automatic Real-Time Webhook Triggers:"))
            content_container.add_widget(_make_toggle("Send on Task Edit / Update", "api_edit", on_color="#059669"))
            content_container.add_widget(_make_toggle("Send on Task Create / Save", "api_create", on_color="#0284c7"))
            content_container.add_widget(_make_toggle("Send on Task Delete", "api_delete", on_color="#ef4444"))

        def _build_gsheet_tab():
            content_container.clear_widgets()

            content_container.add_widget(self._create_field_label("Google Sheet Web App URL:"))
            content_container.add_widget(in_gsheet_url)

            btn_test_gs = Button(
                text="Test Sheet Connection",
                font_size='12sp',
                bold=True,
                size_hint_y=None,
                height=dp(40),
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
            content_container.add_widget(btn_test_gs)

            content_container.add_widget(self._create_field_label("Synchronization Preferences:"))
            content_container.add_widget(_make_toggle("Auto-Sync on Save", "gsheet_sync", on_color="#059669"))
            content_container.add_widget(_make_toggle("Startup Fetch Priority", "gsheet_fetch", on_color="#0284c7"))

            # Direct sync & fetch buttons
            row_gs_acts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(6))
            btn_sync_now = Button(
                text="Sync Month Now",
                font_size='12sp',
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
                font_size='12sp',
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
            content_container.add_widget(row_gs_acts)

        def _build_reminders_tab():
            content_container.clear_widgets()

            content_container.add_widget(self._create_field_label("Scheduler System Controls:"))
            content_container.add_widget(_make_toggle("Reminders System", "rem_enabled", on_color="#2563eb", on_text="ENABLED", off_text="DISABLED"))
            content_container.add_widget(_make_toggle("Play Audio Chime Sound", "rem_sound", on_color="#7c3aed"))
            content_container.add_widget(_make_toggle("Show System Notifications", "rem_notify", on_color="#059669"))
            content_container.add_widget(_make_toggle("Daily Shift Alerts (Login, Lunch, Tea, Standup)", "rem_daily", on_color="#0f766e"))
            content_container.add_widget(_make_toggle("Skip Alerts on Weekends & Holidays", "rem_skip", on_color="#d97706", on_text="YES", off_text="NO"))

            btn_test_alert = Button(
                text="Test Alert Now (Ringtone & Notification)",
                font_size='13sp',
                bold=True,
                size_hint_y=None,
                height=dp(44),
                background_normal='',
                background_color=get_color_from_hex("#7c3aed")
            )
            btn_test_alert.bind(on_release=lambda x: self.test_alert_now())
            content_container.add_widget(btn_test_alert)

        tab_builders = [
            _build_general_tab,
            _build_holidays_tab,
            _build_data_api_tab,
            _build_gsheet_tab,
            _build_reminders_tab
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
            tab_builders[idx]()
            content_scroll.scroll_y = 1.0

        for idx, (t_name, t_color) in enumerate(tab_names):
            t_btn = Button(
                text=t_name,
                font_size='12sp',
                bold=True,
                size_hint_x=None,
                height=dp(38),
                background_normal='',
                background_color=get_color_from_hex(t_color if idx == 0 else "#1e293b"),
                color=(1, 1, 1, 1) if idx == 0 else get_color_from_hex("#94a3b8"),
                padding=[dp(12), dp(6)]
            )
            t_btn.width = dp(max(100, len(t_name) * 8 + 24))
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

        # Initial render of Tab 0
        _build_general_tab()
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
