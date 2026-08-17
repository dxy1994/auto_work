package com.auto.trade;

public record SalesProductsSyncResult(
        int receivedCount,
        int insertedCount,
        int updatedCount,
        int unchangedCount,
        int deletedCount) {
}
