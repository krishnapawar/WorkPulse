"""
WorkPulse - Cross-Platform Application Launcher
Automatically detects environment:
- Android: Launches Mobile Touch UI (Kivy)
- Desktop (Windows / macOS / Linux): Launches Full Desktop App (Tkinter)
"""

import sys
import os

try:
    from storage_config import is_android
except Exception:
    def is_android():
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

def main():
    if is_android():
        # Android Mobile environment
        import datetime
        import traceback
        try:
            from mobile_app import WorkPulseMobileApp
            WorkPulseMobileApp().run()
        except Exception as e:
            err_text = traceback.format_exc()
            print(f"FATAL ERROR launching WorkPulse Mobile App:\n{err_text}")
            
            # Save crash log to disk
            for log_path in [
                "/sdcard/workpulse_crash.txt",
                os.path.expanduser("~/workpulse_crash.txt"),
                "/tmp/workpulse_crash.txt"
            ]:
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"\n========================================\n"
                                f"WorkPulse Crash at {datetime.datetime.now()}\n"
                                f"========================================\n"
                                f"{err_text}\n")
                    break
                except Exception:
                    pass

            # Safe diagnostic fallback screen so the app does not suddenly vanish
            try:
                from kivy.app import App
                from kivy.uix.boxlayout import BoxLayout
                from kivy.uix.label import Label
                from kivy.uix.scrollview import ScrollView
                from kivy.uix.button import Button
                from kivy.core.window import Window

                class WorkPulseDiagnosticApp(App):
                    def build(self):
                        if hasattr(Window, 'clearcolor'):
                            Window.clearcolor = (0.04, 0.06, 0.11, 1.0)
                        box = BoxLayout(orientation='vertical', padding=24, spacing=16)
                        lbl_title = Label(
                            text="[b]WorkPulse - Startup Diagnostic[/b]",
                            markup=True,
                            font_size='18sp',
                            size_hint_y=None,
                            height=48,
                            color=(0.95, 0.35, 0.35, 1.0)
                        )
                        box.add_widget(lbl_title)
                        lbl_msg = Label(
                            text="WorkPulse encountered an error during initialization.\nDetails have been recorded:",
                            font_size='13sp',
                            size_hint_y=None,
                            height=40,
                            color=(0.85, 0.85, 0.85, 1.0),
                            halign='center'
                        )
                        box.add_widget(lbl_msg)
                        scroll = ScrollView(size_hint=(1, 1))
                        lbl_trace = Label(
                            text=err_text,
                            font_size='11sp',
                            size_hint_y=None,
                            color=(1.0, 0.8, 0.8, 1.0),
                            halign='left',
                            valign='top'
                        )
                        lbl_trace.bind(texture_size=lambda s, ts: setattr(s, 'size', ts))
                        lbl_trace.bind(width=lambda s, w: setattr(s, 'text_size', (w, None)))
                        scroll.add_widget(lbl_trace)
                        box.add_widget(scroll)

                        btn_exit = Button(
                            text="Close",
                            font_size='14sp',
                            bold=True,
                            size_hint_y=None,
                            height=48,
                            background_normal='',
                            background_color=(0.2, 0.25, 0.35, 1.0),
                            color=(1, 1, 1, 1)
                        )
                        btn_exit.bind(on_release=lambda x: self.stop())
                        box.add_widget(btn_exit)
                        return box

                WorkPulseDiagnosticApp().run()
            except Exception as crash_ui_err:
                print(f"Diagnostic UI failed to launch: {crash_ui_err}")
    else:
        # Desktop environment (Tkinter)
        import app
        import tkinter as tk
        root = tk.Tk()
        workpulse = app.TodayWorkUpdateApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
