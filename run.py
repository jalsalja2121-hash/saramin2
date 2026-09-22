"""Start the app using the interpreter that runs this file."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    raise SystemExit(subprocess.call([
        sys.executable, "-m", "streamlit", "run", str(root / "streamlit_app.py"),
        "--server.address", "127.0.0.1", "--server.headless", "true", *sys.argv[1:]
    ], cwd=root))
