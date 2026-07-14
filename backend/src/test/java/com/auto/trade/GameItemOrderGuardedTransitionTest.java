package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.mapper.GameItemOrderMapper;
import com.auto.service.impl.GameItemOrderServiceImpl;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.junit.jupiter.api.Test;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.mockito.ArgumentCaptor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GameItemOrderGuardedTransitionTest {

    @Test
    void updateConditionIncludesCurrentRowVersion() {
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(new MybatisConfiguration(), "test"),
                GameItemOrder.class);
        GameItemOrderMapper mapper = mock(GameItemOrderMapper.class);
        TestService service = new TestService();
        service.useMapper(mapper);
        GameItemOrder current = new GameItemOrder();
        current.setId(55);
        current.setDeliveryStatus("offered");
        current.setRowVersion(4);
        when(mapper.selectById(55)).thenReturn(current);
        when(mapper.update(isNull(), any())).thenReturn(1);

        service.updateDeliveryStatus(55, "offered", "assigned", "a-1");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Wrapper<GameItemOrder>> wrapperCaptor =
                ArgumentCaptor.forClass(Wrapper.class);
        verify(mapper).update(isNull(), wrapperCaptor.capture());
        assertThat(wrapperCaptor.getValue().getSqlSegment()).contains("row_version");
    }

    private static final class TestService extends GameItemOrderServiceImpl {
        void useMapper(GameItemOrderMapper mapper) {
            this.baseMapper = mapper;
        }
    }
}
