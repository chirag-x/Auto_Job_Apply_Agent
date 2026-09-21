import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from litellm import Router, completion
from src.core.crud import get_all_llm_configs

def create_llm_router():
    """
    Reads active LLM configurations from the database and creates a LiteLLM Router 
    with automatic fallbacks based on the user-defined priority.
    """
    configs = get_all_llm_configs()
    # Filter active and sort by priority (1 is highest)
    active_configs = [c for c in configs if c.get('is_active')]
    active_configs.sort(key=lambda x: x.get('priority', 99))
    
    if not active_configs:
        print("Warning: No active LLM providers configured in the database.")
        return None
    
    model_list = []
    model_names = []
    
    for idx, conf in enumerate(active_configs):
        provider = conf['provider'].lower()
        raw_model_name = conf['model_name']
        api_key = conf.get('api_key', "")
        base_url = conf.get('base_url', "")
        
        litellm_params = {}
        
        # Format for LiteLLM
        if provider == "ollama":
            litellm_params["model"] = f"ollama/{raw_model_name}"
            if base_url:
                litellm_params["api_base"] = base_url
        elif provider == "gemini":
            litellm_params["model"] = f"gemini/{raw_model_name}"
            if api_key:
                litellm_params["api_key"] = api_key
        elif provider == "openrouter":
            litellm_params["model"] = f"openrouter/{raw_model_name}"
            if api_key:
                litellm_params["api_key"] = api_key
        elif provider == "omniroute":
            # Assuming standard OpenAI compatible interface
            litellm_params["model"] = f"openai/{raw_model_name}"
            if api_key:
                litellm_params["api_key"] = api_key
            if base_url:
                litellm_params["api_base"] = base_url
        else:
            litellm_params["model"] = raw_model_name
            if api_key:
                litellm_params["api_key"] = api_key

        unique_model_alias = f"priority_{idx+1}_{provider}"
        model_names.append(unique_model_alias)
        
        model_list.append({
            "model_name": unique_model_alias,
            "litellm_params": litellm_params
        })
    
    # Configure Fallbacks: priority_1 falls back to priority_2, which falls back to priority_3...
    fallbacks = []
    if len(model_names) > 1:
        fallbacks = [{model_names[0]: model_names[1:]}]
        
    router = Router(
        model_list=model_list,
        fallbacks=fallbacks,
        num_retries=1 # Only retry once before falling back to the next model
    )
    
    return router, model_names[0]

def query_llm(messages, response_format=None):
    """
    Main entry point for agent logic to talk to the AI.
    Automatically routes to the highest priority model and handles failovers.
    """
    router_data = create_llm_router()
    if not router_data:
        raise Exception("No active LLMs configured. Please configure an LLM in the Settings tab.")
        
    router, primary_model = router_data
    
    kwargs = {
        "model": primary_model,
        "messages": messages,
    }
    
    if response_format:
        kwargs["response_format"] = response_format
        
    # LiteLLM router handles the execution and failover automatically
    response = router.completion(**kwargs)
    return response

if __name__ == "__main__":
    # Simple local test script
    print("Testing LLM Gateway Setup...")
    try:
        router_data = create_llm_router()
        if router_data:
            router, primary = router_data
            print(f"Router successfully initialized. Primary model alias: {primary}")
            print(f"Loaded {len(router.model_list)} models from database.")
    except Exception as e:
        print(f"Error: {e}")
