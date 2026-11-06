"""
WorkPulse - Cross-Platform Storage & Environment Configuration
Handles persistent storage paths, Android runtime environment detection,
Wi-Fi multicast locks, Android native notifications, and GUI fallbacks.
"""

import os
import sys
import shutil

_MULTICAST_LOCK = None


def is_android():
    """
    Detects if the application is running inside an Android environment
    across various Android launchers (python-for-android, Termux, Kivy).
    """
    return (
        'ANDROID_BOOTLOGO' in os.environ or
        'ANDROID_ROOT' in os.environ or
        'ANDROID_STORAGE' in os.environ or
        'ANDROID_ARGUMENT' in os.environ or
        'ANDROID_PRIVATE' in os.environ or
        'ANDROID_APP_PATH' in os.environ or
        'PYTHON_SERVICE_ARGUMENT' in os.environ or
        'P4A_BOOTSTRAP' in os.environ or
        sys.platform.startswith('android')
    )


def get_storage_dir():
    """
    Returns a guaranteed writable storage directory across Android and Desktop.
    On Android: uses Kivy running app's user_data_dir or ANDROID_PRIVATE.
    On Desktop: uses the application directory.
    """
    if is_android():
        # 1. Kivy active application private user data directory
        try:
            from kivy.app import App
            running = App.get_running_app()
            if running and hasattr(running, 'user_data_dir') and running.user_data_dir:
                d = running.user_data_dir
                os.makedirs(d, exist_ok=True)
                return d
        except Exception:
            pass

        # 2. Android private app directory environment variables
        for env_k in ('ANDROID_PRIVATE', 'ANDROID_APP_PATH'):
            p = os.environ.get(env_k)
            if p and os.path.exists(p):
                target = os.path.join(p, 'files') if not p.endswith('files') else p
                os.makedirs(target, exist_ok=True)
                return target

        # 3. Fallback to home/user directory on Android
        home = os.path.expanduser('~')
        if home and os.path.exists(home):
            wp_dir = os.path.join(home, 'workpulse_data')
            os.makedirs(wp_dir, exist_ok=True)
            return wp_dir

    # Desktop: directory where main application scripts live
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return base_dir


def get_storage_path(filename):
    """
    Resolves the absolute path for a data file in the writable storage directory.
    If the file does not exist yet in the writable storage directory, but a bundled
    version exists in the application root, it automatically copies it over.
    """
    storage_dir = get_storage_dir()
    target_path = os.path.join(storage_dir, filename)

    if not os.path.exists(target_path):
        bundled_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(bundled_path) and os.path.abspath(bundled_path) != os.path.abspath(target_path):
            try:
                shutil.copy2(bundled_path, target_path)
            except Exception as e:
                print(f"Notice: could not copy bundled {filename} to {target_path}: {e}")

    return target_path


def get_or_create_device_id():
    """
    Returns a persistent, unique device identifier for this installation.
    1. Reads saved device_id from persistent storage file (device_id.txt) or settings.
    2. On Android: attempts to query hardware Settings.Secure.ANDROID_ID via pyjnius.
    3. Desktop / Fallback: generates a stable UUID and saves it permanently to disk.
    Guaranteed to remain constant across app restarts, reboots, and updates.
    """
    dev_file = get_storage_path("device_id.txt")
    if os.path.exists(dev_file):
        try:
            with open(dev_file, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved and len(saved) >= 6:
                    return saved
        except Exception:
            pass

    if is_android():
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            SettingsSecure = autoclass('android.provider.Settings$Secure')
            activity = getattr(PythonActivity, 'mActivity', None)
            if activity:
                cr = activity.getContentResolver()
                aid = SettingsSecure.getString(cr, SettingsSecure.ANDROID_ID)
                if aid and len(str(aid).strip()) >= 6:
                    dev_id = f"dev_{str(aid).strip()[:12]}"
                    try:
                        with open(dev_file, "w", encoding="utf-8") as f:
                            f.write(dev_id)
                    except Exception:
                        pass
                    return dev_id
        except Exception as e:
            print(f"Notice: Android ANDROID_ID query: {e}")

    import uuid
    dev_id = f"dev_{uuid.uuid4().hex[:12]}"
    try:
        with open(dev_file, "w", encoding="utf-8") as f:
            f.write(dev_id)
    except Exception as e:
        print(f"Notice: could not save device_id: {e}")

    return dev_id


def get_persistent_user_id(user_name="Developer"):
    """
    Returns a permanent LAN user ID combining the user's name and unique device ID.
    Format: '<clean_name>_<device_id>' (e.g. 'developer_dev_a1b2c3d4e5f6').
    Remains strictly identical across app restarts so chats and peer IDs never reset.
    """
    import re
    device_id = get_or_create_device_id()
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', (user_name or "user").lower())[:10] or "user"
    return f"{clean_name}_{device_id}"


# ==============================================================================
# Android Hardware & OS Integrations (Multicast Lock & System Notifications)
# ==============================================================================

def acquire_android_multicast_lock():
    """
    Acquires an Android WifiManager.MulticastLock so the Wi-Fi chip does not
    discard incoming UDP broadcast/multicast packets on Android.
    """
    global _MULTICAST_LOCK
    if _MULTICAST_LOCK is not None:
        return _MULTICAST_LOCK
    if not is_android():
        return None

    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        activity = PythonActivity.mActivity
        if activity:
            wifi_service = activity.getSystemService(Context.WIFI_SERVICE)
            if wifi_service:
                _MULTICAST_LOCK = wifi_service.createMulticastLock("workpulse_multicast_lock")
                _MULTICAST_LOCK.setReferenceCounted(True)
                _MULTICAST_LOCK.acquire()
                print("Android Wi-Fi MulticastLock acquired successfully!")
                return _MULTICAST_LOCK
    except Exception as e:
        print(f"Notice: Android Wi-Fi MulticastLock could not be acquired: {e}")
    return None


def release_android_multicast_lock():
    """Releases the Android WifiManager.MulticastLock when stopping LAN chat."""
    global _MULTICAST_LOCK
    if _MULTICAST_LOCK is not None:
        try:
            if hasattr(_MULTICAST_LOCK, "isHeld") and _MULTICAST_LOCK.isHeld():
                _MULTICAST_LOCK.release()
            print("Android Wi-Fi MulticastLock released.")
        except Exception:
            pass
        _MULTICAST_LOCK = None


def get_android_network_info():
    """
    Queries Android's java.net.NetworkInterface via pyjnius to accurately detect
    the active Wi-Fi IPv4 address and subnet broadcast address even on offline routers.
    Returns (local_ip, [broadcast_addresses]) or (None, []).
    """
    if not is_android():
        return None, []

    try:
        from jnius import autoclass
        NetworkInterface = autoclass('java.net.NetworkInterface')
        interfaces = NetworkInterface.getNetworkInterfaces()
        local_ips = []
        broadcasts = set()

        while interfaces.hasMoreElements():
            iface = interfaces.nextElement()
            if iface.isLoopback() or not iface.isUp():
                continue

            name = iface.getName().lower()
            addrs = iface.getInterfaceAddresses()
            for i in range(addrs.size()):
                ia = addrs.get(i)
                addr = ia.getAddress()
                ip_str = addr.getHostAddress()
                if ip_str and "." in ip_str and not ip_str.startswith("127."):
                    # Prefer Wi-Fi / Ethernet interface names
                    if "wlan" in name or "eth" in name or "swlan" in name:
                        local_ips.insert(0, ip_str)
                    else:
                        local_ips.append(ip_str)

                    bcast = ia.getBroadcast()
                    if bcast:
                        bcast_ip = bcast.getHostAddress()
                        if bcast_ip and "." in bcast_ip:
                            broadcasts.add(bcast_ip)

        primary_ip = local_ips[0] if local_ips else None
        return primary_ip, list(broadcasts)
    except Exception as e:
        print(f"Notice: Android network interface detection: {e}")
        return None, []


def show_android_notification(title, message):
    """
    Displays a native Android system notification in the notification bar
    using Android NotificationManager with channel support (Android 8.0+).
    """
    if not is_android():
        return False

    try:
        import time
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        Intent = autoclass('android.content.Intent')
        PendingIntent = autoclass('android.app.PendingIntent')
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        Build = autoclass('android.os.Build')

        activity = PythonActivity.mActivity
        if not activity:
            return False

        channel_id = "workpulse_channel"
        channel_name = "WorkPulse Alerts"
        notification_manager = activity.getSystemService(Context.NOTIFICATION_SERVICE)

        # Android 8.0+ (API 26+) requires NotificationChannel
        if Build.VERSION.SDK_INT >= 26:
            importance = NotificationManager.IMPORTANCE_HIGH
            channel = NotificationChannel(channel_id, channel_name, importance)
            channel.setDescription("WorkPulse task and schedule notifications")
            channel.enableVibration(True)
            notification_manager.createNotificationChannel(channel)

        intent = Intent(activity, PythonActivity)
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP)
        flags = PendingIntent.FLAG_UPDATE_CURRENT
        if Build.VERSION.SDK_INT >= 31:
            flags |= PendingIntent.FLAG_IMMUTABLE

        pending_intent = PendingIntent.getActivity(activity, 0, intent, flags)

        # Try androidx first, fallback to standard android.app.Notification.Builder
        builder = None
        try:
            NotificationCompatBuilder = autoclass('androidx.core.app.NotificationCompat$Builder')
            builder = NotificationCompatBuilder(activity, channel_id)
        except Exception:
            NativeBuilder = autoclass('android.app.Notification$Builder')
            if Build.VERSION.SDK_INT >= 26:
                builder = NativeBuilder(activity, channel_id)
            else:
                builder = NativeBuilder(activity)

        builder.setContentTitle(str(title))
        builder.setContentText(str(message))
        builder.setContentIntent(pending_intent)
        builder.setAutoCancel(True)
        try:
            icon_id = activity.getApplicationInfo().icon
            builder.setSmallIcon(icon_id)
        except Exception:
            pass

        notification_id = int(time.time() * 1000) % 100000
        notification_manager.notify(notification_id, builder.build())

        # Play system notification ringtone & vibrate
        try:
            RingtoneManager = autoclass('android.media.RingtoneManager')
            notification_uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            r = RingtoneManager.getRingtone(activity.getApplicationContext(), notification_uri)
            if r:
                r.play()
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Notice: Could not post Android system notification: {e}")
        return False


# ==============================================================================
# GUI Fallback Classes for Non-Tkinter Environments (Android / Headless)
# ==============================================================================

class DummyMessageBox:
    """Safe fallback for tkinter.messagebox when running on Android or headless."""
    @staticmethod
    def showerror(title="", message="", **kwargs):
        print(f"[WorkPulse Error: {title}] {message}")

    @staticmethod
    def showinfo(title="", message="", **kwargs):
        print(f"[WorkPulse Info: {title}] {message}")

    @staticmethod
    def showwarning(title="", message="", **kwargs):
        print(f"[WorkPulse Warning: {title}] {message}")

    @staticmethod
    def askyesno(title="", message="", **kwargs):
        return True

    @staticmethod
    def askokcancel(title="", message="", **kwargs):
        return True


class DummyFileDialog:
    """Safe fallback for tkinter.filedialog when running on Android or headless."""
    @staticmethod
    def askopenfilename(**kwargs):
        return ""

    @staticmethod
    def asksaveasfilename(**kwargs):
        return ""

    @staticmethod
    def askdirectory(**kwargs):
        return ""

