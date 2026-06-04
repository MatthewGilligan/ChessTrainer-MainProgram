"""
start_all.py  —  Chess Trainer launcher
CS 361 Final Project

Starts all four microservice servers as separate subprocesses,
then launches the main program. Works on Windows, Mac, and Linux.

Usage (from inside chess-trainer-main folder):
    python3 start_all.py

Expected folder layout:
    FinalSprint/
    ├── ms-a-move-validation/
    ├── ms-b-chess-engine/
    ├── ms-c-turn-timer/
    ├── ms-d-chat-log/
    └── chess-trainer-main/      <- run from here
"""

import subprocess
import sys
import time
import os
import signal

# chess-trainer-main/ lives inside a parent folder that also holds the services
HERE   = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)

SERVICES = [
    {
        "name":   "Microservice A — Move Validation",
        "folder": os.path.join(PARENT, "ms-a-move-validation"),
        "port":   50051,
    },
    {
        "name":   "Microservice B — Chess Engine",
        "folder": os.path.join(PARENT, "ms-b-chess-engine"),
        "port":   50052,
    },
    {
        "name":   "Microservice C — Turn Timer",
        "folder": os.path.join(PARENT, "ms-c-turn-timer"),
        "port":   50053,
    },
    {
        "name":   "Microservice D — Chat / Game Log",
        "folder": os.path.join(PARENT, "ms-d-chat-log"),
        "port":   50054,
    },
]

processes = []

def shutdown(sig=None, frame=None):
    print("\n\nShutting down all microservices...")
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass
    for p in processes:
        try:
            p.wait(timeout=3)
        except Exception:
            pass
    print("All processes stopped.")
    sys.exit(0)

# Graceful shutdown on Ctrl+C
signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    print("=" * 58)
    print("   Chess Trainer — Starting all microservices")
    print("=" * 58)

    for svc in SERVICES:
        folder = svc["folder"]
        script = os.path.join(folder, "server.py")

        # Verify the folder and script actually exist before trying to launch
        if not os.path.isdir(folder):
            print(f"\n  ERROR: Folder not found: {folder}")
            print(f"  Make sure '{os.path.basename(folder)}' is a sibling of chess-trainer-main.")
            shutdown()

        if not os.path.isfile(script):
            print(f"\n  ERROR: server.py not found in {folder}")
            shutdown()

        env = os.environ.copy()
        # Put the service folder on PYTHONPATH so its _pb2 stubs are importable
        env["PYTHONPATH"] = folder + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            [sys.executable, script],   # full path to script — works on Windows
            cwd=folder,                 # run from the service's own folder
            env=env,
        )
        processes.append(proc)
        print(f"\n  ✓  {svc['name']}")
        print(f"       port : {svc['port']}")
        print(f"       PID  : {proc.pid}")
        print(f"       path : {folder}")

    print(f"\n  Waiting 3s for services to bind to ports...")
    time.sleep(3)

    # Quick check: did any crash on startup?
    any_crashed = False
    for i, proc in enumerate(processes):
        if proc.poll() is not None:
            print(f"\n  ERROR: {SERVICES[i]['name']} crashed on startup!")
            print(f"  Try running its server.py manually to see the error:")
            print(f"    cd \"{SERVICES[i]['folder']}\"")
            print(f"    python3 server.py")
            any_crashed = True

    if any_crashed:
        shutdown()

    print("\n" + "=" * 58)
    print("   All services running — launching main program")
    print("=" * 58 + "\n")

    try:
        subprocess.run(
            [sys.executable, os.path.join(HERE, "main.py")],
            cwd=HERE,
        )
    except KeyboardInterrupt:
        pass

    shutdown()
