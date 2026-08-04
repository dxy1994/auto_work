<template>
  <el-container class="app-wrapper">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="24"><Monitor /></el-icon>
        <span>中控平台</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#409eff"
      >
        <el-sub-menu index="platform">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>平台接入</span>
          </template>
          <el-menu-item index="/platforms">
            <el-icon><Grid /></el-icon>
            <span>交易平台</span>
          </el-menu-item>
          <el-menu-item index="/platform-accounts">
            <el-icon><User /></el-icon>
            <span>平台账号</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="game-config">
          <template #title>
            <el-icon><Trophy /></el-icon>
            <span>游戏配置</span>
          </template>
          <el-menu-item index="/games">
            <el-icon><Trophy /></el-icon>
            <span>游戏管理</span>
          </el-menu-item>
          <el-menu-item index="/game-items">
            <el-icon><GoodsFilled /></el-icon>
            <span>游戏物品</span>
          </el-menu-item>
          <el-menu-item index="/region-inventories">
            <el-icon><Box /></el-icon>
            <span>大区库存</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="machine">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>机器管理</span>
          </template>
          <el-menu-item index="/machines">
            <el-icon><Monitor /></el-icon>
            <span>机器列表</span>
          </el-menu-item>
          <el-menu-item index="/game-accounts">
            <el-icon><Avatar /></el-icon>
            <span>游戏账号</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="order">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>订单交易</span>
          </template>
          <el-menu-item index="/orders">
            <el-icon><Document /></el-icon>
            <span>订单管理</span>
            <span v-if="manualAlerts.total" class="menu-alert-count">{{ manualAlerts.total }}</span>
          </el-menu-item>
          <el-menu-item index="/platform-sales-products">
            <el-icon><ShoppingBag /></el-icon>
            <span>在售商品</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="device">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>设备管理</span>
          </template>
          <el-menu-item index="/mk-devices">
            <el-icon><Mouse /></el-icon>
            <span>Wireless HID</span>
          </el-menu-item>
          <el-menu-item index="/vs-devices">
            <el-icon><VideoCameraFilled /></el-icon>
            <span>视频流设备</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system">
          <template #title>
            <el-icon><Files /></el-icon>
            <span>系统工具</span>
          </template>
          <el-menu-item index="/system-controls">
            <el-icon><Operation /></el-icon>
            <span>系统控制</span>
          </el-menu-item>
          <el-menu-item index="/software-distribution">
            <el-icon><Download /></el-icon>
            <span>软件分发</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-main class="main-content">
      <el-badge
        v-if="manualAlerts.total"
        :value="manualAlerts.total > 99 ? '99+' : manualAlerts.total"
        class="global-alert-trigger"
      >
        <el-button type="danger" size="large" @click="manualAlerts.drawerVisible = true">
          <el-icon><BellFilled /></el-icon>
          待处理提醒
        </el-button>
      </el-badge>
      <router-view />
    </el-main>
  </el-container>

  <el-dialog
    v-model="manualAlerts.voiceConsentRequired"
    title="开启语音提醒"
    width="440px"
    align-center
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <div class="voice-consent-content">
      <el-icon class="voice-consent-icon" :size="46"><BellFilled /></el-icon>
      <div>
        <p>中控平台会在订单需要人工处理时持续语音提醒，直到异常状态恢复。</p>
        <p class="voice-consent-hint">同意状态仅保存在当前浏览器中，每个新浏览器需要各自开启一次。</p>
      </div>
    </div>
    <el-alert
      v-if="!manualAlerts.speechSupported"
      title="当前浏览器不支持语音合成，请使用 Chrome 或 Edge"
      type="error"
      :closable="false"
      show-icon
    />
    <template #footer>
      <el-button
        type="primary"
        size="large"
        :disabled="!manualAlerts.speechSupported"
        @click="manualAlerts.grantVoiceConsent"
      >
        <el-icon><Microphone /></el-icon>
        同意并开启语音提醒
      </el-button>
    </template>
  </el-dialog>

  <el-drawer
    v-model="manualAlerts.drawerVisible"
    title="待处理提醒"
    size="520px"
    append-to-body
    @open="manualAlerts.refresh"
  >
    <div class="alert-drawer-toolbar">
      <div>
        <div class="alert-count-title">共 {{ manualAlerts.total }} 条待处理提醒</div>
        <div class="alert-count-hint">订单异常恢复后自动移除；机器掉线提醒在重连后自动移除</div>
      </div>
      <div class="alert-actions">
        <el-button
          v-if="manualAlerts.total"
          type="warning"
          plain
          @click="manualAlerts.speak(true)"
        >
          <el-icon><Microphone /></el-icon>
          立即播报
        </el-button>
        <el-button :loading="manualAlerts.loading" @click="manualAlerts.refresh">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="!manualAlerts.speechSupported"
      title="当前浏览器不支持语音合成，请使用 Chrome 或 Edge"
      type="error"
      :closable="false"
      show-icon
      class="alert-notice"
    />
    <el-alert
      v-else-if="manualAlerts.needsInteraction && manualAlerts.total"
      title="浏览器阻止了自动语音，请点击“立即播报”启用"
      type="warning"
      :closable="false"
      show-icon
      class="alert-notice"
    />
    <el-alert
      v-if="manualAlerts.fetchError"
      :title="manualAlerts.fetchError"
      description="已保留上一次异常列表，提醒不会因为短暂断线而停止"
      type="error"
      :closable="false"
      show-icon
      class="alert-notice"
    />

    <el-empty v-if="!manualAlerts.total && !manualAlerts.loading" description="当前没有待人工处理的异常" />
    <div v-else class="manual-alert-list">
      <article
        v-for="item in manualAlerts.items"
        :key="item.id"
        class="manual-alert-card"
        :class="`severity-${item.severity}`"
      >
        <div class="manual-alert-heading">
          <el-tag :type="severityType(item.severity)" effect="dark" size="small">
            {{ severityLabel(item.severity) }}
          </el-tag>
          <strong>{{ item.title }}</strong>
          <span class="manual-alert-time">{{ formatTime(item.occurred_at) }}</span>
          <el-button
            v-if="item.entity_type === 'system'"
            class="manual-alert-close"
            link
            aria-label="关闭提醒"
            :loading="manualAlerts.dismissLoadingId === item.id"
            @click="handleDismissSystemAlert(item)"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <div v-if="item.entity_type !== 'system'" class="manual-alert-order">
          订单：{{ item.source_order_no || item.order_no || item.entity_id }}
          <span v-if="item.buyer_character">· 买家 {{ item.buyer_character }}</span>
        </div>
        <div v-else class="manual-alert-machine">
          <div v-if="item.machine_id" class="manual-alert-machine-primary">
            <el-icon><Monitor /></el-icon>
            <strong>{{ machineDisplayName(item) }}</strong>
            <span>机器 ID #{{ item.machine_id }}</span>
          </div>
          <div v-if="machineDetails(item).length" class="manual-alert-machine-details">
            <span v-for="detail in machineDetails(item)" :key="detail">{{ detail }}</span>
          </div>
          <div v-if="item.account_id" class="manual-alert-account">平台账号 #{{ item.account_id }}</div>
        </div>
        <p>{{ item.message }}</p>
        <template v-if="item.entity_type === 'buyer_review'">
          <div class="alert-review-line">
            订单客户：<strong>{{ item.expected_buyer || '-' }}</strong>
            · OCR：<strong>{{ item.observed_buyer || '未识别' }}</strong>
            · {{ formatConfidence(item.ocr_confidence) }}
          </div>
          <el-image
            class="alert-review-image"
            :src="item.screenshot_data_url"
            :preview-src-list="[item.screenshot_data_url]"
            fit="contain"
          />
          <div class="alert-review-actions">
            <el-button type="danger" :loading="manualAlerts.reviewDecisionLoading" @click="handleBuyerReview(false, item)">不同意</el-button>
            <el-button type="success" :loading="manualAlerts.reviewDecisionLoading" @click="handleBuyerReview(true, item)">同意</el-button>
          </div>
        </template>
        <div class="manual-alert-footer">
          <el-tag v-if="item.error_code" type="danger" size="small">{{ item.error_code }}</el-tag>
          <el-button
            v-if="item.entity_type === 'system'"
            link
            type="primary"
            :loading="manualAlerts.dismissLoadingId === item.id"
            @click="handleDismissSystemAlert(item)"
          >关闭提醒</el-button>
          <el-button v-else link type="primary" @click="openAlertOrder(item)">查看并处理</el-button>
        </div>
      </article>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useManualAlertStore } from './stores/manualAlerts'

const route = useRoute()
const router = useRouter()
const manualAlerts = useManualAlertStore()
const activeMenu = computed(() => route.path)

function severityType(severity) {
  return { critical: 'danger', danger: 'danger', warning: 'warning' }[severity] || 'info'
}

function severityLabel(severity) {
  return { critical: '紧急复核', danger: '交易异常', warning: '配置异常' }[severity] || '待处理'
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function formatConfidence(value) {
  const confidence = Number(value)
  return Number.isFinite(confidence) && confidence >= 0 ? `${confidence.toFixed(1)}%` : '无法识别'
}

function machineDisplayName(item) {
  return item.machine_name || item.machine_hostname || item.machine_mac_address || `未命名机器 #${item.machine_id}`
}

function machineDetails(item) {
  const details = []
  if (item.machine_hostname && item.machine_hostname !== machineDisplayName(item)) {
    details.push(`主机名 ${item.machine_hostname}`)
  }
  if (item.machine_mac_address && item.machine_mac_address !== machineDisplayName(item)) {
    details.push(`MAC ${item.machine_mac_address}`)
  }
  if (item.machine_ip_address) details.push(`IP ${item.machine_ip_address}`)
  return details
}

async function handleBuyerReview(approved, item) {
  try {
    const response = await manualAlerts.decideBuyerReview(item, approved)
    if (response) ElMessage.success(response.message)
  } catch (error) {
    ElMessage.error(error.message || '审核决定提交失败')
  }
}

async function handleDismissSystemAlert(item) {
  try {
    const response = await manualAlerts.dismissSystemAlert(item)
    if (response) ElMessage.success(response.message || '提醒已关闭')
  } catch (error) {
    ElMessage.error(error.message || '关闭提醒失败')
  }
}

function openAlertOrder(item) {
  manualAlerts.drawerVisible = false
  router.push({
    path: '/orders',
    query: { alert_order_id: item.entity_id, alert_nonce: Date.now() },
  })
}

onMounted(() => manualAlerts.start())
onBeforeUnmount(() => manualAlerts.stop())
</script>

<style>
/* 全局样式 */
*, *::before, *::after { box-sizing: border-box; }
html, body, #app { height: 100%; margin: 0; padding: 0; }

.app-wrapper { height: 100vh; }

.sidebar {
  background-color: #001529;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #ffffff1a;
}
.sidebar-menu { border-right: none; flex: 1; overflow-y: auto; }

.main-content {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
  position: relative;
}

.global-alert-trigger {
  position: fixed;
  z-index: 1000;
  top: 16px;
  right: 28px;
}
.global-alert-trigger .el-button { box-shadow: 0 6px 18px rgba(245, 108, 108, .35); }
.voice-consent-content { display: flex; gap: 16px; align-items: flex-start; }
.voice-consent-content p { margin: 0 0 10px; color: #303133; line-height: 1.7; }
.voice-consent-icon { flex-shrink: 0; color: #e6a23c; }
.voice-consent-content .voice-consent-hint { color: #909399; font-size: 13px; }
.menu-alert-count {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #f56c6c;
  color: #fff;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}
.alert-drawer-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}
.alert-count-title { color: #303133; font-size: 18px; font-weight: 700; }
.alert-count-hint { margin-top: 6px; color: #909399; font-size: 12px; }
.alert-actions { display: flex; flex-shrink: 0; }
.alert-notice { margin-top: 14px; }
.manual-alert-list { display: grid; gap: 12px; margin-top: 16px; }
.manual-alert-card {
  padding: 14px 16px;
  border: 1px solid #e4e7ed;
  border-left-width: 5px;
  border-radius: 8px;
  background: #fff;
}
.manual-alert-card.severity-critical,
.manual-alert-card.severity-danger { border-left-color: #f56c6c; }
.manual-alert-card.severity-warning { border-left-color: #e6a23c; }
.manual-alert-heading { display: flex; align-items: center; gap: 8px; }
.manual-alert-heading strong { color: #303133; }
.manual-alert-time { margin-left: auto; color: #909399; font-size: 12px; }
.manual-alert-close { margin-left: 2px; color: #909399; }
.manual-alert-close:hover { color: #f56c6c; }
.manual-alert-order { margin-top: 10px; color: #606266; font-size: 13px; }
.manual-alert-machine {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f5f7fa;
  color: #606266;
  font-size: 13px;
}
.manual-alert-machine-primary { display: flex; align-items: center; gap: 7px; }
.manual-alert-machine-primary strong { color: #303133; font-size: 14px; }
.manual-alert-machine-primary span { margin-left: auto; color: #909399; font-size: 12px; }
.manual-alert-machine-details { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 7px; color: #606266; }
.manual-alert-account { margin-top: 7px; color: #909399; }
.manual-alert-card p { margin: 8px 0; color: #303133; line-height: 1.6; }
.manual-alert-footer { display: flex; align-items: center; justify-content: space-between; min-height: 24px; }
.buyer-review-names { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 18px 0 14px; }
.buyer-review-names div { padding: 12px; border-radius: 8px; background: #f5f7fa; }
.buyer-review-names span { display: block; margin-bottom: 6px; color: #909399; font-size: 12px; }
.buyer-review-names strong { color: #303133; word-break: break-all; }
.buyer-review-image, .alert-review-image { width: 100%; min-height: 100px; border: 1px solid #dcdfe6; border-radius: 8px; background: #111827; }
.alert-review-line { margin: 8px 0; color: #606266; font-size: 13px; }
.alert-review-image { min-height: 76px; max-height: 150px; }
.alert-review-actions { display: flex; justify-content: flex-end; margin: 10px 0; }
</style>
