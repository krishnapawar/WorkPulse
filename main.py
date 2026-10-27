"""
WorkPulse - Cross-Platform Application Launcher
Automatically detects environment:
- Android: Launches Mobile Touch UI (Kivy)
- Desktop (Windows / macOS / Linux): Launches Full Desktop App (Tkinter)
"""

import sys
import os

def is_android():
    return (
        'ANDROID_BOOTLOGO' in os.environ or 
        'ANDROID_ROOT' in os.environ or 
        'ANDROID_STORAGE' in os.environ or
        sys.platform.startswith('android')
    )

def main():
    if is_android():
        # Android Mobile environment
        try:
            from mobile_app import WorkPulseMobileApp
            WorkPulseMobileApp().run()
        except Exception as e:
            print(f"Error launching Mobile App: {e}")
            import traceback
            traceback.print_exc()
    else:
        # Desktop environment (Tkinter)
        import app
        import tkinter as tk
        root = tk.Tk()
        workpulse = app.TodayWorkUpdateApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
