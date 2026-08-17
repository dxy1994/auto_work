package com.auto.whid.sdk;

import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.CRC32;

/** Stateless Wireless HID V1 frame encoder and decoder. */
public final class WirelessHidCodec {

    public static final int HEADER_SIZE = 16;
    public static final int MAX_PAYLOAD_SIZE = 64;
    private static final byte[] MAGIC = "WHID".getBytes(StandardCharsets.US_ASCII);

    private WirelessHidCodec() {
    }

    public static byte[] encode(
            WirelessHidMessageType type,
            long sequence,
            byte[] payload) {
        byte[] body = payload == null ? new byte[0] : payload;
        if (body.length > MAX_PAYLOAD_SIZE) {
            throw new IllegalArgumentException("TCP 负载不能超过 64 字节");
        }
        if (sequence < 0 || sequence > 0xFFFF_FFFFL) {
            throw new IllegalArgumentException("sequence 必须是 uint32");
        }

        ByteBuffer buffer = ByteBuffer.allocate(HEADER_SIZE + body.length)
                .order(ByteOrder.LITTLE_ENDIAN);
        buffer.put(MAGIC);
        buffer.put((byte) 1);
        buffer.put((byte) type.code());
        buffer.putShort((short) body.length);
        buffer.putInt((int) sequence);
        buffer.putInt((int) crc32(body));
        buffer.put(body);
        return buffer.array();
    }

    public static WirelessHidFrame read(InputStream input) throws IOException {
        byte[] header = readExactly(input, HEADER_SIZE);
        if (!Arrays.equals(MAGIC, Arrays.copyOfRange(header, 0, 4))) {
            throw new WirelessHidException("响应帧 Magic 不是 WHID");
        }

        ByteBuffer buffer = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN);
        buffer.position(4);
        int version = Byte.toUnsignedInt(buffer.get());
        if (version != 1) {
            throw new WirelessHidException("不支持的协议版本: " + version);
        }
        WirelessHidMessageType type =
                WirelessHidMessageType.fromCode(Byte.toUnsignedInt(buffer.get()));
        int length = Short.toUnsignedInt(buffer.getShort());
        if (length > MAX_PAYLOAD_SIZE) {
            throw new WirelessHidException("响应帧负载超过 64 字节");
        }
        long sequence = Integer.toUnsignedLong(buffer.getInt());
        long expectedCrc = Integer.toUnsignedLong(buffer.getInt());
        byte[] payload = readExactly(input, length);
        long actualCrc = crc32(payload);
        if (actualCrc != expectedCrc) {
            throw new WirelessHidException(
                    "响应帧 CRC32 错误: expected=%08X actual=%08X"
                            .formatted(expectedCrc, actualCrc));
        }
        return new WirelessHidFrame(type, sequence, payload);
    }

    public static WirelessHidFrame decode(byte[] frame) throws IOException {
        if (frame == null) {
            throw new IllegalArgumentException("frame 不能为空");
        }
        java.io.ByteArrayInputStream input = new java.io.ByteArrayInputStream(frame);
        WirelessHidFrame decoded = read(input);
        if (input.available() != 0) {
            throw new WirelessHidException("帧尾存在多余字节");
        }
        return decoded;
    }

    public static long crc32(byte[] payload) {
        if (payload == null || payload.length == 0) {
            return 0;
        }
        CRC32 crc = new CRC32();
        crc.update(payload);
        return crc.getValue();
    }

    private static byte[] readExactly(InputStream input, int length) throws IOException {
        byte[] result = input.readNBytes(length);
        if (result.length != length) {
            throw new EOFException("连接在读取完整 Wireless HID 帧前关闭");
        }
        return result;
    }
}
