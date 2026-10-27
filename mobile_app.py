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
    BoxLayout = GridLayout = ScrollView = Label = TextInput = Button = Spinner = Popup = Window = object
    Clipboard = None

    def get_color_from_hex(hex_str):  # type: ignore
        return (1, 1, 1, 1)

# Import backend functions from app.py
try:
    from app import (
        save_work_update, load_settings, save_settings,
        calculate_net_working_hours, format_human_time,
        get_daily_timings, save_daily_timings,
        format_date_only, FILE
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
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=54, spacing=10)
        lbl_title = Label(
            text="[b]📝 WorkPulse[/b]",
            markup=True,
            font_size='22sp',
            color=get_color_from_hex("#38bdf8"),
            size_hint_x=0.6,
            halign='left',
            valign='middle'
        )
        lbl_title.bind(size=lbl_title.setter('text_size'))
        header.add_widget(lbl_title)

        btn_today = Button(
            text="📅 Today",
            size_hint_x=0.4,
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

    def show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=12, spacing=10)
        content.add_widget(Label(text=msg, font_size='14sp', color=(1, 1, 1, 1)))
        btn = Button(text="OK", size_hint_y=None, height=44, background_color=get_color_from_hex("#2563eb"))
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_release=popup.dismiss)
        content.add_widget(btn)
        popup.open()

if __name__ == "__main__":
    if KIVY_AVAILABLE:
        WorkPulseMobileApp().run()
    else:
        print("Kivy is not installed. To run mobile UI on desktop, run: pip install kivy")
