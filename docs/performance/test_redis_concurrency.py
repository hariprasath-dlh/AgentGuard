"""
AgentGuard Phase 18 — Redis Rate Limiting & Budget Enforcement Under Concurrency.

Tests:
1. Rate-Limit Enforcement:
   Sends 5,000 concurrent requests to RateLimitTestAgent (cap = 200 req/min).
   Verifies Redis sliding-window/counter accurately admits exactly ~200 and rejects the rest.
2. Budget Enforcement:
   Sends concurrent requests with cost to BudgetCappedTestAgent (cap = $0.50/session).
   Verifies Redis/DB budget enforcement halts spend at cap under concurrency.
"""
import os
import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

PERF_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(PERF_DIR, "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
BASE_URL = "http://127.0.0.1:8000"

def test_redis_rate_limiter_direct(total_requests=5000, concurrency=50):
    """Directly benchmarks the Phase 6 RedisRateLimitChecker ZSET sliding-window under 5,000 concurrent calls."""
    from app.services.rate_limiter import RedisRateLimitChecker
    from app.core.redis import get_redis_client
    from unittest.mock import MagicMock
    import uuid

    print(f"\n[REDIS DIRECT RATE-LIMIT] Benchmarking RedisRateLimitChecker directly with {total_requests} calls ({concurrency} workers)...")
    redis_client = get_redis_client()
    limiter = RedisRateLimitChecker(redis_client, default_requests_per_minute=200)
    
    test_agent_id = uuid.uuid4()
    mock_agent = MagicMock()
    mock_agent.id = test_agent_id
    mock_agent.name = "DirectPerfAgent"

    mock_tool = MagicMock()
    mock_tool.name = "read_customer"

    from app.schemas.policy import DecisionInput
    input_data = DecisionInput(
        agent_id=str(test_agent_id),
        tool_name="read_customer",
        action="read",
        parameters={},
        estimated_tokens=0,
        estimated_cost=0.0,
    )

    mock_db = MagicMock()
    # Mock budget row returning max_requests_per_minute = 200
    mock_budget = MagicMock()
    mock_budget.max_requests_per_minute = 200
    mock_db.query.return_value.filter.return_value.first.return_value = mock_budget

    # Clear state
    limiter.reset(test_agent_id)

    allowed_count = 0
    denied_count = 0
    t0 = time.time()

    def check_call(i):
        # We record to ZSET if allowed (mimicking post-check recording or evaluation)
        allowed, reason = limiter(mock_db, input_data, mock_agent, mock_tool)
        if allowed:
            # record request timestamp
            now = time.time()
            req_key = limiter._get_request_key(test_agent_id)
            redis_client.zadd(req_key, {f"{now}:{i}": now})
        return allowed

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(check_call, i) for i in range(total_requests)]
        for f in as_completed(futures):
            if f.result():
                allowed_count += 1
            else:
                denied_count += 1

    elapsed = time.time() - t0
    rps = total_requests / elapsed
    print(f"  Total Calls: {total_requests}")
    print(f"  Allowed: {allowed_count} (Cap: 200)")
    print(f"  Denied (Rate Limited): {denied_count}")
    print(f"  Elapsed: {elapsed:.3f}s -> Throughput: {rps:.1f} ops/sec")

    assert allowed_count <= 210, f"Expected <= 210 allowed, got {allowed_count}"
    assert denied_count >= (total_requests - 210)
    print("  [SUCCESS] Redis sliding-window rate limiter enforced token window under direct concurrency.")

    return {
        "test": "redis_rate_limiter_direct",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "allowed": allowed_count,
        "denied": denied_count,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_ops_per_sec": round(rps, 1),
        "status": "PASSED",
    }

def test_redis_budget_direct(total_requests=1000, concurrency=25):
    """Directly benchmarks the Phase 6 RedisBudgetChecker under concurrent increments."""
    from app.services.budget_guard import RedisBudgetChecker
    from app.core.redis import get_redis_client
    from unittest.mock import MagicMock
    from app.schemas.policy import DecisionInput
    import uuid

    print(f"\n[REDIS DIRECT BUDGET] Benchmarking RedisBudgetChecker directly with {total_requests} calls ({concurrency} workers)...")
    redis_client = get_redis_client()
    checker = RedisBudgetChecker(redis_client)

    test_agent_id = uuid.uuid4()
    mock_agent = MagicMock()
    mock_agent.id = test_agent_id
    mock_agent.name = "DirectBudgetAgent"

    mock_tool = MagicMock()
    mock_tool.name = "read_customer"

    cost_per_req = 0.05  # 100 calls allowed against $5.00 limit
    input_data = DecisionInput(
        agent_id=str(test_agent_id),
        tool_name="read_customer",
        action="read",
        parameters={},
        estimated_tokens=100,
        estimated_cost=cost_per_req,
    )

    from decimal import Decimal
    mock_db = MagicMock()
    mock_budget = MagicMock()
    mock_budget.max_budget_per_session = Decimal("5.00")
    mock_budget.max_budget_per_day = Decimal("50.00")
    mock_budget.current_spend = Decimal("0.00")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_budget

    checker.reset(test_agent_id)

    allowed_count = 0
    denied_count = 0
    t0 = time.time()

    def check_call(i):
        allowed, reason = checker(mock_db, input_data, mock_agent, mock_tool)
        return allowed

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(check_call, i) for i in range(total_requests)]
        for f in as_completed(futures):
            if f.result():
                allowed_count += 1
            else:
                denied_count += 1

    elapsed = time.time() - t0
    rps = total_requests / elapsed
    print(f"  Total Calls: {total_requests}")
    print(f"  Allowed: {allowed_count} (Cap: $5.00 / 100 calls)")
    print(f"  Denied (Budget Exceeded): {denied_count}")
    print(f"  Elapsed: {elapsed:.3f}s -> Throughput: {rps:.1f} ops/sec")

    assert 100 <= allowed_count <= 125, f"Expected between 100 and 125 allowed, got {allowed_count}"
    assert denied_count >= (total_requests - 125)
    print("  [SUCCESS] Redis budget checker enforced spend cap under direct concurrency.")

    return {
        "test": "redis_budget_direct",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "allowed": allowed_count,
        "denied": denied_count,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_ops_per_sec": round(rps, 1),
        "status": "PASSED",
    }

def test_rate_limit_http_concurrency(special_keys, total_requests=300, concurrency=10):
    api_key = special_keys["rate_limit_agent_key"]
    agent_id = special_keys["rate_limit_agent_id"]
    print(f"\n[RATE-LIMIT HTTP TEST] Firing {total_requests} requests ({concurrency} workers) to /guard/check against RateLimitTestAgent (cap=200/min)...")

    url = f"{BASE_URL}/api/v1/guard/check"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "agent_id": agent_id,
        "tool_name": "read_customer",
        "action": "read",
        "parameters": {"customer_id": "CUST-RL-TEST"},
        "estimated_tokens": 100,
        "estimated_cost": 0.001,
    }

    allowed_count = 0
    denied_count = 0
    rate_limited_count = 0
    error_count = 0
    start_time = time.time()

    def send_one(i):
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    decision = data.get("decision", "")
                    reason = data.get("reason", "")
                    return ("OK", decision, reason)
                elif resp.status_code == 429:
                    return ("429", "DENY", "Rate limit exceeded")
                else:
                    return ("ERR", str(resp.status_code), resp.text)
        except Exception as e:
            return ("EXC", "ERROR", str(e))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_one, i) for i in range(total_requests)]
        for f in as_completed(futures):
            status, decision, reason = f.result()
            if status == "OK" and decision == "ALLOW":
                allowed_count += 1
            elif status == "429" or "rate limit" in reason.lower() or decision == "DENY":
                denied_count += 1
                if "rate limit" in reason.lower() or status == "429":
                    rate_limited_count += 1
            else:
                error_count += 1

    elapsed = time.time() - start_time
    print(f"  Total Requests: {total_requests}")
    print(f"  Allowed: {allowed_count}")
    print(f"  Denied / Rate-Limited: {denied_count} (Rate-limit reasons: {rate_limited_count})")
    print(f"  Errors / Timeouts: {error_count}")
    print(f"  Elapsed Time: {elapsed:.2f}s ({total_requests / elapsed:.1f} req/s)")

    assert allowed_count <= 210, f"Rate limit breach: allowed {allowed_count} requests, expected ~200!"
    assert denied_count >= (total_requests - 210), "Rate limiter failed to block excess traffic!"
    print("  [SUCCESS] Redis rate limiting held strictly under HTTP concurrent load.")

    return {
        "test": "rate_limit_http_concurrency",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "allowed": allowed_count,
        "denied_rate_limited": denied_count,
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 2),
        "throughput_rps": round(total_requests / elapsed, 1),
        "status": "PASSED",
    }

def test_budget_concurrency(special_keys, total_requests=50, concurrency=5):
    api_key = special_keys["budget_agent_key"]
    agent_id = special_keys["budget_agent_id"]
    print(f"\n[BUDGET HTTP TEST] Firing {total_requests} requests ({concurrency} workers) to /guard/check against BudgetCappedTestAgent (cap=$0.50, $0.05/req)...")

    url = f"{BASE_URL}/api/v1/guard/check"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "agent_id": agent_id,
        "tool_name": "read_customer",
        "action": "read",
        "parameters": {"customer_id": "CUST-BUDGET-TEST"},
        "estimated_tokens": 100,
        "estimated_cost": 0.05,  # 10 calls = $0.50 cap
    }

    allowed_count = 0
    denied_count = 0
    budget_denied_count = 0
    start_time = time.time()

    def send_one(i):
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    decision = data.get("decision", "")
                    reason = data.get("reason", "")
                    return ("OK", decision, reason)
                else:
                    return ("ERR", str(resp.status_code), resp.text)
        except Exception as e:
            return ("EXC", "ERROR", str(e))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_one, i) for i in range(total_requests)]
        for f in as_completed(futures):
            status, decision, reason = f.result()
            if status == "OK" and decision == "ALLOW":
                allowed_count += 1
            else:
                denied_count += 1
                if "budget" in reason.lower():
                    budget_denied_count += 1

    elapsed = time.time() - start_time
    print(f"  Total Requests: {total_requests}")
    print(f"  Allowed: {allowed_count}")
    print(f"  Denied / Budget Exceeded: {denied_count} (Budget reasons: {budget_denied_count})")
    print(f"  Elapsed Time: {elapsed:.2f}s")

    assert allowed_count <= 12, f"Budget cap breach: allowed {allowed_count} requests ($0.05 each) against $0.50 cap!"
    assert budget_denied_count >= (total_requests - 15), "Budget guard failed to enforce cap under concurrency!"
    print("  [SUCCESS] Redis/DB budget enforcement held strictly under concurrent HTTP load.")

    return {
        "test": "budget_http_concurrency",
        "total_requests": total_requests,
        "concurrency": concurrency,
        "cost_per_request": 0.05,
        "cap": 0.50,
        "allowed": allowed_count,
        "denied_budget": denied_count,
        "elapsed_seconds": round(elapsed, 2),
        "status": "PASSED",
    }

def is_server_running(url=f"{BASE_URL}/health"):
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False

def start_backend_server():
    if is_server_running():
        print("[INFO] Backend server already running on port 8000.")
        return None
    
    import subprocess
    print("[INFO] Starting backend uvicorn server on 127.0.0.1:8000...")
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://agentguard:agentguard_password@localhost:5432/agentguard")
    env["REDIS_URL"] = env.get("REDIS_URL", "redis://localhost:6379/0")
    BACKEND_DIR = os.path.abspath(os.path.join(PERF_DIR, "..", "..", "backend"))
    env["PYTHONPATH"] = BACKEND_DIR

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(30):
        time.sleep(1)
        if is_server_running():
            print("[INFO] Backend server is UP and healthy.")
            return proc
    raise RuntimeError("Backend server failed to start within 30 seconds.")

def main():
    special_keys_path = os.path.join(PERF_DIR, "special_keys.json")
    if not os.path.exists(special_keys_path):
        print("[ERROR] special_keys.json not found. Run seed_perf.py first.")
        sys.exit(1)
    
    with open(special_keys_path, "r") as f:
        special_keys = json.load(f)

    results = []

    # 1. Direct Redis rate limiter concurrency test
    direct_rl = test_redis_rate_limiter_direct(total_requests=5000, concurrency=50)
    results.append(direct_rl)

    # 2. Direct Redis budget concurrency test
    direct_b = test_redis_budget_direct(total_requests=1000, concurrency=25)
    results.append(direct_b)

    # 3. HTTP Concurrency tests against live server
    server_proc = start_backend_server()
    try:
        rl_res = test_rate_limit_http_concurrency(special_keys, total_requests=300, concurrency=10)
        results.append(rl_res)

        b_res = test_budget_concurrency(special_keys, total_requests=50, concurrency=5)
        results.append(b_res)

        out_file = os.path.join(PERF_DIR, "redis_concurrency_results.json")
        with open(out_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[INFO] Saved results to {out_file}")
    finally:
        if server_proc:
            print("[INFO] Terminating backend server...")
            server_proc.terminate()
            server_proc.wait()

if __name__ == "__main__":
    main()
