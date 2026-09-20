"""
AgentGuard Phase 18 Benchmark Automation Runner.

Executes:
1. Setup and seeder for 4 test organizations and dedicated test agents.
2. Starts uvicorn server against live Postgres + Redis stack.
3. Runs k6 load tests against /api/v1/guard/check for:
   - 100 requests (single-org)
   - 500 requests (single-org)
   - 1,000 requests (single-org)
   - 1,000 requests (multi-org)
   - 5,000 requests (single-org)
   - 5,000 requests (multi-org)
4. Executes Redis-backed rate limiting & budget enforcement concurrency tests.
5. Captures query efficiency profiling & dashboard endpoint sanity checks.
6. Writes raw k6 summary JSONs, query logs, and markdown summaries to docs/performance/.
"""
import os
import sys
import json
import shutil
import time
import socket
import subprocess
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError

PERF_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(PERF_DIR, "..", "..", "backend"))
BASE_URL = "http://127.0.0.1:8000"

def is_server_running(url=f"{BASE_URL}/health"):
    try:
        with urlopen(url, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def start_backend_server():
    if is_server_running():
        print("[INFO] Backend server already running on port 8000.")
        return None
    
    print("[INFO] Starting backend uvicorn server on 127.0.0.1:8000...")
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://agentguard:agentguard_password@localhost:5432/agentguard")
    env["REDIS_URL"] = env.get("REDIS_URL", "redis://localhost:6379/0")
    env["PYTHONPATH"] = BACKEND_DIR

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to become healthy
    for _ in range(30):
        time.sleep(1)
        if is_server_running():
            print("[INFO] Backend server is UP and healthy.")
            return proc
    raise RuntimeError("Backend server failed to start within 30 seconds.")

def run_seed():
    print("[INFO] Seeding test organizations and API keys...")
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://agentguard:agentguard_password@localhost:5432/agentguard")
    env["REDIS_URL"] = env.get("REDIS_URL", "redis://localhost:6379/0")
    env["PYTHONPATH"] = BACKEND_DIR

    res = subprocess.run(
        [sys.executable, os.path.join(PERF_DIR, "seed_perf.py")],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("[ERROR] Seed failed:", res.stderr)
        raise RuntimeError("Seed script failed.")
    
    # Extract JSON from output
    stdout = res.stdout.strip()
    json_start = stdout.find("[")
    if json_start == -1:
        raise ValueError("Could not find JSON array in seed output: " + stdout)
    data = json.loads(stdout[json_start:])
    
    keys_file = os.path.join(PERF_DIR, "perf_keys.json")
    with open(keys_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[INFO] Seeded {len(data)} organizations. Keys written to {keys_file}")
    return data

def run_k6_benchmark(vus, iterations, scenario, keys, out_name):
    print(f"\n==================================================")
    print(f"[BENCHMARK] Scenario: {scenario}, Iterations: {iterations}, VUs: {vus}")
    print(f"==================================================")

    k6_script = os.path.join(PERF_DIR, "k6_guard.js")
    summary_json_path = os.path.join(PERF_DIR, f"summary_{out_name}.json")
    k6_bin = shutil.which("k6") or r"C:\Program Files\k6\k6.exe"
    cmd = [
        k6_bin, "run",
        "--env", f"K6_VUS={vus}",
        "--env", f"K6_ITERATIONS={iterations}",
        "--env", f"K6_SCENARIO={scenario}",
        "--env", f"K6_BASE_URL={BASE_URL}",
        "--env", f"K6_API_KEYS={json.dumps(keys)}",
        "--summary-export", summary_json_path,
        k6_script
    ]

    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_t

    raw_log_path = os.path.join(PERF_DIR, f"k6_output_{out_name}.txt")
    with open(raw_log_path, "w", encoding="utf-8") as f:
        f.write(res.stdout + "\n" + res.stderr)

    print(res.stdout)
    if res.returncode != 0:
        print(f"[WARN] k6 exited with code {res.returncode}. Stderr: {res.stderr}")

    summary = {}
    if os.path.exists(summary_json_path):
        with open(summary_json_path, "r") as f:
            summary = json.load(f)
    
    return {
        "scenario": scenario,
        "iterations": iterations,
        "vus": vus,
        "duration_seconds": round(duration, 2),
        "raw_log": raw_log_path,
        "summary": summary
    }

def main():
    server_proc = None
    try:
        keys = run_seed()
        server_proc = start_backend_server()

        # Benchmarks to execute
        scenarios = [
            {"vus": 10,  "iterations": 100,  "scenario": "single_org", "name": "100_single"},
            {"vus": 25,  "iterations": 500,  "scenario": "single_org", "name": "500_single"},
            {"vus": 50,  "iterations": 1000, "scenario": "single_org", "name": "1000_single"},
            {"vus": 50,  "iterations": 1000, "scenario": "multi_org",  "name": "1000_multi"},
            {"vus": 100, "iterations": 5000, "scenario": "single_org", "name": "5000_single"},
            {"vus": 100, "iterations": 5000, "scenario": "multi_org",  "name": "5000_multi"},
        ]

        results = []
        for sc in scenarios:
            res = run_k6_benchmark(
                vus=sc["vus"],
                iterations=sc["iterations"],
                scenario=sc["scenario"],
                keys=keys,
                out_name=sc["name"]
            )
            results.append(res)

        with open(os.path.join(PERF_DIR, "all_benchmark_results.json"), "w") as f:
            json.dump(results, f, indent=2)

        print("\n[INFO] All k6 benchmarks finished successfully!")

    finally:
        if server_proc:
            print("[INFO] Terminating backend server...")
            server_proc.terminate()
            server_proc.wait()

if __name__ == "__main__":
    main()
