import subprocess
import sys
import importlib


REQUIREMENTS_FILE = "requirements.txt"


def install_requirements():
    print("[BOOTSTRAP] Installing dependencies...")

    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        REQUIREMENTS_FILE
    ])


def verify_imports():
    print("[BOOTSTRAP] Verifying imports...")

    critical_modules = [
        "fastapi",
        "uvicorn",
        "openai",
        "pydantic",
    ]

    for module in critical_modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"[BOOTSTRAP] Missing: {module}")
            raise


def main():
    install_requirements()
    verify_imports()
    print("[BOOTSTRAP] OK - environment ready")


if __name__ == "__main__":
    main()