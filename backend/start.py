import subprocess
import sys


def main():

    subprocess.check_call([
        sys.executable,
        "-m",
        "uvicorn",
        "app.core.app:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000"
    ])


if __name__ == "__main__":
    main()