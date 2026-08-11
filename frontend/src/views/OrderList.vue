<template>
  <div class="page-container">
    <section class="order-directory">
      <header class="order-directory__header">
        <div class="order-directory__intro">
          <span class="order-directory__eyebrow">交易流水</span>
          <div class="order-directory__title-line">
            <h1>订单管理</h1>
            <span class="order-directory__count">{{ total }} 笔</span>
          </div>
          <p>按平台订单跟踪商品、买家和自动交付进度。</p>
        </div>
        <div :class="['order-live', { 'is-active': autoRefreshEnabled }]">
          <span class="order-live__dot" aria-hidden="true"></span>
          <span class="order-live__state">{{ autoRefreshEnabled ? '自动刷新中' : '自动刷新已暂停' }}</span>
          <el-input-number v-model="refreshIntervalSeconds" :min="1" :max="3600" :step="1" size="small" controls-position="right" aria-label="自动刷新间隔秒数" />
          <span class="order-live__unit">秒</span>
          <el-button size="small" text :type="autoRefreshEnabled ? 'danger' : 'success'" @click="toggleAutoRefresh">
            <el-icon><RefreshRight /></el-icon>{{ autoRefreshEnabled ? '暂停' : '开启' }}
          </el-button>
        </div>
      </header>

      <div class="order-filters">
        <div class="order-filters__fields">
          <el-select v-model="filterWebsiteId" class="order-filter order-filter--website" placeholder="全部平台" clearable filterable @change="handleSearch">
            <el-option v-for="website in websiteList" :key="website.id" :label="website.name" :value="website.id" />
          </el-select>
          <el-select v-model="filterGameId" class="order-filter order-filter--game" placeholder="全部游戏" clearable filterable @change="handleSearch">
            <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <el-select v-model="filterStatus" class="order-filter" placeholder="订单状态" clearable @change="handleSearch">
            <el-option label="待分配" value="pending" />
            <el-option label="已分配" value="assigned" />
            <el-option label="处理中" value="processing" />
            <el-option label="异常" value="abnormal" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
          <el-select v-model="filterDeliveryStatus" class="order-filter order-filter--delivery" placeholder="交付进度" clearable @change="handleSearch">
            <el-option label="招呼阶段" value="greeting" />
            <el-option label="排队中" value="queued" />
            <el-option label="等待指派" value="waiting_assignment" />
            <el-option label="已发送指派" value="offered" />
            <el-option label="交易执行中" value="assigned" />
            <el-option label="等待网站确认" value="wait_web_confirm" />
            <el-option label="待人工复核" value="review_required" />
            <el-option label="已挂起" value="suspended" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
          <div class="order-filter-date-wrap">
            <el-date-picker
              v-model="filterCreatedRange"
              class="order-filter--date"
              type="datetimerange"
              value-format="YYYY-MM-DD HH:mm:ss"
              format="YYYY-MM-DD HH:mm"
              range-separator="至"
              start-placeholder="创建开始时间"
              end-placeholder="创建结束时间"
              @change="handleSearch"
            />
          </div>
        </div>
        <div class="order-filters__tools">
          <el-input v-model="keyword" class="order-search" placeholder="订单号 / 商品 / 客户 / 角色" clearable @keyup.enter="handleSearch" @clear="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button :disabled="!hasActiveFilters" @click="resetFilters">重置<span v-if="activeFilterCount"> · {{ activeFilterCount }}</span></el-button>
        </div>
      </div>

      <div ref="orderTableViewport" class="order-table-viewport">
      <el-table class="order-table" :data="list" border stripe height="100%" v-loading="loading" highlight-current-row :row-class-name="orderRowClassName" @current-change="onCurrentChange" @row-dblclick="openOrderLogs" row-key="id" aria-label="订单列表，双击订单行查看操作日志">
        <el-table-column label="平台订单" width="132">
          <template #default="{ row }">
            <div class="order-identity">
              <button type="button" class="order-identity__number" :title="row.source_order_no || '未提供平台订单号'" @click="openDetailDrawer(row)" @dblclick.stop>{{ compactOrderNo(row.source_order_no) }}</button>
              <div class="order-identity__meta">
                <span
                  class="order-platform-badge"
                  :style="platformBadgeStyle(row.website_id)"
                  :title="websiteNameMap[row.website_id] || '未知来源'"
                >
                  <span>{{ websiteNameMap[row.website_id] || '未知来源' }}</span>
                </span>
                <time :title="String(row.created_at || '')">{{ formatOrderTime(row.created_at) }}</time>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="商品与游戏" :width="orderColumnWidths.product">
          <template #default="{ row }">
            <div class="order-product">
              <strong :title="row.product_title || row.trade_item_name || row.remark || ''">{{ row.product_title || row.trade_item_name || row.remark || '未提供商品标题' }}</strong>
              <div class="order-product__meta">
                <el-tag size="small" effect="plain">{{ gameNameMap[row.game_id] || '未知游戏' }}</el-tag>
                <span v-if="row.trade_item_name" :title="row.trade_item_name">{{ row.trade_item_name }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="买家与资产" :width="orderColumnWidths.buyer">
          <template #default="{ row }">
            <div class="order-buyer">
              <strong :title="row.buyer_character || row.customer_name || ''">{{ row.buyer_character || row.customer_name || '未提供买家' }}</strong>
              <span :title="formatAssetSummary(row)">{{ formatAssetSummary(row) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="平台售价" width="168" align="right">
          <template #default="{ row }">
            <div class="order-price">
              <strong>{{ formatPlatformPrice(row.platform_price) }}</strong>
              <span v-if="row.quantity != null || row.sale_quantity != null">售出 {{ formatOrderQuantity(row.sale_quantity) }}/{{ formatOrderQuantity(row.quantity) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="订单进度" :width="orderColumnWidths.progress">
          <template #default="{ row }">
            <el-tooltip :content="orderErrorMessage(row) || retryActionLabel(row)" :disabled="!orderErrorMessage(row) && !row.retryable" placement="top">
              <div :class="['order-progress', `tone-${orderVisualTone(row)}`]">
                <div class="order-progress__main">
                  <i aria-hidden="true"></i>
                  <strong>{{ deliveryStatusLabel(row) }}</strong>
                </div>
                <div class="order-progress__meta">
                  <span>{{ orderStatusLabel(row.status) }}</span>
                  <span v-if="row.retryable">可重新尝试</span>
                </div>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="252" fixed="right" align="right" class-name="order-action-cell" label-class-name="order-action-header">
          <template #default="{ row }">
            <div class="order-row-actions" @dblclick.stop>
              <el-tooltip v-if="canRetryOrder(row)" :content="retryActionLabel(row)" placement="top">
                <el-button
                  size="small"
                  link
                  type="warning"
                  :loading="retryingOrderId === row.id"
                  :disabled="retryingOrderId !== null && retryingOrderId !== row.id"
                  @click.stop="handleRetryOrder(row)"
                >重新尝试</el-button>
              </el-tooltip>
              <el-popconfirm
                v-if="canCompleteOrder(row)"
                width="320"
                :title="completeConfirmTitle(row)"
                confirm-button-text="确认完成"
                cancel-button-text="返回"
                @confirm="handleTerminalOrder(row, 'complete')"
              >
                <template #reference>
                  <el-button
                    size="small"
                    link
                    type="success"
                    :loading="terminalActionKey === `complete:${row.id}`"
                    :disabled="Boolean(terminalActionKey) && terminalActionKey !== `complete:${row.id}`"
                  >{{ completeActionLabel(row) }}</el-button>
                </template>
              </el-popconfirm>
              <el-popconfirm
                v-if="canCancelOrder(row)"
                width="300"
                :title="cancelConfirmTitle(row)"
                confirm-button-text="确认取消"
                cancel-button-text="返回"
                @confirm="handleTerminalOrder(row, 'cancel')"
              >
                <template #reference>
                  <el-button
                    size="small"
                    link
                    type="danger"
                    :loading="terminalActionKey === `cancel:${row.id}`"
                    :disabled="Boolean(terminalActionKey) && terminalActionKey !== `cancel:${row.id}`"
                  >{{ cancelActionLabel(row) }}</el-button>
                </template>
              </el-popconfirm>
              <template v-if="orderOverflowActions(row).length < 4">
                <el-tooltip
                  v-for="action in orderOverflowActions(row)"
                  :key="action.command"
                  :content="action.label"
                  placement="top"
                >
                  <el-button
                    class="order-overflow-action"
                    size="small"
                    link
                    :type="overflowActionButtonType(action)"
                    :aria-label="action.label"
                    :loading="action.command === 'copy' && copyLoadingOrderId === row.id"
                    :disabled="action.disabled"
                    @click.stop="handleOrderCommand(row, action.command)"
                  >
                    <el-icon><component :is="action.icon" /></el-icon>
                  </el-button>
                </el-tooltip>
              </template>
              <el-dropdown v-else trigger="click" @command="handleOrderCommand(row, $event)">
                <el-button size="small" link type="primary">更多 <el-icon><ArrowDown /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="action in orderOverflowActions(row)"
                      :key="action.command"
                      :command="action.command"
                      :icon="action.icon"
                      :disabled="action.disabled"
                      :divided="action.divided"
                    >{{ action.label }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        <template #empty><el-empty :description="hasActiveFilters ? '没有匹配的订单' : '当前还没有订单'" :image-size="80" /></template>
      </el-table>
      </div>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="fetchList"
          @size-change="handlePageSizeChange"
        />
      </div>
    </section>

    <!-- 复制订单弹窗：复制业务信息，重置交易运行态 -->
    <el-dialog v-model="copyDialogVisible" title="复制订单" width="1080px" destroy-on-close top="4vh">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="copy-order-alert"
        title="新订单默认从“招呼已完成，等待交易指派”开始；交易指派、错误、截图及完成时间不会复制。"
      />
      <el-form :model="copyForm" label-width="110px" ref="copyFormRef" :rules="copyRules">
        <el-divider content-position="left">编号与初始状态</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="平台订单号" prop="source_order_no">
              <el-input v-model="copyForm.source_order_no" maxlength="100" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始步骤" prop="initial_state">
              <el-select v-model="copyForm.initial_state" style="width:100%">
                <el-option label="招呼已完成，等待交易指派" value="waiting_assignment" />
                <el-option label="等待/正在招呼" value="greeting" />
                <el-option label="订单刚入库" value="detected" />
                <el-option label="招呼阶段异常" value="greeting_abnormal" />
                <el-option label="已挂起" value="suspended" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">平台与商品信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="来源平台">
              <el-select v-model="copyForm.website_id" clearable style="width:100%" @change="onCopyWebsiteChange">
                <el-option v-for="w in websiteList" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="平台账号">
              <el-select v-model="copyForm.platform_account_id" clearable filterable style="width:100%">
                <el-option v-for="a in copyPlatformAccounts" :key="a.id" :label="a.label || a.username" :value="a.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="平台下单时间">
              <el-date-picker v-model="copyForm.platform_order_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="平台分类"><el-input v-model="copyForm.platform_item_type" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="平台售价"><el-input-number v-model="copyForm.platform_price" :min="0" :precision="2" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="商品标题"><el-input v-model="copyForm.product_title" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="交易物品"><el-input v-model="copyForm.trade_item_name" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="上架数量"><el-input-number v-model="copyForm.quantity" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="已售数量"><el-input-number v-model="copyForm.sale_quantity" :min="0" style="width:100%" /></el-form-item></el-col>
        </el-row>

        <el-divider content-position="left">游戏与交易信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="游戏" prop="game_id">
              <el-select v-model="copyForm.game_id" style="width:100%" @change="onCopyGameChange">
                <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="大区" prop="region_id">
              <el-select v-model="copyForm.region_id" filterable style="width:100%" @change="onCopyRegionChange">
                <el-option v-for="r in copyRegionList" :key="r.id" :label="r.name" :value="r.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="游戏账号">
              <el-select v-model="copyForm.game_account_id" clearable filterable style="width:100%">
                <el-option v-for="a in copyGameAccounts" :key="a.id" :label="a.account_name || a.nickname || a.account_no" :value="a.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="买家角色"><el-input v-model="copyForm.buyer_character" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="资产类型"><el-input v-model="copyForm.asset_type" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="交付数量"><el-input-number v-model="copyForm.asset_amount" :min="0" :precision="2" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="客户名称"><el-input v-model="copyForm.customer_name" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="联系方式"><el-input v-model="copyForm.customer_contact" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="备注"><el-input v-model="copyForm.remark" /></el-form-item></el-col>
        </el-row>
      </el-form>

      <el-divider content-position="left">订单明细</el-divider>
      <div class="detail-toolbar">
        <el-select v-model="newDetailItemId" placeholder="选择物品" filterable style="width: 260px">
          <el-option v-for="i in copyItemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="newDetailQty" :min="1" :max="9999" style="width:120px" />
        <el-input-number v-model="newDetailPrice" :min="0" :precision="2" placeholder="单价" style="width:130px" />
        <el-button type="primary" size="small" @click="addCopyDetailRow" :disabled="!newDetailItemId">添加明细</el-button>
      </div>
      <el-table :data="copyForm.details" border size="small" max-height="300" style="margin-top:10px">
        <el-table-column label="物品" min-width="180">
          <template #default="{ row }">
            <el-select v-model="row.item_id" filterable style="width:100%" @change="onCopyDetailItemChange(row)">
              <el-option v-for="i in copyItemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="105"><template #default="{ row }"><el-input-number v-model="row.quantity" :min="1" size="small" style="width:90px" @change="calcRowSubtotal(row)" /></template></el-table-column>
        <el-table-column label="单价" width="115"><template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" style="width:100px" @change="calcRowSubtotal(row)" /></template></el-table-column>
        <el-table-column label="进货价" width="115"><template #default="{ row }"><el-input-number v-model="row.purchase_price" :min="0" :precision="2" size="small" style="width:100px" /></template></el-table-column>
        <el-table-column label="出货价" width="115"><template #default="{ row }"><el-input-number v-model="row.selling_price" :min="0" :precision="2" size="small" style="width:100px" /></template></el-table-column>
        <el-table-column label="来源套装" min-width="130"><template #default="{ row }"><el-input v-model="row.bundle_name" size="small" /></template></el-table-column>
        <el-table-column label="备注" min-width="130"><template #default="{ row }"><el-input v-model="row.remark" size="small" /></template></el-table-column>
        <el-table-column label="小计" width="90" align="right"><template #default="{ row }">{{ Number(row.subtotal || 0).toFixed(2) }}</template></el-table-column>
        <el-table-column label="" width="55"><template #default="{ $index }"><el-button link type="danger" @click="copyForm.details.splice($index, 1)">删除</el-button></template></el-table-column>
      </el-table>
      <div class="total-line">合计：¥ {{ copyTotal }}</div>

      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="copySubmitting" @click="handleCopyOrder">创建复制订单</el-button>
      </template>
    </el-dialog>

    <!-- 订单明细抽屉（子表联动） -->
    <el-drawer v-model="detailDrawerVisible" :title="`订单明细 · ${compactOrderNo(currentOrder?.source_order_no)}`" size="min(860px, 92vw)" class="order-detail-drawer" destroy-on-close>
      <section class="detail-summary">
        <div class="detail-summary__top">
          <div class="detail-summary__identity">
            <span>{{ websiteNameMap[currentOrder?.website_id] || currentOrder?.website_id || '未知平台' }}</span>
            <h2>{{ currentOrder?.product_title || currentOrder?.trade_item_name || currentOrder?.remark || '未提供商品标题' }}</h2>
            <div class="detail-summary__meta">
              <code :title="currentOrder?.source_order_no || ''">{{ currentOrder?.source_order_no || '未提供平台订单号' }}</code>
              <time>{{ currentOrder?.platform_order_time || currentOrder?.created_at || '时间未记录' }}</time>
            </div>
          </div>
          <div :class="['order-progress', 'detail-summary__status', `tone-${orderVisualTone(currentOrder)}`]">
            <div class="order-progress__main">
              <i aria-hidden="true"></i>
              <strong>{{ deliveryStatusLabel(currentOrder) }}</strong>
            </div>
            <div class="order-progress__meta">
              <span>{{ orderStatusLabel(currentOrder?.status) }}</span>
              <span v-if="currentOrder?.retryable">可重新尝试</span>
            </div>
          </div>
        </div>
        <div class="detail-summary__metrics">
          <div>
            <span>平台售价</span>
            <strong>{{ formatPlatformPrice(currentOrder?.platform_price) }}</strong>
          </div>
          <div>
            <span>出售进度</span>
            <strong>{{ formatOrderQuantity(currentOrder?.sale_quantity) }}/{{ formatOrderQuantity(currentOrder?.quantity) }}</strong>
          </div>
          <div>
            <span>买家与交付</span>
            <strong>{{ currentOrder?.buyer_character || currentOrder?.customer_name || '未提供买家' }}</strong>
            <small>{{ formatAssetSummary(currentOrder) }}</small>
          </div>
        </div>
      </section>

      <div class="order-action-bar detail-primary-actions">
        <el-button type="primary" plain size="small" :loading="copyLoadingOrderId === currentOrder?.id" @click="openCopyDialog(currentOrder)">复制订单</el-button>
        <el-button type="primary" plain size="small" @click="openOrderLogs(currentOrder)">查看订单日志</el-button>
        <el-button type="primary" size="small" @click="openChatDialog(currentOrder)">发送聊天消息</el-button>
        <el-button v-if="canRetryOrder(currentOrder)" type="warning" size="small" :loading="retryingOrderId === currentOrder?.id" @click="handleRetryOrder(currentOrder, true)">
          <el-icon><RefreshRight /></el-icon> 重新尝试
        </el-button>
        <el-popconfirm
          v-if="canCompleteOrder(currentOrder)"
          width="320"
          :title="completeConfirmTitle(currentOrder)"
          confirm-button-text="确认完成"
          cancel-button-text="返回"
          @confirm="handleTerminalOrder(currentOrder, 'complete', true)"
        >
          <template #reference><el-button type="success" size="small">{{ completeActionLabel(currentOrder, true) }}</el-button></template>
        </el-popconfirm>
        <el-popconfirm
          v-if="canCancelOrder(currentOrder)"
          width="300"
          :title="cancelConfirmTitle(currentOrder)"
          confirm-button-text="确认取消"
          cancel-button-text="返回"
          @confirm="handleTerminalOrder(currentOrder, 'cancel', true)"
        >
          <template #reference><el-button type="warning" plain size="small">{{ cancelActionLabel(currentOrder, true) }}</el-button></template>
        </el-popconfirm>
      </div>

      <el-alert
        v-if="currentOrder?.last_error_code"
        class="detail-section"
        type="error"
        :closable="false"
        show-icon
        :title="deliveryStatusLabel(currentOrder)"
        :description="orderErrorMessage(currentOrder) || errorCodeLabel(currentOrder.last_error_code)"
      />
      <div class="retry-resume-info detail-section" v-if="currentOrder?.last_error_code && canRetryOrder(currentOrder)">
        <strong>重新尝试将执行：</strong>{{ retryActionLabel(currentOrder) }}
      </div>

      <section v-if="currentOrder?.game_trade_screenshot" class="detail-section game-trade-proof">
        <div class="game-trade-proof-title">
          <strong>游戏交易证据</strong>
          <span>最终确认前直传 RustFS 于 {{ currentOrder.game_trade_screenshot_at || '-' }}</span>
        </div>
        <el-image
          class="game-trade-proof-image"
          :src="currentOrder.game_trade_screenshot"
          :preview-src-list="[currentOrder.game_trade_screenshot]"
          fit="contain"
        />
        <div class="game-trade-proof-path">
          RustFS 路径：<code>{{ currentOrder.game_trade_screenshot }}</code>
        </div>
      </section>

      <section v-if="currentOrder?.buyer_review" class="detail-section buyer-review-detail">
        <div class="buyer-review-detail-title">
          <strong>交易客户 OCR 审核</strong>
          <el-tag :type="currentOrder.buyer_review.status === 'pending' ? 'danger' : 'info'">
            {{ buyerReviewStatusLabel(currentOrder.buyer_review.status) }}
          </el-tag>
        </div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="订单客户名">{{ currentOrder.buyer_review.expected_buyer || '-' }}</el-descriptions-item>
          <el-descriptions-item label="OCR 文字">{{ currentOrder.buyer_review.observed_buyer || '未识别' }}</el-descriptions-item>
          <el-descriptions-item label="OCR 置信度">{{ formatConfidence(currentOrder.buyer_review.ocr_confidence) }}</el-descriptions-item>
          <el-descriptions-item label="请求时间">{{ currentOrder.buyer_review.requested_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="处理时间" :span="2">{{ currentOrder.buyer_review.decided_at || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-image
          class="buyer-review-detail-image"
          :src="currentOrder.buyer_review.screenshot_data_url"
          :preview-src-list="[currentOrder.buyer_review.screenshot_data_url]"
          fit="contain"
        />
        <div v-if="currentOrder.buyer_review.status === 'pending'" class="buyer-review-detail-actions">
          <el-button type="danger" :loading="buyerReviewLoading" @click="handleBuyerReview(false)">不同意并拒绝申请</el-button>
          <el-button type="success" :loading="buyerReviewLoading" @click="handleBuyerReview(true)">同意并继续交易</el-button>
        </div>
      </section>

      <div class="detail-information-grid detail-section">
        <section class="detail-information-card">
          <header>
            <span>交易范围</span>
            <small>游戏与交付对象</small>
          </header>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="游戏">{{ gameNameMap[currentOrder?.game_id] || currentOrder?.game_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="大区">{{ currentOrder?.region_name || regionNameMap[currentOrder?.region_id] || currentOrder?.region_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="大区编码"><code class="region-code">{{ currentOrder?.region_code || regionCodeMap[currentOrder?.region_id] || '-' }}</code></el-descriptions-item>
            <el-descriptions-item label="交易物品">{{ currentOrder?.trade_item_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="资产类型">{{ currentOrder?.asset_type || '-' }}</el-descriptions-item>
            <el-descriptions-item label="平台分类">
              <el-tag size="small" v-if="currentOrder?.platform_item_type">{{ currentOrder.platform_item_type }}</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="detail-information-card">
          <header>
            <span>订单记录</span>
            <small>系统状态与时间</small>
          </header>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="订单状态"><el-tag :type="orderStatusType(currentOrder?.status)" size="small">{{ orderStatusLabel(currentOrder?.status) }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="客户 / 联系">{{ currentOrder?.customer_name || '-' }} · {{ currentOrder?.customer_contact || '-' }}</el-descriptions-item>
            <el-descriptions-item label="分配机器">{{ machineNameMap[currentOrder?.assigned_machine_id] || '-' }}</el-descriptions-item>
            <el-descriptions-item label="游戏交付">{{ currentOrder?.game_delivered_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="网站确认">{{ currentOrder?.website_confirmed_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="完成 / 创建">{{ currentOrder?.completed_at || '-' }} · {{ currentOrder?.created_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ currentOrder?.remark || '-' }}</el-descriptions-item>
            <el-descriptions-item v-if="currentOrder?.last_error_code" label="失败代码">
              <el-tag type="danger" size="small">{{ errorCodeLabel(currentOrder.last_error_code) }}</el-tag>
              <span class="error-code-text">{{ currentOrder.last_error_code }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </div>

      <div class="detail-list-heading">
        <div>
          <strong>订单明细</strong>
          <span>{{ detailList.length }} 条物品记录</span>
        </div>
      </div>
      <div v-if="currentOrder?.status === 'pending'" class="detail-toolbar">
        <el-select v-model="addDetailItemId" placeholder="选择物品添加" filterable style="width: 200px">
          <el-option v-for="i in detailItemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="addDetailQty" :min="1" :max="9999" size="default" style="width:110px" />
        <el-button type="primary" size="small" @click="handleAddDetail" :disabled="!addDetailItemId">添加</el-button>
      </div>
      <el-table class="detail-items-table" :data="detailList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id" empty-text="暂无物品明细">
        <el-table-column label="物品" min-width="240">
          <template #default="{ row }">
            <div class="detail-line-item">
              <el-image v-if="row.item_image" :src="row.item_image" :preview-src-list="[row.item_image]" fit="cover" />
              <div v-else class="detail-line-item__placeholder">无图</div>
              <div>
                <strong :title="row.item_name || ''">{{ row.item_name || '未命名物品' }}</strong>
                <el-tag v-if="row.bundle_name" size="small" type="info" effect="plain">{{ row.bundle_name }}</el-tag>
                <small v-else>未关联来源套装</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="112" align="right">
          <template #default="{ row }"><strong class="detail-line-quantity">{{ formatOrderQuantity(row.quantity) }}</strong></template>
        </el-table-column>
        <el-table-column label="价格信息" width="185">
          <template #default="{ row }">
            <div class="detail-line-prices">
              <strong>单价 {{ Number(row.unit_price || 0).toFixed(2) }}</strong>
              <span>进 {{ row.purchase_price != null ? Number(row.purchase_price).toFixed(2) : '-' }}</span>
              <span>出 {{ row.selling_price != null ? Number(row.selling_price).toFixed(2) : '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="subtotal" label="小计" width="90" align="right">
          <template #default="{ row }"><strong class="detail-line-subtotal">{{ Number(row.subtotal || 0).toFixed(2) }}</strong></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="detailStatusType(row.status)" size="small">{{ detailStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" align="center" v-if="currentOrder?.status === 'pending'">
          <template #default="{ row }">
            <el-popconfirm title="确认删除？" @confirm="handleDeleteDetail(row.id)">
              <template #reference><el-button size="small" link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 订单客户聊天 -->
    <el-dialog
      v-model="chatDialogVisible"
      title="发送订单聊天消息"
      width="760px"
      append-to-body
      destroy-on-close
      top="4vh"
    >
      <div class="chat-target">
        <div>
          <span class="chat-target-label">发送给</span>
          <strong>{{ chatOrder?.customer_name || chatOrder?.buyer_character || '订单客户' }}</strong>
        </div>
        <div class="chat-target-meta">
          <span>{{ websiteNameMap[chatOrder?.website_id] || `平台 ${chatOrder?.website_id || '-'}` }}</span>
          <span>平台订单号 {{ chatOrder?.source_order_no || '-' }}</span>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        class="chat-order-tip"
        title="消息会按下方顺序逐条发送；同一条中的图片先发送，随后发送文字。"
      />

      <div class="chat-message-list">
        <article v-for="(message, index) in chatMessages" :key="message._key" class="chat-message-card">
          <header class="chat-message-header">
            <div class="chat-message-index">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <strong>消息 {{ index + 1 }}</strong>
                <small>{{ chatMessageTypeLabel(message) }}</small>
              </div>
            </div>
            <div class="chat-message-actions">
              <el-button size="small" text :disabled="index === 0" @click="moveChatMessage(index, -1)">上移</el-button>
              <el-button size="small" text :disabled="index === chatMessages.length - 1" @click="moveChatMessage(index, 1)">下移</el-button>
              <el-button size="small" text type="danger" :disabled="chatMessages.length === 1" @click="removeChatMessage(index)">删除</el-button>
            </div>
          </header>

          <el-input
            v-model="message.content"
            type="textarea"
            :rows="3"
            maxlength="5000"
            show-word-limit
            resize="vertical"
            placeholder="输入要发送给该订单客户的文字（可只发图片）"
          />

          <div class="chat-image-row">
            <div v-for="(imageUrl, imageIndex) in message.image_urls" :key="imageUrl" class="chat-image-tile">
              <el-image :src="imageUrl" :preview-src-list="message.image_urls" fit="cover" />
              <button type="button" aria-label="移除图片" @click="removeChatImage(message, imageIndex)">×</button>
            </div>
            <el-upload
              class="chat-image-upload"
              accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
              multiple
              :auto-upload="false"
              :show-file-list="false"
              :disabled="message._uploading > 0 || message.image_urls.length >= 30"
              :on-change="file => handleChatImageChange(message, file)"
            >
              <div class="chat-image-add" :class="{ 'is-loading': message._uploading > 0 }">
                <span>{{ message._uploading > 0 ? '上传中…' : '+' }}</span>
                <small>{{ message._uploading > 0 ? '请稍候' : '添加图片' }}</small>
              </div>
            </el-upload>
          </div>
        </article>
      </div>

      <el-button
        class="chat-add-message"
        plain
        :disabled="chatMessages.length >= 30"
        @click="addChatMessage"
      >+ 添加下一条消息</el-button>

      <template #footer>
        <div class="chat-dialog-footer">
          <span>共 {{ chatMessages.length }} 条，{{ chatImageCount }} 张图片</span>
          <div>
            <el-button @click="chatDialogVisible = false">取消</el-button>
            <el-button
              type="primary"
              :loading="chatSending"
              :disabled="chatUploadCount > 0"
              @click="handleSendChat"
            >发送给客户</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 订单自动交付日志 -->
    <el-dialog
      v-model="orderLogsDialogVisible"
      :title="`订单日志 · ${orderLogTarget?.source_order_no || '未提供平台订单号'}`"
      width="780px"
      append-to-body
      destroy-on-close
    >
      <div class="order-log-toolbar">
        <div>
          <strong>{{ orderLogTotal }}</strong> 条关联事件
          <span v-if="orderLogTotal > orderLogs.length">（显示最新 {{ orderLogs.length }} 条）</span>
        </div>
        <el-button size="small" :loading="orderLogsLoading" @click="fetchOrderLogs">刷新</el-button>
      </div>

      <div class="order-log-body" v-loading="orderLogsLoading && !orderLogs.length">
        <el-empty v-if="!orderLogsLoading && !orderLogs.length" description="该订单还没有自动交付日志" :image-size="80" />
        <el-timeline v-else class="order-log-timeline">
          <el-timeline-item
            v-for="item in orderLogs"
            :key="item.id"
            :timestamp="formatOrderLogTime(item.created_at)"
            :type="orderLogType(item.event_type)"
            placement="top"
          >
            <div class="order-log-card">
              <div class="order-log-heading">
                <strong>{{ orderLogLabel(item.event_type) }}</strong>
                <el-tag size="small" effect="plain">{{ item.event_type || 'unknown' }}</el-tag>
              </div>
              <div v-if="item.from_status || item.to_status" class="order-log-transition">
                {{ deliveryStateText(item.from_status) }}
                <span>→</span>
                {{ deliveryStateText(item.to_status) }}
              </div>
              <p class="order-log-message">{{ item.message || '未记录说明' }}</p>
              <div v-if="item.assignment_id" class="order-log-meta">
                指派编号：<span>{{ item.assignment_id }}</span>
              </div>
              <el-collapse v-if="item.payload && Object.keys(item.payload).length" class="order-log-payload">
                <el-collapse-item title="查看附加数据">
                  <pre>{{ formatOrderLogPayload(item.payload) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, CopyDocument, Delete, RefreshRight } from '@element-plus/icons-vue'
import {
  getAllGames, getAllRegions, getAllMachines, getAllItems, getAllWebsites,
  getAllAccounts, getAllGameAccounts,
  getOrders, getOrder, getOrderLogs, copyOrder, deleteOrder,
  addOrderDetail, deleteOrderDetail, retryOrder, completeOrder, cancelOrder,
  sendOrderChat, uploadFile,
  decideBuyerReview as submitBuyerReview,
} from '../api'

const gameList = ref([])
const allRegions = ref([])
const machineList = ref([])
const allItems = ref([])
const websiteList = ref([])
const platformAccountList = ref([])
const gameAccountList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const filterWebsiteId = ref(null)
const filterGameId = ref(null)
const filterStatus = ref('')
const filterDeliveryStatus = ref('')
const filterCreatedRange = ref([])
const loading = ref(false)
const route = useRoute()
const orderTableViewport = ref(null)
const orderTableWidth = ref(1018)
let orderTableResizeObserver = null

const orderColumnWidths = computed(() => {
  const extraWidth = Math.max(0, Math.floor(orderTableWidth.value) - 1018)
  const productExtra = Math.round(extraWidth * 0.5)
  const buyerExtra = Math.round(extraWidth * 0.25)
  return {
    product: 166 + productExtra,
    buyer: 130 + buyerExtra,
    progress: 170 + extraWidth - productExtra - buyerExtra,
  }
})

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.name])))
const regionCodeMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.code])))
const machineNameMap = computed(() => Object.fromEntries(machineList.value.map(m => [m.id, m.name || m.mac_address])))
const websiteNameMap = computed(() => Object.fromEntries(websiteList.value.map(w => [w.id, w.name])))
const platformPalette = [
  { color: '#2563a9', background: '#edf5ff', border: '#bfd8f5', dot: '#4086d8' },
  { color: '#7651a8', background: '#f5f0fc', border: '#d8c8ed', dot: '#956fca' },
  { color: '#98601f', background: '#fff5e6', border: '#efd4a9', dot: '#d38a2d' },
  { color: '#16756c', background: '#edf8f6', border: '#bce0da', dot: '#2b9b8f' },
  { color: '#a24c69', background: '#fff0f5', border: '#ebc7d4', dot: '#cf6d8d' },
  { color: '#52657d', background: '#f1f5f8', border: '#cfd9e3', dot: '#7389a2' },
]
const platformColorIndexMap = computed(() => Object.fromEntries(
  [...websiteList.value]
    .sort((left, right) => Number(left.id) - Number(right.id))
    .map((website, index) => [website.id, index]),
))
function platformBadgeStyle(websiteId) {
  const index = platformColorIndexMap.value[websiteId]
  const palette = index == null ? platformPalette.at(-1) : platformPalette[index % platformPalette.length]
  return {
    '--platform-color': palette.color,
    '--platform-background': palette.background,
    '--platform-border': palette.border,
    '--platform-dot': palette.dot,
  }
}
const activeFilterCount = computed(() => [
  filterWebsiteId.value,
  filterGameId.value,
  filterStatus.value,
  filterDeliveryStatus.value,
  filterCreatedRange.value?.length ? filterCreatedRange.value : null,
  keyword.value.trim(),
].filter(Boolean).length)
const hasActiveFilters = computed(() => activeFilterCount.value > 0)

function orderStatusLabel(s) { return { pending: '待分配', assigned: '已分配', processing: '处理中', abnormal: '异常', completed: '已完成', cancelled: '已取消' }[s] || s }
function orderStatusType(s) { return { pending: 'warning', assigned: 'primary', processing: '', abnormal: 'danger', completed: 'success', cancelled: 'info' }[s] || '' }
function detailStatusLabel(s) { return { pending: '待处理', processing: '处理中', completed: '已完成', cancelled: '已取消', failed: '失败' }[s] || s }
function detailStatusType(s) { return { pending: 'warning', processing: '', completed: 'success', cancelled: 'info', failed: 'danger' }[s] || '' }
function formatOrderTime(value) {
  if (!value) return '时间未记录'
  const normalized = String(value).replace('T', ' ')
  return normalized.length >= 16 ? normalized.slice(5, 16) : normalized
}
function compactOrderNo(value) {
  const orderNo = String(value || '').trim()
  if (!orderNo) return '未提供订单号'
  if (orderNo.length <= 13) return orderNo
  return `${orderNo.slice(0, 6)}…${orderNo.slice(-5)}`
}
function formatPlatformPrice(value) {
  const price = Number(value)
  return Number.isFinite(price) && price > 0 ? `₩ ${price.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}` : '-'
}
function formatOrderQuantity(value) {
  const quantity = Number(value)
  return Number.isFinite(quantity) ? quantity.toLocaleString('zh-CN') : '0'
}
function formatAssetSummary(order) {
  const type = order?.asset_type || '资产未设置'
  const amount = Number(order?.asset_amount)
  return Number.isFinite(amount) && amount > 0 ? `${type} · ${amount.toLocaleString('zh-CN')}` : type
}
function errorCodeLabel(code) {
  return {
    SUB_ORDER_MISSING: '子订单生成失败',
    NO_GREETING_SCRIPT: '招呼配置缺失',
    GREETING_SEND_FAILED: '招呼指令发送失败',
    GREETING_EXECUTION_FAILED: '招呼执行失败',
    GREETING_FAILED: '招呼执行失败',
    TRADE_DISPATCH_FAILED: '交易指派失败',
    START_DISPATCH_FAILED: '交易启动失败',
    TRADE_EXECUTION_FAILED: '游戏交易失败',
    TRADE_REQUEST_TIMEOUT: '游戏交易超时',
    FINAL_CONFIRMATION_NOT_FOUND: '未识别到最终确认提示',
    TRADE_RESULT_UNCERTAIN: '交易结果待复核',
    WEBSITE_DELIVERY_DISPATCH_FAILED: '网站交付确认指令下发失败',
    WEBSITE_DELIVERY_CONFIRM_FAILED: '网站商品交付确认失败',
    CONFIG_MISSING: '配置缺失',
    ITEM_NAME_PARSE_FAILED: '物品解析失败',
    INVENTORY_RECONCILIATION_REQUIRED: '库存待核对',
  }[code] || code || '未知异常'
}
function orderErrorMessage(order) {
  if (order?.last_error_code === 'FINAL_CONFIRMATION_NOT_FOUND') {
    return '原因：系统未能识别最终确认提示，无法据此判断当前界面。解决方案：请人工核对游戏和交易平台的实际结果，然后选择“复核为已完成”或“复核为已取消”。'
  }
  return order?.last_error_message || ''
}
function deliveryStatusLabel(order) {
  if (!order) return '待分配'
  if (order.last_error_code) return errorCodeLabel(order.last_error_code)
  if (order.delivery_status === 'greeting' && order.status === 'abnormal') return '招呼阶段异常'
  return { greeting: '待招呼', detected: '待分配', queued: '排队中', waiting_assignment: '等待指派', offered: '已发送指派', assigned: '交易执行中', delivering: '交付中', delivered: '已交付', wait_web_confirm: '等待网站确认', review_required: '待人工复核', suspended: '已挂起', completed: '已完成', cancelled: '已取消', failed: '失败' }[order.delivery_status] || order.delivery_status || '待分配'
}
function deliveryStatusType(order) {
  if (!order) return 'info'
  if (order.last_error_code || (order.delivery_status === 'greeting' && order.status === 'abnormal')) return 'danger'
  return { greeting: 'warning', detected: 'info', queued: 'warning', waiting_assignment: 'warning', offered: 'primary', assigned: 'primary', delivering: '', delivered: 'success', wait_web_confirm: 'warning', review_required: 'danger', suspended: 'danger', completed: 'success', cancelled: 'info', failed: 'danger' }[order.delivery_status] || 'info'
}
function orderVisualTone(order) {
  if (!order) return 'neutral'
  if (order.last_error_code || order.status === 'abnormal' || ['review_required', 'failed'].includes(order.delivery_status)) return 'danger'
  if (order.status === 'completed' || ['completed', 'delivered'].includes(order.delivery_status)) return 'success'
  if (order.status === 'cancelled' || order.delivery_status === 'cancelled') return 'neutral'
  if (['offered', 'assigned', 'delivering'].includes(order.delivery_status) || ['assigned', 'processing'].includes(order.status)) return 'active'
  return 'warning'
}
function orderRowClassName({ row }) { return `order-row--${orderVisualTone(row)}` }
function canRetryOrder(order) { return Boolean(order?.retryable) }
function isTerminalOrder(order) { return ['completed', 'cancelled'].includes(order?.status) }
function canCompleteOrder(order) { return Boolean(order) && !isTerminalOrder(order) }
function canCancelOrder(order) {
  return Boolean(order)
    && !isTerminalOrder(order)
    && order?.delivery_status !== 'wait_web_confirm'
    && !order?.game_delivered_at
}
function isReviewRequired(order) { return order?.delivery_status === 'review_required' }
function completeActionLabel(order, detail = false) {
  if (isReviewRequired(order)) return '复核为已完成'
  return detail ? '设为已完成' : '已完成'
}
function cancelActionLabel(order, detail = false) {
  if (isReviewRequired(order)) return '复核为已取消'
  return detail ? '设为已取消' : '已取消'
}
function completeConfirmTitle(order) {
  if (isReviewRequired(order)) {
    return '请先在游戏和交易平台核对结果。确认实际交易已完成？确认后将完成子订单并按已交付处理库存。'
  }
  return '确认设为已完成？系统会将子订单标记完成，并按已交付处理库存。'
}
function cancelConfirmTitle(order) {
  if (isReviewRequired(order)) {
    return '请先在游戏和交易平台核对结果。确认实际交易未完成？确认后订单将取消且不能重新尝试。'
  }
  return '确认设为已取消？取消后该订单不能重新尝试。'
}
function canDeleteOrder(order) {
  return Boolean(order) && order.status !== 'completed'
}
function orderOverflowActions(order) {
  const actions = [
    { command: 'chat', label: '客户聊天', icon: ChatDotRound, disabled: false, divided: false },
    { command: 'copy', label: '复制订单', icon: CopyDocument, disabled: copyLoadingOrderId.value === order?.id, divided: false },
  ]
  if (canDeleteOrder(order)) {
    actions.push({ command: 'delete', label: '删除订单', icon: Delete, disabled: false, divided: true })
  }
  return actions
}
function overflowActionButtonType(action) { return action?.command === 'delete' ? 'danger' : 'primary' }
async function handleOrderCommand(order, command) {
  if (command === 'chat') return openChatDialog(order)
  if (command === 'copy') return openCopyDialog(order)

  try {
    if (command === 'delete') {
      await ElMessageBox.confirm('删除后订单及全部子订单将无法恢复，确认删除？', '删除订单', {
        confirmButtonText: '确认删除', cancelButtonText: '返回', type: 'error',
      })
      return handleDeleteOrder(order.id)
    }
  } catch (action) {
    if (action !== 'cancel' && action !== 'close') throw action
  }
}
function retryActionLabel(order) {
  return {
    greeting: '恢复到招呼出错前状态，然后重新执行招呼',
    sub_order_generation: '恢复到子订单生成出错前状态，然后生成子订单并继续交易指派',
    assignment: '恢复到交易指派出错前状态，然后重新执行交易指派',
  }[order?.retry_stage] || '根据订单实际状态继续未完成步骤'
}

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (filterWebsiteId.value) params.website_id = filterWebsiteId.value
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterDeliveryStatus.value) params.delivery_status = filterDeliveryStatus.value
    if (filterCreatedRange.value?.length === 2) {
      params.created_from = filterCreatedRange.value[0]
      params.created_to = filterCreatedRange.value[1]
    }
    const res = await getOrders(params)
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }
function handlePageSizeChange() { page.value = 1; fetchList() }
function resetFilters() {
  filterWebsiteId.value = null
  filterGameId.value = null
  filterStatus.value = ''
  filterDeliveryStatus.value = ''
  filterCreatedRange.value = []
  keyword.value = ''
  handleSearch()
}

// ── 订单客户聊天 ──
const chatDialogVisible = ref(false)
const chatOrder = ref(null)
const chatMessages = ref([])
const chatSending = ref(false)
let chatMessageKey = 0

function createChatMessage() {
  chatMessageKey += 1
  return {
    _key: `chat-message-${chatMessageKey}`,
    _uploading: 0,
    content: '',
    image_urls: [],
  }
}

const chatImageCount = computed(() =>
  chatMessages.value.reduce((total, message) => total + message.image_urls.length, 0),
)
const chatUploadCount = computed(() =>
  chatMessages.value.reduce((total, message) => total + message._uploading, 0),
)

function openChatDialog(order) {
  if (!order?.id) return
  chatOrder.value = order
  chatMessages.value = [createChatMessage()]
  chatDialogVisible.value = true
}

function chatMessageTypeLabel(message) {
  const hasText = Boolean(message.content?.trim())
  const hasImage = message.image_urls.length > 0
  if (hasText && hasImage) return '图片 + 文字'
  if (hasImage) return '图片消息'
  return '文字消息'
}

function addChatMessage() {
  if (chatMessages.value.length < 30) chatMessages.value.push(createChatMessage())
}

function removeChatMessage(index) {
  if (chatMessages.value.length > 1) chatMessages.value.splice(index, 1)
}

function moveChatMessage(index, offset) {
  const nextIndex = index + offset
  if (nextIndex < 0 || nextIndex >= chatMessages.value.length) return
  const [message] = chatMessages.value.splice(index, 1)
  chatMessages.value.splice(nextIndex, 0, message)
}

function removeChatImage(message, imageIndex) {
  message.image_urls.splice(imageIndex, 1)
}

async function handleChatImageChange(message, file) {
  if (!file?.raw) return
  if (chatImageCount.value + chatUploadCount.value >= 30) {
    ElMessage.warning('一次最多发送 30 张图片')
    return
  }
  message._uploading += 1
  try {
    const result = await uploadFile(file.raw)
    if (result?.url && !message.image_urls.includes(result.url)) {
      message.image_urls.push(result.url)
    }
  } catch (error) {
    ElMessage.error(error.message || '图片上传失败')
  } finally {
    message._uploading -= 1
  }
}

async function handleSendChat() {
  if (!chatOrder.value?.id || chatSending.value || chatUploadCount.value > 0) return
  const messages = chatMessages.value
    .map(message => ({
      content: message.content.trim(),
      image_urls: [...message.image_urls],
    }))
    .filter(message => message.content || message.image_urls.length)
    .map(message => ({
      type: message.content && message.image_urls.length
        ? 'mixed'
        : message.content ? 'text' : 'image',
      ...(message.content ? { content: message.content } : {}),
      ...(message.image_urls.length ? { image_urls: message.image_urls } : {}),
    }))
  if (!messages.length) {
    ElMessage.warning('请至少输入一段文字或添加一张图片')
    return
  }
  chatSending.value = true
  try {
    const result = await sendOrderChat(chatOrder.value.id, { messages })
    ElMessage.success(result.message || '聊天指令已下发')
    chatDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.message || '聊天指令发送失败')
  } finally {
    chatSending.value = false
  }
}

// ── 订单关联日志 ──
const orderLogsDialogVisible = ref(false)
const orderLogTarget = ref(null)
const orderLogs = ref([])
const orderLogTotal = ref(0)
const orderLogsLoading = ref(false)

function orderLogLabel(type) {
  return {
    order_detected: '检测到订单',
    order_copied: '复制订单创建',
    no_greeting_script: '未找到招呼话术',
    no_sub_order: '子订单生成失败',
    greeting_send_failed: '招呼指令发送失败',
    greeting_failed: '招呼执行失败',
    greeting_success: '招呼执行成功',
    chat_command_sent: '聊天指令已下发',
    chat_message_sent: '聊天消息已发送',
    chat_message_failed: '聊天消息发送失败',
    queue_assignment: '订单进入机器队列',
    dequeue_assignment: '队首订单开始指派',
    offer_accepted: '交易指派已接受',
    offer_rejected: '交易指派被拒绝',
    offer_expired: '交易指派已过期',
    worker_disconnected: '执行机器已断线',
    start_failed: '交易启动失败',
    queued_offer_rejected: '队首指派被拒，继续排队',
    queued_offer_expired: '队首指派过期，继续排队',
    queued_start_failed: '队首启动失败，继续排队',
    queued_worker_disconnected: '队首机器断线，继续排队',
    trade_completed: '交易完成',
    game_trade_completed: '游戏内交易完成',
    trade_completion_message_failed: '交易完成话术发送失败（已继续）',
    trade_screenshot_stored: '交易截图已存入 RustFS',
    delivery_proof_sent: '交易截图已发送并关闭聊天',
    delivery_proof_failed: '交易截图发送失败',
    delivery_confirmation_dispatched: '网站交付确认指令已下发（截图未重复发送）',
    delivery_confirmation_completed: '网站商品交付已确认',
    delivery_confirmation_failed: '网站商品交付确认失败',
    trade_retryable_failed: '交易失败，可重新尝试',
    trade_failed: '交易失败',
    trade_timed_out: '交易超时',
    trade_verification_failed: '交易结果校验失败',
    trade_cancelled: '交易已取消',
    manual_dispatch: '人工发起指派',
    retry_greeting: '重新尝试招呼',
    retry_assignment: '重新尝试交易指派',
    reset_to_greeting: '恢复到招呼阶段',
    buyer_review_rejected: '人工拒绝交易请求',
  }[type] || type || '未知事件'
}
function orderLogType(type) {
  if (['greeting_success', 'chat_message_sent', 'dequeue_assignment', 'offer_accepted', 'trade_completed', 'game_trade_completed', 'trade_screenshot_stored', 'delivery_proof_sent', 'delivery_confirmation_completed'].includes(type)) return 'success'
  if (['chat_command_sent', 'trade_completion_message_failed', 'delivery_confirmation_dispatched', 'queue_assignment', 'queued_offer_rejected', 'queued_offer_expired', 'queued_start_failed', 'queued_worker_disconnected', 'retry_greeting', 'retry_assignment', 'reset_to_greeting', 'manual_dispatch'].includes(type)) return 'warning'
  if (type?.includes('failed') || ['no_greeting_script', 'no_sub_order', 'offer_rejected', 'offer_expired', 'worker_disconnected', 'trade_timed_out', 'trade_cancelled', 'buyer_review_rejected'].includes(type)) return 'danger'
  return 'primary'
}
function deliveryStateText(status) {
  return { detected: '已检测', greeting: '招呼阶段', queued: '排队中', waiting_assignment: '等待指派', offered: '已发送指派', assigned: '交易执行中', delivering: '交付中', delivered: '已交付', wait_web_confirm: '等待网站确认', review_required: '待人工复核', suspended: '已挂起', completed: '已完成', cancelled: '已取消', failed: '失败' }[status] || status || '-'
}
function formatOrderLogTime(value) { return value ? String(value).replace('T', ' ') : '-' }
function formatOrderLogPayload(payload) { return JSON.stringify(payload, null, 2) }
async function fetchOrderLogs() {
  const orderId = orderLogTarget.value?.id
  if (!orderId || orderLogsLoading.value) return
  orderLogsLoading.value = true
  try {
    const result = await getOrderLogs(orderId)
    if (orderLogTarget.value?.id === orderId) {
      orderLogs.value = result.items || []
      orderLogTotal.value = result.total || 0
    }
  } catch (error) {
    ElMessage.error(error.message || '订单日志加载失败')
  } finally {
    orderLogsLoading.value = false
  }
}
function openOrderLogs(order) {
  if (!order?.id) return
  orderLogTarget.value = order
  orderLogs.value = []
  orderLogTotal.value = 0
  orderLogsDialogVisible.value = true
  fetchOrderLogs()
}

// ── 自动刷新 ──
const autoRefreshEnabled = ref(true)
const refreshIntervalSeconds = ref(5)
let autoRefreshTimer = null

function clearAutoRefreshTimer() {
  if (autoRefreshTimer !== null) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

async function refreshIfIdle() {
  if (loading.value) return
  try { await fetchList() } catch (_) { /* 请求层统一处理错误提示 */ }
}

function startAutoRefreshTimer() {
  clearAutoRefreshTimer()
  const seconds = Number(refreshIntervalSeconds.value)
  if (!Number.isFinite(seconds) || seconds < 1) return
  autoRefreshTimer = window.setInterval(refreshIfIdle, seconds * 1000)
}

function toggleAutoRefresh() {
  if (autoRefreshEnabled.value) {
    autoRefreshEnabled.value = false
    clearAutoRefreshTimer()
    ElMessage.success('自动刷新已关闭')
    return
  }
  if (!Number.isFinite(Number(refreshIntervalSeconds.value)) || Number(refreshIntervalSeconds.value) < 1) {
    refreshIntervalSeconds.value = 5
  }
  autoRefreshEnabled.value = true
  startAutoRefreshTimer()
  refreshIfIdle()
  ElMessage.success(`已开启每 ${refreshIntervalSeconds.value} 秒自动刷新`)
}

watch(refreshIntervalSeconds, (value) => {
  if (value == null) return
  if (autoRefreshEnabled.value) startAutoRefreshTimer()
})

// ── 复制订单 ──
const copyDialogVisible = ref(false)
const copySubmitting = ref(false)
const copyLoadingOrderId = ref(null)
const copySourceOrderId = ref(null)
const copyFormRef = ref(null)
const copyRules = {
  game_id: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  region_id: [{ required: true, message: '请选择大区', trigger: 'change' }],
  initial_state: [{ required: true, message: '请选择初始步骤', trigger: 'change' }],
}

const defaultCopyForm = () => ({
  order_no: '', source_order_no: '', initial_state: 'waiting_assignment',
  website_id: null, platform_account_id: null, platform_order_time: null,
  platform_price: null, platform_item_type: '', product_title: '', trade_item_name: '',
  quantity: null, sale_quantity: null,
  game_id: null, region_id: null, game_account_id: null,
  buyer_character: '', asset_type: 'adena', asset_amount: null,
  customer_name: '', customer_contact: '', remark: '', details: [],
})
const copyForm = reactive(defaultCopyForm())

const copyRegionList = computed(() => allRegions.value.filter(r => !copyForm.game_id || r.game_id === copyForm.game_id))
const copyItemOptions = computed(() => allItems.value.filter(i => !copyForm.game_id || i.game_id === copyForm.game_id))
const detailItemOptions = computed(() => allItems.value.filter(i => !currentOrder.value?.game_id || i.game_id === currentOrder.value.game_id))
const copyPlatformAccounts = computed(() => platformAccountList.value.filter(a => !copyForm.website_id || a.website_id === copyForm.website_id))
const copyGameAccounts = computed(() => gameAccountList.value.filter(a => {
  if (Number(a.is_active) !== 1) return false
  if (copyForm.game_id && a.game_id !== copyForm.game_id) return false
  return !copyForm.region_id || !Array.isArray(a.region_ids) || a.region_ids.includes(copyForm.region_id)
}))

const newDetailItemId = ref(null)
const newDetailQty = ref(1)
const newDetailPrice = ref(0)

function copyNumber(original, maxLength) {
  const now = new Date()
  const pad = value => String(value).padStart(2, '0')
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}${String(now.getMilliseconds()).padStart(3, '0')}`
  const suffix = `-COPY-${stamp}`
  const base = String(original || 'ORDER').trim() || 'ORDER'
  return `${base.slice(0, Math.max(1, maxLength - suffix.length))}${suffix}`
}

async function openCopyDialog(row) {
  if (!row?.id || copyLoadingOrderId.value !== null) return
  copyLoadingOrderId.value = row.id
  try {
    const order = await getOrder(row.id)
    const sourcePlatformAccount = platformAccountList.value.find(account => account.id === order.platform_account_id)
    const sourceGameAccount = gameAccountList.value.find(account => account.id === order.game_account_id && Number(account.is_active) === 1)
    copySourceOrderId.value = order.id
    Object.assign(copyForm, {
      order_no: copyNumber(order.order_no, 50),
      source_order_no: copyNumber(order.source_order_no || order.order_no, 100),
      initial_state: 'waiting_assignment',
      website_id: order.website_id ?? null,
      platform_account_id: sourcePlatformAccount?.id ?? null,
      platform_order_time: order.platform_order_time || null,
      platform_price: order.platform_price == null ? null : Number(order.platform_price),
      platform_item_type: order.platform_item_type || '',
      product_title: order.product_title || '',
      trade_item_name: order.trade_item_name || '',
      quantity: order.quantity == null ? null : Number(order.quantity),
      sale_quantity: order.sale_quantity == null ? null : Number(order.sale_quantity),
      game_id: order.game_id ?? null,
      region_id: order.region_id ?? null,
      game_account_id: sourceGameAccount?.id ?? null,
      buyer_character: order.buyer_character || '',
      asset_type: order.asset_type || '',
      asset_amount: order.asset_amount == null ? null : Number(order.asset_amount),
      customer_name: order.customer_name || '',
      customer_contact: order.customer_contact || '',
      remark: order.remark || '',
      details: (order.details || []).map(detail => ({
        item_id: detail.item_id,
        quantity: Number(detail.quantity || 1),
        unit_price: Number(detail.unit_price || 0),
        purchase_price: detail.purchase_price == null ? null : Number(detail.purchase_price),
        selling_price: detail.selling_price == null ? null : Number(detail.selling_price),
        bundle_name: detail.bundle_name || '',
        remark: detail.remark || '',
        subtotal: Number(detail.unit_price || 0) * Number(detail.quantity || 1),
      })),
    })
    newDetailItemId.value = null
    newDetailQty.value = 1
    newDetailPrice.value = 0
    copyDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '订单信息加载失败')
  } finally {
    copyLoadingOrderId.value = null
  }
}

function onCopyWebsiteChange() {
  if (!copyPlatformAccounts.value.some(a => a.id === copyForm.platform_account_id)) {
    copyForm.platform_account_id = null
  }
}

function onCopyGameChange() {
  copyForm.region_id = null
  copyForm.game_account_id = null
  const allowedItemIds = new Set(copyItemOptions.value.map(item => item.id))
  const remaining = copyForm.details.filter(detail => allowedItemIds.has(detail.item_id))
  if (remaining.length !== copyForm.details.length) {
    copyForm.details = remaining
    ElMessage.warning('已移除不属于新游戏的订单明细')
  }
}

function onCopyRegionChange() {
  if (!copyGameAccounts.value.some(account => account.id === copyForm.game_account_id)) {
    copyForm.game_account_id = null
  }
}

function addCopyDetailRow() {
  const item = allItems.value.find(i => i.id === newDetailItemId.value)
  if (!item) return
  const price = newDetailPrice.value || Number(item.price) || 0
  const qty = newDetailQty.value
  copyForm.details.push({
    item_id: item.id, quantity: qty, unit_price: price,
    purchase_price: null, selling_price: null, bundle_name: '', remark: '',
    subtotal: price * qty,
  })
  newDetailItemId.value = null; newDetailQty.value = 1; newDetailPrice.value = 0
}

function onCopyDetailItemChange(row) {
  const item = allItems.value.find(i => i.id === row.item_id)
  if (item && (row.unit_price == null || Number(row.unit_price) === 0)) row.unit_price = Number(item.price || 0)
  calcRowSubtotal(row)
}

function calcRowSubtotal(row) { row.subtotal = (row.unit_price || 0) * (row.quantity || 0) }

const copyTotal = computed(() => copyForm.details.reduce((s, d) => s + Number(d.subtotal || 0), 0).toFixed(2))

function copyInitialState() {
  return {
    waiting_assignment: { delivery_status: 'waiting_assignment', status: 'pending' },
    greeting: { delivery_status: 'greeting', status: 'pending' },
    detected: { delivery_status: 'detected', status: 'pending' },
    greeting_abnormal: { delivery_status: 'greeting', status: 'abnormal' },
    suspended: { delivery_status: 'suspended', status: 'pending' },
  }[copyForm.initial_state]
}

async function handleCopyOrder() {
  await copyFormRef.value?.validate()
  if (!copyForm.details.length) { ElMessage.warning('请至少保留一个订单明细'); return }
  const initialState = copyInitialState()
  if (!initialState || !copySourceOrderId.value) return
  copySubmitting.value = true
  try {
    await copyOrder(copySourceOrderId.value, {
      order_no: copyForm.order_no,
      source_order_no: copyForm.source_order_no,
      ...initialState,
      website_id: copyForm.website_id,
      platform_account_id: copyForm.platform_account_id,
      platform_order_time: copyForm.platform_order_time,
      platform_price: copyForm.platform_price,
      platform_item_type: copyForm.platform_item_type,
      product_title: copyForm.product_title,
      trade_item_name: copyForm.trade_item_name,
      quantity: copyForm.quantity,
      sale_quantity: copyForm.sale_quantity,
      game_id: copyForm.game_id,
      region_id: copyForm.region_id,
      game_account_id: copyForm.game_account_id,
      buyer_character: copyForm.buyer_character,
      asset_type: copyForm.asset_type,
      asset_amount: copyForm.asset_amount,
      customer_name: copyForm.customer_name,
      customer_contact: copyForm.customer_contact,
      remark: copyForm.remark,
      details: copyForm.details.map(detail => ({
        item_id: detail.item_id,
        quantity: detail.quantity,
        unit_price: detail.unit_price,
        purchase_price: detail.purchase_price,
        selling_price: detail.selling_price,
        bundle_name: detail.bundle_name,
        remark: detail.remark,
      })),
    })
    ElMessage.success('订单复制成功')
    copyDialogVisible.value = false
    detailDrawerVisible.value = false
    await fetchList()
  } catch (e) {
    ElMessage.error(e.message || '订单复制失败')
  } finally {
    copySubmitting.value = false
  }
}

// ── 删除订单 ──
async function handleDeleteOrder(id) { try { await deleteOrder(id); ElMessage.success('已删除'); fetchList() } catch (e) { ElMessage.error(e.message) } }

// ── 人工完成/取消订单 ──
const terminalActionKey = ref('')
async function handleTerminalOrder(row, action, refreshDetail = false) {
  if (!row?.id || terminalActionKey.value) return
  terminalActionKey.value = `${action}:${row.id}`
  try {
    if (action === 'complete') await completeOrder(row.id)
    else await cancelOrder(row.id)
    ElMessage.success(action === 'complete' ? '订单已完成' : '订单已取消')
    if (refreshDetail) {
      const orderRes = await getOrder(row.id)
      detailList.value = orderRes.details || []
      currentOrder.value = orderRes
    }
    await fetchList()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    terminalActionKey.value = ''
  }
}

// ── 订单明细抽屉 ──
const detailDrawerVisible = ref(false)
const currentOrder = ref(null)
const detailList = ref([])
const addDetailItemId = ref(null)
const addDetailQty = ref(1)
const buyerReviewLoading = ref(false)

async function openDetailDrawer(order) {
  currentOrder.value = order
  detailDrawerVisible.value = true
  const res = await getOrder(order.id)
  detailList.value = res.details || []
  currentOrder.value = res
}

function formatConfidence(value) {
  const confidence = Number(value)
  return Number.isFinite(confidence) && confidence >= 0 ? `${confidence.toFixed(1)}%` : '无法识别'
}

function buyerReviewStatusLabel(status) {
  return { pending: '待人工确认', approved: '已同意', rejected: '已拒绝', expired: '已失效', cancelled: '已取消' }[status] || status || '-'
}

async function handleBuyerReview(approved) {
  buyerReviewLoading.value = true
  try {
    const review = currentOrder.value.buyer_review
    const response = await submitBuyerReview(currentOrder.value.id, {
      review_id: review.review_id,
      approved: Boolean(approved),
    })
    ElMessage.success(response.message)
    const orderRes = await getOrder(currentOrder.value.id)
    detailList.value = orderRes.details || []
    currentOrder.value = orderRes
    fetchList()
  } catch (error) {
    ElMessage.error(error.message || '审核决定提交失败')
  } finally {
    buyerReviewLoading.value = false
  }
}

let lastAlertNavigation = ''
async function openAlertOrderFromRoute() {
  const orderId = Number(route.query.alert_order_id)
  if (!Number.isInteger(orderId) || orderId <= 0) return
  const navigationKey = `${orderId}:${route.query.alert_nonce || ''}`
  if (navigationKey === lastAlertNavigation) return
  lastAlertNavigation = navigationKey
  try {
    await openDetailDrawer({ id: orderId })
  } catch (error) {
    ElMessage.error(error.message || '订单详情加载失败')
  }
}

watch(
  () => [route.query.alert_order_id, route.query.alert_nonce],
  () => openAlertOrderFromRoute(),
)

async function handleAddDetail() {
  try {
    await addOrderDetail(currentOrder.value.id, { item_id: addDetailItemId.value, quantity: addDetailQty.value })
    ElMessage.success('已添加'); addDetailItemId.value = null; addDetailQty.value = 1
    const res = await getOrder(currentOrder.value.id)
    detailList.value = res.details || []; currentOrder.value = res; fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

async function handleDeleteDetail(detailId) {
  try {
    await deleteOrderDetail(detailId); ElMessage.success('已删除')
    const res = await getOrder(currentOrder.value.id)
    detailList.value = res.details || []; currentOrder.value = res; fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

// ── 失败后从未完成阶段重新尝试 ──
const retryingOrderId = ref(null)

async function handleRetryOrder(row, refreshDetail = false) {
  if (!row?.id || retryingOrderId.value !== null) return
  retryingOrderId.value = row.id
  try {
    const res = await retryOrder(row.id)
    ElMessage.success(res.message || '已继续执行订单')
    if (refreshDetail) {
      const orderRes = await getOrder(row.id)
      detailList.value = orderRes.details || []
      currentOrder.value = orderRes
    }
    await fetchList()
  } catch (e) { ElMessage.error(e.message) }
  finally {
    if (refreshDetail && row?.id) {
      try {
        const orderRes = await getOrder(row.id)
        detailList.value = orderRes.details || []
        currentOrder.value = orderRes
      } catch (_) { /* 保留原错误提示 */ }
    }
    await fetchList()
    retryingOrderId.value = null
  }
}

onMounted(async () => {
  const tableViewport = orderTableViewport.value
  if (tableViewport) {
    const updateTableWidth = () => { orderTableWidth.value = tableViewport.clientWidth || 1018 }
    updateTableWidth()
    orderTableResizeObserver = new ResizeObserver(updateTableWidth)
    orderTableResizeObserver.observe(tableViewport)
  }
  const [games, regions, machines, items, websites, platformAccounts, gameAccounts] = await Promise.all([
    getAllGames(), getAllRegions(), getAllMachines(), getAllItems(), getAllWebsites(),
    getAllAccounts(), getAllGameAccounts(),
  ])
  gameList.value = games
  allRegions.value = regions
  machineList.value = machines
  allItems.value = items
  websiteList.value = websites
  platformAccountList.value = platformAccounts
  gameAccountList.value = Array.isArray(gameAccounts) ? gameAccounts : (gameAccounts.items || [])
  await fetchList()
  await openAlertOrderFromRoute()
  startAutoRefreshTimer()
})

onBeforeUnmount(() => {
  clearAutoRefreshTimer()
  orderTableResizeObserver?.disconnect()
})
</script>

<style scoped>
.page-container { padding: 0; }
.order-directory {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e3e9f1;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 5px 18px rgba(43, 60, 82, .045);
}
.order-directory__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 13px 18px 11px;
}
.order-directory__intro { min-width: 0; }
.order-directory__eyebrow {
  display: block;
  margin-bottom: 2px;
  color: #409eff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
}
.order-directory__title-line { display: flex; align-items: center; gap: 10px; }
.order-directory__title-line h1 { margin: 0; color: #25364a; font-size: 21px; line-height: 1.3; }
.order-directory__count {
  padding: 2px 8px;
  color: #66778c;
  border: 1px solid #dde5ee;
  border-radius: 999px;
  background: #f7f9fc;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.order-directory__intro p { margin: 3px 0 0; color: #8793a3; font-size: 12px; }
.order-live {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  padding: 5px 7px 5px 10px;
  color: #7b8796;
  border: 1px solid #e1e7ee;
  border-radius: 8px;
  background: #fafbfd;
  font-size: 12px;
}
.order-live__dot { width: 7px; height: 7px; border-radius: 50%; background: #aab3bf; }
.order-live.is-active .order-live__dot { background: #32b875; box-shadow: 0 0 0 4px rgba(50, 184, 117, .1); animation: order-live-pulse 2.2s ease-in-out infinite; }
.order-live.is-active .order-live__state { color: #37815f; }
.order-live :deep(.el-input-number) { width: 78px; }
.order-live__unit { margin-left: -3px; }
.order-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid #edf0f4;
  border-bottom: 1px solid #e6ebf1;
  background: #fafbfd;
}
.order-filters__fields,
.order-filters__tools { display: flex; align-items: center; gap: 8px; }
.order-filters__fields { flex: 1 1 820px; flex-wrap: wrap; }
.order-filters__tools { flex: 1 1 350px; justify-content: flex-end; }
.order-filter { width: 130px; }
.order-filter--website { width: 142px; }
.order-filter--game { width: 166px; }
.order-filter--delivery { width: 148px; }
.order-filter-date-wrap { width: 330px; flex: 0 0 330px; }
.order-filter--date { width: 100%; }
.order-search { width: min(280px, 100%); }
.order-table-viewport { min-height: 0; flex: 1; overflow: hidden; }
.order-table { width: 100%; border-right: 0; border-left: 0; }
.order-table :deep(.el-table__header th.el-table__cell) {
  height: 40px;
  color: #66778c;
  background: #f7f9fc;
  font-size: 12px;
  font-weight: 600;
}
.order-table :deep(.el-table__body td.el-table__cell) { padding: 7px 0; }
.order-table :deep(td.order-action-cell .cell),
.order-table :deep(th.order-action-header .cell) { padding-right: 6px; padding-left: 6px; }
.order-table :deep(.el-table__row) { cursor: pointer; transition: background-color .18s ease; }
.order-table :deep(.order-row--danger > td:first-child) { box-shadow: inset 3px 0 0 #d84a4a; }
.order-table :deep(.order-row--warning > td:first-child) { box-shadow: inset 3px 0 0 #d69a2d; }
.order-table :deep(.order-row--active > td:first-child) { box-shadow: inset 3px 0 0 #3f7fd5; }
.order-table :deep(.order-row--success > td:first-child) { box-shadow: inset 3px 0 0 #2b9669; }
.order-identity,
.order-product,
.order-buyer,
.order-price { display: grid; min-width: 0; gap: 3px; }
.order-identity__number {
  display: block;
  width: fit-content;
  max-width: 100%;
  padding: 0;
  overflow: hidden;
  color: #2f6fb9;
  border: 0;
  background: transparent;
  font: 650 13px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.order-identity__number:hover { color: #409eff; text-decoration: underline; text-underline-offset: 3px; }
.order-identity__number:focus-visible { outline: 2px solid #91caff; outline-offset: 3px; border-radius: 2px; }
.order-identity__meta { display: flex; min-width: 0; align-items: center; gap: 5px; color: #8b98a8; font-size: 10px; white-space: nowrap; }
.order-platform-badge {
  display: inline-flex;
  flex: 0 0 auto;
  min-width: 0;
  max-width: 60px;
  align-items: center;
  padding: 1px 4px 1px 5px;
  overflow: hidden;
  color: var(--platform-color);
  border-radius: 4px;
  background: var(--platform-background);
  box-shadow: inset 2px 0 var(--platform-dot);
  font-size: 9px;
  font-weight: 650;
  line-height: 1.35;
}
.order-platform-badge > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.order-identity__meta time { font-variant-numeric: tabular-nums; white-space: nowrap; }
.order-product strong,
.order-buyer strong { overflow: hidden; color: #30445c; font-size: 12px; line-height: 1.35; text-overflow: ellipsis; }
.order-product strong { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal; }
.order-buyer strong { white-space: nowrap; }
.order-product__meta { display: flex; min-width: 0; align-items: center; gap: 8px; }
.order-product__meta span { overflow: hidden; color: #8895a5; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.order-buyer span { overflow: hidden; color: #8c98a8; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.order-price { justify-items: end; }
.order-price strong { color: #30445c; font-size: 14px; font-variant-numeric: tabular-nums; }
.order-price span { color: #939eac; font-size: 9px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.order-progress { display: grid; width: 100%; max-width: 280px; min-width: 0; gap: 3px; padding: 6px 8px; border: 1px solid transparent; border-radius: 6px; }
.order-progress__main { display: flex; min-width: 0; align-items: center; gap: 6px; }
.order-progress__main i { flex: 0 0 auto; width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 12%, transparent); }
.order-progress__main strong { overflow: hidden; font-size: 11px; line-height: 1.25; text-overflow: ellipsis; white-space: nowrap; }
.order-progress__meta { display: flex; gap: 7px; padding-left: 13px; color: #748195; font-size: 9px; line-height: 1.2; }
.order-progress.tone-danger { color: #b93838; border-color: #f1caca; background: #fff1f0; }
.order-progress.tone-warning { color: #a86d12; border-color: #efd9ae; background: #fff8e8; }
.order-progress.tone-active { color: #2f6fbe; border-color: #c8dcf5; background: #edf5ff; }
.order-progress.tone-success { color: #247a56; border-color: #c8e5d7; background: #edf8f2; }
.order-progress.tone-neutral { color: #697586; border-color: #dde3ea; background: #f5f7fa; }
.order-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; white-space: nowrap; }
.order-row-actions :deep(.el-button) { margin-left: 0; padding-right: 1px; padding-left: 1px; }
.order-row-actions :deep(.order-overflow-action) { width: 20px; padding: 0; }
.order-row-actions .el-dropdown { vertical-align: middle; }
.pagination-wrap { display: flex; justify-content: flex-end; min-height: 32px; padding: 10px 16px; border-top: 1px solid #edf0f4; background: #fff; }
@keyframes order-live-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(50, 184, 117, .08); }
  50% { box-shadow: 0 0 0 6px rgba(50, 184, 117, .14); }
}
.detail-toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.order-action-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.detail-summary {
  margin-bottom: 12px;
  overflow: hidden;
  border: 1px solid #dce6f1;
  border-radius: 9px;
  background: #f8fbff;
  box-shadow: 0 5px 18px rgba(33, 67, 101, .05);
}
.detail-summary__top { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 16px 18px 14px; }
.detail-summary__identity { min-width: 0; }
.detail-summary__identity > span { color: #2f6fae; font-size: 10px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
.detail-summary__identity h2 { max-width: 540px; margin: 5px 0 7px; overflow: hidden; color: #24364b; font-size: 16px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.detail-summary__meta { display: flex; min-width: 0; align-items: center; gap: 9px; color: #7b8794; font-size: 11px; }
.detail-summary__meta code { overflow: hidden; color: #42617f; font: 650 11px/1.4 "SFMono-Regular", Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.detail-summary__meta time { padding-left: 9px; border-left: 1px solid #d7e0ea; white-space: nowrap; }
.detail-summary__status { flex: 0 0 190px; margin-top: 1px; }
.detail-summary__metrics { display: grid; grid-template-columns: 1fr 1fr 1.25fr; border-top: 1px solid #e1eaf3; background: #fff; }
.detail-summary__metrics > div { display: grid; min-width: 0; gap: 3px; padding: 11px 18px 12px; }
.detail-summary__metrics > div + div { border-left: 1px solid #e7edf4; }
.detail-summary__metrics span { color: #84909e; font-size: 10px; }
.detail-summary__metrics strong { overflow: hidden; color: #263b53; font-size: 14px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.detail-summary__metrics small { overflow: hidden; color: #718195; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.detail-primary-actions { margin-bottom: 14px; padding: 10px 12px; border: 1px solid #e3e9f0; border-radius: 8px; background: #fff; }
.detail-information-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.detail-information-card { min-width: 0; overflow: hidden; border: 1px solid #e0e6ee; border-radius: 8px; background: #fff; }
.detail-information-card > header { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; padding: 10px 12px; border-bottom: 1px solid #e6ebf1; background: #f7f9fc; }
.detail-information-card > header span { color: #2e4056; font-size: 13px; font-weight: 700; }
.detail-information-card > header small { color: #8b96a3; font-size: 10px; }
.detail-information-card :deep(.el-descriptions__body) { background: transparent; }
.detail-information-card :deep(.el-descriptions__label) { width: 92px; color: #6d7886; background: #fafbfd !important; font-size: 11px; }
.detail-information-card :deep(.el-descriptions__content) { color: #37465a; font-size: 11px; word-break: break-word; }
.detail-information-card :deep(.el-descriptions__cell) { padding: 7px 9px !important; }
.detail-list-heading { display: flex; align-items: center; justify-content: space-between; margin: 4px 0 9px; }
.detail-list-heading > div { display: flex; align-items: baseline; gap: 9px; }
.detail-list-heading strong { color: #2e4056; font-size: 14px; }
.detail-list-heading span { color: #8b96a3; font-size: 11px; }
.detail-items-table { width: 100%; }
.detail-items-table :deep(th.el-table__cell) { color: #607188; background: #f6f8fb; font-size: 11px; }
.detail-items-table :deep(td.el-table__cell) { padding: 6px 0; }
.detail-line-item { display: flex; min-width: 0; align-items: center; gap: 9px; }
.detail-line-item > .el-image,
.detail-line-item__placeholder { display: grid; width: 40px; height: 40px; place-content: center; flex: 0 0 40px; overflow: hidden; color: #98a3af; border: 1px solid #dfe5eb; border-radius: 5px; background: #f4f6f8; font-size: 9px; }
.detail-line-item > div:last-child { display: grid; min-width: 0; justify-items: start; gap: 4px; }
.detail-line-item strong { max-width: 100%; overflow: hidden; color: #31445a; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.detail-line-item small { color: #929ca8; font-size: 10px; }
.detail-line-prices { display: grid; grid-template-columns: 1fr 1fr; gap: 3px 10px; color: #7a8795; font-size: 10px; font-variant-numeric: tabular-nums; }
.detail-line-prices strong { grid-column: 1 / -1; color: #33485f; font-size: 11px; }
.detail-line-quantity { color: #33485f; font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.detail-line-subtotal { color: #2f435a; font-size: 12px; font-variant-numeric: tabular-nums; }
.total-line { text-align: right; font-weight: 600; font-size: 15px; margin-top: 12px; color: #e6a23c; }
.detail-info { margin-bottom: 8px; }
.detail-section { margin-bottom: 16px; }
.copy-order-alert { margin-bottom: 14px; }
.retry-resume-info { margin-top: -8px; padding: 10px 12px; color: #b45309; font-size: 13px; border: 1px solid #f3d19e; border-radius: 6px; background: #fdf6ec; }
.error-code-text { margin-left: 8px; color: #909399; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.region-code { color: #606266; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.buyer-review-detail { padding: 14px; border: 1px solid #f3d19e; border-radius: 8px; background: #fdf6ec; }
.buyer-review-detail-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.buyer-review-detail-image { width: 100%; min-height: 90px; max-height: 210px; margin-top: 12px; border: 1px solid #dcdfe6; border-radius: 6px; background: #111827; }
.buyer-review-detail-actions { display: flex; justify-content: flex-end; margin-top: 12px; }
.game-trade-proof { padding: 14px; border: 1px solid #b3d8ff; border-radius: 8px; background: #ecf5ff; }
.game-trade-proof-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.game-trade-proof-title span { color: #606266; font-size: 12px; }
.game-trade-proof-image { width: 100%; min-height: 220px; max-height: 480px; border: 1px solid #dcdfe6; border-radius: 6px; background: #111827; }
.game-trade-proof-path { margin-top: 8px; color: #606266; font-size: 12px; word-break: break-all; }
.chat-target { display: flex; justify-content: space-between; gap: 20px; padding: 14px 16px; border: 1px solid #d9ecff; border-radius: 8px; background: #f4f9ff; }
.chat-target-label { margin-right: 8px; color: #909399; font-size: 12px; }
.chat-target-meta { display: flex; gap: 16px; align-items: center; color: #606266; font-size: 12px; }
.chat-order-tip { margin: 14px 0; }
.chat-message-list { position: relative; display: grid; gap: 12px; max-height: 52vh; padding: 0 5px 0 18px; overflow-y: auto; }
.chat-message-list::before { position: absolute; top: 22px; bottom: 22px; left: 6px; width: 2px; content: ""; background: #d9ecff; }
.chat-message-card { position: relative; padding: 14px; border: 1px solid #e4e7ed; border-radius: 8px; background: #fff; box-shadow: 0 4px 14px rgba(31, 45, 61, .05); }
.chat-message-card::before { position: absolute; top: 24px; left: -17px; width: 8px; height: 8px; border: 3px solid #fff; border-radius: 50%; content: ""; background: #409eff; box-shadow: 0 0 0 1px #b3d8ff; }
.chat-message-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 11px; }
.chat-message-index { display: flex; align-items: center; gap: 10px; }
.chat-message-index > span { color: #409eff; font: 600 12px/1 Consolas, "SFMono-Regular", monospace; }
.chat-message-index div { display: grid; gap: 2px; }
.chat-message-index small { color: #909399; font-size: 11px; }
.chat-message-actions { display: flex; }
.chat-image-row { display: flex; gap: 9px; margin-top: 11px; overflow-x: auto; }
.chat-image-tile { position: relative; flex: 0 0 72px; width: 72px; height: 72px; overflow: hidden; border: 1px solid #dcdfe6; border-radius: 7px; background: #f5f7fa; }
.chat-image-tile .el-image { width: 100%; height: 100%; }
.chat-image-tile button { position: absolute; top: 3px; right: 3px; width: 20px; height: 20px; padding: 0; color: #fff; border: 0; border-radius: 50%; background: rgba(17, 24, 39, .72); cursor: pointer; }
.chat-image-add { display: grid; place-content: center; flex: 0 0 72px; width: 72px; height: 72px; color: #409eff; border: 1px dashed #a0cfff; border-radius: 7px; background: #f4f9ff; cursor: pointer; }
.chat-image-add:hover { border-color: #409eff; background: #ecf5ff; }
.chat-image-add.is-loading { color: #909399; cursor: wait; }
.chat-image-add span { text-align: center; font-size: 22px; line-height: 1; }
.chat-image-add small { margin-top: 6px; font-size: 11px; }
.chat-add-message { width: 100%; margin-top: 14px; border-style: dashed; }
.chat-dialog-footer { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.chat-dialog-footer > span { color: #909399; font-size: 12px; }
.order-log-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; color: #606266; font-size: 13px; }
.order-log-toolbar strong { color: #303133; font-size: 18px; }
.order-log-body { min-height: 180px; max-height: 62vh; padding: 4px 10px 0 2px; overflow-y: auto; }
.order-log-timeline { padding: 4px 0 0 8px; }
.order-log-card { padding: 13px 15px; border: 1px solid #e4e7ed; border-radius: 7px; background: #fff; box-shadow: 0 2px 8px rgba(31, 45, 61, .04); }
.order-log-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.order-log-transition { display: flex; align-items: center; gap: 9px; margin-top: 10px; color: #606266; font-size: 12px; }
.order-log-transition span { color: #a8abb2; }
.order-log-message { margin: 9px 0 0; color: #303133; line-height: 1.55; white-space: pre-wrap; }
.order-log-meta { margin-top: 9px; color: #909399; font-size: 12px; }
.order-log-meta span { color: #606266; font-family: Consolas, "SFMono-Regular", monospace; }
.order-log-payload { margin-top: 8px; }
.order-log-payload pre { max-height: 220px; margin: 0; padding: 10px; overflow: auto; color: #d6deeb; border-radius: 5px; background: #17212b; font: 12px/1.55 Consolas, "SFMono-Regular", monospace; }
@media (max-width: 900px) {
  .order-directory__header { align-items: flex-start; flex-direction: column; }
  .order-live { align-self: stretch; width: fit-content; }
  .order-filters__tools { justify-content: flex-start; }
  .order-search { flex: 1 1 240px; }
  .pagination-wrap { justify-content: flex-start; overflow-x: auto; }
}
@media (max-width: 760px) {
  .order-directory__header { padding: 18px 16px 15px; }
  .order-live { width: 100%; box-sizing: border-box; flex-wrap: wrap; }
  .order-live__state { margin-right: auto; }
  .order-filters { padding: 12px 16px; }
  .order-filter,
  .order-filter--website,
  .order-filter--game,
  .order-filter--delivery,
  .order-filter-date-wrap,
  .order-search { width: 100%; }
  .order-filter-date-wrap { flex-basis: auto; }
  .order-filters__fields { display: grid; grid-template-columns: 1fr 1fr; width: 100%; }
  .order-filter-date-wrap { grid-column: 1 / -1; }
  .order-filters__tools { width: 100%; }
  .chat-target, .chat-dialog-footer { align-items: flex-start; flex-direction: column; }
  .chat-target-meta { align-items: flex-start; flex-direction: column; gap: 4px; }
  .detail-summary__top { flex-direction: column; }
  .detail-summary__status { width: 100%; max-width: none; flex-basis: auto; }
  .detail-summary__metrics { grid-template-columns: 1fr; }
  .detail-summary__metrics > div + div { border-top: 1px solid #e7edf4; border-left: 0; }
  .detail-information-grid { grid-template-columns: 1fr; }
}
@media (max-width: 430px) {
  .order-filters__fields { grid-template-columns: 1fr; }
  .order-filter-date-wrap { grid-column: auto; }
  .order-filters__tools { align-items: stretch; flex-wrap: wrap; }
  .order-search { flex-basis: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .order-live.is-active .order-live__dot { animation: none; }
  .order-table :deep(.el-table__row) { transition: none; }
}
</style>
