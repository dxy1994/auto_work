package com.auto.service;

import com.auto.config.AppProperties;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

/**
 * AES-256-CBC 加解密服务。
 *
 * <p>与原 Python services/crypto.py 完全字节兼容：
 * <ul>
 *   <li>密钥 = SECRET_KEY 的 UTF-8 前 32 字节，不足右侧补 \0；</li>
 *   <li>加密：随机 16 字节 IV + PKCS7 填充，输出 Base64(iv + 密文)；</li>
 *   <li>解密：取前 16 字节为 IV，其余为密文。</li>
 * </ul>
 */
@Service
public class CryptoService {

    private final byte[] key;
    private final SecureRandom random = new SecureRandom();

    public CryptoService(AppProperties props) {
        byte[] raw = props.getSecretKey().getBytes(StandardCharsets.UTF_8);
        this.key = Arrays.copyOf(raw.length >= 32 ? Arrays.copyOf(raw, 32) : raw, 32);
        // Arrays.copyOf 对不足部分补 0，与 Python ljust(32, b"\0") 一致
    }

    public String encrypt(String plain) {
        try {
            byte[] iv = new byte[16];
            random.nextBytes(iv);
            Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            cipher.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv));
            byte[] encrypted = cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new IllegalStateException("加密失败: " + e.getMessage(), e);
        }
    }

    public String decrypt(String token) {
        try {
            byte[] raw = Base64.getDecoder().decode(token);
            byte[] iv = Arrays.copyOfRange(raw, 0, 16);
            byte[] encrypted = Arrays.copyOfRange(raw, 16, raw.length);
            Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv));
            byte[] data = cipher.doFinal(encrypted);
            return new String(data, StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new IllegalStateException("解密失败: " + e.getMessage(), e);
        }
    }
}
