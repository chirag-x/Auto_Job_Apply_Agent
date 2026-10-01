import os
import sys
import subprocess
import time
import threading
import urllib.request
import psutil

OLLAMA_EXE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
MODEL_NAME = "gemma4:cloud"
OLLAMA_URL = "http://localhost:11434"

class OllamaManager:
    def __init__(self):
        self.running = False
        self.watchdog_thread = None

    def check_and_install(self):
        if not os.path.exists(OLLAMA_EXE):
            print("Ollama not found. Downloading...")
            installer_path = os.path.join(os.environ["TEMP"], "OllamaSetup.exe")
            urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", installer_path)
            print("Installing Ollama silently...")
            subprocess.run([installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True)
            # Wait for it to settle
            time.sleep(5)
            # Kill any auto-started visible instance
            self.kill_ollama()

    def kill_ollama(self):
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'ollama.exe' or proc.info['name'] == 'ollama app.exe':
                try:
                    proc.kill()
                except:
                    pass
        time.sleep(1)

    def start_ollama_silently(self):
        self.kill_ollama()
        if sys.platform == "win32":
            subprocess.Popen([OLLAMA_EXE, "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen([OLLAMA_EXE, "serve"], start_new_session=True)
        time.sleep(2)

    def is_model_available(self):
        try:
            result = subprocess.run([OLLAMA_EXE, "list"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return MODEL_NAME in result.stdout
        except:
            return False

    def handle_auth_and_pull(self):
        if self.is_model_available():
            return True

        print(f"Model {MODEL_NAME} missing. Launching Auth Window...")
        # Launch visible terminal for user to log in
        login_cmd = f"echo 🛡️ Norvi Agent Authentication & echo. & echo Please login to access the premium cloud model. & echo Run 'ollama pull {MODEL_NAME}' or login. & cmd.exe"
        auth_process = subprocess.Popen(["cmd.exe", "/c", "start", "Norvi Auth", "cmd.exe", "/c", login_cmd])

        print("Waiting for successful pull...")
        while True:
            # Try to pull silently
            result = subprocess.run([OLLAMA_EXE, "pull", MODEL_NAME], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 or self.is_model_available():
                print("Pull successful! Authentication complete.")
                break
            time.sleep(3)

        # Kill the visible auth window
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info['name'] == 'cmd.exe' and proc.info['cmdline'] and 'Norvi Auth' in ' '.join(proc.info['cmdline']):
                try:
                    proc.kill()
                except:
                    pass
        
        # Kill Ollama and restart silently to apply any auth changes cleanly
        self.start_ollama_silently()
        return True

    def watchdog_loop(self):
        while self.running:
            is_running = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == 'ollama.exe':
                    is_running = True
                    break
            
            if not is_running:
                print("Watchdog: Ollama died. Restarting silently...")
                self.start_ollama_silently()
            
            time.sleep(5)

    def check_and_start(self):
        self.check_and_install()
        self.start_ollama_silently()
        self.handle_auth_and_pull()
        
        self.running = True
        self.watchdog_thread = threading.Thread(target=self.watchdog_loop, daemon=True)
        self.watchdog_thread.start()

    def shutdown(self):
        self.running = False
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=2)
        self.kill_ollama()
