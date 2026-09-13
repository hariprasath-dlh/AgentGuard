# AgentGuard Phase 11: Framework-Agnostic Governance Demonstration

This directory contains the concrete proof that **AgentGuard is truly framework-agnostic**.

AgentGuard does not depend on any specific agent framework, execution loop, or orchestration graph. Three entirely different agent architectures—written in different programming paradigms—govern identical tool calls using the same `agentguard-sdk` client against the same `/guard/check` gateway.

---

## 1. Demonstrated Agent Architectures

| Demo | Agent Architecture | Paradigm | Implementation File | Key Characteristic |
| :--- | :--- | :--- | :--- | :--- |
| **Demo 1** | **Custom OOP Agent** | Object-Oriented Python | [`demo/agents/custom_agent.py`](file:///d:/agentguard/demo/agents/custom_agent.py) | Zero external dependencies; standard class-based intent handler |
| **Demo 2** | **LangChain-Style Tool Agent** | Tool / Executor Wrapper | [`demo/agents/langchain_agent.py`](file:///d:/agentguard/demo/agents/langchain_agent.py) | Encapsulates tools with a governance pre-hook before tool execution |
| **Demo 3** | **Simulated Agent (FSM)** | Event-Driven State Machine | [`demo/agents/simulated_agent.py`](file:///d:/agentguard/demo/agents/simulated_agent.py) | Explicit state machine transitions (`PROPOSING` → `GOVERNANCE_EVALUATION` → `EXECUTING` / `BLOCKED` / `PAUSED_HITL`) |

All three demos interact with shared mock tool implementations in [`demo/tools/mock_tools.py`](file:///d:/agentguard/demo/tools/mock_tools.py).

---

## 2. Shared Governance Contract & Tool Scenarios

Each agent evaluates the exact same three tool calls in sequence:

1. **`read_customer` (`customer_id="CUST-001"`)**
   - **Risk Level:** `LOW`
   - **Expected Decision:** `ALLOW`
   - **Outcome:** Execution allowed; agent executes the client tool and receives profile data.
2. **`delete_database` (`database="prod_users"`)**
   - **Risk Level:** `CRITICAL`
   - **Expected Decision:** `DENY`
   - **Outcome:** Execution permanently blocked by policy; `AgentGuardDenied` raised with reason.
3. **`process_refund` (`amount=1500.0`, `reason="damaged shipment"`)**
   - **Risk Level:** `HIGH`
   - **Expected Decision:** `PENDING`
   - **Outcome:** Execution paused awaiting human-in-the-loop approval; `AgentGuardPending` raised with `request_id`.

---

## 3. Cross-Demo Consistency Proof

Below is the verified cross-agent comparison table from the live run. All three agent architectures produced **identical decisions** and **identical reason strings** from the backend for identical inputs; only the server-generated `request_id` UUIDs differed:

| Tool & Input | Demo 1 (Custom OOP) | Demo 2 (LangChain) | Demo 3 (Simulated FSM) | Backend Reason | Consistency |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **`read_customer`**<br>`{"customer_id": "CUST-001"}` | **ALLOW**<br>(executed=True) | **ALLOW**<br>(executed=True) | **ALLOW**<br>(executed=True) | `All policy checks passed.` | **IDENTICAL** |
| **`delete_database`**<br>`{"database": "prod_users"}` | **DENY**<br>(executed=False) | **DENY**<br>(executed=False) | **DENY**<br>(executed=False) | `Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.` | **IDENTICAL** |
| **`process_refund`**<br>`{"amount": 1500.0, ...}` | **PENDING**<br>(executed=False) | **PENDING**<br>(executed=False) | **PENDING**<br>(executed=False) | `Action on tool 'process_refund' requires human approval (HITL).` | **IDENTICAL** |

Every single invocation resulted in a unique, authentic server-generated UUID (9 distinct UUIDs across the 9 calls), proving each call reached the live policy engine and hash-chained audit vault.

---

## 4. How to Run the Demonstration

### Prerequisites
1. Ensure the PostgreSQL and Redis containers are active:
   ```bash
   docker ps
   ```
2. Ensure dependencies and `agentguard-sdk` are installed in your environment:
   ```bash
   pip install -e sdk/
   pip install -r backend/requirements.txt
   ```

### Execute the Unified Demo Runner
Run the idempotent orchestrator script:
```bash
python demo/run_all.py
```

The runner will:
- Idempotently provision the demo organization, agent, permissions, and API key reusing the Phase 4 seed pattern.
- Verify or start the live AgentGuard backend FastAPI service.
- Execute Demo 1, Demo 2, and Demo 3 sequentially.
- Perform automated cross-demo consistency assertions.
- Tee all execution logs directly to `demo/demo_output.log`.

---

## 5. Verbatim Live Execution Transcript

The transcript below is an exact capture from the live execution on the actual backend (`demo/demo_output.log`):

```text
================================================================================
AGENTGUARD: FRAMEWORK-AGNOSTIC RUNTIME GOVERNANCE DEMONSTRATION
Timestamp: 2026-09-05T13:20:47.504357+00:00
Python Executable: C:\Python314\python.exe
================================================================================

[Provisioning] Verifying demo organization and seeded tools (slug=agentguard-demo)...
INFO: Organization already exists: agentguard-demo (id=aa2578ee-a04d-4c10-bcbe-da4daa018601)
INFO: Demo admin already exists: admin@agentguard-demo.local
INFO: Tool already exists: read_customer (LOW)
INFO: Tool already exists: create_ticket (LOW)
INFO: Tool already exists: send_email (MEDIUM)
INFO: Tool already exists: process_refund (HIGH)
INFO: Tool already exists: delete_database (CRITICAL)
INFO: Seed complete  tools created: 0, already existed: 5
[Provisioning] Demo agent already exists: FrameworkDemoAgent (id=b2bb00ab-53a6-42b9-96bd-760f6d80ece3)
[Provisioning] Permissions verified (created: 0, existing: 5)
[Provisioning] Demo API key already exists with prefix: ag_live_demo...

[Server] Backend not responding at http://127.0.0.1:8000. Starting live FastAPI server...
INFO: HTTP Request: GET http://127.0.0.1:8000/health "HTTP/1.1 200 OK"
[Server] Live FastAPI backend successfully started at http://127.0.0.1:8000
============================================================
DEMO 1: Custom Python Agent (No Framework)
============================================================

[CustomAgent] Proposing action: read_customer with params={'customer_id': 'CUST-001'}
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[CustomAgent] -> ALLOWED by AgentGuard (request_id=21077670-d623-408a-9204-65b17389b00b)
[CustomAgent] -> Reason: All policy checks passed.
[CustomAgent] -> Tool output: {'status': 'success', 'customer_id': 'CUST-001', 'name': 'Jane Doe', 'email': 'jane.doe@example.com', 'tier': 'enterprise'}

[CustomAgent] Proposing action: delete_database with params={'database': 'prod_users'}
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[CustomAgent] -> BLOCKED by AgentGuard (request_id=e5739ca5-8ae7-44ee-a40b-92187ceff2b1)
[CustomAgent] -> Reason: Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.

[CustomAgent] Proposing action: process_refund with params={'customer_id': 'CUST-001', 'amount': 1500.0, 'reason': 'damaged shipment'}
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[CustomAgent] -> PAUSED for Human Approval (request_id=b43e6ffe-dfd3-4854-a4b2-fca265977622)
[CustomAgent] -> Reason: Action on tool 'process_refund' requires human approval (HITL).
============================================================
DEMO 2: LangChain-Style Tool Agent
============================================================

[LangChainAgent] Tool call requested: read_customer({'customer_id': 'CUST-001'})
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[LangChainAgent] -> AgentGuard: ALLOW (request_id=3ad0c62b-25b8-4d81-83d2-24232e1d9e95)
[LangChainAgent] -> Reason: All policy checks passed.
[LangChainAgent] -> Observation: {'status': 'success', 'customer_id': 'CUST-001', 'name': 'Jane Doe', 'email': 'jane.doe@example.com', 'tier': 'enterprise'}

[LangChainAgent] Tool call requested: delete_database({'database': 'prod_users'})
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[LangChainAgent] -> AgentGuard: DENIED (request_id=a8e9dbca-21e3-43ee-b17e-2b7d6330aee9)
[LangChainAgent] -> Reason: Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.

[LangChainAgent] Tool call requested: process_refund({'customer_id': 'CUST-001', 'amount': 1500.0, 'reason': 'damaged shipment'})
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[LangChainAgent] -> AgentGuard: PENDING HITL (request_id=aa4e7ca0-d0e4-4247-93c9-6c68c1d7f180)
[LangChainAgent] -> Reason: Action on tool 'process_refund' requires human approval (HITL).
============================================================
DEMO 3: Simulated Agent (Event-Driven State Machine)
============================================================

[SimulatedAgent] State=PROPOSING | Intent=read_customer params={'customer_id': 'CUST-001'}
[SimulatedAgent] State=GOVERNANCE_EVALUATION | Consulting AgentGuard...
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[SimulatedAgent] State=EXECUTING | Action ALLOWED (request_id=87bbbcb7-2a38-413a-838d-02d341cf08b5)
[SimulatedAgent] -> Reason: All policy checks passed.
[SimulatedAgent] -> Execution result: {'status': 'success', 'customer_id': 'CUST-001', 'name': 'Jane Doe', 'email': 'jane.doe@example.com', 'tier': 'enterprise'}

[SimulatedAgent] State=PROPOSING | Intent=delete_database params={'database': 'prod_users'}
[SimulatedAgent] State=GOVERNANCE_EVALUATION | Consulting AgentGuard...
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[SimulatedAgent] State=BLOCKED | Action DENIED (request_id=4723f81b-8ea0-4fa6-86db-dec44b311d82)
[SimulatedAgent] -> Reason: Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.

[SimulatedAgent] State=PROPOSING | Intent=process_refund params={'customer_id': 'CUST-001', 'amount': 1500.0, 'reason': 'damaged shipment'}
[SimulatedAgent] State=GOVERNANCE_EVALUATION | Consulting AgentGuard...
INFO: HTTP Request: POST http://127.0.0.1:8000/api/v1/guard/check "HTTP/1.1 200 OK"
[SimulatedAgent] State=PAUSED_HITL | Action PAUSED for HITL (request_id=a9e84c06-c056-4728-94e2-1db096880da3)
[SimulatedAgent] -> Reason: Action on tool 'process_refund' requires human approval (HITL).

================================================================================
CROSS-DEMO CONSISTENCY VERIFICATION
================================================================================
Verifying that Custom, LangChain, and FSM agents received identical decisions
and reasons for the exact same tool calls through the AgentGuard SDK contract.

Tool [1/3]: 'read_customer'
  Demo 1 (Custom OOP Agent): decision=ALLOW, executed=True, req_id=21077670-d623-408a-9204-65b17389b00b
  Demo 2 (LangChain Agent):  decision=ALLOW, executed=True, req_id=3ad0c62b-25b8-4d81-83d2-24232e1d9e95
  Demo 3 (Simulated FSM):    decision=ALLOW, executed=True, req_id=87bbbcb7-2a38-413a-838d-02d341cf08b5
  Unified Reason: 'All policy checks passed.'
  [PASS] Consistency check PASSED for tool 'read_customer'

Tool [2/3]: 'delete_database'
  Demo 1 (Custom OOP Agent): decision=DENY, executed=False, req_id=e5739ca5-8ae7-44ee-a40b-92187ceff2b1
  Demo 2 (LangChain Agent):  decision=DENY, executed=False, req_id=a8e9dbca-21e3-43ee-b17e-2b7d6330aee9
  Demo 3 (Simulated FSM):    decision=DENY, executed=False, req_id=4723f81b-8ea0-4fa6-86db-dec44b311d82
  Unified Reason: 'Tool 'delete_database' has risk level 'CRITICAL', which is denied by policy.'
  [PASS] Consistency check PASSED for tool 'delete_database'

Tool [3/3]: 'process_refund'
  Demo 1 (Custom OOP Agent): decision=PENDING, executed=False, req_id=b43e6ffe-dfd3-4854-a4b2-fca265977622
  Demo 2 (LangChain Agent):  decision=PENDING, executed=False, req_id=aa4e7ca0-d0e4-4247-93c9-6c68c1d7f180
  Demo 3 (Simulated FSM):    decision=PENDING, executed=False, req_id=a9e84c06-c056-4728-94e2-1db096880da3
  Unified Reason: 'Action on tool 'process_refund' requires human approval (HITL).'
  [PASS] Consistency check PASSED for tool 'process_refund'

[PASS] All 9 server-generated request UUIDs are distinct and authentic.
[PASS] CROSS-DEMO CONSISTENCY PROOF COMPLETE: Contract identical across all 3 agent architectures.

================================================================================
PHASE 11 DEMONSTRATION COMPLETED SUCCESSFULLY
Output recorded to: D:\agentguard\demo\demo_output.log
================================================================================
```
