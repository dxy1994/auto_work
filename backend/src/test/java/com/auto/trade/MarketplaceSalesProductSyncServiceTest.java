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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MarketplaceSalesProductSyncServiceTest {

    private PlatformAccountService accountService;
    private PlatformSalesProductService productService;
    private GameService gameService;
    private GameRegionService regionService;
    private GameItemService gameItemService;
    private MarketplaceSalesProductSyncService syncService;

    @BeforeEach
    void setUp() {
        accountService = mock(PlatformAccountService.class);
        productService = mock(PlatformSalesProductService.class);
        gameService = mock(GameService.class);
        regionService = mock(GameRegionService.class);
        gameItemService = mock(GameItemService.class);
        syncService = new MarketplaceSalesProductSyncService(
                accountService,
                productService,
                gameService,
                regionService,
                gameItemService);

        PlatformAccount account = new PlatformAccount();
        account.setId(11);
        account.setWebsiteId(2);
        account.setIsActive(1);
        account.setExtraFields(Map.of());
        when(accountService.getById(11)).thenReturn(account);
    }

    @Test
    void insertsResolvedProductAndDeletesOnlyMissingRows() {
        Game game = new Game();
        game.setId(3);
        game.setName("아이온2");
        game.setCode("aion2");
        game.setIsActive(1);
        GameRegion region = new GameRegion();
        region.setId(5);
        region.setGameId(3);
        region.setName("월드 거래소(마족)");
        region.setCode("aion2-asmo");
        region.setIsActive(1);
        GameItem item = new GameItem();
        item.setId(7);
        item.setGameId(3);
        item.setName("키나");
        item.setCode("kinah");
        item.setIsActive(1);

        when(gameService.findAllActiveOrdered()).thenReturn(List.of(game));
        when(regionService.findByGameIdActive(3))
                .thenReturn(List.of(region));
        when(gameItemService.findActiveByGameIdAndCodeOrName(
                3, "키나")).thenReturn(item);
        when(productService.findByAccountId(11)).thenReturn(List.of());
        when(productService.deleteMissing(any(), any())).thenReturn(2);

        SalesProductsSyncResult result = syncService.sync(
                11,
                new SalesProductsSnapshotMessage(
                        "barotem",
                        List.of(new SalesProductObservation(
                                "39182563",
                                "money",
                                "아이온2",
                                "월드 거래소(마족)",
                                "빠른 %키나% 거래",
                                "99억 키나",
                                "5,080 원",
                                "26년 07월 31일 12:52:43"))));

        ArgumentCaptor<PlatformSalesProduct> saved =
                ArgumentCaptor.forClass(PlatformSalesProduct.class);
        verify(productService).save(saved.capture());
        PlatformSalesProduct row = saved.getValue();
        assertEquals(3, row.getGameId());
        assertEquals(5, row.getRegionId());
        assertEquals(7, row.getGameItemId());
        assertEquals("키나", row.getParsedItemName());
        assertEquals("matched", row.getParseStatus());
        assertEquals(1, result.insertedCount());
        assertEquals(2, result.deletedCount());

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Collection<String>> observed =
                ArgumentCaptor.forClass(Collection.class);
        verify(productService).deleteMissing(
                org.mockito.ArgumentMatchers.eq(11),
                observed.capture());
        assertEquals(List.of("39182563"),
                List.copyOf(observed.getValue()));
    }

    @Test
    void parseFailureIsStillInserted() {
        when(gameService.findAllActiveOrdered()).thenReturn(List.of());
        when(productService.findByAccountId(11)).thenReturn(List.of());
        when(productService.deleteMissing(any(), any())).thenReturn(0);

        syncService.sync(
                11,
                new SalesProductsSnapshotMessage(
                        "itemmania",
                        List.of(new SalesProductObservation(
                                "2026073009945700",
                                "item",
                                "未知游戏",
                                "未知大区",
                                "没有商品标记的标题",
                                "",
                                "1,600,000원",
                                "07-31 14:49"))));

        ArgumentCaptor<PlatformSalesProduct> saved =
                ArgumentCaptor.forClass(PlatformSalesProduct.class);
        verify(productService).save(saved.capture());
        assertEquals("title_parse_failed",
                saved.getValue().getParseStatus());
        assertTrue(saved.getValue().getParseError()
                .contains("商品标题未包含有效"));
    }

    @Test
    void existingProductIsUpdatedInsteadOfInsertedAgain() {
        PlatformSalesProduct existing = new PlatformSalesProduct();
        existing.setId(99);
        existing.setWebsiteId(2);
        existing.setPlatformAccountId(11);
        existing.setPlatform("itembay");
        existing.setPlatformProductId("33572289620");
        existing.setTitle("旧标题");
        existing.setParseStatus("title_parse_failed");
        existing.setParseError("");
        existing.setPlatformItemType("아이템");
        existing.setGameName("");
        existing.setRegionName("");
        existing.setParsedItemName("");
        existing.setQuantityText("");
        existing.setPriceText("");
        existing.setPlatformRegisteredAt("");

        when(gameService.findAllActiveOrdered()).thenReturn(List.of());
        when(productService.findByAccountId(11))
                .thenReturn(List.of(existing));
        when(productService.deleteMissing(any(), any())).thenReturn(0);

        SalesProductsSyncResult result = syncService.sync(
                11,
                new SalesProductsSnapshotMessage(
                        "itembay",
                        List.of(new SalesProductObservation(
                                "33572289620",
                                "아이템",
                                "",
                                "",
                                "新标题",
                                "",
                                "",
                                ""))));

        verify(productService, never()).save(any());
        verify(productService).updateById(existing);
        assertEquals("新标题", existing.getTitle());
        assertEquals(1, result.updatedCount());
    }

    @Test
    void unchangedProductIsNotWrittenAgain() {
        PlatformSalesProduct existing = new PlatformSalesProduct();
        existing.setId(100);
        existing.setWebsiteId(2);
        existing.setPlatformAccountId(11);
        existing.setPlatform("itembay");
        existing.setPlatformProductId("33572289620");
        existing.setPlatformItemType("아이템");
        existing.setGameName("");
        existing.setRegionName("");
        existing.setTitle("无标记标题");
        existing.setParsedItemName("");
        existing.setParseStatus("title_parse_failed");
        existing.setParseError(
                "商品标题未包含有效的 %物品名% 标记; "
                        + "未匹配到游戏: ; 未匹配到大区: ");
        existing.setQuantityText("");
        existing.setPriceText("");
        existing.setPlatformRegisteredAt("");

        when(gameService.findAllActiveOrdered()).thenReturn(List.of());
        when(productService.findByAccountId(11))
                .thenReturn(List.of(existing));
        when(productService.deleteMissing(any(), any())).thenReturn(0);

        SalesProductsSyncResult result = syncService.sync(
                11,
                new SalesProductsSnapshotMessage(
                        "itembay",
                        List.of(new SalesProductObservation(
                                "33572289620",
                                "아이템",
                                "",
                                "",
                                "无标记标题",
                                "",
                                "",
                                ""))));

        verify(productService, never()).save(any());
        verify(productService, never()).updateById(any());
        assertEquals(1, result.unchangedCount());
    }

    @Test
    void emptyCompleteSnapshotPhysicallyDeletesAllAccountProducts() {
        when(gameService.findAllActiveOrdered()).thenReturn(List.of());
        when(productService.findByAccountId(11)).thenReturn(List.of());
        when(productService.deleteMissing(any(), any())).thenReturn(4);

        SalesProductsSyncResult result = syncService.sync(
                11,
                new SalesProductsSnapshotMessage(
                        "barotem", List.of()));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Collection<String>> observed =
                ArgumentCaptor.forClass(Collection.class);
        verify(productService).deleteMissing(
                org.mockito.ArgumentMatchers.eq(11),
                observed.capture());
        assertTrue(observed.getValue().isEmpty());
        assertEquals(4, result.deletedCount());
    }
}
