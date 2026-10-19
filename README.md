# 📝 WorkPulse - Today Work Update Manager

A feature-packed desktop work log, shift tracker, and team reporting tool built with Python & Tkinter. It automatically logs tasks into month-wise Excel sheets (`data.xlsx`), calculates net working hours, formats daily standup updates for Microsoft Teams/Slack, and synchronizes live events and bulk records to your custom **REST API / Webhook**.

---

## 🚀 Key Features

* **⏱️ Shift & Break Tracker**: Log daily Login, Logout, Lunch Break, and Tea Break times. Automatically computes net working hours minus breaks.
* **📊 Month-Wise Excel Logger**: Tasks are saved chronologically in distinct monthly sheets (e.g., `October 2026`, `November 2026`).
* **🌐 Custom REST API / Webhook Integration**:
  * **Real-time Auto-Sync**: Automatically sends a structured JSON payload to your custom API / Webhook endpoint whenever a task is **Edited**, **Updated**, **Created**, or **Deleted**.
  * **"Sync to API" Button**: One-click bulk sync to push all historical records across all months to your API endpoint.
  * **Test Connection**: Instant ping tool inside Settings to verify webhook endpoint health.
* **📢 Team Standup Generator**: One-click copy/share Markdown-formatted daily standup reports formatted for Microsoft Teams, Slack, or Discord.
* **📂 Bulk Data Tools**:
  * **Bulk Paste**: Paste unstructured text logs and auto-extract task titles and durations.
  * **Import Excel**: Bulk import existing tasks from external Excel files with visual column mapping.
* **💬 LAN Team Chat (Same Wi-Fi Network)**:
  * **Zero-Config Peer Discovery**: Automatically detects all colleagues running WorkPulse on the same Wi-Fi / local network via UDP broadcast (no cloud server or external setup required).
  * **Real-Time Instant Messaging**: Private, high-speed team chat that stays strictly within your local network.
  * **Live Colleague Presence & Status**: Real-time presence sidebar with status choices (🟢 Available, 🟡 Focus Mode, 🍱 Lunch Break, ☕ Tea Break, 🔴 In Meeting).
  * **One-Click "Share Today's Tasks"**: Instantly broadcast your today's task log and shift summary into the team chat.
  * **Manual IP Connect Fallback**: "Add Colleague IP" tool to connect across restricted corporate Wi-Fi or isolated subnets.
  * **Persistent SQLite Database Storage**: All messages, task logs, and shift cards are saved locally in an indexed SQLite database (`chat_history.db`) with thread-safe WAL mode and real-time history search (**🔍 Search**).
* **🏖️ Holidays & Weekends**: Auto-marks weekly offs (custom days, 2nd & 4th Saturdays) and official company/national holidays.

---

## 📋 System Requirements

* **Operating System**: Windows (10/11), macOS (10.15+), or Linux (Ubuntu, Debian, Fedora, Arch, etc.)
* **Python**: Python 3.8 or higher
* **Dependencies**: `openpyxl` (handled automatically via `requirements.txt`)

---

## 💻 How to Run on Any Operating System

### 🪟 1. Windows

#### Option A: Quick Launch (Zero Command Line)
Simply double-click:
```bat
run.bat
```
*(The launcher automatically verifies dependencies, installs `openpyxl` if missing, and starts the application).*

#### Option B: Via Command Prompt or PowerShell
1. Open Command Prompt or PowerShell in the project directory:
   ```powershell
   cd path\to\myTodayWorkupdate
   ```
2. (Optional but recommended) Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install required dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run the application:
   ```powershell
   python app.py
   ```
   *(or `py app.py`)*

---

### 🍎 2. macOS

1. Ensure Python 3 and Tkinter are installed (standard with Python from [python.org](https://www.python.org/downloads/) or Homebrew):
   ```bash
   brew install python-tk
   ```
2. Open Terminal and navigate to the project directory:
   ```bash
   cd /path/to/myTodayWorkupdate
   ```
3. Make the launcher script executable and run:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
   *Or run manually via Python:*
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 app.py
   ```

---

### 🐧 3. Linux (Ubuntu, Debian, Fedora, Arch)

On Linux systems, Tkinter is packaged separately from Python and must be installed via your system package manager.

#### Step 1: Install Python and Tkinter
* **Ubuntu / Debian / Linux Mint**:
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-pip python3-tk python3-venv
  ```
* **Fedora / RHEL / CentOS**:
  ```bash
  sudo dnf install -y python3 python3-pip python3-tkinter
  ```
* **Arch Linux / Manjaro**:
  ```bash
  sudo pacman -S python python-pip tk
  ```

#### Step 2: Run the App
Navigate to the directory:
```bash
cd /path/to/myTodayWorkupdate
```

**Using the included shell launcher:**
```bash
chmod +x run.sh
./run.sh
```

**Or using Python Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

---

## 🌐 Custom Data API & Webhook Configuration

You can connect your own backend (Node.js, PHP, Laravel, Python/FastAPI/Django, Go) or webhook service (Zapier, Make, n8n, Webhook.site) to receive live data updates.

### Setting up the Webhook
1. Open the app and click **⚙️ Settings** (or press `Ctrl + ,`).
2. Go to the **`🌐 Data API / Webhook`** tab.
3. Enter your endpoint in **API / Webhook URL** (e.g. `https://example.com/api/tasks/webhook`).
4. (Optional) Provide a **Bearer Token** or API Key (e.g. `Bearer secret_token` or `X-API-Key: secret123`).
5. Choose your triggers:
   * `[✓] Send payload to API whenever a task is Edited or Updated`
   * `[✓] Send payload to API whenever a new task is Created / Saved`
   * `[✓] Send payload to API whenever a task is Deleted`
6. Click **🧪 Send Test Ping to API** to verify connectivity.
7. Click **💾 Save All Settings**.

---

### Payload Structure

#### 1. On Edit / Update Event (Automatic)
```json
{
  "event": "update",
  "action": "edit",
  "timestamp": "2026-10-19 16:30:00",
  "user_name": "Developer",
  "record": {
    "id": "WU-261007-122923",
    "date": "2026-10-01",
    "sheet": "October 2026",
    "project": "Afro Cargo & Logistics",
    "task_title": "Enquiries Menu in MenuSeeder.php",
    "description": "Synced schedule dates and updated API endpoints.",
    "hours": "8.75",
    "status": "Completed",
    "remarks": "",
    "login_time": "10:30 AM",
    "logout_time": "08:15 PM",
    "lunch_break": "02:15 PM - 03:00 PM",
    "tea_break": "05:30 PM - 05:45 PM",
    "updated_at": "2026-10-19 16:30:00"
  },
  "data": { ... }
}
```

#### 2. On "Sync to API" (Send All Data)
Click **`🔄 Sync to API`** on the top header or **`🔄 Sync All to API`** on the table action bar:
```json
{
  "event": "sync_all",
  "action": "sync",
  "scope": "all",
  "timestamp": "2026-10-19 16:30:00",
  "user_name": "Developer",
  "total_records": 34,
  "records": [
    {
      "id": "WU-261007-122923",
      "date": "2026-10-01",
      "sheet": "October 2026",
      "project": "Afro Cargo & Logistics",
      "task_title": "...",
      "hours": "8.75",
      "status": "Completed",
      "remarks": "",
      "login_time": "10:30 AM",
      "logout_time": "08:15 PM",
      "lunch_break": "02:15 PM - 03:00 PM",
      "tea_break": "05:30 PM - 05:45 PM",
      "logged_at": "2026-10-15 19:19:25"
    }
  ],
  "data": [ ... ]
}
```

---

## 📁 Project Structure

```text
myTodayWorkupdate/
├── app.py              # Main desktop GUI application (Tkinter + OpenpyXL)
├── data.xlsx           # Local Excel workbook storing month sheets & records
├── settings.json       # User preferences, shift times, holidays, and API credentials
├── requirements.txt    # Python dependencies (openpyxl)
├── run.bat             # Windows 1-click startup batch script
├── run.sh              # macOS / Linux 1-click bash launcher script
└── README.md           # Documentation and setup guide
```

---

## ❓ Troubleshooting & FAQs

### 1. `ModuleNotFoundError: No module named 'tkinter'`
* **Cause**: On Linux distributions, Tkinter is not installed with the standard Python package.
* **Fix**: Install it using your package manager:
  * Ubuntu/Debian: `sudo apt install python3-tk`
  * Fedora: `sudo apt install python3-tkinter`
  * macOS: `brew install python-tk`

### 2. `PermissionError: Cannot access 'data.xlsx' because it is open in Excel`
* **Cause**: Microsoft Excel locks `.xlsx` files while they are open for editing.
* **Fix**: Close `data.xlsx` in Excel, then click Save/Update again in the app.

### 3. `Python was not found; run without arguments to install...` (Windows)
* **Cause**: Python is installed via Microsoft Store execution alias or not added to system PATH.
* **Fix**:
  1. Open Windows **Settings** > **Apps** > **Advanced app settings** > **App execution aliases**.
  2. Toggle OFF `python.exe` and `python3.exe`.
  3. Ensure your Python installation directory (e.g., `C:\Python312` or `AppData\Local\Programs\Python`) is added to the system `PATH`.

---

## 📄 License
Internal Work Tracker Tool. Created for productive developer daily logging.
