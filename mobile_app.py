"""
WorkPulse - Android Mobile Application Interface (Kivy)
Mobile-optimized UI designed for Android touchscreens.
"""

import os
import sys
import datetime
import json

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

    def get_color_from_hex(hex_str):  # type: ignore
        return (1, 1, 1, 1)

# Import backend functions from app.py & reminder_scheduler.py
try:
    from app import (
        save_work_update, load_settings, save_settings,
        calculate_net_working_hours, format_human_time,
        get_daily_timings, save_daily_timings,
        format_date_only, FILE, sync_google_sheet_month,
        fetch_google_sheet_month, save_fetched_rows_to_excel,
        fetch_and_load_month_data
    )
except ImportError:
    pass

try:
    from reminder_scheduler import (
        ReminderSchedulerEngine, load_all_settings, save_all_settings,
        add_custom_reminder, delete_custom_reminder, toggle_custom_reminder_status,
        snooze_custom_reminder, format_minutes_to_time, parse_time_minutes
    )
except ImportError:
    pass

class WorkPulseMobileApp(App if KIVY_AVAILABLE else object):
    def build(self):
        self.title = "WorkPulse - Mobile"
        Window.clearcolor = get_color_from_hex("#0f172a")

        self.settings = load_settings() if 'load_settings' in globals() else {}
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        root = BoxLayout(orientation='vertical', padding=12, spacing=10)

        # 1. Header Banner
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=54, spacing=8)
        lbl_title = Label(
            text="[b]📝 WorkPulse[/b]",
            markup=True,
            font_size='21sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.48,
            halign='left',
            valign='middle'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        header.add_widget(lbl_title)

        btn_remind = Button(
            text="⏰ Remind",
            size_hint_x=0.26,
            background_normal='',
            background_color=get_color_from_hex("#f59e0b"),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_remind.bind(on_release=lambda x: self.open_reminders_popup())
        header.add_widget(btn_remind)

        btn_today = Button(
            text="📅 Today",
            size_hint_x=0.26,
            background_normal='',
            background_color=get_color_from_hex("#2563eb"),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_today.bind(on_release=lambda x: self.set_today())
        header.add_widget(btn_today)
        root.add_widget(header)

        # 2. Scrollable Form Body
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        form = GridLayout(cols=1, spacing=10, size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # Date input
        form.add_widget(Label(text="Date (YYYY-MM-DD):", size_hint_y=None, height=26, color=get_color_from_hex("#94a3b8"), halign='left'))
        self.in_date = TextInput(text=today_str, multiline=False, size_hint_y=None, height=44, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        form.add_widget(self.in_date)

        # Project input
        form.add_widget(Label(text="Project / Module:", size_hint_y=None, height=26, color=get_color_from_hex("#94a3b8"), halign='left'))
        self.in_proj = TextInput(text="General Work", multiline=False, size_hint_y=None, height=44, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        form.add_widget(self.in_proj)

        # Task title
        form.add_widget(Label(text="Task Title:", size_hint_y=None, height=26, color=get_color_from_hex("#94a3b8"), halign='left'))
        self.in_title = TextInput(hint_text="e.g. Bug fixes, feature development", multiline=False, size_hint_y=None, height=44, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        form.add_widget(self.in_title)

        # Hours & Status row
        h_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=8)
        self.in_hours = TextInput(hint_text="Hours (e.g. 8.0)", multiline=False, size_hint_x=0.5, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        self.sp_status = Spinner(
            text='Completed',
            values=('Completed', 'In Progress', 'Pending', 'Leave', 'Weekly Off', 'Holiday'),
            size_hint_x=0.5,
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        h_row.add_widget(self.in_hours)
        h_row.add_widget(self.sp_status)
        form.add_widget(h_row)

        # Shift timings (Login - Logout)
        form.add_widget(Label(text="Shift Timings (Login - Logout):", size_hint_y=None, height=26, color=get_color_from_hex("#94a3b8"), halign='left'))
        t_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=8)
        self.in_login = TextInput(hint_text="10:30 AM", text=self.settings.get("default_login_time", "10:30 AM"), multiline=False, size_hint_x=0.5, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        self.in_logout = TextInput(hint_text="07:30 PM", text=self.settings.get("default_logout_time", "07:30 PM"), multiline=False, size_hint_x=0.5, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        t_row.add_widget(self.in_login)
        t_row.add_widget(self.in_logout)
        form.add_widget(t_row)

        # Description
        form.add_widget(Label(text="Work Description / Notes:", size_hint_y=None, height=26, color=get_color_from_hex("#94a3b8"), halign='left'))
        self.in_desc = TextInput(hint_text="Enter task details...", multiline=True, size_hint_y=None, height=90, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        form.add_widget(self.in_desc)

        scroll.add_widget(form)
        root.add_widget(scroll)

        # 3. Action Buttons Bottom Bar
        b_box = BoxLayout(orientation='vertical', size_hint_y=None, height=110, spacing=8)

        btn_save = Button(
            text="💾 Save Work Update",
            font_size='16sp',
            bold=True,
            background_normal='',
            background_color=get_color_from_hex("#16a34a"),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=50
        )
        btn_save.bind(on_release=self.on_save)
        b_box.add_widget(btn_save)

        row_extra = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=8)
        btn_copy = Button(
            text="📋 Copy Standup",
            background_normal='',
            background_color=get_color_from_hex("#0284c7"),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_copy.bind(on_release=self.copy_standup)
        row_extra.add_widget(btn_copy)

        btn_sync = Button(
            text="📊 Sync G-Sheet",
            background_normal='',
            background_color=get_color_from_hex("#0f9d58"),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_sync.bind(on_release=self.sync_gsheet)
        row_extra.add_widget(btn_sync)

        btn_fetch = Button(
            text="📥 Fetch G-Sheet",
            background_normal='',
            background_color=get_color_from_hex("#4f46e5"),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_fetch.bind(on_release=self.fetch_gsheet)
        row_extra.add_widget(btn_fetch)

        btn_clear = Button(
            text="🧹 Clear",
            background_normal='',
            background_color=get_color_from_hex("#475569"),
            color=(1, 1, 1, 1)
        )
        btn_clear.bind(on_release=self.clear_form)
        row_extra.add_widget(btn_clear)

        b_box.add_widget(row_extra)
        root.add_widget(b_box)

        return root

    def set_today(self):
        self.in_date.text = datetime.date.today().strftime("%Y-%m-%d")

    def clear_form(self, *args):
        self.in_title.text = ""
        self.in_desc.text = ""
        self.in_hours.text = ""

    def sync_gsheet(self, *args):
        import threading
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
                self.show_popup("Sync Complete", msg)
            else:
                msg = data if isinstance(data, str) else data.get("message", "Error")
                self.show_popup("Sync Failed", f"Failed to sync: {msg}")

        threading.Thread(target=_do_sync, daemon=True).start()

    def fetch_gsheet(self, *args):
        import threading
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
                self.show_popup("Fetch Complete", f"Fetched {len(rows)} records from Google Sheet ('{month_name}') and synchronized with local system!")
            else:
                msg = data if isinstance(data, str) else (data.get("message", "Error") if isinstance(data, dict) else "Error")
                self.show_popup("Fetch Notice", f"Google Sheet unavailable:\n{msg}\nUsing local system records.")

        threading.Thread(target=_do_fetch, daemon=True).start()

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
                save_work_update(
                    date_v, proj_v, title_v, desc_v, hours_v, status_v, "",
                    login_time=login_v, logout_time=logout_v
                )
                self.show_popup("Success", f"✅ Task saved to {FILE}!")
                self.clear_form()

                # Trigger background Google Sheet sync if auto_sync enabled
                settings = load_settings() if 'load_settings' in globals() else {}
                if settings.get("gsheet_auto_sync", False) and settings.get("gsheet_webapp_url"):
                    import threading
                    try:
                        dt = datetime.datetime.strptime(date_v, "%Y-%m-%d")
                        m_name = dt.strftime("%B %Y")
                    except Exception:
                        m_name = datetime.datetime.now().strftime("%B %Y")
                    threading.Thread(target=lambda: sync_google_sheet_month(m_name), daemon=True).start()
            else:
                self.show_popup("Saved", "Task update recorded!")
        except Exception as e:
            self.show_popup("Error", f"Failed to save: {e}")

    def copy_standup(self, *args):
        title_v = self.in_title.text.strip() or "Task completed"
        hours_v = f" ({self.in_hours.text.strip()}h)" if self.in_hours.text.strip() else ""
        date_v = self.in_date.text.strip()
        text = f"#### Work Log - {date_v}\n- **{title_v}**{hours_v}\n{self.in_desc.text.strip()}"
        if Clipboard is not None:
            try:
                Clipboard.copy(text)
            except Exception:
                pass
        self.show_popup("Copied", "📋 Standup update copied to clipboard!")

    def on_start(self):
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
                if KIVY_AVAILABLE and 'Clock' in globals() and Clock is not None:
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

    def open_reminders_popup(self):
        if KIVY_AVAILABLE:
            pop = ReminderMobilePopup(self)
            pop.open()

    def show_reminder_alert(self, title, msg, item_type="custom", reminder_id=None):
        if not KIVY_AVAILABLE:
            return
        content = BoxLayout(orientation='vertical', padding=12, spacing=10)
        content.add_widget(Label(text=f"[b]{title}[/b]\n\n{msg}", markup=True, font_size='15sp', color=(1, 1, 1, 1), halign='center'))

        b_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=6)
        popup = Popup(title="⏰ WorkPulse Reminder Alert", content=content, size_hint=(0.88, 0.42), auto_dismiss=False)

        if item_type == "work_update":
            btn_act = Button(text="📝 Fill Update", background_color=get_color_from_hex("#8b5cf6"), bold=True)
            def _go_fill(x):
                popup.dismiss()
                self.in_title.focus = True
            btn_act.bind(on_release=_go_fill)
            b_row.add_widget(btn_act)
        elif item_type == "login":
            btn_act = Button(text="🌅 Set Login", background_color=get_color_from_hex("#0284c7"), bold=True)
            def _set_log(x):
                popup.dismiss()
                self.in_login.text = datetime.datetime.now().strftime("%I:%M %p")
            btn_act.bind(on_release=_set_log)
            b_row.add_widget(btn_act)

        btn_snooze = Button(text="💤 Snooze 10m", background_color=get_color_from_hex("#334155"), bold=True)
        def _do_snooze(x):
            popup.dismiss()
            if hasattr(self, 'reminder_engine') and self.reminder_engine:
                self.reminder_engine.snooze_runtime_reminder(title, msg, minutes=10, item_type=item_type, reminder_id=reminder_id)
        btn_snooze.bind(on_release=_do_snooze)
        b_row.add_widget(btn_snooze)

        btn_done = Button(text="✅ Done", background_color=get_color_from_hex("#16a34a"), bold=True)
        def _do_done(x):
            popup.dismiss()
            if item_type == "custom" and reminder_id and 'toggle_custom_reminder_status' in globals():
                toggle_custom_reminder_status(reminder_id, "completed")
        btn_done.bind(on_release=_do_done)
        b_row.add_widget(btn_done)

        content.add_widget(b_row)
        popup.open()

    def show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=12, spacing=10)
        content.add_widget(Label(text=msg, font_size='14sp', color=(1, 1, 1, 1)))
        btn = Button(text="OK", size_hint_y=None, height=44, background_color=get_color_from_hex("#2563eb"))
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_release=popup.dismiss)
        content.add_widget(btn)
        popup.open()


class ReminderMobilePopup(Popup if KIVY_AVAILABLE else object):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        self.title = "⏰ Remind Me & Schedule - WorkPulse"
        self.size_hint = (0.95, 0.92)
        self.auto_dismiss = True

        root_box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # 1. Quick Presets Section
        content.add_widget(Label(text="[b]⚡ 1-Click Quick Presets[/b]", markup=True, size_hint_y=None, height=26, color=get_color_from_hex("#38bdf8"), halign='left'))

        row_p1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=6)
        presets = [("10m", 10), ("15m", 15), ("30m", 30), ("1h", 60), ("2h", 120)]
        for lbl, mins in presets:
            btn_p = Button(text=lbl, background_color=get_color_from_hex("#0284c7"), color=(1, 1, 1, 1), bold=True)
            btn_p.bind(on_release=lambda x, m=mins: self.apply_preset_mins(m))
            row_p1.add_widget(btn_p)
        content.add_widget(row_p1)

        row_p2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=6)
        shift_presets = [("🌅 10:00 AM", "10:00 AM"), ("🍱 01:00 PM", "01:00 PM"), ("☕ 04:30 PM", "04:30 PM"), ("📝 07:00 PM", "07:00 PM")]
        for lbl, t_v in shift_presets:
            btn_s = Button(text=lbl, background_color=get_color_from_hex("#d97706"), color=(1, 1, 1, 1), bold=True)
            btn_s.bind(on_release=lambda x, t=t_v: self.apply_preset_time(t))
            row_p2.add_widget(btn_s)
        content.add_widget(row_p2)

        # 2. Custom Schedule Form
        content.add_widget(Label(text="[b]➕ Schedule Custom Reminder[/b]", markup=True, size_hint_y=None, height=26, color=get_color_from_hex("#38bdf8"), halign='left'))

        self.in_rem_title = TextInput(hint_text="Reminder title (e.g. Submit Standup, Client Sync)", multiline=False, size_hint_y=None, height=42, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        content.add_widget(self.in_rem_title)

        row_dt = BoxLayout(orientation='horizontal', size_hint_y=None, height=42, spacing=6)
        today_s = datetime.date.today().strftime("%Y-%m-%d")
        self.in_rem_date = TextInput(text=today_s, multiline=False, size_hint_x=0.5, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))

        def_mins = (datetime.datetime.now().hour * 60 + datetime.datetime.now().minute + 30) % 1440
        def_t = format_minutes_to_time(def_mins) if 'format_minutes_to_time' in globals() else "10:30 AM"
        self.in_rem_time = TextInput(text=def_t, multiline=False, size_hint_x=0.5, background_color=get_color_from_hex("#1e293b"), foreground_color=(1, 1, 1, 1))
        row_dt.add_widget(self.in_rem_date)
        row_dt.add_widget(self.in_rem_time)
        content.add_widget(row_dt)

        row_rep_btn = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=6)
        self.sp_repeat = Spinner(
            text='Once (No Repeat)',
            values=('Once (No Repeat)', 'Daily', 'Weekdays', 'Weekly'),
            size_hint_x=0.5,
            background_color=get_color_from_hex("#334155"),
            color=(1, 1, 1, 1)
        )
        btn_add_rem = Button(
            text="➕ Save Schedule",
            bold=True,
            size_hint_x=0.5,
            background_color=get_color_from_hex("#16a34a"),
            color=(1, 1, 1, 1)
        )
        btn_add_rem.bind(on_release=self.save_schedule)
        row_rep_btn.add_widget(self.sp_repeat)
        row_rep_btn.add_widget(btn_add_rem)
        content.add_widget(row_rep_btn)

        # 3. Daily Shift Alerts Quick Toggle
        content.add_widget(Label(text="[b]⚙️ Daily Shift Alerts (Login, Breaks, Standup)[/b]", markup=True, size_hint_y=None, height=26, color=get_color_from_hex("#38bdf8"), halign='left'))

        settings = load_all_settings() if 'load_all_settings' in globals() else {}
        is_daily_on = settings.get("daily_shift_reminders_enabled", True)
        self.btn_toggle_daily = Button(
            text=f"Daily Shift Alerts: {'✅ ACTIVE' if is_daily_on else '❌ PAUSED'} (Tap to toggle)",
            size_hint_y=None, height=42,
            background_color=get_color_from_hex("#0f766e" if is_daily_on else "#475569"),
            color=(1, 1, 1, 1),
            bold=True
        )
        self.btn_toggle_daily.bind(on_release=self.toggle_daily_alerts)
        content.add_widget(self.btn_toggle_daily)

        # 4. Active Scheduled Reminders List
        content.add_widget(Label(text="[b]📋 Active Schedules[/b]", markup=True, size_hint_y=None, height=26, color=get_color_from_hex("#38bdf8"), halign='left'))
        self.rem_list_box = GridLayout(cols=1, spacing=6, size_hint_y=None)
        self.rem_list_box.bind(minimum_height=self.rem_list_box.setter('height'))
        content.add_widget(self.rem_list_box)
        self.refresh_reminders_list()

        scroll.add_widget(content)
        root_box.add_widget(scroll)

        # Close button at bottom
        btn_close = Button(text="Close", size_hint_y=None, height=44, background_color=get_color_from_hex("#475569"))
        btn_close.bind(on_release=self.dismiss)
        root_box.add_widget(btn_close)

        self.content = root_box

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
            if hasattr(self.app_ref, 'show_popup'):
                self.app_ref.show_popup("Notice", "Please enter a Reminder Title.")
            return

        if 'add_custom_reminder' in globals():
            add_custom_reminder(title, date_v, time_v, repeat=repeat)
            self.in_rem_title.text = ""
            self.refresh_reminders_list()
            if hasattr(self.app_ref, 'show_popup'):
                self.app_ref.show_popup("Scheduled", f"✅ Reminder '{title}' scheduled!")

    def toggle_daily_alerts(self, *args):
        if 'load_all_settings' in globals() and 'save_all_settings' in globals():
            settings = load_all_settings()
            new_val = not settings.get("daily_shift_reminders_enabled", True)
            settings["daily_shift_reminders_enabled"] = new_val
            save_all_settings(settings)
            self.btn_toggle_daily.text = f"Daily Shift Alerts: {'✅ ACTIVE' if new_val else '❌ PAUSED'} (Tap to toggle)"
            self.btn_toggle_daily.background_color = get_color_from_hex("#0f766e" if new_val else "#475569")

    def refresh_reminders_list(self):
        self.rem_list_box.clear_widgets()
        if 'load_all_settings' not in globals():
            return
        settings = load_all_settings()
        reminders = settings.get("custom_reminders", [])

        if not reminders:
            self.rem_list_box.add_widget(Label(text="No scheduled reminders yet.", size_hint_y=None, height=30, color=get_color_from_hex("#64748b")))
            return

        for r in reversed(reminders[-8:]):
            st = r.get("status", "pending")
            status_icon = "⏰" if st == "pending" else "✅"
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=6)

            lbl = Label(
                text=f"{status_icon} [b]{r.get('title')}[/b] • {r.get('datetime', '')}",
                markup=True,
                size_hint_x=0.7,
                halign='left',
                color=get_color_from_hex("#f8fafc" if st == "pending" else "#94a3b8")
            )
            lbl.bind(size=lbl.setter('text_size'))
            row.add_widget(lbl)

            r_id = r.get("id")
            btn_done = Button(
                text="Done" if st == "pending" else "Undo",
                size_hint_x=0.15,
                background_color=get_color_from_hex("#0284c7"),
                bold=True
            )
            btn_done.bind(on_release=lambda x, rid=r_id: self._toggle_status(rid))
            row.add_widget(btn_done)

            btn_del = Button(
                text="Del",
                size_hint_x=0.15,
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


if __name__ == "__main__":
    if KIVY_AVAILABLE:
        WorkPulseMobileApp().run()
    else:
        print("Kivy is not installed. To run mobile UI on desktop, run: pip install kivy")
