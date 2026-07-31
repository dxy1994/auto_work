package com.auto.trade;

import com.auto.entity.Game;
import com.auto.entity.GameItem;
import com.auto.entity.GameRegion;
import com.auto.entity.PlatformAccount;
import com.auto.entity.PlatformSalesProduct;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformSalesProductService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 将 Worker 的完整在售商品快照事务式同步到数据库。 */
@Service
public class MarketplaceSalesProductSyncService {

    private final PlatformAccountService accountService;
    private final PlatformSalesProductService productService;
    private final GameService gameService;
    private final GameRegionService regionService;
    private final GameItemService gameItemService;

    public MarketplaceSalesProductSyncService(
            PlatformAccountService accountService,
            PlatformSalesProductService productService,
            GameService gameService,
            GameRegionService regionService,
            GameItemService gameItemService) {
        this.accountService = accountService;
        this.productService = productService;
        this.gameService = gameService;
        this.regionService = regionService;
        this.gameItemService = gameItemService;
    }

    /**
     * 同步必须接收完整快照。成功事务中会新增、更新变化记录，并物理删除缺失记录。
     */
    @Transactional
    public SalesProductsSyncResult sync(
            int accountId, SalesProductsSnapshotMessage message) {
        PlatformAccount account = accountService.getById(accountId);
        if (account == null || !Integer.valueOf(1).equals(
                account.getIsActive())) {
            throw new IllegalStateException("网站账号不存在或已停用");
        }

        Map<String, PlatformSalesProduct> existingByProductId =
                new LinkedHashMap<>();
        for (PlatformSalesProduct existing :
                productService.findByAccountId(accountId)) {
            existingByProductId.put(
                    existing.getPlatformProductId(), existing);
        }

        int inserted = 0;
        int updated = 0;
        int unchanged = 0;
        Set<String> observedIds = new LinkedHashSet<>();
        List<Game> activeGames = gameService.findAllActiveOrdered();
        Map<Integer, List<GameRegion>> activeRegions = new HashMap<>();
        Map<String, GameItem> itemMatches = new HashMap<>();

        for (SalesProductObservation observation : message.products()) {
            observedIds.add(observation.platformProductId());
            Resolution resolution = resolve(
                    account,
                    observation,
                    activeGames,
                    activeRegions,
                    itemMatches);
            PlatformSalesProduct existing = existingByProductId.get(
                    observation.platformProductId());
            PlatformSalesProduct target = existing == null
                    ? new PlatformSalesProduct() : existing;
            boolean changed = existing != null && differs(
                    existing, account, message.platform(),
                    observation, resolution);
            applySnapshot(
                    target, account, message.platform(),
                    observation, resolution);

            if (existing == null) {
                try {
                    productService.save(target);
                    inserted++;
                } catch (DuplicateKeyException race) {
                    PlatformSalesProduct raced =
                            productService.findByAccountIdAndProductId(
                                    accountId,
                                    observation.platformProductId());
                    if (raced == null) {
                        throw race;
                    }
                    boolean racedChanged = differs(
                            raced, account, message.platform(),
                            observation, resolution);
                    applySnapshot(
                            raced, account, message.platform(),
                            observation, resolution);
                    if (racedChanged) {
                        productService.updateById(raced);
                        updated++;
                    } else {
                        unchanged++;
                    }
                }
            } else if (changed) {
                productService.updateById(target);
                updated++;
            } else {
                unchanged++;
            }
        }

        int deleted = productService.deleteMissing(accountId, observedIds);
        return new SalesProductsSyncResult(
                message.products().size(),
                inserted,
                updated,
                unchanged,
                deleted);
    }

    private Resolution resolve(
            PlatformAccount account,
            SalesProductObservation observation,
            List<Game> activeGames,
            Map<Integer, List<GameRegion>> activeRegions,
            Map<String, GameItem> itemMatches) {
        List<String> errors = new ArrayList<>();
        String parsedItemName =
                MarketplaceOrderIngestionService.parseItemFromTitle(
                        observation.title());
        if (parsedItemName.isEmpty()) {
            errors.add("商品标题未包含有效的 %物品名% 标记");
        }

        Game game = resolveGame(
                account.getExtraFields(),
                observation.gameName(),
                activeGames);
        if (game == null) {
            errors.add("未匹配到游戏: " + observation.gameName());
        }

        GameRegion region = game == null
                ? null
                : resolveRegion(
                        account.getExtraFields(),
                        game.getId(),
                        observation.regionName(),
                        activeRegions);
        if (region == null) {
            errors.add("未匹配到大区: " + observation.regionName());
        }

        GameItem item = null;
        if (game != null && !parsedItemName.isEmpty()) {
            String itemKey = game.getId() + "\u0000" + parsedItemName;
            if (!itemMatches.containsKey(itemKey)) {
                itemMatches.put(
                        itemKey,
                        gameItemService.findActiveByGameIdAndCodeOrName(
                                game.getId(), parsedItemName));
            }
            item = itemMatches.get(itemKey);
        }
        if (!parsedItemName.isEmpty() && item == null) {
            errors.add("未匹配到实际商品: " + parsedItemName);
        }

        String status;
        if (errors.isEmpty()) {
            status = "matched";
        } else if (parsedItemName.isEmpty()) {
            status = "title_parse_failed";
        } else if (game == null) {
            status = "game_unmatched";
        } else if (region == null) {
            status = "region_unmatched";
        } else {
            status = "item_unmatched";
        }
        return new Resolution(
                game == null ? null : game.getId(),
                region == null ? null : region.getId(),
                item == null ? null : item.getId(),
                parsedItemName,
                status,
                String.join("; ", errors));
    }

    private Game resolveGame(
            Map<String, Object> config,
            String externalGameName,
            List<Game> activeGames) {
        String value = normalize(externalGameName);
        Game matched = activeGames.stream()
                .filter(game -> same(value, game.getCode())
                        || same(value, game.getName()))
                .findFirst()
                .orElse(null);
        if (matched != null) {
            return matched;
        }
        if (!value.isEmpty()) {
            return null;
        }
        Integer configuredId = configuredInt(config, "trade_game_id");
        if (configuredId == null) {
            return null;
        }
        return activeGames.stream()
                .filter(game -> configuredId.equals(game.getId()))
                .findFirst()
                .orElse(null);
    }

    private GameRegion resolveRegion(
            Map<String, Object> config, int gameId,
            String externalRegionName,
            Map<Integer, List<GameRegion>> activeRegions) {
        List<GameRegion> regions = activeRegions.computeIfAbsent(
                gameId, regionService::findByGameIdActive);
        if (config != null
                && config.get("trade_region_map") instanceof Map<?, ?> map) {
            Object configured = map.get(externalRegionName);
            Integer configuredId = asInt(configured);
            if (configuredId != null) {
                GameRegion configuredRegion = regions.stream()
                        .filter(region -> configuredId.equals(region.getId()))
                        .findFirst()
                        .orElse(null);
                if (configuredRegion != null) return configuredRegion;
            }
        }
        String value = normalize(externalRegionName);
        return regions.stream()
                .filter(region -> same(value, region.getCode())
                        || same(value, region.getName()))
                .findFirst()
                .orElse(null);
    }

    private void applySnapshot(
            PlatformSalesProduct target,
            PlatformAccount account,
            String platform,
            SalesProductObservation observation,
            Resolution resolution) {
        target.setWebsiteId(account.getWebsiteId());
        target.setPlatformAccountId(account.getId());
        target.setPlatform(platform);
        target.setPlatformProductId(observation.platformProductId());
        target.setPlatformItemType(observation.platformItemType());
        target.setGameId(resolution.gameId());
        target.setRegionId(resolution.regionId());
        target.setGameItemId(resolution.gameItemId());
        target.setGameName(observation.gameName());
        target.setRegionName(observation.regionName());
        target.setTitle(observation.title());
        target.setParsedItemName(resolution.parsedItemName());
        target.setParseStatus(resolution.status());
        target.setParseError(resolution.error());
        target.setQuantityText(observation.quantityText());
        target.setPriceText(observation.priceText());
        target.setPlatformRegisteredAt(
                observation.platformRegisteredAt());
    }

    private boolean differs(
            PlatformSalesProduct existing,
            PlatformAccount account,
            String platform,
            SalesProductObservation observation,
            Resolution resolution) {
        return !Objects.equals(existing.getWebsiteId(),
                    account.getWebsiteId())
                || !Objects.equals(existing.getPlatformAccountId(),
                    account.getId())
                || !Objects.equals(existing.getPlatform(), platform)
                || !Objects.equals(existing.getPlatformItemType(),
                    observation.platformItemType())
                || !Objects.equals(existing.getGameId(),
                    resolution.gameId())
                || !Objects.equals(existing.getRegionId(),
                    resolution.regionId())
                || !Objects.equals(existing.getGameItemId(),
                    resolution.gameItemId())
                || !Objects.equals(existing.getGameName(),
                    observation.gameName())
                || !Objects.equals(existing.getRegionName(),
                    observation.regionName())
                || !Objects.equals(existing.getTitle(),
                    observation.title())
                || !Objects.equals(existing.getParsedItemName(),
                    resolution.parsedItemName())
                || !Objects.equals(existing.getParseStatus(),
                    resolution.status())
                || !Objects.equals(existing.getParseError(),
                    resolution.error())
                || !Objects.equals(existing.getQuantityText(),
                    observation.quantityText())
                || !Objects.equals(existing.getPriceText(),
                    observation.priceText())
                || !Objects.equals(existing.getPlatformRegisteredAt(),
                    observation.platformRegisteredAt());
    }

    private static Integer configuredInt(
            Map<String, Object> config, String key) {
        return config == null ? null : asInt(config.get(key));
    }

    private static Integer asInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return value == null ? null : Integer.parseInt(value.toString());
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim();
    }

    private static boolean same(String left, String right) {
        return left.equalsIgnoreCase(normalize(right));
    }

    private record Resolution(
            Integer gameId,
            Integer regionId,
            Integer gameItemId,
            String parsedItemName,
            String status,
            String error) {
    }
}
