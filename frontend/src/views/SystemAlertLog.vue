<template>
  <div class="alert-log-page">
    <header class="page-heading">
      <div>
        <div class="heading-kicker">ALERT AUDIT TRAIL</div>
        <h1>系统告警日志</h1>
        <p>查看每条系统告警从产生到关闭的通知轨迹，确认中控展示和语音播报是否真正执行。</p>
      </div>
      <div class="heading-actions">
        <div class="query-state">
          <span class="state-dot" :class="{ active: !loading && !loadError }"></span>
          <span>{{ loadError ? '查询异常' : `共 ${total} 条记录` }}</span>
          <small>{{ polledAt ? `更新于 ${formatTime(polledAt)}` : '等待首次查询' }}</small>
        </div>
        <el-button :loading="loading" @click="fetchList">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </header>

    <section class="filter-panel" aria-label="系统告警筛选">
      <el-select v-model="filters.status" placeholder="全部状态" clearable @change="applyFilters">
        <el-option label="进行中" value="open" />
        <el-option label="已关闭" value="dismissed" />
      </el-select>
      <el-select v-model="filters.severity" placeholder="全部级别" clearable @change="applyFilters">
        <el-option label="紧急" value="critical" />
        <el-option label="异常" value="danger" />
        <el-option label="警告" value="warning" />
        <el-option label="提示" value="info" />
      </el-select>
      <el-select v-model="filters.alertType" placeholder="全部类型" clearable @change="applyFilters">
        <el-option label="机器掉线" value="machine_offline" />
        <el-option label="游戏客户端掉线" value="game_client_disconnected" />
        <el-option label="订单监控停止" value="order_monitor_stopped" />
        <el-option label="库存不一致" value="inventory_mismatch" />
        <el-option label="人工拒绝交易" value="buyer_review_rejected" />
      </el-select>
      <el-input-number
        v-model="filters.machineId"
        :min="1"
        :controls="false"
        placeholder="机器 ID"
        class="id-filter"
        @keyup.enter="applyFilters"
      />
      <el-input-number
        v-model="filters.accountId"
        :min="1"
        :controls="false"
        placeholder="账号 ID"
        class="id-filter"
        @keyup.enter="applyFilters"
      />
      <el-input
        v-model="filters.keyword"
        placeholder="标题、正文、类型或来源键"
        clearable
        class="keyword-filter"
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="applyFilters">查询</el-button>
      <el-button link @click="resetFilters">重置</el-button>
    </section>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
      class="load-alert"
    />

    <section class="ledger-shell" aria-label="系统告警记录">
      <el-table
        :data="records"
        v-loading="loading"
        row-key="alert_id"
        height="100%"
        class="alert-table"
        :row-class-name="rowClassName"
        @row-click="openDetails"
      >
        <el-table-column label="首次 / 最近发生" width="170">
          <template #default="{ row }">
            <div class="time-cell">
              <strong>{{ formatTime(row.occurred_at) }}</strong>
              <span v-if="row.last_occurred_at && row.last_occurred_at !== row.occurred_at">
                最近 {{ formatTime(row.last_occurred_at) }}
              </span>
              <span v-else>单次发生</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="92" align="center">
          <template #default="{ row }">
            <span class="status-mark" :class="row.status">
              <i></i>{{ statusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="告警" min-width="280">
          <template #default="{ row }">
            <div class="alert-copy">
              <div>
                <el-tag :type="severityType(row.severity)" size="small" effect="plain">
                  {{ severityLabel(row.severity) }}
                </el-tag>
                <code>{{ alertTypeLabel(row.error_code) }}</code>
              </div>
              <strong>{{ row.title }}</strong>
              <span>{{ row.message || '未记录详细说明' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="190">
          <template #default="{ row }">
            <div class="source-cell">
              <strong>{{ machineLabel(row) }}</strong>
              <span v-if="row.account_id">平台账号 #{{ row.account_id }}</span>
              <span :title="row.source_key">{{ row.source_key || '未记录来源键' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="重复" width="80" align="center">
          <template #default="{ row }">
            <span class="occurrence-count">× {{ row.occurrence_count || 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="通知轨迹" width="188">
          <template #default="{ row }">
            <div class="delivery-track">
              <span :class="{ delivered: row.presentation_count > 0 }">
                <el-icon><View /></el-icon>界面 {{ row.presentation_count || 0 }}
              </span>
              <span :class="{ delivered: row.voice_notification_count > 0 }">
                <el-icon><Microphone /></el-icon>语音 {{ row.voice_notification_count || 0 }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="关闭结果" min-width="170">
          <template #default="{ row }">
            <div v-if="row.status === 'dismissed'" class="close-cell">
              <strong>{{ closeTypeLabel(row.close_type) }}</strong>
              <span>{{ formatTime(row.dismissed_at) }}</span>
            </div>
            <span v-else class="pending-close">等待故障恢复或人工关闭</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="96" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetails(row)">查看流水</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有符合当前条件的系统告警" />
        </template>
      </el-table>
    </section>

    <footer class="ledger-footer">
      <span>点击记录可查看每次展示、播报与关闭事件。</span>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="handlePageSizeChange"
      />
    </footer>

    <el-drawer
      v-model="detailsVisible"
      :size="'min(660px, 94vw)'"
      append-to-body
      class="alert-detail-drawer"
      @closed="clearDetails"
    >
      <template #header>
        <div v-if="selectedAlert" class="drawer-heading">
          <div class="drawer-heading__tags">
            <el-tag :type="severityType(selectedAlert.severity)" effect="dark" size="small">
              {{ severityLabel(selectedAlert.severity) }}
            </el-tag>
            <span class="status-mark" :class="selectedAlert.status">
              <i></i>{{ statusLabel(selectedAlert.status) }}
            </span>
          </div>
          <h2>{{ selectedAlert.title }}</h2>
          <code>#{{ selectedAlert.alert_id }} · {{ selectedAlert.error_code }}</code>
        </div>
      </template>

      <div v-if="selectedAlert" class="drawer-content">
        <section class="incident-message">
          <span>告警说明</span>
          <p>{{ selectedAlert.message || '未记录详细说明' }}</p>
        </section>

        <section class="delivery-summary" aria-label="通知送达摘要">
          <div>
            <el-icon><WarningFilled /></el-icon>
            <span>发生</span>
            <strong>{{ selectedAlert.occurrence_count || 1 }}</strong>
            <small>次</small>
          </div>
          <div :class="{ delivered: selectedAlert.presentation_count > 0 }">
            <el-icon><View /></el-icon>
            <span>界面展示</span>
            <strong>{{ selectedAlert.presentation_count || 0 }}</strong>
            <small>次</small>
          </div>
          <div :class="{ delivered: selectedAlert.voice_notification_count > 0 }">
            <el-icon><Microphone /></el-icon>
            <span>语音启动</span>
            <strong>{{ selectedAlert.voice_notification_count || 0 }}</strong>
            <small>次</small>
          </div>
        </section>

        <dl class="incident-facts">
          <div><dt>来源机器</dt><dd>{{ machineLabel(selectedAlert) }}</dd></div>
          <div><dt>平台账号</dt><dd>{{ selectedAlert.account_id ? `#${selectedAlert.account_id}` : '-' }}</dd></div>
          <div><dt>来源键</dt><dd :title="selectedAlert.source_key">{{ selectedAlert.source_key || '-' }}</dd></div>
          <div><dt>首次发生</dt><dd>{{ formatTime(selectedAlert.occurred_at) }}</dd></div>
          <div><dt>最近发生</dt><dd>{{ formatTime(selectedAlert.last_occurred_at) }}</dd></div>
          <div><dt>关闭方式</dt><dd>{{ selectedAlert.status === 'dismissed' ? closeTypeLabel(selectedAlert.close_type) : '尚未关闭' }}</dd></div>
        </dl>

        <section v-if="selectedAlert.status === 'dismissed'" class="close-note">
          <el-icon><CircleCheckFilled /></el-icon>
          <div>
            <strong>{{ closeTypeLabel(selectedAlert.close_type) }} · {{ formatTime(selectedAlert.dismissed_at) }}</strong>
            <p>{{ selectedAlert.close_reason || '未记录关闭原因' }}</p>
            <small>执行方：{{ actorLabel(selectedAlert.closed_by) }}</small>
          </div>
        </section>

        <section class="event-ledger">
          <div class="section-heading">
            <div>
              <span>生命周期流水</span>
              <strong>{{ events.length }} 条事件</strong>
            </div>
            <el-button link :loading="eventsLoading" @click="loadEvents(selectedAlert.alert_id)">重新读取</el-button>
          </div>

          <el-skeleton v-if="eventsLoading" :rows="5" animated />
          <el-alert v-else-if="eventsError" :title="eventsError" type="error" :closable="false" show-icon />
          <el-empty v-else-if="!events.length" description="该告警没有事件流水" :image-size="72" />
          <ol v-else class="event-list">
            <li v-for="event in events" :key="event.id" :class="`event-${event.event_type}`">
              <span class="event-marker"><el-icon><component :is="eventIcon(event.event_type)" /></el-icon></span>
              <div class="event-card">
                <div>
                  <strong>{{ eventTypeLabel(event.event_type) }}</strong>
                  <time>{{ formatTime(event.event_at) }}</time>
                </div>
                <p>{{ event.details || '未记录补充说明' }}</p>
                <span>执行方：{{ actorLabel(event.actor) }}</span>
              </div>
            </li>
          </ol>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { markRaw, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  BellFilled,
  CircleCheckFilled,
  Clock,
  CloseBold,
  Microphone,
  Refresh,
  RefreshRight,
  UploadFilled,
  View,
  WarningFilled,
} from '@element-plus/icons-vue'
import { getSystemAlertEvents, getSystemAlertHistory } from '../api'

const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const loadError = ref('')
const polledAt = ref('')
const detailsVisible = ref(false)
const selectedAlert = ref(null)
const events = ref([])
const eventsLoading = ref(false)
const eventsError = ref('')

const filters = reactive({
  status: '',
  severity: '',
  alertType: '',
  machineId: null,
  accountId: null,
  keyword: '',
})

const eventLabels = {
  opened: '告警产生',
  refreshed: '相同故障再次发生',
  presented: '中控已展示',
  voice_started: '语音播报已启动',
  voice_completed: '语音播报完成',
  voice_failed: '语音播报失败',
  manual_dismissed: '人工关闭',
  auto_recovered: '故障自动恢复',
  legacy_imported: '旧记录迁入',
}

async function fetchList() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getSystemAlertHistory({
      page: page.value,
      page_size: pageSize.value,
      status: filters.status || undefined,
      severity: filters.severity || undefined,
      alert_type: filters.alertType || undefined,
      machine_id: filters.machineId || undefined,
      account_id: filters.accountId || undefined,
      keyword: filters.keyword.trim() || undefined,
    })
    records.value = response.items || []
    total.value = Number(response.total || 0)
    polledAt.value = response.polled_at || ''
  } catch (error) {
    loadError.value = error.message || '系统告警日志读取失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  fetchList()
}

function resetFilters() {
  Object.assign(filters, {
    status: '',
    severity: '',
    alertType: '',
    machineId: null,
    accountId: null,
    keyword: '',
  })
  applyFilters()
}

function handlePageSizeChange() {
  page.value = 1
  fetchList()
}

async function openDetails(row) {
  selectedAlert.value = row
  detailsVisible.value = true
  await loadEvents(row.alert_id)
}

async function loadEvents(alertId) {
  eventsLoading.value = true
  eventsError.value = ''
  try {
    const response = await getSystemAlertEvents(alertId)
    events.value = response.items || []
  } catch (error) {
    eventsError.value = error.message || '告警事件流水读取失败'
  } finally {
    eventsLoading.value = false
  }
}

function clearDetails() {
  selectedAlert.value = null
  events.value = []
  eventsError.value = ''
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function statusLabel(status) {
  return status === 'open' ? '进行中' : '已关闭'
}

function severityType(severity) {
  return { critical: 'danger', danger: 'danger', warning: 'warning', info: 'info' }[severity] || 'info'
}

function severityLabel(severity) {
  return { critical: '紧急', danger: '异常', warning: '警告', info: '提示' }[severity] || severity || '未知'
}

function alertTypeLabel(type) {
  return {
    machine_offline: '机器掉线',
    game_client_disconnected: '游戏客户端掉线',
    order_monitor_stopped: '订单监控停止',
    inventory_mismatch: '库存不一致',
  }[type] || type || '未知类型'
}

function closeTypeLabel(type) {
  return {
    manual_dismissed: '人工关闭',
    auto_recovered: '自动恢复',
    legacy_unknown: '旧版状态未知',
  }[type] || type || '未记录'
}

function eventTypeLabel(type) {
  return eventLabels[type] || type || '未知事件'
}

function actorLabel(actor) {
  return {
    backend: '中控后端',
    'control-ui': '中控浏览器',
    migration: '数据迁移',
  }[actor] || actor || '未记录'
}

function machineLabel(row) {
  const identity = row.machine_name || row.machine_hostname || row.machine_mac_address
  if (identity && row.machine_id) return `${identity} · #${row.machine_id}`
  if (identity) return identity
  return row.machine_id ? `机器 #${row.machine_id}` : '未关联机器'
}

function rowClassName({ row }) {
  return row.status === 'open' ? 'is-open-alert' : ''
}

function eventIcon(type) {
  const icons = {
    opened: WarningFilled,
    refreshed: RefreshRight,
    presented: View,
    voice_started: Microphone,
    voice_completed: CircleCheckFilled,
    voice_failed: CloseBold,
    manual_dismissed: BellFilled,
    auto_recovered: CircleCheckFilled,
    legacy_imported: UploadFilled,
  }
  return markRaw(icons[type] || Clock)
}

onMounted(fetchList)
</script>

<style scoped>
.alert-log-page {
  --ink: #17202a;
  --muted: #687684;
  --line: #dce3e8;
  --paper: #ffffff;
  --canvas: #f4f6f8;
  --danger: #d84a4a;
  --warning: #c47b18;
  --success: #168778;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  color: var(--ink);
}

.page-heading {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.heading-kicker {
  color: #6c7d8a;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .18em;
  margin-bottom: 5px;
}

.page-heading h1 { margin: 0; font-size: 25px; letter-spacing: -.02em; }
.page-heading p { margin: 7px 0 0; color: var(--muted); font-size: 14px; }
.heading-actions { display: flex; gap: 14px; align-items: center; }
.query-state { display: grid; grid-template-columns: 8px auto; column-gap: 8px; align-items: center; text-align: right; }
.query-state span:not(.state-dot) { font-size: 13px; font-weight: 600; }
.query-state small { grid-column: 2; color: #8a96a1; font-size: 11px; }
.state-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--danger); box-shadow: 0 0 0 3px rgba(216,74,74,.12); }
.state-dot.active { background: var(--success); box-shadow: 0 0 0 3px rgba(22,135,120,.12); }

.filter-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  padding: 12px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.86);
  box-shadow: 0 5px 18px rgba(24,42,56,.04);
}
.filter-panel :deep(.el-select) { width: 128px; }
.id-filter { width: 102px; }
.keyword-filter { flex: 1; min-width: 190px; }
.load-alert { margin: 0; }

.ledger-shell {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--paper);
  box-shadow: 0 10px 28px rgba(25,43,57,.06);
}
.alert-table { width: 100%; cursor: pointer; }
.alert-table :deep(th.el-table__cell) { background: #f3f6f8; color: #52616e; font-size: 12px; font-weight: 700; }
.alert-table :deep(.el-table__row.is-open-alert td:first-child) { box-shadow: inset 3px 0 0 var(--danger); }
.alert-table :deep(.el-table__row:hover > td.el-table__cell) { background: #f8fbfc; }

.time-cell, .source-cell, .close-cell, .alert-copy { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.time-cell strong, .close-cell strong { font-size: 12px; font-variant-numeric: tabular-nums; }
.time-cell span, .source-cell span, .close-cell span { color: #87939d; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.source-cell strong { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alert-copy > div { display: flex; align-items: center; gap: 8px; }
.alert-copy code { color: #71808d; font-size: 11px; background: transparent; }
.alert-copy > strong { font-size: 13px; line-height: 1.35; }
.alert-copy > span { color: #7c8994; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-mark { display: inline-flex; align-items: center; gap: 5px; color: #65737e; font-size: 12px; font-weight: 600; white-space: nowrap; }
.status-mark i { width: 7px; height: 7px; border-radius: 50%; background: #8b98a3; }
.status-mark.open { color: #ba3636; }
.status-mark.open i { background: var(--danger); box-shadow: 0 0 0 3px rgba(216,74,74,.12); }
.status-mark.dismissed { color: var(--success); }
.status-mark.dismissed i { background: var(--success); }
.occurrence-count { font-weight: 700; color: #44525e; font-variant-numeric: tabular-nums; }
.delivery-track { display: flex; gap: 6px; }
.delivery-track span { display: inline-flex; align-items: center; gap: 4px; padding: 4px 6px; color: #8a959e; background: #f1f3f5; border-radius: 3px; font-size: 11px; }
.delivery-track span.delivered { color: #147568; background: #e8f5f2; }
.pending-close { color: #a26c27; font-size: 12px; }

.ledger-footer { display: flex; justify-content: space-between; align-items: center; min-height: 32px; color: #7b8893; font-size: 12px; }
.drawer-heading { padding-right: 24px; }
.drawer-heading__tags { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
.drawer-heading h2 { margin: 0 0 6px; font-size: 20px; color: var(--ink); }
.drawer-heading code { color: #73818c; font-size: 11px; }
.drawer-content { display: flex; flex-direction: column; gap: 18px; padding-bottom: 24px; color: var(--ink); }
.incident-message { border-left: 3px solid var(--danger); background: #faf6f5; padding: 13px 15px; }
.incident-message span, .section-heading span { color: #8a6f6c; font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.incident-message p { margin: 6px 0 0; color: #44515c; line-height: 1.65; font-size: 13px; }
.delivery-summary { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--line); }
.delivery-summary > div { display: grid; grid-template-columns: auto 1fr auto auto; align-items: baseline; gap: 5px; padding: 12px; color: #77848e; border-right: 1px solid var(--line); }
.delivery-summary > div:last-child { border-right: 0; }
.delivery-summary > div.delivered { color: var(--success); background: #f2faf8; }
.delivery-summary span { font-size: 11px; }
.delivery-summary strong { font-size: 21px; font-variant-numeric: tabular-nums; }
.delivery-summary small { font-size: 10px; }
.incident-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0; border-top: 1px solid var(--line); border-left: 1px solid var(--line); }
.incident-facts > div { min-width: 0; padding: 10px 12px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.incident-facts dt { color: #8b97a1; font-size: 11px; margin-bottom: 4px; }
.incident-facts dd { margin: 0; font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.close-note { display: flex; gap: 11px; padding: 12px 14px; color: var(--success); background: #edf8f5; border: 1px solid #cde9e2; }
.close-note p { margin: 4px 0; color: #48655f; font-size: 12px; }
.close-note small { color: #79908b; }
.event-ledger { border-top: 1px solid var(--line); padding-top: 16px; }
.section-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.section-heading > div { display: flex; flex-direction: column; gap: 3px; }
.section-heading strong { font-size: 15px; }
.event-list { list-style: none; padding: 0; margin: 0; }
.event-list li { position: relative; display: grid; grid-template-columns: 28px 1fr; gap: 10px; padding-bottom: 14px; }
.event-list li:not(:last-child)::before { content: ''; position: absolute; top: 25px; bottom: -1px; left: 13px; width: 1px; background: #d8e0e5; }
.event-marker { z-index: 1; display: grid; place-items: center; width: 28px; height: 28px; color: #677681; background: #eef2f4; border: 1px solid #d8e0e5; border-radius: 50%; }
.event-card { padding: 1px 0 2px; }
.event-card > div { display: flex; justify-content: space-between; gap: 12px; }
.event-card strong { font-size: 13px; }
.event-card time, .event-card > span { color: #8b97a1; font-size: 11px; }
.event-card p { margin: 5px 0; color: #586671; font-size: 12px; line-height: 1.5; }
.event-opened .event-marker, .event-refreshed .event-marker, .event-voice_failed .event-marker { color: var(--danger); background: #fff0f0; border-color: #f0cccc; }
.event-presented .event-marker, .event-voice_started .event-marker { color: #2b6f9e; background: #edf6fc; border-color: #cadfeb; }
.event-voice_completed .event-marker, .event-auto_recovered .event-marker { color: var(--success); background: #eaf7f4; border-color: #cae7df; }

@media (max-width: 900px) {
  .alert-log-page { height: auto; min-height: calc(100vh - 40px); }
  .ledger-shell { flex: none; height: 560px; }
  .page-heading, .ledger-footer { align-items: flex-start; flex-direction: column; }
  .heading-actions { width: 100%; justify-content: space-between; }
  .filter-panel :deep(.el-select), .id-filter { width: calc(50% - 5px); }
  .keyword-filter { min-width: 100%; }
  .delivery-summary { grid-template-columns: 1fr; }
  .delivery-summary > div { border-right: 0; border-bottom: 1px solid var(--line); }
  .delivery-summary > div:last-child { border-bottom: 0; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
</style>
