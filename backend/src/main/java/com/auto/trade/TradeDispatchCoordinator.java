package com.auto.trade;

import com.auto.entity.GameAccount;
import com.auto.entity.GameItemOrder;
import com.auto.entity.Machine;
import com.auto.entity.MachineGame;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.MachineGameService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.scheduling.annotation.Scheduled;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
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

    private final GameItemOrderService orderService;
    private final MachineGameService machineGameService;
    private final GameAccountService gameAccountService;
    private final MachineService machineService;
    private final TradeAssignmentService assignmentService;
    private final AgentRegistry agentRegistry;
    private final TradeMachineSelector selector;
    private final OrderDeliveryStateMachine stateMachine;
    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, TradeOffer> pendingOffers = new ConcurrentHashMap<>();
    private final Set<String> acceptedAssignments = ConcurrentHashMap.newKeySet();

    public TradeDispatchCoordinator(
            GameItemOrderService orderService,
            MachineGameService machineGameService,
            GameAccountService gameAccountService,
            MachineService machineService,
            TradeAssignmentService assignmentService,
            AgentRegistry agentRegistry,
            TradeMachineSelector selector,
            OrderDeliveryStateMachine stateMachine) {
        this.orderService = orderService;
        this.machineGameService = machineGameService;
        this.gameAccountService = gameAccountService;
        this.machineService = machineService;
        this.assignmentService = assignmentService;
        this.agentRegistry = agentRegistry;
        this.selector = selector;
        this.stateMachine = stateMachine;
    }

    @Transactional
    public TradeOffer dispatch(Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw new IllegalStateException("订单不存在");
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
                orderPayload(order));

        // 状态机驱动状态转换
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", assignmentId);
        ctx.put("message", "总控发送交易指派");
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
            ctx.put("message", "Worker 接受交易指派");
            stateMachine.fire(order, DeliveryEvent.OFFER_ACCEPTED, ctx);
            acceptedAssignments.add(assignmentId);

            if (!agentRegistry.sendTradeStart(machineId, assignmentId, offer.executionToken())) {
                // 状态机：assigned → suspended
                Map<String, Object> failCtx = new HashMap<>();
                failCtx.put("assignmentId", assignmentId);
                failCtx.put("machineId", machineId);
                failCtx.put("gameAccountId", offer.gameAccountId());
                failCtx.put("message", "发送交易启动指令失败");
                stateMachine.fire(order, DeliveryEvent.START_FAILED, failCtx);
                acceptedAssignments.remove(assignmentId);
                pendingOffers.remove(assignmentId);
                throw new IllegalStateException("发送交易启动指令失败");
            }
        }
    }

    @Transactional
    public void handleStatus(String assignmentId, int machineId, String status, String message) {
        TradeOffer offer = requirePendingOffer(assignmentId, machineId);
        if (!acceptedAssignments.contains(assignmentId)) {
            throw new IllegalStateException("指派尚未接受，不能上报执行状态");
        }

        GameItemOrder order = orderService.getById(offer.orderId());
        Map<String, Object> ctx = new HashMap<>();
        ctx.put("assignmentId", assignmentId);
        ctx.put("machineId", machineId);
        ctx.put("gameAccountId", offer.gameAccountId());
        ctx.put("message", message);

        if ("simulation_completed".equals(status)) {
            stateMachine.fire(order, DeliveryEvent.TRADE_COMPLETED, ctx);
            pendingOffers.remove(assignmentId);
            acceptedAssignments.remove(assignmentId);
        } else if ("start_rejected".equals(status) || "cancelled".equals(status)) {
            stateMachine.fire(order, DeliveryEvent.TRADE_CANCELLED, ctx);
            pendingOffers.remove(assignmentId);
            acceptedAssignments.remove(assignmentId);
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
    }

    private List<TradeCandidate> buildCandidates(GameItemOrder order) {
        List<MachineGame> machineGames = machineGameService
                .findByGameIdActiveOrderByPriorityDesc(order.getGameId());
        List<GameAccount> accounts = gameAccountService
                .findIdleByGameAndRegion(order.getGameId(), order.getRegionId());
        Map<Integer, GameAccount> accountByMachine = new LinkedHashMap<>();
        for (GameAccount account : accounts) {
            accountByMachine.putIfAbsent(account.getMachineId(), account);
        }

        List<TradeCandidate> candidates = new ArrayList<>();
        for (MachineGame machineGame : machineGames) {
            int machineId = machineGame.getMachineId();
            GameAccount account = accountByMachine.get(machineId);
            WorkerRuntimeStatus runtime = agentRegistry.getRuntimeStatus(machineId);
            if (account == null || runtime == null) {
                continue;
            }
            boolean runtimeMatchesAccount = account.getId().equals(runtime.gameAccountId())
                    && order.getGameId().equals(runtime.gameId())
                    && order.getRegionId().equals(runtime.regionId());
            candidates.add(new TradeCandidate(
                    machineId,
                    account.getId(),
                    machineGame.getGameId(),
                    order.getRegionId(),
                    machineGame.getPriority(),
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

    private Map<String, Object> orderPayload(GameItemOrder order) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("order_id", order.getId());
        payload.put("game_id", order.getGameId());
        payload.put("region_id", order.getRegionId());
        payload.put("buyer_character", order.getBuyerCharacter());
        payload.put("asset_type", order.getAssetType());
        payload.put("asset_amount", order.getAssetAmount());
        return payload;
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
}
