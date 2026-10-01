import os
import sys
import psutil
import subprocess
import time
from langchain_openai import ChatOpenAI as _ChatOpenAI

# browser-use requires a 'provider' attribute and injects attributes dynamically.
class ChatOpenAI(_ChatOpenAI):
    model_config = {"extra": "allow"}
    
    @property
    def provider(self) -> str:
        return "openai"

def ensure_ollama_running():
    """Lightweight check to ensure Ollama is alive before we return the LLM"""
    is_running = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'ollama.exe':
                is_running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    if not is_running:
        print("[Brain] Offline! Auto-reviving Ollama silently...", flush=True)
        try:
            # We import here to avoid circular dependencies
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
            from src.core.ollama_manager import OLLAMA_EXE
            
            if sys.platform == "win32":
                subprocess.Popen([OLLAMA_EXE, "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([OLLAMA_EXE, "serve"], start_new_session=True)
            time.sleep(2.5) # Give it time to bind to the port
        except Exception as e:
            print(f"Failed to auto-revive Ollama: {e}", flush=True)

def get_browser_use_llm():
    """
    Hardcoded to use the Norvi centralized Ollama backend.
    """
    ensure_ollama_running()
    
    print("Using Norvi Managed LLM (gemma4:cloud) for Browser-Use Agent.", flush=True)
    return ChatOpenAI(
        model="gemma4:cloud",
        api_key="norvi-agency-key",  
        base_url="http://localhost:11434/v1",
        temperature=0.0
    )

def build_llm(config=None, temperature=0.0, max_tokens=None):
    """
    Hardcoded to use the Norvi centralized Ollama backend.
    """
    ensure_ollama_running()
    
    kwargs = {
        "model": "gemma4:cloud",
        "api_key": "norvi-agency-key",
        "temperature": temperature,
        "base_url": "http://localhost:11434/v1",
        "timeout": 25.0
    }
    if max_tokens: kwargs["max_tokens"] = max_tokens
    
    return ChatOpenAI(**kwargs)
