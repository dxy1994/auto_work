package com.auto.trade;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TradeMachineSelectorTest {

    private final TradeMachineSelector selector = new TradeMachineSelector();

    @Test
    void reportsEveryRealtimeConditionThatRejectedAMachine() {
        TradeCandidate candidate = new TradeCandidate(
                1, 10, 7, 30, 0,
                false, true, false,
                "disconnected", "busy", "blocked", null);

        List<String> reasons = selector.rejectionReasons(7, 30, List.of(candidate));

        assertEquals(1, reasons.size());
        assertTrue(reasons.get(0).contains("机器#1/账号#10"));
        assertTrue(reasons.get(0).contains("Worker不在线"));
        assertTrue(reasons.get(0).contains("运行账号与绑定账号不一致"));
        assertTrue(reasons.get(0).contains("执行器状态=busy"));
        assertTrue(reasons.get(0).contains("界面状态=blocked，且无法由脚本自动恢复"));
    }

    @Test
    void selectsOnlyCandidateWhoseRuntimeIsReadyAndMatchesAccount() {
        TradeCandidate mismatch = new TradeCandidate(
                1, 10, 7, 30, 10,
                true, true, false,
                "logged_in", "idle", "ready", null);
        TradeCandidate ready = new TradeCandidate(
                2, 11, 7, 30, 1,
                true, true, true,
                "logged_in", "idle", "ready", null);

        assertEquals(2, selector.select(7, 30, List.of(mismatch, ready)).orElseThrow().machineId());
    }

    @Test
    void acceptsStartingOrRecoverableClientBecauseWorkerCanPrepareIt() {
        TradeCandidate starting = new TradeCandidate(
                1, 10, 7, 30, 0,
                true, true, true,
                "not_ready", "idle", "recoverable", null);

        assertEquals(1, selector.select(7, 30, List.of(starting)).orElseThrow().machineId());
        assertTrue(selector.rejectionReasons(7, 30, List.of(starting)).isEmpty());
    }

    @Test
    void acceptsUnknownUiDuringTheFirstStartupHeartbeat() {
        TradeCandidate starting = new TradeCandidate(
                1, 10, 7, 30, 0,
                true, true, true,
                "unknown", "idle", "unknown", null);

        assertEquals(1, selector.select(7, 30, List.of(starting)).orElseThrow().machineId());
    }
}
