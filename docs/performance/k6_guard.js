/**
 * AgentGuard Phase 18 — k6 Load Test Script
 *
 * Tests POST /guard/check at 100, 500, 1000, 5000 virtual users.
 * Configured via K6_VUS and K6_SCENARIO env vars.
 *
 * Usage:
 *   k6 run --env K6_VUS=100  --env K6_SCENARIO=single_org  --out json=results_100_single.json  k6_guard.js
 *   k6 run --env K6_VUS=500  --env K6_SCENARIO=single_org  --out json=results_500_single.json  k6_guard.js
 *   k6 run --env K6_VUS=1000 --env K6_SCENARIO=single_org  --out json=results_1000_single.json k6_guard.js
 *   k6 run --env K6_VUS=1000 --env K6_SCENARIO=multi_org   --out json=results_1000_multi.json  k6_guard.js
 *   k6 run --env K6_VUS=5000 --env K6_SCENARIO=single_org  --out json=results_5000_single.json k6_guard.js
 *   k6 run --env K6_VUS=5000 --env K6_SCENARIO=multi_org   --out json=results_5000_multi.json  k6_guard.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// --- Configuration ----------------------------------------------------------
const BASE_URL = __ENV.K6_BASE_URL || 'http://127.0.0.1:8000';
const VUS      = parseInt(__ENV.K6_VUS || '100', 10);
const SCENARIO = __ENV.K6_SCENARIO || 'single_org';  // 'single_org' | 'multi_org'

// Pre-seeded API keys — one per org. The setup phase seeds these.
// For single_org all VUs use API_KEY_ORG_A.
// For multi_org, VUs alternate across the four keys.
const API_KEYS = JSON.parse(__ENV.K6_API_KEYS || '[]');

// Metrics
const errorRate   = new Rate('error_rate');
const latency     = new Trend('request_latency_ms', true);

const ITERATIONS = __ENV.K6_ITERATIONS ? parseInt(__ENV.K6_ITERATIONS, 10) : null;

// --- k6 options ------------------------------------------------------------
export const options = ITERATIONS ? {
  vus: VUS,
  iterations: ITERATIONS,
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed: ['rate<0.05'],
  },
} : {
  vus: VUS,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed: ['rate<0.05'],
  },
};

// --- Main test function -----------------------------------------------------
export default function () {
  // Pick API key & agent_id: single_org always uses key[0], multi_org round-robins
  const keyIndex = (SCENARIO === 'multi_org' && API_KEYS.length > 1)
    ? (__VU % API_KEYS.length)
    : 0;
  const currentKeyObj = API_KEYS[keyIndex] || {};
  const apiKey = currentKeyObj.api_key || currentKeyObj || 'MISSING_KEY';
  const agentId = currentKeyObj.agent_id || '00000000-0000-0000-0000-000000000000';

  const payload = JSON.stringify({
    agent_id:         agentId,
    tool_name:        'read_customer',
    action:           'read',
    parameters:       { customer_id: `CUST-${__VU}-${__ITER}` },
    estimated_tokens: 100,
    estimated_cost:   0.001,
  });

  const params = {
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    timeout: '10s',
  };

  const res = http.post(`${BASE_URL}/api/v1/guard/check`, payload, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'decision present': (r) => {
      try { return JSON.parse(r.body).decision !== undefined; } catch { return false; }
    },
  });

  errorRate.add(!ok);
  latency.add(res.timings.duration);

  sleep(0.01);  // 10ms think time — keep connection realistic
}

// --- Setup: seed test organizations and API keys ----------------------------
export function setup() {
  // This is printed to logs and used externally by the runner script.
  // Actual seeding is done by the Python seed script before k6 runs.
  console.log(`Scenario: ${SCENARIO}, VUs: ${VUS}`);
}
