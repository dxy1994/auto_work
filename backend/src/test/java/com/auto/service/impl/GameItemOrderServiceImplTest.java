package com.auto.service.impl;

import com.auto.entity.GameItemOrder;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;

class GameItemOrderServiceImplTest {

    @Test
    @SuppressWarnings({"rawtypes", "unchecked"})
    void searchAppliesOrderAndDeliveryStatusFiltersTogether() {
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(new MybatisConfiguration(), "test"),
                GameItemOrder.class);
        GameItemOrderServiceImpl service = spy(new GameItemOrderServiceImpl());
        Page<GameItemOrder> page = new Page<>(1, 20);
        doReturn(page).when(service).page(eq(page), any());

        service.search(7, "abnormal", "greeting", null, page);

        ArgumentCaptor<Wrapper> wrapper = ArgumentCaptor.forClass(Wrapper.class);
        verify(service).page(eq(page), wrapper.capture());
        String sql = wrapper.getValue().getSqlSegment();
        assertTrue(sql.contains("status"));
        assertTrue(sql.contains("delivery_status"));
    }
}
