package com.auto.controller;

import com.auto.entity.PlatformAccount;
import com.auto.service.CryptoService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.PlatformAccountService;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PlatformAccountControllerTest {

    @Test
    void revealPasswordDecryptsOneAccountAndDisablesCaching() {
        PlatformAccountService accountService = mock(PlatformAccountService.class);
        CryptoService crypto = mock(CryptoService.class);
        GameRegionInventoryShopPriceService shopPriceService =
                mock(GameRegionInventoryShopPriceService.class);
        PlatformAccountController controller =
                new PlatformAccountController(accountService, crypto, shopPriceService);
        PlatformAccount account = new PlatformAccount();
        account.setId(7);
        account.setPassword("encrypted-password");
        when(accountService.getById(7)).thenReturn(account);
        when(crypto.decrypt("encrypted-password")).thenReturn("plain-password");

        ResponseEntity<Map<String, String>> response =
                controller.revealPassword(7);

        assertEquals("plain-password", response.getBody().get("password"));
        assertTrue(response.getHeaders().getCacheControl().contains("no-store"));
    }
}
