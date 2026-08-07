package com.auto.trade;

import com.auto.common.ApiException;
import com.auto.entity.GameItemOrder;
import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.Platform;
import com.auto.entity.PlatformAccount;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Routes ordered chat messages to the monitor that owns an order's platform account.
 *
 * <p>The order, platform, account, machine and customer conversation are resolved
 * together so a command cannot accidentally use another account or order.</p>
 */
@Service
public class ChatDispatchService {

    private static final Logger log = LoggerFactory.getLogger(ChatDispatchService.class);
    private static final int MAX_MESSAGES = 30;
    private static final int MAX_IMAGES = 30;
    private static final int MAX_TEXT_LENGTH = 5000;
    private static final Set<String> SUPPORTED_TYPES =
            Set.of("text", "image", "mixed", "text_image");
    private static final String ITEMMANIA_URL_TEMPLATE =
            "https://www.itemmania.com/myroom/chat/new_chat.html"
                    + "?tid={order_no}&type=sell&c_type=apl";
    private static final String ITEMMANIA_DELIVERY_URL_TEMPLATE =
            "https://www.itemmania.com/myroom/sell/sell_ing_view.html"
                    + "?id={order_no}&type=sell";
    private static final String ITEMBAY_URL_TEMPLATE =
            "https://www.itembay.com/ibmessenger/bayTalkChatTran"
                    + "?iTranSeq={order_no}";
    private static final String BAROTEM_ORDER_LIST_URL_TEMPLATE =
            "https://www.barotem.com/mypage/sellview/4"
                    + "?mode=4&itemtype={item_type}&page=1&limit=500"
                    + "&source_order_no={order_no}";
    private static final String ITEMBAY_DELIVERY_URL_TEMPLATE =
            "https://www.itembay.com/item/transaction/transactionGiveTakeDetail"
                    + "?iTranSeq={order_no}";
    private static final int ITEMBAY_MAX_TEXT_LENGTH = 800;
    private static final int ITEMBAY_MAX_IMAGE_BYTES = 5 * 1024 * 1024;
    private static final List<String> KOREAN_AFFIRMATIVE_REPLIES = List.of(
            "네",
            "예",
            "넵",
            "네네",
            "네 맞습니다",
            "예 맞습니다",
            "네 본인 맞습니다",
            "네 본인 맛습니다",
            "맛습니다",
            "맞습니다",
            "맞아요",
            "본인입니다",
            "ok",
            "네 저예요");

    private final GameItemOrderService orderService;
    private final PlatformAccountService accountService;
    private final MachinePlatformAccountService machinePlatformAccountService;
    private final PlatformService platformService;
    private final TradeEventService tradeEventService;
    private final AgentRegistry agentRegistry;

    public ChatDispatchService(
            GameItemOrderService orderService,
            PlatformAccountService accountService,
            MachinePlatformAccountService machinePlatformAccountService,
            PlatformService platformService,
            TradeEventService tradeEventService,
            AgentRegistry agentRegistry) {
        this.orderService = orderService;
        this.accountService = accountService;
        this.machinePlatformAccountService = machinePlatformAccountService;
        this.platformService = platformService;
        this.tradeEventService = tradeEventService;
        this.agentRegistry = agentRegistry;
    }

    /** Dispatch a manually composed conversation without changing the order state. */
    public DispatchReceipt dispatchOrderChat(
            int orderId,
            List<Map<String, Object>> rawMessages) {
        GameItemOrder order = requireOrder(orderId);
        Route route = resolveRoute(order);
        return dispatch(
                route.machineId(),
                order,
                route.platform(),
                route.accountId(),
                normalizeMessages(rawMessages),
                "manual",
                null);
    }

    /** 最终游戏确认前发送确认话术与截图，并等待买家新回复。 */
    public DispatchReceipt dispatchTradeFinalConfirmation(
            int orderId,
            String requestId,
            List<Map<String, Object>> rawMessages) {
        GameItemOrder order = requireOrder(orderId);
        Route route = resolveRoute(order);
        return dispatch(
                route.machineId(),
                order,
                route.platform(),
                route.accountId(),
                normalizeMessages(rawMessages),
                TradeFinalConfirmationService.PURPOSE,
                null,
                requestId);
    }

    /** Dispatch automatic greeting scripts through the same generic chat command. */
    public DispatchReceipt dispatchGreeting(
            int machineId,
            int orderId,
            int websiteId,
            int accountId,
            String sourceOrderNo,
            String platformHint,
            List<Map<String, Object>> rawMessages) {
        GameItemOrder order = requireOrder(orderId);
        if (!Integer.valueOf(websiteId).equals(order.getWebsiteId())
                || !Integer.valueOf(accountId).equals(order.getPlatformAccountId())
                || !normalizeOrderNo(sourceOrderNo).equals(
                        normalizeOrderNo(order.getSourceOrderNo()))) {
            throw ApiException.badRequest("招呼指令与订单来源平台、账号或平台订单号不匹配");
        }
        Platform platform = requirePlatform(websiteId);
        String platformCode = platformCode(platformHint, platform);
        return dispatch(
                machineId,
                order,
                new PlatformRoute(platform, platformCode),
                accountId,
                normalizeMessages(rawMessages),
                "greeting",
                null);
    }

    /** 游戏交易完成后只确认网站商品交付；最终确认截图此前已经发送。 */
    public DispatchReceipt dispatchDeliveryConfirmation(int orderId) {
        GameItemOrder order = requireOrder(orderId);
        if (!"wait_web_confirm".equals(order.getDeliveryStatus())) {
            throw ApiException.badRequest("订单尚未进入等待网站确认状态");
        }
        String screenshotPath = safe(order.getGameTradeScreenshot()).strip();
        if (!screenshotPath.startsWith("/uploads/trade-screenshots/")
                || screenshotPath.length() > 512
                || screenshotPath.contains("..")) {
            throw ApiException.badRequest("订单缺少有效的最终确认前截图路径");
        }

        Route route = resolveRoute(order);
        Map<String, Object> action = resolveDeliveryAction(route.platform(), order);
        action.put("skip_chat", true);
        return dispatch(
                route.machineId(),
                order,
                route.platform(),
                route.accountId(),
                List.of(),
                "delivery_confirmation",
                action);
    }

    public void handleResult(
            int machineId,
            String requestId,
            int orderId,
            boolean success,
            String message) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            log.warn("[Chat] 回执对应订单不存在 request_id={} order_id={}", requestId, orderId);
            return;
        }
        String eventType = success ? "chat_message_sent" : "chat_message_failed";
        appendEvent(
                order,
                eventType,
                success ? "聊天消息已发送" : normalizeResultMessage(message),
                Map.of(
                        "request_id", safe(requestId),
                        "machine_id", machineId,
                        "success", success));
    }

    public List<ChatMessage> normalizeMessages(List<Map<String, Object>> rawMessages) {
        if (rawMessages == null || rawMessages.isEmpty()) {
            throw ApiException.badRequest("聊天消息不能为空");
        }
        if (rawMessages.size() > MAX_MESSAGES) {
            throw ApiException.badRequest("一次最多发送 " + MAX_MESSAGES + " 条聊天消息");
        }

        List<ChatMessage> messages = new ArrayList<>();
        int imageCount = 0;
        for (int index = 0; index < rawMessages.size(); index++) {
            Map<String, Object> raw = rawMessages.get(index);
            if (raw == null) {
                throw ApiException.badRequest("第 " + (index + 1) + " 条聊天消息无效");
            }
            String requestedType = safe(raw.get("type")).toLowerCase(Locale.ROOT);
            if (!requestedType.isBlank() && !SUPPORTED_TYPES.contains(requestedType)) {
                throw ApiException.badRequest(
                        "第 " + (index + 1) + " 条消息类型不支持: " + requestedType);
            }

            String content = safe(raw.get("content"));
            if (content.isBlank()) {
                content = safe(raw.get("text"));
            }
            content = content.strip();
            if (content.length() > MAX_TEXT_LENGTH) {
                throw ApiException.badRequest(
                        "第 " + (index + 1) + " 条文字超过 " + MAX_TEXT_LENGTH + " 个字符");
            }

            LinkedHashSet<String> imageUrls = new LinkedHashSet<>();
            Object manyImages = raw.get("image_urls");
            if (manyImages instanceof List<?> list) {
                for (Object value : list) {
                    addImageUrl(imageUrls, value, index);
                }
            }
            addImageUrl(imageUrls, raw.get("image_url"), index);
            imageCount += imageUrls.size();
            if (imageCount > MAX_IMAGES) {
                throw ApiException.badRequest("一次最多发送 " + MAX_IMAGES + " 张图片");
            }
            if (content.isBlank() && imageUrls.isEmpty()) {
                throw ApiException.badRequest(
                        "第 " + (index + 1) + " 条消息必须包含文字或图片");
            }
            String type = !content.isBlank() && !imageUrls.isEmpty()
                    ? "mixed"
                    : !content.isBlank() ? "text" : "image";
            messages.add(new ChatMessage(
                    type,
                    content.isBlank() ? null : content,
                    List.copyOf(imageUrls)));
        }
        return List.copyOf(messages);
    }

    private DispatchReceipt dispatch(
            int machineId,
            GameItemOrder order,
            PlatformRoute platformRoute,
            int accountId,
            List<ChatMessage> messages,
            String purpose,
            Map<String, Object> postAction) {
        return dispatch(
                machineId, order, platformRoute, accountId, messages,
                purpose, postAction, null);
    }

    private DispatchReceipt dispatch(
            int machineId,
            GameItemOrder order,
            PlatformRoute platformRoute,
            int accountId,
            List<ChatMessage> messages,
            String purpose,
            Map<String, Object> postAction,
            String requestedRequestId) {
        Map<String, Object> target =
                resolveTarget(
                        platformRoute.platform(), platformRoute.code(), order,
                        messages, purpose);
        String requestId = safe(requestedRequestId).strip();
        if (requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }
        List<Map<String, Object>> payloadMessages =
                messages.stream().map(ChatMessage::toPayload).toList();
        boolean sent = postAction == null
                ? agentRegistry.sendChat(
                        machineId,
                        requestId,
                        order.getId(),
                        order.getWebsiteId(),
                        accountId,
                        platformRoute.code(),
                        order.getSourceOrderNo(),
                        purpose,
                        payloadMessages,
                        target)
                : agentRegistry.sendChat(
                        machineId,
                        requestId,
                        order.getId(),
                        order.getWebsiteId(),
                        accountId,
                        platformRoute.code(),
                        order.getSourceOrderNo(),
                        purpose,
                        payloadMessages,
                        target,
                        postAction);
        if (!sent) {
            throw ApiException.badRequest("订单来源账号绑定的监控机器不在线或连接不可用");
        }
        int imageCount = messages.stream().mapToInt(message -> message.imageUrls().size()).sum();
        appendEvent(
                order,
                "chat_command_sent",
                "聊天指令已下发",
                Map.of(
                        "request_id", requestId,
                        "machine_id", machineId,
                        "platform", platformRoute.code(),
                        "purpose", purpose,
                        "message_count", messages.size(),
                        "image_count", imageCount));
        return new DispatchReceipt(
                requestId,
                order.getId(),
                machineId,
                platformRoute.code(),
                messages.size(),
                imageCount);
    }

    private Map<String, Object> resolveDeliveryAction(
            PlatformRoute platformRoute,
            GameItemOrder order) {
        Platform platform = platformRoute.platform();
        String platformCode = platformRoute.code();
        Map<?, ?> config = nestedMap(platform.getLoginConfig(), "delivery_config");
        String urlTemplate = configString(config, "detail_url_template");
        String openConfirmSelector = configString(config, "open_confirm_selector");
        String confirmSelector = configString(config, "confirm_selector");
        String successSelector = configString(config, "success_selector");
        String successAbsentSelector = configString(
                config, "success_absent_selector");
        String successUrlContains = configString(
                config, "success_url_contains");
        String readySelector = configString(config, "ready_selector");
        String blockingPopupSelector = configString(
                config, "blocking_popup_selector");
        String blockingPopupCloseSelector = configString(
                config, "blocking_popup_close_selector");
        List<String> successTexts = configStringList(config, "success_texts");
        String stageSelector = configString(config, "stage_selector");
        String stageActiveClass = configString(config, "stage_active_class");
        int pendingStage = configInt(config, "pending_stage", 0);
        boolean singleClick = configBoolean(config, "single_click", false);

        if ("itemmania".equals(platformCode)) {
            if (urlTemplate.isBlank()) {
                urlTemplate = ITEMMANIA_DELIVERY_URL_TEMPLATE;
            }
            if (openConfirmSelector.isBlank()) {
                openConfirmSelector = "#trade_btn";
            }
            if (confirmSelector.isBlank()) {
                confirmSelector =
                        "#dvTradeSellCheck button:has-text(\"상품인계 확인\")";
            }
            if (successSelector.isBlank()) {
                successSelector = ".caution_list .caution.active p";
            }
            if (successTexts.isEmpty()) {
                successTexts = List.of("인계완료", "판매완료");
            }
            if (stageSelector.isBlank()) {
                stageSelector = ".caution_list .caution";
            }
            if (pendingStage <= 0) {
                pendingStage = 3;
            }
        }

        if ("itembay".equals(platformCode)) {
            if (urlTemplate.isBlank()) {
                urlTemplate = ITEMBAY_DELIVERY_URL_TEMPLATE;
            }
            if (openConfirmSelector.isBlank()) {
                openConfirmSelector =
                        ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']";
            }
            if (readySelector.isBlank()) {
                readySelector = "#middle .list-page-detail";
            }
            if (successAbsentSelector.isBlank()) {
                successAbsentSelector =
                        ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']";
            }
            if (successUrlContains.isBlank()) {
                successUrlContains = "/mybay/status/mybayStatusGiveList";
            }
            singleClick = configBoolean(config, "single_click", true);
        }

        if ("barotem".equals(platformCode)) {
            if (urlTemplate.isBlank()) {
                urlTemplate = BAROTEM_ORDER_LIST_URL_TEMPLATE;
            }
            if (openConfirmSelector.isBlank()) {
                openConfirmSelector = "#state5";
            }
            if (confirmSelector.isBlank()) {
                confirmSelector = "#commonAlert .common_alert_check";
            }
            if (readySelector.isBlank()) {
                readySelector = ".chat_info_process";
            }
            if (successSelector.isBlank()) {
                successSelector = "#commonAlert .common_alert_wrap h2";
            }
            if (successTexts.isEmpty()) {
                successTexts = List.of("구매자에게 인수확인 요청하였습니다.");
            }
            if (stageSelector.isBlank()) {
                stageSelector = ".chat_info_process > div";
            }
            if (stageActiveClass.isBlank()) {
                stageActiveClass = "on";
            }
            if (pendingStage <= 0) {
                pendingStage = 2;
            }
        }

        String orderNo = normalizeOrderNo(order.getSourceOrderNo());
        if (orderNo.isBlank()) {
            throw ApiException.badRequest("订单缺少平台订单号，无法确认商品交付");
        }
        if (urlTemplate.isBlank()
                || (!urlTemplate.contains("{order_no}")
                && !urlTemplate.contains("{source_order_no}"))) {
            throw ApiException.badRequest(
                    "平台未配置包含 {order_no} 的订单详情地址模板");
        }
        boolean hasTextSuccessCheck = !successSelector.isBlank()
                && !successTexts.isEmpty();
        if (openConfirmSelector.isBlank()
                || (!singleClick && confirmSelector.isBlank())
                || (successAbsentSelector.isBlank()
                && successUrlContains.isBlank()
                && !hasTextSuccessCheck)) {
            throw ApiException.badRequest("平台未完整配置商品交付确认选择器");
        }
        if (stageSelector.isBlank() != (pendingStage <= 0)) {
            throw ApiException.badRequest("平台交付阶段选择器与待交付阶段编号必须同时配置");
        }

        String encodedOrderNo = URLEncoder.encode(orderNo, StandardCharsets.UTF_8);
        String detailUrl = urlTemplate
                .replace("{order_no}", encodedOrderNo)
                .replace("{source_order_no}", encodedOrderNo)
                .replace(
                        "{item_type}",
                        URLEncoder.encode(
                                barotemItemType(order),
                                StandardCharsets.UTF_8));
        validateTargetUrl(detailUrl, platform);

        Map<String, Object> action = new LinkedHashMap<>();
        action.put("type", "confirm_delivery");
        action.put("detail_url", detailUrl);
        action.put("open_confirm_selector", openConfirmSelector);
        action.put("single_click", singleClick);
        if (!confirmSelector.isBlank()) {
            action.put("confirm_selector", confirmSelector);
        }
        if (!readySelector.isBlank()) {
            action.put("ready_selector", readySelector);
        }
        if (!successAbsentSelector.isBlank()) {
            action.put("success_absent_selector", successAbsentSelector);
        }
        if (!successUrlContains.isBlank()) {
            action.put("success_url_contains", successUrlContains);
        }
        if (!successSelector.isBlank()) {
            action.put("success_selector", successSelector);
        }
        if (!successTexts.isEmpty()) {
            action.put("success_texts", successTexts);
        }
        if (!blockingPopupSelector.isBlank()) {
            action.put("blocking_popup_selector", blockingPopupSelector);
        }
        if (!blockingPopupCloseSelector.isBlank()) {
            action.put(
                    "blocking_popup_close_selector",
                    blockingPopupCloseSelector);
        }
        if (!stageSelector.isBlank()) {
            action.put("stage_selector", stageSelector);
            action.put("pending_stage", pendingStage);
            if (!stageActiveClass.isBlank()) {
                action.put("stage_active_class", stageActiveClass);
            }
        }
        if ("barotem".equals(platformCode)) {
            action.put("conversation_resolver", "barotem_order_list");
            action.put("order_no", orderNo);
            action.put("success_before_reload", true);
        }
        return action;
    }

    private Route resolveRoute(GameItemOrder order) {
        Integer accountId = order.getPlatformAccountId();
        if (accountId == null) {
            throw ApiException.badRequest("订单缺少来源平台账号");
        }
        PlatformAccount account = accountService.getById(accountId);
        if (account == null
                || !Integer.valueOf(1).equals(account.getIsActive())
                || !order.getWebsiteId().equals(account.getWebsiteId())) {
            throw ApiException.badRequest("订单来源平台账号不存在、已停用或与平台不匹配");
        }
        Integer machineId = null;
        for (MachinePlatformAccount binding
                : machinePlatformAccountService.findByAccountIdActive(accountId)) {
            if (agentRegistry.pickAgent(binding.getMachineId()) != null) {
                machineId = binding.getMachineId();
                break;
            }
        }
        if (machineId == null) {
            throw ApiException.badRequest("订单来源账号没有已绑定且在线的监控机器");
        }
        Platform platform = requirePlatform(order.getWebsiteId());
        return new Route(
                machineId,
                accountId,
                new PlatformRoute(platform, platformCode(null, platform)));
    }

    private Map<String, Object> resolveTarget(
            Platform platform,
            String platformCode,
            GameItemOrder order,
            List<ChatMessage> messages,
            String purpose) {
        String orderNo = normalizeOrderNo(order.getSourceOrderNo());
        if (orderNo.isBlank()) {
            throw ApiException.badRequest("订单缺少平台订单号，无法定位客户会话");
        }
        Map<?, ?> chatConfig = nestedMap(platform.getLoginConfig(), "chat_config");
        String urlTemplate = configString(chatConfig, "url_template");
        String inputSelector = configString(chatConfig, "input_selector");
        String sendSelector = configString(chatConfig, "send_selector");
        String fileSelector = configString(chatConfig, "file_selector");
        String uploadSendSelector = configString(chatConfig, "upload_send_selector");
        String uploadCloseSelector = configString(chatConfig, "upload_close_selector");
        String blockingPopupSelector = configString(chatConfig, "blocking_popup_selector");
        String blockingPopupCloseSelector =
                configString(chatConfig, "blocking_popup_close_selector");
        String sentSelector = configString(chatConfig, "sent_selector");
        String conversationSelector = configString(
                chatConfig, "conversation_selector");
        String conversationSelfClass = configString(
                chatConfig, "conversation_self_class");
        String conversationTextSelector = configString(
                chatConfig, "conversation_text_selector");
        boolean uploadAutoSend = configBoolean(chatConfig, "upload_auto_send", true);
        int sentTimeoutMs = configInt(chatConfig, "sent_timeout_ms", 0);
        int maxTextLength = configInt(chatConfig, "max_text_length", 0);
        int maxImageBytes = configInt(chatConfig, "max_image_bytes", 0);
        boolean barotemImageSubmit = false;

        if ("itemmania".equals(platformCode)) {
            if (urlTemplate.isBlank()) urlTemplate = ITEMMANIA_URL_TEMPLATE;
            if (inputSelector.isBlank()) inputSelector = "#write_chat";
            if (sendSelector.isBlank()) sendSelector = "#send_btn";
            if (fileSelector.isBlank()) {
                fileSelector = "#attach_layer input[type=file]";
            }
            if (uploadCloseSelector.isBlank()) {
                uploadCloseSelector = "#attach_layer .close";
            }
            if (sentSelector.isBlank()) {
                sentSelector = ".chat_item.me";
            }
            if (conversationSelector.isBlank()) {
                conversationSelector = ".chat_item.me, .chat_item.another";
            }
            if (conversationSelfClass.isBlank()) {
                conversationSelfClass = "me";
            }
            if (conversationTextSelector.isBlank()) {
                conversationTextSelector = ".chat_msg";
            }
            if (sentTimeoutMs <= 0) sentTimeoutMs = 10_000;
        }
        if ("itembay".equals(platformCode)) {
            if (urlTemplate.isBlank()) urlTemplate = ITEMBAY_URL_TEMPLATE;
            if (inputSelector.isBlank()) inputSelector = "#txtAreaMsgSend";
            if (sendSelector.isBlank()) sendSelector = "#btnSend";
            if (fileSelector.isBlank()) fileSelector = "#txtScreenShot";
            if (blockingPopupSelector.isBlank()) {
                blockingPopupSelector = "#sTalkPop";
            }
            if (blockingPopupCloseSelector.isBlank()) {
                blockingPopupCloseSelector = "#sTalkPop .btn_pop_close";
            }
            if (sentSelector.isBlank()) {
                sentSelector = "#chat_container .list_message li.send";
            }
            if (conversationSelector.isBlank()) {
                conversationSelector = "#chat_container .list_message li";
            }
            if (conversationSelfClass.isBlank()) {
                conversationSelfClass = "send";
            }
            if (conversationTextSelector.isBlank()) {
                conversationTextSelector = ".message_balloon";
            }
            if (sentTimeoutMs <= 0) sentTimeoutMs = 10_000;
            if (maxTextLength <= 0) {
                maxTextLength = ITEMBAY_MAX_TEXT_LENGTH;
            }
            if (maxImageBytes <= 0) {
                maxImageBytes = ITEMBAY_MAX_IMAGE_BYTES;
            }
            uploadAutoSend = true;
        }
        if ("barotem".equals(platformCode)) {
            // Barotem 的聊天地址使用订单卡片中的 jangNum，不能由平台订单号直接拼接。
            // 先打开卖家订单列表，Worker 再按 source_order_no 找到卡片并解析聊天地址。
            urlTemplate = BAROTEM_ORDER_LIST_URL_TEMPLATE;
            if (inputSelector.isBlank()) {
                inputSelector = "#happy_chating_form #message";
            }
            if (sendSelector.isBlank()) {
                sendSelector = "#happy_chating_form .chat_send_btn";
            }
            // 将文件参数交给聊天页 imgchg() 生成预览，再点击当前页确认按钮。
            barotemImageSubmit = true;
            if (sentSelector.isBlank()) {
                sentSelector = "#chatBox .chattingDate.chat_converse.from_me";
            }
            if (conversationSelector.isBlank()) {
                conversationSelector = "#chatBox .chattingDate.chat_converse";
            }
            if (conversationSelfClass.isBlank()) {
                conversationSelfClass = "from_me";
            }
            if (conversationTextSelector.isBlank()) {
                conversationTextSelector = ".chat_txt";
            }
            if (sentTimeoutMs <= 0) sentTimeoutMs = 10_000;
        }
        if (urlTemplate.isBlank()
                || (!urlTemplate.contains("{order_no}")
                && !urlTemplate.contains("{source_order_no}"))) {
            throw ApiException.badRequest(
                    "平台未配置包含 {order_no} 的客户聊天地址模板");
        }
        if (inputSelector.isBlank() || sendSelector.isBlank()) {
            throw ApiException.badRequest("平台未配置聊天输入框或发送按钮选择器");
        }
        boolean hasImages = messages.stream().anyMatch(message -> !message.imageUrls().isEmpty());
        if (hasImages && !barotemImageSubmit && fileSelector.isBlank()) {
            throw ApiException.badRequest("平台未配置聊天图片上传控件选择器");
        }
        if (hasImages && !barotemImageSubmit
                && !uploadAutoSend && uploadSendSelector.isBlank()) {
            throw ApiException.badRequest("平台未配置图片上传后的发送按钮选择器");
        }
        if (maxTextLength > 0) {
            for (int index = 0; index < messages.size(); index++) {
                String content = safe(messages.get(index).content());
                if (content.length() > maxTextLength) {
                    throw ApiException.badRequest(
                            "第 " + (index + 1) + " 条文字超过平台限制 "
                                    + maxTextLength + " 个字符");
                }
            }
        }

        String encodedOrderNo = URLEncoder.encode(orderNo, StandardCharsets.UTF_8);
        String encodedItemType = URLEncoder.encode(
                barotemItemType(order), StandardCharsets.UTF_8);
        String url = urlTemplate
                .replace("{order_no}", encodedOrderNo)
                .replace("{source_order_no}", encodedOrderNo)
                .replace("{item_type}", encodedItemType);
        validateTargetUrl(url, platform);

        Map<String, Object> target = new LinkedHashMap<>();
        target.put("url", url);
        target.put("input_selector", inputSelector);
        target.put("send_selector", sendSelector);
        if (!barotemImageSubmit && !fileSelector.isBlank()) {
            target.put("file_selector", fileSelector);
        }
        if (!barotemImageSubmit) {
            target.put("upload_auto_send", uploadAutoSend);
        }
        if ("barotem".equals(platformCode)) {
            target.put("conversation_resolver", "barotem_order_list");
            target.put("order_no", orderNo);
            target.put("barotem_image_submit", barotemImageSubmit);
        }
        if (!barotemImageSubmit && !uploadSendSelector.isBlank()) {
            target.put("upload_send_selector", uploadSendSelector);
        }
        if (!barotemImageSubmit && !uploadCloseSelector.isBlank()) {
            target.put("upload_close_selector", uploadCloseSelector);
        }
        if (!blockingPopupCloseSelector.isBlank()) {
            target.put("blocking_popup_selector", blockingPopupSelector);
            target.put("blocking_popup_close_selector", blockingPopupCloseSelector);
            target.put("blocking_popup_wait_ms", 2_000);
        }
        if (!sentSelector.isBlank()) {
            target.put("sent_selector", sentSelector);
            target.put("sent_timeout_ms", sentTimeoutMs > 0 ? sentTimeoutMs : 10_000);
        }
        if (TradeFinalConfirmationService.PURPOSE.equals(purpose)) {
            if (conversationSelector.isBlank()
                    || conversationSelfClass.isBlank()
                    || conversationTextSelector.isBlank()) {
                throw ApiException.badRequest("平台未完整配置确认问句后的聊天判断选择器");
            }
            target.put("wait_for_reply", true);
            target.put("conversation_selector", conversationSelector);
            target.put("conversation_self_class", conversationSelfClass);
            target.put("conversation_text_selector", conversationTextSelector);
            target.put("reply_timeout_ms", 300_000);
            target.put("affirmative_replies", KOREAN_AFFIRMATIVE_REPLIES);
        }
        if (maxTextLength > 0) {
            target.put("max_text_length", maxTextLength);
        }
        if (maxImageBytes > 0) {
            target.put("max_image_bytes", maxImageBytes);
        }
        target.put("order_no", orderNo);
        return target;
    }

    private String barotemItemType(GameItemOrder order) {
        String itemType = safe(order.getPlatformItemType())
                .trim()
                .toLowerCase(Locale.ROOT);
        return Set.of("money", "item", "id", "etc", "gift")
                .contains(itemType) ? itemType : "money";
    }

    private void validateTargetUrl(String url, Platform platform) {
        try {
            URI uri = URI.create(url);
            if (!Set.of("http", "https").contains(uri.getScheme())
                    || uri.getHost() == null) {
                throw new IllegalArgumentException("invalid scheme or host");
            }
            URI platformUri = URI.create(platform.getUrl());
            String expectedHost = platformUri.getHost();
            if (expectedHost != null
                    && !uri.getHost().equalsIgnoreCase(expectedHost)
                    && !uri.getHost().endsWith("." + expectedHost)) {
                throw ApiException.badRequest("聊天地址模板与订单来源平台域名不一致");
            }
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            throw ApiException.badRequest("平台聊天地址模板无效");
        }
    }

    private Platform requirePlatform(Integer websiteId) {
        Platform platform = platformService.getById(websiteId);
        if (platform == null || !Integer.valueOf(1).equals(platform.getIsActive())) {
            throw ApiException.badRequest("订单来源平台不存在或已停用");
        }
        return platform;
    }

    private GameItemOrder requireOrder(int orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw ApiException.notFound("订单不存在");
        }
        return order;
    }

    private String platformCode(String hint, Platform platform) {
        String value = safe(hint).toLowerCase(Locale.ROOT);
        if (Set.of("itemmania", "itembay", "barotem").contains(value)) {
            return value;
        }
        String source = (safe(platform.getUrl()) + " " + safe(platform.getName()))
                .toLowerCase(Locale.ROOT);
        if (source.contains("itemmania")) return "itemmania";
        if (source.contains("itembay")) return "itembay";
        if (source.contains("barotem")) return "barotem";
        return "platform-" + platform.getId();
    }

    private void appendEvent(
            GameItemOrder order,
            String eventType,
            String message,
            Map<String, Object> payload) {
        try {
            TradeEvent event = new TradeEvent();
            event.setOrderId(order.getId());
            event.setEventType(eventType);
            event.setFromStatus(order.getDeliveryStatus());
            event.setToStatus(order.getDeliveryStatus());
            event.setMessage(message);
            event.setPayload(payload);
            tradeEventService.save(event);
        } catch (Exception e) {
            log.warn("[Chat] 事件记录失败 order_id={} type={}: {}",
                    order.getId(), eventType, e.getMessage());
        }
    }

    private void addImageUrl(
            LinkedHashSet<String> target,
            Object rawValue,
            int messageIndex) {
        String value = safe(rawValue);
        if (value.isBlank()) {
            return;
        }
        value = value.strip();
        boolean accepted = value.startsWith("/uploads/")
                || value.startsWith("https://")
                || value.startsWith("http://");
        if (!accepted || value.length() > 2048) {
            throw ApiException.badRequest(
                    "第 " + (messageIndex + 1) + " 条消息包含无效图片地址");
        }
        target.add(value);
    }

    private Map<?, ?> nestedMap(Map<String, Object> source, String key) {
        if (source == null) return Map.of();
        Object value = source.get(key);
        return value instanceof Map<?, ?> map ? map : Map.of();
    }

    private String configString(Map<?, ?> source, String key) {
        return safe(source.get(key)).strip();
    }

    private boolean configBoolean(Map<?, ?> source, String key, boolean fallback) {
        Object value = source.get(key);
        return value instanceof Boolean booleanValue ? booleanValue : fallback;
    }

    private int configInt(Map<?, ?> source, String key, int fallback) {
        Object value = source.get(key);
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            String text = safe(value).strip();
            return text.isBlank() ? fallback : Integer.parseInt(text);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private List<String> configStringList(Map<?, ?> source, String key) {
        Object value = source.get(key);
        if (!(value instanceof List<?> list)) {
            return List.of();
        }
        return list.stream()
                .map(this::safe)
                .map(String::strip)
                .filter(item -> !item.isBlank())
                .toList();
    }

    private String normalizeResultMessage(String message) {
        String value = safe(message).strip();
        return value.isBlank() ? "聊天消息发送失败" : value.substring(0, Math.min(500, value.length()));
    }

    private String normalizeOrderNo(String value) {
        return safe(value).strip();
    }

    private String safe(Object value) {
        return value == null ? "" : value.toString();
    }

    public record ChatMessage(String type, String content, List<String> imageUrls) {
        public Map<String, Object> toPayload() {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("type", type);
            if (content != null) {
                payload.put("content", content);
            }
            if (!imageUrls.isEmpty()) {
                payload.put("image_urls", imageUrls);
            }
            return payload;
        }
    }

    public record DispatchReceipt(
            String requestId,
            int orderId,
            int machineId,
            String platform,
            int messageCount,
            int imageCount) {
        public Map<String, Object> toPayload() {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("status", "started");
            result.put("request_id", requestId);
            result.put("order_id", orderId);
            result.put("machine_id", machineId);
            result.put("platform", platform);
            result.put("message_count", messageCount);
            result.put("image_count", imageCount);
            result.put("message", "聊天指令已下发");
            return result;
        }
    }

    private record PlatformRoute(Platform platform, String code) {
    }

    private record Route(int machineId, int accountId, PlatformRoute platform) {
    }
}
