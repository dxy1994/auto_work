package com.auto.trade;

import com.auto.entity.Game;
import com.auto.entity.GameAccount;
import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegion;
import com.auto.entity.Machine;
import com.auto.entity.MachineGameAccount;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.MachineGameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.context.event.EventListener;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.scheduling.annotation.Scheduled;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/** 总控交易选机、预占以及 offer/start 两阶段协调器。 */
@Service
@Slf4j
public class TradeDispatchCoordinator {

    private static final int OFFER_LEASE_SECONDS = 30;
    private static final int EXECUTION_WATCHDOG_GRACE_SECONDS = 180;
    private static final Set<String> PROGRESS_STATUSES = Set.of(
            "started", "preparing", "switching_region", "waiting_buyer",
            "waiting_buyer_review", "trading", "verifying");

    private final GameItemOrderService orderService;
    private final MachineGameAccountService machineGameService;
    private final GameAccountService gameAccountService;
    private final MachineService machineService;
    private final TradeAssignmentService assignmentService;
    private final AgentRegistry agentRegistry;
    private final TradeMachineSelector selector;
    private final OrderDeliveryStateMachine stateMachine;
    private final GameService gameService;
    private final GameItemOrderDetailService detailService;
    private final GameItemService itemService;
    private final GameRegionService gameRegionService;
    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, TradeOffer> pendingOffers = new ConcurrentHashMap<>();
    private final Set<String> acceptedAssignments = ConcurrentHashMap.newKeySet();
    private final Map<String, Instant> executionDeadlines = new ConcurrentHashMap<>();

    public TradeDispatchCoordinator(
            GameItemOrderService orderService,
            MachineGameAccountService machineGameService,
            GameAccountService gameAccountService,
            MachineService machineService,
            TradeAssignmentService assignmentService,
            AgentRegistry agentRegistry,
            TradeMachineSelector selector,
            OrderDeliveryStateMachine stateMachine,
            GameService gameService,
            GameItemOrderDetailService detailService,
            GameItemService itemService,
            GameRegionService gameRegionService) {
        this.orderService = orderService;
        this.machineGameService = machineGameService;
        this.gameAccountService = gameAccountService;
        this.machineService = machineService;
        this.assignmentService = assignmentService;
        this.agentRegistry = agentRegistry;
        this.selector = selector;
        this.stateMachine = stateMachine;
        this.gameService = gameService;
        this.detailService = detailService;
        this.itemService = itemService;
        this.gameRegionService = gameRegionService;
    }

    @Transactional
    public TradeOffer dispatch(Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw new IllegalStateException("订单不存在");
        }

        // 校验交易通道：目前仅支持 script（游戏内键鼠交易）
        Game game = gameService.getById(order.getGameId());
        if (game == null || !"script".equals(game.getTradeType())) {
            throw new IllegalStateException("该游戏不支持自动交易（tradeType="
                    + (game != null ? game.getTradeType() : "null") + "）");
        }

        // 根据当前状态选择事件
        DeliveryEvent event;
        String ds = order.getDeliveryStatus();
        if ("greeting".equals(ds)) {
            event = DeliveryEvent.GREETING_SUCCESS;
        } else if ("waiting_assignment".equals(ds)) {
            event = DeliveryEvent.MANUAL_DISPATCH;
        } else {
            throw new IllegalStateException("订单不在待指派状态");
        }

        TradeCandidate candidate = selector.select(
                        order.getGameId(), order.getRegionId(), buildCandidates(order))
                .orElseThrow(() -> new IllegalStateException("没有符合条件的交易机器"));

        String assignmentId = UUID.randomUUID().toString();
        String token = newExecutionToken();
        Instant leaseExpiresAt = Instant.now().plusSeconds(OFFER_LEASE_SECONDS);
        TradeOffer offer = new TradeOffer(
                assignmentId,
                orderId,
                candidate.machineId(),
                candidate.gameAccountId(),
                token,
                leaseExpiresAt,
                orderPayload(order, game, candidate.gameAccountId()));

        // 状态机驱动状态转换
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", assignmentId);
        ctx.put("message", "总控发送交易指派");
        order.setAssignmentId(assignmentId);
        stateMachine.fire(order, event, ctx);

        // 指派相关副作用
        persistAssignment(offer);
        reserveResources(candidate.machineId(), candidate.gameAccountId());
        pendingOffers.put(assignmentId, offer);

        if (!agentRegistry.sendTradeOffer(candidate.machineId(), offer)) {
            pendingOffers.remove(assignmentId);
            throw new IllegalStateException("发送交易指派失败");
        }
        return offer;
    }

    @Transactional
    public void handleDecision(
            String assignmentId,
            int machineId,
            boolean accepted,
            String reason) {
        TradeOffer offer = requirePendingOffer(assignmentId, machineId);
        synchronized (offer) {
            if (acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派已接受，不能重复决策");
            }
            if (offer.leaseExpiresAt().isBefore(Instant.now())) {
                expireOffer(offer);
                throw new IllegalStateException("指派租约已过期");
            }
            if (!accepted) {
                rejectOffer(offer, reason == null ? "worker_rejected" : reason);
                return;
            }

            // 状态机：offered → assigned
            GameItemOrder order = orderService.getById(offer.orderId());
            Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", assignmentId);
        ctx.put("machineId", machineId);
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("message", "Worker 接受交易指派");
            stateMachine.fire(order, DeliveryEvent.OFFER_ACCEPTED, ctx);
            acceptedAssignments.add(assignmentId);
            executionDeadlines.put(
                    assignmentId,
                    Instant.now().plusSeconds(executionTimeoutSeconds(offer)));

            if (!agentRegistry.sendTradeStart(machineId, assignmentId, offer.executionToken())) {
                // 启动指令未下发到 Worker，可安全重新指派。
                Map<String, Object> failCtx = new HashMap<>();
                failCtx.put("assignmentId", assignmentId);
                failCtx.put("machineId", machineId);
                failCtx.put("gameAccountId", offer.gameAccountId());
                failCtx.put("message", "发送交易启动指令失败");
                failCtx.put("errorCode", "START_DISPATCH_FAILED");
                failCtx.put("errorMessage", "发送交易启动指令失败");
                stateMachine.fire(order, DeliveryEvent.START_FAILED, failCtx);
                acceptedAssignments.remove(assignmentId);
                pendingOffers.remove(assignmentId);
                executionDeadlines.remove(assignmentId);
                throw new IllegalStateException("发送交易启动指令失败");
            }
        }
    }

    @Transactional
    public void handleStatus(
            String assignmentId,
            int machineId,
            String status,
            String message,
            String errorCode) {
        TradeOffer offer = requirePendingOffer(assignmentId, machineId);
        synchronized (offer) {
            if (!acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派尚未接受，不能上报执行状态");
            }
            if (PROGRESS_STATUSES.contains(status)) {
                persistProgress(assignmentId, status);
                return;
            }

            GameItemOrder order = orderService.getById(offer.orderId());
            Map<String, Object> ctx = terminalContext(offer, message);
            DeliveryEvent event;
            String assignmentStatus;
            String defaultErrorCode;

            switch (status) {
                case "completed", "wait_web_confirm" -> {
                    stateMachine.fire(order, DeliveryEvent.GAME_TRADE_COMPLETED, ctx);
                    clearActiveAssignment(assignmentId);
                    return;
                }
                case "retryable_failed", "start_rejected" -> {
                    event = DeliveryEvent.TRADE_RETRYABLE_FAILED;
                    assignmentStatus = "retryable_failed";
                    defaultErrorCode = "TRADE_RETRYABLE_FAILURE";
                }
                case "failed" -> {
                    event = DeliveryEvent.TRADE_FAILED;
                    assignmentStatus = "failed";
                    defaultErrorCode = "TRADE_EXECUTION_FAILED";
                }
                case "timed_out" -> {
                    event = DeliveryEvent.TRADE_TIMED_OUT;
                    assignmentStatus = "timed_out";
                    defaultErrorCode = "TRADE_REQUEST_TIMEOUT";
                }
                case "verification_failed" -> {
                    event = DeliveryEvent.TRADE_VERIFICATION_FAILED;
                    assignmentStatus = "verification_failed";
                    defaultErrorCode = "TRADE_RESULT_UNCERTAIN";
                }
                case "cancelled" -> {
                    event = DeliveryEvent.TRADE_CANCELLED;
                    assignmentStatus = "cancelled";
                    defaultErrorCode = "TRADE_CANCELLED";
                }
                default -> throw new IllegalStateException("不支持的交易状态: " + status);
            }
            ctx.put("assignmentStatus", assignmentStatus);
            ctx.put("errorCode", errorCode == null || errorCode.isBlank()
                    ? defaultErrorCode : errorCode);
            ctx.put("errorMessage", message);
            stateMachine.fire(order, event, ctx);
            clearActiveAssignment(assignmentId);
        }
    }

    /** 保存 Worker 上报的低置信客户名，并等待前端人工判断。 */
    @Transactional
    public void handleBuyerReview(
            String assignmentId,
            int machineId,
            String reviewId,
            String observedBuyer,
            double ocrConfidence,
            String screenshotDataUrl) {
        TradeOffer offer = requirePendingOffer(assignmentId, machineId);
        synchronized (offer) {
            if (!acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派尚未接受，不能请求买家审核");
            }
            if (reviewId == null || reviewId.isBlank() || reviewId.length() > 36) {
                throw new IllegalStateException("买家审核编号无效");
            }
            if (screenshotDataUrl == null
                    || !screenshotDataUrl.startsWith("data:image/png;base64,")
                    || screenshotDataUrl.length() > 1_800_000) {
                throw new IllegalStateException("买家审核截图无效或过大");
            }
            TradeAssignment assignment = assignmentService.getOne(
                    new LambdaQueryWrapper<TradeAssignment>()
                            .eq(TradeAssignment::getAssignmentId, assignmentId), false);
            if (assignment == null) {
                throw new IllegalStateException("交易指派记录不存在: " + assignmentId);
            }
            GameItemOrder order = orderService.getById(offer.orderId());
            assignment.setStatus("waiting_buyer_review");
            assignment.setBuyerReviewId(reviewId);
            assignment.setBuyerReviewStatus("pending");
            assignment.setExpectedBuyerName(order == null ? null : order.getBuyerCharacter());
            assignment.setObservedBuyerName(truncate(observedBuyer, 255));
            assignment.setBuyerOcrConfidence(ocrConfidence);
            assignment.setBuyerReviewScreenshot(screenshotDataUrl);
            assignment.setBuyerReviewRequestedAt(LocalDateTime.now());
            assignment.setBuyerReviewDecidedAt(null);
            if (assignment.getStartedAt() == null) {
                assignment.setStartedAt(LocalDateTime.now());
            }
            assignmentService.updateById(assignment);
        }
    }

    /** 保存最终确认按钮点击前的完整游戏截图。 */
    @Transactional
    public void handleGameTradeScreenshot(
            String assignmentId, int machineId, String screenshotDataUrl) {
        TradeOffer offer = requirePendingOffer(assignmentId, machineId);
        synchronized (offer) {
            if (!acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派尚未接受，不能保存交易截图");
            }
            if (screenshotDataUrl == null
                    || !screenshotDataUrl.startsWith("data:image/png;base64,")
                    || screenshotDataUrl.length() > 3_500_000) {
                throw new IllegalStateException("游戏交易截图无效或过大");
            }
            GameItemOrder order = orderService.getById(offer.orderId());
            if (order == null || !assignmentId.equals(order.getAssignmentId())) {
                throw new IllegalStateException("订单不存在或交易指派已失效");
            }
            order.setGameTradeScreenshot(screenshotDataUrl);
            order.setGameTradeScreenshotAt(LocalDateTime.now());
            orderService.updateById(order);
        }
    }

    /** 前端人工决定后，将结果发送给原 Worker；下发失败时保留 pending 供重试。 */
    @Transactional
    public TradeAssignment decideBuyerReview(
            Integer orderId, String reviewId, boolean approved) {
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getOrderId, orderId)
                        .eq(TradeAssignment::getBuyerReviewId, reviewId)
                        .eq(TradeAssignment::getBuyerReviewStatus, "pending"), false);
        if (assignment == null) {
            throw new IllegalStateException("审核请求不存在或已处理");
        }
        TradeOffer offer = requirePendingOffer(
                assignment.getAssignmentId(), assignment.getMachineId());
        synchronized (offer) {
            boolean claimed = assignmentService.update(new LambdaUpdateWrapper<TradeAssignment>()
                    .eq(TradeAssignment::getId, assignment.getId())
                    .eq(TradeAssignment::getBuyerReviewStatus, "pending")
                    .set(TradeAssignment::getBuyerReviewStatus, "decision_sending"));
            if (!claimed) {
                throw new IllegalStateException("审核请求已由其他页面处理");
            }
            if (!agentRegistry.sendTradeBuyerReviewDecision(
                    assignment.getMachineId(), assignment.getAssignmentId(), reviewId, approved)) {
                throw new IllegalStateException("交易 Worker 已离线，审核决定下发失败");
            }
            LocalDateTime decidedAt = LocalDateTime.now();
            String reviewStatus = approved ? "approved" : "rejected";
            assignmentService.update(new LambdaUpdateWrapper<TradeAssignment>()
                    .eq(TradeAssignment::getId, assignment.getId())
                    .eq(TradeAssignment::getBuyerReviewStatus, "decision_sending")
                    .set(TradeAssignment::getBuyerReviewStatus, reviewStatus)
                    .set(TradeAssignment::getBuyerReviewDecidedAt, decidedAt));
            assignment.setBuyerReviewStatus(reviewStatus);
            assignment.setBuyerReviewDecidedAt(decidedAt);
            return assignment;
        }
    }

    /** 定期回收未被 Worker 接受的过期 offer。 */
    @Scheduled(fixedDelayString = "${trade.offer-expiry-scan-ms:5000}")
    @Transactional
    public void expireOffers() {
        expireOffersAt(Instant.now());
    }

    void expireOffersAt(Instant now) {
        pendingOffers.values().stream()
                .filter(offer -> !acceptedAssignments.contains(offer.assignmentId()))
                .filter(offer -> !offer.leaseExpiresAt().isAfter(now))
                .toList()
                .forEach(offer -> {
                    synchronized (offer) {
                        if (pendingOffers.get(offer.assignmentId()) == offer
                                && !acceptedAssignments.contains(offer.assignmentId())) {
                            expireOffer(offer);
                        }
                    }
                });
    }

    /** 会话丢失后清除无法继续使用的明文令牌和内存指派。 */
    @EventListener
    public void discardLostMachineOffers(MachineSessionLost event) {
        pendingOffers.values().stream()
                .filter(offer -> offer.machineId() == event.machineId())
                .toList()
                .forEach(offer -> {
                    pendingOffers.remove(offer.assignmentId(), offer);
                    acceptedAssignments.remove(offer.assignmentId());
                    executionDeadlines.remove(offer.assignmentId());
                });
    }

    /** 回收 Worker 已接受但长时间未进入终态的交易。 */
    @Scheduled(fixedDelayString = "${trade.execution-watchdog-scan-ms:5000}")
    @Transactional
    public void expireExecutions() {
        expireExecutionsAt(Instant.now());
    }

    void expireExecutionsAt(Instant now) {
        executionDeadlines.entrySet().stream()
                .filter(entry -> !entry.getValue().isAfter(now))
                .toList()
                .forEach(entry -> {
                    String assignmentId = entry.getKey();
                    TradeOffer offer = pendingOffers.get(assignmentId);
                    if (offer == null) {
                        executionDeadlines.remove(assignmentId, entry.getValue());
                        return;
                    }
                    synchronized (offer) {
                        if (!acceptedAssignments.contains(assignmentId)
                                || !entry.getValue().equals(executionDeadlines.get(assignmentId))) {
                            return;
                        }
                        agentRegistry.sendTradeCancel(
                                offer.machineId(), assignmentId, "execution_watchdog_timeout");
                        GameItemOrder order = orderService.getById(offer.orderId());
                        Map<String, Object> ctx = terminalContext(
                                offer, "交易总执行时间超过限制，结果需要人工复核");
                        ctx.put("assignmentStatus", "watchdog_timed_out");
                        ctx.put("errorCode", "EXECUTION_WATCHDOG_TIMEOUT");
                        ctx.put("errorMessage", "execution watchdog timeout");
                        stateMachine.fire(order, DeliveryEvent.TRADE_VERIFICATION_FAILED, ctx);
                        clearActiveAssignment(assignmentId);
                    }
                });
    }

    private void rejectOffer(TradeOffer offer, String reason) {
        GameItemOrder order = orderService.getById(offer.orderId());
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", offer.assignmentId());
        ctx.put("machineId", offer.machineId());
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("reason", reason);
        ctx.put("message", reason);
        stateMachine.fire(order, DeliveryEvent.OFFER_REJECTED, ctx);
        pendingOffers.remove(offer.assignmentId());
        executionDeadlines.remove(offer.assignmentId());
    }

    private void expireOffer(TradeOffer offer) {
        GameItemOrder order = orderService.getById(offer.orderId());
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", offer.assignmentId());
        ctx.put("machineId", offer.machineId());
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("message", "Worker 未在租约内接受指派");
        stateMachine.fire(order, DeliveryEvent.OFFER_EXPIRED, ctx);
        pendingOffers.remove(offer.assignmentId(), offer);
        executionDeadlines.remove(offer.assignmentId());
    }

    private List<TradeCandidate> buildCandidates(GameItemOrder order) {
        List<GameAccount> accounts = gameAccountService
                .findIdleByGameAndRegion(order.getGameId(), order.getRegionId());
        if (accounts.isEmpty()) return List.of();

        List<Integer> accountIds = accounts.stream().map(GameAccount::getId).toList();
        // 账号与目标大区的绑定决定该机器是否可接单；客户端当前大区允许不同，
        // Worker 会在交易前根据订单中的目标大区完成切换。
        List<MachineGameAccount> machineGames = machineGameService
                .findByGameAccountIdsAndRegionIdActive(accountIds, order.getRegionId());
        Map<Integer, MachineGameAccount> mgByAccountId = new HashMap<>();
        Map<Integer, Integer> accountCountByMachine = new HashMap<>();
        for (MachineGameAccount mg : machineGames) {
            mgByAccountId.putIfAbsent(mg.getGameAccountId(), mg);
            accountCountByMachine.merge(mg.getMachineId(), 1, Integer::sum);
        }

        List<TradeCandidate> candidates = new ArrayList<>();
        for (GameAccount account : accounts) {
            MachineGameAccount mg = mgByAccountId.get(account.getId());
            if (mg == null) continue;
            int machineId = mg.getMachineId();
            if (!agentRegistry.isAgentGameExecutor(machineId)) continue;
            WorkerRuntimeStatus runtime = agentRegistry.getRuntimeStatus(machineId);
            if (runtime == null) continue;
            boolean runtimeIdentityUnknown = runtime.gameAccountId() == null && runtime.gameId() == null;
            boolean runtimeMatchesAccount = (runtimeIdentityUnknown
                    && accountCountByMachine.getOrDefault(machineId, 0) == 1)
                    || (account.getId().equals(runtime.gameAccountId())
                    && order.getGameId().equals(runtime.gameId()));
            candidates.add(new TradeCandidate(
                    machineId,
                    account.getId(),
                    order.getGameId(),
                    order.getRegionId(),
                    mg.getPriority(),
                    agentRegistry.isAgentOnline(machineId),
                    runtimeMatchesAccount && "idle".equals(account.getStatus()),
                    runtime.clientStatus(),
                    runtime.executorStatus(),
                    runtime.uiHealth(),
                    null));
        }
        return candidates;
    }

    private void persistAssignment(TradeOffer offer) {
        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId(offer.assignmentId());
        assignment.setOrderId(offer.orderId());
        assignment.setMachineId(offer.machineId());
        assignment.setGameAccountId(offer.gameAccountId());
        assignment.setStatus("offered");
        assignment.setTokenHash(sha256(offer.executionToken()));
        assignment.setLeaseExpiresAt(java.time.LocalDateTime.ofInstant(
                offer.leaseExpiresAt(), ZoneOffset.UTC));
        assignmentService.save(assignment);
    }

    private void reserveResources(int machineId, int gameAccountId) {
        Machine machine = machineService.getById(machineId);
        if (machine != null) {
            machine.setStatus("busy");
            machineService.updateById(machine);
        }
        GameAccount account = gameAccountService.getById(gameAccountId);
        if (account != null) {
            account.setStatus("in_use");
            gameAccountService.updateById(account);
        }
    }

    private TradeOffer requirePendingOffer(String assignmentId, int machineId) {
        TradeOffer offer = pendingOffers.get(assignmentId);
        if (offer == null || offer.machineId() != machineId) {
            throw new IllegalStateException("指派不存在、已过期或机器不匹配");
        }
        return offer;
    }

    private void persistProgress(String assignmentId, String status) {
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment == null) {
            throw new IllegalStateException("交易指派记录不存在: " + assignmentId);
        }
        assignment.setStatus(status);
        if (assignment.getStartedAt() == null) {
            assignment.setStartedAt(LocalDateTime.now());
        }
        assignmentService.updateById(assignment);
    }

    private Map<String, Object> terminalContext(TradeOffer offer, String message) {
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", offer.assignmentId());
        ctx.put("machineId", offer.machineId());
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("message", message);
        return ctx;
    }

    private void clearActiveAssignment(String assignmentId) {
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment != null && "pending".equals(assignment.getBuyerReviewStatus())) {
            assignment.setBuyerReviewStatus("expired");
            assignment.setBuyerReviewDecidedAt(LocalDateTime.now());
            assignmentService.updateById(assignment);
        }
        pendingOffers.remove(assignmentId);
        acceptedAssignments.remove(assignmentId);
        executionDeadlines.remove(assignmentId);
    }

    private int executionTimeoutSeconds(TradeOffer offer) {
        Object raw = offer.orderPayload().get("trade_timeout_seconds");
        int waitingSeconds = raw instanceof Number number ? number.intValue() : 300;
        waitingSeconds = Math.max(30, Math.min(7200, waitingSeconds));
        return waitingSeconds + EXECUTION_WATCHDOG_GRACE_SECONDS;
    }

    private Map<String, Object> orderPayload(GameItemOrder order, Game game, int gameAccountId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("order_id", order.getId());
        payload.put("game_id", order.getGameId());
        payload.put("game_code", game.getCode());
        payload.put("game_account_id", gameAccountId);
        payload.put("trade_timeout_seconds",
                game.getTradeTimeoutSeconds() != null ? game.getTradeTimeoutSeconds() : 300);
        payload.put("region_id", order.getRegionId());
        GameRegion region = gameRegionService.getById(order.getRegionId());
        if (region != null) {
            appendRegionNavigationPayload(payload, region);
        }
        payload.put("buyer_character", order.getBuyerCharacter());
        payload.put("asset_type", order.getAssetType());
        payload.put("asset_amount", order.getAssetAmount());
        payload.put("trade_type", "script");

        // 子订单明细
        List<Map<String, Object>> details = new ArrayList<>();
        List<Map<String, Object>> positions = new ArrayList<>();
        for (GameItemOrderDetail d : detailService.findByOrderId(order.getId())) {
            Map<String, Object> detail = new LinkedHashMap<>();
            detail.put("item_id", d.getItemId());
            detail.put("item_name", d.getItemName());
            detail.put("quantity", d.getQuantity());
            detail.put("item_image", d.getItemImage());
            details.add(detail);

            // 物品在游戏中的位置坐标
            if (d.getItemId() != null) {
                GameItem item = itemService.getById(d.getItemId());
                if (item != null && item.getPosition() != null && !item.getPosition().isBlank()) {
                    String[] parts = item.getPosition().trim().split("\\s*,\\s*");
                    if (parts.length == 2) {
                        try {
                            Map<String, Object> pos = new LinkedHashMap<>();
                            pos.put("item_id", d.getItemId());
                            pos.put("x", Integer.parseInt(parts[0]));
                            pos.put("y", Integer.parseInt(parts[1]));
                            pos.put("image_url", item.getImage());
                            positions.add(pos);
                        } catch (NumberFormatException ignored) {
                            // 位置格式不合法则跳过
                        }
                    }
                }
            }
        }
        payload.put("details", details);
        payload.put("item_positions", positions);
        return payload;
    }

    static void appendRegionNavigationPayload(Map<String, Object> payload, GameRegion region) {
        payload.put("region_name", region.getName());
        payload.put("region_code", region.getCode());
        payload.put("region_sort_order", region.getSortOrder());
        payload.put("region_select_x", region.getSelectX());
        payload.put("region_select_y", region.getSelectY());
    }

    private String newExecutionToken() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private static String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }
}
