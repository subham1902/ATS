# ATS MARKET-READY OPERATOR RUNBOOK
**Session Target**: Live A2 Paper Trading Session  
**Operating Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`  
**Operating Mode**: `AGGRESSIVE` (Requested Execution Envelope)  

---

### Step 1: Pre-Market Stage 1 Acceptance (09:00–09:10 IST)
Before launching the stack, verify live Upstox authentication, download Monday's official BOD contract master, and ensure zero prior session collisions:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_pre_market_stack.ps1
```
- **Required Verdict**: `READY_FOR_A2_PAPER_SESSION` (Exit code `0`).
- **If Blocked**: Do **not** launch. Review the reported blocker in the output JSON.

---

### Step 2: Canonical Paper Stack Launch (09:10–09:14 IST)
Launch the backend FastAPI server and Next.js Control Center frontend:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE
```
- **Backend API**: `http://127.0.0.1:8000/v1/runtime/status`
- **Control Center UI**: `http://127.0.0.1:3000`
- **Verify Invariants**: Target = `PAPER`, Live Money = `DISABLED`, Real Orders = `0`.

---

### Step 3: Market Open Stage 2 Live Data Gate (09:15 IST)
At market open, verify live quote streams and <= 2,000ms freshness across underlying indices and ATM options:
- Inspect `http://127.0.0.1:8000/v1/pipeline/counters`.
- Ensure `MARKET_OPEN_DATA_READY` is established.
- `can_enter_new_risk = true` unlocks autonomously under strict A04 governance.

---

### Step 4: Autonomous Forward Observation (09:15–15:15 IST)
- Monitor real-time telemetry on the Control Center UI ([http://127.0.0.1:3000](http://127.0.0.1:3000)).
- C0 executes autonomously as champion (threshold `0.55`).
- Alpha V4, M1–M9, and R10-X run as shadow observers without execution authority.
- **Operating Discipline**: Zero manual trades, zero threshold adjustments, zero martingale sizing.

---

### Step 5: Entry Cutoff (15:15 IST)
- Session FSM transitions to `EXIT_ONLY`.
- All new risk creation is deterministically disabled.
- Existing open paper positions remain actively managed by the position monitor.

---

### Step 6: Mandatory Flatten Window (15:25 IST)
- Session FSM transitions to `FLATTEN_WINDOW`.
- All open paper positions are systematically closed/reduced to zero exposure.

---

### Step 7: Session Closure & Finalization (15:30 IST)
1. **Trigger graceful session closure**:
   ```powershell
   python -c "import urllib.request, json; req = urllib.request.Request('http://127.0.0.1:8000/v1/runtime/command', data=json.dumps({'command': 'STOP_A2_PAPER_SESSION'}).encode('utf-8'), headers={'Content-Type': 'application/json'}); print(urllib.request.urlopen(req).read().decode('utf-8'))"
   ```
2. **Stop background services**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/stop_ats_a2_live_paper.ps1
   ```
3. **Verify reconciliation**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/reconcile_a2_session_state.ps1 -Check
   ```
   - **Required State**: `CLEAN_NO_PRIOR_SESSION` (Exit code `0`).

---

### Step 8: Post-Session Reporting
- Review the generated evidence in `data/runtime/sessions/<YYYY-MM-DD>/<session_id>/events.jsonl` and `manifest.json`.
- Compile `FINAL_REPORT_A2_FORWARD_SESSION_01.md`.
