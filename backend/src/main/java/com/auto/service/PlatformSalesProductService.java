package com.auto.service;

import com.auto.entity.PlatformSalesProduct;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.Collection;
import java.util.List;

public interface PlatformSalesProductService extends IService<PlatformSalesProduct> {

    IPage<PlatformSalesProduct> search(
            Integer websiteId,
            Integer platformAccountId,
            Integer gameId,
            String parseStatus,
            String keyword,
            Page<PlatformSalesProduct> page);

    List<PlatformSalesProduct> findByAccountId(Integer accountId);

    PlatformSalesProduct findByAccountIdAndProductId(
            Integer accountId, String platformProductId);

    int deleteMissing(Integer accountId, Collection<String> observedProductIds);
}
