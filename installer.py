#!/usr/bin/env python3
"""
Disk Atlas — Setup & Installation Wizard
Installs Disk Atlas, asks user for destination directory, creates Desktop & Start Menu shortcuts.
Handles Administrator elevation automatically for directories like C:\\Program Files and C:\\Program Files (x86).
"""

import os
import sys
import shutil
import zipfile
import tempfile
import threading
import subprocess
import ctypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Determine payload location
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent

PAYLOAD_ZIP = BUNDLE_DIR / "DiskAtlas_Payload.zip"

def is_admin():
    if sys.platform != 'win32':
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_installer(target_dir=None):
    if sys.platform != 'win32':
        return False
    try:
        args = []
        if target_dir:
            args.extend(["--dir", target_dir])
        params = " ".join([f'"{a}"' for a in args])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        return ret > 32
    except Exception as e:
        print(f"Elevation error: {e}")
        return False

def create_windows_shortcut(target_exe, shortcut_lnk, description="Disk Atlas — 3D Disk Visualizer"):
    try:
        os.makedirs(os.path.dirname(shortcut_lnk), exist_ok=True)
        ps_content = f'''$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("{shortcut_lnk}")
$sc.TargetPath = "{target_exe}"
$sc.WorkingDirectory = "{os.path.dirname(target_exe)}"
$sc.Description = "{description}"
$sc.Save()
'''
        ps_path = os.path.join(tempfile.gettempdir(), f"shortcut_{os.getpid()}_{hash(shortcut_lnk) & 0xffff}.ps1")
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(ps_content)
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps_path],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if os.path.exists(ps_path):
            os.remove(ps_path)
        return True
    except Exception as e:
        print(f"Error creating shortcut {shortcut_lnk}: {e}")
        return False

def create_uninstaller_script(target_dir, target_exe):
    uninstall_cmd_path = os.path.join(target_dir, "uninstall.cmd")
    cmd_content = r'''@echo off
setlocal
title Disk Atlas Uninstaller
cls

if /i "%~1"=="/silent" goto do_uninstall
if /i "%~1"=="/quiet" goto do_uninstall
if /i "%~1"=="-s" goto do_uninstall

echo ====================================================
echo             Disk Atlas Uninstall
echo ====================================================
echo.
powershell -NoProfile -NonInteractive -Command "$ans = [System.Windows.Forms.MessageBox]::Show('Are you sure you want to completely remove Disk Atlas and all of its components?', 'Disk Atlas Uninstall', 'YesNo', 'Question'); if ($ans -ne 'Yes') { exit 1 }"
if errorlevel 1 (
    echo Uninstall cancelled by user.
    exit /b 1
)

:do_uninstall
echo Uninstalling Disk Atlas...

:: Terminate running processes
taskkill /f /im DiskAtlas.exe >nul 2>&1

:: Remove Windows Installed Apps Registry entries
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas" /f >nul 2>&1
reg delete "HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas" /f >nul 2>&1

:: Remove Desktop shortcuts
del /f /q "%USERPROFILE%\Desktop\Disk Atlas.lnk" >nul 2>&1
del /f /q "%PUBLIC%\Desktop\Disk Atlas.lnk" >nul 2>&1

:: Remove Start Menu shortcuts
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Disk Atlas.lnk" >nul 2>&1
del /f /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Disk Atlas.lnk" >nul 2>&1

:: Remove directory files
set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"
echo.
echo Disk Atlas has been successfully uninstalled.
timeout /t 2 /nobreak >nul

start /b "" cmd /c timeout /t 1 /nobreak ^>nul ^& rd /s /q "%INSTALL_DIR%"
exit /b 0
'''
    try:
        with open(uninstall_cmd_path, "w", encoding="utf-8") as f:
            f.write(cmd_content)
        return uninstall_cmd_path
    except Exception as e:
        print(f"Failed to create uninstaller script: {e}")
        return None

def register_in_windows_apps(target_dir, target_exe):
    """Registers Disk Atlas in Windows Settings > Installed apps / Apps & features."""
    if sys.platform != 'win32':
        return

    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    uninstall_cmd = os.path.join(target_dir, "uninstall.cmd")
    uninstall_str = f'cmd.exe /c ""{uninstall_cmd}""'
    quiet_uninstall_str = f'cmd.exe /c ""{uninstall_cmd}" /silent"'
    icon_str = f'"{target_exe}",0'

    # 1. Method A: Windows winreg module
    try:
        import winreg
        targets = []
        if is_admin():
            targets.append((winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas", winreg.KEY_WOW64_64KEY))
            targets.append((winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas", winreg.KEY_WOW64_32KEY))
        targets.append((winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas", 0))

        for root_key, subkey, sam in targets:
            try:
                flags = winreg.KEY_WRITE | sam if sam else winreg.KEY_WRITE
                key = winreg.CreateKeyEx(root_key, subkey, 0, flags)
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Disk Atlas")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "2.0.0")
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Disk Atlas Team")
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_str)
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target_dir))
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_str)
                winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, quiet_uninstall_str)
                winreg.SetValueEx(key, "InstallDate", 0, winreg.REG_SZ, today)
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 35840)
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "HelpLink", 0, winreg.REG_SZ, "https://github.com")
                winreg.SetValueEx(key, "URLInfoAbout", 0, winreg.REG_SZ, "https://github.com")
                winreg.CloseKey(key)
            except Exception as e:
                print(f"winreg error for {subkey}: {e}")
    except Exception as e:
        print(f"winreg import error: {e}")

    # 2. Method B: reg.exe add (fallback & reinforcement across standard hives)
    reg_roots = []
    if is_admin():
        reg_roots.append(r"HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas")
        reg_roots.append(r"HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas")
    reg_roots.append(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\DiskAtlas")

    for rk in reg_roots:
        cmds = [
            f'reg add "{rk}" /v "DisplayName" /t REG_SZ /d "Disk Atlas" /f',
            f'reg add "{rk}" /v "DisplayVersion" /t REG_SZ /d "2.0.0" /f',
            f'reg add "{rk}" /v "Publisher" /t REG_SZ /d "Disk Atlas Team" /f',
            f'reg add "{rk}" /v "DisplayIcon" /t REG_SZ /d "{icon_str}" /f',
            f'reg add "{rk}" /v "InstallLocation" /t REG_SZ /d "{target_dir}" /f',
            f'reg add "{rk}" /v "UninstallString" /t REG_SZ /d "{uninstall_str}" /f',
            f'reg add "{rk}" /v "QuietUninstallString" /t REG_SZ /d "{quiet_uninstall_str}" /f',
            f'reg add "{rk}" /v "InstallDate" /t REG_SZ /d "{today}" /f',
            f'reg add "{rk}" /v "EstimatedSize" /t REG_DWORD /d 35840 /f',
            f'reg add "{rk}" /v "NoModify" /t REG_DWORD /d 1 /f',
            f'reg add "{rk}" /v "NoRepair" /t REG_DWORD /d 1 /f'
        ]
        for cmd in cmds:
            try:
                subprocess.run(
                    cmd,
                    shell=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

class DiskAtlasInstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Disk Atlas Setup")
        self.root.geometry("580x440")
        self.root.resizable(False, False)

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Palette
        self.bg_color = "#0f172a"
        self.card_color = "#1e293b"
        self.text_color = "#f8fafc"
        self.muted_color = "#94a3b8"
        self.accent_color = "#3b82f6"

        self.root.configure(bg=self.bg_color)

        # Main Layout Container
        main_frame = tk.Frame(root, bg=self.bg_color, padx=24, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header Banner
        header_frame = tk.Frame(main_frame, bg=self.card_color, padx=16, pady=14, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, pady=(0, 16))

        admin_badge = " [Administrator]" if is_admin() else ""
        title_lbl = tk.Label(
            header_frame,
            text=f"🌐 Disk Atlas Setup{admin_badge}",
            font=("Segoe UI", 14, "bold"),
            fg=self.text_color,
            bg=self.card_color
        )
        title_lbl.pack(anchor=tk.W)

        subtitle_lbl = tk.Label(
            header_frame,
            text="Interactive 3D Disk Space Visualizer (City • Layers • Terrain)",
            font=("Segoe UI", 9),
            fg=self.muted_color,
            bg=self.card_color
        )
        subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 2. Destination Folder Section
        folder_section = tk.Frame(main_frame, bg=self.bg_color)
        folder_section.pack(fill=tk.X, pady=(0, 14))

        folder_lbl = tk.Label(
            folder_section,
            text="Choose folder where Disk Atlas will be saved & installed:",
            font=("Segoe UI", 9, "bold"),
            fg=self.text_color,
            bg=self.bg_color
        )
        folder_lbl.pack(anchor=tk.W, pady=(0, 6))

        path_row = tk.Frame(folder_section, bg=self.bg_color)
        path_row.pack(fill=tk.X)

        # Check command line args for preselected directory
        initial_dir = None
        if "--dir" in sys.argv:
            try:
                idx = sys.argv.index("--dir")
                if idx + 1 < len(sys.argv):
                    initial_dir = sys.argv[idx + 1]
            except Exception:
                pass

        if not initial_dir:
            if is_admin():
                # Prefer Program Files when running as administrator
                prog_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", "C:\\Program Files (x86)"))
                initial_dir = os.path.join(prog_files, "DiskAtlas")
            else:
                initial_dir = os.path.join(
                    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Programs",
                    "DiskAtlas"
                )

        self.path_var = tk.StringVar(value=initial_dir)

        self.path_entry = tk.Entry(
            path_row,
            textvariable=self.path_var,
            font=("Segoe UI", 9),
            bg=self.card_color,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#334155"
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        browse_btn = tk.Button(
            path_row,
            text="Browse...",
            font=("Segoe UI", 9),
            bg=self.card_color,
            fg=self.text_color,
            activebackground=self.accent_color,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.browse_folder
        )
        browse_btn.pack(side=tk.RIGHT)

        # 3. Shortcut Checkboxes
        opts_frame = tk.Frame(main_frame, bg=self.bg_color)
        opts_frame.pack(fill=tk.X, pady=(0, 16))

        self.desktop_var = tk.BooleanVar(value=True)
        chk_desktop = tk.Checkbutton(
            opts_frame,
            text="Create Desktop shortcut",
            variable=self.desktop_var,
            font=("Segoe UI", 9),
            bg=self.bg_color,
            fg=self.text_color,
            selectcolor=self.card_color,
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        chk_desktop.pack(anchor=tk.W, pady=2)

        self.startmenu_var = tk.BooleanVar(value=True)
        chk_startmenu = tk.Checkbutton(
            opts_frame,
            text="Add to Windows Start Menu",
            variable=self.startmenu_var,
            font=("Segoe UI", 9),
            bg=self.bg_color,
            fg=self.text_color,
            selectcolor=self.card_color,
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        chk_startmenu.pack(anchor=tk.W, pady=2)

        self.launch_var = tk.BooleanVar(value=True)
        chk_launch = tk.Checkbutton(
            opts_frame,
            text="Launch Disk Atlas when installation finishes",
            variable=self.launch_var,
            font=("Segoe UI", 9),
            bg=self.bg_color,
            fg=self.text_color,
            selectcolor=self.card_color,
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        chk_launch.pack(anchor=tk.W, pady=2)

        # 4. Progress Area
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))

        self.status_lbl = tk.Label(
            main_frame,
            text="Ready to install.",
            font=("Segoe UI", 8),
            fg=self.muted_color,
            bg=self.bg_color
        )
        self.status_lbl.pack(anchor=tk.W, pady=(0, 16))

        # 5. Buttons Footer
        btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 9),
            bg=self.card_color,
            fg=self.text_color,
            relief=tk.FLAT,
            padx=16,
            pady=5,
            cursor="hand2",
            command=self.root.quit
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.install_btn = tk.Button(
            btn_frame,
            text="Install Disk Atlas",
            font=("Segoe UI", 9, "bold"),
            bg=self.accent_color,
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=5,
            cursor="hand2",
            command=self.start_installation
        )
        self.install_btn.pack(side=tk.RIGHT)

    def browse_folder(self):
        selected = filedialog.askdirectory(
            title="Select Destination Folder",
            initialdir=self.path_var.get()
        )
        if selected:
            self.path_var.set(os.path.normpath(selected))

    def start_installation(self):
        target_dir = self.path_var.get().strip()
        if not target_dir:
            messagebox.showerror("Error", "Please specify a destination folder.")
            return

        # Check if destination is in Program Files and needs elevation
        is_prog_files = "program files" in target_dir.lower()
        if is_prog_files and not is_admin():
            elevate_now = messagebox.askyesno(
                "Administrator Rights Required",
                f"Installing into '{target_dir}' requires Administrator privileges.\n\n"
                "Would you like to elevate and run setup as Administrator?"
            )
            if elevate_now:
                if elevate_installer(target_dir):
                    self.root.destroy()
                    sys.exit(0)
            return

        self.install_btn.config(state=tk.DISABLED, bg="#475569")
        self.cancel_btn.config(state=tk.DISABLED)
        self.status_lbl.config(text="Preparing installation...")

        threading.Thread(target=self._run_install_worker, args=(target_dir,), daemon=True).start()

    def _run_install_worker(self, target_dir):
        try:
            target_path = Path(target_dir)
            target_path.mkdir(parents=True, exist_ok=True)

            if not PAYLOAD_ZIP.exists():
                raise FileNotFoundError(f"Installation payload not found: {PAYLOAD_ZIP}")

            # Extract zip payload
            with zipfile.ZipFile(PAYLOAD_ZIP, 'r') as zf:
                members = zf.infolist()
                total = len(members)

                for i, member in enumerate(members):
                    zf.extract(member, target_path)
                    progress = ((i + 1) / total) * 75
                    self.root.after(0, lambda p=progress, name=member.filename: self._update_progress(p, f"Installing: {name}"))

            target_exe = target_path / "DiskAtlas.exe"
            if not target_exe.exists():
                exes = list(target_path.glob("*.exe"))
                if exes:
                    target_exe = exes[0]

            self.root.after(0, lambda: self._update_progress(85, "Creating shortcuts..."))

            # Create Desktop Shortcut(s)
            if self.desktop_var.get() and sys.platform == 'win32':
                user_desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
                create_windows_shortcut(str(target_exe), os.path.join(user_desktop, "Disk Atlas.lnk"))

                # Also place on Public Desktop if installing system-wide as admin
                if is_admin():
                    public_desktop = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
                    if os.path.exists(public_desktop):
                        create_windows_shortcut(str(target_exe), os.path.join(public_desktop, "Disk Atlas.lnk"))

            # Create Start Menu Shortcut(s)
            if self.startmenu_var.get() and sys.platform == 'win32':
                user_start = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")),
                    "Microsoft", "Windows", "Start Menu", "Programs"
                )
                create_windows_shortcut(str(target_exe), os.path.join(user_start, "Disk Atlas.lnk"))

                # Also place in Common Start Menu if installing system-wide as admin
                if is_admin():
                    common_start = os.path.join(
                        os.environ.get("ProgramData", r"C:\ProgramData"),
                        "Microsoft", "Windows", "Start Menu", "Programs"
                    )
                    if os.path.exists(common_start):
                        create_windows_shortcut(str(target_exe), os.path.join(common_start, "Disk Atlas.lnk"))

            # Create uninstaller script and register in Windows Settings > Installed Apps list
            self.root.after(0, lambda: self._update_progress(92, "Registering in Windows Installed Apps..."))
            create_uninstaller_script(str(target_path), str(target_exe))
            register_in_windows_apps(str(target_path), str(target_exe))

            self.root.after(0, lambda: self._update_progress(100, "Installation complete!"))
            self.root.after(0, lambda: self._on_install_complete(str(target_exe)))

        except PermissionError as pe:
            self.root.after(0, lambda: self._on_permission_error(target_dir, str(pe)))
        except Exception as e:
            self.root.after(0, lambda err=str(e): self._on_install_error(err))

    def _update_progress(self, val, msg):
        self.progress_var.set(val)
        self.status_lbl.config(text=msg)

    def _on_permission_error(self, target_dir, err_msg):
        self.install_btn.config(state=tk.NORMAL, bg=self.accent_color)
        self.cancel_btn.config(state=tk.NORMAL)
        self.status_lbl.config(text="Permission denied.")

        if not is_admin():
            elevate_now = messagebox.askyesno(
                "Administrator Rights Required",
                f"Permission denied writing to:\n{target_dir}\n\n"
                "Administrator privileges are required for this folder.\n"
                "Would you like to restart setup with Administrator privileges?"
            )
            if elevate_now:
                if elevate_installer(target_dir):
                    self.root.destroy()
                    sys.exit(0)
        else:
            messagebox.showerror(
                "Permission Denied",
                f"Cannot write to:\n{target_dir}\n\n"
                "The destination folder or a file inside it may be locked by another running process.\n"
                "Please close any open instances of Disk Atlas and try again."
            )

    def _on_install_complete(self, installed_exe):
        messagebox.showinfo(
            "Installation Complete",
            f"Disk Atlas has been successfully installed!\n\n"
            f"Location: {os.path.dirname(installed_exe)}\n"
            f"Shortcuts have been added to your Desktop and Start Menu."
        )

        if self.launch_var.get() and os.path.exists(installed_exe):
            subprocess.Popen([installed_exe], cwd=os.path.dirname(installed_exe))

        self.root.destroy()

    def _on_install_error(self, err):
        self.install_btn.config(state=tk.NORMAL, bg=self.accent_color)
        self.cancel_btn.config(state=tk.NORMAL)
        self.status_lbl.config(text="Installation failed.")
        messagebox.showerror("Installation Error", f"An error occurred during installation:\n\n{err}")

def main():
    root = tk.Tk()
    app = DiskAtlasInstallerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
