# Lineage Classic Trade Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, testable control-plane foundation that persists trade state, selects an eligible game machine, performs a two-phase `trade_offer`/`trade_start` assignment, and lets a Worker accept or reject without touching the real game.

**Architecture:** Backend remains the authority for orders and assignments. A pure selector filters reported Worker runtime state against machine/game/account configuration; a transactional coordinator reserves the order, then AgentRegistry carries the two-phase WebSocket protocol. Worker owns a single-slot trade execution gate and reports offer decisions and lifecycle events. The actual Lineage screen recognizer and input driver are deliberately deferred to a later plan.

**Tech Stack:** Java 17, Spring Boot 3.2, MyBatis-Plus, MySQL 8, JUnit 5, Mockito, Python 3.9+, `unittest`, WebSocket JSON.

---

## File map

**Database and Backend domain**

- Modify `sql/1_central_control.sql`: make fresh installations include trade columns and tables.
- Create `sql/2_lineage_trade_foundation.sql`: idempotent migration for existing installations.
- Modify `backend/src/main/java/com/auto/entity/GameItemOrder.java`: add durable delivery and assignment fields.
- Create `backend/src/main/java/com/auto/entity/TradeAssignment.java`: persist assignment leases and decisions.
- Create `backend/src/main/java/com/auto/entity/TradeEvent.java`: append-only lifecycle record.
- Create `backend/src/main/java/com/auto/mapper/TradeAssignmentMapper.java`.
- Create `backend/src/main/java/com/auto/mapper/TradeEventMapper.java`.
- Create `backend/src/main/java/com/auto/service/TradeAssignmentService.java` and implementation.
- Create `backend/src/main/java/com/auto/service/TradeEventService.java` and implementation.

**Backend orchestration**

- Create `backend/src/main/java/com/auto/trade/TradeDeliveryStatus.java`: explicit legal state transitions.
- Create `backend/src/main/java/com/auto/trade/WorkerRuntimeStatus.java`: immutable runtime snapshot.
- Create `backend/src/main/java/com/auto/trade/TradeCandidate.java`: selector input.
- Create `backend/src/main/java/com/auto/trade/TradeMachineSelector.java`: pure deterministic selection.
- Create `backend/src/main/java/com/auto/trade/TradeOffer.java`: outbound offer plus ephemeral execution token.
- Create `backend/src/main/java/com/auto/trade/TradeDispatchCoordinator.java`: reserve, offer, accept/reject, start.
- Create `backend/src/main/java/com/auto/controller/TradeDispatchController.java`: manual dispatch/status API for phase-one validation.
- Modify `backend/src/main/java/com/auto/service/GameItemOrderService.java`: optimistic delivery transition contract.
- Modify `backend/src/main/java/com/auto/service/impl/GameItemOrderServiceImpl.java`: implement guarded delivery transition.
- Modify `backend/src/main/java/com/auto/ws/AgentRegistry.java`: runtime snapshots and outbound trade messages.
- Modify `backend/src/main/java/com/auto/ws/AgentWebSocketHandler.java`: route runtime and trade decision messages.

**Worker protocol**

- Create `worker/trade/__init__.py`.
- Create `worker/trade/runtime_status.py`: thread-safe local runtime snapshot.
- Create `worker/trade/task_gate.py`: one-slot offer/start/cancel state machine.
- Modify `worker/reporter.py`: report runtime, offer decisions, and trade lifecycle.
- Modify `worker/main.py`: add runtime heartbeat payload and trade message dispatch.

**Tests**

- Create `backend/src/test/java/com/auto/trade/TradeDeliveryStatusTest.java`.
- Create `backend/src/test/java/com/auto/trade/TradeMachineSelectorTest.java`.
- Create `backend/src/test/java/com/auto/trade/TradeDispatchCoordinatorTest.java`.
- Create `worker/tests/__init__.py`.
- Create `worker/tests/test_trade_task_gate.py`.
- Create `worker/tests/test_runtime_status.py`.

## Task 1: Add the durable trade schema

**Files:**

- Create: `sql/2_lineage_trade_foundation.sql`
- Modify: `sql/1_central_control.sql`
- Modify: `backend/src/main/java/com/auto/entity/GameItemOrder.java`
- Create: `backend/src/main/java/com/auto/entity/TradeAssignment.java`
- Create: `backend/src/main/java/com/auto/entity/TradeEvent.java`
- Create: `backend/src/main/java/com/auto/mapper/TradeAssignmentMapper.java`
- Create: `backend/src/main/java/com/auto/mapper/TradeEventMapper.java`
- Create: `backend/src/main/java/com/auto/service/TradeAssignmentService.java`
- Create: `backend/src/main/java/com/auto/service/TradeEventService.java`
- Create: `backend/src/main/java/com/auto/service/impl/TradeAssignmentServiceImpl.java`
- Create: `backend/src/main/java/com/auto/service/impl/TradeEventServiceImpl.java`

- [ ] **Step 1: Write the migration contract test**

Create `backend/src/test/java/com/auto/trade/TradeSchemaContractTest.java`:

```java
package com.auto.trade;

import org.junit.jupiter.api.Test;
import java.nio.file.Files;
import java.nio.file.Path;
import static org.assertj.core.api.Assertions.assertThat;

class TradeSchemaContractTest {
    @Test
    void migrationDefinesOrderIdentityAssignmentAndEventStorage() throws Exception {
        String sql = Files.readString(Path.of("..", "sql", "2_lineage_trade_foundation.sql"));
        assertThat(sql).contains("source_order_no", "uk_source_order", "trade_assignments",
                "assignment_id", "trade_events", "delivery_status", "row_version");
    }
}
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd backend
/Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=TradeSchemaContractTest test
```

Expected: FAIL because `sql/2_lineage_trade_foundation.sql` does not exist.

- [ ] **Step 3: Add migration and fresh-install schema**

The migration is a versioned, one-time script and must add these order columns and tables using MySQL 8 syntax:

```sql
ALTER TABLE game_item_orders
    ADD COLUMN website_id INT NULL,
    ADD COLUMN source_order_no VARCHAR(100) NULL,
    ADD COLUMN game_account_id INT NULL,
    ADD COLUMN buyer_character VARCHAR(100) NULL,
    ADD COLUMN asset_type VARCHAR(32) NOT NULL DEFAULT 'adena',
    ADD COLUMN asset_amount DECIMAL(30,0) NULL,
    ADD COLUMN delivery_status VARCHAR(32) NOT NULL DEFAULT 'detected',
    ADD COLUMN assignment_id VARCHAR(36) NULL,
    ADD COLUMN row_version INT NOT NULL DEFAULT 0,
    ADD COLUMN game_delivered_at DATETIME NULL,
    ADD COLUMN website_confirmed_at DATETIME NULL,
    ADD COLUMN last_error_code VARCHAR(64) NULL,
    ADD COLUMN last_error_message VARCHAR(500) NULL,
    ADD UNIQUE KEY uk_source_order (website_id, source_order_no);

CREATE TABLE IF NOT EXISTS trade_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id VARCHAR(36) NOT NULL,
    order_id INT NOT NULL,
    machine_id INT NOT NULL,
    game_account_id INT NOT NULL,
    status VARCHAR(24) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    lease_expires_at DATETIME NOT NULL,
    reject_reason VARCHAR(255) NULL,
    accepted_at DATETIME NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_assignment_id (assignment_id),
    KEY idx_assignment_order_status (order_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    assignment_id VARCHAR(36) NULL,
    event_type VARCHAR(64) NOT NULL,
    from_status VARCHAR(32) NULL,
    to_status VARCHAR(32) NULL,
    message VARCHAR(500) NULL,
    payload JSON NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_trade_event_order (order_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Mirror the same final definitions in `sql/1_central_control.sql`. Map the new columns in `GameItemOrder`, annotating `rowVersion` with `@Version`. Add conventional MyBatis-Plus entities, mappers, and empty `IService` implementations for `TradeAssignment` and `TradeEvent`.

- [ ] **Step 4: Run schema test and Backend compile**

Run:

```bash
cd backend
/Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=TradeSchemaContractTest test
```

Expected: PASS, one test, BUILD SUCCESS.

- [ ] **Step 5: Commit the schema foundation**

```bash
git add sql/1_central_control.sql sql/2_lineage_trade_foundation.sql backend/src/main backend/src/test/java/com/auto/trade/TradeSchemaContractTest.java
git commit -m "feat: add durable trade assignment schema"
```

## Task 2: Enforce legal delivery-state transitions

**Files:**

- Create: `backend/src/main/java/com/auto/trade/TradeDeliveryStatus.java`
- Test: `backend/src/test/java/com/auto/trade/TradeDeliveryStatusTest.java`

- [ ] **Step 1: Write failing transition tests**

```java
package com.auto.trade;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TradeDeliveryStatusTest {
    @Test
    void allowsOfferThenAssignment() {
        assertThat(TradeDeliveryStatus.WAITING_ASSIGNMENT.canMoveTo(TradeDeliveryStatus.OFFERED)).isTrue();
        assertThat(TradeDeliveryStatus.OFFERED.canMoveTo(TradeDeliveryStatus.ASSIGNED)).isTrue();
    }

    @Test
    void gameDeliveredCannotReturnToGameExecution() {
        assertThat(TradeDeliveryStatus.GAME_DELIVERED.canMoveTo(TradeDeliveryStatus.ASSIGNED)).isFalse();
        assertThatThrownBy(() -> TradeDeliveryStatus.GAME_DELIVERED.requireMoveTo(TradeDeliveryStatus.ASSIGNED))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void gameDeliveredCanRetryWebsiteConfirmation() {
        assertThat(TradeDeliveryStatus.GAME_DELIVERED.canMoveTo(TradeDeliveryStatus.WEBSITE_CONFIRMING)).isTrue();
        assertThat(TradeDeliveryStatus.WEBSITE_CONFIRMING.canMoveTo(TradeDeliveryStatus.GAME_DELIVERED)).isTrue();
    }
}
```

- [ ] **Step 2: Run the test and verify compilation failure**

Run `cd backend && /Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=TradeDeliveryStatusTest test`.

Expected: FAIL because `TradeDeliveryStatus` is missing.

- [ ] **Step 3: Implement the explicit transition graph**

```java
package com.auto.trade;

import java.util.EnumSet;
import java.util.Set;

public enum TradeDeliveryStatus {
    DETECTED, VALIDATED, WAITING_ASSIGNMENT, OFFERED, ASSIGNED, PRECHECKING,
    WAITING_BUYER, VERIFYING_BUYER, STAGING_ASSET, REVIEWING, CONFIRMING,
    GAME_DELIVERED, WEBSITE_CONFIRMING, COMPLETED, SUSPENDED, CANCELLED;

    public boolean canMoveTo(TradeDeliveryStatus target) {
        return allowedTargets().contains(target);
    }

    public void requireMoveTo(TradeDeliveryStatus target) {
        if (!canMoveTo(target)) {
            throw new IllegalStateException("illegal trade transition: " + this + " -> " + target);
        }
    }

    private Set<TradeDeliveryStatus> allowedTargets() {
        return switch (this) {
            case DETECTED -> EnumSet.of(VALIDATED, SUSPENDED, CANCELLED);
            case VALIDATED -> EnumSet.of(WAITING_ASSIGNMENT, SUSPENDED, CANCELLED);
            case WAITING_ASSIGNMENT -> EnumSet.of(OFFERED, SUSPENDED, CANCELLED);
            case OFFERED -> EnumSet.of(WAITING_ASSIGNMENT, ASSIGNED, SUSPENDED, CANCELLED);
            case ASSIGNED -> EnumSet.of(PRECHECKING, SUSPENDED, CANCELLED);
            case PRECHECKING -> EnumSet.of(WAITING_BUYER, SUSPENDED);
            case WAITING_BUYER -> EnumSet.of(VERIFYING_BUYER, SUSPENDED);
            case VERIFYING_BUYER -> EnumSet.of(WAITING_BUYER, STAGING_ASSET, SUSPENDED);
            case STAGING_ASSET -> EnumSet.of(REVIEWING, SUSPENDED);
            case REVIEWING -> EnumSet.of(CONFIRMING, SUSPENDED);
            case CONFIRMING -> EnumSet.of(GAME_DELIVERED, SUSPENDED);
            case GAME_DELIVERED -> EnumSet.of(WEBSITE_CONFIRMING, SUSPENDED);
            case WEBSITE_CONFIRMING -> EnumSet.of(GAME_DELIVERED, COMPLETED, SUSPENDED);
            case SUSPENDED -> EnumSet.of(WAITING_ASSIGNMENT, GAME_DELIVERED, CANCELLED);
            case COMPLETED, CANCELLED -> EnumSet.noneOf(TradeDeliveryStatus.class);
        };
    }
}
```

- [ ] **Step 4: Run tests**

Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/auto/trade/TradeDeliveryStatus.java backend/src/test/java/com/auto/trade/TradeDeliveryStatusTest.java
git commit -m "feat: enforce trade delivery transitions"
```

## Task 3: Capture Worker runtime status

**Files:**

- Create: `worker/trade/__init__.py`
- Create: `worker/trade/runtime_status.py`
- Create: `worker/tests/__init__.py`
- Create: `worker/tests/test_runtime_status.py`
- Modify: `worker/main.py`
- Create: `backend/src/main/java/com/auto/trade/WorkerRuntimeStatus.java`
- Modify: `backend/src/main/java/com/auto/ws/AgentRegistry.java`
- Modify: `backend/src/main/java/com/auto/ws/AgentWebSocketHandler.java`

- [ ] **Step 1: Write the failing Python snapshot test**

```python
import unittest
from trade.runtime_status import RuntimeStatus


class RuntimeStatusTest(unittest.TestCase):
    def test_snapshot_is_copy_and_uses_protocol_keys(self):
        status = RuntimeStatus()
        status.update(game_id=3, game_account_id=27, region_id=8,
                      client_status="logged_in", character_name="테스터",
                      executor_status="idle", ui_health="ready")
        snapshot = status.snapshot()
        snapshot["executor_status"] = "busy"
        self.assertEqual("idle", status.snapshot()["executor_status"])
        self.assertIsNone(status.snapshot()["current_assignment_id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

Run `cd worker && python3 -m unittest tests.test_runtime_status -v`.

Expected: FAIL because `trade.runtime_status` does not exist.

- [ ] **Step 3: Implement the thread-safe runtime snapshot**

```python
import threading


class RuntimeStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self._values = {
            "game_id": None,
            "game_account_id": None,
            "region_id": None,
            "client_status": "unknown",
            "character_name": None,
            "executor_status": "idle",
            "current_assignment_id": None,
            "ui_health": "unknown",
        }

    def update(self, **values):
        unknown = set(values) - set(self._values)
        if unknown:
            raise ValueError(f"unknown runtime fields: {sorted(unknown)}")
        with self._lock:
            self._values.update(values)

    def snapshot(self):
        with self._lock:
            return dict(self._values)
```

Add a module singleton `runtime_status`. Change `_heartbeat` in `worker/main.py` to send `{"type": "heartbeat", "runtime": runtime_status.snapshot()}`.

Create a Java `WorkerRuntimeStatus` record with the same fields. In `AgentRegistry`, keep a `ConcurrentHashMap<Integer, WorkerRuntimeStatus>`, parse the heartbeat runtime, expose `getRuntimeStatus(machineId)`, and remove the snapshot when the active session disconnects. Route heartbeat payloads through `AgentWebSocketHandler` to `updateHeartbeat(machineId, raw)`.

- [ ] **Step 4: Run Worker test and Backend compile**

```bash
cd worker && python3 -m unittest tests.test_runtime_status -v
cd ../backend && /Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 test
```

Expected: Python test PASS and Backend BUILD SUCCESS.

- [ ] **Step 5: Commit**

```bash
git add worker/trade worker/tests worker/main.py backend/src/main/java/com/auto/trade/WorkerRuntimeStatus.java backend/src/main/java/com/auto/ws
git commit -m "feat: report game runtime in worker heartbeat"
```

## Task 4: Select an eligible target deterministically

**Files:**

- Create: `backend/src/main/java/com/auto/trade/TradeCandidate.java`
- Create: `backend/src/main/java/com/auto/trade/TradeMachineSelector.java`
- Test: `backend/src/test/java/com/auto/trade/TradeMachineSelectorTest.java`

- [ ] **Step 1: Write failing selection tests**

```java
package com.auto.trade;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class TradeMachineSelectorTest {
    private final TradeMachineSelector selector = new TradeMachineSelector();

    @Test
    void filtersWrongGameBusyAndUnhealthyCandidates() {
        TradeCandidate ready = candidate(1, 9, 4, 10, "idle", "ready", Instant.parse("2026-07-14T01:00:00Z"));
        TradeCandidate busy = candidate(2, 9, 4, 99, "running", "ready", Instant.EPOCH);
        TradeCandidate wrongGame = candidate(3, 8, 4, 99, "idle", "ready", Instant.EPOCH);
        assertThat(selector.select(9, 4, List.of(busy, wrongGame, ready))).contains(ready);
    }

    @Test
    void prefersPriorityThenLeastRecentlyUsed() {
        TradeCandidate older = candidate(1, 9, 4, 20, "idle", "ready", Instant.EPOCH);
        TradeCandidate newer = candidate(2, 9, 4, 20, "idle", "ready", Instant.parse("2026-07-14T01:00:00Z"));
        assertThat(selector.select(9, 4, List.of(newer, older))).contains(older);
    }

    private TradeCandidate candidate(int machineId, int gameId, int regionId, int priority,
                                     String executor, String health, Instant lastUsed) {
        return new TradeCandidate(machineId, machineId + 100, gameId, regionId, priority,
                true, true, "logged_in", executor, health, lastUsed);
    }
}
```

- [ ] **Step 2: Run and verify compilation failure**

Run the Maven command with `-Dtest=TradeMachineSelectorTest`.

- [ ] **Step 3: Implement candidate and selector**

```java
public record TradeCandidate(
        int machineId, int gameAccountId, int gameId, int regionId, int priority,
        boolean machineOnline, boolean accountIdle, String clientStatus,
        String executorStatus, String uiHealth, Instant lastUsedAt) {
}
```

```java
public Optional<TradeCandidate> select(int gameId, int regionId, List<TradeCandidate> candidates) {
    return candidates.stream()
            .filter(TradeCandidate::machineOnline)
            .filter(TradeCandidate::accountIdle)
            .filter(c -> c.gameId() == gameId && c.regionId() == regionId)
            .filter(c -> "logged_in".equals(c.clientStatus()))
            .filter(c -> "idle".equals(c.executorStatus()))
            .filter(c -> "ready".equals(c.uiHealth()))
            .sorted(Comparator.comparingInt(TradeCandidate::priority).reversed()
                    .thenComparing(TradeCandidate::lastUsedAt)
                    .thenComparingInt(TradeCandidate::machineId))
            .findFirst();
}
```

- [ ] **Step 4: Run tests**

Expected: both selector tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/auto/trade/TradeCandidate.java backend/src/main/java/com/auto/trade/TradeMachineSelector.java backend/src/test/java/com/auto/trade/TradeMachineSelectorTest.java
git commit -m "feat: select eligible trade machines"
```

## Task 5: Implement the Worker offer/start gate

**Files:**

- Create: `worker/trade/task_gate.py`
- Test: `worker/tests/test_trade_task_gate.py`
- Modify: `worker/reporter.py`
- Modify: `worker/main.py`

- [ ] **Step 1: Write failing gate tests**

```python
import unittest
from trade.task_gate import TradeTaskGate


class TradeTaskGateTest(unittest.TestCase):
    def test_offer_reserves_one_assignment_and_rejects_second(self):
        gate = TradeTaskGate()
        self.assertEqual((True, "accepted"), gate.offer("a-1", "token-1"))
        self.assertEqual((False, "executor_busy"), gate.offer("a-2", "token-2"))

    def test_start_requires_matching_assignment_and_token(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")
        self.assertFalse(gate.start("a-1", "wrong"))
        self.assertTrue(gate.start("a-1", "token-1"))
        self.assertEqual("running", gate.snapshot()["status"])

    def test_cancel_releases_offer(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")
        self.assertTrue(gate.cancel("a-1"))
        self.assertEqual("idle", gate.snapshot()["status"])
```

- [ ] **Step 2: Run and verify failure**

Run `cd worker && python3 -m unittest tests.test_trade_task_gate -v`.

- [ ] **Step 3: Implement the single-slot gate**

`TradeTaskGate` must store only one assignment, compare both assignment ID and token using `hmac.compare_digest`, and expose `offer`, `start`, `complete`, `cancel`, and `snapshot`. It must never log the token. `offer` returns `(False, "executor_busy")` when occupied.

Add Reporter methods with these exact payloads:

```python
def report_trade_offer_decision(self, assignment_id, accepted, reason=""):
    self._client.send_threadsafe({
        "type": "trade_offer_decision",
        "assignment_id": assignment_id,
        "accepted": accepted,
        "reason": reason,
    })

def report_trade_status(self, assignment_id, status, message=""):
    self._client.send_threadsafe({
        "type": "trade_status",
        "assignment_id": assignment_id,
        "status": status,
        "message": message,
    })
```

Handle `trade_offer`, `trade_start`, and `trade_cancel` in `_dispatch_message`. Phase one `trade_start` uses a no-op runner that reports `started`, then `simulation_completed`, and releases the gate; it must not import or invoke any input driver.

- [ ] **Step 4: Run Worker tests**

Run `cd worker && python3 -m unittest discover -s tests -v`.

Expected: all Worker tests PASS.

- [ ] **Step 5: Commit**

```bash
git add worker/trade/task_gate.py worker/tests/test_trade_task_gate.py worker/reporter.py worker/main.py
git commit -m "feat: add two-phase worker trade gate"
```

## Task 6: Coordinate Backend offer acceptance and start

**Files:**

- Create: `backend/src/main/java/com/auto/trade/TradeDispatchCoordinator.java`
- Create: `backend/src/main/java/com/auto/trade/TradeOffer.java`
- Create: `backend/src/main/java/com/auto/controller/TradeDispatchController.java`
- Modify: `backend/src/main/java/com/auto/service/GameItemOrderService.java`
- Modify: `backend/src/main/java/com/auto/service/impl/GameItemOrderServiceImpl.java`
- Modify: `backend/src/main/java/com/auto/ws/AgentRegistry.java`
- Modify: `backend/src/main/java/com/auto/ws/AgentWebSocketHandler.java`
- Test: `backend/src/test/java/com/auto/trade/TradeDispatchCoordinatorTest.java`

- [x] **Step 1: Write failing coordinator tests**

Use Mockito to mock order, assignment, event and registry dependencies. Cover these cases:

```java
@Test
void acceptedOfferMovesOrderToAssignedAndSendsStart() {
    TradeOffer offer = coordinator.dispatch(orderId);
    coordinator.handleDecision(offer.assignmentId(), true, null);
    verify(agentRegistry).sendTradeStart(offer.machineId(), offer.assignmentId(), offer.executionToken());
    verify(orderService).updateDeliveryStatus(orderId, "offered", "assigned", offer.assignmentId());
}

@Test
void rejectedOfferReturnsOrderToWaitingAssignment() {
    TradeOffer offer = coordinator.dispatch(orderId);
    coordinator.handleDecision(offer.assignmentId(), false, "ui_not_ready");
    verify(orderService).updateDeliveryStatus(orderId, "offered", "waiting_assignment", null);
    verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
}

@Test
void staleDecisionCannotStartTrade() {
    assertThatThrownBy(() -> coordinator.handleDecision("unknown", true, null))
            .isInstanceOf(IllegalStateException.class);
    verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
}
```

- [x] **Step 2: Run and verify compilation failure**

Run the Maven test with `-Dtest=TradeDispatchCoordinatorTest`.

- [x] **Step 3: Implement transactional coordination**

The coordinator must:

1. Load an order in `waiting_assignment`.
2. Build candidates from active `machine_games`, idle bound `game_accounts`, online Agent sessions and runtime snapshots.
3. Ask `TradeMachineSelector` for one candidate.
4. Generate a UUID assignment and 256-bit random execution token.
5. Persist only the SHA-256 token hash.
6. Atomically change the order to `offered`, set `assignment_id`, and mark machine/account busy.
7. Send `trade_offer` with a 30-second lease.
8. On accepted decision, compare the active assignment/session, set `assigned`, and send `trade_start` with the in-memory token.
9. On rejection/send failure/lease expiry, set the assignment rejected or expired, restore order to `waiting_assignment`, and release machine/account.

Define the outbound value with one consistent type:

```java
package com.auto.trade;

import java.time.Instant;
import java.util.Map;

public record TradeOffer(
        String assignmentId,
        int machineId,
        String executionToken,
        Instant leaseExpiresAt,
        Map<String, Object> orderPayload) {
}
```

Extend `GameItemOrderService` with this guarded transition and implement it using an update condition on `id`, expected `delivery_status`, and `row_version`; throw `IllegalStateException` when zero rows update:

```java
void updateDeliveryStatus(Integer orderId, String expectedStatus, String targetStatus,
                          String assignmentId);
```

AgentRegistry outbound payloads:

```java
public boolean sendTradeOffer(int machineId, TradeOffer offer) {
    return sendToAgent(machineId, Map.of(
            "type", "trade_offer",
            "assignment_id", offer.assignmentId(),
            "execution_token", offer.executionToken(),
            "lease_expires_at", offer.leaseExpiresAt().toString(),
            "order", offer.orderPayload()));
}

public boolean sendTradeStart(int machineId, String assignmentId, String token) {
    return sendToAgent(machineId, Map.of(
            "type", "trade_start",
            "assignment_id", assignmentId,
            "execution_token", token));
}
```

Route `trade_offer_decision` and `trade_status` from `AgentWebSocketHandler` only when the sender session is still bound to the assignment machine. Add `POST /api/trades/{orderId}/dispatch` and `GET /api/trades/{orderId}/status` for controlled phase-one validation.

- [x] **Step 4: Run coordinator and full Backend tests**

```bash
cd backend
/Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 -Dtest=TradeDispatchCoordinatorTest test
/Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 test
```

Expected: coordinator tests and full Backend test suite PASS.

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/auto/trade backend/src/main/java/com/auto/controller/TradeDispatchController.java backend/src/main/java/com/auto/service backend/src/main/java/com/auto/ws backend/src/test/java/com/auto/trade/TradeDispatchCoordinatorTest.java
git commit -m "feat: coordinate two-phase trade assignment"
```

## Task 7: Verify the no-game-control scheduling slice

**Files:**

- Modify: `worker/README.md`
- Create: `docs/trade-foundation-verification.md`

- [ ] **Step 1: Document the simulation boundary and protocol**

Document that phase one intentionally stops at a simulation runner, list `trade_offer`, `trade_offer_decision`, `trade_start`, `trade_status`, and `trade_cancel`, and state that no screen capture or input dependency exists yet.

- [ ] **Step 2: Run all automated verification**

```bash
cd backend
/Users/houliangyu/apache-maven-3.9.12/bin/mvn -Dmaven.repo.local=/tmp/auto-work-m2 test
cd ../worker
python3 -m unittest discover -s tests -v
cd ../frontend
PATH=/Users/houliangyu/.nvm/versions/node/v20.20.0/bin:$PATH npm run build
cd ..
git diff --check
git status --short
```

Expected:

- Backend: BUILD SUCCESS.
- Worker: all tests OK.
- Frontend: Vite build succeeds; the existing large-chunk warning is acceptable.
- `git diff --check`: no output.
- `git status`: only the two documentation files before final commit.

- [ ] **Step 3: Commit verification documentation**

```bash
git add worker/README.md docs/trade-foundation-verification.md docs/superpowers/plans/2026-07-14-lineage-classic-trade-foundation.md
git commit -m "docs: verify trade scheduling foundation"
```

- [ ] **Step 4: Record the next plan boundaries**

After this plan passes, create separate implementation plans in this order:

1. Three-platform normalized order ingestion and website confirmation.
2. `FrameSource`/`InputDriver` interfaces plus Windows implementation.
3. Lineage Classic screen-recognition replay harness and Adena state machine.
4. Evidence storage, recovery operations, and management UI.
