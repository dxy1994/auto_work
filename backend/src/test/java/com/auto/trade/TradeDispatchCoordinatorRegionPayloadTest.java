package com.auto.trade;

import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegion;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class TradeDispatchCoordinatorRegionPayloadTest {

    @Test
    void appendsCentralRegionCoordinatesToWorkerInstruction() {
        GameRegion region = new GameRegion();
        region.setName("冥王哈迪斯");
        region.setCode("아툰");
        region.setSortOrder(11);
        region.setSelectX(310);
        region.setSelectY(154);
        Map<String, Object> payload = new LinkedHashMap<>();

        TradeDispatchCoordinator.appendRegionNavigationPayload(payload, region);

        assertEquals("冥王哈迪斯", payload.get("region_name"));
        assertEquals("아툰", payload.get("region_code"));
        assertEquals(11, payload.get("region_sort_order"));
        assertEquals(310, payload.get("region_select_x"));
        assertEquals(154, payload.get("region_select_y"));
    }

    @Test
    void sendsCurrentDatabaseItemImageForRecognition() {
        GameItem item = new GameItem();
        item.setImage("/uploads/images/current.png");
        GameItemOrderDetail orderDetail = new GameItemOrderDetail();
        orderDetail.setItemImage("/uploads/images/snapshot.png");
        Map<String, Object> payload = new LinkedHashMap<>();

        TradeDispatchCoordinator.appendItemRecognitionImage(payload, item, orderDetail);

        assertEquals("/uploads/images/current.png", payload.get("recognition_image_url"));
    }

    @Test
    void fallsBackToOrderImageSnapshotWhenCurrentItemHasNoImage() {
        GameItemOrderDetail orderDetail = new GameItemOrderDetail();
        orderDetail.setItemImage("/uploads/images/snapshot.png");
        Map<String, Object> payload = new LinkedHashMap<>();

        TradeDispatchCoordinator.appendItemRecognitionImage(payload, null, orderDetail);

        assertEquals("/uploads/images/snapshot.png", payload.get("recognition_image_url"));
    }
}
