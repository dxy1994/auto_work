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
import com.auto.trade.statemachine.actions.ResourceHelper;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.context.event.EventListener;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
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
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/** 总控交易选机、预占以及 offer/start 两阶段协调器。 */
@Service
@Slf4j
public class TradeDispatchCoordinator {

    private static final int OFFER_LEASE_SECONDS = 30;
    /** 包含按业务分级的画面等待、三次视觉检测以及多物品拖拽时间。 */
    private static final int EXECUTION_WATCHDOG_GRACE_SECONDS = 600;
    private static final Set<String> PROGRESS_STATUSES = Set.of(
            "started", "preparing", "switching_region", "waiting_buyer",
            "waiting_buyer_review", "trading", "verifying");
    private static final Set<String> ACTIVE_ASSIGNMENT_STATUSES = Set.of(
            "offered", "accepted", "started", "preparing", "switching_region",
            "waiting_buyer", "waiting_buyer_review", "trading", "verifying");

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
    private final ManualOrderStatusService manualOrderStatusService;
    private final TransactionTemplate committedTransaction;
    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, TradeOffer> pendingOffers = new ConcurrentHashMap<>();
    private final Set<String> acceptedAssignments = ConcurrentHashMap.newKeySet();
    private final Map<String, Instant> executionDeadlines = new ConcurrentHashMap<>();
    private final Map<Integer, Object> machineQueueLocks = new ConcurrentHashMap<>();
    /** 单后端实例内串行化“选择 + 预占”，避免两个订单同时拿到同一台空闲机器。 */
    private final Object dispatchLock = new Object();

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
            GameRegionService gameRegionService,
            ManualOrderStatusService manualOrderStatusService,
            PlatformTransactionManager transactionManager) {
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
        this.manualOrderStatusService = manualOrderStatusService;
        this.committedTransaction = new TransactionTemplate(transactionManager);
        this.committedTransaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    public TradeOffer dispatch(Integer orderId) {
        // 必须先提交 offered 状态和资源预占，再向 Worker 发送 offer。
        // Worker 的 WebSocket 回执可能在 sendTradeOffer 返回前就到达；如果仍处于同一事务，
        // 回执线程只能读到旧状态，从而把合法的 OFFER_ACCEPTED 判定为非法转换。
        TradeOffer offer;
        synchronized (dispatchLock) {
            offer = committedTransaction.execute(status -> prepareOffer(orderId));
        }
        // null 表示订单已经持久化进入目标机器队列，并非指派失败。
        if (offer == null) {
            return null;
        }
        pendingOffers.put(offer.assignmentId(), offer);

        if (!agentRegistry.sendTradeOffer(offer.machineId(), offer)) {
            try {
                committedTransaction.executeWithoutResult(status ->
                        rejectOffer(offer, "交易指派发送失败"));
            } catch (RuntimeException cleanupError) {
                pendingOffers.remove(offer.assignmentId(), offer);
                log.error("[Trade] 发送指派失败后的资源释放也失败 assignment_id={}: {}",
                        offer.assignmentId(), cleanupError.getMessage(), cleanupError);
            }
            triggerNextQueuedOrder(offer.machineId());
            throw new IllegalStateException("发送交易指派失败");
        }
        return offer;
    }

    private TradeOffer prepareOffer(Integer orderId) {
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

        CandidatePool candidatePool = buildCandidatePool(order);
        Optional<TradeCandidate> selected = selector.select(
                order.getGameId(), order.getRegionId(), candidatePool.candidates());
        if (selected.isEmpty()) {
            QueueTarget queueTarget = findQueueTarget(order);
            if (queueTarget == null) {
                throw new IllegalStateException(noCandidateMessage(order, candidatePool));
            }
            Map<String, Object> queueContext = new HashMap<>();
            queueContext.put("machineId", queueTarget.machineId());
            queueContext.put("gameAccountId", queueTarget.gameAccountId());
            queueContext.put("message", "交易机器忙碌，订单进入机器 FIFO 队列");
            stateMachine.fire(order, DeliveryEvent.QUEUE_ASSIGNMENT, queueContext);
            log.info("[TradeQueue] 订单进入队列 order_id={} machine_id={} game_account_id={} queue_depth={}",
                    orderId, queueTarget.machineId(), queueTarget.gameAccountId(), queueTarget.queueDepth() + 1);
            return null;
        }
        return createOffer(order, game, selected.get(), event, "总控发送交易指派");
    }

    private TradeOffer createOffer(GameItemOrder order, Game game, TradeCandidate candidate,
                                   DeliveryEvent event, String message) {
        String assignmentId = UUID.randomUUID().toString();
        String token = newExecutionToken();
        Instant leaseExpiresAt = Instant.now().plusSeconds(OFFER_LEASE_SECONDS);
        TradeOffer offer = new TradeOffer(
                assignmentId,
                order.getId(),
                candidate.machineId(),
                candidate.gameAccountId(),
                token,
                leaseExpiresAt,
                orderPayload(order, game, candidate.gameAccountId()));

        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", assignmentId);
        ctx.put("machineId", candidate.machineId());
        ctx.put("gameAccountId", candidate.gameAccountId());
        ctx.put("message", message);
        order.setAssignmentId(assignmentId);
        stateMachine.fire(order, event, ctx);
        persistAssignment(offer);
        reserveResources(candidate.machineId(), candidate.gameAccountId());
        return offer;
    }

    /** 人工完成排队中或自动交易中的订单；活动 Worker 会先收到停止指令。 */
    public GameItemOrder completeOrderManually(Integer orderId) {
        return terminateOrderManually(orderId, true);
    }

    /** 人工取消排队中或自动交易中的订单；活动 Worker 会先收到停止指令。 */
    public GameItemOrder cancelOrderManually(Integer orderId) {
        return terminateOrderManually(orderId, false);
    }

    private GameItemOrder terminateOrderManually(Integer orderId, boolean completed) {
        GameItemOrder snapshot = orderService.getById(orderId);
        if (snapshot == null) {
            throw new IllegalArgumentException("订单不存在");
        }
        if (!Set.of("queued", "offered", "assigned").contains(snapshot.getDeliveryStatus())) {
            throw new IllegalStateException("当前订单不在排队或自动交易状态");
        }

        ManualTermination result;
        TradeOffer activeOffer = snapshot.getAssignmentId() == null
                ? null : pendingOffers.get(snapshot.getAssignmentId());
        if ("queued".equals(snapshot.getDeliveryStatus())) {
            // 与队首出队使用同一把锁，确保取消/完成和下发只会有一个成功。
            synchronized (dispatchLock) {
                result = performManualTermination(orderId, completed);
            }
        } else if (activeOffer != null) {
            // 与 Worker 决策和状态回报串行，保证停止指令不会与 trade_start 交叉。
            synchronized (activeOffer) {
                result = performManualTermination(orderId, completed);
            }
        } else {
            result = performManualTermination(orderId, completed);
        }

        if (result.assignmentId() != null) {
            clearActiveAssignment(result.assignmentId());
        }
        if (result.machineId() != null) {
            triggerNextQueuedOrder(result.machineId());
        }
        return result.order();
    }

    private ManualTermination performManualTermination(Integer orderId, boolean completed) {
        GameItemOrder current = orderService.getById(orderId);
        if (current == null) {
            throw new IllegalArgumentException("订单不存在");
        }
        if (!Set.of("queued", "offered", "assigned").contains(current.getDeliveryStatus())) {
            if ("completed".equals(current.getStatus()) || "cancelled".equals(current.getStatus())) {
                return new ManualTermination(current, current.getAssignedMachineId(), current.getAssignmentId());
            }
            throw new IllegalStateException("当前订单不在排队或自动交易状态");
        }

        TradeAssignment activeAssignment = findAssignment(current.getAssignmentId());
        Integer wakeMachineId = activeAssignment == null
                ? current.getAssignedMachineId() : activeAssignment.getMachineId();
        String assignmentId = current.getAssignmentId();
        if (assignmentId != null && wakeMachineId != null) {
            boolean sent = agentRegistry.sendTradeCancel(
                    wakeMachineId, assignmentId, completed ? "manual_complete" : "manual_cancel");
            log.info("[TradeQueue] 人工{}订单，停止指令{} order_id={} assignment_id={} machine_id={}",
                    completed ? "完成" : "取消", sent ? "已发送" : "未送达",
                    orderId, assignmentId, wakeMachineId);
        }

        GameItemOrder terminal = committedTransaction.execute(status -> {
            GameItemOrder latest = orderService.getById(orderId);
            if (latest == null) {
                throw new IllegalArgumentException("订单不存在");
            }
            if ("completed".equals(latest.getStatus()) || "cancelled".equals(latest.getStatus())) {
                return latest;
            }

            TradeAssignment assignment = findAssignment(latest.getAssignmentId());
            if (assignment != null) {
                assignment.setStatus(completed ? "manually_completed" : "manually_cancelled");
                assignment.setRejectReason(completed ? "manual_complete" : "manual_cancel");
                assignment.setFinishedAt(LocalDateTime.now());
                assignmentService.updateById(assignment);
            }
            // queued 仅绑定队列目标，并未预占资源，不能把正在执行首单的账号错误释放。
            if (!"queued".equals(latest.getDeliveryStatus())
                    && assignment != null
                    && assignment.getMachineId() != null
                    && assignment.getGameAccountId() != null) {
                ResourceHelper.release(machineService, gameAccountService, agentRegistry,
                        assignment.getMachineId(), assignment.getGameAccountId());
            }
            return completed
                    ? manualOrderStatusService.completeAfterAutomationStopped(orderId)
                    : manualOrderStatusService.cancelAfterAutomationStopped(orderId);
        });
        return new ManualTermination(terminal, wakeMachineId, assignmentId);
    }

    private record ManualTermination(GameItemOrder order, Integer machineId, String assignmentId) {
    }

    private TradeAssignment findAssignment(String assignmentId) {
        if (assignmentId == null || assignmentId.isBlank()) {
            return null;
        }
        return assignmentService.getOne(new LambdaQueryWrapper<TradeAssignment>()
                .eq(TradeAssignment::getAssignmentId, assignmentId), false);
    }

    public void handleDecision(
            String assignmentId,
            int machineId,
            boolean accepted,
            String reason) {
        TradeOffer offer = pendingOffers.get(assignmentId);
        if (offer == null) {
            TradeAssignment assignment = findAssignment(assignmentId);
            if (assignment != null && Set.of("manually_completed", "manually_cancelled")
                    .contains(assignment.getStatus())) {
                log.info("[Trade] 忽略人工终结后的 offer 决策 assignment_id={}", assignmentId);
                return;
            }
            throw new IllegalStateException("指派不存在、已过期或机器不匹配");
        }
        if (offer.machineId() != machineId) {
            throw new IllegalStateException("指派不存在、已过期或机器不匹配");
        }
        synchronized (offer) {
            GameItemOrder decisionOrder = orderService.getById(offer.orderId());
            if (decisionOrder == null
                    || !"offered".equals(decisionOrder.getDeliveryStatus())
                    || !assignmentId.equals(decisionOrder.getAssignmentId())) {
                log.info("[Trade] 忽略已经人工终结的 offer 决策 assignment_id={}", assignmentId);
                clearActiveAssignment(assignmentId);
                return;
            }
            boolean queuedOrigin = isQueuedOffer(offer);
            if (acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派已接受，不能重复决策");
            }
            if (offer.leaseExpiresAt().isBefore(Instant.now())) {
                boolean returnedToQueue = committedTransaction.execute(status -> expireOffer(offer));
                if (!returnedToQueue) {
                    triggerNextQueuedOrder(machineId);
                }
                throw new IllegalStateException("指派租约已过期");
            }
            if (!accepted) {
                boolean returnedToQueue = committedTransaction.execute(status ->
                        rejectOffer(offer, reason == null ? "worker_rejected" : reason));
                if (!returnedToQueue) {
                    triggerNextQueuedOrder(machineId);
                }
                return;
            }

            // 先提交 offered → assigned，再发送 trade_start；这样 Worker 即时上报状态时
            // 一定能够从数据库读到 ASSIGNED。
            committedTransaction.executeWithoutResult(status -> {
                GameItemOrder order = orderService.getById(offer.orderId());
                Map<String, Object> ctx = new HashMap<>();
                ctx.put("assignmentId", assignmentId);
                ctx.put("machineId", machineId);
                ctx.put("gameAccountId", offer.gameAccountId());
                ctx.put("message", "Worker 接受交易指派");
                stateMachine.fire(order, DeliveryEvent.OFFER_ACCEPTED, ctx);
            });
            acceptedAssignments.add(assignmentId);
            executionDeadlines.put(
                    assignmentId,
                    Instant.now().plusSeconds(executionTimeoutSeconds(offer)));

            if (!agentRegistry.sendTradeStart(machineId, assignmentId, offer.executionToken())) {
                // 启动指令未下发到 Worker，可安全重新指派。
                committedTransaction.executeWithoutResult(status -> {
                    GameItemOrder order = orderService.getById(offer.orderId());
                    Map<String, Object> failCtx = new HashMap<>();
                    failCtx.put("assignmentId", assignmentId);
                    failCtx.put("machineId", machineId);
                    failCtx.put("gameAccountId", offer.gameAccountId());
                    failCtx.put("message", "发送交易启动指令失败");
                    if (!queuedOrigin) {
                        failCtx.put("errorCode", "START_DISPATCH_FAILED");
                        failCtx.put("errorMessage", "发送交易启动指令失败");
                    }
                    stateMachine.fire(order, queuedOrigin
                            ? DeliveryEvent.QUEUED_START_FAILED
                            : DeliveryEvent.START_FAILED, failCtx);
                });
                acceptedAssignments.remove(assignmentId);
                pendingOffers.remove(assignmentId);
                executionDeadlines.remove(assignmentId);
                if (!queuedOrigin) {
                    triggerNextQueuedOrder(machineId);
                }
                throw new IllegalStateException("发送交易启动指令失败");
            }
        }
    }

    public void handleStatus(
            String assignmentId,
            int machineId,
            String status,
            String message,
            String errorCode) {
        TradeOffer offer = pendingOffers.get(assignmentId);
        if (offer == null) {
            TradeAssignment assignment = findAssignment(assignmentId);
            if (assignment != null && Set.of("manually_completed", "manually_cancelled")
                    .contains(assignment.getStatus())) {
                log.info("[Trade] 忽略人工终结后的 Worker 回报 assignment_id={} status={}",
                        assignmentId, status);
                return;
            }
            throw new IllegalStateException("指派不存在、已过期或机器不匹配");
        }
        if (offer.machineId() != machineId) {
            throw new IllegalStateException("指派不存在、已过期或机器不匹配");
        }
        synchronized (offer) {
            if (!acceptedAssignments.contains(assignmentId)) {
                throw new IllegalStateException("指派尚未接受，不能上报执行状态");
            }
            GameItemOrder latest = orderService.getById(offer.orderId());
            if (latest == null
                    || !"assigned".equals(latest.getDeliveryStatus())
                    || !assignmentId.equals(latest.getAssignmentId())) {
                log.info("[Trade] 忽略已经人工终结的任务回报 assignment_id={} status={}",
                        assignmentId, status);
                clearActiveAssignment(assignmentId);
                return;
            }
            if (PROGRESS_STATUSES.contains(status)) {
                committedTransaction.executeWithoutResult(tx -> persistProgress(assignmentId, status));
                return;
            }

            Map<String, Object> ctx = terminalContext(offer, message);
            DeliveryEvent event;
            String assignmentStatus;
            String defaultErrorCode;

            switch (status) {
                case "completed", "wait_web_confirm" -> {
                    committedTransaction.executeWithoutResult(tx -> {
                        GameItemOrder order = orderService.getById(offer.orderId());
                        if (order != null && "assigned".equals(order.getDeliveryStatus())) {
                            stateMachine.fire(order, DeliveryEvent.GAME_TRADE_COMPLETED, ctx);
                        }
                    });
                    clearActiveAssignment(assignmentId);
                    triggerNextQueuedOrder(machineId);
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
            committedTransaction.executeWithoutResult(tx -> {
                GameItemOrder order = orderService.getById(offer.orderId());
                if (order != null && "assigned".equals(order.getDeliveryStatus())) {
                    stateMachine.fire(order, event, ctx);
                }
            });
            clearActiveAssignment(assignmentId);
            triggerNextQueuedOrder(machineId);
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

    /** 定时兜底扫描持久化队列；后端重启或 Worker 心跳稍晚时也不会遗失后续订单。 */
    @Scheduled(fixedDelayString = "${trade.queue-scan-ms:5000}")
    public void dispatchQueuedOrders() {
        List<Integer> machineIds = orderService.list(
                        new LambdaQueryWrapper<GameItemOrder>()
                                .select(GameItemOrder::getAssignedMachineId)
                                .eq(GameItemOrder::getDeliveryStatus, "queued")
                                .eq(GameItemOrder::getStatus, "pending")
                                .isNotNull(GameItemOrder::getAssignedMachineId)
                                .orderByAsc(GameItemOrder::getCreatedAt)
                                .orderByAsc(GameItemOrder::getId))
                .stream()
                .map(GameItemOrder::getAssignedMachineId)
                .distinct()
                .toList();
        for (Integer machineId : machineIds) {
            triggerNextQueuedOrder(machineId);
        }
    }

    /** 资源释放后主动唤醒该机器最早进入队列且仍为 pending/queued 的订单。 */
    public void triggerNextQueuedOrder(int machineId) {
        Object queueLock = machineQueueLocks.computeIfAbsent(machineId, ignored -> new Object());
        synchronized (queueLock) {
            GameItemOrder queued = orderService.getOne(
                    new LambdaQueryWrapper<GameItemOrder>()
                            .eq(GameItemOrder::getDeliveryStatus, "queued")
                            .eq(GameItemOrder::getStatus, "pending")
                            .eq(GameItemOrder::getAssignedMachineId, machineId)
                            .orderByAsc(GameItemOrder::getCreatedAt)
                            .orderByAsc(GameItemOrder::getId)
                            .last("LIMIT 1"), false);
            if (queued == null) {
                return;
            }

            TradeOffer offer;
            synchronized (dispatchLock) {
                offer = committedTransaction.execute(status ->
                        prepareQueuedOffer(queued.getId(), machineId));
            }
            // Worker 的完成消息可能早于 idle 心跳；保持排队，下一次扫描继续检查。
            if (offer == null) {
                return;
            }

            pendingOffers.put(offer.assignmentId(), offer);
            if (!agentRegistry.sendTradeOffer(machineId, offer)) {
                committedTransaction.executeWithoutResult(status ->
                        returnQueuedOffer(offer, DeliveryEvent.QUEUED_OFFER_REJECTED,
                                "队首交易指派发送失败"));
                pendingOffers.remove(offer.assignmentId(), offer);
                executionDeadlines.remove(offer.assignmentId());
                log.warn("[TradeQueue] 队首指派发送失败，保留排队 order_id={} machine_id={}",
                        offer.orderId(), machineId);
                return;
            }
            log.info("[TradeQueue] 队首订单已主动指派 order_id={} assignment_id={} machine_id={}",
                    offer.orderId(), offer.assignmentId(), machineId);
        }
    }

    private TradeOffer prepareQueuedOffer(int orderId, int machineId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null
                || !"queued".equals(order.getDeliveryStatus())
                || !"pending".equals(order.getStatus())
                || !Integer.valueOf(machineId).equals(order.getAssignedMachineId())
                || order.getGameAccountId() == null) {
            return null;
        }

        Game game = gameService.getById(order.getGameId());
        if (game == null || !"script".equals(game.getTradeType())) {
            return null;
        }
        CandidatePool pool = buildCandidatePool(order);
        List<TradeCandidate> targetCandidates = pool.candidates().stream()
                .filter(candidate -> candidate.machineId() == machineId)
                .filter(candidate -> candidate.gameAccountId() == order.getGameAccountId())
                .toList();
        Optional<TradeCandidate> candidate = selector.select(
                order.getGameId(), order.getRegionId(), targetCandidates);
        if (candidate.isEmpty()) {
            return null;
        }
        return createOffer(order, game, candidate.get(), DeliveryEvent.DEQUEUE_ASSIGNMENT,
                "机器空闲，FIFO 队首订单开始交易指派");
    }

    private void returnQueuedOffer(TradeOffer offer, DeliveryEvent event, String reason) {
        GameItemOrder order = orderService.getById(offer.orderId());
        if (order == null || !"offered".equals(order.getDeliveryStatus())) {
            return;
        }
        Map<String, Object> ctx = terminalContext(offer, reason);
        ctx.put("reason", reason);
        ctx.put("assignmentStatus", "queue_retry");
        stateMachine.fire(order, event, ctx);
        pendingOffers.remove(offer.assignmentId(), offer);
        acceptedAssignments.remove(offer.assignmentId());
        executionDeadlines.remove(offer.assignmentId());
    }

    /** 定期回收未被 Worker 接受的过期 offer。 */
    @Scheduled(fixedDelayString = "${trade.offer-expiry-scan-ms:5000}")
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
                            boolean returnedToQueue = committedTransaction.execute(
                                    status -> expireOffer(offer));
                            if (!returnedToQueue) {
                                triggerNextQueuedOrder(offer.machineId());
                            }
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
                        Map<String, Object> ctx = terminalContext(
                                offer, "交易总执行时间超过限制，结果需要人工复核");
                        ctx.put("assignmentStatus", "watchdog_timed_out");
                        ctx.put("errorCode", "EXECUTION_WATCHDOG_TIMEOUT");
                        ctx.put("errorMessage", "execution watchdog timeout");
                        committedTransaction.executeWithoutResult(status -> {
                            GameItemOrder order = orderService.getById(offer.orderId());
                            if (order != null && "assigned".equals(order.getDeliveryStatus())) {
                                stateMachine.fire(order, DeliveryEvent.TRADE_VERIFICATION_FAILED, ctx);
                            }
                        });
                        clearActiveAssignment(assignmentId);
                        triggerNextQueuedOrder(offer.machineId());
                    }
                });
    }

    private boolean rejectOffer(TradeOffer offer, String reason) {
        GameItemOrder order = orderService.getById(offer.orderId());
        if (order == null || !"offered".equals(order.getDeliveryStatus())) {
            pendingOffers.remove(offer.assignmentId(), offer);
            return false;
        }
        boolean queuedOrigin = isQueuedOffer(order, offer);
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", offer.assignmentId());
        ctx.put("machineId", offer.machineId());
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("reason", reason);
        ctx.put("message", reason);
        stateMachine.fire(order, queuedOrigin
                ? DeliveryEvent.QUEUED_OFFER_REJECTED
                : DeliveryEvent.OFFER_REJECTED, ctx);
        pendingOffers.remove(offer.assignmentId());
        executionDeadlines.remove(offer.assignmentId());
        return queuedOrigin;
    }

    private boolean expireOffer(TradeOffer offer) {
        GameItemOrder order = orderService.getById(offer.orderId());
        if (order == null || !"offered".equals(order.getDeliveryStatus())) {
            pendingOffers.remove(offer.assignmentId(), offer);
            return false;
        }
        boolean queuedOrigin = isQueuedOffer(order, offer);
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", offer.assignmentId());
        ctx.put("machineId", offer.machineId());
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("message", "Worker 未在租约内接受指派");
        stateMachine.fire(order, queuedOrigin
                ? DeliveryEvent.QUEUED_OFFER_EXPIRED
                : DeliveryEvent.OFFER_EXPIRED, ctx);
        pendingOffers.remove(offer.assignmentId(), offer);
        executionDeadlines.remove(offer.assignmentId());
        return queuedOrigin;
    }

    private boolean isQueuedOffer(TradeOffer offer) {
        return isQueuedOffer(orderService.getById(offer.orderId()), offer);
    }

    private static boolean isQueuedOffer(GameItemOrder order, TradeOffer offer) {
        return order != null
                && order.getAssignedAt() == null
                && Integer.valueOf(offer.machineId()).equals(order.getAssignedMachineId())
                && Integer.valueOf(offer.gameAccountId()).equals(order.getGameAccountId());
    }

    private CandidatePool buildCandidatePool(GameItemOrder order) {
        List<String> blockers = new ArrayList<>();
        List<GameAccount> accounts = gameAccountService
                .findIdleByGameAndRegion(order.getGameId(), order.getRegionId());
        if (accounts.isEmpty()) {
            blockers.add("游戏#" + order.getGameId() + "/大区#" + order.getRegionId()
                    + "没有已启用、空闲且关联该大区的游戏账号");
            return new CandidatePool(List.of(), blockers);
        }

        List<Integer> accountIds = accounts.stream().map(GameAccount::getId).toList();
        // 账号是否支持目标大区已由 findIdleByGameAndRegion 通过 game_account_regions 筛选；
        // 机器只需关联账号，Worker 会在交易前根据订单中的目标大区完成切换。
        List<MachineGameAccount> machineGames = machineGameService
                .findByGameAccountIdsActive(accountIds);
        Map<Integer, MachineGameAccount> mgByAccountId = new HashMap<>();
        Map<Integer, Integer> accountCountByMachine = new HashMap<>();
        for (MachineGameAccount mg : machineGames) {
            mgByAccountId.putIfAbsent(mg.getGameAccountId(), mg);
            accountCountByMachine.merge(mg.getMachineId(), 1, Integer::sum);
        }

        List<TradeCandidate> candidates = new ArrayList<>();
        for (GameAccount account : accounts) {
            MachineGameAccount mg = mgByAccountId.get(account.getId());
            if (mg == null) {
                blockers.add("游戏账号#" + account.getId() + "未绑定启用的游戏执行机器");
                continue;
            }
            int machineId = mg.getMachineId();
            if (!agentRegistry.isAgentGameExecutor(machineId)) {
                blockers.add(agentRegistry.isAgentOnline(machineId)
                        ? "机器#" + machineId + "在线，但连接角色不是游戏执行端"
                        : "机器#" + machineId + "的游戏执行Worker未在线");
                continue;
            }
            WorkerRuntimeStatus runtime = agentRegistry.getRuntimeStatus(machineId);
            if (runtime == null) {
                // Worker 刚注册时首个心跳可能尚未到达；执行端已经在线且只绑定一个
                // 候选账号时可以先接收 offer，后续脚本会自行激活并修复游戏窗口。
                boolean singleAccount = accountCountByMachine.getOrDefault(machineId, 0) == 1;
                candidates.add(new TradeCandidate(
                        machineId,
                        account.getId(),
                        order.getGameId(),
                        order.getRegionId(),
                        mg.getPriority(),
                        agentRegistry.isAgentOnline(machineId),
                        "idle".equals(account.getStatus()),
                        singleAccount,
                        "starting",
                        "idle",
                        "starting",
                        null));
                continue;
            }
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
                    "idle".equals(account.getStatus()),
                    runtimeMatchesAccount,
                    runtime.clientStatus(),
                    runtime.executorStatus(),
                    runtime.uiHealth(),
                    null));
        }
        return new CandidatePool(candidates, blockers);
    }

    /**
     * 仅在兼容账号确实存在活动指派时选择排队目标。普通离线、配置错误或健康检查失败
     * 不会被伪装成“排队中”，仍按没有合格机器处理。
     */
    private QueueTarget findQueueTarget(GameItemOrder order) {
        List<GameAccount> accounts = gameAccountService
                .findActiveByGameAndRegion(order.getGameId(), order.getRegionId());
        if (accounts.isEmpty()) {
            return null;
        }
        List<Integer> accountIds = accounts.stream().map(GameAccount::getId).toList();
        List<MachineGameAccount> bindings = machineGameService.findByGameAccountIdsActive(accountIds);
        if (bindings.isEmpty()) {
            return null;
        }

        Set<String> activeResources = new HashSet<>();
        for (TradeAssignment assignment : assignmentService.findByStatuses(ACTIVE_ASSIGNMENT_STATUSES)) {
            activeResources.add(resourceKey(assignment.getMachineId(), assignment.getGameAccountId()));
        }

        return bindings.stream()
                .filter(binding -> activeResources.contains(
                        resourceKey(binding.getMachineId(), binding.getGameAccountId())))
                .filter(binding -> agentRegistry.isAgentGameExecutor(binding.getMachineId()))
                .filter(binding -> agentRegistry.isAgentOnline(binding.getMachineId()))
                .map(binding -> new QueueTarget(
                        binding.getMachineId(),
                        binding.getGameAccountId(),
                        binding.getPriority() == null ? 0 : binding.getPriority(),
                        queueDepth(binding.getMachineId())))
                .min(Comparator.comparingLong(QueueTarget::queueDepth)
                        .thenComparing(Comparator.comparingInt(QueueTarget::priority).reversed())
                        .thenComparingInt(QueueTarget::machineId))
                .orElse(null);
    }

    private long queueDepth(int machineId) {
        return orderService.count(new LambdaQueryWrapper<GameItemOrder>()
                .eq(GameItemOrder::getDeliveryStatus, "queued")
                .eq(GameItemOrder::getAssignedMachineId, machineId));
    }

    private static String resourceKey(Integer machineId, Integer gameAccountId) {
        return String.valueOf(machineId) + ":" + gameAccountId;
    }

    private String noCandidateMessage(GameItemOrder order, CandidatePool pool) {
        List<String> reasons = new ArrayList<>(pool.blockers());
        reasons.addAll(selector.rejectionReasons(
                order.getGameId(), order.getRegionId(), pool.candidates()));
        if (reasons.isEmpty()) {
            return "没有符合条件的交易机器，且未获得可诊断的候选状态";
        }
        String detail = reasons.stream().limit(8).collect(java.util.stream.Collectors.joining("；"));
        return "没有符合条件的交易机器：" + truncate(detail, 800);
    }

    private record CandidatePool(List<TradeCandidate> candidates, List<String> blockers) {
    }

    private record QueueTarget(int machineId, int gameAccountId, int priority, long queueDepth) {
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
        int waitingSeconds = raw instanceof Number number ? number.intValue() : 600;
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
                game.getTradeTimeoutSeconds() != null ? game.getTradeTimeoutSeconds() : 600);
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
            detail.put("item_selected_image", d.getItemSelectedImage());
            GameItem item = d.getItemId() != null ? itemService.getById(d.getItemId()) : null;
            appendItemRecognitionImage(detail, item, d);
            details.add(detail);

            // 旧版执行器仍可读取位置坐标；新版以识别图为准。
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
        payload.put("details", details);
        payload.put("item_positions", positions);
        return payload;
    }

    static void appendRegionNavigationPayload(Map<String, Object> payload, GameRegion region) {
        payload.put("region_name", region.getName());
        payload.put("region_code", region.getCode());
        payload.put("region_sort_order", region.getSortOrder());
        payload.put("region_select_page", region.getSelectPage() != null ? region.getSelectPage() : 1);
        payload.put("region_select_x", region.getSelectX());
        payload.put("region_select_y", region.getSelectY());
    }

    static void appendItemRecognitionImage(
            Map<String, Object> detail,
            GameItem currentItem,
            GameItemOrderDetail orderDetail) {
        String unselected = currentItem != null ? currentItem.getImage() : null;
        String selected = currentItem != null ? currentItem.getSelectedImage() : null;
        if (unselected == null || unselected.isBlank()) {
            unselected = orderDetail.getItemImage();
        }
        if (selected == null || selected.isBlank()) {
            selected = orderDetail.getItemSelectedImage();
        }
        unselected = unselected == null || unselected.isBlank() ? null : unselected.trim();
        selected = selected == null || selected.isBlank() ? null : selected.trim();
        detail.put("recognition_image_url", unselected); // 兼容升级中的旧 Worker
        detail.put("recognition_image_unselected_url", unselected);
        detail.put("recognition_image_selected_url", selected);
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
