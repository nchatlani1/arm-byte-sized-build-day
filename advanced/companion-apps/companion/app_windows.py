"""Windows notification-area host. Uses the existing pywin32/pywebview runtime."""
from pathlib import Path
import subprocess
import sys
import threading

CLASS_NAME = 'CrowPanelCompanionTray'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'CrowPanel Companion'


def startup_command(executable):
    command = subprocess.list2cmdline([str(executable),'--background'])
    if len(command) > 260:
        raise ValueError('Move the app to a shorter permanent folder before enabling Start at sign-in.')
    return command


def startup_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key,RUN_VALUE)
        return value == startup_command(sys.executable)
    except OSError:
        return False


def set_startup(enabled):
    import winreg
    if not getattr(sys,'frozen',False):
        raise ValueError('Start at sign-in is available in the packaged app. Keep its folder in a permanent location.')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key,RUN_VALUE,0,winreg.REG_SZ,startup_command(sys.executable))
        else:
            try:
                winreg.DeleteValue(key,RUN_VALUE)
            except FileNotFoundError:
                pass


class Instance:
    def __init__(self):
        import win32api, win32event, winerror
        self.handle = win32event.CreateMutex(None,False,'Local\\CrowPanelCompanion')
        self.acquired = win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS

    def show_existing(self):
        import win32con, win32gui
        window = win32gui.FindWindow(CLASS_NAME,CLASS_NAME)
        if window:
            win32gui.PostMessage(window,win32con.WM_APP+2,0,0)


def run(url, core, background, instance):
    import webview
    import win32api, win32con, win32gui
    window = webview.create_window('CrowPanel Companion',url,width=760,height=860,min_size=(620,650),hidden=background)
    quitting = threading.Event()
    ready = threading.Event()
    tray = {'hwnd':None,'error':None}
    shown = {'value':not background}

    def visible(value):
        try:
            window.evaluate_js('window.setCompanionVisible && window.setCompanionVisible('+('true' if value else 'false')+')')
        except Exception:
            pass  # The local page can still be loading.

    def show():
        shown['value'] = True
        window.show()
        window.restore()
        visible(True)

    def hide(*_):
        if quitting.is_set():
            return True
        shown['value'] = False
        visible(False)
        window.hide()
        return False

    def quit_app():
        quitting.set()
        window.destroy()

    callback = win32con.WM_APP+1
    taskbar_created = win32gui.RegisterWindowMessage('TaskbarCreated')

    def tray_thread():
        icon = None
        try:
            def add_icon(hwnd):
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD,(hwnd,0,win32gui.NIF_ICON|win32gui.NIF_MESSAGE|win32gui.NIF_TIP,callback,icon,'CrowPanel Companion'))

            def menu(hwnd):
                with core.lock:
                    paused = not core.want_connection and not core.device_busy
                    busy = core.device_busy
                    label = 'Paused' if paused else core.device.label
                popup = win32gui.CreatePopupMenu()
                win32gui.AppendMenu(popup,win32con.MF_STRING|win32con.MF_GRAYED,0,label)
                win32gui.AppendMenu(popup,win32con.MF_SEPARATOR,0,None)
                win32gui.AppendMenu(popup,win32con.MF_STRING,1,'Open CrowPanel Companion')
                win32gui.AppendMenu(popup,win32con.MF_STRING|(win32con.MF_GRAYED if busy else 0),2,'Resume connection' if paused else 'Pause connection')
                win32gui.AppendMenu(popup,win32con.MF_STRING|(win32con.MF_CHECKED if startup_enabled() else 0),3,'Start at sign-in')
                win32gui.AppendMenu(popup,win32con.MF_SEPARATOR,0,None)
                win32gui.AppendMenu(popup,win32con.MF_STRING,4,'Quit CrowPanel Companion')
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    x,y = win32gui.GetCursorPos()
                    choice = win32gui.TrackPopupMenu(popup,win32con.TPM_RETURNCMD|win32con.TPM_RIGHTBUTTON,x,y,0,hwnd,None)
                    win32gui.PostMessage(hwnd,win32con.WM_NULL,0,0)
                finally:
                    win32gui.DestroyMenu(popup)
                try:
                    if choice == 1:
                        show()
                    elif choice == 2:
                        core.reconnect() if paused else core.disconnect()
                    elif choice == 3:
                        set_startup(not startup_enabled())
                    elif choice == 4:
                        quit_app()
                except Exception as exc:
                    win32gui.MessageBox(hwnd,str(exc),'CrowPanel Companion',win32con.MB_OK|win32con.MB_ICONINFORMATION)

            def message(hwnd,msg,wparam,lparam):
                if msg == callback:
                    if lparam in (win32con.WM_RBUTTONUP,win32con.WM_CONTEXTMENU):
                        menu(hwnd)
                    elif lparam == win32con.WM_LBUTTONDBLCLK:
                        show()
                    return 0
                if msg == win32con.WM_APP+2:
                    show()
                    return 0
                if msg == taskbar_created:
                    add_icon(hwnd)
                    return 0
                if msg == win32con.WM_POWERBROADCAST:
                    if wparam == 4:  # PBT_APMSUSPEND
                        threading.Thread(target=core.suspend,daemon=True).start()
                    elif wparam in (7,18):  # Resume from suspend or automatic wake.
                        core.resume_from_sleep()
                    return 1
                if msg == win32con.WM_CLOSE:
                    win32gui.DestroyWindow(hwnd)
                    return 0
                if msg == win32con.WM_DESTROY:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE,(hwnd,0))
                    win32gui.PostQuitMessage(0)
                    return 0
                return win32gui.DefWindowProc(hwnd,msg,wparam,lparam)

            wc = win32gui.WNDCLASS()
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = CLASS_NAME
            wc.lpfnWndProc = message
            atom = win32gui.RegisterClass(wc)
            tray['hwnd'] = win32gui.CreateWindow(atom,CLASS_NAME,0,0,0,0,0,0,0,wc.hInstance,None)
            resources = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
            icon = win32gui.LoadImage(0,str(resources/'companion/ui/tray.ico'),win32con.IMAGE_ICON,32,32,win32con.LR_LOADFROMFILE)
            add_icon(tray['hwnd'])
            ready.set()
            win32gui.PumpMessages()
        except Exception as exc:
            tray['error'] = exc
            ready.set()
            # Never hide an app with no usable tray controls.
            quitting.set()
            window.destroy()
        finally:
            if icon:
                win32gui.DestroyIcon(icon)

    def start():
        worker = threading.Thread(target=tray_thread,daemon=True,name='notification-area')
        worker.start()
        if not ready.wait(10) or tray['error']:
            win32gui.MessageBox(0,'The system tray could not start. Reopen the app from its permanent folder.','CrowPanel Companion',win32con.MB_OK|win32con.MB_ICONERROR)
            quit_app()

    window.events.closing += hide
    window.events.minimized += hide
    window.events.loaded += lambda: visible(shown['value'])
    try:
        webview.start(start)
    finally:
        quitting.set()
        if tray['hwnd']:
            win32gui.PostMessage(tray['hwnd'],win32con.WM_CLOSE,0,0)
