package com.auto.whid.sdk;

import java.util.HashMap;
import java.util.Map;

/** USB HID Boot Keyboard usage helpers for test typing. */
public final class HidKeyboard {

    public static final int LEFT_CTRL = 0x01;
    public static final int LEFT_SHIFT = 0x02;
    public static final int LEFT_ALT = 0x04;
    public static final int LEFT_GUI = 0x08;

    private static final Map<Character, Keystroke> ASCII = buildAsciiMap();

    private HidKeyboard() {
    }

    public static Keystroke forCharacter(char character) {
        Keystroke keystroke = ASCII.get(character);
        if (keystroke == null) {
            throw new IllegalArgumentException(
                    "当前键盘映射不支持字符 U+%04X；仅支持常用 ASCII 文本"
                            .formatted((int) character));
        }
        return keystroke;
    }

    private static Map<Character, Keystroke> buildAsciiMap() {
        Map<Character, Keystroke> map = new HashMap<>();
        for (char character = 'a'; character <= 'z'; character++) {
            int usage = 0x04 + character - 'a';
            map.put(character, new Keystroke(0, usage));
            map.put(Character.toUpperCase(character), new Keystroke(LEFT_SHIFT, usage));
        }

        String digits = "1234567890";
        String shiftedDigits = "!@#$%^&*()";
        for (int index = 0; index < digits.length(); index++) {
            int usage = 0x1E + index;
            map.put(digits.charAt(index), new Keystroke(0, usage));
            map.put(shiftedDigits.charAt(index), new Keystroke(LEFT_SHIFT, usage));
        }

        map.put('\n', new Keystroke(0, 0x28));
        map.put('\r', new Keystroke(0, 0x28));
        map.put('\t', new Keystroke(0, 0x2B));
        map.put(' ', new Keystroke(0, 0x2C));
        addPair(map, '-', '_', 0x2D);
        addPair(map, '=', '+', 0x2E);
        addPair(map, '[', '{', 0x2F);
        addPair(map, ']', '}', 0x30);
        addPair(map, '\\', '|', 0x31);
        addPair(map, ';', ':', 0x33);
        addPair(map, '\'', '"', 0x34);
        addPair(map, '`', '~', 0x35);
        addPair(map, ',', '<', 0x36);
        addPair(map, '.', '>', 0x37);
        addPair(map, '/', '?', 0x38);
        return Map.copyOf(map);
    }

    private static void addPair(
            Map<Character, Keystroke> map,
            char normal,
            char shifted,
            int usage) {
        map.put(normal, new Keystroke(0, usage));
        map.put(shifted, new Keystroke(LEFT_SHIFT, usage));
    }

    public record Keystroke(int modifier, int usageId) {
    }
}
