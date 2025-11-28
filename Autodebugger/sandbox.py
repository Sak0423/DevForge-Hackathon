import subprocess
import sys

def run_code(filename):
    """
    Runs the python script with a strict TIMEOUT.
    """
    try:
        # We enforce a 2-second timeout. 
        # If code runs longer, it raises subprocess.TimeoutExpired
        result = subprocess.run(
            [sys.executable, filename],
            capture_output=True,
            text=True,
            timeout=2  # <--- THIS IS THE KEY FIX
        )
        
        # Check if the script crashed (non-zero exit code)
        if result.returncode != 0:
            return {
                "success": False, 
                "error": result.stderr, 
                "output": result.stdout
            }
        
        return {
            "success": True, 
            "output": result.stdout, 
            "error": ""
        }

    except subprocess.TimeoutExpired:
        # This catches the Infinite Loop!
        return {
            "success": False,
            "error": "TimeLimitExceeded: Process timed out. Infinite loop detected.",
            "output": ""
        }

    except Exception as e:
        return {
            "success": False, 
            "error": str(e), 
            "output": ""
        }
