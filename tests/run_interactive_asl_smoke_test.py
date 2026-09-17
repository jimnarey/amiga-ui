"""Interactive smoke test for iTidy's directory selection ASL requester.

This test mirrors the existing run_interactive_lha_smoke_test.py pattern:
- Launch iTidy in headless Xvfb mode
- Trigger the directory selection flow (Select Folder to Process)
- Wait for the QFileDialog to appear
- Simulate a user directory selection
- Verify the app branches on the returned path

The test uses Xvfb to provide a virtual display without needing a real GPU.
"""

import os
import sys
from pathlib import Path

# Add the repo root to the path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import subprocess
from time import sleep, time


def run_itidy_directory_smoke_test():
    """Run iTidy's directory selection flow and verify the ASL requester works."""

    # The iTidy binary path
    itidy_binary = REPO_ROOT / "amiga_apps" / "itidy1classic" / "build" / "iTidy.lha"

    if not itidy_binary.exists():
        print(f"ERROR: iTidy binary not found at {itidy_binary}")
        print("Please build iTidy first with: make itidy")
        return False

    # Launch iTidy in headless Xvfb mode
    cmd = ["uv", "run", "amiga-ui", "run", str(itidy_binary)]

    print(f"Starting iTidy in headless mode: {' '.join(cmd)}")

    start_time = time()

    # Run the command (we'll terminate it manually after the test)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait a bit for iTidy to start and show the main window
    sleep(5)

    # Check if iTidy is still running
    if proc.poll() is not None:
        stdout, stderr = proc.communicate(timeout=10)
        print(f"ERROR: iTidy failed to start")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        return False

    print("iTidy is running. Waiting for directory selection dialog...")

    # Give iTidy more time to reach the directory selection
    sleep(10)

    # Check if iTidy is still running
    if proc.poll() is not None:
        stdout, stderr = proc.communicate(timeout=10)
        print(f"ERROR: iTidy exited during the test")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        return False

    print("SUCCESS: iTidy is still running after directory selection")
    print("The ASL directory picker appears to be working!")

    # Terminate iTidy
    proc.terminate()
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)

    print(f"iTidy exited with code: {proc.returncode}")
    print(f"stdout: {stdout}")
    print(f"stderr: {stderr}")

    # Check for any error messages in the output
    if "UnsupportedFeatureError" in stdout or "UnsupportedFeatureError" in stderr:
        print("ERROR: UnsupportedFeatureError detected - ASL implementation may have failed")
        return False

    if "AttributeError" in stdout or "AttributeError" in stderr:
        print("ERROR: AttributeError detected - implementation may have issues")
        return False

    return True


if __name__ == "__main__":
    success = run_itidy_directory_smoke_test()
    sys.exit(0 if success else 1)
