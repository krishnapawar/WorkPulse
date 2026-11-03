"""
WorkPulse - Android Mobile Application Interface (Kivy)
Mobile-optimized UI designed for Android touchscreens with high-DPI scaling,
full LAN Team Chat integration, Daily Work Manager, and Reminder Scheduler.
"""

import os
import sys
import datetime
import json
import threading

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

try:
    from storage_config import is_android, get_storage_path, acquire_android_multicast_lock
except Exception:
    def is_android(): return False
    def get_storage_path(fn): return fn
    def acquire_android_multicast_lock(): return None

# Import backend business logic
try:
    from app import (
        save_work_update, load_settings, save_settings,
        calculate_net_working_hours, format_human_time,
        get_daily_timings, save_daily_timings,
        format_date_only, FILE, sync_google_sheet_month,
        fetch_google_sheet_month, save_fetched_rows_to_excel,
        fetch_and_load_month_data, init_file
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
        LANChatEngine, get_network_info, get_avatar_color, get_initials
    )
except Exception as e:
    print(f"Warning: lan_chat import: {e}")
    LANChatEngine = None
    get_network_info = None
    get_avatar_color = None
    get_initials = None


class WorkPulseMobileApp(App if KIVY_AVAILABLE else object):
    def build(self):
        self.title = "WorkPulse - Mobile"
        if KIVY_AVAILABLE and hasattr(Window, 'clearcolor'):
            Window.clearcolor = get_color_from_hex("#0f172a")

        self.settings = load_settings() if 'load_settings' in globals() else {}
        self.chat_engine = None
        self.unread_chat_count = 0
        self.current_tab = "work"

        # Main Root Container
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # 1. Top Header App Bar
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(52), padding=[dp(12), dp(6), dp(12), dp(6)], spacing=dp(8))
        
        lbl_app = Label(
            text="[b]WorkPulse[/b] [color=#38bdf8]Mobile[/color]",
            markup=True,
            font_size='19sp',
            color=get_color_from_hex("#f8fafc"),
            size_hint_x=0.6,
            halign='left',
            valign='middle'
        )
        lbl_app.bind(size=lbl_app.setter('text_size'))
        header.add_widget(lbl_app)

        self.lbl_net_chip = Label(
            text="Online",
            font_size='12sp',
            color=get_color_from_hex("#34d399"),
            size_hint_x=0.4,
            halign='right',
            valign='middle'
        )
        self.lbl_net_chip.bind(size=self.lbl_net_chip.setter('text_size'))
        header.add_widget(self.lbl_net_chip)
        root.add_widget(header)

        # 2. Modern Navigation Tabs
        nav_tabs = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=[dp(8), 0, dp(8), dp(4)], spacing=dp(6))
        
        self.btn_tab_work = Button(
            text="Work Update",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        self.btn_tab_work.bind(on_release=lambda x: self.switch_tab("work"))
        nav_tabs.add_widget(self.btn_tab_work)

        self.btn_tab_chat = Button(
            text="Team Chat",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            color=get_color_from_hex("#94a3b8")
        )
        self.btn_tab_chat.bind(on_release=lambda x: self.switch_tab("chat"))
        nav_tabs.add_widget(self.btn_tab_chat)

        self.btn_tab_remind = Button(
            text="Reminders",
            font_size='14sp',
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
        self.view_chat = self.build_chat_view()
        self.view_remind = self.build_reminders_view()

        # Display default tab
        self.content_container.add_widget(self.view_work)

        # Initialize background LAN Chat Engine
        self.init_lan_chat_engine()

        return root

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.content_container.clear_widgets()

        # Reset button styling
        self.btn_tab_work.background_color = get_color_from_hex("#1e293b")
        self.btn_tab_work.color = get_color_from_hex("#94a3b8")
        self.btn_tab_chat.background_color = get_color_from_hex("#1e293b")
        self.btn_tab_chat.color = get_color_from_hex("#94a3b8")
        self.btn_tab_remind.background_color = get_color_from_hex("#1e293b")
        self.btn_tab_remind.color = get_color_from_hex("#94a3b8")

        if tab_name == "work":
            self.btn_tab_work.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_work.color = (1, 1, 1, 1)
            self.content_container.add_widget(self.view_work)
        elif tab_name == "chat":
            self.btn_tab_chat.background_color = get_color_from_hex("#2563eb")
            self.btn_tab_chat.color = (1, 1, 1, 1)
            self.unread_chat_count = 0
            self.btn_tab_chat.text = "Team Chat"
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
    # TAB 2: LAN TEAM CHAT VIEW
    # =========================================================================
    def build_chat_view(self):
        container = BoxLayout(orientation='vertical', padding=0, spacing=0)

        # Chat Header Status Card
        chat_top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=[dp(10), dp(4), dp(10), dp(4)], spacing=dp(8))
        
        self.lbl_chat_status = Label(
            text="Connecting to LAN...",
            font_size='12sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.38,
            halign='left',
            valign='middle'
        )
        self.lbl_chat_status.bind(size=self.lbl_chat_status.setter('text_size'))
        chat_top.add_widget(self.lbl_chat_status)

        btn_share_task = Button(
            text="Share Tasks",
            font_size='12sp',
            bold=True,
            size_hint_x=0.24,
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
            size_hint_x=0.18,
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
            size_hint_x=0.20,
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

        # Chat Input Bottom Bar
        chat_input_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(54), padding=[dp(8), dp(4), dp(8), dp(6)], spacing=dp(6))
        
        self.in_chat_msg = TextInput(
            hint_text="Type a message to team...",
            multiline=False,
            font_size='15sp',
            size_hint_x=0.78,
            background_normal='',
            background_color=get_color_from_hex("#1e293b"),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=get_color_from_hex("#64748b"),
            padding=[dp(10), dp(12)]
        )
        self.in_chat_msg.bind(on_text_validate=self.send_chat_message)
        chat_input_bar.add_widget(self.in_chat_msg)

        btn_send = Button(
            text="Send",
            font_size='15sp',
            bold=True,
            size_hint_x=0.22,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1)
        )
        btn_send.bind(on_release=self.send_chat_message)
        chat_input_bar.add_widget(btn_send)

        container.add_widget(chat_input_bar)
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
        for msg in self.chat_engine.messages[-60:]:
            self.add_message_bubble(msg)

    def add_message_bubble(self, msg):
        is_me = msg.get("is_me", False) or (self.chat_engine and msg.get("sender_id") == self.chat_engine.user_id)
        msg_type = msg.get("type", "text")
        sender = msg.get("user_name", "Anonymous")
        time_s = msg.get("time_str", "")

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
        if msg_type == "work_update":
            title = msg.get("title", "Daily Work Update")
            tasks = msg.get("tasks", [])
            task_lines = "\n".join([f"• {t.get('title', '')} ({t.get('hours', '')}h)" for t in tasks[:3]])
            body_text = f"[b]{title}[/b]\n{task_lines}"
            body_color = "#e2e8f0"
        elif msg_type == "file":
            fn = msg.get("file_name", "file")
            fs = msg.get("file_size_str", "")
            body_text = f"[Shared File] {fn} ({fs})"
            body_color = "#93c5fd"
        else:
            body_text = msg.get("text", "")
            body_color = "#ffffff"

        content_lbl = Label(
            text=body_text,
            markup=True,
            font_size='14sp',
            color=get_color_from_hex(body_color),
            size_hint_y=None,
            halign='right' if is_me else 'left'
        )
        content_lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        content_lbl.bind(texture_size=lambda s, ts: setattr(s, 'height', max(dp(24), ts[1])))
        bubble.add_widget(content_lbl)

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
            self.refresh_chat_messages_ui()
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.05)

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

        # Active Scheduled Reminders List
        content.add_widget(self._create_field_label("Active Schedules:"))
        self.rem_list_box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.rem_list_box.bind(minimum_height=self.rem_list_box.setter('height'))
        content.add_widget(self.rem_list_box)
        self.refresh_reminders_list()

        scroll.add_widget(content)
        return scroll

    def apply_preset_mins(self, minutes):
        target = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        self.in_rem_date.text = target.strftime("%Y-%m-%d")
        self.in_rem_time.text = target.strftime("%I:%M %p")

    def apply_preset_time(self, time_val):
        self.in_rem_date.text = datetime.date.today().strftime("%Y-%m-%d")
        self.in_rem_time.text = time_val

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
            self.show_popup("Notice", "Please enter a Reminder Title.")
            return

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
        content.add_widget(Label(text=msg, font_size='14sp', color=(1, 1, 1, 1), halign='center'))
        btn = Button(text="OK", font_size='14sp', size_hint_y=None, height=dp(44), background_normal='', background_color=get_color_from_hex("#2563eb"))
        popup = Popup(title=title, content=content, size_hint=(0.85, 0.38))
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
        content.add_widget(Label(text=f"[b]{title}[/b]\n\n{msg}", markup=True, font_size='15sp', color=(1, 1, 1, 1), halign='center'))

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
