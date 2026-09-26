import os
from langchain_openai import ChatOpenAI as _ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI as _ChatGoogleGenerativeAI
from src.core.crud import get_all_llm_configs

# browser-use requires a 'provider' attribute and injects attributes dynamically.
# We subclass and allow extra attributes to prevent Pydantic V2 crashes without breaking LangChain.
class ChatOpenAI(_ChatOpenAI):
    model_config = {"extra": "allow"}
    
    @property
    def provider(self) -> str:
        return "openai"

class ChatGoogleGenerativeAI(_ChatGoogleGenerativeAI):
    model_config = {"extra": "allow"}
    
    @property
    def provider(self) -> str:
        return "google"
        
    @property
    def model_name(self) -> str:
        return self.model

def get_browser_use_llm():
    """
    Reads the highest priority active LLM config from the database
    and returns a LangChain ChatModel compatible with `browser-use`.
    """
    configs = get_all_llm_configs()
    active_configs = [c for c in configs if c.get('is_active')]
    active_configs.sort(key=lambda x: x.get('priority', 99))
    
    if not active_configs:
        raise ValueError("No active LLM providers configured.")
        
    best_config = active_configs[0]
    provider = best_config['provider'].lower()
    model_name = best_config['model_name']
    api_key = best_config.get('api_key', "")
    base_url = best_config.get('base_url', "")
    
    print(f"Using {provider.capitalize()} ({model_name}) for Browser-Use Agent.")
    
    if provider == "ollama":
        # The browser-use library expects standard LangChain models (like ChatOpenAI).
        # We can bypass compatibility errors by using Ollama's built-in OpenAI-compatible endpoint!
        parsed_url = base_url if base_url else "http://localhost:11434"
        if not parsed_url.endswith("/v1"):
            parsed_url = parsed_url.rstrip("/") + "/v1"
            
        return ChatOpenAI(
            model=model_name,
            api_key="ollama-local",  # Dummy key required by ChatOpenAI
            base_url=parsed_url,
            temperature=0.0
        )
    elif provider == "gemini":
        if not api_key:
            raise ValueError("Gemini requires an API Key.")
        
        os.environ["GOOGLE_API_KEY"] = api_key
        # We must use native ChatGoogleGenerativeAI and DISABLE all safety filters. 
        # When Gemini hits a safety block (like 'automated form filling'), it returns an empty response
        # which browser-use catches as error='items'.
        from langchain_google_genai import HarmCategory, HarmBlockThreshold
        safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            safety_settings=safety_settings
        )
    elif provider == "groq":
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.0
        )
    elif provider == "openrouter":
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.0
        )
    elif provider == "omniroute":
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0
        )
    else:
        # Fallback to standard OpenAI format
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url if base_url else None,
            temperature=0.0
        )

def build_llm(config, temperature=0.0, max_tokens=None):
    '''Factory to build an LLM instance from a DB config dictionary.'''
    provider = config.get('provider', '').lower()
    model_name = config.get('model_name')
    api_key = config.get('api_key') or "empty"
    base_url = config.get('base_url')

    if provider == "ollama":
        base_url = base_url if base_url else "http://localhost:11434"
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        api_key = "ollama-local"
    elif provider == "groq":
        base_url = "https://api.groq.com/openai/v1"
    elif provider == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
    
    if provider == "gemini":
        if not api_key or api_key == "empty":
            raise ValueError("Gemini requires an API Key.")
        os.environ["GOOGLE_API_KEY"] = api_key
        from langchain_google_genai import HarmCategory, HarmBlockThreshold
        safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
        kwargs = {
            "model": model_name,
            "temperature": temperature,
            "safety_settings": safety_settings
        }
        if max_tokens: kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)
        
    kwargs = {
        "model": model_name,
        "api_key": api_key,
        "temperature": temperature,
        "timeout": 25.0
    }
    if base_url: kwargs["base_url"] = base_url
    if max_tokens: kwargs["max_tokens"] = max_tokens
    
    return ChatOpenAI(**kwargs)
