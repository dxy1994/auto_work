package com.auto.service.impl;

import com.auto.entity.GameRegionInventory;
import com.auto.entity.GameRegionInventoryShopPrice;
import com.auto.entity.PlatformAccount;
import com.auto.mapper.GameRegionInventoryMapper;
import com.auto.mapper.GameRegionInventoryShopPriceMapper;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.PlatformAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class GameRegionInventoryShopPriceServiceImpl
        extends ServiceImpl<GameRegionInventoryShopPriceMapper, GameRegionInventoryShopPrice>
        implements GameRegionInventoryShopPriceService {

    private final GameRegionInventoryMapper inventoryMapper;
    private final PlatformAccountService accountService;

    public GameRegionInventoryShopPriceServiceImpl(GameRegionInventoryMapper inventoryMapper,
                                                    PlatformAccountService accountService) {
        this.inventoryMapper = inventoryMapper;
        this.accountService = accountService;
    }

    @Override
    public GameRegionInventoryShopPrice findByInventoryIdAndAccountId(Integer inventoryId, Integer accountId) {
        return getOne(new LambdaQueryWrapper<GameRegionInventoryShopPrice>()
                .eq(GameRegionInventoryShopPrice::getInventoryId, inventoryId)
                .eq(GameRegionInventoryShopPrice::getAccountId, accountId)
                .eq(GameRegionInventoryShopPrice::getIsActive, 1), false);
    }

    @Override
    public List<GameRegionInventoryShopPrice> findByInventoryId(Integer inventoryId) {
        return list(new LambdaQueryWrapper<GameRegionInventoryShopPrice>()
                .eq(GameRegionInventoryShopPrice::getInventoryId, inventoryId)
                .eq(GameRegionInventoryShopPrice::getIsActive, 1));
    }

    @Override
    public List<GameRegionInventoryShopPrice> findByAccountId(Integer accountId) {
        return list(new LambdaQueryWrapper<GameRegionInventoryShopPrice>()
                .eq(GameRegionInventoryShopPrice::getAccountId, accountId)
                .eq(GameRegionInventoryShopPrice::getIsActive, 1));
    }

    @Override
    @Transactional
    public void initForInventory(Integer inventoryId) {
        GameRegionInventory inv = inventoryMapper.selectById(inventoryId);
        if (inv == null) return;

        List<PlatformAccount> accounts = accountService.findAllActive();
        for (PlatformAccount acc : accounts) {
            GameRegionInventoryShopPrice existing = findByInventoryIdAndAccountId(inventoryId, acc.getId());
            if (existing != null) continue;

            GameRegionInventoryShopPrice sp = new GameRegionInventoryShopPrice();
            sp.setInventoryId(inventoryId);
            sp.setAccountId(acc.getId());
            sp.setSellingPrice(java.math.BigDecimal.ZERO);
            sp.setMinSellingPrice(java.math.BigDecimal.ZERO);
            sp.setMaxSellingPrice(java.math.BigDecimal.ZERO);
            save(sp);
        }
    }

    @Override
    @Transactional
    public void initForAccount(Integer accountId) {
        List<PlatformAccount> accounts = accountService.findAllActive();
        boolean exists = accounts.stream().anyMatch(a -> a.getId().equals(accountId));
        if (!exists) return;

        List<GameRegionInventory> allInv = inventoryMapper.selectList(
                new LambdaQueryWrapper<GameRegionInventory>()
                        .eq(GameRegionInventory::getIsActive, 1));

        for (GameRegionInventory inv : allInv) {
            GameRegionInventoryShopPrice existing = findByInventoryIdAndAccountId(inv.getId(), accountId);
            if (existing != null) continue;

            GameRegionInventoryShopPrice sp = new GameRegionInventoryShopPrice();
            sp.setInventoryId(inv.getId());
            sp.setAccountId(accountId);
            sp.setSellingPrice(java.math.BigDecimal.ZERO);
            sp.setMinSellingPrice(java.math.BigDecimal.ZERO);
            sp.setMaxSellingPrice(java.math.BigDecimal.ZERO);
            save(sp);
        }
    }
}
