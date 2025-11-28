import re
import requests
import json
import os
import sys

# CONFIG
# Use "qwen2.5-coder:7b" if you have the larger model, otherwise "1.5b"
MODEL_NAME = "qwen2.5-coder:7b" 
OLLAMA_URL = "http://localhost:11434/api/generate"

def analyze_and_fix(code_content, error_msg):
    """
    Final Robust Patcher: Duplicate Guards, Environment Signals & Hybrid Logic
    """
    lines = code_content.splitlines()
    
    # ==========================================
    # LEVEL 0: SYNTAX & HINTS
    # ==========================================
    if "def _init_" in code_content:
        return code_content.replace("def _init_", "def __init__"), "Structure: Fixed constructor typo."

    if "Did you mean:" in error_msg:
        # Extract hint from Python error
        match = re.search(r"Did you mean: '(\w+)'", error_msg)
        if match:
            # Try to find what caused the error (NameError or AttributeError)
            bad_match = re.search(r"'(\w+)'", error_msg)
            if bad_match:
                bad = bad_match.group(1)
                good = match.group(1)
                # Only replace if it looks safe
                if len(bad) > 1:
                    return code_content.replace(bad, good), f"Hint: Fixed typo '{bad}' -> '{good}'"

    # ==========================================
    # LEVEL 1: RUNTIME SAFETY
    # ==========================================
    if "arguments are required" in error_msg:
        if "required=True" in code_content:
            return code_content.replace("required=True", "required=False, default='dummy'"), "Rule: Made CLI args optional."

    if "KeyError" in error_msg:
        match = re.search(r"KeyError: '(\w+)'", error_msg)
        if match:
            key = match.group(1)
            if "CONFIG = {" in code_content:
                repl = f'CONFIG = {{\n    "{key}": False, # [AUTO] Injected key'
                return code_content.replace("CONFIG = {", repl), f"Rule: Injected key '{key}'."

    if "RecursionError" in error_msg:
        if "setrecursionlimit" not in code_content:
            return "import sys\nsys.setrecursionlimit(3000)\n" + code_content, "Rule: Increased recursion limit."

    # 5. RECURSION & TIMEOUT
    if "RecursionError" in error_msg:
        if "setrecursionlimit" not in code_content:
            return "import sys\nsys.setrecursionlimit(3000)\n" + code_content, "Rule: Increased recursion limit."

    # FIX: Check for 'TimeLimitExceeded' OR 'timed out'
   # --- FIX: SMART INPUT MOCKER (Generic) ---
    # Detects blocking inputs and mocks them based on type context.
    if ("TimeLimitExceeded" in error_msg or "Timeout" in error_msg) and "input(" in code_content:
        new_lines = []
        for line in lines:
            if "input(" in line:
                # 1. Determine the Type
                mock_value = '"mock_input"' # Default to string (safest)
                
                if "int(input" in line:
                    mock_value = "1"
                elif "float(input" in line:
                    mock_value = "1.0"
                elif "eval(input" in line:
                    mock_value = "0"
                
                # 2. Replace the line
                if "=" in line:
                    # Logic: variable = input(...)  ->  variable = "mock"
                    var_name = line.split("=")[0].strip()
                    new_lines.append(f"{var_name} = {mock_value} # [AUTO] Mocked Input")
                else:
                    # Logic: input(...) without assignment -> Just comment it out
                    new_lines.append(f"# {line.strip()} # [AUTO] Removed blocking wait")
            else:
                new_lines.append(line)
        
        return "\n".join(new_lines), "Environment: Mocked blocking user inputs."
    
    if "ModuleNotFoundError" in error_msg:
        match = re.search(r"No module named '([\w\.-]+)'", error_msg)
        if match:
            bad = match.group(1)
            return "\n".join([l for l in lines if bad not in l]), f"Rule: Removed module '{bad}'."

    # --- FIX 1: ENVIRONMENT SIGNAL (Stops the "Stuck" error) ---
    if "FileNotFoundError" in error_msg:
        match = re.search(r"No such file or directory: '(.+?)'", error_msg)
        if match:
            path = match.group(1)
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            except: pass
            
            with open(path, "w") as f: 
                f.write("Mock Data")
            
            # CRITICAL: Append a comment so 'app.py' sees the code changed
            return code_content + f"\n# [ENV] Created mock file: {path}", f"Environment: Created mock file '{path}'."

    # --- FIX 2: DUPLICATE GUARD (Stops the 18 function copies) ---
    if "NameError" in error_msg and "is not defined" in error_msg:
        match = re.search(r"name '(\w+)'", error_msg)
        if match:
            name = match.group(1)
            
            # CHECK: Does it already exist?
            if f"def {name}" in code_content or f"{name} =" in code_content:
                pass # It exists, so this is a logic error, not a missing structure. Let LLM handle it.
            else:
                if f"{name}(" in code_content:
                    stub = f"\n\ndef {name}(*args, **kwargs):\n    print('LOG: Stub for {name}')\n    return None\n"
                    return code_content + stub, f"Structure: Stubbed function '{name}'."
                else:
                    return f"{name} = None # Auto-Def\n" + code_content, f"Structure: Defined variable '{name}'."

    # ==========================================
    # LEVEL 3: LLM FALLBACK
    # ==========================================
    print(f">>> Calling LLM ({MODEL_NAME})...")
    prompt = f"""You are a Python expert. Fix this error.
    Error: {error_msg}
    Code:
    ```python
    {code_content}
    ```
    Return FULL CODE only."""
    
    return call_ollama(prompt, code_content)

def apply_user_instruction(code_content, instruction):
    """
    Used by the 'AI Edit' bar in the GUI.
    """
    print(f">>> User Instruction: {instruction}")
    
    prompt = f"""
    You are an expert AI coding assistant.
    TASK: Modify the code according to this instruction: "{instruction}"
    RULES: Return FULL updated code only. No text.
    
    CODE:
    ```python
    {code_content}
    ```
    """
    return call_ollama(prompt, code_content)

def call_ollama(prompt, original_code):
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096}
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        out = res.json().get("response", "")
        
        match = re.search(r"```(?:python)?\n(.*?)```", out, re.DOTALL)
        new_code = match.group(1).strip() if match else out.strip()
        
        if len(new_code) < len(original_code) * 0.5:
            return original_code, "Safety: LLM truncated code."
            
        return new_code, "LLM: Logic rewritten."
    except Exception as e:
        return original_code, f"Error: {str(e)}"
