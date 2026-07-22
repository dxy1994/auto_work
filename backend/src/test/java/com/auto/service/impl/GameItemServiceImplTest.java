package com.auto.service.impl;

import com.auto.entity.GameItem;
import com.auto.service.ItemBundleRelationService;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;

class GameItemServiceImplTest {

    @Test
    void prefersAnActiveCodeMatchWithoutQueryingByName() {
        GameItemServiceImpl service = spy(new GameItemServiceImpl(mock(ItemBundleRelationService.class)));
        GameItem matchedByCode = new GameItem();
        matchedByCode.setIsActive(1);

        doReturn(matchedByCode).when(service).findByGameIdAndCode(7, "游戏币");

        assertSame(matchedByCode, service.findActiveByGameIdAndCodeOrName(7, "游戏币"));
        verify(service, never()).findByGameIdAndName(7, "游戏币");
    }

    @Test
    void fallsBackToAnActiveNameMatch() {
        GameItemServiceImpl service = spy(new GameItemServiceImpl(mock(ItemBundleRelationService.class)));
        GameItem matchedByName = new GameItem();

        doReturn(null).when(service).findByGameIdAndCode(7, "ADENA");
        doReturn(matchedByName).when(service).findByGameIdAndName(7, "ADENA");

        assertSame(matchedByName, service.findActiveByGameIdAndCodeOrName(7, "ADENA"));
        verify(service).findByGameIdAndName(7, "ADENA");
    }

    @Test
    void returnsNullWhenNeitherNameNorCodeMatches() {
        GameItemServiceImpl service = spy(new GameItemServiceImpl(mock(ItemBundleRelationService.class)));

        doReturn(null).when(service).findByGameIdAndCode(7, "不存在");
        doReturn(null).when(service).findByGameIdAndName(7, "不存在");

        assertNull(service.findActiveByGameIdAndCodeOrName(7, "不存在"));
    }

    @Test
    void fallsBackToNameWhenCodeMatchIsInactive() {
        GameItemServiceImpl service = spy(new GameItemServiceImpl(mock(ItemBundleRelationService.class)));
        GameItem inactiveItem = new GameItem();
        inactiveItem.setIsActive(0);
        GameItem matchedByName = new GameItem();

        doReturn(inactiveItem).when(service).findByGameIdAndCode(7, "停用编码");
        doReturn(matchedByName).when(service).findByGameIdAndName(7, "停用编码");

        assertSame(matchedByName, service.findActiveByGameIdAndCodeOrName(7, "停用编码"));
    }
}
