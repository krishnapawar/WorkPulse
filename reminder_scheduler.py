"""
WorkPulse - Remind Me & Schedule Module
Provides automated daily shift reminders (Login, Lunch, Tea, Daily Work Update submission),
custom task & meeting scheduling, background scheduler engine, desktop system notifications,
interactive alert dialogs, and a full-featured Remind Me & Schedule Manager.
"""

import os
import sys
import json
import time
import datetime
import calendar
import threading
import subprocess
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
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
    messagebox = None
    TK_AVAILABLE = False

# ---------------------------------------------------------------------------
# Default Configuration & Schemas
# ---------------------------------------------------------------------------

DEFAULT_DAILY_REMINDERS = {
    "login": {
        "enabled": True,
        "time": "10:00 AM",
        "title": "🌅 Shift Login Reminder",
        "message": "Good morning! Time to log in and start your work day."
    },
    "lunch": {
        "enabled": True,
        "time": "01:00 PM",
        "title": "🍱 Lunch Break Reminder",
        "message": "Time for lunch break! Step away and recharge."
    },
    "tea": {
        "enabled": True,
        "time": "04:30 PM",
        "title": "☕ Tea Break Reminder",
        "message": "Time for a quick tea break and stretch!"
    },
    "work_update": {
        "enabled": True,
        "time": "07:00 PM",
        "title": "📝 Daily Work Update & Standup Reminder",
        "message": "Please log your completed tasks and submit today's work update before logout!"
    }
}

DEFAULT_REMINDER_SETTINGS = {
    "reminders_enabled": True,
    "reminder_sound": True,
    "reminder_desktop_notify": True,
    "daily_shift_reminders_enabled": True,
    "remind_skip_weekends_holidays": True,
    "daily_reminders": DEFAULT_DAILY_REMINDERS,
    "custom_reminders": []
}

def get_settings_file_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "settings.json")


def load_all_settings():
    """Load settings from settings.json with default fallback values."""
    s_path = get_settings_file_path()
    data = {}
    if os.path.exists(s_path):
        try:
            with open(s_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")

    # Ensure reminder settings are populated
    for k, v in DEFAULT_REMINDER_SETTINGS.items():
        if k not in data:
            data[k] = json.loads(json.dumps(v))

    if not isinstance(data.get("daily_reminders"), dict):
        data["daily_reminders"] = json.loads(json.dumps(DEFAULT_DAILY_REMINDERS))
    else:
        for r_key, r_def in DEFAULT_DAILY_REMINDERS.items():
            if r_key not in data["daily_reminders"]:
                data["daily_reminders"][r_key] = json.loads(json.dumps(r_def))

    if not isinstance(data.get("custom_reminders"), list):
        data["custom_reminders"] = []

    return data


def save_all_settings(settings_data):
    """Save full settings dictionary back to settings.json safely."""
    s_path = get_settings_file_path()
    try:
        with open(s_path, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


# ---------------------------------------------------------------------------
# Time & Date Parsing Helpers
# ---------------------------------------------------------------------------

def parse_time_minutes(time_str):
    """Parse time string like '10:00 AM', '18:30', '7:30 PM' into minutes from midnight."""
    if not time_str:
        return None
    s = str(time_str).strip()
    import re
    m = re.match(r'^(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?$', s, re.IGNORECASE)
    if not m:
        m2 = re.match(r'^(\d{1,2})\s*(am|pm)$', s, re.IGNORECASE)
        if m2:
            h, mer = int(m2.group(1)), m2.group(2).lower()
            if mer == 'pm' and h != 12:
                h += 12
            elif mer == 'am' and h == 12:
                h = 0
            return h * 60
        return None
    h, mins, mer = int(m.group(1)), int(m.group(2)), m.group(3)
    if mer:
        mer = mer.lower()
        if mer == 'pm' and h != 12:
            h += 12
        elif mer == 'am' and h == 12:
            h = 0
    elif h < 7:
        h += 12
    return h * 60 + mins


def format_minutes_to_time(minutes):
    """Convert minutes from midnight to 'HH:MM AM/PM' string."""
    if minutes is None:
        return ""
    minutes = int(minutes) % 1440
    h = minutes // 60
    m = minutes % 60
    mer = "AM"
    if h >= 12:
        mer = "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{m:02d} {mer}"


def parse_datetime_flexible(dt_str):
    """Parse a flexible date/time string into a datetime object."""
    if not dt_str:
        return None
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %I:%M %p",
    ]
    s = str(dt_str).strip()
    for fmt in formats:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Cross-Platform Desktop Notifications & Sound
# ---------------------------------------------------------------------------

def deliver_desktop_notification(title, message, app_name="WorkPulse"):
    """
    Shows a native OS desktop notification across Linux, Windows, and macOS.
    Does not block the calling thread.
    """
    def _worker():
        try:
            if sys.platform.startswith("linux"):
                subprocess.run(
                    ["notify-send", "-a", app_name, "-i", "alarm", "-t", "6000", str(title), str(message)],
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
                    f'$n.showballoontip(6000, "{title}", "{message}", [system.windows.forms.tooltipicon]::Info)'
                )
                subprocess.run(["powershell", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception as e:
            print(f"Error delivering desktop notification: {e}")

    threading.Thread(target=_worker, daemon=True, name="WorkPulseNotifyWorker").start()


def play_audio_alert(root=None):
    """Emits an audible notification chime safely."""
    try:
        if root:
            root.bell()
        elif sys.platform == "win32":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Custom Reminders CRUD Operations
# ---------------------------------------------------------------------------

def add_custom_reminder(title, date_str, time_str, notes="", repeat="none", notify_desktop=True):
    """
    Creates and saves a new scheduled reminder.
    Returns the created reminder dictionary.
    """
    settings = load_all_settings()
    reminders = settings.get("custom_reminders", [])

    # Format datetime canonical
    t_mins = parse_time_minutes(time_str)
    if t_mins is None:
        t_str = "10:00 AM"
    else:
        t_str = format_minutes_to_time(t_mins)

    # Normalize date
    try:
        dt_test = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d")
        d_str = dt_test.strftime("%Y-%m-%d")
    except Exception:
        d_str = datetime.date.today().strftime("%Y-%m-%d")

    canonical_dt = f"{d_str} {t_str}"
    rem_id = f"rem_{int(time.time())}_{len(reminders) + 1}"

    new_item = {
        "id": rem_id,
        "title": title.strip() or "Untitled Reminder",
        "notes": notes.strip(),
        "date": d_str,
        "time": t_str,
        "datetime": canonical_dt,
        "repeat": repeat or "none",  # "none", "daily", "weekdays", "weekly"
        "status": "pending",  # "pending", "completed"
        "notify_desktop": bool(notify_desktop),
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    reminders.append(new_item)
    settings["custom_reminders"] = reminders
    save_all_settings(settings)
    return new_item


def delete_custom_reminder(reminder_id):
    """Deletes a custom scheduled reminder by ID."""
    settings = load_all_settings()
    reminders = settings.get("custom_reminders", [])
    updated = [r for r in reminders if r.get("id") != reminder_id]
    settings["custom_reminders"] = updated
    save_all_settings(settings)
    return len(updated) < len(reminders)


def toggle_custom_reminder_status(reminder_id, new_status=None):
    """Toggles or sets the status of a reminder ('pending' / 'completed')."""
    settings = load_all_settings()
    reminders = settings.get("custom_reminders", [])
    found = None
    for r in reminders:
        if r.get("id") == reminder_id:
            if new_status:
                r["status"] = new_status
            else:
                r["status"] = "completed" if r.get("status") == "pending" else "pending"
            found = r
            break
    if found:
        settings["custom_reminders"] = reminders
        save_all_settings(settings)
    return found


def snooze_custom_reminder(reminder_id, minutes=10):
    """Snoozes a reminder by pushing its scheduled datetime forward by X minutes."""
    settings = load_all_settings()
    reminders = settings.get("custom_reminders", [])
    found = None
    for r in reminders:
        if r.get("id") == reminder_id:
            now = datetime.datetime.now()
            new_dt = now + datetime.timedelta(minutes=minutes)
            r["date"] = new_dt.strftime("%Y-%m-%d")
            r["time"] = new_dt.strftime("%I:%M %p")
            r["datetime"] = f"{r['date']} {r['time']}"
            r["status"] = "pending"
            found = r
            break
    if found:
        settings["custom_reminders"] = reminders
        save_all_settings(settings)
    return found


def clear_completed_reminders():
    """Removes all completed reminders from storage."""
    settings = load_all_settings()
    reminders = settings.get("custom_reminders", [])
    active = [r for r in reminders if r.get("status") == "pending"]
    settings["custom_reminders"] = active
    save_all_settings(settings)
    return len(reminders) - len(active)


# ---------------------------------------------------------------------------
# Background Scheduler Engine
# ---------------------------------------------------------------------------

class ReminderSchedulerEngine:
    """
    Background daemon scheduler engine that monitors daily shift triggers
    (Login, Lunch, Tea, Work Update submission) and custom timed reminders.
    Works seamlessly across Desktop (Tkinter) and Mobile (Kivy).
    """
    _instance = None

    @classmethod
    def get_instance(cls, app_ref=None):
        if cls._instance is None:
            cls._instance = cls(app_ref=app_ref)
        elif app_ref is not None:
            cls._instance.app_ref = app_ref
        return cls._instance

    def __init__(self, app_ref=None, on_trigger_callback=None):
        self.app_ref = app_ref
        self.on_trigger_callback = on_trigger_callback
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._fired_daily = {}  # {date_str: set(daily_keys)}
        self._snoozed_items = []  # [{due_dt, title, message, type, id}]
        self._lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="WorkPulseSchedulerEngine")
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()

    def snooze_runtime_reminder(self, title, message, minutes=10, item_type="custom", reminder_id=None):
        """Adds a runtime snoozed reminder that fires in X minutes."""
        with self._lock:
            due_dt = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            self._snoozed_items.append({
                "id": reminder_id,
                "due_dt": due_dt,
                "title": f"⏰ [Snoozed] {title}",
                "message": message,
                "type": item_type
            })

    def check_reminders_now(self):
        """Forces an immediate check of all scheduled reminders."""
        self._perform_check()

    def _worker_loop(self):
        # Initial short pause so the host app finishes rendering
        time.sleep(1.5)
        while self.running and not self._stop_event.is_set():
            try:
                self._perform_check()
            except Exception as e:
                print(f"Error in scheduler tick: {e}")
            self._stop_event.wait(10.0)

    def _perform_check(self):
        settings = load_all_settings()
        if not settings.get("reminders_enabled", True):
            return

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        now_hm = now.strftime("%H:%M")
        now_mins = now.hour * 60 + now.minute

        # 1. Process Runtime Snoozed Reminders
        with self._lock:
            due_snoozed = [item for item in self._snoozed_items if item["due_dt"] <= now]
            self._snoozed_items = [item for item in self._snoozed_items if item["due_dt"] > now]

        for item in due_snoozed:
            self._trigger_reminder(
                item_type=item.get("type", "custom"),
                title=item.get("title", "⏰ Reminder"),
                message=item.get("message", ""),
                reminder_id=item.get("id")
            )

        # 2. Process Daily Shift & Work Update Reminders
        if settings.get("daily_shift_reminders_enabled", True):
            # Check if today should be skipped (Weekend or Holiday)
            skip = False
            if settings.get("remind_skip_weekends_holidays", True):
                try:
                    from app import is_date_holiday, is_date_weekly_off
                    if is_date_holiday(today_str) or is_date_weekly_off(today_str, settings):
                        skip = True
                except Exception:
                    pass

            if not skip:
                daily_reminders = settings.get("daily_reminders", {})
                for key, config in daily_reminders.items():
                    if not config.get("enabled", True):
                        continue
                    t_str = config.get("time", "")
                    t_mins = parse_time_minutes(t_str)
                    if t_mins is None:
                        continue

                    # Fire if within 1 minute of scheduled time
                    if abs(now_mins - t_mins) <= 1:
                        fired_today = self._fired_daily.setdefault(today_str, set())
                        if key not in fired_today:
                            fired_today.add(key)
                            self._trigger_reminder(
                                item_type=key,
                                title=config.get("title", "⏰ Daily Shift Reminder"),
                                message=config.get("message", ""),
                                reminder_id=key
                            )

        # 3. Process Custom Scheduled Reminders
        custom_reminders = settings.get("custom_reminders", [])
        modified = False

        for r in custom_reminders:
            if r.get("status") != "pending":
                continue

            dt_parsed = parse_datetime_flexible(r.get("datetime"))
            if dt_parsed and dt_parsed <= now:
                # Trigger reminder!
                self._trigger_reminder(
                    item_type="custom",
                    title=f"⏰ {r.get('title', 'Scheduled Reminder')}",
                    message=r.get("notes") or f"Scheduled for {r.get('time', '')} ({r.get('date', '')})",
                    reminder_id=r.get("id")
                )

                # Handle repetition
                rep = r.get("repeat", "none").lower()
                if rep == "daily":
                    next_dt = dt_parsed + datetime.timedelta(days=1)
                    while next_dt <= now:
                        next_dt += datetime.timedelta(days=1)
                    r["date"] = next_dt.strftime("%Y-%m-%d")
                    r["time"] = next_dt.strftime("%I:%M %p")
                    r["datetime"] = f"{r['date']} {r['time']}"
                    modified = True
                elif rep == "weekdays":
                    next_dt = dt_parsed + datetime.timedelta(days=1)
                    while next_dt.weekday() in (5, 6) or next_dt <= now:
                        next_dt += datetime.timedelta(days=1)
                    r["date"] = next_dt.strftime("%Y-%m-%d")
                    r["time"] = next_dt.strftime("%I:%M %p")
                    r["datetime"] = f"{r['date']} {r['time']}"
                    modified = True
                elif rep == "weekly":
                    next_dt = dt_parsed + datetime.timedelta(weeks=1)
                    while next_dt <= now:
                        next_dt += datetime.timedelta(weeks=1)
                    r["date"] = next_dt.strftime("%Y-%m-%d")
                    r["time"] = next_dt.strftime("%I:%M %p")
                    r["datetime"] = f"{r['date']} {r['time']}"
                    modified = True
                else:
                    r["status"] = "completed"
                    r["completed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    modified = True

        if modified:
            settings["custom_reminders"] = custom_reminders
            save_all_settings(settings)

    def _trigger_reminder(self, item_type, title, message, reminder_id=None):
        """Dispatches notification to Desktop OS and UI application."""
        settings = load_all_settings()

        # 1. OS Native Notification
        if settings.get("reminder_desktop_notify", True):
            deliver_desktop_notification(title, message, app_name="WorkPulse")

        # 2. Host Application UI Notification
        if self.on_trigger_callback:
            try:
                self.on_trigger_callback(item_type, title, message, reminder_id)
                return
            except Exception as e:
                print(f"Error in scheduler on_trigger_callback: {e}")

        # If Tkinter app_ref is set, dispatch to Tkinter main thread
        if self.app_ref:
            try:
                from app import run_on_ui_thread
                run_on_ui_thread(lambda: self._show_tkinter_reminder(item_type, title, message, reminder_id))
            except Exception as e:
                print(f"Error dispatching reminder to UI thread: {e}")

    def _show_tkinter_reminder(self, item_type, title, message, reminder_id):
        """Displays interactive Tkinter Alert Window and in-app toast on main thread."""
        settings = load_all_settings()
        root = getattr(self.app_ref, "root", None)

        # Audio chime
        if settings.get("reminder_sound", True):
            play_audio_alert(root)

        # In-App Toast
        try:
            from lan_chat import show_in_app_toast
            if root:
                show_in_app_toast(root, title, message, icon="⏰", duration_ms=6000)
        except Exception:
            pass

        # Interactive Modal Alert Window
        try:
            ReminderAlertWindow(
                parent=root,
                title=title,
                message=message,
                item_type=item_type,
                reminder_id=reminder_id,
                app_ref=self.app_ref
            )
        except Exception as e:
            print(f"Error creating ReminderAlertWindow: {e}")


# ---------------------------------------------------------------------------
# Tkinter Interactive Alert Window
# ---------------------------------------------------------------------------

class ReminderAlertWindow(tk.Toplevel):
    """
    Eye-catching interactive alert popup that appears on screen when a reminder triggers.
    Includes contextual action buttons (e.g. 'Open Work Logger', 'Fill Login', 'Snooze').
    """
    def __init__(self, parent, title, message, item_type="custom", reminder_id=None, app_ref=None):
        super().__init__(parent)
        self.parent = parent
        self.rem_title = title
        self.rem_message = message
        self.item_type = item_type
        self.reminder_id = reminder_id
        self.app_ref = app_ref

        self.title("⏰ WorkPulse Reminder")
        self.configure(bg="#0f172a")
        self.resizable(False, False)

        # Ensure window is on top and focused
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = 480, 310
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(20, (sw - w) // 2)
        y = max(30, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Color thematic based on reminder category
        color_theme = {
            "login": ("#0284c7", "🌅 SHIFT LOGIN REMINDER"),
            "lunch": ("#059669", "🍱 LUNCH BREAK REMINDER"),
            "tea": ("#d97706", "☕ TEA BREAK REMINDER"),
            "work_update": ("#7c3aed", "📝 DAILY WORK UPDATE & STANDUP"),
            "custom": ("#2563eb", "⏰ SCHEDULED REMINDER")
        }.get(self.item_type, ("#2563eb", "⏰ WORKPULSE REMINDER"))

        banner_color, banner_sub = color_theme

        # Top Header Banner
        banner = tk.Frame(self, bg=banner_color, padx=16, pady=12)
        banner.pack(fill=tk.X, side=tk.TOP)

        lbl_banner_sub = tk.Label(
            banner, text=banner_sub,
            font=("Segoe UI", 9, "bold"), fg="#e0f2fe", bg=banner_color
        )
        lbl_banner_sub.pack(anchor="w")

        lbl_banner_title = tk.Label(
            banner, text=self.rem_title,
            font=("Segoe UI", 13, "bold"), fg="#ffffff", bg=banner_color
        )
        lbl_banner_title.pack(anchor="w", pady=(2, 0))

        # Main Content Card
        body = tk.Frame(self, bg="#1e293b", padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        now_str = datetime.datetime.now().strftime("%I:%M %p • %A, %b %d")
        lbl_time = tk.Label(
            body, text=f"🔔 Triggered at {now_str}",
            font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b"
        )
        lbl_time.pack(anchor="w", pady=(0, 8))

        lbl_msg = tk.Label(
            body, text=self.rem_message,
            font=("Segoe UI", 10), fg="#f8fafc", bg="#1e293b",
            wraplength=430, justify="left"
        )
        lbl_msg.pack(anchor="w", fill=tk.BOTH, expand=True)

        # Bottom Action Buttons
        btn_bar = tk.Frame(self, bg="#0f172a", padx=16, pady=12)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Contextual Action Button (Work Update / Login / Custom)
        if self.item_type == "work_update":
            btn_act = tk.Button(
                btn_bar, text="📝 Log Today's Work",
                font=("Segoe UI", 9, "bold"), bg="#8b5cf6", fg="white",
                activebackground="#7c3aed", activeforeground="white",
                relief="flat", padx=10, pady=5, cursor="hand2",
                command=self._action_open_work_logger
            )
            btn_act.pack(side=tk.LEFT, padx=(0, 6))
        elif self.item_type == "login":
            btn_act = tk.Button(
                btn_bar, text="🌅 Fill Login Time",
                font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="white",
                activebackground="#0369a1", activeforeground="white",
                relief="flat", padx=10, pady=5, cursor="hand2",
                command=self._action_fill_login_time
            )
            btn_act.pack(side=tk.LEFT, padx=(0, 6))

        # Snooze dropdown / buttons
        btn_snooze_10 = tk.Button(
            btn_bar, text="💤 Snooze 10m",
            font=("Segoe UI", 8, "bold"), bg="#334155", fg="#e2e8f0",
            activebackground="#475569", activeforeground="white",
            relief="flat", padx=8, pady=5, cursor="hand2",
            command=lambda: self._snooze(10)
        )
        btn_snooze_10.pack(side=tk.LEFT, padx=3)

        btn_snooze_30 = tk.Button(
            btn_bar, text="💤 30m",
            font=("Segoe UI", 8, "bold"), bg="#334155", fg="#e2e8f0",
            activebackground="#475569", activeforeground="white",
            relief="flat", padx=8, pady=5, cursor="hand2",
            command=lambda: self._snooze(30)
        )
        btn_snooze_30.pack(side=tk.LEFT, padx=3)

        # Dismiss / Done Button
        btn_dismiss = tk.Button(
            btn_bar, text="✅ Got it / Done",
            font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white",
            activebackground="#15803d", activeforeground="white",
            relief="flat", padx=14, pady=5, cursor="hand2",
            command=self._dismiss
        )
        btn_dismiss.pack(side=tk.RIGHT)

    def _snooze(self, minutes):
        engine = ReminderSchedulerEngine.get_instance(self.app_ref)
        engine.snooze_runtime_reminder(
            title=self.rem_title,
            message=self.rem_message,
            minutes=minutes,
            item_type=self.item_type,
            reminder_id=self.reminder_id
        )
        self.destroy()

    def _dismiss(self):
        if self.item_type == "custom" and self.reminder_id:
            toggle_custom_reminder_status(self.reminder_id, "completed")
        self.destroy()

    def _action_open_work_logger(self):
        """Brings the main WorkPulse window to front and focuses the task title input."""
        if self.app_ref:
            try:
                root = getattr(self.app_ref, "root", None)
                if root:
                    root.deiconify()
                    root.lift()
                    root.focus_force()
                if hasattr(self.app_ref, "entry_task_title"):
                    self.app_ref.entry_task_title.focus_set()
            except Exception:
                pass
        self._dismiss()

    def _action_fill_login_time(self):
        """Fills the current time into the login field of the main form."""
        if self.app_ref:
            try:
                now_str = datetime.datetime.now().strftime("%I:%M %p")
                if hasattr(self.app_ref, "entry_login"):
                    self.app_ref.entry_login.delete(0, tk.END)
                    self.app_ref.entry_login.insert(0, now_str)
                root = getattr(self.app_ref, "root", None)
                if root:
                    root.deiconify()
                    root.lift()
            except Exception:
                pass
        self._dismiss()


# ---------------------------------------------------------------------------
# Full Remind Me & Schedule Manager Dialog (Tkinter)
# ---------------------------------------------------------------------------

class ReminderScheduleDialog(tk.Toplevel):
    """
    Comprehensive Remind Me & Schedule Manager Dialog.
    Features:
    - Quick 'Remind Me' in 10m, 15m, 30m, 1h, Login, Lunch, Tea, Logout
    - Custom Task & Event Scheduler with Date, Time, Repeat & Sound
    - Active Schedules & History Manager (Filter, Test/Trigger, Snooze, Delete)
    - Automated Daily Shift & Work Update Reminder Settings
    """
    def __init__(self, parent, app_ref=None):
        super().__init__(parent)
        self.parent = parent
        self.app_ref = app_ref
        self.title("⏰ Remind Me & Schedule Manager - WorkPulse")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()

        self._center(default_w=780, default_h=620)
        self.settings = load_all_settings()

        self._create_widgets()

    def _center(self, default_w=780, default_h=620):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(default_w, sw - 40)
        h = min(default_h, sh - 60)
        x = max(10, (sw - w) // 2)
        y = max(10, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(680, 520)

    def _create_widgets(self):
        # 1. Header Banner
        header = tk.Frame(self, bg="#1e293b", height=58, padx=16)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_icon = tk.Label(header, text="⏰", font=("Segoe UI", 18), bg="#1e293b", fg="#38bdf8")
        h_icon.pack(side=tk.LEFT, padx=(0, 10), pady=10)

        h_text_box = tk.Frame(header, bg="#1e293b")
        h_text_box.pack(side=tk.LEFT, pady=8)

        lbl_h_title = tk.Label(h_text_box, text="Remind Me & Schedule Manager", font=("Segoe UI", 12, "bold"), fg="#ffffff", bg="#1e293b")
        lbl_h_title.pack(anchor="w")

        lbl_h_sub = tk.Label(h_text_box, text="Automated daily shift alerts • Standup submission • Custom task reminders", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b")
        lbl_h_sub.pack(anchor="w")

        # Master Switch on Header Right
        self.var_master_enabled = tk.BooleanVar(value=self.settings.get("reminders_enabled", True))
        chk_master = tk.Checkbutton(
            header, text="Reminders Active", variable=self.var_master_enabled,
            font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#1e293b",
            activebackground="#1e293b", activeforeground="#38bdf8",
            selectcolor="#0f172a", cursor="hand2", command=self._toggle_master_switch
        )
        chk_master.pack(side=tk.RIGHT, padx=10, pady=12)

        # 2. Main Tab Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(10, 8))

        # Tab 1: Quick Remind & Schedule
        tab_new = tk.Frame(self.notebook, bg="#ffffff", padx=16, pady=14)
        self.notebook.add(tab_new, text="  ⏰ Quick Remind & New Schedule  ")
        self._build_quick_schedule_tab(tab_new)

        # Tab 2: Active Schedules & History
        tab_list = tk.Frame(self.notebook, bg="#ffffff", padx=14, pady=12)
        self.notebook.add(tab_list, text="  📋 Scheduled Reminders & History  ")
        self._build_schedule_list_tab(tab_list)

        # Tab 3: Daily Shift & Work Update Auto-Reminders
        tab_daily = tk.Frame(self.notebook, bg="#ffffff", padx=16, pady=14)
        self.notebook.add(tab_daily, text="  ⚙️ Daily Shift & Standup Auto-Alerts  ")
        self._build_daily_shift_tab(tab_daily)

        # 3. Bottom Close Bar
        bottom = tk.Frame(self, bg="#f1f5f9", padx=16, pady=8)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        btn_close = tk.Button(
            bottom, text="Close", font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0", fg="#334155", relief="flat", padx=16, pady=5,
            cursor="hand2", command=self.destroy
        )
        btn_close.pack(side=tk.RIGHT)

        self.lbl_feedback = tk.Label(bottom, text="", font=("Segoe UI", 9), fg="#16a34a", bg="#f1f5f9")
        self.lbl_feedback.pack(side=tk.LEFT)

    # -----------------------------------------------------------------------
    # TAB 1: Quick Remind & New Schedule
    # -----------------------------------------------------------------------
    def _build_quick_schedule_tab(self, parent):
        # Top: Fast One-Click Presets Box
        card_presets = tk.LabelFrame(
            parent, text="  ⚡ 1-Click Quick Remind Me Presets  ",
            font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#f8fafc", bd=1, relief="solid", padx=12, pady=10
        )
        card_presets.pack(fill=tk.X, pady=(0, 12))

        p_row1 = tk.Frame(card_presets, bg="#f8fafc")
        p_row1.pack(fill=tk.X, pady=2)

        presets = [
            ("⚡ In 10 Mins", 10),
            ("⚡ In 15 Mins", 15),
            ("⚡ In 30 Mins", 30),
            ("⚡ In 1 Hour", 60),
            ("⚡ In 2 Hours", 120),
        ]
        for label, mins in presets:
            btn = tk.Button(
                p_row1, text=label, font=("Segoe UI", 8, "bold"),
                bg="#e0f2fe", fg="#0369a1", activebackground="#bae6fd",
                relief="flat", padx=9, pady=4, cursor="hand2",
                command=lambda m=mins: self._apply_quick_preset(m)
            )
            btn.pack(side=tk.LEFT, padx=3)

        p_row2 = tk.Frame(card_presets, bg="#f8fafc")
        p_row2.pack(fill=tk.X, pady=(6, 2))

        shift_presets = [
            ("🌅 At Login (10:00 AM)", "10:00 AM"),
            ("🍱 At Lunch Break (01:00 PM)", "01:00 PM"),
            ("☕ At Tea Break (04:30 PM)", "04:30 PM"),
            ("📝 At Daily Work Update / Logout (07:00 PM)", "07:00 PM"),
        ]
        for label, t_val in shift_presets:
            btn = tk.Button(
                p_row2, text=label, font=("Segoe UI", 8, "bold"),
                bg="#fef3c7", fg="#92400e", activebackground="#fde68a",
                relief="flat", padx=9, pady=4, cursor="hand2",
                command=lambda t=t_val: self._apply_shift_preset(t)
            )
            btn.pack(side=tk.LEFT, padx=3)

        # Form: Custom Schedule Entry
        card_form = tk.LabelFrame(
            parent, text="  ➕ Create Custom Scheduled Reminder  ",
            font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff", bd=1, relief="solid", padx=14, pady=10
        )
        card_form.pack(fill=tk.BOTH, expand=True)

        # Row 1: Reminder Title
        r1 = tk.Frame(card_form, bg="#ffffff")
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Reminder Title / Task:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", width=20, anchor="w").pack(side=tk.LEFT)
        self.entry_rem_title = tk.Entry(r1, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_rem_title.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.entry_rem_title.insert(0, "Submit Today's Work Update & Standup")

        # Row 2: Date & Quick Helpers
        r2 = tk.Frame(card_form, bg="#ffffff")
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", width=20, anchor="w").pack(side=tk.LEFT)
        self.entry_rem_date = tk.Entry(r2, font=("Segoe UI", 9), width=14, relief="solid", bd=1)
        self.entry_rem_date.pack(side=tk.LEFT, ipady=3)
        self.entry_rem_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        btn_today = tk.Button(r2, text="Today", font=("Segoe UI", 8), bg="#e2e8f0", fg="#334155", relief="flat", padx=6, pady=2, cursor="hand2", command=lambda: self._set_date_offset(0))
        btn_today.pack(side=tk.LEFT, padx=(6, 2))

        btn_tomorrow = tk.Button(r2, text="Tomorrow", font=("Segoe UI", 8), bg="#e2e8f0", fg="#334155", relief="flat", padx=6, pady=2, cursor="hand2", command=lambda: self._set_date_offset(1))
        btn_tomorrow.pack(side=tk.LEFT, padx=2)

        # Row 3: Time & Repeat
        r3 = tk.Frame(card_form, bg="#ffffff")
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Time (HH:MM AM/PM):", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", width=20, anchor="w").pack(side=tk.LEFT)
        self.entry_rem_time = tk.Entry(r3, font=("Segoe UI", 9), width=14, relief="solid", bd=1)
        self.entry_rem_time.pack(side=tk.LEFT, ipady=3)
        
        # Default: current time + 30 mins
        def_mins = (datetime.datetime.now().hour * 60 + datetime.datetime.now().minute + 30) % 1440
        self.entry_rem_time.insert(0, format_minutes_to_time(def_mins))

        tk.Label(r3, text="Repeat:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(16, 6))
        self.cmb_repeat = ttk.Combobox(r3, values=["Once (No Repeat)", "Daily", "Weekdays (Mon-Fri)", "Weekly"], state="readonly", width=18)
        self.cmb_repeat.current(0)
        self.cmb_repeat.pack(side=tk.LEFT)

        # Row 4: Notes / Work Description
        r4 = tk.Frame(card_form, bg="#ffffff")
        r4.pack(fill=tk.X, pady=4)
        tk.Label(r4, text="Notes / Details (Optional):", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", width=20, anchor="w").pack(side=tk.LEFT, anchor="n", pady=4)
        self.txt_rem_notes = tk.Text(r4, font=("Segoe UI", 9), height=3, relief="solid", bd=1)
        self.txt_rem_notes.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 5: Action Button & Desktop notify checkbox
        r5 = tk.Frame(card_form, bg="#ffffff")
        r5.pack(fill=tk.X, pady=(10, 0))

        self.var_notify_desktop = tk.BooleanVar(value=True)
        chk_desktop = tk.Checkbutton(
            r5, text="🔔 Show Native Desktop System Notification",
            variable=self.var_notify_desktop, font=("Segoe UI", 8),
            bg="#ffffff", fg="#475569", selectcolor="#ffffff"
        )
        chk_desktop.pack(side=tk.LEFT)

        btn_save = tk.Button(
            r5, text="➕ Schedule Reminder", font=("Segoe UI", 10, "bold"),
            bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white",
            relief="flat", padx=16, pady=6, cursor="hand2", command=self._save_new_reminder
        )
        btn_save.pack(side=tk.RIGHT)

    def _apply_quick_preset(self, minutes):
        now = datetime.datetime.now()
        target = now + datetime.timedelta(minutes=minutes)
        self.entry_rem_date.delete(0, tk.END)
        self.entry_rem_date.insert(0, target.strftime("%Y-%m-%d"))
        self.entry_rem_time.delete(0, tk.END)
        self.entry_rem_time.insert(0, target.strftime("%I:%M %p"))

    def _apply_shift_preset(self, time_val):
        self.entry_rem_date.delete(0, tk.END)
        self.entry_rem_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        self.entry_rem_time.delete(0, tk.END)
        self.entry_rem_time.insert(0, time_val)

    def _set_date_offset(self, days):
        target = datetime.date.today() + datetime.timedelta(days=days)
        self.entry_rem_date.delete(0, tk.END)
        self.entry_rem_date.insert(0, target.strftime("%Y-%m-%d"))

    def _save_new_reminder(self):
        title = self.entry_rem_title.get().strip()
        date_v = self.entry_rem_date.get().strip()
        time_v = self.entry_rem_time.get().strip()
        notes = self.txt_rem_notes.get("1.0", tk.END).strip()
        rep_val = self.cmb_repeat.get()

        rep_map = {
            "Once (No Repeat)": "none",
            "Daily": "daily",
            "Weekdays (Mon-Fri)": "weekdays",
            "Weekly": "weekly"
        }
        repeat = rep_map.get(rep_val, "none")

        if not title:
            messagebox.showwarning("Missing Title", "Please enter a Reminder Title.", parent=self)
            return

        t_mins = parse_time_minutes(time_v)
        if t_mins is None:
            messagebox.showwarning("Invalid Time", "Please enter a valid time (e.g. 10:30 AM or 18:30).", parent=self)
            return

        item = add_custom_reminder(
            title=title,
            date_str=date_v,
            time_str=time_v,
            notes=notes,
            repeat=repeat,
            notify_desktop=self.var_notify_desktop.get()
        )

        self.lbl_feedback.config(text=f"✅ Scheduled: '{title}' for {item.get('datetime')}", fg="#16a34a")
        self.entry_rem_title.delete(0, tk.END)
        self.entry_rem_title.insert(0, "Quick Follow-up")
        self.txt_rem_notes.delete("1.0", tk.END)

        # Refresh scheduler list tab
        self._refresh_schedule_list()
        self.notebook.select(1)

    # -----------------------------------------------------------------------
    # TAB 2: Scheduled Reminders & History
    # -----------------------------------------------------------------------
    def _build_schedule_list_tab(self, parent):
        # Top Filter Bar
        top_bar = tk.Frame(parent, bg="#ffffff")
        top_bar.pack(fill=tk.X, pady=(0, 8))

        tk.Label(top_bar, text="Filter:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 6))

        self.var_filter = tk.StringVar(value="All")
        for f_val in ["All", "Pending", "Completed"]:
            rb = tk.Radiobutton(
                top_bar, text=f_val, value=f_val, variable=self.var_filter,
                font=("Segoe UI", 9), bg="#ffffff", activebackground="#ffffff",
                cursor="hand2", command=self._refresh_schedule_list
            )
            rb.pack(side=tk.LEFT, padx=4)

        btn_clear_comp = tk.Button(
            top_bar, text="🧹 Clear Completed", font=("Segoe UI", 8),
            bg="#f1f5f9", fg="#475569", relief="flat", padx=8, pady=3,
            cursor="hand2", command=self._clear_completed
        )
        btn_clear_comp.pack(side=tk.RIGHT)

        # Treeview Table
        cols = ("id", "status", "datetime", "title", "repeat", "notes")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=12)

        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("datetime", text="Due Date & Time")
        self.tree.heading("title", text="Reminder Title")
        self.tree.heading("repeat", text="Repeat")
        self.tree.heading("notes", text="Notes")

        self.tree.column("id", width=0, stretch=False)
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("datetime", width=140, anchor="center")
        self.tree.column("title", width=220, anchor="w")
        self.tree.column("repeat", width=100, anchor="center")
        self.tree.column("notes", width=180, anchor="w")

        v_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y, before=self.tree)

        # Action Buttons below Treeview
        act_bar = tk.Frame(parent, bg="#ffffff", pady=8)
        act_bar.pack(fill=tk.X, side=tk.BOTTOM)

        btn_test = tk.Button(
            act_bar, text="🔔 Trigger / Test Now", font=("Segoe UI", 8, "bold"),
            bg="#fef3c7", fg="#92400e", relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._trigger_selected_now
        )
        btn_test.pack(side=tk.LEFT, padx=(0, 4))

        btn_toggle = tk.Button(
            act_bar, text="✅ Mark Completed / Pending", font=("Segoe UI", 8, "bold"),
            bg="#e0f2fe", fg="#0369a1", relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._toggle_selected_status
        )
        btn_toggle.pack(side=tk.LEFT, padx=4)

        btn_snooze = tk.Button(
            act_bar, text="💤 Snooze +15m", font=("Segoe UI", 8),
            bg="#f1f5f9", fg="#334155", relief="flat", padx=8, pady=4,
            cursor="hand2", command=lambda: self._snooze_selected(15)
        )
        btn_snooze.pack(side=tk.LEFT, padx=4)

        btn_delete = tk.Button(
            act_bar, text="🗑️ Delete", font=("Segoe UI", 8, "bold"),
            bg="#fee2e2", fg="#b91c1c", relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._delete_selected
        )
        btn_delete.pack(side=tk.RIGHT)

        self._refresh_schedule_list()

    def _refresh_schedule_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        settings = load_all_settings()
        reminders = settings.get("custom_reminders", [])
        filt = self.var_filter.get()

        for r in reversed(reminders):
            st = r.get("status", "pending")
            if filt == "Pending" and st != "pending":
                continue
            if filt == "Completed" and st != "completed":
                continue

            status_icon = "⏰ Pending" if st == "pending" else "✅ Done"
            self.tree.insert("", tk.END, values=(
                r.get("id"),
                status_icon,
                r.get("datetime", ""),
                r.get("title", ""),
                r.get("repeat", "none").capitalize(),
                r.get("notes", "")
            ))

    def _get_selected_reminder_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select Item", "Please select a reminder from the list first.", parent=self)
            return None
        return self.tree.item(sel[0])["values"][0]

    def _trigger_selected_now(self):
        rem_id = self._get_selected_reminder_id()
        if not rem_id:
            return
        settings = load_all_settings()
        for r in settings.get("custom_reminders", []):
            if r.get("id") == rem_id:
                engine = ReminderSchedulerEngine.get_instance(self.app_ref)
                engine._trigger_reminder(
                    item_type="custom",
                    title=f"⏰ [TEST] {r.get('title')}",
                    message=r.get("notes") or f"Scheduled for {r.get('time', '')} ({r.get('date', '')})",
                    reminder_id=rem_id
                )
                self.lbl_feedback.config(text=f"🔔 Test alert fired for '{r.get('title')}'!", fg="#2563eb")
                break

    def _toggle_selected_status(self):
        rem_id = self._get_selected_reminder_id()
        if not rem_id:
            return
        toggle_custom_reminder_status(rem_id)
        self._refresh_schedule_list()

    def _snooze_selected(self, minutes):
        rem_id = self._get_selected_reminder_id()
        if not rem_id:
            return
        snooze_custom_reminder(rem_id, minutes)
        self.lbl_feedback.config(text=f"💤 Snoozed by {minutes} mins!", fg="#0369a1")
        self._refresh_schedule_list()

    def _delete_selected(self):
        rem_id = self._get_selected_reminder_id()
        if not rem_id:
            return
        delete_custom_reminder(rem_id)
        self.lbl_feedback.config(text="🗑️ Reminder deleted.", fg="#b91c1c")
        self._refresh_schedule_list()

    def _clear_completed(self):
        cnt = clear_completed_reminders()
        self.lbl_feedback.config(text=f"🧹 Cleared {cnt} completed reminder(s).", fg="#475569")
        self._refresh_schedule_list()

    # -----------------------------------------------------------------------
    # TAB 3: Daily Shift & Work Update Auto-Reminders
    # -----------------------------------------------------------------------
    def _build_daily_shift_tab(self, parent):
        top_opts = tk.Frame(parent, bg="#ffffff")
        top_opts.pack(fill=tk.X, pady=(0, 10))

        self.var_daily_shift_enabled = tk.BooleanVar(value=self.settings.get("daily_shift_reminders_enabled", True))
        chk_daily_shift = tk.Checkbutton(
            top_opts, text="Enable Automated Daily Shift Reminders",
            variable=self.var_daily_shift_enabled, font=("Segoe UI", 9, "bold"),
            bg="#ffffff", fg="#1e293b", selectcolor="#ffffff"
        )
        chk_daily_shift.pack(side=tk.LEFT)

        self.var_skip_holidays = tk.BooleanVar(value=self.settings.get("remind_skip_weekends_holidays", True))
        chk_skip_holidays = tk.Checkbutton(
            top_opts, text="Automatically Skip on Weekends & Official Holidays",
            variable=self.var_skip_holidays, font=("Segoe UI", 9),
            bg="#ffffff", fg="#475569", selectcolor="#ffffff"
        )
        chk_skip_holidays.pack(side=tk.RIGHT)

        # Shift Reminders Grid Cards
        daily_config = self.settings.get("daily_reminders", DEFAULT_DAILY_REMINDERS)
        self.daily_entries = {}

        items = [
            ("login", "🌅 Shift Login Reminder", "#0284c7"),
            ("lunch", "🍱 Lunch Break Reminder", "#059669"),
            ("tea", "☕ Tea Break Reminder", "#d97706"),
            ("work_update", "📝 Daily Work Update & Standup Reminder", "#7c3aed")
        ]

        grid_frame = tk.Frame(parent, bg="#ffffff")
        grid_frame.pack(fill=tk.BOTH, expand=True)

        for idx, (key, title, border_col) in enumerate(items):
            c_data = daily_config.get(key, DEFAULT_DAILY_REMINDERS[key])
            card = tk.LabelFrame(
                grid_frame, text=f"  {title}  ", font=("Segoe UI", 9, "bold"),
                fg=border_col, bg="#f8fafc", bd=1, relief="solid", padx=10, pady=6
            )
            card.pack(fill=tk.X, pady=4)

            r1 = tk.Frame(card, bg="#f8fafc")
            r1.pack(fill=tk.X)

            var_en = tk.BooleanVar(value=c_data.get("enabled", True))
            chk = tk.Checkbutton(r1, text="Active", variable=var_en, font=("Segoe UI", 8, "bold"), bg="#f8fafc", selectcolor="#f8fafc")
            chk.pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(r1, text="Time:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 4))
            ent_time = tk.Entry(r1, font=("Segoe UI", 8), width=10, relief="solid", bd=1)
            ent_time.pack(side=tk.LEFT, ipady=1)
            ent_time.insert(0, c_data.get("time", "10:00 AM"))

            tk.Label(r1, text="Message:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(12, 4))
            ent_msg = tk.Entry(r1, font=("Segoe UI", 8), relief="solid", bd=1)
            ent_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=1)
            ent_msg.insert(0, c_data.get("message", ""))

            self.daily_entries[key] = {
                "var_en": var_en,
                "ent_time": ent_time,
                "ent_msg": ent_msg
            }

        # Save Button
        btn_save_daily = tk.Button(
            parent, text="💾 Save Daily Shift Reminders Configuration",
            font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white",
            activebackground="#15803d", activeforeground="white",
            relief="flat", padx=16, pady=6, cursor="hand2", command=self._save_daily_shift_settings
        )
        btn_save_daily.pack(side=tk.RIGHT, pady=(10, 0))

    def _save_daily_shift_settings(self):
        settings = load_all_settings()
        settings["daily_shift_reminders_enabled"] = self.var_daily_shift_enabled.get()
        settings["remind_skip_weekends_holidays"] = self.var_skip_holidays.get()

        daily_cfg = settings.get("daily_reminders", {})
        for key, widgets in self.daily_entries.items():
            daily_cfg[key] = {
                "enabled": widgets["var_en"].get(),
                "time": widgets["ent_time"].get().strip(),
                "title": DEFAULT_DAILY_REMINDERS[key]["title"],
                "message": widgets["ent_msg"].get().strip()
            }
        settings["daily_reminders"] = daily_cfg
        save_all_settings(settings)
        self.lbl_feedback.config(text="✅ Daily shift reminders updated & saved!", fg="#16a34a")

    def _toggle_master_switch(self):
        val = self.var_master_enabled.get()
        settings = load_all_settings()
        settings["reminders_enabled"] = val
        save_all_settings(settings)
        status_txt = "ACTIVATED" if val else "PAUSED"
        self.lbl_feedback.config(text=f"Reminders system {status_txt}.", fg="#0284c7" if val else "#dc2626")
