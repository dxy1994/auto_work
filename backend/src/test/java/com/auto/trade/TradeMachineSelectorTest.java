package com.auto.trade;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class TradeMachineSelectorTest {

    private final TradeMachineSelector selector = new TradeMachineSelector();

    @Test
    void filtersWrongGameBusyAndUnhealthyCandidates() {
        TradeCandidate ready = candidate(1, 9, 4, 10,
                true, true, "idle", "ready", Instant.parse("2026-07-14T01:00:00Z"));
        TradeCandidate busy = candidate(2, 9, 4, 99,
                true, true, "running", "ready", Instant.EPOCH);
        TradeCandidate wrongGame = candidate(3, 8, 4, 99,
                true, true, "idle", "ready", Instant.EPOCH);
        TradeCandidate unhealthy = candidate(4, 9, 4, 99,
                true, true, "idle", "mismatch", Instant.EPOCH);

        assertThat(selector.select(9, 4, List.of(busy, wrongGame, unhealthy, ready)))
                .contains(ready);
    }

    @Test
    void filtersOfflineMachineAndUnavailableAccount() {
        TradeCandidate offline = candidate(1, 9, 4, 20,
                false, true, "idle", "ready", Instant.EPOCH);
        TradeCandidate accountInUse = candidate(2, 9, 4, 20,
                true, false, "idle", "ready", Instant.EPOCH);

        assertThat(selector.select(9, 4, List.of(offline, accountInUse))).isEmpty();
    }

    @Test
    void prefersPriorityThenLeastRecentlyUsedThenMachineId() {
        TradeCandidate lowPriority = candidate(1, 9, 4, 10,
                true, true, "idle", "ready", Instant.EPOCH);
        TradeCandidate newer = candidate(3, 9, 4, 20,
                true, true, "idle", "ready", Instant.parse("2026-07-14T01:00:00Z"));
        TradeCandidate olderHigherId = candidate(4, 9, 4, 20,
                true, true, "idle", "ready", Instant.EPOCH);
        TradeCandidate olderLowerId = candidate(2, 9, 4, 20,
                true, true, "idle", "ready", Instant.EPOCH);

        assertThat(selector.select(9, 4,
                List.of(lowPriority, newer, olderHigherId, olderLowerId)))
                .contains(olderLowerId);
    }

    @Test
    void treatsNeverUsedCandidateAsOldest() {
        TradeCandidate neverUsed = candidate(1, 9, 4, 20,
                true, true, "idle", "ready", null);
        TradeCandidate used = candidate(2, 9, 4, 20,
                true, true, "idle", "ready", Instant.EPOCH);

        assertThat(selector.select(9, 4, List.of(used, neverUsed))).contains(neverUsed);
    }

    private TradeCandidate candidate(
            int machineId,
            int gameId,
            int regionId,
            int priority,
            boolean machineOnline,
            boolean accountIdle,
            String executorStatus,
            String uiHealth,
            Instant lastUsedAt) {
        return new TradeCandidate(
                machineId,
                machineId + 100,
                gameId,
                regionId,
                priority,
                machineOnline,
                accountIdle,
                "logged_in",
                executorStatus,
                uiHealth,
                lastUsedAt);
    }
}
