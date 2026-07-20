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
          <el-menu-item index="/platform-schedules">
            <el-icon><Clock /></el-icon>
            <span>定时调度</span>
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
        </el-sub-menu>

        <el-sub-menu index="device">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>设备管理</span>
          </template>
          <el-menu-item index="/mk-devices">
            <el-icon><Mouse /></el-icon>
            <span>键鼠设备</span>
          </el-menu-item>
          <el-menu-item index="/vs-devices">
            <el-icon><VideoCameraFilled /></el-icon>
            <span>视频流设备</span>
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
          待人工处理
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

  <el-dialog
    v-model="manualAlerts.reviewDialogVisible"
    title="确认交易申请客户"
    width="650px"
    align-center
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <template v-if="manualAlerts.currentBuyerReview">
      <el-alert
        title="OCR 置信度不足或玩家名不匹配，本次必须由人工判断"
        type="warning"
        :closable="false"
        show-icon
      />
      <div class="buyer-review-names">
        <div><span>订单客户名</span><strong>{{ manualAlerts.currentBuyerReview.expected_buyer || '-' }}</strong></div>
        <div><span>OCR 识别（仅参考）</span><strong>{{ manualAlerts.currentBuyerReview.observed_buyer || '未识别' }}</strong></div>
        <div><span>OCR 置信度</span><strong>{{ formatConfidence(manualAlerts.currentBuyerReview.ocr_confidence) }}</strong></div>
      </div>
      <el-image
        class="buyer-review-image"
        :src="manualAlerts.currentBuyerReview.screenshot_data_url"
        :preview-src-list="[manualAlerts.currentBuyerReview.screenshot_data_url]"
        fit="contain"
      />
    </template>
    <template #footer>
      <el-button
        type="danger"
        size="large"
        :loading="manualAlerts.reviewDecisionLoading"
        @click="handleBuyerReview(false)"
      >不同意并拒绝申请</el-button>
      <el-button
        type="success"
        size="large"
        :loading="manualAlerts.reviewDecisionLoading"
        @click="handleBuyerReview(true)"
      >同意并继续交易</el-button>
    </template>
  </el-dialog>

  <el-drawer
    v-model="manualAlerts.drawerVisible"
    title="待人工处理"
    size="520px"
    append-to-body
    @open="manualAlerts.refresh"
  >
    <div class="alert-drawer-toolbar">
      <div>
        <div class="alert-count-title">共 {{ manualAlerts.total }} 条未处理异常</div>
        <div class="alert-count-hint">后台状态恢复后自动移除并停止播报</div>
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
        </div>
        <div class="manual-alert-order">
          订单：{{ item.source_order_no || item.order_no || item.entity_id }}
          <span v-if="item.buyer_character">· 买家 {{ item.buyer_character }}</span>
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
          <el-button link type="primary" @click="openAlertOrder(item)">查看并处理</el-button>
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

async function handleBuyerReview(approved, item = manualAlerts.currentBuyerReview) {
  try {
    const response = await manualAlerts.decideBuyerReview(item, approved)
    if (response) ElMessage.success(response.message)
  } catch (error) {
    ElMessage.error(error.message || '审核决定提交失败')
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
.sidebar-menu { border-right: none; flex: 1; }

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
.manual-alert-order { margin-top: 10px; color: #606266; font-size: 13px; }
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
