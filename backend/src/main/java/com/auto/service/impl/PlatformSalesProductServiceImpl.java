package com.auto.service.impl;

import com.auto.entity.PlatformSalesProduct;
import com.auto.mapper.PlatformSalesProductMapper;
import com.auto.service.PlatformSalesProductService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.Collection;
import java.util.List;

@Service
public class PlatformSalesProductServiceImpl
        extends ServiceImpl<PlatformSalesProductMapper, PlatformSalesProduct>
        implements PlatformSalesProductService {

    @Override
    public IPage<PlatformSalesProduct> search(
            Integer websiteId,
            Integer platformAccountId,
            Integer gameId,
            String parseStatus,
            String keyword,
            Page<PlatformSalesProduct> page) {
        boolean hasStatus = parseStatus != null && !parseStatus.isBlank();
        boolean hasKeyword = keyword != null && !keyword.isBlank();
        LambdaQueryWrapper<PlatformSalesProduct> query =
                new LambdaQueryWrapper<PlatformSalesProduct>()
                        .eq(websiteId != null,
                                PlatformSalesProduct::getWebsiteId,
                                websiteId)
                        .eq(platformAccountId != null,
                                PlatformSalesProduct::getPlatformAccountId,
                                platformAccountId)
                        .eq(gameId != null,
                                PlatformSalesProduct::getGameId,
                                gameId)
                        .eq(hasStatus,
                                PlatformSalesProduct::getParseStatus,
                                hasStatus ? parseStatus.trim() : null)
                        .and(hasKeyword, nested -> nested
                                .like(PlatformSalesProduct::getPlatformProductId,
                                        keyword.trim())
                                .or()
                                .like(PlatformSalesProduct::getTitle,
                                        keyword.trim())
                                .or()
                                .like(PlatformSalesProduct::getGameName,
                                        keyword.trim())
                                .or()
                                .like(PlatformSalesProduct::getRegionName,
                                        keyword.trim())
                                .or()
                                .like(PlatformSalesProduct::getParsedItemName,
                                        keyword.trim()))
                        .orderByDesc(PlatformSalesProduct::getUpdatedAt)
                        .orderByDesc(PlatformSalesProduct::getId);
        return page(page, query);
    }

    @Override
    public List<PlatformSalesProduct> findByAccountId(Integer accountId) {
        return list(new LambdaQueryWrapper<PlatformSalesProduct>()
                .eq(PlatformSalesProduct::getPlatformAccountId, accountId)
                .orderByAsc(PlatformSalesProduct::getPlatformProductId));
    }

    @Override
    public PlatformSalesProduct findByAccountIdAndProductId(
            Integer accountId, String platformProductId) {
        return getOne(new LambdaQueryWrapper<PlatformSalesProduct>()
                .eq(PlatformSalesProduct::getPlatformAccountId, accountId)
                .eq(PlatformSalesProduct::getPlatformProductId,
                        platformProductId), false);
    }

    @Override
    public int deleteMissing(
            Integer accountId, Collection<String> observedProductIds) {
        LambdaQueryWrapper<PlatformSalesProduct> query =
                new LambdaQueryWrapper<PlatformSalesProduct>()
                        .eq(PlatformSalesProduct::getPlatformAccountId,
                                accountId);
        if (observedProductIds != null && !observedProductIds.isEmpty()) {
            query.notIn(
                    PlatformSalesProduct::getPlatformProductId,
                    observedProductIds);
        }
        return baseMapper.delete(query);
    }
}
