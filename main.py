import sys
import os
import io

# --noconsole makes sys.stdout/stderr None, which crashes uvicorn's logger
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import uvicorn
import webbrowser
import threading
import time

def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        import multiprocessing
        multiprocessing.freeze_support()
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    from server import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
