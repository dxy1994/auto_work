package com.auto.trade;

import org.springframework.stereotype.Component;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/** 按游戏、大区、运行态、优先级和最近使用时间确定目标机器。 */
@Component
public class TradeMachineSelector {

    private static final Comparator<TradeCandidate> ORDER =
            Comparator.comparingInt(TradeCandidate::priority).reversed()
                    .thenComparing(TradeCandidate::lastUsedAt,
                            Comparator.nullsFirst(Comparator.naturalOrder()))
                    .thenComparingInt(TradeCandidate::machineId);

    public Optional<TradeCandidate> select(
            int gameId,
            int regionId,
            List<TradeCandidate> candidates) {
        return candidates.stream()
                .filter(TradeCandidate::machineOnline)
                .filter(TradeCandidate::accountIdle)
                .filter(candidate -> candidate.gameId() == gameId)
                .filter(candidate -> candidate.regionId() == regionId)
                .filter(candidate -> "logged_in".equals(candidate.clientStatus()))
                .filter(candidate -> "idle".equals(candidate.executorStatus()))
                .filter(candidate -> "ready".equals(candidate.uiHealth()))
                .sorted(ORDER)
                .findFirst();
    }
}
