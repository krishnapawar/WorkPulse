"""
WorkPulse LAN Team Chat System
------------------------------
Zero-configuration peer-to-peer chat for teams on the same Wi-Fi or Local Area Network.
Features:
  - Automatic UDP broadcast & unicast peer discovery (no cloud server needed)
  - Real-time instant messaging across local subnet
  - Instant 'Share Today's Tasks' work update integration
  - Live colleague presence & customizable status (Available, Focus Mode, Lunch, etc.)
  - Enterprise manual IP connect fallback (for Wi-Fi APs with client isolation)
  - Persistent local chat history & unread notification badges
  - Modern, responsive desktop UI with auto-centering and high-DPI scaling
"""

import os
import sys
import json
import time
import uuid
import socket
import select
import sqlite3
import datetime
import threading
import collections
import tkinter as tk
from tkinter import ttk, messagebox

# Default port for WorkPulse LAN Chat
DEFAULT_LAN_PORT = 45454
CHAT_DB_FILE = "chat_history.db"
LEGACY_JSON_FILE = "chat_history.json"
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


def center_window(window, parent=None, default_w=None, default_h=None, min_w=None, min_h=None):
    """Auto-adjust and center a window relative to its parent or screen, ensuring it fits cleanly on any display."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    w = default_w or window.winfo_reqwidth()
    h = default_h or window.winfo_reqheight()

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

    x = max(10, min(x, screen_w - w - 10))
    y = max(10, min(y, screen_h - h - 50))

    window.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")


def get_network_info():
    """
    Detects primary local IP and broadcast addresses for LAN communication.
    Works reliably across Linux, Windows, and macOS.
    """
    local_ip = "127.0.0.1"
    hostname = socket.gethostname()
    broadcasts = {"255.255.255.255", "<broadcast>"}

    # Probe outbound routing to determine primary network interface IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "127.0.0.1"

    # Compute subnet broadcast for /24 standard Wi-Fi LAN
    parts = local_ip.split(".")
    if len(parts) == 4 and parts[0] != "127":
        subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        broadcasts.add(subnet_bcast)

    return local_ip, hostname, list(broadcasts)


# ==============================================================================
# SQLite Chat Database Engine
# ==============================================================================

class ChatDatabase:
    """
    High-performance, persistent SQLite database storage for WorkPulse LAN chat.
    Stores messages, work summaries, task breakdowns, timestamps, and metadata.
    Thread-safe with WAL mode enabled.
    """
    def __init__(self, db_path=CHAT_DB_FILE):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
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

        conn.execute("""
            INSERT OR REPLACE INTO chat_messages (
                id, type, sender_id, user_name, avatar_color, text, time_str,
                timestamp, date_str, is_me, title, tasks_json, shift_str, total_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m_id, m_type, sender_id, user_name, avatar_color, text, time_str,
            timestamp, date_str, is_me, title, tasks_json, shift_str, total_hours
        ))

    def save_message(self, msg_dict):
        """Persists a message dictionary into SQLite."""
        with self.lock:
            try:
                with self._get_connection() as conn:
                    self._insert_row(conn, msg_dict)
                    conn.commit()
                return True
            except Exception as e:
                print(f"Error saving chat to SQLite: {e}")
                return False

    def load_recent_messages(self, limit=MAX_HISTORY_ITEMS):
        """Loads last N messages from SQLite in chronological order."""
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT id, type, sender_id, user_name, avatar_color, text,
                               time_str, timestamp, date_str, is_me, title, tasks_json,
                               shift_str, total_hours
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
                            "total_hours": r["total_hours"]
                        })
                    return result
            except Exception as e:
                print(f"Error loading chat from SQLite: {e}")
                return []

    def search_messages(self, query_str, limit=50):
        """Searches message texts, user names, or task titles in SQLite."""
        q = f"%{query_str.strip()}%"
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT id, type, sender_id, user_name, avatar_color, text,
                               time_str, timestamp, date_str, is_me, title, tasks_json,
                               shift_str, total_hours
                        FROM chat_messages
                        WHERE text LIKE ? OR user_name LIKE ? OR title LIKE ?
                        ORDER BY timestamp DESC LIMIT ?
                    """, (q, q, q, limit))
                    rows = cursor.fetchall()
                    result = []
                    for r in rows:
                        tasks = []
                        if r["tasks_json"]:
                            try:
                                tasks = json.loads(r["tasks_json"])
                            except Exception:
                                tasks = []
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
                            "total_hours": r["total_hours"]
                        })
                    return result
            except Exception as e:
                print(f"Error searching chat in SQLite: {e}")
                return []

    def get_message_count(self):
        """Returns total message count stored in SQLite."""
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM chat_messages")
                    row = cursor.fetchone()
                    return row[0] if row else 0
            except Exception:
                return 0

    def clear_all(self):
        """Deletes all messages from SQLite database."""
        with self.lock:
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
# LAN Chat Networking Engine
# ==============================================================================

class LANChatEngine:
    """
    Manages background sockets, UDP broadcast discovery, peer tracking,
    message deduplication, and thread-safe callbacks.
    """
    def __init__(self, user_name="Developer", port=DEFAULT_LAN_PORT,
                 on_message=None, on_peers_change=None):
        self.user_name = user_name
        self.port = port
        self.on_message = on_message
        self.on_peers_change = on_peers_change

        self.user_id = uuid.uuid4().hex[:10]
        self.local_ip, self.hostname, self.broadcast_addrs = get_network_info()
        self.avatar_color = get_avatar_color(self.user_name)

        self.status = "Available"
        self.status_emoji = "🟢"

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

        # SQLite Chat Database
        self.db = ChatDatabase(CHAT_DB_FILE)
        self.messages = []
        self.load_history()

    def start(self):
        """Starts socket listeners and discovery heartbeats."""
        if self.running:
            return
        self.running = True

        # Refresh network info in case Wi-Fi connected recently
        self.local_ip, self.hostname, self.broadcast_addrs = get_network_info()

        # Create receiving UDP socket
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        try:
            self.rx_sock.bind(("", self.port))
        except Exception as e:
            # Fallback to OS assigned ephemeral port if standard port is locked
            try:
                self.rx_sock.bind(("", 0))
                self.port = self.rx_sock.getsockname()[1]
            except Exception:
                pass

        self.rx_sock.settimeout(1.0)

        # Create transmitting UDP socket with broadcast enabled
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Launch background threads
        self.rx_thread = threading.Thread(target=self._listen_loop, daemon=True, name="LANChat-Rx")
        self.beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True, name="LANChat-Beacon")
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="LANChat-Cleanup")

        self.rx_thread.start()
        self.beacon_thread.start()
        self.cleanup_thread.start()

        # Send immediate initial discovery beacon
        self._broadcast_beacon()

    def stop(self):
        """Gracefully announces departure and closes sockets."""
        if not self.running:
            return
        self.running = False

        # Broadcast leave packet so peers immediately remove this instance
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

    def update_profile(self, user_name, status=None, status_emoji=None):
        """Updates user profile and broadcasts state change to peers."""
        with self.lock:
            self.user_name = user_name or self.user_name
            self.avatar_color = get_avatar_color(self.user_name)
            if status is not None:
                self.status = status
            if status_emoji is not None:
                self.status_emoji = status_emoji

        # Broadcast status update
        pkt = {
            "v": 1,
            "id": uuid.uuid4().hex[:12],
            "type": "status_update",
            "sender_id": self.user_id,
            "user_name": self.user_name,
            "status": self.status,
            "status_emoji": self.status_emoji,
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

        # Ping directly
        pkt = self._build_beacon_packet(is_ack=False)
        try:
            data = json.dumps(pkt).encode("utf-8")
            self.tx_sock.sendto(data, (clean_ip, DEFAULT_LAN_PORT))
        except Exception:
            pass
        return True

    def send_chat_message(self, text):
        """Sends a public team chat message."""
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
            "is_me": True
        }

        # Remember own packet so we don't duplicate when loopback receives it
        with self.lock:
            self._record_seen_packet(pkt_id)
            self.messages.append(msg_obj)
            self.save_history()

        # Send across LAN
        self._send_raw_packet(msg_obj)

        # Trigger callback
        if self.on_message:
            self.on_message(msg_obj)

        return msg_obj

    def send_work_update(self, title, date_str, tasks, shift_str, total_hours):
        """Sends a structured Work Update card to the team."""
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
            "tasks": tasks,  # list of {"title", "hours", "status", "project"}
            "shift_str": shift_str,
            "total_hours": total_hours,
            "time_str": time_str,
            "timestamp": time.time(),
            "is_me": True
        }

        with self.lock:
            self._record_seen_packet(pkt_id)
            self.messages.append(msg_obj)
            self.save_history()

        self._send_raw_packet(msg_obj)

        if self.on_message:
            self.on_message(msg_obj)

        return msg_obj

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

    # ---------- Internal Socket & Protocol Helpers ----------

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
            "status": self.status,
            "status_emoji": self.status_emoji,
            "avatar_color": self.avatar_color,
            "timestamp": time.time()
        }

    def _broadcast_beacon(self):
        pkt = self._build_beacon_packet(is_ack=False)
        self._send_raw_packet(pkt)

    def _send_raw_packet(self, pkt_dict):
        """
        Sends packet to all broadcast addresses + all known peers unicast.
        This provides high resilience on Wi-Fi networks with broadcast filtering.
        """
        try:
            data = json.dumps(pkt_dict).encode("utf-8")
        except Exception:
            return

        # 1. Send to all broadcast targets
        for bcast in self.broadcast_addrs:
            try:
                self.tx_sock.sendto(data, (bcast, DEFAULT_LAN_PORT))
            except Exception:
                pass

        # 2. Unicast directly to all known peers
        with self.lock:
            peer_endpoints = [(p["ip"], p["port"]) for p in self.peers.values()]
            custom_targets = list(self.custom_ips)

        for ip, port in peer_endpoints:
            try:
                if ip and ip != self.local_ip:
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

        # Ignore our own messages
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
                    "status": pkt.get("status", "Available"),
                    "status_emoji": pkt.get("status_emoji", "🟢"),
                    "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                    "last_seen": time.time()
                }

            # If this is a newly discovered peer and they sent a beacon, reply with ACK immediately
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
                    self.peers[sender_id]["last_seen"] = time.time()
            if self.on_peers_change:
                self.on_peers_change(self.get_online_peers())

        elif pkt_type == "chat":
            msg_obj = {
                "v": 1,
                "id": pkt_id,
                "type": "chat",
                "sender_id": sender_id,
                "user_name": pkt.get("user_name", "Colleague"),
                "avatar_color": pkt.get("avatar_color", get_avatar_color(pkt.get("user_name", ""))),
                "text": pkt.get("text", ""),
                "time_str": pkt.get("time_str", datetime.datetime.now().strftime("%I:%M %p")),
                "timestamp": pkt.get("timestamp", time.time()),
                "is_me": False
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history()

            if self.on_message:
                self.on_message(msg_obj)

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
                "is_me": False
            }
            with self.lock:
                self.messages.append(msg_obj)
                self.save_history()

            if self.on_message:
                self.on_message(msg_obj)

        elif pkt_type == "leave":
            with self.lock:
                if sender_id in self.peers:
                    del self.peers[sender_id]
            if self.on_peers_change:
                self.on_peers_change(self.get_online_peers())

    def _beacon_loop(self):
        """Sends periodic heartbeats to maintain presence on LAN."""
        while self.running:
            try:
                self._broadcast_beacon()
            except Exception:
                pass
            time.sleep(BEACON_INTERVAL)

    def _cleanup_loop(self):
        """Removes peers who haven't sent a heartbeat within PEER_TIMEOUT."""
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
      - Split pane: Colleague Presence Sidebar + Real-Time Chat Stream
      - Interactive status changer (Available, Lunch, Focus, etc.)
      - Rich speech bubble cards (User vs Colleagues)
      - Formatted 'Work Update' cards
      - One-click 'Share Today's Tasks' integration
      - Colleague IP manual connect for enterprise/restricted Wi-Fi
    """
    def __init__(self, parent, engine, app_ref=None):
        self.parent = parent
        self.engine = engine
        self.app_ref = app_ref

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("WorkPulse - LAN Team Chat (Same Wi-Fi Network)")
        self.dialog.configure(bg="#0f172a")

        # Responsive window sizing & auto-center
        center_window(self.dialog, parent, default_w=1020, default_h=680, min_w=820, min_h=520)

        self._build_header()
        self._build_body()
        self._populate_initial_data()

        # Wire engine callbacks to this dialog only after all UI widgets exist
        self.engine.on_message = self._on_engine_message
        self.engine.on_peers_change = self._on_engine_peers_change

        # Keyboard shortcuts
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

        # Clean-up on close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        # Detach dialog callbacks
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
        header = tk.Frame(self.dialog, bg="#1e293b", padx=16, pady=10)
        header.pack(fill=tk.X, side=tk.TOP)

        # Right Action Buttons (Pack RIGHT first so they are never clipped)
        right_box = tk.Frame(header, bg="#1e293b")
        right_box.pack(side=tk.RIGHT)

        btn_search = tk.Button(
            right_box,
            text="🔍 Search",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=9,
            pady=3,
            cursor="hand2",
            command=self._prompt_search_dialog
        )
        btn_search.pack(side=tk.LEFT, padx=2)

        btn_add_ip = tk.Button(
            right_box,
            text="➕ Add IP",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=9,
            pady=3,
            cursor="hand2",
            command=self._prompt_add_colleague_ip
        )
        btn_add_ip.pack(side=tk.LEFT, padx=2)

        btn_clear = tk.Button(
            right_box,
            text="🧹 Clear",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=9,
            pady=3,
            cursor="hand2",
            command=self._clear_chat_history
        )
        btn_clear.pack(side=tk.LEFT, padx=2)

        # Left branding
        left_box = tk.Frame(header, bg="#1e293b")
        left_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title_lbl = tk.Label(
            left_box,
            text="💬 LAN Team Chat",
            font=("Segoe UI", 13, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        )
        title_lbl.pack(anchor="w")

        net_text = f"🟢 Local Subnet • IP: {self.engine.local_ip}:{self.engine.port} • 💾 SQLite DB Active"
        self.lbl_net_info = tk.Label(
            left_box,
            text=net_text,
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#1e293b"
        )
        self.lbl_net_info.pack(anchor="w", pady=(1, 0))

    def _build_body(self):
        """Split layout: Left Sidebar (Presence) + Right Area (Chat stream)."""
        body = tk.Frame(self.dialog, bg="#0f172a")
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ----------------- LEFT SIDEBAR: PEER PRESENCE -----------------
        sidebar = tk.Frame(body, bg="#1e293b", width=280, bd=1, relief="solid")
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        sidebar.pack_propagate(False)

        # My Profile Card
        my_card = tk.Frame(sidebar, bg="#334155", padx=10, pady=10)
        my_card.pack(fill=tk.X, padx=8, pady=8)

        my_top = tk.Frame(my_card, bg="#334155")
        my_top.pack(fill=tk.X)

        self.my_avatar_lbl = tk.Label(
            my_top,
            text=get_initials(self.engine.user_name),
            font=("Segoe UI", 8, "bold"),
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
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg="#334155"
        )
        my_name_lbl.pack(anchor="w")

        # Status Dropdown
        status_frame = tk.Frame(my_card, bg="#334155")
        status_frame.pack(fill=tk.X, pady=(6, 0))

        tk.Label(status_frame, text="My Status:", font=("Segoe UI", 8), fg="#cbd5e1", bg="#334155").pack(anchor="w")
        self.status_var = tk.StringVar(value=f"{self.engine.status_emoji} {self.engine.status}")
        self.combo_status = ttk.Combobox(
            status_frame,
            textvariable=self.status_var,
            values=[opt[0] for opt in STATUS_CHOICES],
            state="readonly",
            font=("Segoe UI", 8)
        )
        self.combo_status.pack(fill=tk.X, pady=(2, 0))
        self.combo_status.bind("<<ComboboxSelected>>", self._on_status_changed)

        # Online Peers Section Heading
        peer_header = tk.Frame(sidebar, bg="#1e293b", padx=10, pady=5)
        peer_header.pack(fill=tk.X)

        self.lbl_peer_count = tk.Label(
            peer_header,
            text="COLLEAGUES ON WI-FI (0)",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#1e293b"
        )
        self.lbl_peer_count.pack(anchor="w")

        # Scrollable Peers Container
        peers_canvas_frame = tk.Frame(sidebar, bg="#1e293b")
        peers_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

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

        # Chat Banner
        chat_top = tk.Frame(chat_box, bg="#0f172a", padx=12, pady=6)
        chat_top.pack(fill=tk.X, side=tk.TOP)

        tk.Label(
            chat_top,
            text="# team-general",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        ).pack(side=tk.LEFT)

        tk.Label(
            chat_top,
            text="• Local Wi-Fi broadcast • Real-time across devices",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#0f172a"
        ).pack(side=tk.LEFT, padx=6)

        # Scrollable Messages Canvas
        msg_canvas_box = tk.Frame(chat_box, bg="#0f172a")
        msg_canvas_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.msg_canvas = tk.Canvas(msg_canvas_box, bg="#0f172a", highlightthickness=0)
        self.msg_scroll = ttk.Scrollbar(msg_canvas_box, orient=tk.VERTICAL, command=self.msg_canvas.yview)
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

        # Bottom Input Dock
        input_dock = tk.Frame(chat_box, bg="#1e293b", padx=10, pady=8)
        input_dock.pack(fill=tk.X, side=tk.BOTTOM)

        # Send Button (Pack RIGHT first so it is always visible)
        btn_send = tk.Button(
            input_dock,
            text="✈️ Send",
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._send_message
        )
        btn_send.pack(side=tk.RIGHT, padx=(3, 0))

        # Share Today's Tasks Button (Pack RIGHT second)
        btn_share_tasks = tk.Button(
            input_dock,
            text="📋 Share Tasks",
            font=("Segoe UI", 9, "bold"),
            bg="#8b5cf6",
            fg="white",
            activebackground="#7c3aed",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._share_today_tasks_to_chat
        )
        btn_share_tasks.pack(side=tk.RIGHT, padx=3)

        # Text input field (Packs LEFT and expands into all remaining space)
        self.entry_msg = tk.Entry(
            input_dock,
            font=("Segoe UI", 10),
            bg="#334155",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=5
        )
        self.entry_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=4)
        self.entry_msg.bind("<Return>", lambda e: self._send_message())
        self.entry_msg.focus_set()

    def _populate_initial_data(self):
        """Renders existing message history and online peers."""
        # Render historical messages
        for msg in self.engine.messages:
            self._render_message_bubble(msg, scroll=False)

        # Scroll to bottom
        self.dialog.after(100, lambda: self.msg_canvas.yview_moveto(1.0))

        # Render online peers
        self._refresh_peers_ui(self.engine.get_online_peers())

    # ---------- UI Action Handlers ----------

    def _send_message(self):
        text = self.entry_msg.get().strip()
        if not text:
            return
        self.entry_msg.delete(0, tk.END)
        self.engine.send_chat_message(text)

    def _share_today_tasks_to_chat(self):
        """Grabs today's tasks from the active WorkPulse app and posts to chat."""
        if not self.app_ref:
            messagebox.showinfo("WorkPulse", "Active application reference not found.")
            return

        data = self.app_ref.get_all_categorized_tasks()
        tasks_pool = data.get("today", [])
        if not tasks_pool:
            tasks_pool = data.get("month", [])

        if not tasks_pool:
            messagebox.showinfo("No Tasks", "No tasks found for today to share.")
            return

        date_str = data.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))

        # Compute shift info
        shift_str = ""
        if hasattr(self.app_ref, "get_current_day_timings"):
            timings = self.app_ref.get_current_day_timings(date_str)
            if timings.get("login") or timings.get("logout"):
                shift_str = f"Shift: {timings.get('login', '-')} to {timings.get('logout', '-')}"

        # Calculate total hours
        total_hours = 0.0
        for t in tasks_pool:
            try:
                total_hours += float(t.get("hours", 0) or 0)
            except Exception:
                pass

        total_hours_str = f"{total_hours:.1f} hrs"

        # Broadcast as a Work Update card
        self.engine.send_work_update(
            title=f"Today's Work Log ({date_str})",
            date_str=date_str,
            tasks=tasks_pool[:12],  # Cap at 12 for clean presentation
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
        self.engine.update_profile(self.engine.user_name, status=status_text, status_emoji=status_emoji)

    def _prompt_add_colleague_ip(self):
        """Opens a modal to manually enter colleague's IP for isolated Wi-Fi."""
        prompt_win = tk.Toplevel(self.dialog)
        prompt_win.title("Add Colleague IP")
        prompt_win.configure(bg="#1e293b")
        prompt_win.resizable(False, False)

        center_window(prompt_win, self.dialog, default_w=400, default_h=190)

        tk.Label(
            prompt_win,
            text="Enter Colleague's IP Address:",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        ).pack(anchor="w", padx=16, pady=(14, 4))

        tk.Label(
            prompt_win,
            text="Useful if Wi-Fi Access Point blocks UDP broadcast discovery.",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#1e293b"
        ).pack(anchor="w", padx=16, pady=(0, 8))

        e_ip = tk.Entry(prompt_win, font=("Segoe UI", 10), bg="#334155", fg="#ffffff", insertbackground="#ffffff")
        e_ip.pack(fill=tk.X, padx=16, pady=4)
        e_ip.insert(0, "192.168.1.")
        e_ip.focus_set()

        btn_box = tk.Frame(prompt_win, bg="#1e293b")
        btn_box.pack(fill=tk.X, padx=16, pady=12)

        def _do_add():
            val = e_ip.get().strip()
            if val and val != "192.168.1.":
                self.engine.add_custom_peer_ip(val)
                messagebox.showinfo("Ping Sent", f"Sent connection beacon to {val}.\nIf WorkPulse is open on that machine, they will appear in your colleague list!")
                prompt_win.destroy()

        e_ip.bind("<Return>", lambda e: _do_add())

        tk.Button(btn_box, text="Connect", font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="white", relief="flat", padx=14, pady=3, command=_do_add).pack(side=tk.RIGHT, padx=4)
        tk.Button(btn_box, text="Cancel", font=("Segoe UI", 9), bg="#475569", fg="white", relief="flat", padx=10, pady=3, command=prompt_win.destroy).pack(side=tk.RIGHT)

    def _clear_chat_history(self):
        if messagebox.askyesno("Clear Chat History", "Are you sure you want to clear your local chat history from SQLite?"):
            self.engine.clear_history()
            for widget in self.msg_inner.winfo_children():
                widget.destroy()

    def _prompt_search_dialog(self):
        """Opens modal dialog to search SQLite chat history."""
        search_win = tk.Toplevel(self.dialog)
        search_win.title("🔍 Search LAN Chat History (SQLite)")
        search_win.configure(bg="#0f172a")

        center_window(search_win, self.dialog, default_w=580, default_h=480, min_w=480, min_h=360)

        # Header
        top_bar = tk.Frame(search_win, bg="#1e293b", padx=14, pady=8)
        top_bar.pack(fill=tk.X)

        tk.Label(
            top_bar,
            text="🔍 Search Chat History (SQLite)",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg="#1e293b"
        ).pack(anchor="w")

        total_count = self.engine.db.get_message_count()
        lbl_info = tk.Label(
            top_bar,
            text=f"Indexed across {total_count} messages in {CHAT_DB_FILE}",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#1e293b"
        )
        lbl_info.pack(anchor="w", pady=(1, 0))

        # Search Input
        input_bar = tk.Frame(search_win, bg="#0f172a", padx=14, pady=8)
        input_bar.pack(fill=tk.X)

        e_search = tk.Entry(
            input_bar,
            font=("Segoe UI", 10),
            bg="#1e293b",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=6
        )
        e_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        e_search.focus_set()

        # Results area
        results_frame = tk.Frame(search_win, bg="#0f172a", padx=12, pady=4)
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
                    font=("Segoe UI", 9),
                    fg="#64748b",
                    bg="#0f172a",
                    wraplength=440
                ).pack(anchor="w", padx=6, pady=20)
                return

            matches = self.engine.search_history(query, limit=50)
            if not matches:
                tk.Label(
                    res_inner,
                    text=f"No messages found matching '{query}'.",
                    font=("Segoe UI", 9, "bold"),
                    fg="#94a3b8",
                    bg="#0f172a"
                ).pack(pady=20)
                return

            tk.Label(
                res_inner,
                text=f"Found {len(matches)} matching message{'s' if len(matches) != 1 else ''}:",
                font=("Segoe UI", 8, "bold"),
                fg="#38bdf8",
                bg="#0f172a"
            ).pack(anchor="w", pady=(0, 6))

            for m in matches:
                card = tk.Frame(res_inner, bg="#1e293b", padx=10, pady=8, bd=1, relief="solid")
                card.pack(fill=tk.X, pady=3)

                header_f = tk.Frame(card, bg="#1e293b")
                header_f.pack(fill=tk.X)

                av = tk.Label(
                    header_f,
                    text=get_initials(m["user_name"]),
                    font=("Segoe UI", 7, "bold"),
                    fg="#ffffff",
                    bg=m.get("avatar_color", AVATAR_PALETTE[0]),
                    width=2,
                    height=1
                )
                av.pack(side=tk.LEFT, padx=(0, 5))

                tk.Label(
                    header_f,
                    text=m["user_name"],
                    font=("Segoe UI", 8, "bold"),
                    fg="#ffffff",
                    bg="#1e293b"
                ).pack(side=tk.LEFT)

                date_part = m.get("date_str") or ""
                time_part = m.get("time_str") or ""
                tk.Label(
                    header_f,
                    text=f"{date_part} {time_part}",
                    font=("Segoe UI", 7),
                    fg="#64748b",
                    bg="#1e293b"
                ).pack(side=tk.RIGHT)

                body_txt = m.get("text") or m.get("title") or "Work Update"
                tk.Label(
                    card,
                    text=body_txt,
                    font=("Segoe UI", 9),
                    fg="#e2e8f0",
                    bg="#1e293b",
                    wraplength=540,
                    justify="left"
                ).pack(anchor="w", pady=(4, 0))

        e_search.bind("<KeyRelease>", _do_search)
        e_search.bind("<Return>", _do_search)

        btn_find = tk.Button(
            input_bar,
            text="Search",
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            padx=12,
            pady=4,
            command=_do_search
        )
        btn_find.pack(side=tk.RIGHT)

        # Initial prompt
        _do_search()

    # ---------- Thread-Safe Engine Callback Handlers ----------

    def _on_engine_message(self, msg_obj):
        """Invoked by background socket thread when a message is received."""
        if not hasattr(self, "msg_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        self.dialog.after(0, lambda: self._render_message_bubble(msg_obj, scroll=True))

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
        self.lbl_peer_count.config(text=f"COLLEAGUES ON WI-FI ({count})")

        if not peers:
            placeholder = tk.Frame(self.peers_inner, bg="#1e293b", padx=10, pady=16)
            placeholder.pack(fill=tk.X)

            tk.Label(
                placeholder,
                text="📡 Searching Wi-Fi...",
                font=("Segoe UI", 9, "bold"),
                fg="#cbd5e1",
                bg="#1e293b"
            ).pack(anchor="w")

            tk.Label(
                placeholder,
                text="Colleagues who open WorkPulse on this Wi-Fi will automatically connect here.\n\nTip: Click 'Add Colleague IP' above if your router isolates Wi-Fi clients.",
                font=("Segoe UI", 8),
                fg="#64748b",
                bg="#1e293b",
                justify="left",
                wraplength=210
            ).pack(anchor="w", pady=(4, 0))
            return

        for p in peers:
            p_card = tk.Frame(self.peers_inner, bg="#334155", padx=8, pady=8, bd=1, relief="solid")
            p_card.pack(fill=tk.X, padx=4, pady=3)

            top = tk.Frame(p_card, bg="#334155")
            top.pack(fill=tk.X)

            avatar = tk.Label(
                top,
                text=get_initials(p["user_name"]),
                font=("Segoe UI", 8, "bold"),
                fg="#ffffff",
                bg=p.get("avatar_color", AVATAR_PALETTE[0]),
                width=3,
                height=1,
                relief="flat"
            )
            avatar.pack(side=tk.LEFT, padx=(0, 6))

            info = tk.Frame(top, bg="#334155")
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)

            name_lbl = tk.Label(
                info,
                text=p["user_name"],
                font=("Segoe UI", 9, "bold"),
                fg="#ffffff",
                bg="#334155"
            )
            name_lbl.pack(anchor="w")

            status_str = f"{p.get('status_emoji', '🟢')} {p.get('status', 'Available')}"
            status_lbl = tk.Label(
                info,
                text=status_str,
                font=("Segoe UI", 8),
                fg="#38bdf8",
                bg="#334155"
            )
            status_lbl.pack(anchor="w")

            ip_lbl = tk.Label(
                p_card,
                text=f"{p.get('hostname', 'Device')} • {p.get('ip', '')}",
                font=("Segoe UI", 7),
                fg="#94a3b8",
                bg="#334155"
            )
            ip_lbl.pack(anchor="w", pady=(3, 0))

    def _render_message_bubble(self, msg, scroll=True):
        """Renders chat messages or work update cards into the message canvas."""
        if not hasattr(self, "msg_inner") or not hasattr(self, "dialog") or not self.dialog.winfo_exists():
            return
        m_type = msg.get("type", "chat")
        is_me = msg.get("is_me", False)
        sender = msg.get("user_name", "Colleague")
        time_str = msg.get("time_str", "")
        avatar_bg = msg.get("avatar_color", AVATAR_PALETTE[0])

        row_frame = tk.Frame(self.msg_inner, bg="#0f172a")
        row_frame.pack(fill=tk.X, padx=10, pady=4)

        if m_type == "work_update":
            # ----------------- WORK UPDATE CARD -----------------
            card = tk.Frame(row_frame, bg="#1e293b", bd=1, relief="solid", padx=12, pady=10)
            card.pack(fill=tk.X, padx=8, pady=4)

            # Card Header
            c_header = tk.Frame(card, bg="#1e293b")
            c_header.pack(fill=tk.X, pady=(0, 6))

            av = tk.Label(
                c_header,
                text=get_initials(sender),
                font=("Segoe UI", 8, "bold"),
                fg="#ffffff",
                bg=avatar_bg,
                width=3,
                height=1
            )
            av.pack(side=tk.LEFT, padx=(0, 6))

            # Pack time right first
            tk.Label(
                c_header,
                text=time_str,
                font=("Segoe UI", 8),
                fg="#64748b",
                bg="#1e293b"
            ).pack(side=tk.RIGHT)

            tk.Label(
                c_header,
                text=f"📋 {msg.get('title', 'Work Summary')} - {sender}",
                font=("Segoe UI", 10, "bold"),
                fg="#38bdf8",
                bg="#1e293b"
            ).pack(side=tk.LEFT)

            # Shift & Total Hours bar
            meta_box = tk.Frame(card, bg="#334155", padx=8, pady=4)
            meta_box.pack(fill=tk.X, pady=(0, 6))

            meta_parts = []
            if msg.get("shift_str"):
                meta_parts.append(msg["shift_str"])
            if msg.get("total_hours"):
                meta_parts.append(f"Total: {msg['total_hours']}")
            meta_text = "  |  ".join(meta_parts) if meta_parts else f"Date: {msg.get('date_str', '')}"

            tk.Label(
                meta_box,
                text=meta_text,
                font=("Segoe UI", 8, "bold"),
                fg="#f1f5f9",
                bg="#334155"
            ).pack(anchor="w")

            # Tasks List
            tasks = msg.get("tasks", [])
            for t in tasks:
                t_row = tk.Frame(card, bg="#1e293b")
                t_row.pack(fill=tk.X, pady=2)

                st = t.get("status", "Completed")
                st_color = "#10b981" if "Complete" in st else ("#f59e0b" if "Progress" in st else "#94a3b8")

                tk.Label(
                    t_row,
                    text=f"[{st}]",
                    font=("Segoe UI", 8, "bold"),
                    fg=st_color,
                    bg="#1e293b"
                ).pack(side=tk.LEFT, padx=(0, 6))

                title_txt = t.get("title", "Task")
                hours_txt = f"({t.get('hours')}h)" if t.get("hours") else ""
                tk.Label(
                    t_row,
                    text=f"{title_txt} {hours_txt}",
                    font=("Segoe UI", 9),
                    fg="#e2e8f0",
                    bg="#1e293b"
                ).pack(side=tk.LEFT, anchor="w")

        else:
            # ----------------- STANDARD CHAT BUBBLE -----------------
            if is_me:
                # Aligned to right
                align_box = tk.Frame(row_frame, bg="#0f172a")
                align_box.pack(side=tk.RIGHT, padx=4)

                bubble = tk.Frame(align_box, bg="#2563eb", padx=10, pady=6)
                bubble.pack(anchor="e")

                tk.Label(
                    bubble,
                    text=msg.get("text", ""),
                    font=("Segoe UI", 9),
                    fg="#ffffff",
                    bg="#2563eb",
                    wraplength=480,
                    justify="left"
                ).pack(anchor="w")

                tk.Label(
                    align_box,
                    text=f"You • {time_str}",
                    font=("Segoe UI", 7),
                    fg="#64748b",
                    bg="#0f172a"
                ).pack(anchor="e", pady=(2, 0))

            else:
                # Aligned to left with avatar
                align_box = tk.Frame(row_frame, bg="#0f172a")
                align_box.pack(side=tk.LEFT, padx=4)

                top_info = tk.Frame(align_box, bg="#0f172a")
                top_info.pack(anchor="w", pady=(0, 2))

                av = tk.Label(
                    top_info,
                    text=get_initials(sender),
                    font=("Segoe UI", 7, "bold"),
                    fg="#ffffff",
                    bg=avatar_bg,
                    width=2,
                    height=1
                )
                av.pack(side=tk.LEFT, padx=(0, 4))

                tk.Label(
                    top_info,
                    text=f"{sender} • {time_str}",
                    font=("Segoe UI", 8, "bold"),
                    fg="#94a3b8",
                    bg="#0f172a"
                ).pack(side=tk.LEFT)

                bubble = tk.Frame(align_box, bg="#334155", padx=10, pady=6)
                bubble.pack(anchor="w")

                tk.Label(
                    bubble,
                    text=msg.get("text", ""),
                    font=("Segoe UI", 9),
                    fg="#f8fafc",
                    bg="#334155",
                    wraplength=480,
                    justify="left"
                ).pack(anchor="w")

        if scroll:
            self.dialog.update_idletasks()
            self.msg_canvas.yview_moveto(1.0)
