<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 160px" @change="handleSearch">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="订单状态" clearable style="width: 120px" @change="handleSearch">
        <el-option label="待分配" value="pending" />
        <el-option label="已分配" value="assigned" />
        <el-option label="处理中" value="processing" />
        <el-option label="异常" value="abnormal" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-select v-model="filterDeliveryStatus" placeholder="交付状态" clearable style="width: 140px" @change="handleSearch">
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
      <el-input v-model="keyword" placeholder="搜索订单号/客户..." clearable style="width: 220px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <div class="toolbar-actions">
        <div class="auto-refresh-controls">
          <span class="auto-refresh-label">刷新间隔</span>
          <el-input-number
            v-model="refreshIntervalSeconds"
            :min="1"
            :max="3600"
            :step="1"
            controls-position="right"
            style="width: 100px"
            aria-label="自动刷新间隔秒数"
          />
          <span class="auto-refresh-unit">秒</span>
          <el-button :type="autoRefreshEnabled ? 'danger' : 'success'" plain @click="toggleAutoRefresh">
            <el-icon><RefreshRight /></el-icon>
            {{ autoRefreshEnabled ? '关闭自动刷新' : '开启自动刷新' }}
          </el-button>
        </div>
      </div>
    </div>

    <el-table :data="list" border stripe v-loading="loading" highlight-current-row @current-change="onCurrentChange" row-key="id">
      <el-table-column prop="order_no" label="订单号" width="160" show-overflow-tooltip />
      <el-table-column label="来源" width="80">
        <template #default="{ row }">{{ websiteNameMap[row.website_id] || row.website_id || '-' }}</template>
      </el-table-column>
      <el-table-column label="游戏" width="80">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
      </el-table-column>
      <el-table-column prop="product_title" label="商品标题" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.product_title || row.remark || '-' }}</template>
      </el-table-column>
      <el-table-column prop="trade_item_name" label="交易物品" width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.trade_item_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="资产类型" width="90">
        <template #default="{ row }">{{ row.asset_type || '-' }}</template>
      </el-table-column>
      <el-table-column prop="buyer_character" label="买家" width="90" show-overflow-tooltip />
      <el-table-column prop="platform_price" label="平台售价" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row.platform_price">₩ {{ Number(row.platform_price).toLocaleString() }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="当前步骤" width="140" align="center">
        <template #default="{ row }">
          <el-tooltip
            :content="row.last_error_message || retryActionLabel(row)"
            :disabled="!row.last_error_message && !row.retryable"
            placement="top"
          >
            <el-tag :type="deliveryStatusType(row)" size="small">{{ deliveryStatusLabel(row) }}</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="150" />
      <el-table-column label="操作" width="360" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetailDrawer(row)">明细</el-button>
          <el-button size="small" link type="primary" @click="openOrderLogs(row)">日志</el-button>
          <el-button
            size="small"
            link
            type="primary"
            :loading="copyLoadingOrderId === row.id"
            @click="openCopyDialog(row)"
          >复制</el-button>
          <el-button
            v-if="canRetryOrder(row)"
            size="small"
            link
            type="warning"
            :loading="retryingOrderId === row.id"
            @click="handleRetryOrder(row)"
          >重新尝试</el-button>
          <el-popconfirm
            v-if="canCompleteOrder(row)"
            width="320"
            title="确认设为已完成？系统会将子订单标记完成，并按已交付处理库存。"
            confirm-button-text="确认完成"
            cancel-button-text="返回"
            @confirm="handleTerminalOrder(row, 'complete')"
          >
            <template #reference>
              <el-button size="small" link type="success" :loading="terminalActionKey === `complete:${row.id}`">已完成</el-button>
            </template>
          </el-popconfirm>
          <el-popconfirm
            v-if="canCancelOrder(row)"
            width="300"
            title="确认设为已取消？取消后该订单不能重新尝试。"
            confirm-button-text="确认取消"
            cancel-button-text="返回"
            @confirm="handleTerminalOrder(row, 'cancel')"
          >
            <template #reference>
              <el-button size="small" link type="warning" :loading="terminalActionKey === `cancel:${row.id}`">已取消</el-button>
            </template>
          </el-popconfirm>
          <el-popconfirm
            v-if="canDeleteOrder(row)"
            width="300"
            title="删除后订单及全部子订单将无法恢复，确认删除？"
            confirm-button-text="确认删除"
            cancel-button-text="返回"
            @confirm="handleDeleteOrder(row.id)"
          >
            <template #reference><el-button size="small" link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

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
          <el-col :span="8">
            <el-form-item label="订单号" prop="order_no">
              <el-input v-model="copyForm.order_no" maxlength="50" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="平台订单号" prop="source_order_no">
              <el-input v-model="copyForm.source_order_no" maxlength="100" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="8">
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
    <el-drawer v-model="detailDrawerVisible" :title="`订单明细 - ${currentOrder?.order_no || ''}`" size="700px" destroy-on-close>
      <!-- 平台信息 -->
      <el-descriptions :column="2" border size="small" title="平台信息" class="detail-section">
        <el-descriptions-item label="来源平台">{{ websiteNameMap[currentOrder?.website_id] || currentOrder?.website_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台订单号">{{ currentOrder?.source_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台下单时间">{{ currentOrder?.platform_order_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台分类">
          <el-tag size="small" v-if="currentOrder?.platform_item_type">{{ currentOrder.platform_item_type }}</el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="商品标题" :span="2">{{ currentOrder?.product_title || currentOrder?.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="交易物品">{{ currentOrder?.trade_item_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="资产类型">{{ currentOrder?.asset_type || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 交易信息 -->
      <el-descriptions :column="3" border size="small" title="交易信息" class="detail-section">
        <el-descriptions-item label="平台售价">₩ {{ currentOrder?.platform_price ? Number(currentOrder.platform_price).toLocaleString() : '-' }}</el-descriptions-item>
        <el-descriptions-item label="上架数量">{{ currentOrder?.quantity || '-' }}</el-descriptions-item>
        <el-descriptions-item label="已售数量">{{ currentOrder?.sale_quantity || '-' }}</el-descriptions-item>
        <el-descriptions-item label="买家角色">{{ currentOrder?.buyer_character || '-' }}</el-descriptions-item>
        <el-descriptions-item label="交付资产">{{ currentOrder?.asset_type }} × {{ currentOrder?.asset_amount || 0 }}</el-descriptions-item>
        <el-descriptions-item label="交付状态">
          <el-tag :type="deliveryStatusType(currentOrder)" size="small">{{ deliveryStatusLabel(currentOrder) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="currentOrder?.last_error_code"
        class="detail-section"
        type="error"
        :closable="false"
        show-icon
        :title="deliveryStatusLabel(currentOrder)"
        :description="currentOrder.last_error_message || errorCodeLabel(currentOrder.last_error_code)"
      />
      <div class="retry-resume-info detail-section" v-if="currentOrder?.last_error_code && canRetryOrder(currentOrder)">
        <strong>重新尝试将执行：</strong>{{ retryActionLabel(currentOrder) }}
      </div>

      <section v-if="currentOrder?.game_trade_screenshot" class="detail-section game-trade-proof">
        <div class="game-trade-proof-title">
          <strong>游戏交易证据</strong>
          <span>最终确认前保存于 {{ currentOrder.game_trade_screenshot_at || '-' }}</span>
        </div>
        <el-image
          class="game-trade-proof-image"
          :src="currentOrder.game_trade_screenshot"
          :preview-src-list="[currentOrder.game_trade_screenshot]"
          fit="contain"
        />
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

      <!-- 订单信息 -->
      <el-descriptions :column="2" border size="small" title="订单信息" class="detail-section">
        <el-descriptions-item label="游戏">{{ gameNameMap[currentOrder?.game_id] || currentOrder?.game_id }}</el-descriptions-item>
        <el-descriptions-item label="大区">{{ currentOrder?.region_name || regionNameMap[currentOrder?.region_id] || currentOrder?.region_id }}</el-descriptions-item>
        <el-descriptions-item label="大区编码">
          <code class="region-code">{{ currentOrder?.region_code || regionCodeMap[currentOrder?.region_id] || '-' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="orderStatusType(currentOrder?.status)" size="small">{{ orderStatusLabel(currentOrder?.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总金额">¥ {{ Number(currentOrder?.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentOrder?.customer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{ currentOrder?.customer_contact || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分配机器">{{ machineNameMap[currentOrder?.assigned_machine_id] || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentOrder?.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="currentOrder?.last_error_code" label="失败信息" :span="2">
          <el-tag type="danger" size="small">{{ errorCodeLabel(currentOrder.last_error_code) }}</el-tag>
          <span class="error-code-text">{{ currentOrder.last_error_code }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentOrder?.created_at }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>明细列表</el-divider>
      <div class="order-action-bar">
        <el-button type="primary" plain size="small" :loading="copyLoadingOrderId === currentOrder?.id" @click="openCopyDialog(currentOrder)">复制订单</el-button>
        <el-button type="primary" plain size="small" @click="openOrderLogs(currentOrder)">查看订单日志</el-button>
        <el-button v-if="canRetryOrder(currentOrder)" type="warning" size="small" :loading="retryingOrderId === currentOrder?.id" @click="handleRetryOrder(currentOrder, true)">
          <el-icon><RefreshRight /></el-icon> 重新尝试
        </el-button>
        <el-popconfirm
          v-if="canCompleteOrder(currentOrder)"
          width="320"
          title="确认设为已完成？系统会将子订单标记完成，并按已交付处理库存。"
          confirm-button-text="确认完成"
          cancel-button-text="返回"
          @confirm="handleTerminalOrder(currentOrder, 'complete', true)"
        >
          <template #reference><el-button type="success" size="small">设为已完成</el-button></template>
        </el-popconfirm>
        <el-popconfirm
          v-if="canCancelOrder(currentOrder)"
          width="300"
          title="确认设为已取消？取消后该订单不能重新尝试。"
          confirm-button-text="确认取消"
          cancel-button-text="返回"
          @confirm="handleTerminalOrder(currentOrder, 'cancel', true)"
        >
          <template #reference><el-button type="warning" plain size="small">设为已取消</el-button></template>
        </el-popconfirm>
      </div>
      <div v-if="currentOrder?.status === 'pending'" class="detail-toolbar">
        <el-select v-model="addDetailItemId" placeholder="选择物品添加" filterable style="width: 200px">
          <el-option v-for="i in detailItemOptions" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
        </el-select>
        <el-input-number v-model="addDetailQty" :min="1" :max="9999" size="default" style="width:110px" />
        <el-button type="primary" size="small" @click="handleAddDetail" :disabled="!addDetailItemId">添加</el-button>
      </div>
      <el-table :data="detailList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
        <el-table-column prop="item_name" label="物品名称" min-width="140" />
        <el-table-column prop="bundle_name" label="来源套装" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" type="info" v-if="row.bundle_name">{{ row.bundle_name }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="图片" width="60">
          <template #default="{ row }">
            <el-image v-if="row.item_image" :src="row.item_image" :preview-src-list="[row.item_image]" style="width:36px;height:36px" fit="cover" />
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="70" align="center" />
        <el-table-column prop="unit_price" label="单价" width="80" align="right">
          <template #default="{ row }">{{ Number(row.unit_price || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="subtotal" label="小计" width="80" align="right">
          <template #default="{ row }">{{ Number(row.subtotal || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="进货价" width="80" align="right">
          <template #default="{ row }">{{ row.purchase_price != null ? Number(row.purchase_price).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="出货价" width="80" align="right">
          <template #default="{ row }">{{ row.selling_price != null ? Number(row.selling_price).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="detailStatusType(row.status)" size="small">{{ detailStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" v-if="currentOrder?.status === 'pending'">
          <template #default="{ row }">
            <el-popconfirm title="确认删除？" @confirm="handleDeleteDetail(row.id)">
              <template #reference><el-button size="small" link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 订单自动交付日志 -->
    <el-dialog
      v-model="orderLogsDialogVisible"
      :title="`订单日志 · ${orderLogTarget?.order_no || orderLogTarget?.source_order_no || orderLogTarget?.id || ''}`"
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
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import {
  getAllGames, getAllRegions, getAllMachines, getAllItems, getAllWebsites,
  getAllAccounts, getAllGameAccounts,
  getOrders, getOrder, getOrderLogs, copyOrder, deleteOrder,
  addOrderDetail, deleteOrderDetail, retryOrder, completeOrder, cancelOrder,
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
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterStatus = ref('')
const filterDeliveryStatus = ref('')
const loading = ref(false)
const route = useRoute()

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.name])))
const regionCodeMap = computed(() => Object.fromEntries(allRegions.value.map(r => [r.id, r.code])))
const machineNameMap = computed(() => Object.fromEntries(machineList.value.map(m => [m.id, m.name || m.mac_address])))
const websiteNameMap = computed(() => Object.fromEntries(websiteList.value.map(w => [w.id, w.name])))

function orderStatusLabel(s) { return { pending: '待分配', assigned: '已分配', processing: '处理中', abnormal: '异常', completed: '已完成', cancelled: '已取消' }[s] || s }
function orderStatusType(s) { return { pending: 'warning', assigned: 'primary', processing: '', abnormal: 'danger', completed: 'success', cancelled: 'info' }[s] || '' }
function detailStatusLabel(s) { return { pending: '待处理', processing: '处理中', completed: '已完成', cancelled: '已取消', failed: '失败' }[s] || s }
function detailStatusType(s) { return { pending: 'warning', processing: '', completed: 'success', cancelled: 'info', failed: 'danger' }[s] || '' }
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
    TRADE_RESULT_UNCERTAIN: '交易结果待复核',
  }[code] || code || '未知异常'
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
function canRetryOrder(order) { return Boolean(order?.retryable) }
function isTerminalOrder(order) { return ['completed', 'cancelled'].includes(order?.status) }
function canCompleteOrder(order) { return Boolean(order) && !isTerminalOrder(order) && order?.delivery_status !== 'review_required' }
function canCancelOrder(order) {
  return Boolean(order)
    && !isTerminalOrder(order)
    && order?.delivery_status !== 'review_required'
    && order?.delivery_status !== 'wait_web_confirm'
    && !order?.game_delivered_at
}
function canDeleteOrder(order) {
  if (!order) return false
  if (order.status === 'cancelled') return true
  return ['pending', 'abnormal'].includes(order.status)
    && !['queued', 'offered', 'assigned', 'review_required', 'wait_web_confirm'].includes(order.delivery_status)
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
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterDeliveryStatus.value) params.delivery_status = filterDeliveryStatus.value
    const res = await getOrders(params)
    list.value = res.items; total.value = res.total
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }

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
  if (['greeting_success', 'dequeue_assignment', 'offer_accepted', 'trade_completed', 'game_trade_completed'].includes(type)) return 'success'
  if (['queue_assignment', 'queued_offer_rejected', 'queued_offer_expired', 'queued_start_failed', 'queued_worker_disconnected', 'retry_greeting', 'retry_assignment', 'reset_to_greeting', 'manual_dispatch'].includes(type)) return 'warning'
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
const autoRefreshEnabled = ref(false)
const refreshIntervalSeconds = ref(10)
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
    refreshIntervalSeconds.value = 10
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
  order_no: [{ required: true, message: '请输入新订单号', trigger: 'blur' }],
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
})

onBeforeUnmount(clearAutoRefreshTimer)
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar-actions { display: flex; gap: 12px; align-items: center; margin-left: auto; }
.auto-refresh-controls { display: flex; gap: 8px; align-items: center; }
.auto-refresh-label, .auto-refresh-unit { color: #606266; font-size: 13px; white-space: nowrap; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.detail-toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.order-action-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
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
</style>
