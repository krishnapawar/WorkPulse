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
    BoxLayout = GridLayout = ScrollView = Label = TextInput = Button = Spinner = Popup = Window = Clock = object
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
        get_available_months, load_month_records, delete_work_update
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
        LANChatEngine, get_network_info, get_avatar_color, get_initials, format_file_size
    )
except Exception as e:
    print(f"Warning: lan_chat import: {e}")
    LANChatEngine = None
    get_network_info = None
    get_avatar_color = None
    get_initials = None
    def format_file_size(b): return f"{b} B"


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

        # Main Root Container
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # 1. Top Header App Bar
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=[dp(10), dp(4), dp(10), dp(4)], spacing=dp(6))
        
        lbl_app = Label(
            text="[b]WorkPulse[/b] [color=#38bdf8]Mobile[/color]",
            markup=True,
            font_size='18sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.52,
            halign='left',
            valign='middle'
        )
        lbl_app.bind(size=lbl_app.setter('text_size'))
        header.add_widget(lbl_app)

        self.lbl_net_chip = Label(
            text="Online",
            font_size='11sp',
            color=get_color_from_hex("#34d399"),
            size_hint_x=0.34,
            halign='right',
            valign='middle'
        )
        self.lbl_net_chip.bind(size=self.lbl_net_chip.setter('text_size'))
        header.add_widget(self.lbl_net_chip)

        btn_settings = Button(
            text="⚙️",
            font_size='17sp',
            size_hint_x=0.14,
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
        
        pin_prefix = "[color=#f59e0b]📌 [/color]" if is_pinned else ""
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

        msg = f"📝 [b]Shared Note: {title}[/b]  ([color=#38bdf8]{tag}[/color])\n{content}"
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
        chat_top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=[dp(8), dp(4), dp(8), dp(4)], spacing=dp(6))
        
        self.lbl_chat_status = Label(
            text="Connecting to LAN...",
            font_size='11sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.32,
            halign='left',
            valign='middle'
        )
        self.lbl_chat_status.bind(size=self.lbl_chat_status.setter('text_size'))
        chat_top.add_widget(self.lbl_chat_status)

        btn_share_file = Button(
            text="Send File",
            font_size='12sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#059669"),
            color=(1, 1, 1, 1)
        )
        btn_share_file.bind(on_release=self.open_file_picker_popup)
        chat_top.add_widget(btn_share_file)

        btn_share_task = Button(
            text="Tasks",
            font_size='12sp',
            bold=True,
            size_hint_x=0.18,
            background_normal='',
            background_color=get_color_from_hex("#8b5cf6"),
            color=(1, 1, 1, 1)
        )
        btn_share_task.bind(on_release=self.share_today_tasks_to_chat)
        chat_top.add_widget(btn_share_task)

        btn_add_ip = Button(
            text="+ IP",
            font_size='12sp',
            bold=True,
            size_hint_x=0.14,
            background_normal='',
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_add_ip.bind(on_release=self.open_custom_ip_popup)
        chat_top.add_widget(btn_add_ip)

        btn_rescan = Button(
            text="Rescan",
            font_size='12sp',
            bold=True,
            size_hint_x=0.14,
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1)
        )
        btn_rescan.bind(on_release=self.rescan_lan_network)
        chat_top.add_widget(btn_rescan)

        container.add_widget(chat_top)

        # Chat Message Stream ScrollView
        self.chat_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.chat_list_layout = GridLayout(cols=1, spacing=dp(8), padding=[dp(10), dp(8), dp(10), dp(8)], size_hint_y=None)
        self.chat_list_layout.bind(minimum_height=self.chat_list_layout.setter('height'))
        self.chat_scroll.add_widget(self.chat_list_layout)
        container.add_widget(self.chat_scroll)

        # Chat Input Bottom Bar (with soft-keyboard lift support)
        self.chat_input_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(54), padding=[dp(6), dp(4), dp(6), dp(6)], spacing=dp(6))
        
        btn_attach = Button(
            text="📎",
            font_size='18sp',
            size_hint_x=0.14,
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
        if self.current_tab != "chat":
            self.unread_chat_count += 1
            self.btn_tab_chat.text = f"Team Chat ({self.unread_chat_count})"
        else:
            self.add_message_bubble(msg_dict)
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

    def _update_network_status_labels(self):
        if not self.chat_engine:
            if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
                self.lbl_chat_status.text = "Offline"
            return
        ip = self.chat_engine.local_ip
        peer_cnt = len(self.chat_engine.peers)
        txt = f"IP: {ip} | Peers: {peer_cnt}"
        if hasattr(self, 'lbl_chat_status') and self.lbl_chat_status:
            self.lbl_chat_status.text = txt
        if hasattr(self, 'lbl_net_chip') and self.lbl_net_chip:
            self.lbl_net_chip.text = f"{peer_cnt} Online" if peer_cnt > 0 else f"{ip}"

    def refresh_chat_messages_ui(self):
        if not self.chat_engine:
            return
        self.chat_list_layout.clear_widgets()
        self.rendered_msg_ids.clear()
        for msg in self.chat_engine.messages[-60:]:
            self.add_message_bubble(msg)

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
            fn = safe_escape_markup(msg.get("file_name", "file"))
            fs = safe_escape_markup(msg.get("file_size_str", ""))
            body_text = f"[b]Shared File:[/b] {fn} ({fs})"
            body_color = "#93c5fd"
            use_markup = True
            if not is_me:
                btn_action = Button(
                    text=f"⬇ Download ({msg.get('file_size_str', '')})",
                    font_size='12sp',
                    bold=True,
                    size_hint_y=None,
                    height=dp(34),
                    background_normal='',
                    background_color=get_color_from_hex("#0284c7"),
                    color=(1, 1, 1, 1)
                )
                btn_action.bind(on_release=lambda x, m=msg: self.download_chat_file(m))
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
            if hasattr(self.chat_engine, "send_chat_message"):
                self.chat_engine.send_chat_message(text)
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

    def _send_picked_file(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            self.show_popup("Error", "Selected file could not be read.")
            return
        if self.chat_engine:
            try:
                msg_obj = self.chat_engine.send_file(file_path)
                if msg_obj:
                    fn = os.path.basename(file_path)
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
                text="📱 Open System Files / Gallery (Photos, Docs, Downloads)",
                font_size='12sp',
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
            text="⬆️ Up",
            font_size='12sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        path_bar.add_widget(btn_up)

        lbl_path = Label(
            text=f"📁 {start_dir}",
            font_size='11sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.78,
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
                    lbl_path.text = f"📁 {target_path}"
                    lbl_selected.text = "Tap a folder to open, or tap a file to select."
                    btn_send.text = "Send File"
                    btn_send.background_color = get_color_from_hex("#059669")
                b.bind(on_release=_do_nav)
                nav_row.add_widget(b)
        content.add_widget(nav_row)

        content.add_widget(filechooser)

        # Status / Selected item indicator
        lbl_selected = Label(
            text="💡 Tap any folder (e.g. resumes) to open. Tap a file to select.",
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
                lbl_path.text = f"📁 {parent}"
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
                    lbl_path.text = f"📁 {target}"
                    lbl_selected.text = f"Inside: [b]{os.path.basename(target)}[/b]. Tap a file to select."
                    btn_send.text = "Send File"
                    btn_send.background_color = get_color_from_hex("#059669")
            elif os.path.isfile(target):
                fn = os.path.basename(target)
                try:
                    sz_str = format_file_size(os.path.getsize(target))
                except Exception:
                    sz_str = ""
                lbl_selected.text = f"Selected: [b]{safe_escape_markup(fn)}[/b] ({sz_str})"
                btn_send.text = f"Send '{fn[:18]}...'" if len(fn) > 18 else f"Send '{fn}'"
                btn_send.background_color = get_color_from_hex("#10b981")

        filechooser.bind(selection=_on_selection_change)

        def _do_send_file(x):
            sel = filechooser.selection
            if not sel or not os.path.isfile(sel[0]):
                self.show_popup("Notice", "Please tap on a file to select it before sending.")
                return
            chosen_file = sel[0]
            popup.dismiss()
            self._send_picked_file(chosen_file)

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

    def download_chat_file(self, msg):
        if not self.chat_engine:
            self.show_popup("Notice", "LAN Chat engine is not active.")
            return

        file_name = msg.get("file_name", "downloaded_file")
        target_dir = self.get_best_download_dir()

        self.show_popup("Downloading", f"Downloading '{file_name}' from peer...")

        def _on_done(saved_path):
            Clock.schedule_once(lambda dt: self.show_popup("Download Complete", f"File saved successfully!\nLocation:\n{saved_path}"), 0)

        def _on_err(err_msg):
            Clock.schedule_once(lambda dt: self.show_popup("Download Failed", f"Could not download '{file_name}':\n{err_msg}"), 0)

        self.chat_engine.download_file(
            msg,
            target_dir=target_dir,
            on_done=_on_done,
            on_error=_on_err
        )

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
            text="🔔 Test Alert Now (Ringtone & Notification)",
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

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        form = GridLayout(cols=1, spacing=dp(10), padding=[dp(12), dp(10), dp(12), dp(16)], size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # Header Title
        form.add_widget(Label(
            text="[b]WorkPulse Settings[/b]",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_y=None,
            height=dp(28),
            halign='center'
        ))

        # 1. Profile / LAN Chat Identity
        form.add_widget(self._create_field_label("Your Name (Identity in Team Chat):"))
        in_user_name = TextInput(
            text=str(settings.get("user_name", "Developer")),
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        form.add_widget(in_user_name)

        form.add_widget(self._create_field_label("Default Project:"))
        in_def_proj = TextInput(
            text=str(settings.get("default_project", "General Work")),
            multiline=False,
            font_size='14sp',
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        form.add_widget(in_def_proj)

        # 2. Shift Timings
        form.add_widget(self._create_field_label("Default Shift Timings (Login - Logout):"))
        row_shift = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        in_login_t = TextInput(
            text=str(settings.get("default_login_time", "10:00 AM")),
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        in_logout_t = TextInput(
            text=str(settings.get("default_logout_time", "07:00 PM")),
            multiline=False,
            font_size='14sp',
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        row_shift.add_widget(in_login_t)
        row_shift.add_widget(in_logout_t)
        form.add_widget(row_shift)

        # 3. Google Sheet Integration
        form.add_widget(self._create_field_label("Google Sheet Web App URL:"))
        in_gsheet_url = TextInput(
            text=str(settings.get("gsheet_webapp_url", "")),
            multiline=False,
            font_size='13sp',
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(11)]
        )
        form.add_widget(in_gsheet_url)

        # Google Sheet Options (Auto Sync & Startup Fetch)
        is_auto_sync = settings.get("gsheet_auto_sync", True)
        is_fetch_pri = settings.get("gsheet_fetch_priority", True)

        row_gs_opts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        
        btn_tog_sync = Button(
            text=f"Auto-Sync: {'ON' if is_auto_sync else 'OFF'}",
            font_size='12sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#059669" if is_auto_sync else "#475569")
        )
        def _tog_sync(x):
            nonlocal is_auto_sync
            is_auto_sync = not is_auto_sync
            btn_tog_sync.text = f"Auto-Sync: {'ON' if is_auto_sync else 'OFF'}"
            btn_tog_sync.background_color = get_color_from_hex("#059669" if is_auto_sync else "#475569")
        btn_tog_sync.bind(on_release=_tog_sync)
        row_gs_opts.add_widget(btn_tog_sync)

        btn_tog_fetch = Button(
            text=f"Startup Fetch: {'ON' if is_fetch_pri else 'OFF'}",
            font_size='12sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#0284c7" if is_fetch_pri else "#475569")
        )
        def _tog_fetch(x):
            nonlocal is_fetch_pri
            is_fetch_pri = not is_fetch_pri
            btn_tog_fetch.text = f"Startup Fetch: {'ON' if is_fetch_pri else 'OFF'}"
            btn_tog_fetch.background_color = get_color_from_hex("#0284c7" if is_fetch_pri else "#475569")
        btn_tog_fetch.bind(on_release=_tog_fetch)
        row_gs_opts.add_widget(btn_tog_fetch)
        form.add_widget(row_gs_opts)

        # 4. Alerts & Reminders Settings
        form.add_widget(self._create_field_label("Alerts & Reminders:"))
        is_daily_on = settings.get("daily_shift_reminders_enabled", True)
        is_sound_on = settings.get("reminder_sound", True)

        row_al_opts = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_tog_daily = Button(
            text=f"Shift Alerts: {'ON' if is_daily_on else 'OFF'}",
            font_size='12sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#0f766e" if is_daily_on else "#475569")
        )
        def _tog_daily(x):
            nonlocal is_daily_on
            is_daily_on = not is_daily_on
            btn_tog_daily.text = f"Shift Alerts: {'ON' if is_daily_on else 'OFF'}"
            btn_tog_daily.background_color = get_color_from_hex("#0f766e" if is_daily_on else "#475569")
        btn_tog_daily.bind(on_release=_tog_daily)
        row_al_opts.add_widget(btn_tog_daily)

        btn_tog_sound = Button(
            text=f"Chime Sound: {'ON' if is_sound_on else 'OFF'}",
            font_size='12sp',
            bold=True,
            size_hint_x=0.5,
            background_normal='',
            background_color=get_color_from_hex("#7c3aed" if is_sound_on else "#475569")
        )
        def _tog_sound(x):
            nonlocal is_sound_on
            is_sound_on = not is_sound_on
            btn_tog_sound.text = f"Chime Sound: {'ON' if is_sound_on else 'OFF'}"
            btn_tog_sound.background_color = get_color_from_hex("#7c3aed" if is_sound_on else "#475569")
        btn_tog_sound.bind(on_release=_tog_sound)
        row_al_opts.add_widget(btn_tog_sound)
        form.add_widget(row_al_opts)

        scroll.add_widget(form)

        # Bottom Action Buttons Row
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        root_box = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(8))
        root_box.add_widget(scroll)
        root_box.add_widget(btn_row)

        popup = Popup(title="WorkPulse Settings", content=root_box, size_hint=(0.94, 0.90))

        def _do_save_settings(x):
            new_name = in_user_name.text.strip() or "Developer"
            new_proj = in_def_proj.text.strip() or "General Work"
            new_login = in_login_t.text.strip() or "10:00 AM"
            new_logout = in_logout_t.text.strip() or "07:00 PM"
            new_url = in_gsheet_url.text.strip()

            settings["user_name"] = new_name
            settings["default_project"] = new_proj
            settings["default_login_time"] = new_login
            settings["default_logout_time"] = new_logout
            settings["gsheet_webapp_url"] = new_url
            settings["gsheet_auto_sync"] = is_auto_sync
            settings["gsheet_fetch_priority"] = is_fetch_pri
            settings["daily_shift_reminders_enabled"] = is_daily_on
            settings["reminder_sound"] = is_sound_on

            if 'save_all_settings' in globals():
                save_all_settings(settings)
            elif 'save_settings' in globals():
                save_settings(settings)

            self.settings = settings
            if self.chat_engine:
                self.chat_engine.user_name = new_name

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
            self.show_popup("Settings Saved", "Your settings have been updated and applied successfully!")

        btn_save = Button(
            text="💾 Save Settings",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_save.bind(on_release=_do_save_settings)
        btn_row.add_widget(btn_save)

        btn_close = Button(
            text="Close",
            font_size='14sp',
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_close.bind(on_release=popup.dismiss)
        btn_row.add_widget(btn_close)

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
