package com.auto.trade;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class TradeSchemaContractTest {

    @Test
    void migrationDefinesOrderIdentityAssignmentAndEventStorage() throws Exception {
        String sql = Files.readString(Path.of("..", "sql", "2_lineage_trade_foundation.sql"));

        assertThat(sql).contains(
                "source_order_no",
                "uk_source_order",
                "trade_assignments",
                "assignment_id",
                "trade_events",
                "delivery_status",
                "row_version");
    }
}
