package com.auto.config;


import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.cfg.CoercionAction;
import tools.jackson.databind.cfg.CoercionInputShape;
import tools.jackson.databind.type.LogicalType;

/**
 * Jackson 公共定制：
 * <ul>
 *   <li>布尔 → 数字容错转换（true→1，false→0），覆盖所有数字逻辑类型</li>
 *   <li>日期格式由 application.yml 中 spring.jackson.* 配置统一管理</li>
 * </ul>
 */
@Configuration
public class JacksonConfig {

    @Bean
    public JsonMapperBuilderCustomizer booleanToNumberCoercion() {
        return builder -> {
            // 针对 Integer / Float 显式配置；额外添加默认兜底配置
            builder.withCoercionConfig(LogicalType.Integer,
                    config -> config.setCoercion(CoercionInputShape.Boolean, CoercionAction.TryConvert));
            builder.withCoercionConfig(LogicalType.Float,
                    config -> config.setCoercion(CoercionInputShape.Boolean, CoercionAction.TryConvert));
            builder.withCoercionConfigDefaults(
                    config -> config.setCoercion(CoercionInputShape.Boolean, CoercionAction.TryConvert));
        };
    }
}
