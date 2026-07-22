package com.auto.trade;

import org.springframework.stereotype.Component;

import java.util.Comparator;
import java.util.ArrayList;
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
                .filter(TradeCandidate::runtimeMatchesAccount)
                .filter(candidate -> candidate.gameId() == gameId)
                .filter(candidate -> candidate.regionId() == regionId)
                .filter(candidate -> "idle".equals(candidate.executorStatus()))
                .filter(candidate -> uiCanRecover(candidate.uiHealth()))
                .sorted(ORDER)
                .findFirst();
    }

    /** 返回每个候选被淘汰的具体实时条件，供订单错误信息和前端展示。 */
    public List<String> rejectionReasons(
            int gameId,
            int regionId,
            List<TradeCandidate> candidates) {
        List<String> results = new ArrayList<>();
        for (TradeCandidate candidate : candidates) {
            List<String> reasons = new ArrayList<>();
            if (!candidate.machineOnline()) reasons.add("Worker不在线");
            if (!candidate.accountIdle()) reasons.add("游戏账号不是空闲状态");
            if (!candidate.runtimeMatchesAccount()) reasons.add("Worker当前运行账号与绑定账号不一致");
            if (candidate.gameId() != gameId) reasons.add("游戏不匹配");
            if (candidate.regionId() != regionId) reasons.add("大区不匹配");
            if (!"idle".equals(candidate.executorStatus())) {
                reasons.add("执行器状态=" + status(candidate.executorStatus()) + "，需要idle");
            }
            if (!uiCanRecover(candidate.uiHealth())) {
                reasons.add("界面状态=" + status(candidate.uiHealth())
                        + "，且无法由脚本自动恢复");
            }
            if (!reasons.isEmpty()) {
                results.add("机器#" + candidate.machineId()
                        + "/账号#" + candidate.gameAccountId()
                        + "：" + String.join("、", reasons));
            }
        }
        return results;
    }

    private static String status(String value) {
        return value == null || value.isBlank() ? "未上报" : value;
    }

    private static boolean uiCanRecover(String value) {
        return value == null
                || value.isBlank()
                || "unknown".equals(value)
                || "ready".equals(value)
                || "recoverable".equals(value)
                || "starting".equals(value);
    }
}
