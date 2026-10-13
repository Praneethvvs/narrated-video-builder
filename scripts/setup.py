"""One-time setup: Python deps, Playwright Chromium, GSAP (npm) and the Kokoro voice model (~340 MB).

  python scripts/setup.py              # everything
  python scripts/setup.py --no-pip     # skip pip install (deps already in your venv)

Model downloads go to <skill>/models (or $NVB_MODELS). Behind a TLS-intercepting proxy, `pip install truststore`
first so Python trusts the OS certificate store.
"""
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("NVB_MODELS", SKILL / "models"))
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]


def run(*cmd, cwd=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd, shell=(os.name == "nt" and cmd[0] == "npm"))


def main():
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    if "--no-pip" not in sys.argv:
        run(sys.executable, "-m", "pip", "install", "-r", str(SKILL / "requirements.txt"))
    run(sys.executable, "-m", "playwright", "install", "chromium")
    if not (SKILL / "node_modules" / "gsap").exists():
        if not shutil.which("npm"):
            sys.exit("npm not found: install Node.js, then re-run (GSAP is loaded from local node_modules)")
        run("npm", "install", cwd=str(SKILL))
    MODELS.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dst = MODELS / f
        if dst.exists():
            print("ok", dst)
            continue
        print("downloading", f)
        urllib.request.urlretrieve(BASE + f, dst.with_suffix(".part"))
        dst.with_suffix(".part").rename(dst)
    print("setup complete")


if __name__ == "__main__":
    main()
