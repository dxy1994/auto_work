package com.auto.entity;

import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

/** 套装子物品视图对象（含数量）。 */
@Getter
@Setter
public class BundleChildVO {
    private Integer id;
    private String code;
    private String name;
    private String image;
    private BigDecimal price;
    private String category;
    private Integer sortOrder;
    private Integer quantity;

    public static BundleChildVO from(GameItem item, Integer quantity) {
        BundleChildVO vo = new BundleChildVO();
        vo.setId(item.getId());
        vo.setCode(item.getCode());
        vo.setName(item.getName());
        vo.setImage(item.getImage());
        vo.setPrice(item.getPrice());
        vo.setCategory(item.getCategory());
        vo.setSortOrder(item.getSortOrder());
        vo.setQuantity(quantity);
        return vo;
    }
}
