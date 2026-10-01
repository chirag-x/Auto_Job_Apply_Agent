import sys
import os
import subprocess
import time
import psutil

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from src.core.ollama_manager import OllamaManager

def main():
    print("Initializing Norvi Agent Environment...")
    manager = OllamaManager()
    
    # Check, install, and boot Ollama
    manager.check_and_start()

    print("Brain is online. Booting User Interface...")
    # Launch Streamlit
    streamlit_cmd = [sys.executable, "-m", "streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.headless=false"]
    
    # We want Streamlit to run in the current visible window for now
    st_process = subprocess.Popen(streamlit_cmd)
    
    try:
        # Wait until Streamlit is closed by the user
        st_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down Norvi Agent...")
        st_process.kill()
    finally:
        manager.shutdown()
        print("Shutdown complete. All ghost processes killed.")

if __name__ == "__main__":
    main()
