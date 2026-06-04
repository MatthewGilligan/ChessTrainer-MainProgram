"""
start_all.py  —  Chess Trainer launcher
CS 361 Final Project

Starts all four microservice servers as separate subprocesses,
then launches the main program. Each process runs independently
and communicates only via gRPC over its assigned port.

  Process 1: Microservice A — Move Validation  (port 50051)
  Process 2: Microservice B — Chess Engine     (port 50052)
  Process 3: Microservice C — Turn Timer       (port 50053)
  Process 4: Microservice D — Chat / Game Log  (port 50054)
  Process 5: Main Program   — Orchestrator

Usage:
    python3 start_all.py
"""

import subprocess
import sys
import time
import os
import signal

BASE = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name":   "Microservice A — Move Validation",
        "script": os.path.join(BASE, "services", "validation", "server.py"),
        "port":   50051,
    },
    {
        "name":   "Microservice B — Chess Engine",
        "script": os.path.join(BASE, "services", "engine", "server.py"),
        "port":   50052,
    },
    {
        "name":   "Microservice C — Turn Timer",
        "script": os.path.join(BASE, "services", "timer", "server.py"),
        "port":   50053,
    },
    {
        "name":   "Microservice D — Chat / Game Log",
        "script": os.path.join(BASE, "services", "chat", "server.py"),
        "port":   50054,
    },
]

processes = []

def shutdown(sig=None, frame=None):
    print("\n\nShutting down all microservices...")
    for p in processes:
        p.terminate()
    for p in processes:
        p.wait()
    print("All processes stopped.")
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    print("=" * 58)
    print("   Chess Trainer — Starting all microservices")
    print("=" * 58)

    # Launch each microservice as a separate subprocess
    for svc in SERVICES:
        env = os.environ.copy()
        # Each service dir must be on PYTHONPATH so its stubs are importable
        svc_dir = os.path.dirname(svc["script"])
        env["PYTHONPATH"] = svc_dir + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            [sys.executable, svc["script"]],
            env=env,
            cwd=svc_dir,
        )
        processes.append(proc)
        print(f"  ✓ Started {svc['name']}  (port {svc['port']}, PID {proc.pid})")

    print(f"\n  {len(SERVICES)} microservices running. Waiting for them to be ready...")
    time.sleep(2)

    print("\n" + "=" * 58)
    print("   Starting Main Program")
    print("=" * 58 + "\n")

    # Launch main program — runs in the foreground so you can interact with it
    main_env = os.environ.copy()
    main_env["PYTHONPATH"] = (
        os.path.join(BASE, "services", "validation") + os.pathsep +
        os.path.join(BASE, "services", "engine")     + os.pathsep +
        os.path.join(BASE, "services", "timer")      + os.pathsep +
        os.path.join(BASE, "services", "chat")       + os.pathsep +
        main_env.get("PYTHONPATH", "")
    )

    main_proc = subprocess.run(
        [sys.executable, os.path.join(BASE, "main_app", "main.py")],
        env=main_env,
        cwd=BASE,
    )

    shutdown()
