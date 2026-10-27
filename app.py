import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import subprocess
import re
import json
import datetime
import calendar
import csv
import urllib.request
import urllib.parse
import webbrowser
import threading
import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import from_excel
from collections import defaultdict
from lan_chat import LANChatEngine, LANChatDialog

def open_file_externally(filepath):
    """Open a file with the default system application across Windows, macOS, and Linux."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(filepath)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", filepath], check=True)
            return True
        else:
            subprocess.run(["xdg-open", filepath], check=True)
            return True
    except Exception as e:
        print(f"Error opening file externally: {e}")
        return False

def center_window(window, parent=None, default_w=None, default_h=None, min_w=None, min_h=None):
    """Auto-adjust and center a window relative to its parent or screen, ensuring it fits cleanly on any display."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    w = default_w or window.winfo_reqwidth()
    h = default_h or window.winfo_reqheight()

    # Scale down gracefully if display viewport is smaller than dialog's desired size
    w = min(w, max(420, screen_w - 50))
    h = min(h, max(320, screen_h - 80))

    if min_w is not None or min_h is not None:
        actual_min_w = min(min_w or 420, w)
        actual_min_h = min(min_h or 320, h)
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

    # Keep completely within screen viewport bounds
    x = max(10, min(x, screen_w - w - 10))
    y = max(10, min(y, screen_h - h - 50))

    window.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")

FILE = "data.xlsx"
SETTINGS_FILE = "settings.json"

HEADERS = [
    "ID",
    "Date",
    "Project / Module",
    "Task Title",
    "Work Description",
    "Hours Spent",
    "Status",
    "Remarks",
    "Login Time",
    "Logout Time",
    "Lunch Break",
    "Tea Break",
    "Logged At"
]

STANDARD_HOLIDAYS_2026 = [
    {"date": "2026-01-26", "name": "Republic Day"},
    {"date": "2026-03-04", "name": "Maha Shivratri"},
    {"date": "2026-03-20", "name": "Holi"},
    {"date": "2026-03-21", "name": "Id-ul-Fitr (Eid)"},
    {"date": "2026-04-03", "name": "Good Friday"},
    {"date": "2026-04-14", "name": "Dr. Ambedkar Jayanti"},
    {"date": "2026-05-01", "name": "Maharashtra Day / May Day"},
    {"date": "2026-05-28", "name": "Bakrid / Eid-al-Adha"},
    {"date": "2026-08-15", "name": "Independence Day"},
    {"date": "2026-08-28", "name": "Raksha Bandhan"},
    {"date": "2026-09-04", "name": "Janmashtami"},
    {"date": "2026-09-15", "name": "Milad-un-Nabi"},
    {"date": "2026-10-02", "name": "Mahatma Gandhi Jayanti"},
    {"date": "2026-10-20", "name": "Dussehra (Vijayadashami)"},
    {"date": "2026-11-08", "name": "Diwali (Laxmi Pujan)"},
    {"date": "2026-11-09", "name": "Govardhan Puja / New Year"},
    {"date": "2026-11-10", "name": "Bhai Dooj"},
    {"date": "2026-11-24", "name": "Guru Nanak Jayanti"},
    {"date": "2026-12-25", "name": "Christmas"}
]

DEFAULT_SETTINGS = {
    "user_name": "Developer",
    "webhook_url": "",
    "webhook_type": "Microsoft Teams",
    "auto_copy_on_save": True,
    "prompt_team_share_on_save": True,
    "default_login_time": "10:00 AM",
    "default_logout_time": "07:30 PM",
    "default_lunch_break": "01:00 PM - 02:00 PM",
    "default_tea_break": "04:30 PM - 04:45 PM",
    "weekend_mode": "Sunday",
    "second_fourth_saturday": False,
    "weekly_offs": ["Sunday"],
    "holidays": STANDARD_HOLIDAYS_2026,
    "auto_arrange_by_date": True,
    "date_sort_order": "asc",
    "auto_sync_weekends_holidays": True,
    "highlight_weekends_holidays": True,
    "daily_timings": {},
    "recent_teammates": [],
    "data_api_url": "",
    "data_api_token": "",
    "data_api_sync_on_edit": True,
    "data_api_sync_on_create": True,
    "data_api_sync_on_delete": True,
    "lan_chat_enabled": True,
    "lan_chat_port": 45454,
    "gsheet_webapp_url": "",
    "gsheet_auto_sync": True,
    "gsheet_last_sync": ""
}

# ---------- Settings Management ----------
def load_settings():
    merged = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged.update(data)
        except Exception:
            pass
    if "weekly_offs" not in merged or not isinstance(merged["weekly_offs"], list):
        merged["weekly_offs"] = ["Sunday"]
    if "holidays" not in merged or not isinstance(merged["holidays"], list):
        merged["holidays"] = STANDARD_HOLIDAYS_2026
    if "weekend_mode" not in merged:
        merged["weekend_mode"] = "Sunday"
    if "second_fourth_saturday" not in merged:
        merged["second_fourth_saturday"] = False
    if "auto_arrange_by_date" not in merged:
        merged["auto_arrange_by_date"] = True
    if "date_sort_order" not in merged:
        merged["date_sort_order"] = "asc"
    if "auto_sync_weekends_holidays" not in merged:
        merged["auto_sync_weekends_holidays"] = True
    if "highlight_weekends_holidays" not in merged:
        merged["highlight_weekends_holidays"] = True
    if "data_api_url" not in merged:
        merged["data_api_url"] = ""
    if "data_api_token" not in merged:
        merged["data_api_token"] = ""
    if "data_api_sync_on_edit" not in merged:
        merged["data_api_sync_on_edit"] = True
    if "data_api_sync_on_create" not in merged:
        merged["data_api_sync_on_create"] = True
    if "data_api_sync_on_delete" not in merged:
        merged["data_api_sync_on_delete"] = True
    if "lan_chat_enabled" not in merged:
        merged["lan_chat_enabled"] = True
    if "lan_chat_port" not in merged:
        merged["lan_chat_port"] = 45454
    if "gsheet_webapp_url" not in merged:
        merged["gsheet_webapp_url"] = ""
    if "gsheet_auto_sync" not in merged:
        merged["gsheet_auto_sync"] = True
    return merged

def save_settings(settings_data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=4)
        return True
    except Exception as e:
        print("Error saving settings:", e)
        return False

# ---------- Holiday & Weekly Off Helper Queries ----------
def get_configured_weekly_offs():
    """Retrieve list of configured weekly off day names (e.g. ['Sunday'])."""
    settings = load_settings()
    offs = settings.get("weekly_offs")
    if not isinstance(offs, list):
        offs = ["Sunday"]
    return offs

def get_configured_holidays():
    """Retrieve list of holiday dicts [{'date': 'YYYY-MM-DD', 'name': '...'}]."""
    settings = load_settings()
    holidays = settings.get("holidays", [])
    if not isinstance(holidays, list):
        holidays = STANDARD_HOLIDAYS_2026
    try:
        holidays = sorted(holidays, key=lambda h: h.get("date", ""))
    except Exception:
        pass
    return holidays

def get_holidays_map():
    """Returns {norm_date_str: holiday_name} dictionary for quick lookup."""
    h_list = get_configured_holidays()
    h_map = {}
    for item in h_list:
        d = format_date_only(item.get("date", ""))
        name = item.get("name", "Holiday")
        if d:
            h_map[d] = name
    return h_map

def is_date_holiday(date_str):
    """Check if date is a configured Holiday. Returns holiday name or None."""
    norm_date = format_date_only(date_str)
    if not norm_date:
        return None
    h_map = get_holidays_map()
    return h_map.get(norm_date)

def is_date_weekly_off(date_str, settings=None):
    """Check if date falls on a configured Weekly Off or 2nd/4th Saturday. Returns day name / reason or None."""
    norm_date = format_date_only(date_str)
    if not norm_date:
        return None
    if settings is None:
        settings = load_settings()
    try:
        dt = datetime.datetime.strptime(norm_date, "%Y-%m-%d").date()
        day_name = dt.strftime("%A")
        
        # Check explicit weekly offs list (e.g. Sunday, Saturday)
        weekly_offs = settings.get("weekly_offs", ["Sunday"])
        if not isinstance(weekly_offs, list):
            weekly_offs = ["Sunday"]
        if day_name in weekly_offs:
            return day_name

        # Check 2nd and 4th Saturday if enabled
        if settings.get("second_fourth_saturday", False) and day_name == "Saturday":
            sats = [d for d in range(1, calendar.monthrange(dt.year, dt.month)[1] + 1)
                    if datetime.date(dt.year, dt.month, d).weekday() == 5]
            if len(sats) >= 2 and dt.day == sats[1]:
                return "2nd Saturday"
            if len(sats) >= 4 and dt.day == sats[3]:
                return "4th Saturday"
    except Exception:
        pass
    return None

# ---------- Daily Shift & Break Timings Storage ----------
def get_daily_timings(date_str):
    """Retrieve saved shift & break timings for a specific date (YYYY-MM-DD)."""
    settings = load_settings()
    daily_timings = settings.get("daily_timings", {})
    norm_date = format_date_only(date_str)
    if norm_date in daily_timings:
        t = daily_timings[norm_date]
        return {
            "login": t.get("login", ""),
            "logout": t.get("logout", ""),
            "lunch": t.get("lunch", ""),
            "tea": t.get("tea", ""),
            "lunch_taken": t.get("lunch_taken", bool(t.get("lunch"))),
            "tea_taken": t.get("tea_taken", bool(t.get("tea")))
        }
    return {
        "login": settings.get("default_login_time", "10:00 AM"),
        "logout": settings.get("default_logout_time", "07:30 PM"),
        "lunch": settings.get("default_lunch_break", "01:00 PM - 02:00 PM"),
        "tea": settings.get("default_tea_break", "04:30 PM - 04:45 PM"),
        "lunch_taken": True,
        "tea_taken": True
    }

def save_daily_timings(date_str, timings_dict):
    """Save or update shift & break timings for a specific date."""
    if not date_str:
        return
    norm_date = format_date_only(date_str)
    settings = load_settings()
    if "daily_timings" not in settings or not isinstance(settings["daily_timings"], dict):
        settings["daily_timings"] = {}
    settings["daily_timings"][norm_date] = {
        "login": timings_dict.get("login", "").strip(),
        "logout": timings_dict.get("logout", "").strip(),
        "lunch": timings_dict.get("lunch", "").strip(),
        "tea": timings_dict.get("tea", "").strip(),
        "lunch_taken": bool(timings_dict.get("lunch_taken", bool(timings_dict.get("lunch")))),
        "tea_taken": bool(timings_dict.get("tea_taken", bool(timings_dict.get("tea"))))
    }
    save_settings(settings)

# ---------- Time Parsing & Working Hours Calculation Helpers ----------
def parse_time_to_minutes(time_str):
    """Convert time string (e.g., '10:00 AM', '6:30 PM', '18:30', '9:30') to minutes from midnight."""
    if not time_str:
        return None
    s = str(time_str).strip()
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

def parse_break_duration_minutes(b_str):
    """Extract duration in minutes from break string (e.g., '01:00 PM - 02:00 PM', '45 mins', '1 hr', '15m')."""
    if not b_str:
        return 0
    s = str(b_str).strip()
    range_match = re.split(r'\s*(?:-|–|to)\s*', s)
    if len(range_match) == 2:
        t1 = parse_time_to_minutes(range_match[0])
        t2 = parse_time_to_minutes(range_match[1])
        if t1 is not None and t2 is not None:
            diff = t2 - t1
            if diff < 0:
                diff += 24 * 60
            return diff
    m_min = re.search(r'([\d.]+)\s*(?:mins?|minutes?|m\b)', s, re.IGNORECASE)
    if m_min:
        try:
            return float(m_min.group(1))
        except ValueError:
            pass
    m_hr = re.search(r'([\d.]+)\s*(?:hrs?|hours?|h\b)', s, re.IGNORECASE)
    if m_hr:
        try:
            return float(m_hr.group(1)) * 60
        except ValueError:
            pass
    return 0

def calculate_net_working_hours(login_str, logout_str, lunch_str="", tea_str="", lunch_taken=True, tea_taken=True):
    """
    Compute net working hours:
    (Logout - Login) - Lunch (if taken) - Tea (if taken).
    Returns (net_hours_float, net_hours_str, span_hours_float, lunch_mins, tea_mins).
    """
    t_login = parse_time_to_minutes(login_str)
    t_logout = parse_time_to_minutes(logout_str)
    if t_login is None or t_logout is None:
        return 0.0, "", 0.0, 0, 0

    diff_mins = t_logout - t_login
    if diff_mins < 0:
        diff_mins += 24 * 60

    span_hours = round(diff_mins / 60.0, 2)
    lunch_mins = parse_break_duration_minutes(lunch_str) if (lunch_taken and lunch_str) else 0
    tea_mins = parse_break_duration_minutes(tea_str) if (tea_taken and tea_str) else 0

    net_mins = max(0.0, diff_mins - lunch_mins - tea_mins)
    net_hours = round(net_mins / 60.0, 2)

    net_str = f"{net_hours:.2f}".rstrip('0').rstrip('.') if '.' in f"{net_hours:.2f}" else f"{net_hours}"
    if '.' not in net_str:
        net_str += ".0"
    return net_hours, net_str, span_hours, lunch_mins, tea_mins

def format_current_time_str():
    """Return formatted current time e.g., '10:00 AM'."""
    return datetime.datetime.now().strftime("%I:%M %p")

def format_human_time(val):
    """Format decimal hours float or string into friendly 'X hrs Y mins' string."""
    try:
        total_mins = round(float(val) * 60)
    except (ValueError, TypeError):
        return str(val or "")
    if total_mins <= 0:
        return "0 hrs"
    h = total_mins // 60
    m = total_mins % 60
    h_label = "hr" if h == 1 else "hrs"
    m_label = "min" if m == 1 else "mins"
    if h > 0 and m > 0:
        return f"{h} {h_label} {m} {m_label}"
    elif h > 0:
        return f"{h}.0 hrs"
    elif m > 0:
        return f"{m} {m_label}"
    return "0 hrs"

def format_duration_display(val):
    """Format duration for markdown headers, showing both human time and decimal e.g. '8 hrs 51 mins (8.85 hrs)'."""
    try:
        f_val = float(val)
    except (ValueError, TypeError):
        return str(val or "")
    total_mins = round(f_val * 60)
    m = total_mins % 60
    human = format_human_time(f_val)
    if m > 0:
        return f"{human} ({f_val:.2f} hrs)"
    return f"{f_val:.1f} hrs"

def parse_duration_to_hours(s):
    """
    Parse a duration string (e.g. '8.85', '8:51', '8h 51m', '8 hrs 51 mins') to decimal hours float.
    Returns (hours_float, hours_formatted_str).
    """
    if s is None or s == "":
        return 0.0, ""
    if isinstance(s, (int, float)):
        v = float(s)
        s_val = f"{v:.2f}".rstrip('0').rstrip('.') if '.' in f"{v:.2f}" else f"{v}"
        if '.' not in s_val:
            s_val += ".0"
        return v, s_val
    if isinstance(s, datetime.time):
        dec = round(s.hour + s.minute / 60.0 + s.second / 3600.0, 2)
        s_val = f"{dec:.2f}".rstrip('0').rstrip('.') if '.' in f"{dec:.2f}" else f"{dec}"
        if '.' not in s_val:
            s_val += ".0"
        return dec, s_val
    s_clean = str(s).strip()
    m_col = re.match(r'^(\d{1,2}):(\d{1,2})$', s_clean)
    if m_col:
        h, m = int(m_col.group(1)), int(m_col.group(2))
        dec = round(h + m / 60.0, 2)
        return dec, f"{dec:.2f}".rstrip('0').rstrip('.')
    
    m_word = re.search(r'(?:(\d+(?:\.\d+)?)\s*(?:hrs?|hours?|h))?\s*(?:(\d+(?:\.\d+)?)\s*(?:mins?|minutes?|m))?', s_clean, re.I)
    if m_word and (m_word.group(1) or m_word.group(2)):
        h = float(m_word.group(1)) if m_word.group(1) else 0.0
        m = float(m_word.group(2)) if m_word.group(2) else 0.0
        dec = round(h + m / 60.0, 2)
        return dec, f"{dec:.2f}".rstrip('0').rstrip('.')

    try:
        val = float(s_clean)
        return val, f"{val:.2f}".rstrip('0').rstrip('.')
    except ValueError:
        return 0.0, ""

# ---------- Helper Functions ----------
# ---------- Helper Functions & Date Formatting ----------
def format_date_only(val):
    """Normalize any date representation (datetime, date, serial number, string) to 'YYYY-MM-DD'."""
    if val is None or val == "":
        return ""
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        try:
            return from_excel(val).strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(val).strip()
    if s.isdigit() and len(s) == 5:
        try:
            return from_excel(int(s)).strftime("%Y-%m-%d")
        except Exception:
            pass
    if "T" in s:
        s = s.split("T")[0]
    if " " in s and not re.search(r'[A-Za-z]', s):
        s = s.split(" ")[0]
    s = re.sub(r'\s+\d{1,2}:\d{2}(?::\d{2})?.*$', '', s).strip()
    for fmt in (
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d %B %Y",
        "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y"
    ):
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s

def get_month_sheet_name(date_str):
    """Returns sheet name formatted as 'Month YYYY' (e.g., 'October 2026') from date."""
    normalized = format_date_only(date_str)
    try:
        dt = datetime.datetime.strptime(normalized, "%Y-%m-%d")
        return dt.strftime("%B %Y")
    except Exception:
        return datetime.datetime.now().strftime("%B %Y")

def style_header_row(ws):
    """Apply styling to the header row in openpyxl."""
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_num in range(1, len(HEADERS) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    ws.row_dimensions[1].height = 28

def restyle_all_rows_in_sheet(ws):
    """Ensure header is styled and all data rows have clean borders, proper alignments, and distinct fills for holidays & weekly offs."""
    style_header_row(ws)
    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB")
    )
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    holiday_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    holiday_font = Font(name="Calibri", size=10, bold=True, color="92400E")

    weekly_off_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
    weekly_off_font = Font(name="Calibri", size=10, bold=True, color="1E40AF")

    leave_fill = PatternFill(start_color="FCE7F3", end_color="FCE7F3", fill_type="solid")
    leave_font = Font(name="Calibri", size=10, bold=True, color="9D174D")

    regular_font = Font(name="Calibri", size=10, color="1E293B")
    white_fill = PatternFill(fill_type=None)

    for row_idx in range(2, ws.max_row + 1):
        status_val = str(ws.cell(row=row_idx, column=7).value or "").strip()
        proj_val = str(ws.cell(row=row_idx, column=3).value or "").strip()
        title_val = str(ws.cell(row=row_idx, column=4).value or "").strip()
        st_lower = status_val.lower()
        pj_lower = proj_val.lower()
        tt_lower = title_val.lower()

        is_holiday = ("holiday" in st_lower or "holiday" in pj_lower or "holiday" in tt_lower)
        is_weekly_off = ("weekly off" in st_lower or "weekly off" in pj_lower or "weekly off" in tt_lower or "weekend" in st_lower or "weekend" in pj_lower)
        is_leave = ("leave" in st_lower or "leave" in pj_lower or "leave" in tt_lower)

        ws.row_dimensions[row_idx].height = 24

        for col_idx in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            if is_holiday:
                cell.fill = holiday_fill
                cell.font = holiday_font
            elif is_weekly_off:
                cell.fill = weekly_off_fill
                cell.font = weekly_off_font
            elif is_leave:
                cell.fill = leave_fill
                cell.font = leave_font
            else:
                cell.font = regular_font
                cell.fill = white_fill

            if col_idx in (1, 2, 6, 7, 9, 10, 11, 12, 13):
                cell.alignment = align_center
            else:
                cell.alignment = align_left

def sort_sheet_records_by_date(ws, ascending=True):
    """
    Sorts all data rows (row 2 onwards) chronologically by Date.
    If dates match: Holidays come first, then Weekly Offs, then Leaves, then work updates sorted by login time or ID.
    Re-applies all styles and adjusts column widths.
    """
    if ws.max_row <= 2:
        restyle_all_rows_in_sheet(ws)
        adjust_column_widths(ws)
        return

    data_rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        data_rows.append(list(row))

    if not data_rows:
        return

    def sort_key(r):
        raw_date = str(r[1] or "").strip()
        norm_date = format_date_only(raw_date)
        try:
            d_obj = datetime.datetime.strptime(norm_date, "%Y-%m-%d").date()
        except Exception:
            d_obj = datetime.date(2099, 12, 31)

        status_val = str(r[6] or "").strip().lower() if len(r) > 6 else ""
        proj_val = str(r[2] or "").strip().lower() if len(r) > 2 else ""

        if "holiday" in status_val or "holiday" in proj_val:
            type_prio = 0
        elif "weekly off" in status_val or "weekly off" in proj_val or "weekend" in status_val:
            type_prio = 1
        elif "leave" in status_val or "leave" in proj_val:
            type_prio = 2
        else:
            type_prio = 3

        login_val = str(r[8] or "").strip() if len(r) > 8 else ""
        t_mins = parse_time_to_minutes(login_val)
        if t_mins is None:
            t_mins = 9999

        id_str = str(r[0] or "")
        d_val = d_obj if ascending else -d_obj.toordinal()
        return (d_val, type_prio, t_mins, id_str)

    data_rows.sort(key=sort_key)

    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    for r in data_rows:
        while len(r) < len(HEADERS):
            r.append("")
        ws.append(r)

    restyle_all_rows_in_sheet(ws)
    adjust_column_widths(ws)

def auto_arrange_sheet_by_date(sheet_name, ascending=True):
    """
    Explicitly auto-arranges all rows in the given sheet of data.xlsx chronologically date-wise.
    Re-applies styles and column widths and saves workbook.
    """
    if not os.path.exists(FILE):
        return False
    try:
        wb = load_workbook(FILE)
        if sheet_name not in wb.sheetnames:
            return False
        ws = wb[sheet_name]
        sort_sheet_records_by_date(ws, ascending=ascending)
        wb.save(FILE)
        trigger_google_sheet_auto_sync(sheet_name)
        return True
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return False
    except Exception as e:
        print("auto_arrange_sheet_by_date error:", e)
        return False

def adjust_column_widths(ws):
    """Auto-fit column widths based on contents."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            if "\n" in val:
                val = max(val.split("\n"), key=len)
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

def sync_month_holidays_and_weekly_offs(target_month=None, clean_re_sync=False, silent=False):
    """
    Populates missing holidays and weekly offs for the specified month tab in data.xlsx.
    If clean_re_sync=True, removes old placeholder holidays and weekly offs first (preserving actual work tasks).
    Auto-sorts sheet by date.
    Returns (added_holidays_count, added_offs_count, sheet_name).
    """
    if not target_month:
        target_month = datetime.datetime.now().strftime("%B %Y")

    try:
        dt_month = datetime.datetime.strptime(target_month, "%B %Y")
        year = dt_month.year
        month_num = dt_month.month
    except Exception:
        now = datetime.datetime.now()
        year = now.year
        month_num = now.month
        target_month = now.strftime("%B %Y")

    _, num_days = calendar.monthrange(year, month_num)

    settings = load_settings()
    holidays_map = get_holidays_map()

    try:
        wb = load_workbook(FILE)
        ensure_excel_schema(wb)
    except PermissionError:
        if not silent:
            messagebox.showerror("Permission Error", f"Cannot access '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, 0, target_month
    except Exception:
        wb = Workbook()

    ws = get_or_create_sheet(wb, target_month)

    # If clean_re_sync: purge placeholder holiday and weekly off rows (where hours are 0/-)
    if clean_re_sync:
        rows_to_keep = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            r_status = str(row[6] or "").strip().lower() if len(row) > 6 else ""
            r_proj = str(row[2] or "").strip().lower() if len(row) > 2 else ""
            h_val = str(row[5] or "").strip() if len(row) > 5 else ""
            is_zero_hours = (h_val in ("", "0", "0.0", "-"))
            if ("holiday" in r_status or "holiday" in r_proj) and is_zero_hours:
                continue
            if ("weekly off" in r_status or "weekly off" in r_proj or "weekend" in r_status) and is_zero_hours:
                continue
            rows_to_keep.append(list(row))

        if ws.max_row >= 2:
            ws.delete_rows(2, ws.max_row - 1)
        for r in rows_to_keep:
            while len(r) < len(HEADERS):
                r.append("")
            ws.append(r)

    # Inspect existing records for this month
    existing_dates_with_holiday = set()
    existing_dates_with_off = set()
    existing_dates_with_leave = set()
    existing_dates_with_work = set()

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        r_date = format_date_only(row[1])
        r_status = str(row[6] or "").strip().lower() if len(row) > 6 else ""
        r_proj = str(row[2] or "").strip().lower() if len(row) > 2 else ""

        if "holiday" in r_status or "holiday" in r_proj:
            existing_dates_with_holiday.add(r_date)
        elif "weekly off" in r_status or "weekly off" in r_proj or "weekend" in r_status:
            existing_dates_with_off.add(r_date)
        elif "leave" in r_status or "leave" in r_proj:
            existing_dates_with_leave.add(r_date)
        else:
            existing_dates_with_work.add(r_date)

    # Clean up any redundant 0-hour weekly off placeholders if actual work or leave has been recorded on that date
    conflicting_dates = existing_dates_with_off.intersection(existing_dates_with_work.union(existing_dates_with_leave))
    if conflicting_dates:
        cleaned_rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            r_date = format_date_only(row[1])
            r_status = str(row[6] or "").strip().lower() if len(row) > 6 else ""
            r_proj = str(row[2] or "").strip().lower() if len(row) > 2 else ""
            h_val = str(row[5] or "").strip() if len(row) > 5 else ""
            is_zero = (h_val in ("", "0", "0.0", "-"))
            if r_date in conflicting_dates and ("weekly off" in r_status or "weekly off" in r_proj) and is_zero:
                continue
            cleaned_rows.append(list(row))
        if ws.max_row >= 2:
            ws.delete_rows(2, ws.max_row - 1)
        for r in cleaned_rows:
            while len(r) < len(HEADERS):
                r.append("")
            ws.append(r)
        existing_dates_with_off -= conflicting_dates

    added_holidays = 0
    added_offs = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for day in range(1, num_days + 1):
        dt = datetime.date(year, month_num, day)
        date_str = dt.strftime("%Y-%m-%d")

        # Check Holiday first
        if date_str in holidays_map:
            if date_str not in existing_dates_with_holiday:
                h_name = holidays_map[date_str]
                rec_id = f"HOL-{dt.strftime('%y%m%d')}"
                ws.append([rec_id, date_str, "Holiday", h_name, f"Official Holiday: {h_name}", "0.0", "Holiday", "Official Holiday", "-", "-", "-", "-", now_str])
                added_holidays += 1
                existing_dates_with_holiday.add(date_str)
        else:
            # Check Weekly Off / Weekend (including 2nd/4th Saturday)
            off_name = is_date_weekly_off(date_str, settings)
            if off_name:
                if date_str not in existing_dates_with_off and date_str not in existing_dates_with_work and date_str not in existing_dates_with_leave:
                    rec_id = f"WO-{dt.strftime('%y%m%d')}"
                    ws.append([rec_id, date_str, "Weekly Off", f"Weekly Off ({off_name})", f"Weekend / Weekly Off: {off_name}", "0.0", "Weekly Off", "Weekly Off", "-", "-", "-", "-", now_str])
                    added_offs += 1
                    existing_dates_with_off.add(date_str)

    asc = (settings.get("date_sort_order", "asc") == "asc")
    sort_sheet_records_by_date(ws, ascending=asc)
    try:
        wb.save(FILE)
        if added_holidays > 0 or added_offs > 0:
            trigger_google_sheet_auto_sync(target_month)
    except PermissionError:
        if not silent:
            messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, 0, target_month

    return added_holidays, added_offs, target_month

# ---------- Excel Data Operations ----------
def ensure_excel_schema(wb):
    """Ensure all sheets in workbook have the updated 13 columns including Login, Logout, Lunch, and Tea breaks."""
    modified = False
    for s_name in wb.sheetnames:
        ws = wb[s_name]
        headers = [c.value for c in ws[1]]
        if "Login Time" not in headers:
            if len(headers) == 9:
                ws.insert_cols(9, 4)
                ws.cell(1, 9).value = "Login Time"
                ws.cell(1, 10).value = "Logout Time"
                ws.cell(1, 11).value = "Lunch Break"
                ws.cell(1, 12).value = "Tea Break"
                style_header_row(ws)
                adjust_column_widths(ws)
                modified = True
            elif len(headers) < len(HEADERS):
                ws.delete_rows(1)
                ws.insert_rows(1)
                ws.append(HEADERS)
                style_header_row(ws)
                adjust_column_widths(ws)
                modified = True
    return modified

def init_file():
    """Initialize data.xlsx with current month tab if file doesn't exist, migrate schema, and auto-sort all sheets by date."""
    current_month = datetime.datetime.now().strftime("%B %Y")
    if not os.path.exists(FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = current_month
        ws.append(HEADERS)
        style_header_row(ws)
        adjust_column_widths(ws)
        try:
            wb.save(FILE)
        except Exception:
            pass
    else:
        try:
            wb = load_workbook(FILE)
            changed = False
            if "Records" in wb.sheetnames and len(wb.sheetnames) == 1:
                ws = wb.create_sheet(title=current_month)
                ws.append(HEADERS)
                style_header_row(ws)
                adjust_column_widths(ws)
                wb.remove(wb["Records"])
                changed = True
            elif current_month not in wb.sheetnames and len(wb.sheetnames) == 0:
                ws = wb.create_sheet(title=current_month)
                ws.append(HEADERS)
                style_header_row(ws)
                adjust_column_widths(ws)
                changed = True
            
            if ensure_excel_schema(wb):
                changed = True

            if changed:
                wb.save(FILE)
            wb.close()

            # Auto-sync weekends & holidays and sort all sheets by date
            settings = load_settings()
            sheet_names = get_available_months()
            auto_sync = settings.get("auto_sync_weekends_holidays", True)
            for s_name in sheet_names:
                if auto_sync:
                    sync_month_holidays_and_weekly_offs(s_name, silent=True)
                elif settings.get("auto_arrange_by_date", True):
                    auto_arrange_sheet_by_date(s_name)
        except Exception as e:
            print("Init file exception:", e)

def get_or_create_sheet(wb, sheet_name):
    """Get worksheet or create with proper headers and styling."""
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(title=sheet_name)
        ws.append(HEADERS)
        style_header_row(ws)
    return ws

def save_work_update(date_str, project, task_title, description, hours, status_val, remarks, 
                     login_time="", logout_time="", lunch_break="", tea_break="", record_id=None):
    """Save or update single work update in the appropriate Month sheet with shift & break timings, auto-arranging by date."""
    sheet_name = get_month_sheet_name(date_str)
    try:
        wb = load_workbook(FILE)
        ensure_excel_schema(wb)
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot access '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return False
    except Exception:
        wb = Workbook()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save daily timings to settings cache
    if login_time or logout_time or lunch_break or tea_break:
        save_daily_timings(date_str, {
            "login": login_time,
            "logout": logout_time,
            "lunch": lunch_break,
            "tea": tea_break,
            "lunch_taken": bool(lunch_break),
            "tea_taken": bool(tea_break)
        })

    if not record_id:
        ts = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
        record_id = f"WU-{ts}"
        ws = get_or_create_sheet(wb, sheet_name)
        row_data = [record_id, date_str, project, task_title, description, hours, status_val, remarks, 
                    login_time, logout_time, lunch_break, tea_break, now_str]
        ws.append(row_data)
        sort_sheet_records_by_date(ws)
        try:
            wb.save(FILE)
            trigger_google_sheet_auto_sync(sheet_name)
            return True
        except PermissionError:
            messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
            return False
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred: {e}")
            return False
    else:
        found = False
        affected_sheets = [sheet_name]
        target_ws = get_or_create_sheet(wb, sheet_name)
        for s_name in wb.sheetnames:
            ws = wb[s_name]
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
                if row[0].value == record_id:
                    if s_name != sheet_name:
                        ws.delete_rows(row_idx)
                        target_ws.append([record_id, date_str, project, task_title, description, hours, status_val, remarks, 
                                          login_time, logout_time, lunch_break, tea_break, now_str])
                        sort_sheet_records_by_date(ws)
                        sort_sheet_records_by_date(target_ws)
                        affected_sheets = [s_name, sheet_name]
                    else:
                        row[1].value = date_str
                        row[2].value = project
                        row[3].value = task_title
                        row[4].value = description
                        row[5].value = hours
                        row[6].value = status_val
                        row[7].value = remarks
                        ws.cell(row=row_idx, column=9).value = login_time
                        ws.cell(row=row_idx, column=10).value = logout_time
                        ws.cell(row=row_idx, column=11).value = lunch_break
                        ws.cell(row=row_idx, column=12).value = tea_break
                        ws.cell(row=row_idx, column=13).value = now_str
                        sort_sheet_records_by_date(ws)
                        affected_sheets = [sheet_name]
                    found = True
                    break
            if found:
                break
        
        if not found:
            target_ws.append([record_id, date_str, project, task_title, description, hours, status_val, remarks, 
                       login_time, logout_time, lunch_break, tea_break, now_str])
            sort_sheet_records_by_date(target_ws)

        try:
            wb.save(FILE)
            trigger_google_sheet_auto_sync(affected_sheets)
            return True
        except PermissionError:
            messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
            return False
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred: {e}")
            return False

def save_bulk_work_updates(date_str, project, tasks_list, batch_login="", batch_logout="", batch_lunch="", batch_tea=""):
    """Save multiple tasks at once into the appropriate month tab with shift & break timings, auto-arranging by date."""
    if not tasks_list:
        return 0, ""
    sheet_name = get_month_sheet_name(date_str)
    try:
        wb = load_workbook(FILE)
        ensure_excel_schema(wb)
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot access '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, ""
    except Exception:
        wb = Workbook()

    ws = get_or_create_sheet(wb, sheet_name)
    now_dt = datetime.datetime.now()
    saved_count = 0

    if batch_login or batch_logout or batch_lunch or batch_tea:
        save_daily_timings(date_str, {
            "login": batch_login,
            "logout": batch_logout,
            "lunch": batch_lunch,
            "tea": batch_tea,
            "lunch_taken": bool(batch_lunch),
            "tea_taken": bool(batch_tea)
        })

    for i, t in enumerate(tasks_list, start=1):
        ts = (now_dt + datetime.timedelta(seconds=i)).strftime("%y%m%d-%H%M%S")
        record_id = f"WU-{ts}"
        task_title = t.get("title", "Untitled Task")
        description = t.get("desc", "")
        hours = str(t.get("hours", "") or "").strip()
        status_val = t.get("status", "Completed")
        remarks = t.get("remarks", "")
        t_login = t.get("login") if t.get("login") is not None else batch_login
        t_logout = t.get("logout") if t.get("logout") is not None else batch_logout
        t_lunch = t.get("lunch") if t.get("lunch") is not None else batch_lunch
        t_tea = t.get("tea") if t.get("tea") is not None else batch_tea
        now_str = (now_dt + datetime.timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")

        ws.append([record_id, date_str, project, task_title, description, hours, status_val, remarks, 
                   t_login, t_logout, t_lunch, t_tea, now_str])
        saved_count += 1

    sort_sheet_records_by_date(ws)
    try:
        wb.save(FILE)
        trigger_google_sheet_auto_sync(sheet_name)
        return saved_count, sheet_name
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, sheet_name
    except Exception as e:
        messagebox.showerror("Save Error", f"An error occurred: {e}")
        return 0, sheet_name

def save_excel_file_bulk_import(tasks_list, default_proj="General Work"):
    """
    Imports list of tasks parsed from an uploaded Excel or CSV file.
    Routes tasks to their respective Month sheets based on date.
    Auto-sorts each affected sheet chronologically by date.
    Updates daily shift timings cache.
    Returns (total_saved, dict_of_counts_per_sheet).
    """
    if not tasks_list:
        return 0, {}

    try:
        wb = load_workbook(FILE)
        ensure_excel_schema(wb)
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot access '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, {}
    except Exception:
        wb = Workbook()

    now_dt = datetime.datetime.now()
    counts_per_sheet = {}
    affected_sheets = set()
    total_saved = 0

    # Group tasks by month tab
    tasks_by_sheet = {}
    for t in tasks_list:
        d_val = format_date_only(t.get("date", "")) or now_dt.strftime("%Y-%m-%d")
        s_name = get_month_sheet_name(d_val)
        if s_name not in tasks_by_sheet:
            tasks_by_sheet[s_name] = []
        tasks_by_sheet[s_name].append((d_val, t))

    seq = 0
    for s_name, sheet_tasks in tasks_by_sheet.items():
        ws = get_or_create_sheet(wb, s_name)
        affected_sheets.add(s_name)
        sheet_saved = 0

        for d_val, t in sheet_tasks:
            seq += 1
            ts = (now_dt + datetime.timedelta(seconds=seq)).strftime("%y%m%d-%H%M%S")
            rec_id = t.get("id") or f"WU-{ts}"
            p_val = t.get("project") or default_proj
            title_val = t.get("title") or "Task"
            desc_val = t.get("desc") or ""
            hours_val = str(t.get("hours") or "").strip()
            if hours_val:
                _, formatted_h = parse_duration_to_hours(hours_val)
                hours_val = formatted_h or hours_val
            st_val = t.get("status") or "Completed"
            rem_val = t.get("remarks") or ""
            in_val = t.get("login") or ""
            out_val = t.get("logout") or ""
            lunch_val = t.get("lunch") or ""
            tea_val = t.get("tea") or ""
            logged_at = t.get("logged_at") or (now_dt + datetime.timedelta(seconds=seq)).strftime("%Y-%m-%d %H:%M:%S")

            ws.append([
                rec_id, d_val, p_val, title_val, desc_val, hours_val, st_val, rem_val,
                in_val, out_val, lunch_val, tea_val, logged_at
            ])
            sheet_saved += 1
            total_saved += 1

            if in_val or out_val or lunch_val or tea_val:
                save_daily_timings(d_val, {
                    "login": in_val,
                    "logout": out_val,
                    "lunch": lunch_val,
                    "tea": tea_val,
                    "lunch_taken": bool(lunch_val),
                    "tea_taken": bool(tea_val)
                })

        counts_per_sheet[s_name] = sheet_saved

    for s_name in affected_sheets:
        ws = wb[s_name]
        sheet_work_dates = {d for d, t in tasks_by_sheet.get(s_name, []) if t.get("status") not in ("Weekly Off", "Holiday")}
        if sheet_work_dates:
            rows_to_delete = []
            for r_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
                r_date = format_date_only(row[1].value)
                r_status = str(row[6].value or "").strip().lower()
                r_proj = str(row[2].value or "").strip().lower()
                val_h = str(row[5].value or "").strip()
                is_zero = (not val_h or val_h in ("0", "0.0", "-") or val_h.startswith("0.0"))
                if r_date in sheet_work_dates and ("weekly off" in r_status or "weekly off" in r_proj) and is_zero:
                    rows_to_delete.append(r_idx)
            for r_idx in reversed(rows_to_delete):
                ws.delete_rows(r_idx)
        sort_sheet_records_by_date(ws)
        restyle_all_rows_in_sheet(ws)


    try:
        wb.save(FILE)
        trigger_google_sheet_auto_sync(list(counts_per_sheet.keys()))
        return total_saved, counts_per_sheet
    except PermissionError:
        messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
        return 0, {}
    except Exception as e:
        messagebox.showerror("Save Error", f"An error occurred while saving: {e}")
        return 0, {}

def delete_work_update(record_id, sheet_name):
    """Delete a record by ID from a specific month sheet or any sheet."""
    try:
        wb = load_workbook(FILE)
    except PermissionError:
        messagebox.showerror("Permission Error", f"'{FILE}' is open in Excel. Please close it first.")
        return False

    deleted = False
    sheets_to_check = [sheet_name] if sheet_name in wb.sheetnames else wb.sheetnames
    deleted_from_sheet = sheet_name
    for s_name in sheets_to_check:
        ws = wb[s_name]
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
            if row[0].value == record_id:
                ws.delete_rows(row_idx)
                sort_sheet_records_by_date(ws)
                deleted = True
                deleted_from_sheet = s_name
                break
        if deleted:
            break

    if deleted:
        try:
            wb.save(FILE)
            trigger_google_sheet_auto_sync(deleted_from_sheet)
        except Exception:
            pass
    return deleted

def load_month_records(sheet_name):
    """Load records for a specific month sheet, sorted chronologically by date."""
    if not os.path.exists(FILE):
        return []
    try:
        wb = load_workbook(FILE, data_only=True)
        if sheet_name not in wb.sheetnames:
            return []
        ws = wb[sheet_name]
        records = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(row):
                records.append(list(row))
        
        settings = load_settings()
        asc = (settings.get("date_sort_order", "asc") == "asc")

        def sort_key(r):
            raw_d = str(r[1] or "").strip()
            norm_d = format_date_only(raw_d)
            try:
                dt = datetime.datetime.strptime(norm_d, "%Y-%m-%d").date()
            except Exception:
                dt = datetime.date(2099, 12, 31)
            
            st = str(r[6] or "").lower() if len(r) > 6 else ""
            pj = str(r[2] or "").lower() if len(r) > 2 else ""
            prio = 0 if "holiday" in st or "holiday" in pj else (1 if "weekly off" in st or "weekly off" in pj or "weekend" in st else (2 if "leave" in st or "leave" in pj else 3))
            t_val = parse_time_to_minutes(str(r[8] or "")) if len(r) > 8 else 9999
            if t_val is None:
                t_val = 9999
            d_val = dt if asc else -dt.toordinal()
            return (d_val, prio, t_val, str(r[0] or ""))

        records.sort(key=sort_key)
        return records
    except Exception as e:
        print("Load records error:", e)
        return []

def get_available_months():
    """Get list of all month sheets in the Excel workbook."""
    if not os.path.exists(FILE):
        return [datetime.datetime.now().strftime("%B %Y")]
    try:
        wb = load_workbook(FILE, read_only=True)
        sheets = [s for s in wb.sheetnames if s != "Records"]
        if not sheets:
            sheets = [datetime.datetime.now().strftime("%B %Y")]
        return sheets
    except Exception:
        return [datetime.datetime.now().strftime("%B %Y")]

def get_distinct_projects():
    """Retrieve distinct project names for autocomplete."""
    projects = set()
    if not os.path.exists(FILE):
        return ["Afro Cargo & Logistics", "Web Development", "Bug Fixes", "API Integration", "Database Design"]
    try:
        wb = load_workbook(FILE, data_only=True)
        for s_name in wb.sheetnames:
            ws = wb[s_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and len(row) > 2 and row[2]:
                    projects.add(str(row[2]).strip())
    except Exception:
        pass
    default_list = ["Afro Cargo & Logistics", "Web Development", "Bug Fixes", "API Integration", "Database Design"]
    return sorted(list(projects.union(default_list)))

# ---------- Team Summary Formatter & Webhook Sender ----------
def generate_team_markdown(date_str, project, tasks_list, user_name="Developer", timings=None):
    """Generate clean, professional Markdown formatted log for team sharing with shift & break timings."""
    norm_date = format_date_only(date_str)
    try:
        dt = datetime.datetime.strptime(norm_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%d-%b-%Y")
    except Exception:
        formatted_date = norm_date or datetime.datetime.now().strftime("%d-%b-%Y")

    # If timings not supplied, check daily timings or tasks
    if timings is None:
        timings = get_daily_timings(norm_date)
        if not timings.get("login") and not timings.get("logout"):
            for t in tasks_list:
                if t.get("login") or t.get("logout"):
                    timings["login"] = t.get("login", "")
                    timings["logout"] = t.get("logout", "")
                    timings["lunch"] = t.get("lunch", "")
                    timings["tea"] = t.get("tea", "")
                    timings["lunch_taken"] = bool(t.get("lunch"))
                    timings["tea_taken"] = bool(t.get("tea"))
                    break

    # Collect distinct projects in tasks_list
    projects_in_tasks = set()
    for t in tasks_list:
        p = str(t.get("project") or "").strip()
        if p:
            projects_in_tasks.add(p)

    total_hrs = 0.0
    has_any_hrs = False
    for t in tasks_list:
        h = str(t.get("hours", "") or "").strip()
        if h:
            try:
                val = float(h)
                if val > 0:
                    total_hrs += val
                    has_any_hrs = True
            except ValueError:
                pass

    md = []
    md.append(f"#### Today's Work Log - {formatted_date}")
    md.append(f"**Member:** {user_name}")
    
    if len(projects_in_tasks) == 1:
        md.append(f"**Project:** {list(projects_in_tasks)[0]}")
    elif len(projects_in_tasks) > 1:
        md.append(f"**Projects:** {', '.join(sorted(projects_in_tasks))}")
    elif project:
        md.append(f"**Project:** {project}")

    # Timings formatting
    net_h = 0.0
    net_str = ""
    if timings:
        login_val = str(timings.get("login") or "").strip()
        logout_val = str(timings.get("logout") or "").strip()
        lunch_val = str(timings.get("lunch") or "").strip()
        tea_val = str(timings.get("tea") or "").strip()
        lunch_taken = bool(timings.get("lunch_taken", bool(lunch_val)))
        tea_taken = bool(timings.get("tea_taken", bool(tea_val)))

        if login_val and logout_val:
            md.append(f"**Login Time:** {login_val} | **Logout Time:** {logout_val}")
            net_h, net_str, span_h, _, _ = calculate_net_working_hours(login_val, logout_val, lunch_val, tea_val, lunch_taken, tea_taken)
        elif login_val:
            md.append(f"**Login Time:** {login_val}")
        elif logout_val:
            md.append(f"**Logout Time:** {logout_val}")

        # Total hours / net working hours: Prioritize shift calculation (Login - Logout minus breaks)
        if net_h > 0:
            md.append(f"**Total Hours:** {format_duration_display(net_h)}")
        elif has_any_hrs and total_hrs > 0:
            md.append(f"**Total Hours:** {format_duration_display(total_hrs)}")

        if lunch_taken and lunch_val and lunch_val.lower() not in ('none', 'no', 'not taken', 'n/a', '-'):
            md.append(f"**Lunch Break:** {lunch_val}")

        if tea_taken and tea_val and tea_val.lower() not in ('none', 'no', 'not taken', 'n/a', '-'):
            md.append(f"**Tea Break:** {tea_val}")
    else:
        if has_any_hrs and total_hrs > 0:
            md.append(f"**Total Hours:** {format_duration_display(total_hrs)}")

    # Distinct dates summary for monthly view
    distinct_dates = set()
    daily_h = defaultdict(float)
    daily_off = set()
    for t in tasks_list:
        d_val = t.get("date")
        if d_val:
            distinct_dates.add(d_val)
            h_str = str(t.get("hours", "") or "").replace(" hrs", "").strip()
            try:
                h_f = float(h_str)
            except Exception:
                h_f = 0.0
            daily_h[d_val] += h_f
            st_l = str(t.get("status") or "").lower()
            pj_l = str(t.get("project") or "").lower()
            if "weekly off" in st_l or "weekly off" in pj_l or "holiday" in st_l or "holiday" in pj_l:
                daily_off.add(d_val)

    if len(distinct_dates) > 1:
        gte_8_cnt = sum(1 for d, h in daily_h.items() if h >= 8.0)
        lt_8_cnt = sum(1 for d, h in daily_h.items() if (0 < h < 8.0 and d not in daily_off))
        md.append(f"**Monthly Working Days:** **≥ 8 Hours:** {gte_8_cnt} days | **< 8 Hours:** {lt_8_cnt} days")

    md.append("\n---\n")

    # Group by status
    completed = [t for t in tasks_list if t.get("status") == "Completed"]
    in_progress = [t for t in tasks_list if t.get("status") == "In Progress"]
    leaves = [t for t in tasks_list if t.get("status") == "Leave" or t.get("project") == "Leave"]
    holidays = [t for t in tasks_list if t.get("status") == "Holiday" or t.get("project") == "Holiday"]
    weekly_offs = [t for t in tasks_list if t.get("status") == "Weekly Off" or t.get("project") == "Weekly Off"]
    others = [t for t in tasks_list if t.get("status") not in ("Completed", "In Progress", "Holiday", "Weekly Off", "Leave") and t.get("project") not in ("Holiday", "Weekly Off", "Leave")]

    def format_task_hours(t_hours):
        hrs_val = str(t_hours or "").strip()
        if len(tasks_list) == 1 and net_h > 0:
            return format_human_time(net_h)
        if hrs_val:
            try:
                val = float(hrs_val)
                return format_human_time(val)
            except ValueError:
                dec_val, formatted_s = parse_duration_to_hours(hrs_val)
                return formatted_s or hrs_val
        return ""

    idx = 1
    if completed:
        md.append("### Completed Tasks\n")
        for t in completed:
            title = str(t.get("title") or "Task").strip()
            desc = str(t.get("desc") or "").strip()
            remarks = str(t.get("remarks") or "").strip()
            hrs = format_task_hours(t.get("hours"))
            hrs_suffix = f" ({hrs})" if hrs and hrs not in ("0", "0.0", "0 hrs") else ""
            t_proj = str(t.get("project") or "").strip()
            proj_badge = f" - *[{t_proj}]*" if (len(projects_in_tasks) > 1 and t_proj) else ""

            md.append(f"{idx}. **`{title}`**{hrs_suffix}{proj_badge}:")
            if desc:
                for dline in desc.split("\n"):
                    dline = dline.strip()
                    if dline:
                        md.append(f"   - {dline}")
            if remarks:
                md.append(f"   - Docs / Note: `{remarks}`")
            md.append("")
            idx += 1

    if in_progress:
        md.append("### In Progress Tasks\n")
        for t in in_progress:
            title = str(t.get("title") or "Task").strip()
            desc = str(t.get("desc") or "").strip()
            remarks = str(t.get("remarks") or "").strip()
            hrs = format_task_hours(t.get("hours"))
            hrs_suffix = f" ({hrs})" if hrs and hrs not in ("0", "0.0", "0 hrs") else ""
            t_proj = str(t.get("project") or "").strip()
            proj_badge = f" - *[{t_proj}]*" if (len(projects_in_tasks) > 1 and t_proj) else ""

            md.append(f"{idx}. **`{title}`**{hrs_suffix}{proj_badge} [In Progress]:")
            if desc:
                for dline in desc.split("\n"):
                    dline = dline.strip()
                    if dline:
                        md.append(f"   - {dline}")
            if remarks:
                md.append(f"   - Note: `{remarks}`")
            md.append("")
            idx += 1

    if leaves:
        md.append("### 🌴 On Leave\n")
        for t in leaves:
            l_desc = f" - {t.get('desc')}" if t.get('desc') else ""
            md.append(f"- **{t.get('title')}** ({formatted_date}){l_desc}")
        md.append("")

    if holidays:
        md.append("### 🎉 Official Holidays\n")
        for t in holidays:
            md.append(f"- **{t.get('title')}** ({formatted_date}) - {t.get('desc') or 'Official Holiday'}")
        md.append("")

    if weekly_offs:
        md.append("### 🏖️ Weekly Off\n")
        for t in weekly_offs:
            md.append(f"- **{t.get('title')}** ({formatted_date})")
        md.append("")

    if others:
        md.append("### Other Updates / Pending\n")
        for t in others:
            title = str(t.get("title") or "Task").strip()
            desc = str(t.get("desc") or "").strip()
            st = str(t.get("status") or "Pending").strip()
            remarks = str(t.get("remarks") or "").strip()
            hrs = format_task_hours(t.get("hours"))
            hrs_suffix = f" ({hrs})" if hrs and hrs not in ("0", "0.0", "0 hrs") else ""
            t_proj = str(t.get("project") or "").strip()
            proj_badge = f" - *[{t_proj}]*" if (len(projects_in_tasks) > 1 and t_proj) else ""

            md.append(f"{idx}. **{title}**{hrs_suffix}{proj_badge} [{st}]:")
            if desc:
                for dline in desc.split("\n"):
                    if dline.strip():
                        md.append(f"   - {dline.strip()}")
            if remarks:
                md.append(f"   - Note: `{remarks}`")
            md.append("")
            idx += 1

    return "\n".join(md).strip()

def send_webhook_message(webhook_url, text_content, webhook_type="Slack / Discord"):
    """Send formatted text to Slack, Discord, Microsoft Teams, or custom webhook."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "Invalid Webhook URL. Please configure in Settings."

    try:
        # Prepare payload
        if "discord.com" in webhook_url.lower():
            payload = {"content": text_content[:1990]}
        elif "teams.microsoft.com" in webhook_url.lower() or "office.com" in webhook_url.lower():
            payload = {"text": text_content.replace("\n", "\n\n")}
        else:
            payload = {"text": text_content}

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TodayWorkUpdateManager/2.0"
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            if status_code in (200, 204):
                return True, "Successfully delivered to team channel!"
            else:
                return True, f"Delivered with HTTP status {status_code}"
    except Exception as e:
        return False, f"Failed to send webhook: {e}"

# ---------- Custom Data API / Webhook Integration ----------
def serialize_record_row(row, sheet_name=""):
    """Convert an Excel row (list/tuple) into a clean, serializable dictionary."""
    def _val(idx):
        if idx < len(row) and row[idx] is not None:
            v = str(row[idx]).strip()
            return "" if v == "-" else v
        return ""

    return {
        "id": _val(0),
        "date": _val(1),
        "sheet": sheet_name,
        "project": _val(2),
        "task_title": _val(3),
        "description": _val(4),
        "hours": _val(5),
        "status": _val(6),
        "remarks": _val(7),
        "login_time": _val(8),
        "logout_time": _val(9),
        "lunch_break": _val(10),
        "tea_break": _val(11),
        "logged_at": _val(12)
    }

def get_all_records_across_all_sheets():
    """Reads all records from all month sheets in FILE and returns list of dicts."""
    records = []
    if not os.path.exists(FILE):
        return records
    try:
        wb = load_workbook(FILE, data_only=True)
        for s_name in wb.sheetnames:
            if s_name == "Records":
                continue
            ws = wb[s_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(row):
                    records.append(serialize_record_row(list(row), sheet_name=s_name))
    except Exception as e:
        print("Error getting all records:", e)
    return records

def get_records_for_month(sheet_name):
    """Reads all records from a specific month sheet in FILE and returns list of dicts."""
    records = []
    if not os.path.exists(FILE):
        return records
    try:
        wb = load_workbook(FILE, data_only=True)
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(row):
                    records.append(serialize_record_row(list(row), sheet_name=sheet_name))
    except Exception as e:
        print(f"Error getting records for {sheet_name}:", e)
    return records

def send_data_api_webhook(payload, api_url=None, auth_token=None, timeout=15):
    """
    Send structured JSON payload to custom Data API / Webhook endpoint.
    Returns (success: bool, response_text: str, status_code: int).
    """
    settings = load_settings()
    url = (api_url or settings.get("data_api_url", "")).strip()
    if not url:
        return False, "Data API URL is not configured. Please set it in Settings.", 0
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "Invalid API URL (must start with http:// or https://)", 0

    token = (auth_token if auth_token is not None else settings.get("data_api_token", "")).strip()

    try:
        data_bytes = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "TodayWorkUpdateManager/2.0",
            "Accept": "application/json, text/plain, */*"
        }
        if token:
            if ":" in token and not token.lower().startswith("http"):
                hk, hv = token.split(":", 1)
                headers[hk.strip()] = hv.strip()
            else:
                headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            snippet = body.strip()
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            if 200 <= code < 300:
                return True, f"HTTP {code}: {snippet or 'Success'}", code
            else:
                return False, f"Server responded with status {code}: {snippet}", code

    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace").strip()
            if len(err_body) > 200:
                err_body = err_body[:197] + "..."
        except Exception:
            pass
        msg = f"HTTP Error {e.code}: {e.reason}"
        if err_body:
            msg += f" - {err_body}"
        return False, msg, e.code
    except urllib.error.URLError as e:
        return False, f"Connection Error: {e.reason}", 0
    except Exception as e:
        return False, f"Request Error: {str(e)}", 0

# ---------- Google Sheets Sync Integration ----------

def get_google_apps_script_code():
    """Reads or returns the ready-to-deploy Google Apps Script code for Google Sheets sync."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_apps_script.js")
    if os.path.exists(script_path):
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                return f.read()
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
    if (data.action === "ping") {
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Connected to Google Sheet: '" + ss.getName() + "'",
        sheetTitle: ss.getName(),
        sheets: ss.getSheets().map(function(s) { return s.getName(); })
      })).setMimeType(ContentService.MimeType.JSON);
    }
    if (data.action === "sync_month" || data.action === "sync_sheet") {
      var sName = data.sheet_name || "Work Logs";
      var s = ss.getSheetByName(sName) || ss.insertSheet(sName);
      var hd = data.headers || [];
      var rows = data.rows || [];
      s.clearContents();
      if (hd.length) {
        s.getRange(1, 1, 1, hd.length).setValues([hd]).setBackground("#1F4E79").setFontColor("#FFFFFF").setFontWeight("bold");
      }
      if (rows.length) {
        s.getRange(2, 1, rows.length, hd.length).setValues(rows);
      }
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Synced " + rows.length + " rows to tab '" + sName + "'",
        updatedRows: rows.length,
        sheetTitle: ss.getName()
      })).setMimeType(ContentService.MimeType.JSON);
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
  return ContentService.createTextOutput(JSON.stringify({ status: "online", sheetTitle: ss.getName() })).setMimeType(ContentService.MimeType.JSON);
}"""

def get_raw_sheet_rows(sheet_name):
    """
    Reads all formatted data rows from a specific month sheet in FILE.
    Returns (headers: list, rows: list of lists).
    """
    if not os.path.exists(FILE):
        return HEADERS, []
    try:
        wb = load_workbook(FILE, data_only=True)
        if sheet_name not in wb.sheetnames:
            return HEADERS, []
        ws = wb[sheet_name]
        headers = [str(cell.value or "") for cell in ws[1]] if ws.max_row >= 1 else HEADERS
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(row):
                cleaned = []
                for val in row:
                    if val is None:
                        cleaned.append("")
                    elif isinstance(val, (datetime.date, datetime.datetime)):
                        cleaned.append(val.strftime("%Y-%m-%d"))
                    else:
                        cleaned.append(str(val))
                rows.append(cleaned)
        return headers, rows
    except Exception as e:
        print(f"Error reading rows for sheet {sheet_name}: {e}")
        return HEADERS, []

def get_all_raw_sheets():
    """
    Reads all month sheets in FILE.
    Returns (headers: list, sheets_dict: { sheet_name: [rows] }).
    """
    result = {}
    if not os.path.exists(FILE):
        return HEADERS, result
    try:
        wb = load_workbook(FILE, data_only=True)
        headers = HEADERS
        for s_name in wb.sheetnames:
            if s_name == "Records":
                continue
            ws = wb[s_name]
            if ws.max_row >= 1:
                headers = [str(cell.value or "") for cell in ws[1]]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(row):
                    cleaned = []
                    for val in row:
                        if val is None:
                            cleaned.append("")
                        elif isinstance(val, (datetime.date, datetime.datetime)):
                            cleaned.append(val.strftime("%Y-%m-%d"))
                        else:
                            cleaned.append(str(val))
                    rows.append(cleaned)
            result[s_name] = rows
        return headers, result
    except Exception as e:
        print(f"Error reading all sheets: {e}")
        return HEADERS, {}

def send_google_sheet_payload(url, payload, timeout=35):
    """
    Sends structured JSON payload to Google Apps Script Web App.
    Handles Google's 302 redirects seamlessly via requests or urllib.
    Returns (success: bool, response_dict_or_text, status_code: int).
    """
    url = (url or "").strip()
    if not url:
        return False, "Google Sheet Web App URL is not configured. Please paste your Web App URL.", 0
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "Invalid Web App URL. Must start with https://script.google.com/macros/s/...", 0

    try:
        import requests
        resp = requests.post(url, json=payload, timeout=timeout)
        try:
            data = resp.json()
            if isinstance(data, dict):
                if data.get("status") == "success" or data.get("status") == "online":
                    return True, data, resp.status_code
                else:
                    return False, data.get("message", "Unknown error from Google Sheet"), resp.status_code
            return True, {"response": data}, resp.status_code
        except Exception:
            if 200 <= resp.status_code < 300:
                return True, {"message": resp.text.strip()}, resp.status_code
            return False, f"Server HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code
    except ImportError:
        try:
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "WorkPulse/1.0 (Google Sheets Client)"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(body)
                    if data.get("status") == "success" or data.get("status") == "online":
                        return True, data, resp.getcode()
                    return False, data.get("message", body), resp.getcode()
                except Exception:
                    return True, {"message": body}, resp.getcode()
        except urllib.error.HTTPError as e:
            return False, f"HTTP Error {e.code}: {e.reason}", e.code
        except Exception as e:
            return False, f"Connection Error: {str(e)}", 0
    except Exception as e:
        return False, f"Request Error: {str(e)}", 0

def ping_google_sheet(webapp_url=None, timeout=15):
    """Pings the Google Sheet Web App to verify connection and fetch sheet title."""
    settings = load_settings()
    url = (webapp_url or settings.get("gsheet_webapp_url", "")).strip()
    payload = {"action": "ping", "client": "WorkPulse", "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    return send_google_sheet_payload(url, payload, timeout=timeout)

def sync_google_sheet_month(month_name=None, webapp_url=None, timeout=35):
    """Synchronizes all rows of a single month tab to Google Sheet."""
    settings = load_settings()
    url = (webapp_url or settings.get("gsheet_webapp_url", "")).strip()
    if not month_name:
        month_name = datetime.datetime.now().strftime("%B %Y")
    headers, rows = get_raw_sheet_rows(month_name)
    payload = {
        "action": "sync_month",
        "sheet_name": month_name,
        "headers": headers,
        "rows": rows,
        "user_name": settings.get("user_name", "Developer"),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    ok, data, code = send_google_sheet_payload(url, payload, timeout=timeout)
    if ok:
        settings["gsheet_last_sync"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_settings(settings)
    return ok, data, code

def sync_google_sheet_all(webapp_url=None, timeout=50):
    """Synchronizes all month tabs across the entire workbook to Google Sheet."""
    settings = load_settings()
    url = (webapp_url or settings.get("gsheet_webapp_url", "")).strip()
    headers, all_sheets = get_all_raw_sheets()
    payload = {
        "action": "sync_all",
        "headers": headers,
        "sheets": all_sheets,
        "user_name": settings.get("user_name", "Developer"),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    ok, data, code = send_google_sheet_payload(url, payload, timeout=timeout)
    if ok:
        settings["gsheet_last_sync"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_settings(settings)
    return ok, data, code

# ==============================================================================
# ---------- Google Sheets Auto-Sync Engine & Background Worker ----------
# ==============================================================================

class GoogleSheetSyncWorker:
    """
    Thread-safe, queued, debounced background synchronization engine for Google Sheets.
    Guarantees:
    - Never freezes or blocks the UI thread.
    - Queues and batches rapid changes (multi-task adds, edits, deletes, leaves).
    - Prevents overlapping concurrent requests to Google Apps Script.
    - Accurately notifies status bar when WorkPulse app window is running.
    """
    _lock = threading.Lock()
    _dirty_sheets = set()
    _is_running = False
    _app_ref = None

    @classmethod
    def set_app_ref(cls, app_instance):
        cls._app_ref = app_instance

    @classmethod
    def queue_sync(cls, sheet_names=None, app_ref=None):
        """
        Enqueues sheet(s) for background auto-sync to Google Sheets.
        `sheet_names` can be None (current month), a single sheet name str, or an iterable of sheet names.
        """
        if app_ref:
            cls._app_ref = app_ref

        settings = load_settings()
        url = (settings.get("gsheet_webapp_url") or "").strip()
        auto_sync = settings.get("gsheet_auto_sync", bool(url))

        if not auto_sync or not url:
            return

        with cls._lock:
            if not sheet_names:
                cls._dirty_sheets.add(datetime.datetime.now().strftime("%B %Y"))
            elif isinstance(sheet_names, str):
                cls._dirty_sheets.add(sheet_names.strip())
            else:
                for s in sheet_names:
                    if s:
                        cls._dirty_sheets.add(str(s).strip())

            if not cls._is_running:
                cls._is_running = True
                threading.Thread(target=cls._worker_loop, daemon=True).start()

    @classmethod
    def _worker_loop(cls):
        while True:
            target_sheet = None
            with cls._lock:
                if not cls._dirty_sheets:
                    cls._is_running = False
                    break
                target_sheet = cls._dirty_sheets.pop()

            if not target_sheet:
                continue

            cls._notify_ui(f"🔄 Auto-syncing '{target_sheet}' to Google Sheet...", color="#0284c7")

            try:
                ok, data, code = sync_google_sheet_month(target_sheet)
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                if ok:
                    cls._notify_ui(f"✅ Auto-synced to Google Sheet ('{target_sheet}') at {now_str}", color="#16a34a")
                else:
                    err_msg = data.get("message") if isinstance(data, dict) else str(data)
                    cls._notify_ui(f"⚠️ Google Sheet sync error: {str(err_msg)[:65]}", color="#dc2626")
            except Exception as e:
                cls._notify_ui(f"⚠️ Google Sheet sync error: {str(e)[:65]}", color="#dc2626")

    @classmethod
    def _notify_ui(cls, msg, color=None):
        if cls._app_ref:
            try:
                if hasattr(cls._app_ref, 'root') and cls._app_ref.root:
                    cls._app_ref.root.after(0, lambda: cls._safe_status_update(msg, color))
            except Exception:
                pass

    @classmethod
    def _safe_status_update(cls, msg, color=None):
        try:
            if cls._app_ref and hasattr(cls._app_ref, 'status') and cls._app_ref.status.winfo_exists():
                cfg = {"text": msg}
                if color:
                    cfg["fg"] = color
                cls._app_ref.status.config(**cfg)
        except Exception:
            pass

def trigger_google_sheet_auto_sync(sheet_names=None, app_ref=None):
    """
    Public function called across WorkPulse whenever any record, task, leave,
    weekend off, or file import modifies Excel data.
    """
    GoogleSheetSyncWorker.queue_sync(sheet_names, app_ref=app_ref)


# ---------- Markdown / Text Bulk Log Parser ----------
def extract_task_hours_and_title(raw_title):
    """Extract hours if specified in task title (e.g., '(2.5h)', '[1.5 hrs]', '(2 hours)', '- 2h') and return clean title."""
    m = re.search(r'[\(\[]\s*([\d.]+)\s*(?:h|hr|hrs|hour|hours)\s*[\)\]]', raw_title, re.IGNORECASE)
    if not m:
        m = re.search(r'[-–—]\s*([\d.]+)\s*(?:h|hr|hrs|hours?)\s*$', raw_title, re.IGNORECASE)
    
    if m:
        try:
            val = float(m.group(1))
            val_str = f"{val:.2f}".rstrip('0').rstrip('.') if '.' in f"{val:.2f}" else f"{val}"
            if '.' not in val_str:
                val_str += ".0"
            cleaned_title = raw_title[:m.start()] + raw_title[m.end():]
            cleaned_title = re.sub(r'[:\s\-–—]+$', '', cleaned_title).strip()
            cleaned_title = re.sub(r'^\*\*|\*\*$', '', cleaned_title).strip()
            cleaned_title = re.sub(r'^`|`$', '', cleaned_title).strip()
            return val_str, cleaned_title
        except ValueError:
            pass
    return "", raw_title.strip()

def parse_bulk_markdown(raw_text):
    """Parses raw text / markdown work log and extracts Date, Project, Total Hours, Shift Timings, and Task items."""
    date_match = re.search(r'(\d{1,2})[-/ ]([A-Za-z]+|\d{1,2})[-/ ](\d{4})', raw_text)
    found_date = datetime.datetime.now().strftime("%Y-%m-%d")
    if date_match:
        d_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d", "%m-%d-%Y"):
            try:
                found_date = datetime.datetime.strptime(d_str, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass

    proj_match = re.search(r'\*\*Project:\*\*\s*(.+)', raw_text, re.IGNORECASE)
    if not proj_match:
        proj_match = re.search(r'Project:\s*(.+)', raw_text, re.IGNORECASE)
    project_name = proj_match.group(1).strip() if proj_match else "General Work"
    project_name = re.sub(r'[*_`]', '', project_name).strip()

    # Detect Total Hours if mentioned in the header
    tot_match = re.search(r'(?:\*\*Total\s+Hours?\*\*|Total\s+Hours?|Total\s+Time|Total\s+Spent)\s*[:=\-]?\s*([\d.]+)', raw_text, re.IGNORECASE)
    detected_total_hours = ""
    if tot_match:
        try:
            val = float(tot_match.group(1))
            detected_total_hours = f"{val:.2f}".rstrip('0').rstrip('.') if '.' in f"{val:.2f}" else f"{val}"
            if '.' not in detected_total_hours:
                detected_total_hours += ".0"
        except ValueError:
            pass

    # Detect Shift & Break Timings
    detected_login = ""
    detected_logout = ""
    detected_lunch = ""
    detected_tea = ""

    m_in = re.search(r'\bLogin(?:\s+Time)?(?:\*\*|:|\s)*[:=\-]?\s*([0-9]{1,2}:[0-9]{2}(?:\s*[AaPp][Mm])?)', raw_text, re.IGNORECASE)
    if m_in:
        detected_login = m_in.group(1).strip()

    m_out = re.search(r'\bLogout(?:\s+Time)?(?:\*\*|:|\s)*[:=\-]?\s*([0-9]{1,2}:[0-9]{2}(?:\s*[AaPp][Mm])?)', raw_text, re.IGNORECASE)
    if m_out:
        detected_logout = m_out.group(1).strip()

    if not detected_login or not detected_logout:
        m_shift = re.search(r'\bShift(?:\s+Timing)?(?:\*\*|:|\s)*[:=\-]?\s*([0-9]{1,2}:[0-9]{2}(?:\s*[AaPp][Mm])?)\s*(?:-|–|to)\s*([0-9]{1,2}:[0-9]{2}(?:\s*[AaPp][Mm])?)', raw_text, re.IGNORECASE)
        if m_shift:
            if not detected_login:
                detected_login = m_shift.group(1).strip()
            if not detected_logout:
                detected_logout = m_shift.group(2).strip()

    m_lunch = re.search(r'\bLunch(?:\s+Break)?(?:\*\*|:|\s)*[:=\-]?\s*([^\n\r|]+)', raw_text, re.IGNORECASE)
    if m_lunch:
        lunch_val = re.sub(r'[*_`]', '', m_lunch.group(1)).strip()
        if lunch_val.lower() not in ('none', 'no', 'not taken', 'n/a', '-'):
            detected_lunch = lunch_val

    m_tea = re.search(r'\bTea(?:\s+Break)?(?:\*\*|:|\s)*[:=\-]?\s*([^\n\r|]+)', raw_text, re.IGNORECASE)
    if m_tea:
        tea_val = re.sub(r'[*_`]', '', m_tea.group(1)).strip()
        if tea_val.lower() not in ('none', 'no', 'not taken', 'n/a', '-'):
            detected_tea = tea_val

    # If Total Hours wasn't explicitly provided, but Login and Logout are present, auto-calculate net hours
    if not detected_total_hours and detected_login and detected_logout:
        net_h, net_str, span_h, _, _ = calculate_net_working_hours(
            detected_login, detected_logout, detected_lunch, detected_tea,
            lunch_taken=bool(detected_lunch), tea_taken=bool(detected_tea)
        )
        if net_h > 0:
            detected_total_hours = net_str

    detected_timings = {
        "login": detected_login,
        "logout": detected_logout,
        "lunch": detected_lunch,
        "tea": detected_tea,
        "lunch_taken": bool(detected_lunch),
        "tea_taken": bool(detected_tea)
    }

    lines = raw_text.split('\n')
    tasks = []
    current_task = None
    current_status = "Completed"

    for line in lines:
        sline = line.strip()
        if not sline:
            continue
        
        if sline.startswith('#'):
            lower_h = sline.lower()
            if 'progress' in lower_h:
                current_status = "In Progress"
            elif 'pending' in lower_h or 'todo' in lower_h:
                current_status = "Pending"
            elif 'review' in lower_h:
                current_status = "Under Review"
            elif 'blocked' in lower_h:
                current_status = "Blocked"
            elif 'completed' in lower_h or 'done' in lower_h:
                current_status = "Completed"
            continue

        # Skip header metadata lines so they don't get treated as task descriptions
        lower_line = sline.lower()
        if (sline.startswith('---') or
            sline.startswith('**Project') or sline.startswith('Project:') or
            sline.startswith('**Member') or sline.startswith('Member:') or
            sline.startswith('**Total Hours') or sline.startswith('Total Hours:') or
            'login time' in lower_line or 'logout time' in lower_line or
            'lunch break' in lower_line or 'tea break' in lower_line or
            lower_line.startswith('shift:')):
            continue

        num_match = re.match(r'^(\d+)\.\s*(.+)', sline)
        bullet_match = re.match(r'^[-*•]\s+\*\*(.+?)\*\*[:\s]*(.*)', sline)

        if num_match:
            if current_task:
                current_task["desc"] = "\n".join(current_task["desc"])
                tasks.append(current_task)
            full_title = num_match.group(2).strip()
            cleaned_title = re.sub(r'^\*\*|\*\*$', '', full_title).strip()
            cleaned_title = re.sub(r'^`|`$', '', cleaned_title).strip()
            cleaned_title = re.sub(r':$', '', cleaned_title).strip()
            cleaned_title = re.sub(r'^\*\*|\*\*$', '', cleaned_title).strip()
            
            task_hrs, cleaned_title = extract_task_hours_and_title(cleaned_title)

            current_task = {
                "title": cleaned_title,
                "desc": [],
                "status": current_status,
                "hours": task_hrs,
                "remarks": "",
                "login": detected_login,
                "logout": detected_logout,
                "lunch": detected_lunch,
                "tea": detected_tea
            }
            continue
        elif bullet_match and not current_task:
            b_title = bullet_match.group(1).strip()
            b_rest = bullet_match.group(2).strip()
            task_hrs, cleaned_b_title = extract_task_hours_and_title(b_title)

            current_task = {
                "title": cleaned_b_title,
                "desc": [b_rest] if b_rest else [],
                "status": current_status,
                "hours": task_hrs,
                "remarks": "",
                "login": detected_login,
                "logout": detected_logout,
                "lunch": detected_lunch,
                "tea": detected_tea
            }
            continue

        if current_task:
            if sline.startswith('- ') or sline.startswith('* ') or sline.startswith('• ') or sline.startswith('  -'):
                sub_text = re.sub(r'^[-*•\s]+', '', sline).strip()
                if sub_text.lower().startswith('docs:') or sub_text.lower().startswith('doc:'):
                    current_task["remarks"] = sub_text
                else:
                    current_task["desc"].append(sub_text)
            else:
                current_task["desc"].append(sline)

    if current_task:
        current_task["desc"] = "\n".join(current_task["desc"])
        tasks.append(current_task)

    # If Total Hours was given in header and tasks don't have explicit hours, auto-split total hours evenly
    if detected_total_hours and tasks:
        try:
            total_float = float(detected_total_hours)
            tasks_without_hours = [t for t in tasks if not t.get("hours")]
            explicit_hours_sum = sum([float(t["hours"]) for t in tasks if t.get("hours") and str(t["hours"]).replace('.', '', 1).isdigit()])
            
            if tasks_without_hours:
                rem_hours = max(0.0, total_float - explicit_hours_sum)
                split_val = round(rem_hours / len(tasks_without_hours), 2)
                split_str = f"{split_val:.2f}".rstrip('0').rstrip('.') if '.' in f"{split_val:.2f}" else f"{split_val}"
                if '.' not in split_str:
                    split_str += ".0"
                for t in tasks_without_hours:
                    t["hours"] = split_str
            elif not any(t.get("hours") for t in tasks):
                split_val = round(total_float / len(tasks), 2)
                split_str = f"{split_val:.2f}".rstrip('0').rstrip('.') if '.' in f"{split_val:.2f}" else f"{split_val}"
                if '.' not in split_str:
                    split_str += ".0"
                for t in tasks:
                    t["hours"] = split_str
        except Exception:
            pass

    return found_date, project_name, tasks, detected_total_hours, detected_timings

# ---------- Share with Team Modal Dialog ----------
class ShareTeamDialog(tk.Toplevel):
    def __init__(self, parent, date_str, default_project, tasks_dict, initial_scope="today"):
        super().__init__(parent)
        self.title("📢 Share Work Update with Team")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=920, default_h=660, min_w=760, min_h=520)

        self.date_str = date_str
        self.default_project = default_project
        self.tasks_dict = tasks_dict  # {"today": [...], "month": [...], "selected": [...]}
        self.settings = load_settings()
        self.recent_teammates = self.settings.get("recent_teammates", [])
        
        # Determine initial scope
        if initial_scope == "selected" and self.tasks_dict.get("selected"):
            self.current_scope = "selected"
        elif self.tasks_dict.get("today"):
            self.current_scope = "today"
        else:
            self.current_scope = "month"

        self.create_widgets()
        self.update_scope_content()

    def create_widgets(self):
        # Header banner
        header = tk.Frame(self, bg="#1e293b", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(header, text="📢 Share Work Update with Team", font=("Segoe UI", 12, "bold"), fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=15, pady=12)

        # Date and Month info on right
        today_cnt = len(self.tasks_dict.get("today", []))
        month_cnt = len(self.tasks_dict.get("month", []))
        tk.Label(header, text=f"Today's Tasks: {today_cnt} | Month Total: {month_cnt}", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b").pack(side=tk.RIGHT, padx=15, pady=12)

        main_frame = tk.Frame(self, bg="#f8fafc", padx=15, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. MS Teams Direct Launch Card
        teams_card = tk.LabelFrame(main_frame, text=" 🎯 Microsoft Teams - Direct Share (No Webhook Required!) ", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        teams_card.pack(fill=tk.X, pady=(0, 10))

        # Main Teams Share Button
        btn_teams_share = tk.Button(teams_card, text="🚀 Open Microsoft Teams (Select User / Channel to Share)", font=("Segoe UI", 10, "bold"), bg="#5046e5", fg="white", activebackground="#4338ca", activeforeground="white", relief="flat", padx=14, pady=6, cursor="hand2", command=self.open_teams_share_dialog)
        btn_teams_share.pack(side=tk.LEFT, padx=(0, 12))

        # Optional Direct Teammate chat input
        tk.Label(teams_card, text="Or Direct User:", font=("Segoe UI", 9), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_teammate = ttk.Combobox(teams_card, values=self.recent_teammates, font=("Segoe UI", 9), width=22)
        self.combo_teammate.pack(side=tk.LEFT, padx=(0, 6))
        if self.recent_teammates:
            self.combo_teammate.set(self.recent_teammates[0])

        btn_direct_chat = tk.Button(teams_card, text="💬 Open Direct Chat", font=("Segoe UI", 9, "bold"), bg="#e0e7ff", fg="#3730a3", relief="flat", padx=10, pady=4, cursor="hand2", command=self.open_teams_direct_chat)
        btn_direct_chat.pack(side=tk.LEFT)

        # 2. Scope Selector Bar & Other Quick Actions
        control_bar = tk.Frame(main_frame, bg="#f8fafc")
        control_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(control_bar, text="Showing Tasks:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b").pack(side=tk.LEFT, padx=(0, 4))
        
        scope_options = []
        scope_options.append(f"📅 Today's Tasks ({today_cnt} tasks)")
        scope_options.append(f"📁 All Tasks in Selected Month ({month_cnt} tasks)")
        if self.tasks_dict.get("selected"):
            scope_options.append(f"☑️ Selected Rows ({len(self.tasks_dict['selected'])} tasks)")

        self.combo_scope = ttk.Combobox(control_bar, values=scope_options, state="readonly", font=("Segoe UI", 9, "bold"), width=32)
        self.combo_scope.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_scope.current(0)
        self.combo_scope.bind("<<ComboboxSelected>>", lambda e: self.on_scope_changed())

        btn_copy = tk.Button(control_bar, text="📋 Copy Markdown", font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.copy_to_clipboard)
        btn_copy.pack(side=tk.LEFT, padx=(0, 6))

        btn_wa = tk.Button(control_bar, text="📱 WhatsApp", font=("Segoe UI", 9), bg="#dcfce7", fg="#166534", relief="flat", padx=8, pady=4, cursor="hand2", command=self.open_whatsapp)
        btn_wa.pack(side=tk.LEFT, padx=(0, 6))

        btn_email = tk.Button(control_bar, text="✉️ Email", font=("Segoe UI", 9), bg="#e2e8f0", fg="#334155", relief="flat", padx=8, pady=4, cursor="hand2", command=self.open_email)
        btn_email.pack(side=tk.LEFT, padx=(0, 6))

        btn_slack = tk.Button(control_bar, text="💬 Slack", font=("Segoe UI", 9), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=8, pady=4, cursor="hand2", command=self.open_slack_web)
        btn_slack.pack(side=tk.LEFT)

        # Optional Webhook button (only if configured)
        if self.settings.get("webhook_url"):
            btn_webhook = tk.Button(control_bar, text="⚡ Webhook", font=("Segoe UI", 8), bg="#f1f5f9", fg="#64748b", relief="flat", padx=6, pady=4, cursor="hand2", command=self.send_to_webhook)
            btn_webhook.pack(side=tk.RIGHT)

        # 3. Shift & Break Timings Card (Editable for the shared message)
        timing_card = tk.LabelFrame(main_frame, text=" ⏰ Shift & Break Timings for this Update (Optional) ", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        timing_card.pack(fill=tk.X, pady=(0, 8))

        # Initial timings from date or tasks
        self.active_timings = get_daily_timings(self.date_str)
        for t in self.tasks_dict.get("today", []):
            if t.get("login") or t.get("logout"):
                if t.get("login"):
                    self.active_timings["login"] = t.get("login")
                if t.get("logout"):
                    self.active_timings["logout"] = t.get("logout")
                if t.get("lunch"):
                    self.active_timings["lunch"] = t.get("lunch")
                if t.get("tea"):
                    self.active_timings["tea"] = t.get("tea")
                break

        # Row 1: Login & Logout
        r1 = tk.Frame(timing_card, bg="#ffffff")
        r1.pack(fill=tk.X, pady=2)

        tk.Label(r1, text="Login Time:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_share_login = tk.Entry(r1, font=("Segoe UI", 9), width=11, relief="solid", bd=1)
        self.entry_share_login.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_share_login.insert(0, self.active_timings.get("login", ""))
        self.entry_share_login.bind("<KeyRelease>", lambda e: self.on_timing_changed())

        btn_share_now_in = tk.Button(r1, text="Now", font=("Segoe UI", 8), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=5, pady=1, cursor="hand2", command=lambda: self.set_share_time(self.entry_share_login, format_current_time_str()))
        btn_share_now_in.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(r1, text="Logout Time:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_share_logout = tk.Entry(r1, font=("Segoe UI", 9), width=11, relief="solid", bd=1)
        self.entry_share_logout.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_share_logout.insert(0, self.active_timings.get("logout", ""))
        self.entry_share_logout.bind("<KeyRelease>", lambda e: self.on_timing_changed())

        btn_share_now_out = tk.Button(r1, text="Now", font=("Segoe UI", 8), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=5, pady=1, cursor="hand2", command=lambda: self.set_share_time(self.entry_share_logout, format_current_time_str()))
        btn_share_now_out.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_share_net = tk.Label(r1, text="", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0369a1")
        self.lbl_share_net.pack(side=tk.LEFT)

        # Row 2: Lunch & Tea Breaks (Optional / If taken)
        r2 = tk.Frame(timing_card, bg="#ffffff")
        r2.pack(fill=tk.X, pady=2)

        self.var_share_lunch = tk.BooleanVar(value=bool(self.active_timings.get("lunch_taken", bool(self.active_timings.get("lunch")))))
        self.chk_share_lunch = tk.Checkbutton(r2, text="Lunch Break:", variable=self.var_share_lunch, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", command=self.on_timing_changed)
        self.chk_share_lunch.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_share_lunch = tk.Entry(r2, font=("Segoe UI", 9), width=24, relief="solid", bd=1)
        self.entry_share_lunch.pack(side=tk.LEFT, padx=(0, 18), ipady=1)
        self.entry_share_lunch.insert(0, self.active_timings.get("lunch", "01:00 PM - 02:00 PM"))
        self.entry_share_lunch.bind("<KeyRelease>", lambda e: self.on_timing_changed())

        self.var_share_tea = tk.BooleanVar(value=bool(self.active_timings.get("tea_taken", bool(self.active_timings.get("tea")))))
        self.chk_share_tea = tk.Checkbutton(r2, text="Tea Break:", variable=self.var_share_tea, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155", command=self.on_timing_changed)
        self.chk_share_tea.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_share_tea = tk.Entry(r2, font=("Segoe UI", 9), width=24, relief="solid", bd=1)
        self.entry_share_tea.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        self.entry_share_tea.insert(0, self.active_timings.get("tea", "04:30 PM - 04:45 PM"))
        self.entry_share_tea.bind("<KeyRelease>", lambda e: self.on_timing_changed())

        # Text Area with formatted content
        self.lbl_preview_title = tk.Label(main_frame, text="Formatted Team Work Log (Ready to send/copy):", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#1e293b")
        self.lbl_preview_title.pack(anchor="w", pady=(0, 4))

        self.text_preview = tk.Text(main_frame, font=("Consolas", 10), relief="solid", bd=1, wrap=tk.WORD)
        self.text_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Status indicator
        bottom_bar = tk.Frame(self, bg="#f1f5f9", padx=15, pady=8)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(bottom_bar, text="📋 All today's work update copied to clipboard! Click 'Open Microsoft Teams' to share.", font=("Segoe UI", 9, "bold"), fg="#2563eb", bg="#f1f5f9")
        self.lbl_status.pack(side=tk.LEFT)

        btn_close = tk.Button(bottom_bar, text="Done", font=("Segoe UI", 9), bg="#e2e8f0", fg="#334155", relief="flat", padx=15, pady=4, cursor="hand2", command=self.destroy)
        btn_close.pack(side=tk.RIGHT)

    def set_share_time(self, entry_widget, val):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, val)
        self.on_timing_changed()

    def on_timing_changed(self):
        # Update entry states based on checkboxes
        if hasattr(self, 'entry_share_lunch'):
            if self.var_share_lunch.get():
                self.entry_share_lunch.config(state=tk.NORMAL)
            else:
                self.entry_share_lunch.config(state=tk.DISABLED)
        if hasattr(self, 'entry_share_tea'):
            if self.var_share_tea.get():
                self.entry_share_tea.config(state=tk.NORMAL)
            else:
                self.entry_share_tea.config(state=tk.DISABLED)
        self.update_scope_content()

    def on_scope_changed(self):
        sel_idx = self.combo_scope.current()
        if sel_idx == 0:
            self.current_scope = "today"
        elif sel_idx == 1:
            self.current_scope = "month"
        else:
            self.current_scope = "selected"
        self.update_scope_content()

    def update_scope_content(self):
        current_tasks = self.tasks_dict.get(self.current_scope, [])
        if not current_tasks and self.current_scope != "today":
            current_tasks = self.tasks_dict.get("today", [])
        if not current_tasks:
            current_tasks = self.tasks_dict.get("month", [])

        user_name = self.settings.get("user_name", "Developer")

        # Gather timings from share dialog entries
        login_v = self.entry_share_login.get().strip() if hasattr(self, 'entry_share_login') else self.active_timings.get("login", "")
        logout_v = self.entry_share_logout.get().strip() if hasattr(self, 'entry_share_logout') else self.active_timings.get("logout", "")
        lunch_v = self.entry_share_lunch.get().strip() if (hasattr(self, 'entry_share_lunch') and self.var_share_lunch.get()) else ""
        tea_v = self.entry_share_tea.get().strip() if (hasattr(self, 'entry_share_tea') and self.var_share_tea.get()) else ""

        timings_obj = {
            "login": login_v,
            "logout": logout_v,
            "lunch": lunch_v,
            "tea": tea_v,
            "lunch_taken": bool(lunch_v),
            "tea_taken": bool(tea_v)
        }

        # Update net badge
        if hasattr(self, 'lbl_share_net'):
            net_h, net_str, span_h, _, _ = calculate_net_working_hours(
                login_v, logout_v, lunch_v, tea_v,
                lunch_taken=bool(lunch_v), tea_taken=bool(tea_v)
            )
            if net_h > 0:
                span_text = format_human_time(span_h)
                net_text = format_human_time(net_h)
                self.lbl_share_net.config(text=f"⏱️ Span: {span_text} | Net Working: {net_text} ({net_str} hrs)")
            else:
                self.lbl_share_net.config(text="")

        # Save to daily timings cache
        save_daily_timings(self.date_str, timings_obj)

        formatted_md = generate_team_markdown(self.date_str, self.default_project, current_tasks, user_name, timings=timings_obj)

        self.text_preview.delete("1.0", tk.END)
        self.text_preview.insert("1.0", formatted_md)

        # Auto copy current scope markdown to clipboard
        self.clipboard_clear()
        self.clipboard_append(formatted_md)

        count = len(current_tasks)
        scope_name = "Today's Work" if self.current_scope == "today" else ("Selected Month" if self.current_scope == "month" else "Selected Rows")
        self.lbl_status.config(text=f"📋 Showing {scope_name} ({count} tasks). Copied to clipboard! Ready to share.", fg="#2563eb")

    def copy_to_clipboard(self):
        text = self.text_preview.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.lbl_status.config(text="📋 Copied formatted update to clipboard! You can paste in Teams / Slack / WhatsApp.", fg="#2563eb")
        messagebox.showinfo("Copied", "Work update copied to clipboard!")

    def open_teams_share_dialog(self):
        """Directly opens Microsoft Teams Share Dialog where user can pick any teammate, chat, or channel."""
        text = self.text_preview.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(text)

        msg_enc = urllib.parse.quote(text)
        teams_share_url = f"https://teams.microsoft.com/share?msgText={msg_enc}"
        
        try:
            webbrowser.open(teams_share_url)
        except Exception:
            webbrowser.open("https://teams.microsoft.com")

        self.lbl_status.config(
            text="🚀 Opened Microsoft Teams Share Dialog! Select the user or channel to send.", 
            fg="#16a34a"
        )

    def open_teams_direct_chat(self):
        """Opens Microsoft Teams directly into a specific user's chat."""
        target_user = self.combo_teammate.get().strip()
        text = self.text_preview.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(text)

        if not target_user:
            self.open_teams_share_dialog()
            return

        # Save to recent teammates list
        if target_user not in self.recent_teammates:
            self.recent_teammates.insert(0, target_user)
            self.recent_teammates = self.recent_teammates[:10]
            self.settings["recent_teammates"] = self.recent_teammates
            save_settings(self.settings)
            self.combo_teammate['values'] = self.recent_teammates

        msg_enc = urllib.parse.quote(text)
        teams_url = f"https://teams.microsoft.com/l/chat/0/0?users={urllib.parse.quote(target_user)}&message={msg_enc}"
        
        try:
            webbrowser.open(teams_url)
        except Exception:
            webbrowser.open(f"https://teams.microsoft.com/l/chat/0/0?message={msg_enc}")

        self.lbl_status.config(
            text=f"🚀 Opened Microsoft Teams chat with {target_user}!", 
            fg="#16a34a"
        )

    def open_slack_web(self):
        text = self.text_preview.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        try:
            webbrowser.open("https://app.slack.com/client")
        except Exception:
            pass
        self.lbl_status.config(text="✅ Copied to clipboard & opened Slack.", fg="#16a34a")

    def open_email(self):
        text = self.text_preview.get("1.0", tk.END).strip()
        subject = urllib.parse.quote(f"Work Update - {self.default_project} - {self.date_str}")
        body = urllib.parse.quote(text)
        webbrowser.open(f"mailto:?subject={subject}&body={body}")
        self.lbl_status.config(text="✉️ Opened default Email client.", fg="#16a34a")

    def open_whatsapp(self):
        text = self.text_preview.get("1.0", tk.END).strip()
        msg_enc = urllib.parse.quote(text)
        webbrowser.open(f"https://web.whatsapp.com/send?text={msg_enc}")
        self.lbl_status.config(text="📱 Opened WhatsApp Web with message pre-filled.", fg="#16a34a")

    def send_to_webhook(self):
        webhook_url = self.settings.get("webhook_url", "").strip()
        if not webhook_url:
            messagebox.showinfo("Webhook Optional", "No webhook configured in Settings. You don't need a webhook - you can directly click 'Open Microsoft Teams' to share!")
            return

        text = self.text_preview.get("1.0", tk.END).strip()
        wh_type = self.settings.get("webhook_type", "Slack / Discord")
        self.lbl_status.config(text="⏳ Sending to team channel...", fg="#2563eb")
        self.update()

        success, msg = send_webhook_message(webhook_url, text, wh_type)
        if success:
            self.lbl_status.config(text=f"✅ {msg}", fg="#16a34a")
            messagebox.showinfo("Sent to Team", f"🎉 {msg}")
        else:
            self.lbl_status.config(text=f"❌ {msg}", fg="#dc2626")
            messagebox.showerror("Send Error", msg)

# ---------- Settings Dialog ----------
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app_ref=None):
        super().__init__(parent)
        self.parent = parent
        self.app_ref = app_ref
        self.title("⚙️ Work Logger Settings & Shift Configuration")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=680, default_h=580, min_w=620, min_h=500)

        self.settings = load_settings()
        self.holidays_list = list(self.settings.get("holidays", []))
        self.create_widgets()

    def create_widgets(self):
        header = tk.Frame(self, bg="#1e293b", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(header, text="⚙️ Work Logger & Shift Configuration", font=("Segoe UI", 12, "bold"), fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=15, pady=12)

        # Tab Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 6))

        # Tab 1: General & Shift Settings
        tab_general = tk.Frame(self.notebook, bg="#ffffff", padx=15, pady=12)
        self.notebook.add(tab_general, text="  ⚙️ General & Shifts  ")
        self.build_general_tab(tab_general)

        # Tab 2: Weekly Off & Holidays
        tab_holidays = tk.Frame(self.notebook, bg="#ffffff", padx=15, pady=12)
        self.notebook.add(tab_holidays, text="  🏖️ Weekly Off & Holidays  ")
        self.build_holidays_tab(tab_holidays)

        # Tab 3: Data API & Webhook Integration
        tab_api = tk.Frame(self.notebook, bg="#ffffff", padx=15, pady=12)
        self.notebook.add(tab_api, text="  🌐 Data API / Webhook  ")
        self.build_data_api_tab(tab_api)

        # Tab 4: Google Sheet Integration
        tab_gsheet = tk.Frame(self.notebook, bg="#ffffff", padx=15, pady=12)
        self.notebook.add(tab_gsheet, text="  📊 Google Sheet  ")
        self.build_gsheet_tab(tab_gsheet)

        # Bottom Bar
        bottom = tk.Frame(self, bg="#f1f5f9", padx=15, pady=10)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        btn_save = tk.Button(bottom, text="💾 Save All Settings", font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white", relief="flat", padx=16, pady=6, cursor="hand2", command=self.save)
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(bottom, text="Cancel", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=12, pady=6, cursor="hand2", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=4)

    def build_general_tab(self, parent):
        form_frame = tk.Frame(parent, bg="#ffffff")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Your Name
        tk.Label(form_frame, text="Your Name / Handle:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=5)
        self.entry_name = tk.Entry(form_frame, font=("Segoe UI", 9), width=35, relief="solid", bd=1)
        self.entry_name.grid(row=0, column=1, sticky="w", pady=5, padx=(10, 0))
        self.entry_name.insert(0, self.settings.get("user_name", "Developer"))

        # Default Shift Section
        tk.Label(form_frame, text="Default Shift & Breaks:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e40af").grid(row=1, column=0, sticky="w", pady=(8, 4))
        
        shift_box = tk.Frame(form_frame, bg="#f8fafc", padx=8, pady=6, bd=1, relief="solid")
        shift_box.grid(row=1, column=1, sticky="w", pady=(8, 4), padx=(10, 0))

        # Row A: Login & Logout
        s_r1 = tk.Frame(shift_box, bg="#f8fafc")
        s_r1.pack(fill=tk.X, pady=2)
        tk.Label(s_r1, text="Login:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 2))
        self.entry_def_login = tk.Entry(s_r1, font=("Segoe UI", 8), width=10, relief="solid", bd=1)
        self.entry_def_login.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        self.entry_def_login.insert(0, self.settings.get("default_login_time", "10:00 AM"))

        tk.Label(s_r1, text="Logout:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 2))
        self.entry_def_logout = tk.Entry(s_r1, font=("Segoe UI", 8), width=10, relief="solid", bd=1)
        self.entry_def_logout.pack(side=tk.LEFT, ipady=1)
        self.entry_def_logout.insert(0, self.settings.get("default_logout_time", "07:30 PM"))

        # Row B: Lunch & Tea
        s_r2 = tk.Frame(shift_box, bg="#f8fafc")
        s_r2.pack(fill=tk.X, pady=2)
        tk.Label(s_r2, text="Lunch:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 2))
        self.entry_def_lunch = tk.Entry(s_r2, font=("Segoe UI", 8), width=18, relief="solid", bd=1)
        self.entry_def_lunch.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        self.entry_def_lunch.insert(0, self.settings.get("default_lunch_break", "01:00 PM - 02:00 PM"))

        tk.Label(s_r2, text="Tea:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 2))
        self.entry_def_tea = tk.Entry(s_r2, font=("Segoe UI", 8), width=18, relief="solid", bd=1)
        self.entry_def_tea.pack(side=tk.LEFT, ipady=1)
        self.entry_def_tea.insert(0, self.settings.get("default_tea_break", "04:30 PM - 04:45 PM"))

        # Webhook Type
        tk.Label(form_frame, text="Platform:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=2, column=0, sticky="w", pady=5)
        self.combo_type = ttk.Combobox(form_frame, values=["Microsoft Teams", "Slack / Discord", "Custom HTTP Webhook"], state="readonly", width=33, font=("Segoe UI", 9))
        self.combo_type.grid(row=2, column=1, sticky="w", pady=5, padx=(10, 0))
        self.combo_type.set(self.settings.get("webhook_type", "Microsoft Teams"))

        # Webhook URL
        tk.Label(form_frame, text="Incoming Webhook URL:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=3, column=0, sticky="w", pady=5)
        self.entry_wh = tk.Entry(form_frame, font=("Segoe UI", 9), width=35, relief="solid", bd=1)
        self.entry_wh.grid(row=3, column=1, sticky="w", pady=5, padx=(10, 0))
        self.entry_wh.insert(0, self.settings.get("webhook_url", ""))

        # Checkboxes
        self.var_prompt_share = tk.BooleanVar(value=self.settings.get("prompt_team_share_on_save", True))
        chk_prompt = tk.Checkbutton(form_frame, text="Open Team Share dialog automatically on Save / Bulk Upload", variable=self.var_prompt_share, bg="#ffffff", font=("Segoe UI", 9))
        chk_prompt.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 2))

        self.var_auto_copy = tk.BooleanVar(value=self.settings.get("auto_copy_on_save", True))
        chk_copy = tk.Checkbutton(form_frame, text="Auto-copy Markdown summary to Clipboard on Save", variable=self.var_auto_copy, bg="#ffffff", font=("Segoe UI", 9))
        chk_copy.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        # Test Webhook Button
        btn_test = tk.Button(form_frame, text="🧪 Send Test Webhook Message", font=("Segoe UI", 8, "bold"), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=10, pady=3, cursor="hand2", command=self.test_webhook)
        btn_test.grid(row=6, column=0, columnspan=2, sticky="w", pady=6)

    def build_holidays_tab(self, parent):
        # Header info
        top_bar = tk.Frame(parent, bg="#ffffff")
        top_bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(top_bar, text="Manage company weekly offs, public holidays & monthly sheet auto-arranging.", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)
        btn_open_full = tk.Button(top_bar, text="🏖️ Open Advanced Weekend & Holiday Dialog", font=("Segoe UI", 8, "bold"), bg="#0284c7", fg="white", activebackground="#0369a1", activeforeground="white", relief="flat", padx=8, pady=3, cursor="hand2", command=self.open_full_holiday_dialog)
        btn_open_full.pack(side=tk.RIGHT)

        # 1. Weekly Off Section
        off_frame = tk.LabelFrame(parent, text="  1. Weekly Off Days (Weekends)  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        off_frame.pack(fill=tk.X, pady=(0, 8))

        days_box = tk.Frame(off_frame, bg="#ffffff")
        days_box.pack(fill=tk.X)

        configured_offs = set(self.settings.get("weekly_offs", ["Sunday"]))
        self.off_vars = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for d in day_names:
            var = tk.BooleanVar(value=(d in configured_offs))
            self.off_vars[d] = var
            chk = tk.Checkbutton(days_box, text=d, variable=var, bg="#ffffff", font=("Segoe UI", 9))
            chk.pack(side=tk.LEFT, padx=(0, 10))

        self.var_sec_fourth = tk.BooleanVar(value=bool(self.settings.get("second_fourth_saturday", False)))
        chk_sat = tk.Checkbutton(off_frame, text="Include 2nd & 4th Saturday of each month as Weekly Off", variable=self.var_sec_fourth, bg="#ffffff", font=("Segoe UI", 8, "bold"), fg="#334155")
        chk_sat.pack(anchor="w", pady=(4, 0))

        # 2. Company / Official Holidays
        hol_frame = tk.LabelFrame(parent, text="  2. Company & National Holidays  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        hol_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # Add holiday bar
        add_bar = tk.Frame(hol_frame, bg="#ffffff")
        add_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(add_bar, text="Date (YYYY-MM-DD):", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_hol_date = tk.Entry(add_bar, font=("Segoe UI", 9), width=12, relief="solid", bd=1)
        self.entry_hol_date.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_hol_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))

        btn_hol_today = tk.Button(add_bar, text="Today", font=("Segoe UI", 7, "bold"), bg="#edf2f7", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: [self.entry_hol_date.delete(0, tk.END), self.entry_hol_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))])
        btn_hol_today.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(add_bar, text="Holiday Name / Occasion:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_hol_name = tk.Entry(add_bar, font=("Segoe UI", 9), width=18, relief="solid", bd=1)
        self.entry_hol_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=1)

        btn_add_hol = tk.Button(add_bar, text="➕ Add", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="white", relief="flat", padx=8, pady=2, cursor="hand2", command=self.add_holiday)
        btn_add_hol.pack(side=tk.LEFT, padx=(0, 4))

        btn_load_std = tk.Button(add_bar, text="🇮🇳 Load Indian Holidays", font=("Segoe UI", 8), bg="#fef3c7", fg="#92400e", relief="flat", padx=6, pady=2, cursor="hand2", command=self.load_indian_holidays)
        btn_load_std.pack(side=tk.LEFT)

        # Holidays Table
        tree_box = tk.Frame(hol_frame, bg="#ffffff", bd=1, relief="solid")
        tree_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.hol_tree = ttk.Treeview(tree_box, columns=("Date", "Day", "Name"), show="headings", height=5)
        self.hol_tree.heading("Date", text="Date (YYYY-MM-DD)")
        self.hol_tree.column("Date", width=120, anchor="center")

        self.hol_tree.heading("Day", text="Day of Week")
        self.hol_tree.column("Day", width=110, anchor="center")

        self.hol_tree.heading("Name", text="Holiday Name / Occasion")
        self.hol_tree.column("Name", width=260, anchor="w")

        h_scroll = ttk.Scrollbar(tree_box, orient="vertical", command=self.hol_tree.yview)
        self.hol_tree.configure(yscrollcommand=h_scroll.set)
        self.hol_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh_holidays_tree()

        # Action bar under table
        hol_actions = tk.Frame(hol_frame, bg="#ffffff")
        hol_actions.pack(fill=tk.X)

        btn_del_hol = tk.Button(hol_actions, text="🗑️ Remove Selected Holiday", font=("Segoe UI", 8), bg="#fee2e2", fg="#991b1b", relief="flat", padx=8, pady=2, cursor="hand2", command=self.remove_selected_holiday)
        btn_del_hol.pack(side=tk.LEFT)

        btn_sync = tk.Button(hol_actions, text="📅 Sync Holidays & Weekly Offs to Current Sheet", font=("Segoe UI", 8, "bold"), bg="#ede9fe", fg="#6d28d9", relief="flat", padx=10, pady=2, cursor="hand2", command=self.sync_sheet_now)
        btn_sync.pack(side=tk.RIGHT)

    def open_full_holiday_dialog(self):
        WeekendHolidayDialog(self, on_sync_callback=lambda: [self.refresh_from_settings(), getattr(self.parent, 'refresh_all', lambda: None)()])

    def refresh_from_settings(self):
        self.settings = load_settings()
        self.holidays_list = list(self.settings.get("holidays", STANDARD_HOLIDAYS_2026))
        self.refresh_holidays_tree()
        conf_offs = set(self.settings.get("weekly_offs", ["Sunday"]))
        for d, var in self.off_vars.items():
            var.set(d in conf_offs)
        if hasattr(self, "var_sec_fourth"):
            self.var_sec_fourth.set(bool(self.settings.get("second_fourth_saturday", False)))

    def load_indian_holidays(self):
        if messagebox.askyesno("Load Holidays", "Load 2026 standard Indian holidays into the list?"):
            existing = {h.get("date") for h in self.holidays_list}
            for sh in STANDARD_HOLIDAYS_2026:
                if sh["date"] not in existing:
                    self.holidays_list.append(sh.copy())
            self.refresh_holidays_tree()

    def refresh_holidays_tree(self):
        for r in self.hol_tree.get_children():
            self.hol_tree.delete(r)

        for h in sorted(self.holidays_list, key=lambda x: x.get("date", "")):
            d = h.get("date", "")
            try:
                day_name = datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%A")
            except Exception:
                day_name = "-"
            self.hol_tree.insert("", tk.END, values=(d, day_name, h.get("name", "")))

    def add_holiday(self):
        d_val = format_date_only(self.entry_hol_date.get().strip())
        name_val = self.entry_hol_name.get().strip()

        if not d_val:
            messagebox.showwarning("Validation Error", "Please provide a valid date in format YYYY-MM-DD.")
            return

        try:
            datetime.datetime.strptime(d_val, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Date must be YYYY-MM-DD (e.g. 2026-10-02).")
            return

        if not name_val:
            messagebox.showwarning("Validation Error", "Please enter a Holiday Name (e.g. Gandhi Jayanti).")
            return

        for h in self.holidays_list:
            if h.get("date") == d_val:
                h["name"] = name_val
                self.refresh_holidays_tree()
                self.entry_hol_name.delete(0, tk.END)
                messagebox.showinfo("Updated", f"Updated holiday for {d_val}.")
                return

        self.holidays_list.append({"date": d_val, "name": name_val})
        self.refresh_holidays_tree()
        self.entry_hol_name.delete(0, tk.END)

    def remove_selected_holiday(self):
        sel = self.hol_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a holiday from the list to remove.")
            return

        item = self.hol_tree.item(sel[0])
        date_to_remove = str(item["values"][0])
        self.holidays_list = [h for h in self.holidays_list if h.get("date") != date_to_remove]
        self.refresh_holidays_tree()

    def sync_sheet_now(self):
        target_month = None
        if hasattr(self.parent, 'current_selected_month'):
            target_month = self.parent.current_selected_month.get()

        h_count, o_count, s_name = sync_month_holidays_and_weekly_offs(target_month)
        if hasattr(self.parent, 'refresh_all'):
            self.parent.refresh_all()

        messagebox.showinfo("Sync Complete", f"✅ Sheet '{s_name}' synchronized successfully!\n\n• Added Holidays: {h_count}\n• Added Weekly Offs: {o_count}\n\nAll records have been auto-arranged chronologically.")

    def test_webhook(self):
        wh = self.entry_wh.get().strip()
        if not wh:
            messagebox.showwarning("Empty Webhook", "Please enter a Webhook URL first.")
            return
        success, msg = send_webhook_message(wh, "🧪 Test message from Today Work Update Manager. Connection successful!", self.combo_type.get())
        if success:
            messagebox.showinfo("Webhook Success", msg)
        else:
            messagebox.showerror("Webhook Failed", msg)

    def build_data_api_tab(self, parent):
        top_bar = tk.Frame(parent, bg="#ffffff")
        top_bar.pack(fill=tk.X, pady=(0, 10))
        tk.Label(top_bar, text="Configure your custom REST API / Webhook to receive live task updates on edit/save.", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        form_frame = tk.Frame(parent, bg="#ffffff")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # 1. API Configuration Frame
        cfg_box = tk.LabelFrame(form_frame, text="  1. API / Webhook Endpoint Settings  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        cfg_box.pack(fill=tk.X, pady=(0, 10))

        tk.Label(cfg_box, text="API / Webhook URL*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_data_api_url = tk.Entry(cfg_box, font=("Segoe UI", 9), width=42, relief="solid", bd=1)
        self.entry_data_api_url.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.entry_data_api_url.insert(0, self.settings.get("data_api_url", ""))

        tk.Label(cfg_box, text="Bearer Token / API Key:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_data_api_token = tk.Entry(cfg_box, font=("Segoe UI", 9), width=42, relief="solid", bd=1)
        self.entry_data_api_token.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.entry_data_api_token.insert(0, self.settings.get("data_api_token", ""))

        hint_lbl = tk.Label(cfg_box, text="💡 Tip: Token can be raw Bearer token, or custom header like 'X-API-Key: my_secret_token'.", font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#ffffff")
        hint_lbl.grid(row=2, column=1, sticky="w", pady=(2, 6), padx=(8, 0))

        # Test button row
        btn_box = tk.Frame(cfg_box, bg="#ffffff")
        btn_box.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=4)

        btn_test = tk.Button(btn_box, text="🧪 Send Test Ping to API", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=10, pady=3, cursor="hand2", command=self.test_data_api)
        btn_test.pack(side=tk.LEFT, padx=(0, 6))

        btn_sync = tk.Button(btn_box, text="🔄 Open Sync Manager...", font=("Segoe UI", 8, "bold"), bg="#f0fdf4", fg="#16a34a", relief="flat", padx=10, pady=3, cursor="hand2", command=self.open_sync_manager)
        btn_sync.pack(side=tk.LEFT)

        # 2. Automation Triggers Frame
        trig_box = tk.LabelFrame(form_frame, text="  2. Automatic Real-Time Webhook Triggers  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        trig_box.pack(fill=tk.X, pady=(0, 10))

        self.var_api_sync_on_edit = tk.BooleanVar(value=bool(self.settings.get("data_api_sync_on_edit", True)))
        chk_edit = tk.Checkbutton(trig_box, text="⚡ Send payload to API whenever a task is Edited or Updated (Primary)", variable=self.var_api_sync_on_edit, font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff")
        chk_edit.pack(anchor="w", pady=2)

        self.var_api_sync_on_create = tk.BooleanVar(value=bool(self.settings.get("data_api_sync_on_create", True)))
        chk_create = tk.Checkbutton(trig_box, text="➕ Send payload to API whenever a new task is Created / Saved", variable=self.var_api_sync_on_create, font=("Segoe UI", 9), fg="#334155", bg="#ffffff")
        chk_create.pack(anchor="w", pady=2)

        self.var_api_sync_on_delete = tk.BooleanVar(value=bool(self.settings.get("data_api_sync_on_delete", True)))
        chk_del = tk.Checkbutton(trig_box, text="🗑️ Send payload to API whenever a task is Deleted", variable=self.var_api_sync_on_delete, font=("Segoe UI", 9), fg="#334155", bg="#ffffff")
        chk_del.pack(anchor="w", pady=2)

        # 3. Payload Format Documentation Frame
        doc_box = tk.LabelFrame(form_frame, text="  3. Webhook JSON Payload Specification  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        doc_box.pack(fill=tk.BOTH, expand=True)

        doc_text = tk.Text(doc_box, font=("Consolas", 8), height=5, bg="#f8fafc", fg="#475569", relief="flat", wrap=tk.NONE)
        doc_text.pack(fill=tk.BOTH, expand=True)
        sample_json = (
            "// On Edit/Update event:\n"
            "{\n"
            '  "event": "update",\n'
            '  "action": "edit",\n'
            '  "timestamp": "2026-10-19 16:30:00",\n'
            '  "user_name": "Developer",\n'
            '  "record": { "id": "WU-...", "date": "...", "project": "...", "task_title": "...", "hours": "...", "status": "..." }\n'
            "}\n\n"
            "// On Sync All Data:\n"
            "{\n"
            '  "event": "sync_all",\n'
            '  "total_records": 34,\n'
            '  "records": [ { ...record 1... }, { ...record 2... } ]\n'
            "}"
        )
        doc_text.insert("1.0", sample_json)
        doc_text.config(state=tk.DISABLED)

    def test_data_api(self):
        url = self.entry_data_api_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter an API / Webhook URL first.")
            return
        token = self.entry_data_api_token.get().strip()
        test_payload = {
            "event": "test_ping",
            "action": "ping",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": self.entry_name.get().strip() or "Developer",
            "message": "Connection test from Today Work Update Manager",
            "client_version": "2.0"
        }
        success, msg, code = send_data_api_webhook(test_payload, api_url=url, auth_token=token)
        if success:
            messagebox.showinfo("API Connection Successful", f"✅ Successfully connected to API!\n\n• Endpoint: {url}\n• HTTP Status: {code}\n• Response: {msg}")
        else:
            messagebox.showerror("API Connection Failed", f"❌ Failed to reach API endpoint:\n\n{msg}\n\nPlease check your URL, server status, or auth token.")

    def open_sync_manager(self):
        SyncApiDialog(self)

    def build_gsheet_tab(self, parent):
        top_bar = tk.Frame(parent, bg="#ffffff")
        top_bar.pack(fill=tk.X, pady=(0, 10))
        tk.Label(top_bar, text="Synchronize work update records with your online Google Sheet via Google Apps Script.", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        form_frame = tk.Frame(parent, bg="#ffffff")
        form_frame.pack(fill=tk.BOTH, expand=True)

        cfg_box = tk.LabelFrame(form_frame, text="  1. Google Sheet Web App Endpoint  ", font=("Segoe UI", 9, "bold"), fg="#0f9d58", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        cfg_box.pack(fill=tk.X, pady=(0, 10))

        tk.Label(cfg_box, text="Web App URL*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_gsheet_url = tk.Entry(cfg_box, font=("Segoe UI", 9), width=44, relief="solid", bd=1)
        self.entry_gsheet_url.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.entry_gsheet_url.insert(0, self.settings.get("gsheet_webapp_url", ""))

        hint_lbl = tk.Label(cfg_box, text="💡 URL format: https://script.google.com/macros/s/.../exec", font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#ffffff")
        hint_lbl.grid(row=1, column=1, sticky="w", pady=(2, 6), padx=(8, 0))

        btn_box = tk.Frame(cfg_box, bg="#ffffff")
        btn_box.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        btn_test = tk.Button(btn_box, text="🧪 Test Connection", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=10, pady=3, cursor="hand2", command=self.test_gsheet_api)
        btn_test.pack(side=tk.LEFT, padx=(0, 6))

        btn_open_mgr = tk.Button(btn_box, text="🔄 Open Google Sheet Sync...", font=("Segoe UI", 8, "bold"), bg="#ecfdf5", fg="#047857", relief="flat", padx=10, pady=3, cursor="hand2", command=self.open_gsheet_manager)
        btn_open_mgr.pack(side=tk.LEFT, padx=(0, 6))

        btn_copy_code = tk.Button(btn_box, text="📋 Copy Apps Script Code", font=("Segoe UI", 8), bg="#f8fafc", fg="#334155", relief="flat", padx=8, pady=3, cursor="hand2", command=self.copy_apps_script_code)
        btn_copy_code.pack(side=tk.LEFT)

        auto_box = tk.LabelFrame(form_frame, text="  2. Automatic Real-Time Synchronization  ", font=("Segoe UI", 9, "bold"), fg="#0f9d58", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        auto_box.pack(fill=tk.X, pady=(0, 10))

        self.var_gsheet_auto_sync = tk.BooleanVar(value=bool(self.settings.get("gsheet_auto_sync", False)))
        chk_auto = tk.Checkbutton(auto_box, text="⚡ Auto-Sync on Save/Edit/Delete (Automatically updates Google Sheet tab in background)", variable=self.var_gsheet_auto_sync, font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff")
        chk_auto.pack(anchor="w", pady=3)

        guide_box = tk.LabelFrame(form_frame, text="  3. Quick Setup Guide (4 Steps - 30 seconds)  ", font=("Segoe UI", 9, "bold"), fg="#334155", bg="#f8fafc", padx=10, pady=6, bd=1, relief="solid")
        guide_box.pack(fill=tk.BOTH, expand=True)

        guide_text = (
            "1. Open your Google Sheet in a web browser.\n"
            "2. Click 'Extensions' menu -> 'Apps Script'.\n"
            "3. Delete existing code, click 'Copy Apps Script Code' above, paste into editor, and click Save (💾).\n"
            "4. Click 'Deploy' -> 'New deployment' -> type: 'Web app' -> Who has access: 'Anyone' -> Deploy!\n"
            "   Copy the generated Web App URL and paste it into the Web App URL field above."
        )
        tk.Label(guide_box, text=guide_text, font=("Segoe UI", 8), bg="#f8fafc", fg="#475569", justify="left").pack(anchor="w", padx=4, pady=2)

    def test_gsheet_api(self):
        url = self.entry_gsheet_url.get().strip()
        if not url:
            messagebox.showwarning("Empty URL", "Please enter your Google Sheet Web App URL first.")
            return
        ok, data, code = ping_google_sheet(webapp_url=url)
        if ok:
            title = data.get("sheetTitle", "Google Sheet") if isinstance(data, dict) else "Google Sheet"
            messagebox.showinfo("Google Sheet Connected", f"✅ Connection Successful!\n\n• Target Spreadsheet: {title}\n• Status: Online\n\nYou can now sync your work logs!")
        else:
            msg = data if isinstance(data, str) else data.get("message", "Unknown error")
            messagebox.showerror("Connection Failed", f"❌ Failed to reach Google Sheet:\n\n{msg}\n\nPlease verify that your deployment is set to 'Who has access: Anyone'.")

    def open_gsheet_manager(self):
        GoogleSheetSyncDialog(self.parent if self.parent else self)

    def copy_apps_script_code(self):
        code = get_google_apps_script_code()
        self.clipboard_clear()
        self.clipboard_append(code)
        self.update()
        messagebox.showinfo("Copied", "📋 Google Apps Script code copied to clipboard!\n\nOpen your Google Sheet -> Extensions -> Apps Script -> Paste -> Deploy as Web app.")

    def save(self):
        selected_offs = [d for d, var in self.off_vars.items() if var.get()]
        sec_fourth = getattr(self, "var_sec_fourth", tk.BooleanVar(value=False)).get()
        self.settings.update({
            "user_name": self.entry_name.get().strip() or "Developer",
            "webhook_type": self.combo_type.get(),
            "webhook_url": self.entry_wh.get().strip(),
            "prompt_team_share_on_save": self.var_prompt_share.get(),
            "auto_copy_on_save": self.var_auto_copy.get(),
            "default_login_time": self.entry_def_login.get().strip(),
            "default_logout_time": self.entry_def_logout.get().strip(),
            "default_lunch_break": self.entry_def_lunch.get().strip(),
            "default_tea_break": self.entry_def_tea.get().strip(),
            "weekly_offs": selected_offs,
            "second_fourth_saturday": sec_fourth,
            "holidays": self.holidays_list,
            "data_api_url": self.entry_data_api_url.get().strip() if hasattr(self, 'entry_data_api_url') else self.settings.get("data_api_url", ""),
            "data_api_token": self.entry_data_api_token.get().strip() if hasattr(self, 'entry_data_api_token') else self.settings.get("data_api_token", ""),
            "data_api_sync_on_edit": self.var_api_sync_on_edit.get() if hasattr(self, 'var_api_sync_on_edit') else True,
            "data_api_sync_on_create": self.var_api_sync_on_create.get() if hasattr(self, 'var_api_sync_on_create') else True,
            "data_api_sync_on_delete": self.var_api_sync_on_delete.get() if hasattr(self, 'var_api_sync_on_delete') else True,
            "gsheet_webapp_url": self.entry_gsheet_url.get().strip() if hasattr(self, 'entry_gsheet_url') else self.settings.get("gsheet_webapp_url", ""),
            "gsheet_auto_sync": self.var_gsheet_auto_sync.get() if hasattr(self, 'var_gsheet_auto_sync') else self.settings.get("gsheet_auto_sync", False)
        })
        save_settings(self.settings)
        if hasattr(self.parent, 'settings') and isinstance(self.parent.settings, dict):
            self.parent.settings.update(self.settings)

        if hasattr(self, 'app_ref') and self.app_ref and hasattr(self.app_ref, 'lan_engine') and self.app_ref.lan_engine:
            self.app_ref.lan_engine.update_profile(self.settings.get("user_name", "Developer"))

        if hasattr(self.parent, 'current_selected_month'):
            s_name = self.parent.current_selected_month.get()
            if s_name and self.settings.get("auto_sync_weekends_holidays", True):
                sync_month_holidays_and_weekly_offs(s_name, clean_re_sync=True, silent=True)

        if hasattr(self.parent, 'refresh_all'):
            self.parent.refresh_all()

        messagebox.showinfo("Saved", "All settings saved successfully!")
        self.destroy()

# ---------- Dedicated Data API / Webhook Sync Modal Dialog ----------
class SyncApiDialog(tk.Toplevel):
    def __init__(self, parent, on_complete_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_complete_callback = on_complete_callback
        self.title("🔄 Sync Data to API / Webhook")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=680, default_h=620, min_w=600, min_h=520)

        self.settings = load_settings()
        self.is_syncing = False
        self.all_records_cache = get_all_records_across_all_sheets()
        self.create_widgets()

    def create_widgets(self):
        # Header banner
        header = tk.Frame(self, bg="#0f766e", height=54)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_title_box = tk.Frame(header, bg="#0f766e")
        h_title_box.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(h_title_box, text="🔄 API & Webhook Data Synchronizer", font=("Segoe UI", 12, "bold"), fg="white", bg="#0f766e").pack(anchor="w")
        tk.Label(h_title_box, text="Push complete Excel work update records directly to your custom API / Webhook URL", font=("Segoe UI", 8), fg="#99f6e4", bg="#0f766e").pack(anchor="w")

        # Main frame
        main_f = tk.Frame(self, bg="#f8fafc", padx=14, pady=10)
        main_f.pack(fill=tk.BOTH, expand=True)

        # 1. Target API Card
        api_card = tk.LabelFrame(main_f, text="  1. Destination API / Webhook Endpoint  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=10, pady=8, bd=1, relief="solid")
        api_card.pack(fill=tk.X, pady=(0, 8))

        url_row = tk.Frame(api_card, bg="#ffffff")
        url_row.pack(fill=tk.X)

        tk.Label(url_row, text="API URL:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 6))
        self.entry_url = tk.Entry(url_row, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=2)
        configured_url = self.settings.get("data_api_url", "").strip()
        if configured_url:
            self.entry_url.insert(0, configured_url)

        btn_settings = tk.Button(url_row, text="⚙️ Settings", font=("Segoe UI", 8), bg="#f1f5f9", fg="#334155", relief="flat", padx=8, pady=2, cursor="hand2", command=self.open_settings)
        btn_settings.pack(side=tk.RIGHT)

        btn_test_ping = tk.Button(url_row, text="🧪 Test Ping", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=8, pady=2, cursor="hand2", command=self.test_ping)
        btn_test_ping.pack(side=tk.RIGHT, padx=4)

        if not configured_url:
            lbl_warn = tk.Label(api_card, text="⚠️ No Data API URL configured yet. Enter one above or click 'Settings' to save permanently.", font=("Segoe UI", 8, "italic"), fg="#d97706", bg="#ffffff")
            lbl_warn.pack(anchor="w", pady=(4, 0))

        # 2. Scope Card
        scope_card = tk.LabelFrame(main_f, text="  2. Select Data Scope to Send  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=10, pady=8, bd=1, relief="solid")
        scope_card.pack(fill=tk.X, pady=(0, 8))

        self.var_scope = tk.StringVar(value="all")

        total_all = len(self.all_records_cache)
        months_available = get_available_months()
        curr_month = self.parent.current_selected_month.get() if hasattr(self.parent, 'current_selected_month') and self.parent.current_selected_month.get() else (months_available[0] if months_available else "")
        month_records = get_records_for_month(curr_month)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in self.all_records_cache if r.get("date") == today_str]

        r_all = tk.Radiobutton(scope_card, text=f"🌐 All Work Logs Across All Months ({total_all} records across {len(months_available)} sheets)", value="all", variable=self.var_scope, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f766e", command=self.on_scope_change)
        r_all.pack(anchor="w", pady=2)

        r_month = tk.Radiobutton(scope_card, text=f"📅 Current Selected Month: '{curr_month}' ({len(month_records)} records)", value="month", variable=self.var_scope, font=("Segoe UI", 9), bg="#ffffff", fg="#334155", command=self.on_scope_change)
        r_month.pack(anchor="w", pady=2)

        r_today = tk.Radiobutton(scope_card, text=f"📝 Today's Tasks Only: {today_str} ({len(today_records)} records)", value="today", variable=self.var_scope, font=("Segoe UI", 9), bg="#ffffff", fg="#334155", command=self.on_scope_change)
        r_today.pack(anchor="w", pady=2)

        # 3. Payload Stats & Preview Card
        prev_card = tk.LabelFrame(main_f, text="  3. JSON Payload Preview & Server Response  ", font=("Segoe UI", 9, "bold"), fg="#0f766e", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        prev_card.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.lbl_stats = tk.Label(prev_card, text=f"Selected: {total_all} records ready to sync.", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e293b")
        self.lbl_stats.pack(anchor="w", pady=(0, 4))

        self.text_preview = tk.Text(prev_card, font=("Consolas", 8), height=8, bg="#f8fafc", fg="#334155", relief="solid", bd=1, wrap=tk.NONE)
        self.text_preview.pack(fill=tk.BOTH, expand=True)

        sb_y = ttk.Scrollbar(self.text_preview, orient="vertical", command=self.text_preview.yview)
        self.text_preview.configure(yscrollcommand=sb_y.set)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Status row
        self.lbl_status = tk.Label(main_f, text="Ready to synchronize.", font=("Segoe UI", 9), fg="#475569", bg="#f8fafc")
        self.lbl_status.pack(anchor="w", pady=(0, 4))

        # Bottom buttons
        bottom = tk.Frame(self, bg="#f1f5f9", padx=14, pady=10)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_sync = tk.Button(bottom, text="🚀 Send All Data to API", font=("Segoe UI", 9, "bold"), bg="#0d9488", fg="white", activebackground="#0f766e", activeforeground="white", relief="flat", padx=16, pady=6, cursor="hand2", command=self.execute_sync)
        self.btn_sync.pack(side=tk.RIGHT, padx=4)

        btn_close = tk.Button(bottom, text="Close", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=12, pady=6, cursor="hand2", command=self.destroy)
        btn_close.pack(side=tk.RIGHT, padx=4)

        self.on_scope_change()

    def get_selected_records(self):
        scope = self.var_scope.get()
        if scope == "all":
            return self.all_records_cache
        elif scope == "month":
            months_available = get_available_months()
            curr_month = self.parent.current_selected_month.get() if hasattr(self.parent, 'current_selected_month') and self.parent.current_selected_month.get() else (months_available[0] if months_available else "")
            return get_records_for_month(curr_month)
        elif scope == "today":
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            return [r for r in self.all_records_cache if r.get("date") == today_str]
        return self.all_records_cache

    def on_scope_change(self):
        records = self.get_selected_records()
        scope = self.var_scope.get()
        self.lbl_stats.config(text=f"Selected: {len(records)} records ({scope.upper()}) ready to sync.")
        self.btn_sync.config(text=f"🚀 Send Data to API ({len(records)} records)")

        # Prepare sample preview
        preview_data = {
            "event": "sync_all" if scope == "all" else f"sync_{scope}",
            "action": "sync",
            "scope": scope,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": self.settings.get("user_name", "Developer"),
            "total_records": len(records),
            "records": records[:3] if len(records) > 3 else records,
            "_note": f"Showing first {min(3, len(records))} of {len(records)} records in preview" if len(records) > 3 else "Complete payload"
        }
        self.text_preview.delete("1.0", tk.END)
        self.text_preview.insert("1.0", json.dumps(preview_data, indent=2))

    def test_ping(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter an API URL to test.")
            return
        token = self.settings.get("data_api_token", "")
        test_payload = {
            "event": "test_ping",
            "action": "ping",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": self.settings.get("user_name", "Developer"),
            "message": "Connection test from Sync Manager"
        }
        self.lbl_status.config(text="⏳ Testing connection...", fg="#2563eb")
        self.update()
        success, msg, code = send_data_api_webhook(test_payload, api_url=url, auth_token=token)
        if success:
            self.lbl_status.config(text=f"✅ Ping success: HTTP {code}", fg="#16a34a")
            messagebox.showinfo("Ping Success", f"✅ Connected to API successfully!\n\n• Endpoint: {url}\n• HTTP Status: {code}\n• Response: {msg}")
        else:
            self.lbl_status.config(text=f"❌ Ping failed: {msg[:60]}", fg="#dc2626")
            messagebox.showerror("Ping Failed", f"❌ Failed to reach API:\n\n{msg}")

    def open_settings(self):
        SettingsDialog(self)

    def execute_sync(self):
        if self.is_syncing:
            return
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid API URL before syncing.")
            return

        records = self.get_selected_records()
        if not records:
            messagebox.showwarning("No Records", "No records found for the selected scope.")
            return

        confirm = messagebox.askyesno(
            "Confirm Sync",
            f"Are you sure you want to send all {len(records)} records to:\n\n{url}\n\nProceed?"
        )
        if not confirm:
            return

        self.is_syncing = True
        self.btn_sync.config(state=tk.DISABLED, text="⏳ Sending to API... Please wait...")
        self.lbl_status.config(text=f"⏳ Sending {len(records)} records to API...", fg="#2563eb")

        scope = self.var_scope.get()
        token = self.settings.get("data_api_token", "")

        payload = {
            "event": "sync_all" if scope == "all" else f"sync_{scope}",
            "action": "sync",
            "scope": scope,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": self.settings.get("user_name", "Developer"),
            "total_records": len(records),
            "records": records,
            "data": records
        }

        def _do_sync():
            ok, resp_msg, code = send_data_api_webhook(payload, api_url=url, auth_token=token, timeout=40)
            self.after(0, lambda: self._on_sync_finished(ok, resp_msg, code, len(records), url))

        threading.Thread(target=_do_sync, daemon=True).start()

    def _on_sync_finished(self, ok, resp_msg, code, count, url):
        self.is_syncing = False
        self.btn_sync.config(state=tk.NORMAL, text=f"🚀 Send Data to API ({count} records)")

        if ok:
            self.lbl_status.config(text=f"✅ Sync Complete! Delivered {count} records (HTTP {code}).", fg="#16a34a")
            self.text_preview.delete("1.0", tk.END)
            self.text_preview.insert("1.0", f"// Server Response (HTTP {code}):\n{resp_msg}")
            if self.on_complete_callback:
                try:
                    self.on_complete_callback()
                except Exception:
                    pass
            messagebox.showinfo("Sync Successful", f"✅ Successfully synced all {count} records to your API URL!\n\n• Endpoint: {url}\n• HTTP Status: {code}\n• Response: {resp_msg}")
        else:
            self.lbl_status.config(text=f"❌ Sync Failed: {resp_msg[:70]}", fg="#dc2626")
            messagebox.showerror("Sync Failed", f"❌ Failed to sync records to API:\n\n{resp_msg}\n\nPlease check your server logs or URL.")

# ---------- Dedicated Google Sheets Cloud Synchronizer Modal Dialog ----------
class GoogleSheetSyncDialog(tk.Toplevel):
    def __init__(self, parent, app_ref=None, on_complete_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.app_ref = app_ref
        self.on_complete_callback = on_complete_callback
        self.title("📊 Google Sheets Cloud Synchronizer")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=730, default_h=660, min_w=640, min_h=540)

        self.settings = load_settings()
        self.is_syncing = False
        self.create_widgets()

    def create_widgets(self):
        # Header banner
        header = tk.Frame(self, bg="#0f9d58", height=56)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_title_box = tk.Frame(header, bg="#0f9d58")
        h_title_box.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(h_title_box, text="📊 Google Sheets Cloud Synchronizer", font=("Segoe UI", 12, "bold"), fg="white", bg="#0f9d58").pack(anchor="w")
        tk.Label(h_title_box, text="Push complete Excel work updates and monthly tabs to your Google Spreadsheet in real-time", font=("Segoe UI", 8), fg="#d1fae5", bg="#0f9d58").pack(anchor="w")

        # Main frame
        main_f = tk.Frame(self, bg="#f8fafc", padx=14, pady=10)
        main_f.pack(fill=tk.BOTH, expand=True)

        # 1. Google Sheet Connection Card
        cfg_card = tk.LabelFrame(main_f, text="  1. Google Apps Script Web App Connection  ", font=("Segoe UI", 9, "bold"), fg="#0f9d58", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        cfg_card.pack(fill=tk.X, pady=(0, 8))

        row1 = tk.Frame(cfg_card, bg="#ffffff")
        row1.pack(fill=tk.X)

        tk.Label(row1, text="Web App URL:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 6))
        self.entry_url = tk.Entry(row1, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=2)
        saved_url = self.settings.get("gsheet_webapp_url", "").strip()
        if saved_url:
            self.entry_url.insert(0, saved_url)

        btn_save_url = tk.Button(row1, text="💾 Save URL", font=("Segoe UI", 8, "bold"), bg="#f1f5f9", fg="#334155", relief="flat", padx=8, pady=2, cursor="hand2", command=self.save_url_only)
        btn_save_url.pack(side=tk.RIGHT)

        btn_test = tk.Button(row1, text="🧪 Test Connection", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=8, pady=2, cursor="hand2", command=self.test_connection)
        btn_test.pack(side=tk.RIGHT, padx=4)

        # Action buttons under URL (Copy Script, Setup Instructions)
        row_tools = tk.Frame(cfg_card, bg="#ffffff")
        row_tools.pack(fill=tk.X, pady=(6, 0))

        btn_copy_code = tk.Button(row_tools, text="📋 Copy Google Apps Script Code", font=("Segoe UI", 8, "bold"), bg="#ecfdf5", fg="#047857", relief="flat", padx=10, pady=3, cursor="hand2", command=self.copy_apps_script)
        btn_copy_code.pack(side=tk.LEFT, padx=(0, 8))

        btn_instructions = tk.Button(row_tools, text="📖 How to Setup in 30 Seconds", font=("Segoe UI", 8), bg="#f8fafc", fg="#475569", relief="flat", padx=8, pady=3, cursor="hand2", command=self.show_instructions)
        btn_instructions.pack(side=tk.LEFT)

        self.lbl_conn_status = tk.Label(cfg_card, text="", font=("Segoe UI", 8), bg="#ffffff")
        self.lbl_conn_status.pack(anchor="w", pady=(4, 0))
        if saved_url:
            last_sync = self.settings.get("gsheet_last_sync", "")
            if last_sync:
                self.lbl_conn_status.config(text=f"Last synchronized: {last_sync}", fg="#64748b")
            else:
                self.lbl_conn_status.config(text="Configured (ready to test or sync)", fg="#047857")
        else:
            self.lbl_conn_status.config(text="⚠️ Not configured. Click 'How to Setup' for quick 4-step instructions.", fg="#d97706")

        # 2. Synchronization Actions Card
        sync_card = tk.LabelFrame(main_f, text="  2. Push / Synchronize Data  ", font=("Segoe UI", 9, "bold"), fg="#0f9d58", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        sync_card.pack(fill=tk.X, pady=(0, 8))

        # Target Month
        curr_month = ""
        if hasattr(self.parent, 'current_selected_month') and self.parent.current_selected_month.get():
            curr_month = self.parent.current_selected_month.get()
        elif hasattr(self.app_ref, 'current_selected_month') and self.app_ref.current_selected_month.get():
            curr_month = self.app_ref.current_selected_month.get()
        else:
            avail = get_available_months()
            curr_month = avail[0] if avail else datetime.datetime.now().strftime("%B %Y")
        self.target_month_name = curr_month

        avail_months = get_available_months()
        all_recs = get_all_records_across_all_sheets()
        month_recs = get_records_for_month(curr_month)

        act_row = tk.Frame(sync_card, bg="#ffffff")
        act_row.pack(fill=tk.X, pady=4)

        self.btn_sync_month = tk.Button(
            act_row,
            text=f"🚀 Sync Current Month ('{curr_month}' - {len(month_recs)} rows)",
            font=("Segoe UI", 9, "bold"),
            bg="#0f9d58",
            fg="white",
            activebackground="#0b8043",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.sync_current_month
        )
        self.btn_sync_month.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_sync_all = tk.Button(
            act_row,
            text=f"🌐 Sync All Months ({len(avail_months)} sheets - {len(all_recs)} rows)",
            font=("Segoe UI", 9, "bold"),
            bg="#1e40af",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.sync_all_months
        )
        self.btn_sync_all.pack(side=tk.LEFT)

        # Automation checkbox
        self.var_auto_sync = tk.BooleanVar(value=bool(self.settings.get("gsheet_auto_sync", False)))
        chk_auto = tk.Checkbutton(
            sync_card,
            text="⚡ Auto-Sync: Automatically update Google Sheet tab in background on every Save / Edit / Delete",
            variable=self.var_auto_sync,
            font=("Segoe UI", 9, "bold"),
            fg="#1e293b",
            bg="#ffffff",
            command=self.toggle_auto_sync
        )
        chk_auto.pack(anchor="w", pady=(8, 2))

        # 3. Live Activity & Response Log Card
        log_card = tk.LabelFrame(main_f, text="  3. Live Activity & Server Response Log  ", font=("Segoe UI", 9, "bold"), fg="#0f9d58", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.lbl_progress = tk.Label(log_card, text="Ready. Click 'Sync Current Month' or 'Sync All Months' to begin.", font=("Segoe UI", 9), bg="#ffffff", fg="#475569")
        self.lbl_progress.pack(anchor="w", pady=(0, 4))

        self.text_log = tk.Text(log_card, font=("Consolas", 8), height=8, bg="#f8fafc", fg="#334155", relief="solid", bd=1, wrap=tk.NONE)
        self.text_log.pack(fill=tk.BOTH, expand=True)
        self.log_message(f"WorkPulse Google Sheet Sync Initialized. Local sheets: {len(avail_months)} ({', '.join(avail_months[:3])}...)")

        # Bottom Bar
        bottom = tk.Frame(self, bg="#f1f5f9", padx=14, pady=8)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        btn_close = tk.Button(bottom, text="Close", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=14, pady=4, cursor="hand2", command=self.destroy)
        btn_close.pack(side=tk.RIGHT)

    def log_message(self, text):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.text_log.insert(tk.END, f"[{ts}] {text}\n")
        self.text_log.see(tk.END)

    def copy_apps_script(self):
        code = get_google_apps_script_code()
        self.clipboard_clear()
        self.clipboard_append(code)
        self.update()
        self.log_message("Copied Google Apps Script code to clipboard.")
        messagebox.showinfo(
            "Code Copied",
            "📋 Google Apps Script code copied to clipboard!\n\n"
            "Next steps:\n"
            "1. Open your Google Sheet in browser.\n"
            "2. Click Extensions -> Apps Script.\n"
            "3. Paste code and click Save (💾).\n"
            "4. Deploy -> New deployment -> type: Web app (Who has access: Anyone).\n"
            "5. Copy Web app URL and paste into WorkPulse."
        )

    def show_instructions(self):
        top = tk.Toplevel(self)
        top.title("📖 How to Setup Google Sheet Sync (4 Steps)")
        top.configure(bg="#ffffff")
        top.transient(self)
        center_window(top, self, default_w=640, default_h=480)

        header = tk.Frame(top, bg="#0f9d58", height=45)
        header.pack(fill=tk.X)
        tk.Label(header, text="📖 Google Sheets Setup Guide", font=("Segoe UI", 11, "bold"), fg="white", bg="#0f9d58").pack(side=tk.LEFT, padx=12, pady=10)

        txt_frame = tk.Frame(top, bg="#ffffff", padx=15, pady=12)
        txt_frame.pack(fill=tk.BOTH, expand=True)

        guide_msg = (
            "Setting up Google Sheets sync is 100% FREE and takes 30 seconds:\n\n"
            "Step 1: Open your Google Sheet\n"
            "• Create a new Google Sheet or open your existing sheet at sheets.google.com.\n\n"
            "Step 2: Open Apps Script\n"
            "• In the top menu, click 'Extensions' -> 'Apps Script'.\n\n"
            "Step 3: Paste the WorkPulse Script\n"
            "• Delete any template code in the editor.\n"
            "• Click 'Copy Google Apps Script Code' in WorkPulse and paste it in the editor.\n"
            "• Click the Save icon (💾) or press Ctrl+S.\n\n"
            "Step 4: Deploy as Web App\n"
            "• In the top right, click 'Deploy' -> 'New deployment'.\n"
            "• Click the gear icon (⚙️) next to 'Select type' and choose 'Web app'.\n"
            "• Set 'Execute as' -> 'Me (<your email>)'.\n"
            "• Set 'Who has access' -> 'Anyone' (Required for WorkPulse sync).\n"
            "• Click 'Deploy' -> Authorize access.\n"
            "• Copy the 'Web app URL' (ends in /exec) and paste it into WorkPulse!\n\n"
            "That's it! Your WorkPulse desktop & mobile apps will now sync to Google Sheets seamlessly!"
        )
        t = tk.Text(txt_frame, font=("Segoe UI", 9), bg="#f8fafc", fg="#1e293b", wrap=tk.WORD, relief="solid", bd=1, padx=8, pady=8)
        t.insert("1.0", guide_msg)
        t.config(state=tk.DISABLED)
        t.pack(fill=tk.BOTH, expand=True)

        btn_box = tk.Frame(top, bg="#ffffff", padx=15, pady=8)
        btn_box.pack(fill=tk.X)
        btn_copy = tk.Button(btn_box, text="📋 Copy Apps Script Code", font=("Segoe UI", 9, "bold"), bg="#0f9d58", fg="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.copy_apps_script)
        btn_copy.pack(side=tk.LEFT)
        btn_ok = tk.Button(btn_box, text="Got it!", font=("Segoe UI", 9), bg="#e2e8f0", fg="#334155", relief="flat", padx=14, pady=4, cursor="hand2", command=top.destroy)
        btn_ok.pack(side=tk.RIGHT)

    def save_url_only(self):
        url = self.entry_url.get().strip()
        self.settings["gsheet_webapp_url"] = url
        if not self.settings.get("gsheet_auto_sync", False):
            self.settings["gsheet_auto_sync"] = True
            if hasattr(self, 'var_auto_sync'):
                self.var_auto_sync.set(True)
        save_settings(self.settings)
        if hasattr(self.parent, 'settings') and isinstance(self.parent.settings, dict):
            self.parent.settings.update(self.settings)
        self.log_message(f"Saved Web App URL: {url[:50]}...")
        self.lbl_conn_status.config(text="Saved! Ready to test connection.", fg="#047857")
        messagebox.showinfo("Saved", "Google Sheet Web App URL saved successfully!\nAuto-sync is enabled.")

    def toggle_auto_sync(self):
        val = self.var_auto_sync.get()
        self.settings["gsheet_auto_sync"] = val
        save_settings(self.settings)
        if hasattr(self.parent, 'settings') and isinstance(self.parent.settings, dict):
            self.parent.settings["gsheet_auto_sync"] = val
        status_str = "ENABLED" if val else "DISABLED"
        self.log_message(f"Auto-Sync on Save/Edit/Delete is now {status_str}.")

    def test_connection(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Empty URL", "Please enter your Google Sheet Web App URL.")
            return

        self.save_url_only()
        self.log_message(f"Pinging Google Sheet Web App at {url[:45]}...")
        self.lbl_progress.config(text="Testing connection...", fg="#0284c7")

        def _do_ping():
            ok, data, code = ping_google_sheet(webapp_url=url)
            self.after(0, lambda: self._on_ping_finished(ok, data, code))

        threading.Thread(target=_do_ping, daemon=True).start()

    def _on_ping_finished(self, ok, data, code):
        if ok:
            title = data.get("sheetTitle", "Google Spreadsheet") if isinstance(data, dict) else "Google Spreadsheet"
            sheets = data.get("sheets", []) if isinstance(data, dict) else []
            sheets_str = f" ({len(sheets)} tabs: {', '.join(sheets[:3])}...)" if sheets else ""
            self.log_message(f"SUCCESS: Connected to '{title}'{sheets_str} [HTTP {code}]")
            self.lbl_progress.config(text=f"✅ Connected to '{title}'", fg="#16a34a")
            self.lbl_conn_status.config(text=f"✅ Connected: '{title}'", fg="#16a34a")
            messagebox.showinfo("Connected", f"✅ Successfully connected to Google Sheet!\n\n• Sheet: {title}\n• Status: Online\n• Code: HTTP {code}")
        else:
            msg = data if isinstance(data, str) else data.get("message", "Unknown error")
            self.log_message(f"FAILED: {msg} [HTTP {code}]")
            self.lbl_progress.config(text=f"❌ Connection failed: {str(msg)[:40]}", fg="#dc2626")
            self.lbl_conn_status.config(text="❌ Connection failed", fg="#dc2626")
            messagebox.showerror("Connection Failed", f"❌ Failed to reach Google Sheet Web App:\n\n{msg}\n\nPlease check your URL and ensure deployment is set to 'Who has access: Anyone'.")

    def sync_current_month(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Empty URL", "Please enter your Google Sheet Web App URL first.")
            return

        month = self.target_month_name
        self.is_syncing = True
        self.btn_sync_month.config(state=tk.DISABLED, text="⏳ Syncing Month...")
        self.btn_sync_all.config(state=tk.DISABLED)
        self.lbl_progress.config(text=f"Pushing '{month}' to Google Sheet...", fg="#0284c7")
        self.log_message(f"Starting sync for month tab: '{month}'...")

        def _do_sync():
            ok, data, code = sync_google_sheet_month(month_name=month, webapp_url=url)
            self.after(0, lambda: self._on_sync_month_finished(ok, data, code, month))

        threading.Thread(target=_do_sync, daemon=True).start()

    def _on_sync_month_finished(self, ok, data, code, month):
        self.is_syncing = False
        recs = get_records_for_month(month)
        self.btn_sync_month.config(state=tk.NORMAL, text=f"🚀 Sync Current Month ('{month}' - {len(recs)} rows)")
        self.btn_sync_all.config(state=tk.NORMAL)

        if ok:
            rows_cnt = data.get("updatedRows", len(recs)) if isinstance(data, dict) else len(recs)
            title = data.get("sheetTitle", "Google Sheet") if isinstance(data, dict) else "Google Sheet"
            self.log_message(f"SUCCESS: Synchronized {rows_cnt} rows to '{month}' tab in '{title}' [HTTP {code}].")
            self.lbl_progress.config(text=f"✅ Synced {rows_cnt} rows to '{month}' tab successfully!", fg="#16a34a")
            self.lbl_conn_status.config(text=f"Last synchronized: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fg="#64748b")
            if self.on_complete_callback:
                try:
                    self.on_complete_callback()
                except Exception:
                    pass
            messagebox.showinfo("Sync Complete", f"✅ Successfully synchronized month '{month}'!\n\n• Google Sheet: {title}\n• Tab: {month}\n• Rows Synced: {rows_cnt}\n\nWeekly offs and holidays have been highlighted!")
        else:
            msg = data if isinstance(data, str) else data.get("message", "Unknown error")
            self.log_message(f"FAILED: {msg} [HTTP {code}]")
            self.lbl_progress.config(text=f"❌ Sync failed: {str(msg)[:40]}", fg="#dc2626")
            messagebox.showerror("Sync Failed", f"❌ Failed to sync month '{month}' to Google Sheet:\n\n{msg}")

    def sync_all_months(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Empty URL", "Please enter your Google Sheet Web App URL first.")
            return

        months = get_available_months()
        all_recs = get_all_records_across_all_sheets()
        if not messagebox.askyesno("Sync All Months", f"Push all {len(months)} months ({len(all_recs)} total rows) to Google Sheet tabs?"):
            return

        self.is_syncing = True
        self.btn_sync_all.config(state=tk.DISABLED, text="⏳ Syncing All Sheets...")
        self.btn_sync_month.config(state=tk.DISABLED)
        self.lbl_progress.config(text=f"Pushing {len(months)} month tabs to Google Sheet...", fg="#0284c7")
        self.log_message(f"Starting bulk sync for {len(months)} sheets ({len(all_recs)} total records)...")

        def _do_sync_all():
            ok, data, code = sync_google_sheet_all(webapp_url=url)
            self.after(0, lambda: self._on_sync_all_finished(ok, data, code, len(months), len(all_recs)))

        threading.Thread(target=_do_sync_all, daemon=True).start()

    def _on_sync_all_finished(self, ok, data, code, sheets_cnt, total_rows):
        self.is_syncing = False
        recs = get_records_for_month(self.target_month_name)
        self.btn_sync_month.config(state=tk.NORMAL, text=f"🚀 Sync Current Month ('{self.target_month_name}' - {len(recs)} rows)")
        self.btn_sync_all.config(state=tk.NORMAL, text=f"🌐 Sync All Months ({sheets_cnt} sheets - {total_rows} rows)")

        if ok:
            title = data.get("sheetTitle", "Google Sheet") if isinstance(data, dict) else "Google Sheet"
            self.log_message(f"SUCCESS: Synchronized {sheets_cnt} sheets ({total_rows} rows) to '{title}' [HTTP {code}].")
            self.lbl_progress.config(text=f"✅ Synced {sheets_cnt} sheets ({total_rows} records) successfully!", fg="#16a34a")
            self.lbl_conn_status.config(text=f"Last synchronized: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fg="#64748b")
            messagebox.showinfo("Bulk Sync Complete", f"✅ All {sheets_cnt} month tabs synchronized successfully!\n\n• Target Spreadsheet: {title}\n• Total Sheets: {sheets_cnt}\n• Total Records: {total_rows}")
        else:
            msg = data if isinstance(data, str) else data.get("message", "Unknown error")
            self.log_message(f"FAILED: {msg} [HTTP {code}]")
            self.lbl_progress.config(text=f"❌ Bulk sync failed: {str(msg)[:40]}", fg="#dc2626")
            messagebox.showerror("Sync Failed", f"❌ Failed to sync all months to Google Sheet:\n\n{msg}")

# ---------- Dedicated Weekend & Holiday Settings Modal Dialog ----------
class WeekendHolidayDialog(tk.Toplevel):
    def __init__(self, parent, on_sync_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_sync_callback = on_sync_callback
        self.title("🏖️ Weekend & Holiday Settings")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=740, default_h=670, min_w=680, min_h=560)

        self.settings = load_settings()
        self.holidays_list = list(self.settings.get("holidays", STANDARD_HOLIDAYS_2026))
        self.create_widgets()

    def create_widgets(self):
        # Header banner
        header = tk.Frame(self, bg="#0f172a", height=58)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_box = tk.Frame(header, bg="#0f172a")
        h_box.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(h_box, text="🏖️ Weekend & Holiday Settings", font=("Segoe UI", 12, "bold"), fg="white", bg="#0f172a").pack(anchor="w")
        tk.Label(h_box, text="Configure weekly offs, public holidays, date-wise auto-arranging, and 1-click sheet sync", font=("Segoe UI", 8), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

        # Tab Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 6))

        # Tab 1: Weekends & Weekly Offs
        tab_weekends = tk.Frame(self.notebook, bg="#ffffff", padx=16, pady=12)
        self.notebook.add(tab_weekends, text="  🏖️ Weekends & Weekly Offs  ")
        self.build_weekends_tab(tab_weekends)

        # Tab 2: Holidays Manager
        tab_holidays = tk.Frame(self.notebook, bg="#ffffff", padx=16, pady=12)
        self.notebook.add(tab_holidays, text="  🎉 Public & National Holidays  ")
        self.build_holidays_tab(tab_holidays)

        # Tab 3: Sheet Sync & Auto-Arrange
        tab_sync = tk.Frame(self.notebook, bg="#ffffff", padx=16, pady=12)
        self.notebook.add(tab_sync, text="  📅 Monthly Sync & Auto-Arrange  ")
        self.build_sync_tab(tab_sync)

        # Bottom Bar
        bottom = tk.Frame(self, bg="#f1f5f9", padx=16, pady=10)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        btn_save = tk.Button(bottom, text="💾 Save Settings & Apply", font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white", activebackground="#15803d", activeforeground="white", relief="flat", padx=16, pady=6, cursor="hand2", command=self.save)
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(bottom, text="Cancel", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=12, pady=6, cursor="hand2", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=4)

    def build_weekends_tab(self, parent):
        # Preset Frame
        preset_frame = tk.LabelFrame(parent, text="  1. Quick Weekend Preset  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        preset_frame.pack(fill=tk.X, pady=(0, 10))

        self.var_preset = tk.StringVar(value=self.settings.get("weekend_mode", "Sunday"))
        
        presets = [
            ("Sunday", "Sunday Only (Standard 6-day work week)"),
            ("SatSun", "Saturday & Sunday (Standard 5-day work week)"),
            ("Sun2nd4thSat", "Sunday + 2nd & 4th Saturday Off (Corporate / Banking style)"),
            ("Custom", "Custom Weekly Offs (Configure below)")
        ]

        for val, label_text in presets:
            rb = tk.Radiobutton(preset_frame, text=label_text, value=val, variable=self.var_preset, bg="#ffffff", font=("Segoe UI", 9), command=self.on_preset_change)
            rb.pack(anchor="w", pady=2)

        # Individual Days Checkboxes Frame
        days_frame = tk.LabelFrame(parent, text="  2. Select Weekly Off Days  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        days_frame.pack(fill=tk.X, pady=(0, 10))

        configured_offs = set(self.settings.get("weekly_offs", ["Sunday"]))
        self.off_vars = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        d_box = tk.Frame(days_frame, bg="#ffffff")
        d_box.pack(fill=tk.X, pady=4)
        for d in day_names:
            var = tk.BooleanVar(value=(d in configured_offs))
            self.off_vars[d] = var
            chk = tk.Checkbutton(d_box, text=d, variable=var, bg="#ffffff", font=("Segoe UI", 9), command=self.on_day_checkbox_toggle)
            chk.pack(side=tk.LEFT, padx=(0, 10))

        # Alternate Saturdays
        alt_frame = tk.LabelFrame(parent, text="  3. Alternate Saturdays Rule  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=12, pady=8, bd=1, relief="solid")
        alt_frame.pack(fill=tk.X, pady=(0, 10))

        self.var_sec_fourth = tk.BooleanVar(value=bool(self.settings.get("second_fourth_saturday", False)))
        chk_sat = tk.Checkbutton(alt_frame, text="2nd & 4th Saturday of every month are Official Weekly Offs", variable=self.var_sec_fourth, bg="#ffffff", font=("Segoe UI", 9, "bold"), fg="#334155", command=self.on_sec_fourth_toggle)
        chk_sat.pack(anchor="w", pady=2)
        tk.Label(alt_frame, text="• Automatically calculates the 2nd and 4th Saturday for any month (e.g., Oct 10 & Oct 24, 2026).", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(anchor="w")

        # Live info banner
        self.lbl_weekend_summary = tk.Label(parent, text="", font=("Segoe UI", 9, "italic"), bg="#f1f5f9", fg="#1e293b", padx=10, pady=6, relief="flat", bd=1)
        self.lbl_weekend_summary.pack(fill=tk.X, pady=(4, 0))
        self.update_weekend_summary()

    def on_preset_change(self):
        p = self.var_preset.get()
        if p == "Sunday":
            for d, var in self.off_vars.items():
                var.set(d == "Sunday")
            self.var_sec_fourth.set(False)
        elif p == "SatSun":
            for d, var in self.off_vars.items():
                var.set(d in ("Saturday", "Sunday"))
            self.var_sec_fourth.set(False)
        elif p == "Sun2nd4thSat":
            for d, var in self.off_vars.items():
                var.set(d == "Sunday")
            self.var_sec_fourth.set(True)
        self.update_weekend_summary()

    def on_day_checkbox_toggle(self):
        self.var_preset.set("Custom")
        self.update_weekend_summary()

    def on_sec_fourth_toggle(self):
        if self.var_preset.get() != "Sun2nd4thSat":
            self.var_preset.set("Custom")
        self.update_weekend_summary()

    def update_weekend_summary(self):
        offs = [d for d, var in self.off_vars.items() if var.get()]
        text_parts = []
        if offs:
            text_parts.append(f"Weekly Off Days: {', '.join(offs)}")
        else:
            text_parts.append("No full weekly off days selected")
        if self.var_sec_fourth.get():
            text_parts.append("+ 2nd & 4th Saturday Off")
        self.lbl_weekend_summary.config(text="📌 Active Weekend Schedule: " + " | ".join(text_parts))

    def build_holidays_tab(self, parent):
        # Add Holiday form
        add_frame = tk.LabelFrame(parent, text="  Add / Update Holiday  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=8, bd=1, relief="solid")
        add_frame.pack(fill=tk.X, pady=(0, 8))

        r1 = tk.Frame(add_frame, bg="#ffffff")
        r1.pack(fill=tk.X, pady=2)

        tk.Label(r1, text="Date (YYYY-MM-DD):", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_hol_date = tk.Entry(r1, font=("Segoe UI", 9), width=12, relief="solid", bd=1)
        self.entry_hol_date.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_hol_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))

        btn_today = tk.Button(r1, text="Today", font=("Segoe UI", 7, "bold"), bg="#edf2f7", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: [self.entry_hol_date.delete(0, tk.END), self.entry_hol_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))])
        btn_today.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(r1, text="Holiday Name / Occasion:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_hol_name = tk.Entry(r1, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_hol_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=1)

        btn_add = tk.Button(r1, text="➕ Add / Update", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="white", relief="flat", padx=10, pady=2, cursor="hand2", command=self.add_holiday)
        btn_add.pack(side=tk.LEFT)

        # Quick preset buttons bar
        r2 = tk.Frame(add_frame, bg="#ffffff")
        r2.pack(fill=tk.X, pady=(6, 2))

        btn_load_std = tk.Button(r2, text="🇮🇳 Load Standard 2026 Indian Holidays (19 Official Holidays)", font=("Segoe UI", 8, "bold"), bg="#fef3c7", fg="#92400e", activebackground="#fde68a", relief="flat", padx=10, pady=3, cursor="hand2", command=self.load_indian_holidays_preset)
        btn_load_std.pack(side=tk.LEFT)

        # Holidays Table
        tree_box = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        tree_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.hol_tree = ttk.Treeview(tree_box, columns=("Date", "Day", "Name"), show="headings", height=7)
        self.hol_tree.heading("Date", text="Date (YYYY-MM-DD)")
        self.hol_tree.column("Date", width=120, anchor="center")

        self.hol_tree.heading("Day", text="Day of Week")
        self.hol_tree.column("Day", width=110, anchor="center")

        self.hol_tree.heading("Name", text="Holiday Name / Occasion")
        self.hol_tree.column("Name", width=280, anchor="w")

        h_scroll = ttk.Scrollbar(tree_box, orient="vertical", command=self.hol_tree.yview)
        self.hol_tree.configure(yscrollcommand=h_scroll.set)
        self.hol_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.hol_tree.bind("<Double-1>", self.on_holiday_row_double_click)

        self.refresh_holidays_tree()

        # Action bar under table
        hol_actions = tk.Frame(parent, bg="#ffffff")
        hol_actions.pack(fill=tk.X)

        btn_del = tk.Button(hol_actions, text="🗑️ Remove Selected Holiday", font=("Segoe UI", 8), bg="#fee2e2", fg="#991b1b", relief="flat", padx=8, pady=3, cursor="hand2", command=self.remove_selected_holiday)
        btn_del.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = tk.Button(hol_actions, text="🧹 Clear All Holidays", font=("Segoe UI", 8), bg="#f1f5f9", fg="#64748b", relief="flat", padx=8, pady=3, cursor="hand2", command=self.clear_all_holidays)
        btn_clear.pack(side=tk.LEFT)

    def refresh_holidays_tree(self):
        for r in self.hol_tree.get_children():
            self.hol_tree.delete(r)

        for h in sorted(self.holidays_list, key=lambda x: x.get("date", "")):
            d = h.get("date", "")
            try:
                day_name = datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%A")
            except Exception:
                day_name = "-"
            self.hol_tree.insert("", tk.END, values=(d, day_name, h.get("name", "")))

    def on_holiday_row_double_click(self, event):
        sel = self.hol_tree.selection()
        if not sel:
            return
        vals = self.hol_tree.item(sel[0])["values"]
        self.entry_hol_date.delete(0, tk.END)
        self.entry_hol_date.insert(0, str(vals[0]))
        self.entry_hol_name.delete(0, tk.END)
        self.entry_hol_name.insert(0, str(vals[2]))

    def add_holiday(self):
        d_val = format_date_only(self.entry_hol_date.get().strip())
        name_val = self.entry_hol_name.get().strip()

        if not d_val:
            messagebox.showwarning("Validation Error", "Please provide a valid date in format YYYY-MM-DD.")
            return

        try:
            datetime.datetime.strptime(d_val, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Date must be YYYY-MM-DD (e.g. 2026-10-02).")
            return

        if not name_val:
            messagebox.showwarning("Validation Error", "Please enter a Holiday Name (e.g. Mahatma Gandhi Jayanti).")
            return

        for h in self.holidays_list:
            if h.get("date") == d_val:
                h["name"] = name_val
                self.refresh_holidays_tree()
                self.entry_hol_name.delete(0, tk.END)
                messagebox.showinfo("Updated", f"Updated holiday for {d_val}.")
                return

        self.holidays_list.append({"date": d_val, "name": name_val})
        self.refresh_holidays_tree()
        self.entry_hol_name.delete(0, tk.END)

    def remove_selected_holiday(self):
        sel = self.hol_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a holiday from the table to remove.")
            return
        item = self.hol_tree.item(sel[0])
        date_to_remove = str(item["values"][0])
        self.holidays_list = [h for h in self.holidays_list if h.get("date") != date_to_remove]
        self.refresh_holidays_tree()

    def clear_all_holidays(self):
        if not self.holidays_list:
            return
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all configured holidays?"):
            self.holidays_list = []
            self.refresh_holidays_tree()

    def load_indian_holidays_preset(self):
        if messagebox.askyesno("Load 2026 Indian Holidays", "Would you like to load the standard list of 19 official 2026 Indian Holidays?"):
            existing_dates = {h.get("date") for h in self.holidays_list}
            for std_h in STANDARD_HOLIDAYS_2026:
                if std_h["date"] not in existing_dates:
                    self.holidays_list.append(std_h.copy())
            self.refresh_holidays_tree()
            messagebox.showinfo("Holidays Loaded", f"Loaded standard Indian holidays list successfully. Total holidays: {len(self.holidays_list)}")

    def build_sync_tab(self, parent):
        # Auto-Arrange Options Card
        opt_frame = tk.LabelFrame(parent, text="  1. Data Auto-Arrangement Settings  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=12, pady=10, bd=1, relief="solid")
        opt_frame.pack(fill=tk.X, pady=(0, 12))

        self.var_auto_sync = tk.BooleanVar(value=bool(self.settings.get("auto_sync_weekends_holidays", True)))
        chk_sync = tk.Checkbutton(opt_frame, text="🏖️ Automatically populate missing Weekend & Holiday rows for all months", variable=self.var_auto_sync, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0369a1")
        chk_sync.pack(anchor="w", pady=2)

        self.var_auto_arrange = tk.BooleanVar(value=bool(self.settings.get("auto_arrange_by_date", True)))
        chk_auto = tk.Checkbutton(opt_frame, text="⚡ Automatically arrange all records chronologically date-wise on save & load", variable=self.var_auto_arrange, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e293b")
        chk_auto.pack(anchor="w", pady=2)

        self.var_highlight = tk.BooleanVar(value=bool(self.settings.get("highlight_weekends_holidays", True)))
        chk_hl = tk.Checkbutton(opt_frame, text="🎨 Visual Color Highlights for Weekends & Holidays in table and Excel", variable=self.var_highlight, font=("Segoe UI", 9), bg="#ffffff", fg="#334155")
        chk_hl.pack(anchor="w", pady=2)

        # Sort order
        tk.Label(opt_frame, text="Default Date Sort Order:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w", pady=(6, 2))
        s_box = tk.Frame(opt_frame, bg="#ffffff")
        s_box.pack(fill=tk.X)
        self.var_sort_order = tk.StringVar(value=self.settings.get("date_sort_order", "asc"))
        tk.Radiobutton(s_box, text="Ascending (1st → 31st / Chronological)", value="asc", variable=self.var_sort_order, bg="#ffffff", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 15))
        tk.Radiobutton(s_box, text="Descending (Most Recent Date First)", value="desc", variable=self.var_sort_order, bg="#ffffff", font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # Monthly Sheet Synchronization Card
        sync_frame = tk.LabelFrame(parent, text="  2. Excel Monthly Sheet Synchronization  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=12, pady=10, bd=1, relief="solid")
        sync_frame.pack(fill=tk.X, pady=(0, 8))

        target_month = datetime.datetime.now().strftime("%B %Y")
        if hasattr(self.parent, "current_selected_month") and self.parent.current_selected_month.get():
            target_month = self.parent.current_selected_month.get()

        lbl_target = tk.Label(sync_frame, text=f"📁 Target Month Sheet:  {target_month}", font=("Segoe UI", 10, "bold"), bg="#e0f2fe", fg="#0369a1", padx=8, pady=4)
        lbl_target.pack(anchor="w", pady=(0, 8))

        tk.Label(sync_frame, text="Synchronize and populate all configured Weekends and Holidays into the month sheet in Excel.\nReal work updates are never deleted or modified.", font=("Segoe UI", 9), bg="#ffffff", fg="#64748b", justify="left").pack(anchor="w", pady=(0, 8))

        b_box = tk.Frame(sync_frame, bg="#ffffff")
        b_box.pack(fill=tk.X, pady=4)

        btn_sync = tk.Button(b_box, text="📅 Sync Weekends & Holidays to Current Sheet", font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=12, pady=6, cursor="hand2", command=lambda: self.execute_sync(clean=False))
        btn_sync.pack(side=tk.LEFT, padx=(0, 8))

        btn_resync = tk.Button(b_box, text="🔄 Clean Re-Sync Current Sheet", font=("Segoe UI", 9), bg="#ede9fe", fg="#6d28d9", activebackground="#ddd6fe", relief="flat", padx=12, pady=6, cursor="hand2", command=lambda: self.execute_sync(clean=True))
        btn_resync.pack(side=tk.LEFT)

    def execute_sync(self, clean=False):
        target_month = None
        if hasattr(self.parent, 'current_selected_month'):
            target_month = self.parent.current_selected_month.get()
        if not target_month:
            target_month = datetime.datetime.now().strftime("%B %Y")

        self.save_internal()

        h_count, o_count, s_name = sync_month_holidays_and_weekly_offs(target_month, clean_re_sync=clean)
        if hasattr(self.parent, 'refresh_all'):
            self.parent.refresh_all()

        action_desc = "Clean Re-Sync" if clean else "Sync"
        messagebox.showinfo(f"{action_desc} Complete", f"✅ Sheet '{s_name}' synchronized successfully!\n\n• Added Holidays: {h_count}\n• Added Weekly Offs: {o_count}\n\nAll records in '{s_name}' have been auto-arranged chronologically date-wise.")

    def save_internal(self):
        selected_offs = [d for d, var in self.off_vars.items() if var.get()]
        self.settings.update({
            "weekend_mode": self.var_preset.get(),
            "second_fourth_saturday": self.var_sec_fourth.get(),
            "weekly_offs": selected_offs,
            "holidays": self.holidays_list,
            "auto_sync_weekends_holidays": self.var_auto_sync.get(),
            "auto_arrange_by_date": self.var_auto_arrange.get(),
            "date_sort_order": self.var_sort_order.get(),
            "highlight_weekends_holidays": self.var_highlight.get()
        })
        save_settings(self.settings)

    def save(self):
        self.save_internal()

        # Immediately auto-sync / auto-arrange current month sheet
        if hasattr(self.parent, 'current_selected_month'):
            s_name = self.parent.current_selected_month.get()
            if s_name:
                if self.var_auto_sync.get():
                    sync_month_holidays_and_weekly_offs(s_name, clean_re_sync=True, silent=True)
                elif self.var_auto_arrange.get():
                    auto_arrange_sheet_by_date(s_name, ascending=(self.var_sort_order.get() == "asc"))

        if self.on_sync_callback:
            self.on_sync_callback()
        elif hasattr(self.parent, 'refresh_all'):
            self.parent.refresh_all()

        messagebox.showinfo("Saved", "✅ Weekend & Holiday settings saved successfully!\nWeekend & Holiday records have been updated automatically date-wise.")
        self.destroy()

# ---------- Dedicated Add / Mark Leave Modal Dialog ----------
class AddLeaveDialog(tk.Toplevel):
    def __init__(self, parent, default_date=None, on_success_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_success_callback = on_success_callback
        self.title("🌴 Add / Record Leave")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=580, default_h=570, min_w=500, min_h=460)

        # Quick keyboard shortcuts
        self.bind("<Return>", lambda e: self.submit_leave())
        self.bind("<KP_Enter>", lambda e: self.submit_leave())
        self.bind("<Escape>", lambda e: self.destroy())

        self.initial_date = default_date or datetime.datetime.now().strftime("%Y-%m-%d")
        self.settings = load_settings()

        self.create_widgets()
        self.update_preview()

    def create_widgets(self):
        # Header banner
        header = tk.Frame(self, bg="#1e293b", height=46)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_title_box = tk.Frame(header, bg="#1e293b")
        h_title_box.pack(side=tk.LEFT, padx=15, pady=6)
        tk.Label(h_title_box, text="🌴 Add / Record Leave", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(anchor="w")
        tk.Label(h_title_box, text="Record single or multi-day leaves into your monthly Excel sheet", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(anchor="w")

        # Bottom Actions Bar (Pack side=tk.BOTTOM FIRST so it is ALWAYS permanently visible)
        bottom_bar = tk.Frame(self, bg="#f1f5f9", padx=14, pady=8)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        btn_confirm = tk.Button(
            bottom_bar,
            text="💾 Confirm & Record Leave (Enter)",
            font=("Segoe UI", 9, "bold"),
            bg="#16a34a",
            fg="white",
            activebackground="#15803d",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.submit_leave
        )
        btn_confirm.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(
            bottom_bar,
            text="Cancel (Esc)",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#475569",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, padx=4)

        # Main container (Packed in middle between header and bottom_bar)
        main_f = tk.Frame(self, bg="#ffffff", padx=14, pady=8, bd=1, relief="solid")
        main_f.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))

        # 1. Leave Mode Card
        mode_box = tk.LabelFrame(main_f, text="  1. Leave Mode  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=4, bd=1, relief="solid")
        mode_box.pack(fill=tk.X, pady=(0, 6))

        self.var_mode = tk.StringVar(value="single")
        tk.Radiobutton(mode_box, text="📅 Single Day Leave", value="single", variable=self.var_mode, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e293b", command=self.on_mode_change).pack(side=tk.LEFT, padx=(0, 20))
        tk.Radiobutton(mode_box, text="📆 Date Range (Multiple Days)", value="range", variable=self.var_mode, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e293b", command=self.on_mode_change).pack(side=tk.LEFT)

        # 2. Date Selection Card
        self.date_box = tk.LabelFrame(main_f, text="  2. Date Selection  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        self.date_box.pack(fill=tk.X, pady=(0, 6))

        # Container for Single Day
        self.f_single_date = tk.Frame(self.date_box, bg="#ffffff")
        self.f_single_date.pack(fill=tk.X)

        tk.Label(self.f_single_date, text="Leave Date (YYYY-MM-DD):", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w")
        s_date_row = tk.Frame(self.f_single_date, bg="#ffffff")
        s_date_row.pack(fill=tk.X, pady=2)

        self.entry_single_date = tk.Entry(s_date_row, font=("Segoe UI", 9), width=16, relief="solid", bd=1)
        self.entry_single_date.pack(side=tk.LEFT, ipady=2)
        self.entry_single_date.insert(0, self.initial_date)
        self.entry_single_date.bind("<KeyRelease>", lambda e: self.update_preview())

        btn_today = tk.Button(s_date_row, text="Today", font=("Segoe UI", 8), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=6, pady=2, cursor="hand2", command=lambda: self.set_single_date(datetime.datetime.now().strftime("%Y-%m-%d")))
        btn_today.pack(side=tk.LEFT, padx=(6, 4))

        btn_tmr = tk.Button(s_date_row, text="Tomorrow", font=("Segoe UI", 8), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=6, pady=2, cursor="hand2", command=lambda: self.set_single_date((datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")))
        btn_tmr.pack(side=tk.LEFT, padx=4)

        # Container for Date Range (Hidden by default)
        self.f_range_date = tk.Frame(self.date_box, bg="#ffffff")

        r_inputs = tk.Frame(self.f_range_date, bg="#ffffff")
        r_inputs.pack(fill=tk.X, pady=2)

        tk.Label(r_inputs, text="From Date:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_from_date = tk.Entry(r_inputs, font=("Segoe UI", 9), width=13, relief="solid", bd=1)
        self.entry_from_date.pack(side=tk.LEFT, ipady=2)
        self.entry_from_date.insert(0, self.initial_date)
        self.entry_from_date.bind("<KeyRelease>", lambda e: self.update_preview())

        tk.Label(r_inputs, text="To Date:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT, padx=(10, 4))
        self.entry_to_date = tk.Entry(r_inputs, font=("Segoe UI", 9), width=13, relief="solid", bd=1)
        self.entry_to_date.pack(side=tk.LEFT, ipady=2)
        self.entry_to_date.insert(0, self.initial_date)
        self.entry_to_date.bind("<KeyRelease>", lambda e: self.update_preview())

        # Quick preset buttons for range
        r_presets = tk.Frame(self.f_range_date, bg="#ffffff")
        r_presets.pack(fill=tk.X, pady=(4, 2))
        tk.Label(r_presets, text="Quick Duration:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT, padx=(0, 4))

        btn_2d = tk.Button(r_presets, text="2 Days", font=("Segoe UI", 7, "bold"), bg="#f8fafc", fg="#334155", relief="flat", padx=5, pady=1, cursor="hand2", command=lambda: self.apply_range_days(2))
        btn_2d.pack(side=tk.LEFT, padx=2)

        btn_3d = tk.Button(r_presets, text="3 Days", font=("Segoe UI", 7, "bold"), bg="#f8fafc", fg="#334155", relief="flat", padx=5, pady=1, cursor="hand2", command=lambda: self.apply_range_days(3))
        btn_3d.pack(side=tk.LEFT, padx=2)

        btn_5d = tk.Button(r_presets, text="5 Days", font=("Segoe UI", 7, "bold"), bg="#f8fafc", fg="#334155", relief="flat", padx=5, pady=1, cursor="hand2", command=lambda: self.apply_range_days(5))
        btn_5d.pack(side=tk.LEFT, padx=2)

        self.var_skip_weekends = tk.BooleanVar(value=True)
        chk_skip = tk.Checkbutton(self.f_range_date, text="☑️ Skip Weekends (Sundays) & Official Public Holidays in range", variable=self.var_skip_weekends, font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#0369a1", command=self.update_preview)
        chk_skip.pack(anchor="w", pady=(4, 0))

        # 3. Leave Type & Hours Card
        details_box = tk.LabelFrame(main_f, text="  3. Leave Type & Hours  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        details_box.pack(fill=tk.X, pady=(0, 6))

        row_type = tk.Frame(details_box, bg="#ffffff")
        row_type.pack(fill=tk.X)

        f_lt = tk.Frame(row_type, bg="#ffffff")
        f_lt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(f_lt, text="Leave Category / Type:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w", pady=(0, 2))

        self.leave_types = [
            "Casual Leave (CL)",
            "Sick Leave (SL)",
            "Paid Leave (PL)",
            "Half Day Leave (First Half - 4.0 hrs)",
            "Half Day Leave (Second Half - 4.0 hrs)",
            "Unpaid Leave / LOP",
            "Comp Off",
            "Work From Home / Remote",
            "Custom Leave"
        ]
        self.combo_leave_type = ttk.Combobox(f_lt, values=self.leave_types, state="readonly", font=("Segoe UI", 9))
        self.combo_leave_type.pack(fill=tk.X)
        self.combo_leave_type.set("Casual Leave (CL)")
        self.combo_leave_type.bind("<<ComboboxSelected>>", self.on_leave_type_selected)

        f_lh = tk.Frame(row_type, bg="#ffffff")
        f_lh.pack(side=tk.LEFT, padx=(0, 0))
        tk.Label(f_lh, text="Logged Hours:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w", pady=(0, 2))
        self.entry_hours = tk.Entry(f_lh, font=("Segoe UI", 9), width=10, relief="solid", bd=1)
        self.entry_hours.pack(ipady=2)
        self.entry_hours.insert(0, "0.0")

        # 4. Reason / Notes
        reason_box = tk.LabelFrame(main_f, text="  4. Reason / Notes (Optional)  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        reason_box.pack(fill=tk.X, pady=(0, 6))

        self.entry_reason = tk.Entry(reason_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_reason.pack(fill=tk.X, ipady=2, pady=(0, 3))
        self.entry_reason.insert(0, "Personal Work")

        # Reason quick pill buttons
        pills_row = tk.Frame(reason_box, bg="#ffffff")
        pills_row.pack(fill=tk.X)
        quick_reasons = ["Personal Work", "Not Feeling Well", "Family Event", "Doctor Appointment", "Out of Town"]
        for qr in quick_reasons:
            btn_qr = tk.Button(pills_row, text=qr, font=("Segoe UI", 7), bg="#f8fafc", fg="#475569", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda r=qr: self.set_reason(r))
            btn_qr.pack(side=tk.LEFT, padx=(0, 4))

        # 5. Live Summary Preview Card
        self.prev_box = tk.LabelFrame(main_f, text="  5. Dates Preview  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#f8fafc", padx=10, pady=4, bd=1, relief="solid")
        self.prev_box.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        self.lbl_preview = tk.Label(self.prev_box, text="", font=("Segoe UI", 8), bg="#f8fafc", fg="#334155", justify="left", anchor="nw")
        self.lbl_preview.pack(fill=tk.BOTH, expand=True)

    def on_mode_change(self):
        if self.var_mode.get() == "single":
            self.f_range_date.pack_forget()
            self.f_single_date.pack(fill=tk.X)
        else:
            self.f_single_date.pack_forget()
            self.f_range_date.pack(fill=tk.X)
        self.update_preview()

    def set_single_date(self, d_str):
        self.entry_single_date.delete(0, tk.END)
        self.entry_single_date.insert(0, d_str)
        self.update_preview()

    def apply_range_days(self, num_days):
        f_d = self.entry_from_date.get().strip()
        try:
            d_start = datetime.datetime.strptime(f_d, "%Y-%m-%d").date()
        except Exception:
            d_start = datetime.date.today()
            self.entry_from_date.delete(0, tk.END)
            self.entry_from_date.insert(0, d_start.strftime("%Y-%m-%d"))

        d_end = d_start + datetime.timedelta(days=num_days - 1)
        self.entry_to_date.delete(0, tk.END)
        self.entry_to_date.insert(0, d_end.strftime("%Y-%m-%d"))
        self.update_preview()

    def on_leave_type_selected(self, event=None):
        lt = self.combo_leave_type.get()
        if "Half Day" in lt:
            self.entry_hours.delete(0, tk.END)
            self.entry_hours.insert(0, "4.0")
        elif not self.entry_hours.get().strip() or self.entry_hours.get().strip() == "4.0":
            self.entry_hours.delete(0, tk.END)
            self.entry_hours.insert(0, "0.0")

    def set_reason(self, text):
        self.entry_reason.delete(0, tk.END)
        self.entry_reason.insert(0, text)

    def get_calculated_dates(self):
        """Returns (list_of_valid_dates, list_of_skipped_dates_with_reasons)."""
        mode = self.var_mode.get()
        valid_dates = []
        skipped_dates = []

        if mode == "single":
            raw_d = self.entry_single_date.get().strip()
            try:
                dt_obj = datetime.datetime.strptime(raw_d, "%Y-%m-%d").date()
                valid_dates.append(dt_obj)
            except Exception:
                pass
            return valid_dates, skipped_dates

        # Range mode
        raw_from = self.entry_from_date.get().strip()
        raw_to = self.entry_to_date.get().strip()
        try:
            d_start = datetime.datetime.strptime(raw_from, "%Y-%m-%d").date()
            d_end = datetime.datetime.strptime(raw_to, "%Y-%m-%d").date()
        except Exception:
            return valid_dates, skipped_dates

        if d_start > d_end:
            d_start, d_end = d_end, d_start

        skip_offs = self.var_skip_weekends.get()
        curr = d_start
        while curr <= d_end:
            d_str = curr.strftime("%Y-%m-%d")
            if skip_offs:
                hol = is_date_holiday(d_str)
                if hol:
                    skipped_dates.append(f"{d_str} (Holiday: {hol})")
                    curr += datetime.timedelta(days=1)
                    continue
                off = is_date_weekly_off(d_str, self.settings)
                if off:
                    skipped_dates.append(f"{d_str} (Weekly Off: {off})")
                    curr += datetime.timedelta(days=1)
                    continue
            valid_dates.append(curr)
            curr += datetime.timedelta(days=1)

        return valid_dates, skipped_dates

    def update_preview(self):
        valid_dates, skipped_dates = self.get_calculated_dates()
        if not valid_dates:
            self.lbl_preview.config(text="⚠️ Please enter valid date(s) in YYYY-MM-DD format.", fg="#dc2626")
            return

        date_strs = [d.strftime("%Y-%m-%d (%a)") for d in valid_dates]
        preview_lines = []
        preview_lines.append(f"🗓️ Total Leave Days to Mark: {len(valid_dates)}")
        
        # Target months
        target_months = sorted(list({get_month_sheet_name(d.strftime("%Y-%m-%d")) for d in valid_dates}))
        preview_lines.append(f"📁 Target Month Sheet(s): {', '.join(target_months)}")
        
        if len(date_strs) <= 4:
            preview_lines.append(f"📅 Dates: {', '.join(date_strs)}")
        else:
            preview_lines.append(f"📅 Dates: {date_strs[0]}  →  {date_strs[-1]} ({len(date_strs)} days)")

        if skipped_dates:
            preview_lines.append(f"⏭️ Skipped Off Days: {len(skipped_dates)} ({', '.join(skipped_dates[:3])}{'...' if len(skipped_dates) > 3 else ''})")

        self.lbl_preview.config(text="\n".join(preview_lines), fg="#1e293b")

    def submit_leave(self):
        valid_dates, _ = self.get_calculated_dates()
        if not valid_dates:
            messagebox.showwarning("No Valid Dates", "Please specify valid leave date(s).")
            return

        leave_type = self.combo_leave_type.get().strip() or "Casual Leave (CL)"
        hours_val = self.entry_hours.get().strip() or "0.0"
        reason = self.entry_reason.get().strip() or leave_type
        desc = f"On Leave: {leave_type}" if reason == leave_type else f"On Leave: {leave_type} - {reason}"

        try:
            wb = load_workbook(FILE)
            ensure_excel_schema(wb)
        except PermissionError:
            messagebox.showerror("Permission Error", f"Cannot access '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
            return
        except Exception:
            wb = Workbook()

        affected_sheets = set()
        saved_count = 0
        now_dt = datetime.datetime.now()

        for i, dt_obj in enumerate(valid_dates):
            d_str = dt_obj.strftime("%Y-%m-%d")
            s_name = get_month_sheet_name(d_str)
            ws = get_or_create_sheet(wb, s_name)
            affected_sheets.add(s_name)

            # Check if this date has a redundant 0-hour weekly off placeholder: if so, remove it!
            rows_to_keep = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not any(row):
                    continue
                r_date = format_date_only(row[1])
                r_st = str(row[6] or "").strip().lower()
                r_pj = str(row[2] or "").strip().lower()
                h_val = str(row[5] or "").strip()
                is_zero = (h_val in ("", "0", "0.0", "-"))

                # Drop 0-hr weekly off placeholder for this date
                if r_date == d_str and ("weekly off" in r_st or "weekly off" in r_pj) and is_zero:
                    continue
                
                # Replace any previous leave record for this exact date
                if r_date == d_str and ("leave" in r_st or "leave" in r_pj):
                    continue

                rows_to_keep.append(list(row))

            if ws.max_row >= 2:
                ws.delete_rows(2, ws.max_row - 1)
            for r in rows_to_keep:
                while len(r) < len(HEADERS):
                    r.append("")
                ws.append(r)

            ts = (now_dt + datetime.timedelta(seconds=i)).strftime("%y%m%d-%H%M%S")
            rec_id = f"LV-{ts}"
            now_str = (now_dt + datetime.timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")

            ws.append([rec_id, d_str, "Leave", leave_type, desc, hours_val, "Leave", reason, 
                       "-", "-", "-", "-", now_str])
            saved_count += 1

        # Auto-sort affected sheets date-wise
        asc = (self.settings.get("date_sort_order", "asc") == "asc")
        for s_name in affected_sheets:
            sort_sheet_records_by_date(wb[s_name], ascending=asc)

        try:
            wb.save(FILE)
        except PermissionError:
            messagebox.showerror("Permission Error", f"Cannot save '{FILE}' because it is open in Excel.\nPlease close Excel and try again.")
            return

        trigger_google_sheet_auto_sync(affected_sheets)

        if self.on_success_callback:
            self.on_success_callback()
        elif hasattr(self.parent, 'refresh_all'):
            self.parent.refresh_all()

        messagebox.showinfo("Leave Recorded", f"✅ Successfully recorded {saved_count} leave day(s) into Excel!\nAll records have been arranged chronologically date-wise.")
        self.destroy()

# ---------- Edit Task Modal Dialog for Bulk Preview ----------
class EditTaskPreviewDialog(tk.Toplevel):
    def __init__(self, parent, task_data, on_save_callback):
        super().__init__(parent)
        self.title("✏️ Edit Task Details")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=540, default_h=480, min_w=460, min_h=400)

        self.task_data = task_data
        self.on_save_callback = on_save_callback

        self.create_widgets()

    def create_widgets(self):
        header = tk.Frame(self, bg="#1e293b", height=45)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text="✏️ Edit Task Details & Hours", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=15, pady=10)

        main_f = tk.Frame(self, bg="#ffffff", padx=15, pady=12, bd=1, relief="solid")
        main_f.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Date & Project (if provided in task_data)
        if "date" in self.task_data or "project" in self.task_data:
            row0 = tk.Frame(main_f, bg="#ffffff")
            row0.pack(fill=tk.X, pady=(0, 8))

            f_d = tk.Frame(row0, bg="#ffffff")
            f_d.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            tk.Label(f_d, text="Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
            self.entry_date = tk.Entry(f_d, font=("Segoe UI", 9), relief="solid", bd=1)
            self.entry_date.pack(fill=tk.X, ipady=2)
            self.entry_date.insert(0, str(self.task_data.get("date", "")))

            f_p = tk.Frame(row0, bg="#ffffff")
            f_p.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            tk.Label(f_p, text="Project Name:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
            self.entry_proj = tk.Entry(f_p, font=("Segoe UI", 9), relief="solid", bd=1)
            self.entry_proj.pack(fill=tk.X, ipady=2)
            self.entry_proj.insert(0, str(self.task_data.get("project", "")))

        # Title
        tk.Label(main_f, text="Task Title*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
        self.entry_title = tk.Entry(main_f, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_title.pack(fill=tk.X, pady=(0, 8), ipady=2)
        self.entry_title.insert(0, self.task_data.get("title", ""))

        # Row with Hours and Status
        row2 = tk.Frame(main_f, bg="#ffffff")
        row2.pack(fill=tk.X, pady=(0, 8))

        f_hrs = tk.Frame(row2, bg="#ffffff")
        f_hrs.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Label(f_hrs, text="Hours (Optional):", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
        self.entry_hrs = tk.Entry(f_hrs, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_hrs.pack(fill=tk.X, ipady=2)
        self.entry_hrs.insert(0, self.task_data.get("hours", ""))

        f_st = tk.Frame(row2, bg="#ffffff")
        f_st.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        tk.Label(f_st, text="Status:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
        self.combo_st = ttk.Combobox(f_st, values=["Completed", "In Progress", "Pending", "Under Review", "Blocked", "Leave", "Weekly Off", "Holiday"], state="readonly", font=("Segoe UI", 9))
        self.combo_st.pack(fill=tk.X)
        self.combo_st.set(self.task_data.get("status", "Completed"))

        # Description
        tk.Label(main_f, text="Description:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
        self.text_desc = tk.Text(main_f, font=("Segoe UI", 9), height=4, relief="solid", bd=1, wrap=tk.WORD)
        self.text_desc.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.text_desc.insert("1.0", self.task_data.get("desc", ""))

        # Remarks
        tk.Label(main_f, text="Remarks / Docs:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w", pady=(0, 2))
        self.entry_remarks = tk.Entry(main_f, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_remarks.pack(fill=tk.X, pady=(0, 4), ipady=2)
        self.entry_remarks.insert(0, self.task_data.get("remarks", ""))

        # Bottom Bar
        bottom = tk.Frame(self, bg="#f1f5f9", padx=12, pady=8)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        btn_save = tk.Button(bottom, text="💾 Update Task", font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white", relief="flat", padx=12, pady=4, cursor="hand2", command=self.save)
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(bottom, text="Cancel", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=10, pady=4, cursor="hand2", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=4)

    def save(self):
        title = self.entry_title.get().strip()
        if not title:
            messagebox.showwarning("Validation Error", "Task Title cannot be empty.")
            return

        hrs = self.entry_hrs.get().strip()
        if hrs:
            try:
                v = float(hrs)
                hrs = f"{v:.2f}".rstrip('0').rstrip('.') if '.' in f"{v:.2f}" else f"{v}"
                if '.' not in hrs:
                    hrs += ".0"
            except ValueError:
                messagebox.showerror("Invalid Hours", "Hours must be a valid number or left blank.")
                return

        updated_data = dict(self.task_data)
        updated_data.update({
            "title": title,
            "hours": hrs,
            "status": self.combo_st.get(),
            "desc": self.text_desc.get("1.0", tk.END).strip(),
            "remarks": self.entry_remarks.get().strip()
        })
        if hasattr(self, 'entry_date'):
            d_val = format_date_only(self.entry_date.get().strip())
            if d_val:
                updated_data["date"] = d_val
        if hasattr(self, 'entry_proj'):
            updated_data["project"] = self.entry_proj.get().strip() or "General Work"

        self.on_save_callback(updated_data)
        self.destroy()

# ---------- Bulk Import Dialog Window ----------
class BulkImportDialog(tk.Toplevel):
    def __init__(self, parent, on_import_success):
        super().__init__(parent)
        self.title("📋 Bulk Paste / Markdown Work Log & Total Hours Splitter")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=980, default_h=700, min_w=840, min_h=560)

        self.on_import_success = on_import_success
        self.parsed_tasks = []

        self.create_widgets()

    def create_widgets(self):
        header = tk.Frame(self, bg="#1e293b", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(header, text="📋 Bulk Paste & Total Hours Auto-Split Importer", font=("Segoe UI", 12, "bold"), fg="white", bg="#1e293b").pack(side=tk.LEFT, padx=15, pady=12)
        tk.Label(header, text="Paste raw text/markdown • Split total hours or enter per task • Hours is optional", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b").pack(side=tk.LEFT, padx=5, pady=12)

        main_frame = tk.Frame(self, bg="#f8fafc", padx=15, pady=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="1. Paste Your Work Log / Markdown Below:", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#1e293b").pack(anchor="w", pady=(0, 4))
        
        self.text_input = tk.Text(main_frame, font=("Consolas", 9), height=7, relief="solid", bd=1, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=False, pady=(0, 6))

        btn_bar = tk.Frame(main_frame, bg="#f8fafc")
        btn_bar.pack(fill=tk.X, pady=(0, 8))

        btn_parse = tk.Button(btn_bar, text="⚡ Parse & Preview Tasks", font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=14, pady=5, cursor="hand2", command=self.do_parse)
        btn_parse.pack(side=tk.LEFT, padx=(0, 8))

        btn_sample = tk.Button(btn_bar, text="💡 Load Sample Log", font=("Segoe UI", 9), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=10, pady=5, cursor="hand2", command=self.load_sample_template)
        btn_sample.pack(side=tk.LEFT, padx=(0, 8))

        btn_clear = tk.Button(btn_bar, text="🧹 Clear Text", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=10, pady=5, cursor="hand2", command=lambda: self.text_input.delete("1.0", tk.END))
        btn_clear.pack(side=tk.LEFT, padx=(0, 10))

        btn_jump_excel = tk.Button(btn_bar, text="📂 Or Import from Excel (.xlsx) / CSV", font=("Segoe UI", 9, "bold"), bg="#d1fae5", fg="#065f46", relief="flat", padx=12, pady=5, cursor="hand2", command=self.open_excel_file_importer)
        btn_jump_excel.pack(side=tk.RIGHT)

        # Config & Hours Distribution Settings
        cfg_frame = tk.LabelFrame(main_frame, text=" 2. Log Details, Shift Timings & Hours Distribution ", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        cfg_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 0: Date and Project
        f_row0 = tk.Frame(cfg_frame, bg="#ffffff")
        f_row0.pack(fill=tk.X, pady=(2, 3))

        tk.Label(f_row0, text="Log Date:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_date = tk.Entry(f_row0, font=("Segoe UI", 9), width=13, relief="solid", bd=1)
        self.entry_date.pack(side=tk.LEFT, padx=(0, 15), ipady=1)
        self.entry_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))

        tk.Label(f_row0, text="Project Name:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_proj = tk.Entry(f_row0, font=("Segoe UI", 9), width=30, relief="solid", bd=1)
        self.entry_proj.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        self.entry_proj.insert(0, "Afro Cargo & Logistics")

        # Row 1: Shift Timings (Login / Logout)
        f_row_shift = tk.Frame(cfg_frame, bg="#ffffff")
        f_row_shift.pack(fill=tk.X, pady=(2, 3))

        init_timings = get_daily_timings(datetime.datetime.now().strftime("%Y-%m-%d"))

        tk.Label(f_row_shift, text="Login Time:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_bulk_login = tk.Entry(f_row_shift, font=("Segoe UI", 9), width=11, relief="solid", bd=1)
        self.entry_bulk_login.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_bulk_login.insert(0, init_timings.get("login", "10:00 AM"))

        btn_bulk_in_now = tk.Button(f_row_shift, text="Now", font=("Segoe UI", 7, "bold"), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_entry_val(self.entry_bulk_login, format_current_time_str()))
        btn_bulk_in_now.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(f_row_shift, text="Logout Time:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_bulk_logout = tk.Entry(f_row_shift, font=("Segoe UI", 9), width=11, relief="solid", bd=1)
        self.entry_bulk_logout.pack(side=tk.LEFT, padx=(0, 4), ipady=1)
        self.entry_bulk_logout.insert(0, init_timings.get("logout", "07:30 PM"))

        btn_bulk_out_now = tk.Button(f_row_shift, text="Now", font=("Segoe UI", 7, "bold"), bg="#f1f5f9", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_entry_val(self.entry_bulk_logout, format_current_time_str()))
        btn_bulk_out_now.pack(side=tk.LEFT, padx=(0, 15))

        btn_calc_shift = tk.Button(f_row_shift, text="⚡ Calc Shift Working Hours", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=8, pady=2, cursor="hand2", command=self.calc_net_hours_from_shift)
        btn_calc_shift.pack(side=tk.LEFT)

        # Row 2: Lunch & Tea Breaks
        f_row_breaks = tk.Frame(cfg_frame, bg="#ffffff")
        f_row_breaks.pack(fill=tk.X, pady=(2, 3))

        self.var_bulk_lunch = tk.BooleanVar(value=True)
        self.chk_bulk_lunch = tk.Checkbutton(f_row_breaks, text="Lunch Break:", variable=self.var_bulk_lunch, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155")
        self.chk_bulk_lunch.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bulk_lunch = tk.Entry(f_row_breaks, font=("Segoe UI", 9), width=22, relief="solid", bd=1)
        self.entry_bulk_lunch.pack(side=tk.LEFT, padx=(0, 15), ipady=1)
        self.entry_bulk_lunch.insert(0, init_timings.get("lunch", "01:00 PM - 02:00 PM"))

        self.var_bulk_tea = tk.BooleanVar(value=True)
        self.chk_bulk_tea = tk.Checkbutton(f_row_breaks, text="Tea Break:", variable=self.var_bulk_tea, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155")
        self.chk_bulk_tea.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bulk_tea = tk.Entry(f_row_breaks, font=("Segoe UI", 9), width=22, relief="solid", bd=1)
        self.entry_bulk_tea.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        self.entry_bulk_tea.insert(0, init_timings.get("tea", "04:30 PM - 04:45 PM"))

        # Row 3: Total Hours Split vs Per-Task Hours
        f_row1 = tk.Frame(cfg_frame, bg="#ffffff")
        f_row1.pack(fill=tk.X, pady=(3, 2))

        tk.Label(f_row1, text="Total Hours to Split:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e40af").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_total_hrs = tk.Entry(f_row1, font=("Segoe UI", 9, "bold"), width=7, relief="solid", bd=1, fg="#1e40af")
        self.entry_total_hrs.pack(side=tk.LEFT, padx=(0, 4), ipady=1)

        btn_split = tk.Button(f_row1, text="➗ Split Total Hours", font=("Segoe UI", 8, "bold"), bg="#dbeafe", fg="#1d4ed8", activebackground="#bfdbfe", relief="flat", padx=8, pady=2, cursor="hand2", command=self.split_total_hours)
        btn_split.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(f_row1, text="Or Per-Task Hours (Optional):", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_hrs = tk.Entry(f_row1, font=("Segoe UI", 9), width=6, relief="solid", bd=1)
        self.entry_hrs.pack(side=tk.LEFT, padx=(0, 4), ipady=1)

        btn_apply_all = tk.Button(f_row1, text="Apply to All", font=("Segoe UI", 8), bg="#f1f5f9", fg="#334155", relief="flat", padx=6, pady=2, cursor="hand2", command=self.apply_per_task_hours)
        btn_apply_all.pack(side=tk.LEFT, padx=(0, 10))

        btn_clear_hrs = tk.Button(f_row1, text="🧹 Clear All Hours", font=("Segoe UI", 8), bg="#fee2e2", fg="#991b1b", relief="flat", padx=6, pady=2, cursor="hand2", command=self.clear_all_hours)
        btn_clear_hrs.pack(side=tk.LEFT)

        # Preview Table
        preview_header = tk.Frame(main_frame, bg="#f8fafc")
        preview_header.pack(fill=tk.X, pady=(0, 4))
        tk.Label(preview_header, text="3. Preview of Tasks to be Saved into Month Tab:", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#1e293b").pack(side=tk.LEFT)
        tk.Label(preview_header, text="(Double-click any row to edit task details & hours)", font=("Segoe UI", 8, "italic"), bg="#f8fafc", fg="#64748b").pack(side=tk.LEFT, padx=10)

        table_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="solid")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        cols = ("No", "Task Title", "Status", "Hours", "Description", "Remarks")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=6)
        self.tree.heading("No", text="#")
        self.tree.column("No", width=35, anchor="center")

        self.tree.heading("Task Title", text="Task Summary / Title")
        self.tree.column("Task Title", width=240, anchor="w")

        self.tree.heading("Status", text="Status")
        self.tree.column("Status", width=95, anchor="center")

        self.tree.heading("Hours", text="Hours (hrs)")
        self.tree.column("Hours", width=80, anchor="center")

        self.tree.heading("Description", text="Description")
        self.tree.column("Description", width=250, anchor="w")

        self.tree.heading("Remarks", text="Remarks")
        self.tree.column("Remarks", width=140, anchor="w")

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Action bar under table
        tbl_actions = tk.Frame(main_frame, bg="#f8fafc")
        tbl_actions.pack(fill=tk.X, pady=(0, 6))

        btn_edit_task = tk.Button(tbl_actions, text="✏️ Edit Selected Task", font=("Segoe UI", 8, "bold"), bg="#edf2f7", fg="#1e293b", relief="flat", padx=8, pady=3, cursor="hand2", command=self.edit_selected_task)
        btn_edit_task.pack(side=tk.LEFT, padx=(0, 6))

        btn_del_task = tk.Button(tbl_actions, text="🗑️ Remove Task", font=("Segoe UI", 8), bg="#fee2e2", fg="#991b1b", relief="flat", padx=8, pady=3, cursor="hand2", command=self.delete_selected_task)
        btn_del_task.pack(side=tk.LEFT, padx=(0, 6))

        # Bottom Bar
        bottom_bar = tk.Frame(self, bg="#f1f5f9", padx=15, pady=8)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_summary = tk.Label(bottom_bar, text="Ready. Paste your text and click 'Parse & Preview'.", font=("Segoe UI", 9), fg="#475569", bg="#f1f5f9")
        self.lbl_summary.pack(side=tk.LEFT)

        self.btn_import = tk.Button(bottom_bar, text="🚀 Import All Tasks to Excel Month Tab", font=("Segoe UI", 10, "bold"), bg="#16a34a", fg="white", activebackground="#15803d", activeforeground="white", relief="flat", padx=15, pady=6, cursor="hand2", command=self.do_import, state=tk.DISABLED)
        self.btn_import.pack(side=tk.RIGHT)

    def set_entry_val(self, entry_widget, val):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, val)

    def calc_net_hours_from_shift(self):
        login_v = self.entry_bulk_login.get().strip()
        logout_v = self.entry_bulk_logout.get().strip()
        lunch_v = self.entry_bulk_lunch.get().strip() if self.var_bulk_lunch.get() else ""
        tea_v = self.entry_bulk_tea.get().strip() if self.var_bulk_tea.get() else ""
        net_h, net_str, span_h, _, _ = calculate_net_working_hours(
            login_v, logout_v, lunch_v, tea_v,
            lunch_taken=bool(lunch_v), tea_taken=bool(tea_v)
        )
        if net_h > 0:
            self.entry_total_hrs.delete(0, tk.END)
            self.entry_total_hrs.insert(0, net_str)
            self.lbl_summary.config(text=f"⏱️ Calculated Net Working Hours: {net_str} hrs (Shift span: {span_h}h). Click 'Split Total Hours' to distribute.", fg="#2563eb")
        else:
            messagebox.showwarning("Incomplete Timings", "Please enter valid Login and Logout times (e.g., 10:00 AM and 07:30 PM).")

    def load_sample_template(self):
        sample_txt = (
            f"#### Today's Work Log - {datetime.datetime.now().strftime('%d-%b-%Y')}\n"
            "**Member:** Developer\n"
            "**Project:** Afro Cargo & Logistics\n"
            "**Login Time:** 10:00 AM | **Logout Time:** 07:30 PM\n"
            "**Total Hours:** 8.0 hrs\n"
            "**Lunch Break:** 01:00 PM - 02:00 PM\n"
            "**Tea Break:** 04:30 PM - 04:45 PM\n\n"
            "### Completed Tasks\n"
            "1. **Invoice PDF Generation** (2.5h):\n"
            "   - Implemented automated PDF template with customer branding\n"
            "   - Added digital signature support\n"
            "2. **Payment Gateway Webhook**:\n"
            "   - Handled callback verification and auto-status updates\n"
            "3. **Database Index Optimization**:\n"
            "   - Optimized queries on transactions table\n\n"
            "### In Progress Tasks\n"
            "4. **Driver Dispatch Mobile API** [In Progress]:\n"
            "   - Working on GPS tracking endpoint\n"
        )
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", sample_txt)

    def do_parse(self):
        raw_text = self.text_input.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Empty Input", "Please paste your work log text first.")
            return

        found_date, proj_name, tasks, detected_total_hrs, detected_timings = parse_bulk_markdown(raw_text)

        if not tasks:
            messagebox.showwarning("No Tasks Found", "Could not parse any tasks from the text. Make sure tasks are formatted with numbers (1. Task) or bullet points.")
            return

        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, found_date)

        self.entry_proj.delete(0, tk.END)
        self.entry_proj.insert(0, proj_name)

        # Populate shift and break timings if detected
        if detected_timings.get("login"):
            self.set_entry_val(self.entry_bulk_login, detected_timings["login"])
        if detected_timings.get("logout"):
            self.set_entry_val(self.entry_bulk_logout, detected_timings["logout"])
        if detected_timings.get("lunch"):
            self.var_bulk_lunch.set(True)
            self.set_entry_val(self.entry_bulk_lunch, detected_timings["lunch"])
        if detected_timings.get("tea"):
            self.var_bulk_tea.set(True)
            self.set_entry_val(self.entry_bulk_tea, detected_timings["tea"])

        self.entry_total_hrs.delete(0, tk.END)
        if detected_total_hrs:
            self.entry_total_hrs.insert(0, detected_total_hrs)
        else:
            tot = sum([float(t["hours"]) for t in tasks if t.get("hours") and str(t["hours"]).replace('.', '', 1).isdigit()])
            if tot > 0:
                tot_str = f"{tot:.2f}".rstrip('0').rstrip('.') if '.' in f"{tot:.2f}" else f"{tot}"
                if '.' not in tot_str:
                    tot_str += ".0"
                self.entry_total_hrs.insert(0, tot_str)

        self.parsed_tasks = tasks
        self.refresh_preview_tree()

        target_month = get_month_sheet_name(found_date)
        total_hrs_msg = f" (Total Hours: {self.entry_total_hrs.get().strip()} hrs)" if self.entry_total_hrs.get().strip() else " (Hours is optional)"
        self.lbl_summary.config(text=f"✅ Successfully parsed {len(tasks)} tasks{total_hrs_msg}! Target Month Sheet: '{target_month}'", fg="#16a34a")
        self.btn_import.config(state=tk.NORMAL, text=f"🚀 Import All {len(tasks)} Tasks to '{target_month}' Tab")

    def split_total_hours(self):
        if not self.parsed_tasks:
            messagebox.showwarning("No Tasks", "Please parse your work log first.")
            return
        
        tot_val = self.entry_total_hrs.get().strip()
        if not tot_val:
            messagebox.showwarning("Enter Total Hours", "Please enter a total hours number (e.g. 8.0) to split.")
            self.entry_total_hrs.focus_set()
            return
        
        try:
            total_float = float(tot_val)
            if total_float <= 0:
                messagebox.showerror("Invalid Total Hours", "Total Hours must be greater than 0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Total Hours", "Please enter a valid numeric value for Total Hours (e.g. 8, 7.5).")
            return
        
        num_tasks = len(self.parsed_tasks)
        split_val = round(total_float / num_tasks, 2)
        split_str = f"{split_val:.2f}".rstrip('0').rstrip('.') if '.' in f"{split_val:.2f}" else f"{split_val}"
        if '.' not in split_str:
            split_str += ".0"
        
        for t in self.parsed_tasks:
            t["hours"] = split_str
        
        self.refresh_preview_tree()
        self.lbl_summary.config(text=f"➗ Split {total_float:.1f} total hours evenly among {num_tasks} tasks ({split_str} hrs each)!", fg="#2563eb")

    def apply_per_task_hours(self):
        if not self.parsed_tasks:
            messagebox.showwarning("No Tasks", "Please parse your work log first.")
            return
        
        hrs_val = self.entry_hrs.get().strip()
        if hrs_val:
            try:
                val = float(hrs_val)
                hrs_str = f"{val:.2f}".rstrip('0').rstrip('.') if '.' in f"{val:.2f}" else f"{val}"
                if '.' not in hrs_str:
                    hrs_str += ".0"
            except ValueError:
                messagebox.showerror("Invalid Hours", "Please enter a valid numeric value for Hours/Task.")
                return
        else:
            hrs_str = ""

        for t in self.parsed_tasks:
            t["hours"] = hrs_str

        # Calculate sum and update entry_total_hrs
        if hrs_str:
            tot = float(hrs_str) * len(self.parsed_tasks)
            tot_str = f"{tot:.2f}".rstrip('0').rstrip('.') if '.' in f"{tot:.2f}" else f"{tot}"
            if '.' not in tot_str:
                tot_str += ".0"
            self.entry_total_hrs.delete(0, tk.END)
            self.entry_total_hrs.insert(0, tot_str)
        else:
            self.entry_total_hrs.delete(0, tk.END)

        self.refresh_preview_tree()
        self.lbl_summary.config(text=f"✅ Set {hrs_str or 'optional'} hours for all {len(self.parsed_tasks)} tasks.", fg="#16a34a")

    def clear_all_hours(self):
        if not self.parsed_tasks:
            return
        for t in self.parsed_tasks:
            t["hours"] = ""
        self.entry_total_hrs.delete(0, tk.END)
        self.entry_hrs.delete(0, tk.END)
        self.refresh_preview_tree()
        self.lbl_summary.config(text="🧹 Cleared hours from all tasks (Hours spent is optional).", fg="#475569")

    def refresh_preview_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for i, t in enumerate(self.parsed_tasks, start=1):
            h_display = t.get("hours", "")
            if not h_display:
                h_display = "-"
            self.tree.insert("", tk.END, values=(
                i,
                t.get("title", ""),
                t.get("status", "Completed"),
                h_display,
                t.get("desc", "").replace("\n", " "),
                t.get("remarks", "")
            ))

    def on_tree_double_click(self, event):
        self.edit_selected_task()

    def edit_selected_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a task from the preview table to edit.")
            return

        item = self.tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.parsed_tasks):
            task = self.parsed_tasks[idx]
            def save_cb(updated):
                self.parsed_tasks[idx] = updated
                tot = sum([float(t["hours"]) for t in self.parsed_tasks if t.get("hours") and str(t["hours"]).replace('.', '', 1).isdigit()])
                if tot > 0:
                    tot_str = f"{tot:.2f}".rstrip('0').rstrip('.') if '.' in f"{tot:.2f}" else f"{tot}"
                    if '.' not in tot_str:
                        tot_str += ".0"
                    self.entry_total_hrs.delete(0, tk.END)
                    self.entry_total_hrs.insert(0, tot_str)
                self.refresh_preview_tree()
            EditTaskPreviewDialog(self, task, save_cb)

    def delete_selected_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a task from the preview table to remove.")
            return

        item = self.tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.parsed_tasks):
            del self.parsed_tasks[idx]
            self.refresh_preview_tree()
            if self.parsed_tasks:
                self.btn_import.config(state=tk.NORMAL, text=f"🚀 Import All {len(self.parsed_tasks)} Tasks")
            else:
                self.btn_import.config(state=tk.DISABLED, text="🚀 Import All Tasks")

    def do_import(self):
        if not self.parsed_tasks:
            messagebox.showwarning("No Tasks", "Please parse your tasks first.")
            return

        date_val = self.entry_date.get().strip()
        proj_val = self.entry_proj.get().strip()

        try:
            datetime.datetime.strptime(date_val, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Date must be in format YYYY-MM-DD (e.g. 2026-10-06).")
            return

        login_v = self.entry_bulk_login.get().strip()
        logout_v = self.entry_bulk_logout.get().strip()
        lunch_v = self.entry_bulk_lunch.get().strip() if self.var_bulk_lunch.get() else ""
        tea_v = self.entry_bulk_tea.get().strip() if self.var_bulk_tea.get() else ""

        saved_count, sheet_name = save_bulk_work_updates(
            date_val, proj_val, self.parsed_tasks,
            batch_login=login_v, batch_logout=logout_v, batch_lunch=lunch_v, batch_tea=tea_v
        )

        if saved_count > 0:
            settings = load_settings()
            timings_obj = {
                "login": login_v,
                "logout": logout_v,
                "lunch": lunch_v,
                "tea": tea_v,
                "lunch_taken": bool(lunch_v),
                "tea_taken": bool(tea_v)
            }
            save_daily_timings(date_val, timings_obj)
            formatted_team_md = generate_team_markdown(
                date_val, proj_val, self.parsed_tasks,
                settings.get("user_name", "Developer"), timings=timings_obj
            )
            
            if settings.get("auto_copy_on_save", True):
                self.clipboard_clear()
                self.clipboard_append(formatted_team_md)

            self.on_import_success(sheet_name, date_val, proj_val, self.parsed_tasks)
            self.destroy()

    def open_excel_file_importer(self):
        cb = self.on_import_success
        p = self.master
        self.destroy()
        ExcelBulkImportDialog(p, on_import_success=cb)

# ==============================================================================
# ---------- Bulk Import from Excel (.xlsx) / CSV Dialog & Engine ----------
# ==============================================================================

EXCEL_COLUMN_PATTERNS = {
    "date": [r"^date$", r"^work[ _]?date$", r"^log[ _]?date$", r"^entry[ _]?date$", r"^day$", r"^dt$"],
    "project": [r"^project([ _]?name)?$", r"^client([ _]?name)?$", r"^account$", r"^module$", r"^proj$"],
    "title": [r"^task([ _]?(title|name))?$", r"^title$", r"^summary$", r"^activity$", r"^item$", r"^headline$", r"^subject$"],
    "desc": [r"^desc(ription)?$", r"^details?$", r"^work[ _]?done$", r"^notes?$", r"^work[ _]?summary$"],
    "hours": [r"^hours?([ _]?spent)?$", r"^duration$", r"^time([ _]?spent)?$", r"^hrs$", r"^effort$", r"^total[ _]?hours?$"],
    "status": [r"^status$", r"^state$", r"^progress$"],
    "remarks": [r"^remarks?$", r"^comments?$", r"^notes?$"],
    "login": [r"^login([ _]?time)?$", r"^in([ _]?time)?$", r"^start([ _]?time)?$", r"^punch[ _]?in$"],
    "logout": [r"^logout([ _]?time)?$", r"^out([ _]?time)?$", r"^end([ _]?time)?$", r"^punch[ _]?out$"],
    "lunch": [r"^lunch([ _]?(break|time))?$"],
    "tea": [r"^tea([ _]?(break|time))?$"]
}

STATUS_SYNONYMS = {
    "Completed": ["completed", "complete", "done", "finished", "resolved", "closed"],
    "In Progress": ["in progress", "in-progress", "working", "wip", "ongoing", "active"],
    "Pending": ["pending", "to do", "todo", "open", "backlog", "queued"],
    "Under Review": ["under review", "review", "testing", "qa", "qa review", "pr review"],
    "Blocked": ["blocked", "on hold", "stuck", "paused", "waiting"],
    "Weekly Off": ["weekly off", "weekend", "off day", "week off", "day off"],
    "Holiday": ["holiday", "public holiday", "festival"],
    "Leave": ["leave", "on leave", "vacation", "cl", "pl", "sl", "casual leave", "paid leave", "sick leave"]
}

def auto_detect_column_mapping(headers):
    """Detects which column index corresponds to which standard work field."""
    mapping = {k: None for k in EXCEL_COLUMN_PATTERNS}
    assigned_indices = set()

    for col_idx, raw_h in enumerate(headers):
        if raw_h is None:
            continue
        h_clean = re.sub(r'[^a-z0-9_ ]', '', str(raw_h).strip().lower())
        h_clean = re.sub(r'\s+', ' ', h_clean)
        for field, patterns in EXCEL_COLUMN_PATTERNS.items():
            if mapping[field] is None:
                for pat in patterns:
                    if re.search(pat, h_clean):
                        mapping[field] = col_idx
                        assigned_indices.add(col_idx)
                        break
                if mapping[field] is not None:
                    break

    for col_idx, raw_h in enumerate(headers):
        if col_idx in assigned_indices or raw_h is None:
            continue
        h_lower = str(raw_h).strip().lower()
        if mapping["date"] is None and "date" in h_lower:
            mapping["date"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["project"] is None and ("proj" in h_lower or "client" in h_lower):
            mapping["project"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["title"] is None and ("task" in h_lower or "title" in h_lower):
            mapping["title"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["desc"] is None and ("desc" in h_lower or "detail" in h_lower or "work" in h_lower):
            mapping["desc"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["hours"] is None and ("hour" in h_lower or "duration" in h_lower or "hrs" in h_lower):
            mapping["hours"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["status"] is None and "status" in h_lower:
            mapping["status"] = col_idx
            assigned_indices.add(col_idx)
        elif mapping["remarks"] is None and "remark" in h_lower:
            mapping["remarks"] = col_idx
            assigned_indices.add(col_idx)

    return mapping

def format_excel_time_cell(val):
    if val is None or val == "" or val == "-":
        return ""
    if isinstance(val, (datetime.time, datetime.datetime)):
        return val.strftime("%I:%M %p")
    return str(val).strip()

def format_excel_hours_cell(val):
    if val is None or val == "" or val == "-":
        return ""
    if isinstance(val, (int, float)):
        v = float(val)
        s = f"{v:.2f}".rstrip('0').rstrip('.') if '.' in f"{v:.2f}" else f"{v}"
        if '.' not in s:
            s += ".0"
        return s
    if isinstance(val, datetime.time):
        dec = round(val.hour + val.minute / 60.0, 2)
        s = f"{dec:.2f}".rstrip('0').rstrip('.') if '.' in f"{dec:.2f}" else f"{dec}"
        if '.' not in s:
            s += ".0"
        return s
    s = str(val).strip()
    _, formatted = parse_duration_to_hours(s)
    if formatted:
        if '.' not in formatted:
            formatted += ".0"
        return formatted
    return s

def normalize_status_val(val, default_status="Completed"):
    if not val or not str(val).strip():
        return default_status
    s_lower = str(val).strip().lower()
    for std_status, synonyms in STATUS_SYNONYMS.items():
        if s_lower == std_status.lower() or s_lower in synonyms:
            return std_status
    return str(val).strip().capitalize()

def inspect_excel_or_csv_file(filepath):
    """Returns (sheets_info, is_csv, error_message) where sheets_info is [(sheet_name, row_count), ...]."""
    if not os.path.exists(filepath):
        return [], False, "File does not exist."
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        try:
            with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                count = sum(1 for row in reader if any(str(cell).strip() for cell in row))
            return [("CSV File", count)], True, None
        except Exception as e:
            return [], True, str(e)
    elif ext in (".xlsx", ".xlsm", ".xltx"):
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
            sheets_info = []
            for name in wb.sheetnames:
                ws = wb[name]
                count = ws.max_row or 0
                sheets_info.append((name, count))
            wb.close()
            return sheets_info, False, None
        except PermissionError:
            return [], False, f"File '{os.path.basename(filepath)}' is currently open in Excel. Please close Excel and try again."
        except Exception as e:
            return [], False, str(e)
    elif ext == ".xls":
        return [], False, "Legacy .xls format is not supported.\nPlease open the file in Excel and save as .xlsx or .csv, then retry."
    else:
        return [], False, f"Unsupported file extension '{ext}'. Please select an Excel (.xlsx) or .csv file."

def generate_sample_import_template(target_path):
    """Generates a styled, ready-to-use Excel template for bulk import."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Work Updates"
    
    headers = [
        "Date", "Project Name", "Task Title", "Description", "Hours",
        "Status", "Remarks", "Login Time", "Logout Time", "Lunch Break", "Tea Break"
    ]
    ws.append(headers)

    sample_rows = [
        [
            datetime.date.today().strftime("%Y-%m-%d"),
            "Afro Cargo & Logistics",
            "Invoice PDF Generation",
            "Implemented automated PDF invoice generation with digital stamp and customer branding",
            "2.5",
            "Completed",
            "Merged into staging branch",
            "10:00 AM",
            "07:30 PM",
            "01:00 PM - 02:00 PM",
            "04:30 PM - 04:45 PM"
        ],
        [
            datetime.date.today().strftime("%Y-%m-%d"),
            "Afro Cargo & Logistics",
            "Payment Gateway Webhook",
            "Added callback signature verification, error logging, and auto receipt generation",
            "3.0",
            "Completed",
            "Tested with sandbox keys",
            "10:00 AM",
            "07:30 PM",
            "01:00 PM - 02:00 PM",
            "04:30 PM - 04:45 PM"
        ],
        [
            datetime.date.today().strftime("%Y-%m-%d"),
            "Internal CRM",
            "Driver Dispatch Mobile API",
            "Building REST endpoints for real-time driver coordinates and shipment tracking",
            "2.5",
            "In Progress",
            "Under review",
            "10:00 AM",
            "07:30 PM",
            "01:00 PM - 02:00 PM",
            "04:30 PM - 04:45 PM"
        ],
        [
            (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            "General Work",
            "Casual Leave (CL)",
            "Personal work / family function",
            "0.0",
            "Leave",
            "Approved by manager",
            "-",
            "-",
            "-",
            "-"
        ]
    ]

    for row in sample_rows:
        ws.append(row)

    header_fill = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    for r_idx in range(2, len(sample_rows) + 2):
        ws.row_dimensions[r_idx].height = 22
        for col_idx, cell in enumerate(ws[r_idx], start=1):
            cell.font = Font(name="Segoe UI", size=9)
            cell.border = thin_border
            if col_idx in (1, 5, 6, 8, 9, 10, 11):
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    col_widths = {
        'A': 14, 'B': 24, 'C': 26, 'D': 36, 'E': 10,
        'F': 14, 'G': 20, 'H': 13, 'I': 13, 'J': 22, 'K': 22
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    wb.save(target_path)

class ExcelBulkImportDialog(tk.Toplevel):
    def __init__(self, parent, on_import_success):
        super().__init__(parent)
        self.title("📂 Bulk Import Tasks from Excel (.xlsx) / CSV File")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()
        center_window(self, parent, default_w=1060, default_h=720, min_w=920, min_h=600)

        self.on_import_success = on_import_success
        self.filepath = ""
        self.is_csv = False
        self.sheets_info = []
        self.raw_rows = []
        self.headers = []
        self.col_options = []
        self.parsed_tasks = []

        self.create_widgets()

    def create_widgets(self):
        # 1. Header Frame
        header = tk.Frame(self, bg="#064e3b", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        h_left = tk.Frame(header, bg="#064e3b")
        h_left.pack(side=tk.LEFT, padx=15, pady=6)

        tk.Label(h_left, text="📂 Bulk Import Work Updates from Excel (.xlsx) / CSV", font=("Segoe UI", 12, "bold"), fg="white", bg="#064e3b").pack(anchor="w")
        tk.Label(h_left, text="Select workbook • Verify column mappings • Live preview & edit • Auto-routes to Month tabs", font=("Segoe UI", 8), fg="#a7f3d0", bg="#064e3b").pack(anchor="w")

        btn_tmpl = tk.Button(
            header, text="💡 Download Sample Template", font=("Segoe UI", 9, "bold"),
            bg="#10b981", fg="white", activebackground="#059669", activeforeground="white",
            relief="flat", padx=12, pady=5, cursor="hand2", command=self.download_template
        )
        btn_tmpl.pack(side=tk.RIGHT, padx=15, pady=8)

        # Main container
        main_frame = tk.Frame(self, bg="#f8fafc", padx=15, pady=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---------------- Section 1: File & Sheet Selection ----------------
        f_card1 = tk.LabelFrame(main_frame, text=" 1. Select Excel or CSV File ", font=("Segoe UI", 9, "bold"), fg="#064e3b", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        f_card1.pack(fill=tk.X, pady=(0, 6))

        # Row 1: File selection
        r1 = tk.Frame(f_card1, bg="#ffffff")
        r1.pack(fill=tk.X, pady=(2, 4))

        tk.Label(r1, text="File Path:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 6))
        self.entry_file_path = tk.Entry(r1, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=2)
        self.entry_file_path.config(state="readonly")

        btn_browse = tk.Button(
            r1, text="📂 Browse Excel / CSV File...", font=("Segoe UI", 9, "bold"),
            bg="#059669", fg="white", activebackground="#047857", activeforeground="white",
            relief="flat", padx=12, pady=3, cursor="hand2", command=self.browse_file
        )
        btn_browse.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_file_info = tk.Label(r1, text="No file selected", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b")
        self.lbl_file_info.pack(side=tk.LEFT)

        # Row 2: Sheet selection and options
        r2 = tk.Frame(f_card1, bg="#ffffff")
        r2.pack(fill=tk.X, pady=(2, 2))

        tk.Label(r2, text="Sheet to Import:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(side=tk.LEFT, padx=(0, 6))
        self.combo_sheet = ttk.Combobox(r2, state="readonly", width=26, font=("Segoe UI", 9))
        self.combo_sheet.pack(side=tk.LEFT, padx=(0, 15))
        self.combo_sheet.bind("<<ComboboxSelected>>", self.on_sheet_changed)

        self.var_has_header = tk.BooleanVar(value=True)
        chk_header = tk.Checkbutton(r2, text="First row is column header", variable=self.var_has_header, font=("Segoe UI", 9), bg="#ffffff", fg="#334155", command=self.on_config_changed)
        chk_header.pack(side=tk.LEFT, padx=(0, 15))

        self.var_fill_dates = tk.BooleanVar(value=True)
        chk_fill = tk.Checkbutton(r2, text="Auto-fill empty dates from previous row", variable=self.var_fill_dates, font=("Segoe UI", 9), bg="#ffffff", fg="#334155", command=self.on_config_changed)
        chk_fill.pack(side=tk.LEFT)

        # ---------------- Section 2: Column Mapping & Settings ----------------
        f_card2 = tk.LabelFrame(main_frame, text=" 2. Column Mapping & Fallback Defaults ", font=("Segoe UI", 9, "bold"), fg="#064e3b", bg="#ffffff", padx=10, pady=6, bd=1, relief="solid")
        f_card2.pack(fill=tk.X, pady=(0, 6))

        # Row 1: Primary Fields (Date, Project, Title, Desc, Hours, Status)
        grid_f = tk.Frame(f_card2, bg="#ffffff")
        grid_f.pack(fill=tk.X, pady=(2, 4))

        self.map_combos = {}

        fields_row1 = [
            ("Date Column*:", "date"),
            ("Project Column:", "project"),
            ("Task Title*:", "title"),
            ("Hours Column:", "hours"),
            ("Status Column:", "status"),
            ("Description Col:", "desc")
        ]

        for idx, (label_txt, f_key) in enumerate(fields_row1):
            cell = tk.Frame(grid_f, bg="#ffffff")
            cell.grid(row=0, column=idx, padx=4, pady=2, sticky="w")
            tk.Label(cell, text=label_txt, font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w")
            cb = ttk.Combobox(cell, state="readonly", width=16, font=("Segoe UI", 8))
            cb.pack(fill=tk.X)
            cb.bind("<<ComboboxSelected>>", lambda e, k=f_key: self.on_mapping_changed(k))
            self.map_combos[f_key] = cb

        # Row 2: Secondary Fields & Defaults
        grid_f2 = tk.Frame(f_card2, bg="#ffffff")
        grid_f2.pack(fill=tk.X, pady=(2, 2))

        fields_row2 = [
            ("Remarks Col:", "remarks"),
            ("Login Time Col:", "login"),
            ("Logout Time Col:", "logout"),
            ("Lunch Break Col:", "lunch"),
            ("Tea Break Col:", "tea")
        ]

        for idx, (label_txt, f_key) in enumerate(fields_row2):
            cell = tk.Frame(grid_f2, bg="#ffffff")
            cell.grid(row=0, column=idx, padx=4, pady=2, sticky="w")
            tk.Label(cell, text=label_txt, font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(anchor="w")
            cb = ttk.Combobox(cell, state="readonly", width=14, font=("Segoe UI", 8))
            cb.pack(fill=tk.X)
            cb.bind("<<ComboboxSelected>>", lambda e, k=f_key: self.on_mapping_changed(k))
            self.map_combos[f_key] = cb

        # Defaults sub-frame
        f_defs = tk.Frame(grid_f2, bg="#ffffff")
        f_defs.grid(row=0, column=len(fields_row2), padx=6, pady=2, sticky="w")
        tk.Label(f_defs, text="Default Project / Status:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#1e40af").pack(anchor="w")

        f_def_inputs = tk.Frame(f_defs, bg="#ffffff")
        f_def_inputs.pack(anchor="w")

        self.combo_default_proj = ttk.Combobox(f_def_inputs, width=16, font=("Segoe UI", 8))
        self.combo_default_proj.pack(side=tk.LEFT, padx=(0, 4))
        distinct_p = get_distinct_projects()
        self.combo_default_proj['values'] = distinct_p if distinct_p else ["General Work"]
        self.combo_default_proj.set("General Work")
        self.combo_default_proj.bind("<<ComboboxSelected>>", lambda e: self.reparse_tasks())
        self.combo_default_proj.bind("<KeyRelease>", lambda e: self.reparse_tasks())

        self.combo_default_status = ttk.Combobox(f_def_inputs, state="readonly", width=11, font=("Segoe UI", 8), values=["Completed", "In Progress", "Pending", "Under Review", "Blocked", "Leave"])
        self.combo_default_status.pack(side=tk.LEFT)
        self.combo_default_status.set("Completed")
        self.combo_default_status.bind("<<ComboboxSelected>>", lambda e: self.reparse_tasks())

        btn_auto_map = tk.Button(grid_f2, text="⚡ Auto-Detect", font=("Segoe UI", 7, "bold"), bg="#e0f2fe", fg="#0369a1", relief="flat", padx=6, pady=2, cursor="hand2", command=self.reset_column_mapping)
        btn_auto_map.grid(row=0, column=len(fields_row2) + 1, padx=(6, 0), pady=(12, 0), sticky="w")

        # ---------------- Section 3: Live Preview Table ----------------
        f_card3 = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="solid")
        f_card3.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        tbl_top = tk.Frame(f_card3, bg="#f8fafc", padx=8, pady=4)
        tbl_top.pack(fill=tk.X)

        tk.Label(tbl_top, text="3. Preview Tasks to be Imported:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#064e3b").pack(side=tk.LEFT)
        tk.Label(tbl_top, text="(Double-click any row to edit • Dates automatically route into Month tabs)", font=("Segoe UI", 8, "italic"), bg="#f8fafc", fg="#64748b").pack(side=tk.LEFT, padx=8)

        self.lbl_preview_badge = tk.Label(tbl_top, text="0 tasks ready", font=("Segoe UI", 8, "bold"), bg="#ecfdf5", fg="#065f46", padx=6, pady=2)
        self.lbl_preview_badge.pack(side=tk.RIGHT)

        # Treeview
        tree_container = tk.Frame(f_card3, bg="#ffffff")
        tree_container.pack(fill=tk.BOTH, expand=True)

        cols = ("No", "Date", "Month Tab", "Project", "Task Title", "Hours", "Status", "Description", "Timings", "Remarks")
        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=8)

        col_defs = [
            ("No", 35, "center"),
            ("Date", 85, "center"),
            ("Month Tab", 100, "center"),
            ("Project", 130, "w"),
            ("Task Title", 220, "w"),
            ("Hours", 60, "center"),
            ("Status", 85, "center"),
            ("Description", 190, "w"),
            ("Timings", 110, "center"),
            ("Remarks", 100, "w")
        ]

        for col_name, width, anchor in col_defs:
            self.tree.heading(col_name, text=col_name)
            self.tree.column(col_name, width=width, anchor=anchor)

        v_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Under Table Buttons
        tbl_actions = tk.Frame(f_card3, bg="#f8fafc", padx=8, pady=4)
        tbl_actions.pack(fill=tk.X)

        btn_edit = tk.Button(tbl_actions, text="✏️ Edit Selected Task", font=("Segoe UI", 8, "bold"), bg="#f1f5f9", fg="#1e293b", relief="flat", padx=8, pady=2, cursor="hand2", command=self.edit_selected_task)
        btn_edit.pack(side=tk.LEFT, padx=(0, 4))

        btn_del = tk.Button(tbl_actions, text="🗑️ Remove Task", font=("Segoe UI", 8), bg="#fee2e2", fg="#991b1b", relief="flat", padx=8, pady=2, cursor="hand2", command=self.delete_selected_task)
        btn_del.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear = tk.Button(tbl_actions, text="🧹 Clear All", font=("Segoe UI", 8), bg="#e2e8f0", fg="#475569", relief="flat", padx=8, pady=2, cursor="hand2", command=self.clear_all_tasks)
        btn_clear.pack(side=tk.LEFT)

        # ---------------- Bottom Action Bar ----------------
        bottom_bar = tk.Frame(self, bg="#f1f5f9", padx=15, pady=8)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(bottom_bar, text="Ready. Please select an Excel or CSV file to begin.", font=("Segoe UI", 9), fg="#475569", bg="#f1f5f9")
        self.lbl_status.pack(side=tk.LEFT)

        self.btn_import = tk.Button(
            bottom_bar, text="🚀 Import All Tasks to Excel Month Tabs", font=("Segoe UI", 10, "bold"),
            bg="#059669", fg="white", activebackground="#047857", activeforeground="white",
            relief="flat", padx=18, pady=6, cursor="hand2", command=self.do_import, state=tk.DISABLED
        )
        self.btn_import.pack(side=tk.RIGHT)

        btn_cancel = tk.Button(bottom_bar, text="Cancel", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=12, pady=6, cursor="hand2", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=6)

    def browse_file(self):
        f = filedialog.askopenfilename(
            parent=self,
            title="Select Excel or CSV File for Bulk Import",
            filetypes=[
                ("Excel & CSV Files", "*.xlsx *.xlsm *.csv"),
                ("Excel Workbooks (*.xlsx, *.xlsm)", "*.xlsx *.xlsm"),
                ("CSV Files (*.csv)", "*.csv"),
                ("All Files", "*.*")
            ]
        )
        if not f:
            return

        ext = os.path.splitext(f)[1].lower()
        if ext == ".xls":
            messagebox.showerror(
                "Legacy Excel Format",
                "Legacy binary .xls files are not supported.\n\nPlease open the file in Excel and save it as .xlsx (Excel Workbook) or .csv, then re-select."
            )
            return

        self.filepath = f
        self.entry_file_path.config(state=tk.NORMAL)
        self.entry_file_path.delete(0, tk.END)
        self.entry_file_path.insert(0, f)
        self.entry_file_path.config(state="readonly")

        self.load_file_structure()

    def load_file_structure(self):
        sheets_info, is_csv, err = inspect_excel_or_csv_file(self.filepath)
        if err:
            messagebox.showerror("File Error", err)
            self.lbl_status.config(text=f"⚠️ {err}", fg="#dc2626")
            return

        self.is_csv = is_csv
        self.sheets_info = sheets_info

        size_kb = os.path.getsize(self.filepath) / 1024.0
        self.lbl_file_info.config(text=f"📊 {size_kb:.1f} KB • {len(sheets_info)} Sheet(s) found")

        combo_vals = []
        if is_csv:
            combo_vals = ["CSV File"]
        else:
            for s_name, count in sheets_info:
                combo_vals.append(f"{s_name} ({count} rows)")
            if len(sheets_info) > 1:
                combo_vals.append("All Sheets (Combined)")

        self.combo_sheet['values'] = combo_vals
        if combo_vals:
            self.combo_sheet.current(0)

        self.load_sheet_data_and_remap()

    def load_sheet_data_and_remap(self):
        if not self.filepath:
            return

        selected_sheet_str = self.combo_sheet.get()
        sheet_to_load = None
        if not self.is_csv and selected_sheet_str:
            if selected_sheet_str == "All Sheets (Combined)":
                sheet_to_load = "__ALL__"
            else:
                sheet_to_load = selected_sheet_str.split(" (")[0]

        try:
            if self.is_csv:
                with open(self.filepath, "r", encoding="utf-8-sig", errors="replace") as f:
                    reader = csv.reader(f)
                    self.raw_rows = [row for row in reader if any(str(cell).strip() for cell in row)]
            elif sheet_to_load == "__ALL__":
                wb = openpyxl.load_workbook(self.filepath, data_only=True)
                combined = []
                for s_idx, s_name in enumerate(wb.sheetnames):
                    ws = wb[s_name]
                    sheet_rows = []
                    for r in ws.iter_rows(values_only=True):
                        if any(c is not None and str(c).strip() != "" for c in r):
                            sheet_rows.append(list(r))
                    if s_idx == 0:
                        combined.extend(sheet_rows)
                    else:
                        data_part = sheet_rows[1:] if (self.var_has_header.get() and len(sheet_rows) > 1) else sheet_rows
                        combined.extend(data_part)
                wb.close()
                self.raw_rows = combined
            else:
                wb = openpyxl.load_workbook(self.filepath, data_only=True)
                ws = wb[sheet_to_load] if (sheet_to_load and sheet_to_load in wb.sheetnames) else wb.active
                self.raw_rows = []
                for r in ws.iter_rows(values_only=True):
                    if any(c is not None and str(c).strip() != "" for c in r):
                        self.raw_rows.append(list(r))
                wb.close()
        except PermissionError:
            messagebox.showerror("Permission Error", f"Cannot open '{os.path.basename(self.filepath)}' because it is locked in Excel. Please close Excel and try again.")
            return
        except Exception as e:
            messagebox.showerror("Read Error", f"Error reading file: {e}")
            return

        if not self.raw_rows:
            messagebox.showwarning("Empty Sheet", "No data rows were found in the selected sheet.")
            self.parsed_tasks = []
            self.refresh_preview_tree()
            return

        if self.var_has_header.get() and len(self.raw_rows) > 0:
            self.headers = [str(c or "").strip() for c in self.raw_rows[0]]
        else:
            col_count = max(len(r) for r in self.raw_rows) if self.raw_rows else 0
            self.headers = [f"Column {i+1}" for i in range(col_count)]

        self.col_options = ["[None / Not in File]"]
        for i, h in enumerate(self.headers):
            display_h = h if h else f"Col {i+1}"
            self.col_options.append(f"Col {i+1}: {display_h}")

        for cb in self.map_combos.values():
            cb['values'] = self.col_options

        detected = auto_detect_column_mapping(self.headers)
        for f_key, col_idx in detected.items():
            if f_key in self.map_combos:
                if col_idx is not None and col_idx < len(self.headers):
                    self.map_combos[f_key].current(col_idx + 1)
                else:
                    self.map_combos[f_key].current(0)

        self.reparse_tasks()

    def on_sheet_changed(self, event=None):
        self.load_sheet_data_and_remap()

    def on_config_changed(self, *args):
        self.load_sheet_data_and_remap()

    def on_mapping_changed(self, f_key):
        self.reparse_tasks()

    def reset_column_mapping(self):
        detected = auto_detect_column_mapping(self.headers)
        for f_key, col_idx in detected.items():
            if f_key in self.map_combos:
                if col_idx is not None and col_idx < len(self.headers):
                    self.map_combos[f_key].current(col_idx + 1)
                else:
                    self.map_combos[f_key].current(0)
        self.reparse_tasks()

    def reparse_tasks(self):
        if not self.raw_rows:
            self.parsed_tasks = []
            self.refresh_preview_tree()
            return

        col_indices = {}
        for f_key, cb in self.map_combos.items():
            sel_idx = cb.current()
            col_indices[f_key] = (sel_idx - 1) if sel_idx > 0 else None

        data_rows = self.raw_rows[1:] if (self.var_has_header.get() and len(self.raw_rows) > 1) else self.raw_rows
        default_p = self.combo_default_proj.get().strip() or "General Work"
        default_st = self.combo_default_status.get().strip() or "Completed"
        fill_empty_d = self.var_fill_dates.get()

        tasks = []
        last_valid_date = ""

        for r in data_rows:
            def get_cell(f_key):
                idx = col_indices.get(f_key)
                if idx is not None and idx < len(r):
                    return r[idx]
                return None

            d_raw = get_cell("date")
            d_str = format_date_only(d_raw)
            if not d_str and fill_empty_d and last_valid_date:
                d_str = last_valid_date
            if d_str:
                last_valid_date = d_str

            p_val = str(get_cell("project") or "").strip() or default_p
            title_val = str(get_cell("title") or "").strip()
            desc_val = str(get_cell("desc") or "").strip()

            if not title_val and not desc_val and not get_cell("hours"):
                continue

            if not title_val and desc_val:
                first_line = desc_val.split("\n")[0].strip()
                title_val = first_line[:60] if len(first_line) > 60 else first_line

            if not title_val:
                title_val = "Task Update"

            h_raw = get_cell("hours")
            h_str = format_excel_hours_cell(h_raw)

            st_raw = get_cell("status")
            st_str = normalize_status_val(st_raw, default_status=default_st)

            rem_val = str(get_cell("remarks") or "").strip()

            login_val = format_excel_time_cell(get_cell("login"))
            logout_val = format_excel_time_cell(get_cell("logout"))
            lunch_val = str(get_cell("lunch") or "").strip()
            tea_val = str(get_cell("tea") or "").strip()

            tasks.append({
                "date": d_str,
                "project": p_val,
                "title": title_val,
                "desc": desc_val,
                "hours": h_str,
                "status": st_str,
                "remarks": rem_val,
                "login": login_val,
                "logout": logout_val,
                "lunch": lunch_val,
                "tea": tea_val
            })

        self.parsed_tasks = tasks
        self.refresh_preview_tree()

    def refresh_preview_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        total_hours = 0.0
        sheets_set = set()

        for i, t in enumerate(self.parsed_tasks, start=1):
            d_val = t.get("date", "")
            target_month = get_month_sheet_name(d_val) if d_val else "Current Month"
            sheets_set.add(target_month)

            h_val = t.get("hours", "")
            if h_val:
                try:
                    total_hours += float(h_val)
                except ValueError:
                    pass

            timings_disp = ""
            if t.get("login") or t.get("logout"):
                timings_disp = f"{t.get('login', '-')} to {t.get('logout', '-')}"

            self.tree.insert("", tk.END, values=(
                i,
                d_val or "⚠️ Missing",
                target_month,
                t.get("project", ""),
                t.get("title", ""),
                h_val or "-",
                t.get("status", "Completed"),
                t.get("desc", "").replace("\n", " "),
                timings_disp,
                t.get("remarks", "")
            ))

        num = len(self.parsed_tasks)
        sheets_list = sorted(list(sheets_set))
        sheets_txt = ", ".join(sheets_list) if sheets_list else "-"
        hrs_str = f"{total_hours:.2f}".rstrip('0').rstrip('.') if '.' in f"{total_hours:.2f}" else f"{total_hours}"
        if '.' not in hrs_str:
            hrs_str += ".0"

        self.lbl_preview_badge.config(text=f"📊 {num} Tasks • {hrs_str} Total Hours • Month Tabs: {sheets_txt}")

        if num > 0:
            self.btn_import.config(state=tk.NORMAL, text=f"🚀 Import All {num} Tasks to Excel ({len(sheets_list)} Month Tabs)")
            self.lbl_status.config(text=f"✅ {num} tasks parsed and ready to import into '{sheets_txt}'.", fg="#16a34a")
        else:
            self.btn_import.config(state=tk.DISABLED, text="🚀 Import All Tasks to Excel Month Tabs")
            self.lbl_status.config(text="No tasks parsed. Check column mapping above.", fg="#dc2626")

    def on_tree_double_click(self, event):
        self.edit_selected_task()

    def edit_selected_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a task from the preview table to edit.")
            return

        item = self.tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.parsed_tasks):
            task = self.parsed_tasks[idx]
            def save_cb(updated):
                self.parsed_tasks[idx] = updated
                self.refresh_preview_tree()
            EditTaskPreviewDialog(self, task, save_cb)

    def delete_selected_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a task to remove.")
            return

        item = self.tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.parsed_tasks):
            del self.parsed_tasks[idx]
            self.refresh_preview_tree()

    def clear_all_tasks(self):
        if not self.parsed_tasks:
            return
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all tasks from the preview?"):
            self.parsed_tasks = []
            self.refresh_preview_tree()

    def download_template(self):
        default_fn = f"timesheet_import_template_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        f = filedialog.asksaveasfilename(
            parent=self,
            title="Save Sample Timesheet Import Template",
            initialfile=default_fn,
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook (*.xlsx)", "*.xlsx")]
        )
        if not f:
            return
        try:
            generate_sample_import_template(f)
            if messagebox.askyesno("Template Generated", f"✅ Sample Excel template saved successfully to:\n{f}\n\nWould you like to open it now?"):
                try:
                    open_file_externally(f)
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror("Error Saving Template", f"Could not save template: {e}")

    def do_import(self):
        if not self.parsed_tasks:
            messagebox.showwarning("No Tasks", "No tasks to import.")
            return

        missing_dates = sum(1 for t in self.parsed_tasks if not t.get("date"))
        if missing_dates > 0:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            if messagebox.askyesno(
                "Missing Dates",
                f"{missing_dates} tasks do not have a valid date.\n\nWould you like to set their date to today ({today_str}) and proceed?"
            ):
                for t in self.parsed_tasks:
                    if not t.get("date"):
                        t["date"] = today_str
            else:
                return

        default_proj = self.combo_default_proj.get().strip() or "General Work"

        total_saved, counts_per_sheet = save_excel_file_bulk_import(self.parsed_tasks, default_proj=default_proj)

        if total_saved > 0:
            breakdown = "\n".join([f"• {sheet}: {cnt} tasks" for sheet, cnt in counts_per_sheet.items()])
            messagebox.showinfo(
                "Bulk Import Complete",
                f"✅ Successfully imported {total_saved} tasks into Excel ({FILE})!\n\n{breakdown}\n\nAll sheets have been chronologically auto-arranged."
            )

            most_frequent_sheet = max(counts_per_sheet.items(), key=lambda x: x[1])[0] if counts_per_sheet else None
            last_date = self.parsed_tasks[-1].get("date") or datetime.date.today().strftime("%Y-%m-%d")

            self.on_import_success(most_frequent_sheet, last_date, default_proj, self.parsed_tasks, prompt_share=False)
            self.destroy()

# ---------- Main GUI Application ----------
class TodayWorkUpdateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Today's Work Update - Month-Wise Excel Logger & Shift Tracker")
        self.root.configure(bg="#f4f6f9")

        # Set Native Desktop Window Icon (Windows .ico and Linux/macOS .png)
        icon_ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon_128.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")

        if sys.platform.startswith("win") and os.path.exists(icon_ico):
            try:
                self.root.iconbitmap(default=icon_ico)
            except Exception:
                pass
        if os.path.exists(icon_path):
            try:
                self._app_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self._app_icon)
            except Exception:
                pass

        # Dynamically auto-adjust window size according to screen dimensions
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Responsive default geometry (centers on screen, leaves margin for system panels/docks)
        win_w = max(1160, min(1560, int(screen_w * 0.92)))
        win_h = max(700, min(960, int(screen_h * 0.88)))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(980, 560)

        # Maximize / Zoom window to fit display perfectly if supported
        try:
            if sys.platform.startswith("linux"):
                self.root.attributes("-zoomed", True)
            elif sys.platform == "win32":
                self.root.state("zoomed")
        except Exception:
            pass

        self.editing_record_id = None
        self.current_selected_month = tk.StringVar()
        self.search_var = tk.StringVar()
        self.filter_status_var = tk.StringVar(value="All Statuses")

        # LAN Team Chat System initialization
        self.root.app_instance = self
        self.settings = load_settings()
        GoogleSheetSyncWorker.set_app_ref(self)
        self.unread_lan_messages = 0
        self.chat_dialog = None
        self.lan_engine = LANChatEngine(
            user_name=self.settings.get("user_name", "Developer"),
            port=self.settings.get("lan_chat_port", 45454),
            on_message=self._handle_background_lan_message,
            on_peers_change=self._handle_lan_peers_change
        )
        try:
            self.lan_engine.start()
        except Exception as e:
            print(f"Error starting LAN Chat Engine: {e}")

        # Ensure graceful shutdown on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_closing)

        # Initialize File and verify schema
        init_file()

        # Build UI
        self.setup_styles()
        self.create_header()
        self.create_main_content()
        self.create_status_bar()

        # Initial Load
        self.refresh_month_dropdown()
        self.refresh_table()

        # Keyboard Shortcuts
        self.root.bind("<Control-comma>", lambda e: self.open_settings())

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#1f4e79", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#163b5c')])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=28, fieldbackground="white", background="white")
        style.map("Treeview", background=[('selected', '#d0e1fd')], foreground=[('selected', '#0d233a')])
        style.configure("TCombobox", padding=4, font=("Segoe UI", 9))

    def create_header(self):
        header_frame = tk.Frame(self.root, bg="#1a365d")
        header_frame.pack(fill=tk.X, side=tk.TOP)

        title_box = tk.Frame(header_frame, bg="#1a365d")
        title_box.pack(side=tk.LEFT, padx=(18, 10), pady=10)

        title_lbl = tk.Label(title_box, text="📝 Today Work Update Manager", font=("Segoe UI", 15, "bold"), fg="#ffffff", bg="#1a365d")
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(title_box, text="Shift Tracker • Month-Wise Excel Logger • Auto-Arranging", font=("Segoe UI", 8), fg="#90cdf4", bg="#1a365d")
        sub_lbl.pack(anchor="w")

        # Header Right Controls (2-Row compact grid: fits gracefully on all screens)
        right_box = tk.Frame(header_frame, bg="#1a365d")
        right_box.pack(side=tk.RIGHT, padx=14, pady=8)

        # Row 1: Actions
        r1 = tk.Frame(right_box, bg="#1a365d")
        r1.pack(anchor="e", pady=(0, 3))

        btn_share = tk.Button(r1, text="📢 Share with Team", font=("Segoe UI", 8, "bold"), bg="#8b5cf6", fg="white", activebackground="#7c3aed", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.share_current_view_with_team)
        btn_share.pack(side=tk.LEFT, padx=2)

        self.btn_chat = tk.Button(r1, text="💬 LAN Chat", font=("Segoe UI", 8, "bold"), bg="#4f46e5", fg="white", activebackground="#4338ca", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_lan_chat)
        self.btn_chat.pack(side=tk.LEFT, padx=2)

        btn_import_excel = tk.Button(r1, text="📂 Import Excel", font=("Segoe UI", 8, "bold"), bg="#059669", fg="white", activebackground="#047857", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_excel_bulk_import_dialog)
        btn_import_excel.pack(side=tk.LEFT, padx=2)

        btn_bulk = tk.Button(r1, text="📋 Bulk Paste", font=("Segoe UI", 8, "bold"), bg="#d97706", fg="white", activebackground="#b45309", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_bulk_import_dialog)
        btn_bulk.pack(side=tk.LEFT, padx=2)

        btn_open_excel = tk.Button(r1, text="📊 Open Excel", font=("Segoe UI", 8, "bold"), bg="#16a34a", fg="white", activebackground="#15803d", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_excel_file)
        btn_open_excel.pack(side=tk.LEFT, padx=2)

        # Row 2: Management & Settings
        r2 = tk.Frame(right_box, bg="#1a365d")
        r2.pack(anchor="e")

        btn_holidays = tk.Button(r2, text="🏖️ Weekends & Holidays", font=("Segoe UI", 8, "bold"), bg="#0284c7", fg="white", activebackground="#0369a1", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_weekend_holiday_settings)
        btn_holidays.pack(side=tk.LEFT, padx=2)

        btn_leave = tk.Button(r2, text="🌴 Add Leave", font=("Segoe UI", 8, "bold"), bg="#be185d", fg="white", activebackground="#9d174d", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_add_leave_dialog)
        btn_leave.pack(side=tk.LEFT, padx=2)

        btn_sync_api = tk.Button(r2, text="🔄 Sync to API", font=("Segoe UI", 8, "bold"), bg="#0d9488", fg="white", activebackground="#0f766e", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_sync_api_dialog)
        btn_sync_api.pack(side=tk.LEFT, padx=2)

        btn_sync_gsheet = tk.Button(r2, text="📊 Google Sheet", font=("Segoe UI", 8, "bold"), bg="#0f9d58", fg="white", activebackground="#0b8043", activeforeground="white", relief="flat", padx=9, pady=2, cursor="hand2", command=self.open_google_sheet_sync_dialog)
        btn_sync_gsheet.pack(side=tk.LEFT, padx=2)

        btn_settings = tk.Button(r2, text="⚙️ Settings", font=("Segoe UI", 8, "bold"), bg="#334155", fg="white", activebackground="#475569", activeforeground="white", relief="flat", padx=10, pady=2, cursor="hand2", command=self.open_settings)
        btn_settings.pack(side=tk.LEFT, padx=2)

    def create_main_content(self):
        # Top Stats Bar
        self.stats_frame = tk.Frame(self.root, bg="#e2e8f0")
        self.stats_frame.pack(fill=tk.X, padx=12, pady=(8, 4))

        self.lbl_stat_month = tk.Label(self.stats_frame, text="Month: -", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#2d3748")
        self.lbl_stat_month.pack(side=tk.LEFT, padx=12, pady=7)

        self.lbl_stat_tasks = tk.Label(self.stats_frame, text="Total Tasks: 0", font=("Segoe UI", 10), bg="#e2e8f0", fg="#4a5568")
        self.lbl_stat_tasks.pack(side=tk.LEFT, padx=12, pady=7)

        self.lbl_stat_hours = tk.Label(self.stats_frame, text="Total Hours: 0.0 hrs", font=("Segoe UI", 10), bg="#e2e8f0", fg="#4a5568")
        self.lbl_stat_hours.pack(side=tk.LEFT, padx=12, pady=7)

        self.lbl_stat_completed = tk.Label(self.stats_frame, text="Completed: 0", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#2e7d32")
        self.lbl_stat_completed.pack(side=tk.LEFT, padx=6, pady=7)

        self.lbl_stat_gte_8h = tk.Label(self.stats_frame, text="⏱️ ≥ 8h Days: 0", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#15803d", cursor="hand2")
        self.lbl_stat_gte_8h.pack(side=tk.LEFT, padx=6, pady=7)
        self.lbl_stat_gte_8h.bind("<Button-1>", lambda e: self.show_gte_8h_details())
        self.lbl_stat_gte_8h.bind("<Enter>", lambda e: self.status.config(text=f"⏱️ {len(getattr(self, 'current_gte_8_dates', []))} days with ≥ 8.0 working hours in {self.current_selected_month.get()} (Click to view detailed date list)"))
        self.lbl_stat_gte_8h.bind("<Leave>", lambda e: self.status.config(text="Ready"))

        self.lbl_stat_lt_8h = tk.Label(self.stats_frame, text="⏳ < 8h Days: 0", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#c2410c", cursor="hand2")
        self.lbl_stat_lt_8h.pack(side=tk.LEFT, padx=6, pady=7)
        self.lbl_stat_lt_8h.bind("<Button-1>", lambda e: self.show_lt_8h_details())
        self.lbl_stat_lt_8h.bind("<Enter>", lambda e: self.status.config(text=f"⏳ {len(getattr(self, 'current_lt_8_dates', []))} days with < 8.0 working hours in {self.current_selected_month.get()} (Click to view detailed date list)"))
        self.lbl_stat_lt_8h.bind("<Leave>", lambda e: self.status.config(text="Ready"))

        self.lbl_stat_leaves = tk.Label(self.stats_frame, text="🌴 Leaves: 0", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#be185d")
        self.lbl_stat_leaves.pack(side=tk.LEFT, padx=6, pady=7)

        self.lbl_stat_lan = tk.Label(self.stats_frame, text="💬 LAN: 0 online", font=("Segoe UI", 10, "bold"), bg="#e2e8f0", fg="#4f46e5", cursor="hand2")
        self.lbl_stat_lan.pack(side=tk.LEFT, padx=6, pady=7)
        self.lbl_stat_lan.bind("<Button-1>", lambda e: self.open_lan_chat())

        # Shift summary on top right
        self.lbl_stat_shift = tk.Label(self.stats_frame, text="", font=("Segoe UI", 9, "bold"), bg="#e2e8f0", fg="#0369a1")
        self.lbl_stat_shift.pack(side=tk.RIGHT, padx=12, pady=7)

        # Split Container - Resizable PanedWindow between Form and Table
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bd=0, sashwidth=6, sashrelief=tk.FLAT, bg="#cbd5e1")
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 6))

        # ----------------- LEFT FORM PANEL -----------------
        form_card = tk.LabelFrame(self.main_paned, text="  ➕ Single Work Update  ", font=("Segoe UI", 11, "bold"), fg="#1a365d", bg="#ffffff", bd=1, relief="solid", padx=10, pady=6)
        self.main_paned.add(form_card, minsize=420)

        # Form Buttons (PINNED AT BOTTOM OF CARD - ALWAYS VISIBLE!)
        f_btn = tk.Frame(form_card, bg="#ffffff")
        f_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        self.btn_save = tk.Button(f_btn, text="💾 Save Work Update", font=("Segoe UI", 10, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", pady=6, cursor="hand2", command=self.save_record)
        self.btn_save.pack(fill=tk.X, pady=(0, 3))

        f_sub_btns = tk.Frame(f_btn, bg="#ffffff")
        f_sub_btns.pack(fill=tk.X)
        f_sub_btns.columnconfigure(0, weight=1)
        f_sub_btns.columnconfigure(1, weight=1)

        self.btn_cancel_edit = tk.Button(f_sub_btns, text="🧹 Clear Form", font=("Segoe UI", 8, "bold"), bg="#e2e8f0", fg="#475569", relief="flat", pady=3, cursor="hand2", command=self.clear_form)
        self.btn_cancel_edit.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=(0, 2))

        btn_leave_quick = tk.Button(f_sub_btns, text="🌴 Add Leave", font=("Segoe UI", 8, "bold"), bg="#fce7f3", fg="#be185d", relief="flat", pady=3, cursor="hand2", command=self.open_add_leave_dialog)
        btn_leave_quick.grid(row=0, column=1, sticky="nsew", padx=(2, 0), pady=(0, 2))

        btn_excel_quick = tk.Button(f_sub_btns, text="📂 Import Excel File", font=("Segoe UI", 8, "bold"), bg="#d1fae5", fg="#065f46", relief="flat", pady=3, cursor="hand2", command=self.open_excel_bulk_import_dialog)
        btn_excel_quick.grid(row=1, column=0, sticky="nsew", padx=(0, 2), pady=0)

        btn_bulk_quick = tk.Button(f_sub_btns, text="📋 Bulk Paste Text", font=("Segoe UI", 8, "bold"), bg="#fef3c7", fg="#92400e", relief="flat", pady=3, cursor="hand2", command=self.open_bulk_import_dialog)
        btn_bulk_quick.grid(row=1, column=1, sticky="nsew", padx=(2, 0), pady=0)

        # Scrollable inputs canvas
        form_canvas_box = tk.Frame(form_card, bg="#ffffff")
        form_canvas_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.form_canvas = tk.Canvas(form_canvas_box, bg="#ffffff", highlightthickness=0)
        self.form_scroll = ttk.Scrollbar(form_canvas_box, orient=tk.VERTICAL, command=self.form_canvas.yview)
        form_inner = tk.Frame(self.form_canvas, bg="#ffffff")

        self.form_canvas.configure(yscrollcommand=self.form_scroll.set)
        self.form_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_win = self.form_canvas.create_window((0, 0), window=form_inner, anchor="nw")

        def _on_inner_cfg(event):
            self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all"))

        form_inner.bind("<Configure>", _on_inner_cfg)

        def _on_canvas_cfg(event):
            self.form_canvas.itemconfig(canvas_win, width=event.width)
            if hasattr(self, 'lbl_shift_badge'):
                self.lbl_shift_badge.config(wraplength=max(200, event.width - 24))

        self.form_canvas.bind("<Configure>", _on_canvas_cfg)

        # Mousewheel scroll support across Windows, macOS, and Linux (Button-4 / Button-5)
        def _on_mousewheel(event):
            if event.num == 4:
                self.form_canvas.yview_scroll(-2, "units")
            elif event.num == 5:
                self.form_canvas.yview_scroll(2, "units")
            elif event.delta:
                self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(event):
            self.form_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.form_canvas.bind_all("<Button-4>", _on_mousewheel)
            self.form_canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_wheel(event):
            self.form_canvas.unbind_all("<MouseWheel>")
            self.form_canvas.unbind_all("<Button-4>")
            self.form_canvas.unbind_all("<Button-5>")

        self.form_canvas.bind("<Enter>", _bind_wheel)
        self.form_canvas.bind("<Leave>", _unbind_wheel)

        # Date Field
        f_date = tk.Frame(form_inner, bg="#ffffff")
        f_date.pack(fill=tk.X, pady=2)
        tk.Label(f_date, text="Date (YYYY-MM-DD)*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        date_input_box = tk.Frame(f_date, bg="#ffffff")
        date_input_box.pack(fill=tk.X, pady=1)
        self.entry_date = tk.Entry(date_input_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_date.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self.entry_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        self.entry_date.bind("<KeyRelease>", lambda e: self.on_date_changed())

        btn_today = tk.Button(date_input_box, text="Today", font=("Segoe UI", 8, "bold"), bg="#edf2f7", fg="#2b6cb0", relief="flat", padx=6, pady=1, cursor="hand2", command=self.set_today_date)
        btn_today.pack(side=tk.RIGHT, padx=(6, 0))

        # Project / Module
        f_proj = tk.Frame(form_inner, bg="#ffffff")
        f_proj.pack(fill=tk.X, pady=2)
        tk.Label(f_proj, text="Project / Module*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        self.combo_project = ttk.Combobox(f_proj, values=get_distinct_projects(), font=("Segoe UI", 9))
        self.combo_project.pack(fill=tk.X, pady=1)
        self.combo_project.set("Afro Cargo & Logistics")

        # Task Title
        f_title = tk.Frame(form_inner, bg="#ffffff")
        f_title.pack(fill=tk.X, pady=2)
        tk.Label(f_title, text="Task Summary / Title*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        self.entry_title = tk.Entry(f_title, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_title.pack(fill=tk.X, pady=1, ipady=2)

        # Hours & Status in a balanced 2-column grid
        f_row2 = tk.Frame(form_inner, bg="#ffffff")
        f_row2.pack(fill=tk.X, pady=2)
        f_row2.columnconfigure(0, weight=1, uniform="hrs_st")
        f_row2.columnconfigure(1, weight=1, uniform="hrs_st")

        f_hrs = tk.Frame(f_row2, bg="#ffffff")
        f_hrs.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        
        lbl_hrs_box = tk.Frame(f_hrs, bg="#ffffff")
        lbl_hrs_box.pack(fill=tk.X)
        tk.Label(lbl_hrs_box, text="Hours Spent:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(side=tk.LEFT)
        
        self.var_auto_calc_hours = tk.BooleanVar(value=True)
        self.chk_auto_calc = tk.Checkbutton(lbl_hrs_box, text="⚡ Auto-Calc", variable=self.var_auto_calc_hours, font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#2563eb", activebackground="#ffffff", activeforeground="#1d4ed8", selectcolor="#ffffff", command=self.on_auto_calc_toggle)
        self.chk_auto_calc.pack(side=tk.RIGHT)

        self.entry_hours = tk.Entry(f_hrs, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_hours.pack(fill=tk.X, pady=1, ipady=2)
        self.entry_hours.bind("<KeyRelease>", lambda e: self.on_hours_manual_edit())

        f_st = tk.Frame(f_row2, bg="#ffffff")
        f_st.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        tk.Label(f_st, text="Status*:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        self.combo_status = ttk.Combobox(f_st, values=["Completed", "In Progress", "Pending", "Under Review", "Blocked", "Leave"], state="readonly", font=("Segoe UI", 9))
        self.combo_status.pack(fill=tk.X, pady=1)
        self.combo_status.set("Completed")
        self.combo_status.bind("<<ComboboxSelected>>", lambda e: self.on_status_changed())

        # ----------------- SHIFT & BREAK TIMINGS CARD -----------------
        f_shift = tk.LabelFrame(form_inner, text="  ⏰ Shift & Break Timings (Optional)  ", font=("Segoe UI", 9, "bold"), fg="#1e40af", bg="#f8fafc", bd=1, relief="solid", padx=8, pady=5)
        f_shift.pack(fill=tk.X, pady=3)

        # Retrieve today's timings
        today_t = get_daily_timings(datetime.datetime.now().strftime("%Y-%m-%d"))

        # Row 1: Login & Logout in balanced 50-50 columns
        f_inout = tk.Frame(f_shift, bg="#f8fafc")
        f_inout.pack(fill=tk.X, pady=1)
        f_inout.columnconfigure(0, weight=1, uniform="inout")
        f_inout.columnconfigure(1, weight=1, uniform="inout")

        # Login sub-box
        f_login_sub = tk.Frame(f_inout, bg="#f8fafc")
        f_login_sub.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        tk.Label(f_login_sub, text="🕒 Login Time:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#334155").pack(anchor="w")
        b_in_box = tk.Frame(f_login_sub, bg="#f8fafc")
        b_in_box.pack(fill=tk.X, pady=1)
        self.entry_form_login = tk.Entry(b_in_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_form_login.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self.entry_form_login.insert(0, today_t.get("login", "10:00 AM"))
        self.entry_form_login.bind("<KeyRelease>", lambda e: self.update_shift_summary_badge())

        btn_in_now = tk.Button(b_in_box, text="Now", font=("Segoe UI", 7, "bold"), bg="#edf2f7", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_entry_val(self.entry_form_login, format_current_time_str()))
        btn_in_now.pack(side=tk.RIGHT, padx=(3, 0))

        # Logout sub-box
        f_logout_sub = tk.Frame(f_inout, bg="#f8fafc")
        f_logout_sub.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        tk.Label(f_logout_sub, text="🕒 Logout Time:", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#334155").pack(anchor="w")
        b_out_box = tk.Frame(f_logout_sub, bg="#f8fafc")
        b_out_box.pack(fill=tk.X, pady=1)
        self.entry_form_logout = tk.Entry(b_out_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_form_logout.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self.entry_form_logout.insert(0, today_t.get("logout", "07:30 PM"))
        self.entry_form_logout.bind("<KeyRelease>", lambda e: self.update_shift_summary_badge())

        btn_out_now = tk.Button(b_out_box, text="Now", font=("Segoe UI", 7, "bold"), bg="#edf2f7", fg="#2563eb", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_entry_val(self.entry_form_logout, format_current_time_str()))
        btn_out_now.pack(side=tk.RIGHT, padx=(3, 0))

        # Row 2: Lunch Break - Header with Checkbox and Presets, Full-Width Entry below
        f_lunch_box = tk.Frame(f_shift, bg="#f8fafc")
        f_lunch_box.pack(fill=tk.X, pady=2)

        f_lunch_hdr = tk.Frame(f_lunch_box, bg="#f8fafc")
        f_lunch_hdr.pack(fill=tk.X)

        self.var_lunch_taken = tk.BooleanVar(value=bool(today_t.get("lunch_taken", bool(today_t.get("lunch")))))
        self.chk_lunch = tk.Checkbutton(f_lunch_hdr, text="🥪 Lunch Break", variable=self.var_lunch_taken, font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#334155", command=self.on_lunch_chk_toggle)
        self.chk_lunch.pack(side=tk.LEFT)

        f_l_presets = tk.Frame(f_lunch_hdr, bg="#f8fafc")
        f_l_presets.pack(side=tk.RIGHT)
        btn_l_1h = tk.Button(f_l_presets, text="1-2 PM", font=("Segoe UI", 7), bg="#edf2f7", fg="#475569", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_lunch_val("01:00 PM - 02:00 PM"))
        btn_l_1h.pack(side=tk.LEFT, padx=1)
        btn_l_45 = tk.Button(f_l_presets, text="45m", font=("Segoe UI", 7), bg="#edf2f7", fg="#475569", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_lunch_val("45 mins"))
        btn_l_45.pack(side=tk.LEFT, padx=1)

        self.entry_form_lunch = tk.Entry(f_lunch_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_form_lunch.pack(fill=tk.X, pady=(1, 2), ipady=2)
        self.entry_form_lunch.insert(0, today_t.get("lunch", "01:00 PM - 02:00 PM"))
        self.entry_form_lunch.bind("<KeyRelease>", lambda e: self.update_shift_summary_badge())

        # Row 3: Tea Break - Header with Checkbox and Presets, Full-Width Entry below
        f_tea_box = tk.Frame(f_shift, bg="#f8fafc")
        f_tea_box.pack(fill=tk.X, pady=2)

        f_tea_hdr = tk.Frame(f_tea_box, bg="#f8fafc")
        f_tea_hdr.pack(fill=tk.X)

        self.var_tea_taken = tk.BooleanVar(value=bool(today_t.get("tea_taken", bool(today_t.get("tea")))))
        self.chk_tea = tk.Checkbutton(f_tea_hdr, text="☕ Tea Break", variable=self.var_tea_taken, font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#334155", command=self.on_tea_chk_toggle)
        self.chk_tea.pack(side=tk.LEFT)

        f_t_presets = tk.Frame(f_tea_hdr, bg="#f8fafc")
        f_t_presets.pack(side=tk.RIGHT)
        btn_t_15 = tk.Button(f_t_presets, text="4:30-4:45", font=("Segoe UI", 7), bg="#edf2f7", fg="#475569", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_tea_val("04:30 PM - 04:45 PM"))
        btn_t_15.pack(side=tk.LEFT, padx=1)
        btn_t_20 = tk.Button(f_t_presets, text="15m", font=("Segoe UI", 7), bg="#edf2f7", fg="#475569", relief="flat", padx=4, pady=1, cursor="hand2", command=lambda: self.set_tea_val("15 mins"))
        btn_t_20.pack(side=tk.LEFT, padx=1)

        self.entry_form_tea = tk.Entry(f_tea_box, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_form_tea.pack(fill=tk.X, pady=(1, 2), ipady=2)
        self.entry_form_tea.insert(0, today_t.get("tea", "04:30 PM - 04:45 PM"))
        self.entry_form_tea.bind("<KeyRelease>", lambda e: self.update_shift_summary_badge())

        # Row 4: Live Net Shift Badge with dynamic wrap
        f_badge_row = tk.Frame(f_shift, bg="#f8fafc")
        f_badge_row.pack(fill=tk.X, pady=(2, 0))
        self.lbl_shift_badge = tk.Label(f_badge_row, text="⏱️ Shift: 9.0h | Net Work: 7.75 hrs", font=("Segoe UI", 8, "bold"), bg="#e0f2fe", fg="#0369a1", padx=6, pady=3, justify="left")
        self.lbl_shift_badge.pack(fill=tk.X)

        # Detailed Description
        f_desc = tk.Frame(form_inner, bg="#ffffff")
        f_desc.pack(fill=tk.X, pady=2)
        tk.Label(f_desc, text="Work Description / Details:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        self.text_desc = tk.Text(f_desc, font=("Segoe UI", 9), height=3, relief="solid", bd=1, wrap=tk.WORD)
        self.text_desc.pack(fill=tk.X, pady=1)

        # Remarks / Next Steps
        f_rem = tk.Frame(form_inner, bg="#ffffff")
        f_rem.pack(fill=tk.X, pady=2)
        tk.Label(f_rem, text="Remarks / Output Link / Docs:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2d3748").pack(anchor="w")
        self.entry_remarks = tk.Entry(f_rem, font=("Segoe UI", 9), relief="solid", bd=1)
        self.entry_remarks.pack(fill=tk.X, pady=1, ipady=2)

        # Initial badge update
        self.update_shift_summary_badge()

        # ----------------- RIGHT TABLE PANEL -----------------
        table_card = tk.Frame(self.main_paned, bg="#ffffff", bd=1, relief="solid")
        self.main_paned.add(table_card, minsize=520)

        # Initial sash placement after window layout completes
        def _set_initial_sash():
            self.root.update_idletasks()
            total_w = self.main_paned.winfo_width()
            if total_w > 100:
                scale = max(1.0, min(1.8, total_w / 1920.0))
                form_w = max(460, min(int(580 * scale), int(total_w * 0.32)))
                try:
                    self.main_paned.sash_place(0, form_w, 0)
                except Exception:
                    pass

        self.root.after(100, _set_initial_sash)

        filter_bar = tk.Frame(table_card, bg="#f8fafc", padx=10, pady=8, bd=0)
        filter_bar.pack(fill=tk.X, side=tk.TOP)

        tk.Label(filter_bar, text="📁 Month Tab:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_month = ttk.Combobox(filter_bar, textvariable=self.current_selected_month, state="readonly", width=16, font=("Segoe UI", 9, "bold"))
        self.combo_month.pack(side=tk.LEFT, padx=(0, 12))
        self.combo_month.bind("<<ComboboxSelected>>", lambda e: self.on_month_selected())

        tk.Label(filter_bar, text="🔍 Search:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_search = tk.Entry(filter_bar, textvariable=self.search_var, font=("Segoe UI", 9), relief="solid", bd=1, width=15)
        self.entry_search.pack(side=tk.LEFT, padx=(0, 12), ipady=2)
        self.search_var.trace_add("write", lambda *args: self.apply_filter())

        tk.Label(filter_bar, text="Status:", font=("Segoe UI", 9), bg="#f8fafc", fg="#475569").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_status_filter = ttk.Combobox(filter_bar, textvariable=self.filter_status_var, values=["All Statuses", "Completed", "In Progress", "Pending", "Under Review", "Blocked", "Weekly Off", "Holiday", "Leave"], state="readonly", width=12, font=("Segoe UI", 9))
        self.combo_status_filter.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_status_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        # Auto-Arrange Date-Wise Button
        btn_arrange = tk.Button(filter_bar, text="📅 Auto-Arrange Date-Wise", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=9, pady=3, cursor="hand2", command=self.auto_arrange_date_wise)
        btn_arrange.pack(side=tk.RIGHT, padx=(4, 0))

        btn_refresh = tk.Button(filter_bar, text="🔄 Refresh", font=("Segoe UI", 8, "bold"), bg="#edf2f7", fg="#334155", relief="flat", padx=8, pady=3, cursor="hand2", command=self.refresh_all)
        btn_refresh.pack(side=tk.RIGHT, padx=4)

        grid_frame = tk.Frame(table_card, bg="#ffffff")
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        columns = ("ID", "Date", "Project", "Task Title", "Hours", "Status", "Login", "Logout", "Lunch", "Tea", "Description", "Remarks")
        self.tree = ttk.Treeview(grid_frame, columns=columns, show="headings", selectmode="browse")

        self.tree_sort_col = "Date"
        self.tree_sort_desc = False

        self.column_headers = {
            "ID": "ID", "Date": "Date", "Project": "Project", "Task Title": "Task Summary / Title",
            "Hours": "Hours", "Status": "Status", "Login": "Login", "Logout": "Logout",
            "Lunch": "Lunch", "Tea": "Tea", "Description": "Work Description", "Remarks": "Remarks"
        }

        # Responsive column specifications: dynamically scaled to screen resolution
        screen_w = self.root.winfo_screenwidth()
        scale = max(1.0, min(1.8, screen_w / 1920.0))
        def sc(val):
            return int(val * scale)

        column_specs = {
            "ID": {"width": sc(115), "minwidth": 85, "anchor": "center"},
            "Date": {"width": sc(115), "minwidth": 95, "anchor": "center"},
            "Project": {"width": sc(160), "minwidth": 130, "anchor": "w"},
            "Task Title": {"width": sc(230), "minwidth": 160, "anchor": "w"},
            "Hours": {"width": sc(70), "minwidth": 55, "anchor": "center"},
            "Status": {"width": sc(105), "minwidth": 85, "anchor": "center"},
            "Login": {"width": sc(90), "minwidth": 75, "anchor": "center"},
            "Logout": {"width": sc(90), "minwidth": 75, "anchor": "center"},
            "Lunch": {"width": sc(160), "minwidth": 120, "anchor": "center"},
            "Tea": {"width": sc(150), "minwidth": 110, "anchor": "center"},
            "Description": {"width": sc(280), "minwidth": 180, "anchor": "w"},
            "Remarks": {"width": sc(150), "minwidth": 100, "anchor": "w"},
        }

        for col_id, spec in column_specs.items():
            arrow = " 🔼" if col_id == "Date" else ""
            self.tree.heading(col_id, text=f"{self.column_headers[col_id]}{arrow}", command=lambda c=col_id: self.on_tree_header_click(c))
            self.tree.column(col_id, width=spec["width"], minwidth=spec["minwidth"], anchor=spec["anchor"], stretch=True)

        # Treeview tag styling for holidays, weekly offs, and leaves
        self.tree.tag_configure("holiday", background="#fef9c3", foreground="#854d0e")
        self.tree.tag_configure("weekly_off", background="#dbeafe", foreground="#1e40af")
        self.tree.tag_configure("leave", background="#fce7f3", foreground="#9d174d")
        self.tree.tag_configure("normal", background="#ffffff", foreground="#0f172a")

        v_scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_row_double_click)

        # Bottom Action Buttons Bar
        action_bar = tk.Frame(table_card, bg="#f8fafc", padx=10, pady=8)
        action_bar.pack(fill=tk.X, side=tk.BOTTOM)

        f_act_btns = tk.Frame(action_bar, bg="#f8fafc")
        f_act_btns.pack(side=tk.LEFT)

        self.btn_edit = tk.Button(f_act_btns, text="✏️ Edit Selected", font=("Segoe UI", 9, "bold"), bg="#3b82f6", fg="white", activebackground="#2563eb", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.load_selected_into_form)
        self.btn_edit.pack(side=tk.LEFT, padx=3)

        self.btn_del = tk.Button(f_act_btns, text="🗑️ Delete Selected", font=("Segoe UI", 9, "bold"), bg="#ef4444", fg="white", activebackground="#dc2626", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.delete_selected)
        self.btn_del.pack(side=tk.LEFT, padx=3)

        btn_action_leave = tk.Button(f_act_btns, text="🌴 Mark Leave", font=("Segoe UI", 9, "bold"), bg="#fce7f3", fg="#be185d", activebackground="#fbcfe8", relief="flat", padx=10, pady=4, cursor="hand2", command=self.open_add_leave_dialog)
        btn_action_leave.pack(side=tk.LEFT, padx=3)

        btn_share_today = tk.Button(f_act_btns, text="📢 Share Today's Log", font=("Segoe UI", 9, "bold"), bg="#8b5cf6", fg="white", activebackground="#7c3aed", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.share_current_view_with_team)
        btn_share_today.pack(side=tk.LEFT, padx=3)

        btn_sync_api_tbl = tk.Button(f_act_btns, text="🔄 Sync All to API", font=("Segoe UI", 9, "bold"), bg="#0d9488", fg="white", activebackground="#0f766e", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.open_sync_api_dialog)
        btn_sync_api_tbl.pack(side=tk.LEFT, padx=3)

        btn_sync_gsheet_tbl = tk.Button(f_act_btns, text="📊 Sync to Google Sheet", font=("Segoe UI", 9, "bold"), bg="#0f9d58", fg="white", activebackground="#0b8043", activeforeground="white", relief="flat", padx=10, pady=4, cursor="hand2", command=self.open_google_sheet_sync_dialog)
        btn_sync_gsheet_tbl.pack(side=tk.LEFT, padx=3)

        tip_lbl = tk.Label(action_bar, text="💡 Tip: Click 'Share Today's Log' to copy Markdown with Shift Timings to Teams/Slack", font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#f8fafc", wraplength=350, justify="right")
        tip_lbl.pack(side=tk.RIGHT, padx=5)

    def create_status_bar(self):
        f_status = tk.Frame(self.root, bg="#edf2f7", bd=1, relief=tk.SUNKEN)
        f_status.pack(side=tk.BOTTOM, fill=tk.X)

        self.status = tk.Label(f_status, text="Ready | Excel File: data.xlsx", anchor=tk.W, font=("Segoe UI", 8), bg="#edf2f7", fg="#475569", padx=10, pady=3)
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_stat_settings = tk.Button(f_status, text="⚙️ Settings (Ctrl+,)", font=("Segoe UI", 8), bg="#edf2f7", fg="#334155", activebackground="#e2e8f0", relief="flat", padx=8, pady=1, cursor="hand2", command=self.open_settings)
        btn_stat_settings.pack(side=tk.RIGHT, padx=6)

    # ---------- Shift & Break Form Helpers ----------
    def set_entry_val(self, entry_widget, val):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, val)
        self.update_shift_summary_badge()

    def set_lunch_val(self, val):
        self.var_lunch_taken.set(True)
        self.entry_form_lunch.config(state=tk.NORMAL)
        self.set_entry_val(self.entry_form_lunch, val)

    def set_tea_val(self, val):
        self.var_tea_taken.set(True)
        self.entry_form_tea.config(state=tk.NORMAL)
        self.set_entry_val(self.entry_form_tea, val)

    def on_lunch_chk_toggle(self):
        if self.var_lunch_taken.get():
            self.entry_form_lunch.config(state=tk.NORMAL)
            if not self.entry_form_lunch.get().strip():
                self.entry_form_lunch.insert(0, "02:00 PM - 02:45 PM")
        else:
            self.entry_form_lunch.config(state=tk.DISABLED)
        self.update_shift_summary_badge()

    def on_tea_chk_toggle(self):
        if self.var_tea_taken.get():
            self.entry_form_tea.config(state=tk.NORMAL)
            if not self.entry_form_tea.get().strip():
                self.entry_form_tea.insert(0, "05:00 PM - 05:15 PM")
        else:
            self.entry_form_tea.config(state=tk.DISABLED)
        self.update_shift_summary_badge()

    def update_shift_summary_badge(self):
        login_v = self.entry_form_login.get().strip() if hasattr(self, 'entry_form_login') else ""
        logout_v = self.entry_form_logout.get().strip() if hasattr(self, 'entry_form_logout') else ""
        lunch_v = self.entry_form_lunch.get().strip() if (hasattr(self, 'entry_form_lunch') and self.var_lunch_taken.get()) else ""
        tea_v = self.entry_form_tea.get().strip() if (hasattr(self, 'entry_form_tea') and self.var_tea_taken.get()) else ""

        net_h, net_str, span_h, l_m, t_m = calculate_net_working_hours(
            login_v, logout_v, lunch_v, tea_v,
            lunch_taken=bool(lunch_v), tea_taken=bool(tea_v)
        )
        if hasattr(self, 'lbl_shift_badge'):
            if net_h > 0:
                breaks_info = []
                if l_m > 0:
                    breaks_info.append(f"Lunch: {int(l_m)}m")
                if t_m > 0:
                    breaks_info.append(f"Tea: {int(t_m)}m")
                b_str = f" ({', '.join(breaks_info)})" if breaks_info else ""
                span_text = format_human_time(span_h)
                net_text = format_human_time(net_h)
                self.lbl_shift_badge.config(
                    text=f"⏱️ Span: {span_text} | Net Work: {net_text} ({net_str} hrs){b_str}",
                    bg="#e0f2fe", fg="#0369a1"
                )
            else:
                self.lbl_shift_badge.config(
                    text="⏱️ Shift & Break Timings Optional",
                    bg="#f1f5f9", fg="#64748b"
                )

        # Real-time Auto-Calculation of Hours Spent from Shift & Breaks
        if hasattr(self, 'entry_hours') and hasattr(self, 'var_auto_calc_hours'):
            if self.var_auto_calc_hours.get() and net_h > 0:
                cur_val = self.entry_hours.get().strip()
                if cur_val != net_str:
                    self.entry_hours.delete(0, tk.END)
                    self.entry_hours.insert(0, net_str)

    def on_hours_manual_edit(self):
        # When user manually types custom hours, disable auto-calc so it preserves their input
        if hasattr(self, 'var_auto_calc_hours'):
            self.var_auto_calc_hours.set(False)

    def on_auto_calc_toggle(self):
        if self.var_auto_calc_hours.get():
            self.apply_calculated_hours_to_entry()

    def apply_calculated_hours_to_entry(self):
        login_v = self.entry_form_login.get().strip() if hasattr(self, 'entry_form_login') else ""
        logout_v = self.entry_form_logout.get().strip() if hasattr(self, 'entry_form_logout') else ""
        lunch_v = self.entry_form_lunch.get().strip() if (hasattr(self, 'entry_form_lunch') and self.var_lunch_taken.get()) else ""
        tea_v = self.entry_form_tea.get().strip() if (hasattr(self, 'entry_form_tea') and self.var_tea_taken.get()) else ""

        net_h, net_str, span_h, _, _ = calculate_net_working_hours(
            login_v, logout_v, lunch_v, tea_v,
            lunch_taken=bool(lunch_v), tea_taken=bool(tea_v)
        )
        if net_h > 0:
            if hasattr(self, 'var_auto_calc_hours'):
                self.var_auto_calc_hours.set(True)
            self.entry_hours.delete(0, tk.END)
            self.entry_hours.insert(0, net_str)
            self.status.config(text=f"⚡ Auto-calculated {net_str} net working hours from shift (Logout: {logout_v} - Login: {login_v} minus breaks).")
        else:
            messagebox.showwarning("Incomplete Shift", "Please enter both Login Time and Logout Time (e.g., 10:00 AM and 07:30 PM) to calculate hours.")

    def on_date_changed(self):
        date_str = self.entry_date.get().strip()
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            t = get_daily_timings(date_str)
            if hasattr(self, 'entry_form_login'):
                self.set_entry_val(self.entry_form_login, t.get("login", ""))
                self.set_entry_val(self.entry_form_logout, t.get("logout", ""))
                l_taken = bool(t.get("lunch_taken", bool(t.get("lunch"))))
                self.var_lunch_taken.set(l_taken)
                self.entry_form_lunch.config(state=tk.NORMAL if l_taken else tk.DISABLED)
                self.set_entry_val(self.entry_form_lunch, t.get("lunch", "01:00 PM - 02:00 PM") if l_taken else "")
                
                t_taken = bool(t.get("tea_taken", bool(t.get("tea"))))
                self.var_tea_taken.set(t_taken)
                self.entry_form_tea.config(state=tk.NORMAL if t_taken else tk.DISABLED)
                self.set_entry_val(self.entry_form_tea, t.get("tea", "04:30 PM - 04:45 PM") if t_taken else "")
                self.update_shift_summary_badge()
        except ValueError:
            pass

    # ---------- Modal Openers ----------
    def open_bulk_import_dialog(self):
        BulkImportDialog(self.root, on_import_success=self.on_bulk_import_complete)

    def open_excel_bulk_import_dialog(self):
        ExcelBulkImportDialog(self.root, on_import_success=self.on_bulk_import_complete)

    def open_weekend_holiday_settings(self):
        WeekendHolidayDialog(self.root, on_sync_callback=self.refresh_all)

    def open_add_leave_dialog(self):
        curr_d = self.entry_date.get().strip() if hasattr(self, 'entry_date') else datetime.datetime.now().strftime("%Y-%m-%d")
        AddLeaveDialog(self.root, default_date=curr_d, on_success_callback=self.refresh_all)

    def open_settings(self):
        SettingsDialog(self.root, app_ref=self)

    def open_lan_chat(self):
        """Opens or brings to focus the LAN Team Chat dialog."""
        self.unread_lan_messages = 0
        if hasattr(self, 'btn_chat'):
            self.btn_chat.config(text="💬 LAN Chat", bg="#4f46e5")

        if self.chat_dialog and hasattr(self.chat_dialog, "dialog") and self.chat_dialog.dialog.winfo_exists():
            try:
                self.chat_dialog.dialog.deiconify()
                self.chat_dialog.dialog.lift()
                self.chat_dialog.dialog.focus_force()
                return
            except Exception:
                pass

        self.chat_dialog = LANChatDialog(self.root, self.lan_engine, self)

    def _handle_background_lan_message(self, msg_obj):
        """Called by LANChatEngine when a message arrives."""
        is_dialog_open = bool(self.chat_dialog and hasattr(self.chat_dialog, "dialog") and self.chat_dialog.dialog.winfo_exists())
        if not is_dialog_open and not msg_obj.get("is_me", False):
            self.unread_lan_messages += 1
            self.root.after(0, self._update_chat_button_badge)

    def _update_chat_button_badge(self):
        if hasattr(self, 'btn_chat'):
            if self.unread_lan_messages > 0:
                self.btn_chat.config(
                    text=f"💬 LAN Chat ({self.unread_lan_messages})",
                    bg="#ea580c"
                )
                try:
                    self.root.bell()
                except Exception:
                    pass
            else:
                self.btn_chat.config(text="💬 LAN Chat", bg="#4f46e5")

    def _handle_lan_peers_change(self, peer_list):
        """Updates main window LAN presence indicator."""
        self.root.after(0, lambda: self._update_lan_status_label(peer_list))

    def _update_lan_status_label(self, peer_list):
        if hasattr(self, 'lbl_stat_lan'):
            count = len(peer_list)
            if count == 0:
                self.lbl_stat_lan.config(text="💬 LAN: 0 online", fg="#64748b")
            elif count == 1:
                self.lbl_stat_lan.config(text=f"💬 LAN: 1 online ({peer_list[0]['user_name']})", fg="#059669")
            else:
                self.lbl_stat_lan.config(text=f"💬 LAN: {count} online", fg="#059669")

    def on_app_closing(self):
        """Gracefully stop background LAN chat and exit application."""
        try:
            if hasattr(self, 'lan_engine') and self.lan_engine:
                self.lan_engine.stop()
        except Exception:
            pass
        self.root.destroy()

    def open_sync_api_dialog(self):
        SyncApiDialog(self.root)

    def open_google_sheet_sync_dialog(self):
        GoogleSheetSyncDialog(self.root, app_ref=self)

    def on_status_changed(self):
        st = self.combo_status.get()
        if st == "Leave":
            if not self.combo_project.get() or self.combo_project.get() == "General Work":
                self.combo_project.set("Leave")
            if not self.entry_title.get() or self.entry_title.get() == "Untitled Task":
                self.entry_title.delete(0, tk.END)
                self.entry_title.insert(0, "Casual Leave (CL)")
            self.entry_hours.delete(0, tk.END)
            self.entry_hours.insert(0, "0.0")
            if hasattr(self, 'var_auto_calc_hours'):
                self.var_auto_calc_hours.set(False)
            if hasattr(self, 'entry_form_login'):
                self.set_entry_val(self.entry_form_login, "-")
                self.set_entry_val(self.entry_form_logout, "-")
            if hasattr(self, 'var_lunch_taken'):
                self.var_lunch_taken.set(False)
                self.entry_form_lunch.config(state=tk.DISABLED)
                self.set_entry_val(self.entry_form_lunch, "")
            if hasattr(self, 'var_tea_taken'):
                self.var_tea_taken.set(False)
                self.entry_form_tea.config(state=tk.DISABLED)
                self.set_entry_val(self.entry_form_tea, "")
            self.update_shift_summary_badge()

    def get_all_categorized_tasks(self, for_date=None):
        """Extracts today's tasks, month tasks, and selected tasks normalized by date."""
        target_date = format_date_only(for_date) if for_date else datetime.datetime.now().strftime("%Y-%m-%d")
        selected_month = self.current_selected_month.get() or datetime.datetime.now().strftime("%B %Y")

        month_records = load_month_records(selected_month)
        
        # Also check calendar month if different
        cal_month = datetime.datetime.now().strftime("%B %Y")
        all_pool_records = list(month_records)
        if cal_month != selected_month:
            for r in load_month_records(cal_month):
                all_pool_records.append(r)

        today_tasks = []
        month_tasks = []
        default_proj = "General Work"

        # Month tasks
        for r in month_records:
            if len(r) >= 8:
                proj = str(r[2] or "").strip()
                if proj:
                    default_proj = proj
                month_tasks.append({
                    "date": format_date_only(r[1]),
                    "title": str(r[3] or "Task"),
                    "desc": str(r[4] or ""),
                    "hours": str(r[5] or "") if r[5] is not None and str(r[5]) != "-" else "",
                    "status": str(r[6] or "Completed"),
                    "remarks": str(r[7] or ""),
                    "project": proj,
                    "login": str(r[8] or "") if len(r) >= 13 else "",
                    "logout": str(r[9] or "") if len(r) >= 13 else "",
                    "lunch": str(r[10] or "") if len(r) >= 13 else "",
                    "tea": str(r[11] or "") if len(r) >= 13 else ""
                })

        # Today tasks (all records matching target_date)
        seen_ids = set()
        for r in all_pool_records:
            if len(r) >= 8:
                r_id = str(r[0])
                if r_id in seen_ids:
                    continue
                r_date = format_date_only(r[1])
                if r_date == target_date:
                    seen_ids.add(r_id)
                    proj = str(r[2] or "").strip()
                    if proj:
                        default_proj = proj
                    today_tasks.append({
                        "title": str(r[3] or "Task"),
                        "desc": str(r[4] or ""),
                        "hours": str(r[5] or "") if r[5] is not None and str(r[5]) != "-" else "",
                        "status": str(r[6] or "Completed"),
                        "remarks": str(r[7] or ""),
                        "project": proj,
                        "login": str(r[8] or "") if len(r) >= 13 else "",
                        "logout": str(r[9] or "") if len(r) >= 13 else "",
                        "lunch": str(r[10] or "") if len(r) >= 13 else "",
                        "tea": str(r[11] or "") if len(r) >= 13 else ""
                    })

        # Selected tasks in Treeview
        selected_tasks = []
        if hasattr(self, 'tree'):
            selected_items = self.tree.selection()
            for sel in selected_items:
                vals = self.tree.item(sel)["values"]
                if vals and len(vals) >= 12:
                    proj = str(vals[2] or "").strip()
                    selected_tasks.append({
                        "title": str(vals[3] or "Task"),
                        "desc": str(vals[10] or ""),
                        "hours": str(vals[4] or "") if vals[4] is not None and str(vals[4]) != "-" else "",
                        "status": str(vals[5] or "Completed"),
                        "remarks": str(vals[11] or ""),
                        "project": proj,
                        "login": str(vals[6] or "") if str(vals[6]) != "-" else "",
                        "logout": str(vals[7] or "") if str(vals[7]) != "-" else "",
                        "lunch": str(vals[8] or "") if str(vals[8]) != "-" else "",
                        "tea": str(vals[9] or "") if str(vals[9]) != "-" else ""
                    })

        date_timings = get_daily_timings(target_date)

        return {
            "today": today_tasks,
            "month": month_tasks,
            "selected": selected_tasks,
            "date": target_date,
            "default_project": default_proj,
            "timings": date_timings
        }

    def on_bulk_import_complete(self, target_month, date_str, project, tasks_list, prompt_share=False):
        if target_month:
            self.refresh_month_dropdown(select_month=target_month)
        self.refresh_table()
        self.combo_project['values'] = get_distinct_projects()
        num_tasks = len(tasks_list) if tasks_list else 0
        self.status.config(text=f"✅ Bulk imported {num_tasks} tasks into tab '{target_month}' at {datetime.datetime.now().strftime('%H:%M:%S')}")

        settings = load_settings()
        if prompt_share and settings.get("prompt_team_share_on_save", True):
            data = self.get_all_categorized_tasks(for_date=date_str)
            ShareTeamDialog(self.root, data["date"], data["default_project"], data, initial_scope="today")

    def share_current_view_with_team(self):
        """Generates team summary from all today's tasks and opens Share dialog."""
        data = self.get_all_categorized_tasks()
        if not data["today"] and not data["month"]:
            messagebox.showinfo("No Records", "No records found in this month tab to share.")
            return

        initial_scope = "selected" if data["selected"] else "today"
        ShareTeamDialog(self.root, data["date"], data["default_project"], data, initial_scope=initial_scope)

    # ---------- Form Controls & Handlers ----------
    def set_today_date(self):
        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        self.on_date_changed()

    def clear_form(self):
        self.editing_record_id = None
        self.set_today_date()
        self.entry_title.delete(0, tk.END)
        self.entry_hours.delete(0, tk.END)
        if hasattr(self, 'var_auto_calc_hours'):
            self.var_auto_calc_hours.set(True)
        self.combo_status.set("Completed")
        self.text_desc.delete("1.0", tk.END)
        self.entry_remarks.delete(0, tk.END)
        self.update_shift_summary_badge()

        self.btn_save.config(text="💾 Save Work Update", bg="#2563eb")
        if hasattr(self, 'tree') and self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.status.config(text="Form cleared. Ready to add new update.")

    def save_record(self):
        date_val = self.entry_date.get().strip()
        project_val = self.combo_project.get().strip()
        title_val = self.entry_title.get().strip()
        hours_val = self.entry_hours.get().strip()
        status_val = self.combo_status.get().strip()
        desc_val = self.text_desc.get("1.0", tk.END).strip()
        remarks_val = self.entry_remarks.get().strip()

        login_val = self.entry_form_login.get().strip()
        logout_val = self.entry_form_logout.get().strip()
        lunch_val = self.entry_form_lunch.get().strip() if self.var_lunch_taken.get() else ""
        tea_val = self.entry_form_tea.get().strip() if self.var_tea_taken.get() else ""

        if not date_val:
            messagebox.showwarning("Validation Error", "Please provide a Date (YYYY-MM-DD).")
            self.entry_date.focus_set()
            return

        try:
            datetime.datetime.strptime(date_val, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Date must be in format YYYY-MM-DD (e.g., 2026-10-07).")
            self.entry_date.focus_set()
            return

        if not project_val:
            messagebox.showwarning("Validation Error", "Please enter or select a Project/Module.")
            self.combo_project.focus_set()
            return

        if not title_val:
            messagebox.showwarning("Validation Error", "Please enter a Task Summary / Title.")
            self.entry_title.focus_set()
            return

        if hours_val:
            val, formatted_val = parse_duration_to_hours(hours_val)
            if val < 0:
                messagebox.showerror("Invalid Hours", "Hours Spent cannot be negative.")
                self.entry_hours.focus_set()
                return
            if val == 0.0 and str(hours_val).strip() not in ("0", "0.0", "0 hrs"):
                messagebox.showerror("Invalid Hours", "Hours Spent must be a valid number (e.g. 1.5, 8.85, 8 hrs 51 mins, 8:51) or left blank.")
                self.entry_hours.focus_set()
                return
            hours_val = formatted_val
        else:
            if login_val and logout_val:
                net_h, net_str, _, _, _ = calculate_net_working_hours(
                    login_val, logout_val, lunch_val, tea_val,
                    lunch_taken=bool(lunch_val), tea_taken=bool(tea_val)
                )
                if net_h > 0:
                    hours_val = net_str
                else:
                    hours_val = ""
            else:
                hours_val = ""

        target_month = get_month_sheet_name(date_val)

        success = save_work_update(
            date_str=date_val,
            project=project_val,
            task_title=title_val,
            description=desc_val,
            hours=hours_val,
            status_val=status_val,
            remarks=remarks_val,
            login_time=login_val,
            logout_time=logout_val,
            lunch_break=lunch_val,
            tea_break=tea_val,
            record_id=self.editing_record_id
        )

        if success:
            is_edit = bool(self.editing_record_id)
            saved_rec_id = self.editing_record_id or f"WU-{datetime.datetime.now().strftime('%y%m%d-%H%M%S')}"
            action_type = "Updated" if is_edit else "Added"
            self.status.config(text=f"✅ {action_type} successfully in sheet '{target_month}' at {datetime.datetime.now().strftime('%H:%M:%S')}")
            
            self.refresh_month_dropdown(select_month=target_month)
            self.refresh_table()
            self.combo_project['values'] = get_distinct_projects()

            # Team share prompt / auto copy with ALL today's tasks
            settings = load_settings()
            data = self.get_all_categorized_tasks(for_date=date_val)
            timings_obj = {
                "login": login_val,
                "logout": logout_val,
                "lunch": lunch_val,
                "tea": tea_val,
                "lunch_taken": bool(lunch_val),
                "tea_taken": bool(tea_val)
            }
            all_today_md = generate_team_markdown(
                date_val, project_val, data["today"],
                settings.get("user_name", "Developer"), timings=timings_obj
            )
            
            if settings.get("auto_copy_on_save", True):
                self.root.clipboard_clear()
                self.root.clipboard_append(all_today_md)

            if settings.get("prompt_team_share_on_save", True):
                ShareTeamDialog(self.root, data["date"], data["default_project"], data, initial_scope="today")

            # Data API Webhook trigger on Edit/Update or Create
            api_url = settings.get("data_api_url", "").strip()
            should_sync_api = False
            if api_url:
                if is_edit and settings.get("data_api_sync_on_edit", True):
                    should_sync_api = True
                    event_type = "update"
                    action_name = "edit"
                elif not is_edit and settings.get("data_api_sync_on_create", True):
                    should_sync_api = True
                    event_type = "create"
                    action_name = "create"

            if should_sync_api:
                record_payload = {
                    "id": saved_rec_id,
                    "date": date_val,
                    "sheet": target_month,
                    "project": project_val,
                    "task_title": title_val,
                    "description": desc_val,
                    "hours": hours_val,
                    "status": status_val,
                    "remarks": remarks_val,
                    "login_time": login_val,
                    "logout_time": logout_val,
                    "lunch_break": lunch_val,
                    "tea_break": tea_val,
                    "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                api_payload = {
                    "event": event_type,
                    "action": action_name,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_name": settings.get("user_name", "Developer"),
                    "record": record_payload,
                    "data": record_payload
                }
                def _trigger_api_webhook(payload_to_send, act_type):
                    ok, resp_str, status_code = send_data_api_webhook(payload_to_send)
                    if ok:
                        self.root.after(0, lambda: self.status.config(
                            text=f"✅ {act_type} & Webhook delivered to API ({status_code}) at {datetime.datetime.now().strftime('%H:%M:%S')}"
                        ))
                    else:
                        self.root.after(0, lambda: self.status.config(
                            text=f"⚠️ {act_type} locally, but Webhook failed: {resp_str[:60]}"
                        ))

                threading.Thread(target=_trigger_api_webhook, args=(api_payload, action_type), daemon=True).start()

            # Google Sheet Auto-Sync Trigger
            trigger_google_sheet_auto_sync(target_month, app_ref=self)

            self.clear_form()

    def load_selected_into_form(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a row from the table to edit.")
            return

        item = self.tree.item(selected[0])
        values = item["values"]

        self.editing_record_id = str(values[0])
        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, str(values[1]))

        self.combo_project.set(str(values[2]))

        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, str(values[3]))

        self.entry_hours.delete(0, tk.END)
        hrs_val = str(values[4]) if values[4] is not None and str(values[4]) != "-" else ""
        if hrs_val:
            self.entry_hours.insert(0, hrs_val)
            if hasattr(self, 'var_auto_calc_hours'):
                self.var_auto_calc_hours.set(False)
        else:
            if hasattr(self, 'var_auto_calc_hours'):
                self.var_auto_calc_hours.set(True)

        self.combo_status.set(str(values[5]))

        # Login, Logout, Lunch, Tea
        if len(values) >= 12:
            login_v = str(values[6]) if values[6] != "-" else ""
            logout_v = str(values[7]) if values[7] != "-" else ""
            lunch_v = str(values[8]) if values[8] != "-" else ""
            tea_v = str(values[9]) if values[9] != "-" else ""
            desc_v = str(values[10])
            rem_v = str(values[11])
        else:
            login_v = ""
            logout_v = ""
            lunch_v = ""
            tea_v = ""
            desc_v = str(values[6]) if len(values) > 6 else ""
            rem_v = str(values[7]) if len(values) > 7 else ""

        self.set_entry_val(self.entry_form_login, login_v)
        self.set_entry_val(self.entry_form_logout, logout_v)

        l_taken = bool(lunch_v)
        self.var_lunch_taken.set(l_taken)
        self.entry_form_lunch.config(state=tk.NORMAL if l_taken else tk.DISABLED)
        self.set_entry_val(self.entry_form_lunch, lunch_v if l_taken else "")

        t_taken = bool(tea_v)
        self.var_tea_taken.set(t_taken)
        self.entry_form_tea.config(state=tk.NORMAL if t_taken else tk.DISABLED)
        self.set_entry_val(self.entry_form_tea, tea_v if t_taken else "")

        self.update_shift_summary_badge()

        self.text_desc.delete("1.0", tk.END)
        self.text_desc.insert("1.0", desc_v)

        self.entry_remarks.delete(0, tk.END)
        self.entry_remarks.insert(0, rem_v)

        self.btn_save.config(text="✏️ Update Work Record", bg="#d97706")
        self.status.config(text=f"Editing record {self.editing_record_id}...")

    def on_row_double_click(self, event):
        self.load_selected_into_form()

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a row to delete.")
            return

        item = self.tree.item(selected[0])
        values = item["values"]
        rec_id = str(values[0])
        task_title = str(values[3])
        current_month = self.current_selected_month.get()

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this task:\n\n'{task_title}' (ID: {rec_id})?")
        if not confirm:
            return

        deleted = delete_work_update(rec_id, current_month)
        if deleted:
            self.refresh_table()
            if self.editing_record_id == rec_id:
                self.clear_form()
            self.status.config(text=f"🗑️ Deleted record {rec_id} from {current_month}.")

            # Data API Webhook trigger on Delete
            settings = load_settings()
            if settings.get("data_api_url") and settings.get("data_api_sync_on_delete", True):
                del_payload = {
                    "event": "delete",
                    "action": "delete",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_name": settings.get("user_name", "Developer"),
                    "record": {
                        "id": rec_id,
                        "task_title": task_title,
                        "sheet": current_month
                    },
                    "data": {
                        "id": rec_id,
                        "task_title": task_title,
                        "sheet": current_month
                    }
                }
                threading.Thread(target=lambda: send_data_api_webhook(del_payload), daemon=True).start()

            # Google Sheet Auto-Sync on Delete
            trigger_google_sheet_auto_sync(current_month, app_ref=self)
        else:
            messagebox.showerror("Error", "Could not delete record. Please check file permissions.")

    # ---------- Navigation & Refresh ----------
    def refresh_month_dropdown(self, select_month=None):
        months = get_available_months()
        self.combo_month['values'] = months
        if select_month and select_month in months:
            self.current_selected_month.set(select_month)
        elif not self.current_selected_month.get() or self.current_selected_month.get() not in months:
            current_now = datetime.datetime.now().strftime("%B %Y")
            if current_now in months:
                self.current_selected_month.set(current_now)
            elif months:
                self.current_selected_month.set(months[0])

    def on_month_selected(self):
        self.refresh_table()
        self.status.config(text=f"Switched to Month Tab: {self.current_selected_month.get()}")

    def refresh_all(self):
        self.refresh_month_dropdown(select_month=self.current_selected_month.get())
        self.refresh_table()
        self.combo_project['values'] = get_distinct_projects()
        self.status.config(text="Data refreshed from Excel.")

    def refresh_table(self):
        selected_month = self.current_selected_month.get()
        if not selected_month:
            return

        settings = load_settings()
        # Automatically populate missing weekends and holidays for this month!
        if settings.get("auto_sync_weekends_holidays", True):
            sync_month_holidays_and_weekly_offs(selected_month, silent=True)
        elif settings.get("auto_arrange_by_date", True):
            asc = (settings.get("date_sort_order", "asc") == "asc")
            # Ensure file is saved date-wise
            auto_arrange_sheet_by_date(selected_month, ascending=asc)

        records = load_month_records(selected_month)
        self.raw_records = records
        self.apply_filter()
        try:
            self.tree.xview_moveto(0)
        except Exception:
            pass

    def on_tree_header_click(self, col):
        if getattr(self, "tree_sort_col", "Date") == col:
            self.tree_sort_desc = not getattr(self, "tree_sort_desc", False)
        else:
            self.tree_sort_col = col
            self.tree_sort_desc = False

        if hasattr(self, "column_headers"):
            for col_id, col_name in self.column_headers.items():
                arrow = ""
                if col_id == self.tree_sort_col:
                    arrow = " 🔽" if self.tree_sort_desc else " 🔼"
                self.tree.heading(col_id, text=f"{col_name}{arrow}")

        self.apply_filter()

    def auto_arrange_date_wise(self):
        selected_month = self.current_selected_month.get()
        if not selected_month:
            return
        settings = load_settings()
        asc = (settings.get("date_sort_order", "asc") == "asc")
        success = auto_arrange_sheet_by_date(selected_month, ascending=asc)
        self.tree_sort_col = "Date"
        self.tree_sort_desc = not asc
        if hasattr(self, "column_headers"):
            for col_id, col_name in self.column_headers.items():
                arrow = (" 🔼" if asc else " 🔽") if col_id == "Date" else ""
                self.tree.heading(col_id, text=f"{col_name}{arrow}")
        self.refresh_table()
        if success:
            self.status.config(text=f"✅ Sheet '{selected_month}' auto-arranged chronologically date-wise!")
            messagebox.showinfo("Auto-Arrange Complete", f"✅ Sheet '{selected_month}' has been automatically arranged date-wise!\n\nAll records, shift timings, weekends, and holidays are now in chronological order.")
        else:
            self.status.config(text=f"⚠️ Could not auto-arrange sheet '{selected_month}'.")

    def apply_filter(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        search_text = self.search_var.get().lower().strip()
        status_filter = self.filter_status_var.get()

        total_tasks = 0
        total_hours = 0.0
        completed_count = 0
        leave_count = 0
        daily_hours_map = defaultdict(float)
        daily_meta = defaultdict(lambda: {
            "has_work": False, "is_off": False, "is_holiday": False, "is_leave": False, "task_count": 0
        })

        records_to_display = list(getattr(self, "raw_records", []))
        sort_col = getattr(self, "tree_sort_col", "Date")
        sort_desc = getattr(self, "tree_sort_desc", False)

        def tree_sort_key(r):
            if sort_col == "Date":
                raw_d = str(r[1] or "").strip()
                norm_d = format_date_only(raw_d)
                try:
                    dt = datetime.datetime.strptime(norm_d, "%Y-%m-%d").date()
                except Exception:
                    dt = datetime.date(2099, 12, 31)

                st = str(r[6] or "").lower() if len(r) > 6 else ""
                pj = str(r[2] or "").lower() if len(r) > 2 else ""
                prio = 0 if "holiday" in st or "holiday" in pj else (1 if "weekly off" in st or "weekly off" in pj or "weekend" in st else (2 if "leave" in st or "leave" in pj else 3))
                t_val = parse_time_to_minutes(str(r[8] or "")) if len(r) > 8 else 9999
                if t_val is None:
                    t_val = 9999
                return (dt, prio, t_val, str(r[0] or ""))
            elif sort_col == "Hours":
                try:
                    return float(str(r[5] or 0).replace(" hrs", "").strip())
                except Exception:
                    return 0.0
            elif sort_col == "ID":
                return str(r[0] or "")
            elif sort_col == "Project":
                return str(r[2] or "").lower()
            elif sort_col == "Task Title":
                return str(r[3] or "").lower()
            elif sort_col == "Status":
                return str(r[6] or "").lower()
            else:
                return str(r[1] or "")

        try:
            records_to_display.sort(key=tree_sort_key, reverse=sort_desc)
        except Exception:
            pass

        for r in records_to_display:
            if len(r) < 8:
                continue

            r_id = str(r[0] or "")
            r_date = str(r[1] or "")
            r_proj = str(r[2] or "")
            r_title = str(r[3] or "")
            r_desc = str(r[4] or "")
            r_hours = str(r[5] or "").strip()
            r_status = str(r[6] or "")
            r_remarks = str(r[7] or "")

            if len(r) >= 13:
                r_login = str(r[8] or "").strip()
                r_logout = str(r[9] or "").strip()
                r_lunch = str(r[10] or "").strip()
                r_tea = str(r[11] or "").strip()
            else:
                r_login, r_logout, r_lunch, r_tea = "", "", "", ""

            if status_filter != "All Statuses" and r_status != status_filter:
                continue

            combined_search_str = f"{r_id} {r_date} {r_proj} {r_title} {r_desc} {r_status} {r_remarks} {r_login} {r_logout} {r_lunch} {r_tea}".lower()
            if search_text and search_text not in combined_search_str:
                continue

            total_tasks += 1
            h_float = 0.0
            if r_hours:
                try:
                    h_float = float(r_hours)
                except Exception:
                    h_float, _ = parse_duration_to_hours(r_hours)
                total_hours += h_float

            if r_status == "Completed":
                completed_count += 1
            if "leave" in r_status.lower() or "leave" in r_proj.lower():
                leave_count += 1

            norm_date = format_date_only(r_date)
            st_lower = r_status.lower()
            pj_lower = r_proj.lower()
            tt_lower = r_title.lower()
            is_w_off = ("weekly off" in st_lower or "weekly off" in pj_lower or "weekly off" in tt_lower or "weekend" in st_lower or "weekend" in pj_lower)
            is_hol = ("holiday" in st_lower or "holiday" in pj_lower or "holiday" in tt_lower)
            is_lv = ("leave" in st_lower or "leave" in pj_lower or "leave" in tt_lower)

            if norm_date:
                daily_hours_map[norm_date] += h_float
                m = daily_meta[norm_date]
                m["task_count"] += 1
                if is_w_off:
                    m["is_off"] = True
                elif is_hol:
                    m["is_holiday"] = True
                elif is_lv:
                    m["is_leave"] = True
                else:
                    m["has_work"] = True

            display_hours = r_hours if r_hours else "-"

            # Visual tag styling
            tag = "normal"
            if is_hol:
                tag = "holiday"
            elif is_w_off:
                tag = "weekly_off"
            elif is_lv:
                tag = "leave"

            self.tree.insert("", tk.END, values=(
                r_id, r_date, r_proj, r_title, display_hours, r_status,
                r_login or "-", r_logout or "-", r_lunch or "-", r_tea or "-",
                r_desc, r_remarks
            ), tags=(tag,))

        # Evaluate monthly 8-hour day metrics
        days_gte_8 = 0
        days_lt_8 = 0
        gte_8_dates = []
        lt_8_dates = []

        for d_str, d_hours in sorted(daily_hours_map.items()):
            m = daily_meta[d_str]
            if d_hours >= 8.0:
                days_gte_8 += 1
                gte_8_dates.append((d_str, d_hours))
            else:
                # Count days with work logged less than 8 hours, excluding purely off/holiday/full-leave days
                if m["has_work"] or (d_hours > 0 and not m["is_off"] and not m["is_holiday"]):
                    days_lt_8 += 1
                    lt_8_dates.append((d_str, d_hours))
                elif not m["is_off"] and not m["is_holiday"] and not m["is_leave"] and m["task_count"] > 0:
                    days_lt_8 += 1
                    lt_8_dates.append((d_str, d_hours))

        self.current_gte_8_dates = gte_8_dates
        self.current_lt_8_dates = lt_8_dates

        self.lbl_stat_month.config(text=f"📁 Month: {self.current_selected_month.get()}")
        self.lbl_stat_tasks.config(text=f"Total Tasks: {total_tasks}")
        self.lbl_stat_hours.config(text=f"Total Hours: {total_hours:.1f} hrs")
        self.lbl_stat_completed.config(text=f"Completed: {completed_count}")
        if hasattr(self, "lbl_stat_gte_8h"):
            self.lbl_stat_gte_8h.config(text=f"⏱️ ≥ 8h Days: {days_gte_8}")
        if hasattr(self, "lbl_stat_lt_8h"):
            self.lbl_stat_lt_8h.config(text=f"⏳ < 8h Days: {days_lt_8}")
        if hasattr(self, "lbl_stat_leaves"):
            self.lbl_stat_leaves.config(text=f"🌴 Leaves: {leave_count}")

        # Update top shift summary with today's timings
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        t_now = get_daily_timings(today_date)
        if t_now.get("login") or t_now.get("logout"):
            shift_parts = []
            if t_now.get("login") and t_now.get("logout"):
                net_h, net_str, _, _, _ = calculate_net_working_hours(
                    t_now["login"], t_now["logout"], t_now.get("lunch", ""), t_now.get("tea", ""),
                    lunch_taken=t_now.get("lunch_taken", True), tea_taken=t_now.get("tea_taken", True)
                )
                net_human = format_human_time(net_h)
                shift_parts.append(f"🕒 Shift: {t_now['login']} - {t_now['logout']} ({net_human})")
            elif t_now.get("login"):
                shift_parts.append(f"🕒 Login: {t_now['login']}")
            if t_now.get("lunch_taken") and t_now.get("lunch"):
                shift_parts.append(f"🥪 Lunch: {t_now['lunch']}")
            if t_now.get("tea_taken") and t_now.get("tea"):
                shift_parts.append(f"☕ Tea: {t_now['tea']}")
            self.lbl_stat_shift.config(text=" | ".join(shift_parts))
        else:
            self.lbl_stat_shift.config(text="")

    def show_gte_8h_details(self):
        month_name = self.current_selected_month.get() or "Current Month"
        dates = getattr(self, "current_gte_8_dates", [])
        if not dates:
            messagebox.showinfo("≥ 8 Hours Work Days", f"No days with ≥ 8.0 hours found in {month_name}.")
            return
        lines = []
        for d, h in dates:
            try:
                dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                wday = dt.strftime("%a")
                lines.append(f"• {d} ({wday}): {h:.2f} hrs")
            except Exception:
                lines.append(f"• {d}: {h:.2f} hrs")
        count = len(dates)
        detail_msg = f"📁 Month: {month_name}\n⏱️ Total Days with ≥ 8.0 Hours: {count} days\n\n" + "\n".join(lines)
        messagebox.showinfo(f"≥ 8 Hours Days ({count}) - {month_name}", detail_msg)

    def show_lt_8h_details(self):
        month_name = self.current_selected_month.get() or "Current Month"
        dates = getattr(self, "current_lt_8_dates", [])
        if not dates:
            messagebox.showinfo("< 8 Hours Work Days", f"No days with < 8.0 hours found in {month_name}.")
            return
        lines = []
        for d, h in dates:
            try:
                dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                wday = dt.strftime("%a")
                lines.append(f"• {d} ({wday}): {h:.2f} hrs")
            except Exception:
                lines.append(f"• {d}: {h:.2f} hrs")
        count = len(dates)
        detail_msg = f"📁 Month: {month_name}\n⏳ Total Days with < 8.0 Hours: {count} days\n\n" + "\n".join(lines)
        messagebox.showinfo(f"< 8 Hours Days ({count}) - {month_name}", detail_msg)

    def open_excel_file(self):
        if not os.path.exists(FILE):
            init_file()
        try:
            opened = open_file_externally(FILE)
            if opened:
                self.status.config(text=f"Opened '{FILE}' in Excel.")
            else:
                self.status.config(text=f"File saved at '{FILE}'.")
        except Exception as e:
            messagebox.showerror("Cannot Open File", f"Error opening '{FILE}':\n{e}")

# ---------- Main Execution ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = TodayWorkUpdateApp(root)
    root.mainloop()