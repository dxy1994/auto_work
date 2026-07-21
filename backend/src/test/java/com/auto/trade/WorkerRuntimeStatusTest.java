package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WorkerRuntimeStatusTest {

    @Test
    void recognizesNewAndLegacyGameExecutorRoles() {
        assertTrue(status("game_executor").isGameExecutor());
        assertTrue(status("trader").isGameExecutor());
        assertFalse(status("monitor").isGameExecutor());
        assertTrue(status("monitor").isMonitor());
    }

    private WorkerRuntimeStatus status(String role) {
        return new WorkerRuntimeStatus(
                role, null, null, null, null, null, null, null, null);
    }
}
