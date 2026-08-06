package com.auto.trade;

import java.math.BigDecimal;
import java.util.OptionalLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 解析平台库存文本；文本含范围时返回其中最大的库存值。 */
public final class MarketplaceQuantityParser {

    private static final String UNIT_CHARS = "조억만천백십兆亿億万萬千百十";
    private static final Pattern AMOUNT = Pattern.compile(
            "(?:(?:\\d[\\d,]*(?:\\.\\d+)?)?\\s*["
                    + UNIT_CHARS + "]\\s*)+|\\d[\\d,]*(?:\\.\\d+)?");

    private MarketplaceQuantityParser() {
    }

    /**
     * 解析数量文本。诸如“最少 1 最大 43”或“1~43”的范围取 43；
     * “99亿”“10万”等单位会换算为实际整数库存。
     */
    public static OptionalLong parseMaximum(String text) {
        String normalized = normalizeDigits(text);
        if (normalized.isBlank()) {
            return OptionalLong.empty();
        }
        Matcher matcher = AMOUNT.matcher(normalized);
        Long maximum = null;
        while (matcher.find()) {
            try {
                long value = parseAmount(matcher.group()).longValueExact();
                if (value >= 0 && (maximum == null || value > maximum)) {
                    maximum = value;
                }
            } catch (ArithmeticException | NumberFormatException ignored) {
                // 跳过小数库存、超出 BIGINT 范围或格式异常的候选值。
            }
        }
        return maximum == null
                ? OptionalLong.empty() : OptionalLong.of(maximum);
    }

    private static BigDecimal parseAmount(String raw) {
        String value = raw.replace(",", "").replaceAll("\\s+", "");
        if (!containsUnit(value)) {
            return new BigDecimal(value);
        }

        BigDecimal total = BigDecimal.ZERO;
        BigDecimal section = BigDecimal.ZERO;
        BigDecimal pending = null;
        int index = 0;
        while (index < value.length()) {
            int start = index;
            while (index < value.length()
                    && (Character.isDigit(value.charAt(index))
                    || value.charAt(index) == '.')) {
                index++;
            }
            if (index > start) {
                pending = new BigDecimal(value.substring(start, index));
            }
            if (index >= value.length()) {
                break;
            }

            char unit = value.charAt(index++);
            BigDecimal multiplier = multiplier(unit);
            if (isMajorUnit(unit)) {
                BigDecimal sectionValue = pending == null
                        ? section : section.add(pending);
                if (sectionValue.signum() == 0) {
                    sectionValue = BigDecimal.ONE;
                }
                total = total.add(sectionValue.multiply(multiplier));
                section = BigDecimal.ZERO;
            } else {
                BigDecimal coefficient = pending == null
                        ? BigDecimal.ONE : pending;
                section = section.add(coefficient.multiply(multiplier));
            }
            pending = null;
        }
        return total.add(section).add(
                pending == null ? BigDecimal.ZERO : pending);
    }

    private static boolean containsUnit(String value) {
        for (int i = 0; i < value.length(); i++) {
            if (UNIT_CHARS.indexOf(value.charAt(i)) >= 0) {
                return true;
            }
        }
        return false;
    }

    private static boolean isMajorUnit(char unit) {
        return "조억만兆亿億万萬".indexOf(unit) >= 0;
    }

    private static BigDecimal multiplier(char unit) {
        return switch (unit) {
            case '조', '兆' -> new BigDecimal("1000000000000");
            case '억', '亿', '億' -> new BigDecimal("100000000");
            case '만', '万', '萬' -> new BigDecimal("10000");
            case '천', '千' -> new BigDecimal("1000");
            case '백', '百' -> new BigDecimal("100");
            case '십', '十' -> BigDecimal.TEN;
            default -> throw new NumberFormatException("unsupported unit");
        };
    }

    private static String normalizeDigits(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder normalized = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) {
            char value = text.charAt(i);
            if (value >= '０' && value <= '９') {
                normalized.append((char) ('0' + value - '０'));
            } else if (value == '，') {
                normalized.append(',');
            } else if (value == '．') {
                normalized.append('.');
            } else {
                normalized.append(value);
            }
        }
        return normalized.toString();
    }
}
