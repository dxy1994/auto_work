# Three-Platform Order Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert itemmania, barotem and itembay order observations into one idempotent Adena order stream that the existing central coordinator can assign, while defining a guarded website-confirmation command.

**Architecture:** Worker-side adapters translate platform DOM snapshots into a platform-neutral `NormalizedOrder`; the Backend owns deduplication, validation and durable state. Platform-specific selectors remain account configuration, so changing Korean website markup does not alter the central domain model. Website confirmation is a separate command, defaults to `dry_run`, and can execute only for an order already in `game_delivered`.

**Tech Stack:** Python 3 `dataclasses`/`unittest`, Patchright Playwright, Java 17/Spring Boot, MyBatis-Plus, Jackson, JUnit 5/Mockito, WebSocket JSON.

---

### Task 1: Define and test the normalized Worker order contract

**Files:**
- Create: `worker/orders/__init__.py`
- Create: `worker/orders/model.py`
- Create: `worker/tests/test_normalized_order.py`

- [x] **Step 1: Write the failing contract test**

```python
from decimal import Decimal
from orders.model import NormalizedOrder

def test_wire_payload_uses_stable_protocol_fields():
    order = NormalizedOrder("itemmania", "M-100", 1, "adena", Decimal("2500000"), "구매자", "아덴01")
    assert order.to_wire() == {
        "platform": "itemmania", "source_order_no": "M-100", "region_external_key": "1",
        "asset_type": "adena", "asset_amount": "2500000", "buyer_character": "구매자",
        "platform_status": "paid", "raw_title": "아덴01",
    }
```

- [x] **Step 2: Run the test and verify it fails**

Run: `cd worker && python3 -m unittest tests.test_normalized_order -v`  
Expected: import failure for `orders.model`.

- [x] **Step 3: Implement the immutable value object**

Use a frozen dataclass, reject empty order number/buyer, reject non-Adena assets in this phase, and require `asset_amount > 0`. `to_wire()` must serialize `Decimal` as a plain decimal string and never include credentials, cookies or full page HTML.

- [x] **Step 4: Run the test**

Run: `cd worker && python3 -m unittest tests.test_normalized_order -v`  
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add worker/orders worker/tests/test_normalized_order.py
git commit -m "feat: define normalized marketplace order"
```

### Task 2: Add three explicit platform snapshot adapters

**Files:**
- Create: `worker/orders/adapters.py`
- Create: `worker/tests/fixtures/itemmania_order.json`
- Create: `worker/tests/fixtures/barotem_order.json`
- Create: `worker/tests/fixtures/itembay_order.json`
- Create: `worker/tests/test_order_adapters.py`

- [x] **Step 1: Add fixture-driven failing tests**

Each fixture contains only extracted text keyed by `order_no`, `region`, `title`, `quantity`, `buyer`, and `status`. Test `adapter_for("itemmania")`, `adapter_for("barotem")`, and `adapter_for("itembay")`; each must return the same `NormalizedOrder` semantics and must ignore unpaid/cancelled rows.

```python
def test_itemmania_paid_adena_row_is_normalized():
    raw = load_fixture("itemmania_order.json")
    order = adapter_for("itemmania").normalize(raw)
    assert order.source_order_no == "M-100"
    assert order.asset_amount == Decimal("2500000")
```

- [x] **Step 2: Verify RED**

Run: `cd worker && python3 -m unittest tests.test_order_adapters -v`  
Expected: import failure for `orders.adapters`.

- [x] **Step 3: Implement adapters without browser dependencies**

Define `ItemmaniaAdapter`, `BarotemAdapter`, and `ItembayAdapter`. Keep Korean number cleanup in one helper that accepts commas and `만` units. `normalize(raw)` returns `None` unless status is in that platform adapter's paid/ready allowlist. `adapter_for` accepts only the three stable platform codes and raises `ValueError` otherwise.

- [x] **Step 4: Verify GREEN**

Run: `cd worker && python3 -m unittest tests.test_order_adapters -v`  
Expected: all three platform tests PASS.

- [x] **Step 5: Commit**

```bash
git add worker/orders/adapters.py worker/tests/fixtures worker/tests/test_order_adapters.py
git commit -m "feat: normalize three marketplace order formats"
```

### Task 3: Persist ingested orders idempotently in Backend

**Files:**
- Create: `backend/src/main/java/com/auto/trade/OrderDetectedMessage.java`
- Create: `backend/src/main/java/com/auto/trade/MarketplaceOrderIngestionService.java`
- Modify: `backend/src/main/java/com/auto/mapper/GameItemOrderMapper.java`
- Modify: `sql/1_central_control.sql`
- Modify: `sql/2_lineage_trade_foundation.sql`
- Test: `backend/src/test/java/com/auto/trade/MarketplaceOrderIngestionServiceTest.java`

- [ ] **Step 1: Write failing idempotency and validation tests**

Test that `(website_id, source_order_no)` creates exactly one order, a repeated message returns the existing ID, unknown region mapping is rejected before insert, and `asset_type != adena` is suspended with `last_error_code=UNSUPPORTED_ASSET`.

- [ ] **Step 2: Verify RED**

Run: `cd backend && mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=MarketplaceOrderIngestionServiceTest test`  
Expected: compilation failure for missing ingestion types.

- [ ] **Step 3: Implement the guarded upsert**

Add unique key `uk_game_item_orders_source (website_id, source_order_no)`. Parse the message into `OrderDetectedMessage`, resolve the configured internal region ID, create `GameItemOrder` at `validated`, then transition Adena orders to `waiting_assignment`. On duplicate-key races, query and return the existing row. Store only the bounded raw title in `remark`; do not persist HTML or secrets.

- [ ] **Step 4: Verify GREEN and schema contract**

Run: `cd backend && mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=MarketplaceOrderIngestionServiceTest,TradeSchemaContractTest test`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/auto/trade backend/src/main/java/com/auto/mapper sql backend/src/test/java/com/auto/trade
git commit -m "feat: ingest marketplace orders idempotently"
```

### Task 4: Connect Worker observations to Backend ingestion

**Files:**
- Modify: `worker/reporter.py`
- Modify: `worker/automation/order_monitor.py`
- Modify: `backend/src/main/java/com/auto/ws/AgentWebSocketHandler.java`
- Test: `worker/tests/test_trade_reporter.py`
- Test: `backend/src/test/java/com/auto/ws/AgentWebSocketOrderIngestionTest.java`

- [ ] **Step 1: Write failing protocol tests**

Worker test expects `Reporter.report_order_detected(account_id, order)` to emit `type=order_detected`, `account_id`, and `order.to_wire()`. Backend test sends this JSON from the currently bound session and verifies `MarketplaceOrderIngestionService.ingest(machineId, accountId, order)` once; a replaced session must be ignored.

- [ ] **Step 2: Verify RED**

Run both focused suites and confirm missing methods/constructor dependencies.

- [ ] **Step 3: Implement the bridge**

Change site detectors to return extracted row dictionaries, normalize each row with the site adapter, and report every normalized order. Retain the existing audio alert as presentation behavior. Route `order_detected` only from the currently bound machine session and cap one WebSocket message at 32 KiB.

- [ ] **Step 4: Verify GREEN**

Run: `cd worker && python3 -m unittest tests.test_trade_reporter tests.test_order_adapters -v`  
Run: `cd backend && mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=AgentWebSocketOrderIngestionTest,MarketplaceOrderIngestionServiceTest test`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add worker backend/src/main/java/com/auto/ws backend/src/test
git commit -m "feat: report detected marketplace orders"
```

### Task 5: Add guarded website-confirmation command

**Files:**
- Create: `worker/orders/confirmation.py`
- Modify: `worker/main.py`
- Modify: `worker/reporter.py`
- Modify: `backend/src/main/java/com/auto/trade/TradeDispatchCoordinator.java`
- Modify: `backend/src/main/java/com/auto/ws/AgentRegistry.java`
- Test: `worker/tests/test_order_confirmation.py`
- Test: `backend/src/test/java/com/auto/trade/WebsiteConfirmationCoordinatorTest.java`

- [ ] **Step 1: Write failing safety tests**

Require assignment ID, source order number and execution token to match the active task gate. Default `mode=dry_run` must report `website_confirmation_ready` without clicking. `mode=execute` must reject unless Backend order status is `game_delivered`; successful worker result moves Backend to `completed`, while timeout keeps `game_delivered` and records an error.

- [ ] **Step 2: Verify RED**

Run focused Worker and Backend tests; expected missing confirmation classes and methods.

- [ ] **Step 3: Implement confirmation as a separate adapter action**

`confirmation.py` receives a live page plus configured `order_row_selector`, `order_no_selector`, and `confirm_button_selector`. It finds the exact source order number, requires exactly one matching row, and in execute mode clicks once after a final text equality check. No broad text search or first-row fallback is permitted.

- [ ] **Step 4: Run full verification**

```bash
cd backend && mvn -Dmaven.repo.local=/tmp/auto-work-m2 test
cd ../worker && PYTHONPYCACHEPREFIX=/tmp/auto-work-pycache python3 -m unittest discover -s tests -v
cd ../frontend && PATH=/Users/houliangyu/.nvm/versions/node/v20.20.0/bin:$PATH npm run build
cd .. && git diff --check
```

Expected: all Backend and Worker tests pass; frontend build succeeds; only the existing Vite chunk-size warning is acceptable.

- [ ] **Step 5: Commit**

```bash
git add worker backend docs/superpowers/plans/2026-07-14-three-platform-order-ingestion.md
git commit -m "feat: guard marketplace delivery confirmation"
```
