<template>
  <section class="dashboard-page" :class="{ 'is-loading': loading }">
    <header class="dashboard-header">
      <div class="dashboard-heading">
        <div class="dashboard-eyebrow">
          <span class="live-beacon" aria-hidden="true"></span>
          LIVE OPERATIONS · 运营态势
        </div>
        <h1>游戏交易控制台</h1>
      </div>

      <div class="header-vitals" aria-label="系统关键状态">
        <div class="vital-item">
          <span>今日接单</span>
          <strong>{{ todayOrders.length }}</strong>
        </div>
        <div class="vital-item">
          <span>交付率</span>
          <strong>{{ completionRate }}<small>%</small></strong>
        </div>
        <div class="vital-item">
          <span>在线机器</span>
          <strong>{{ onlineMachines }}<small>/{{ machines.length }}</small></strong>
        </div>
        <div class="vital-item vital-alert" :class="{ active: alertTotal > 0 }">
          <span>待处理</span>
          <strong>{{ alertTotal }}</strong>
        </div>
      </div>

      <div class="header-tools">
        <div class="system-clock">
          <strong>{{ clockTime }}</strong>
          <span>{{ clockDate }}</span>
        </div>
        <button class="icon-tool" type="button" :title="isFullscreen ? '退出全屏' : '进入全屏'" @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </button>
        <button class="refresh-tool" type="button" :disabled="loading" @click="loadDashboard">
          <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          <span>{{ loading ? '同步中' : '刷新' }}</span>
        </button>
      </div>
    </header>

    <section class="flow-rail" aria-label="实时交易链路">
      <div class="flow-rail__label">
        <span>实时交易链路</span>
        <strong>{{ activeOrders }} 笔流转中</strong>
      </div>
      <div class="flow-track">
        <div
          v-for="(step, index) in flowSteps"
          :key="step.key"
          class="flow-step"
          :class="{ active: step.count > 0, complete: step.key === 'completed' && step.count > 0 }"
        >
          <div class="flow-node">
            <span class="flow-node__pulse"></span>
            <strong>{{ step.count }}</strong>
          </div>
          <div class="flow-copy">
            <span>{{ step.label }}</span>
            <small>{{ step.hint }}</small>
          </div>
          <div v-if="index < flowSteps.length - 1" class="flow-connector">
            <span></span>
          </div>
        </div>
      </div>
      <div class="flow-health">
        <span>自动交易</span>
        <strong :class="systemControls.auto_game_trade_enabled ? 'is-ok' : 'is-paused'">
          {{ systemControls.auto_game_trade_enabled ? '已接通' : '已暂停' }}
        </strong>
        <small>{{ runningMonitors }} 个账号监控中</small>
      </div>
    </section>

    <main class="dashboard-grid">
      <article class="panel trend-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">近 7 日</span>
            <h2>订单吞吐趋势</h2>
          </div>
          <div class="panel-legend">
            <span><i class="legend-dot total"></i>接单</span>
            <span><i class="legend-dot complete"></i>完成</span>
          </div>
        </div>
        <div ref="trendChartRef" class="chart-canvas"></div>
      </article>

      <article class="panel status-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">当前订单</span>
            <h2>交付状态构成</h2>
          </div>
          <span class="panel-total">共 {{ orders.length }} 笔</span>
        </div>
        <div ref="statusChartRef" class="chart-canvas"></div>
      </article>

      <article class="panel platform-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">平台接入</span>
            <h2>账号与订单来源</h2>
          </div>
          <span class="panel-total">{{ accounts.length }} 个账号</span>
        </div>
        <div ref="platformChartRef" class="chart-canvas"></div>
      </article>

      <article class="panel inventory-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">库存覆盖</span>
            <h2>游戏库存水位</h2>
          </div>
          <span class="panel-total">{{ stockedInventoryCount }}/{{ inventories.length }} 有库存</span>
        </div>
        <div ref="inventoryChartRef" class="chart-canvas"></div>
      </article>

      <article class="panel activity-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">实时动态</span>
            <h2>最新订单</h2>
          </div>
          <button class="text-link" type="button" @click="router.push('/orders')">查看全部</button>
        </div>
        <div v-if="recentOrders.length" class="activity-list">
          <button
            v-for="order in recentOrders"
            :key="order.id"
            class="activity-row"
            type="button"
            @click="openOrder(order)"
          >
            <span class="platform-mark" :style="platformMarkStyle(order.website_id)"></span>
            <span class="activity-main">
              <strong>{{ order.product_title || order.trade_item_name || '未命名交易物品' }}</strong>
              <small>{{ platformName(order.website_id) }} · {{ shortOrderNo(order) }}</small>
            </span>
            <span class="activity-meta">
              <em :class="statusTone(order.status)">{{ statusLabel(order.status) }}</em>
              <small>{{ relativeTime(order.created_at) }}</small>
            </span>
          </button>
        </div>
        <div v-else class="empty-activity">
          <div class="empty-radar" aria-hidden="true"><span></span></div>
          <strong>等待首笔交易信号</strong>
          <span>订单接入后会在这里实时出现</span>
        </div>
      </article>
    </main>

    <div v-if="loadError" class="dashboard-error" role="alert">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ loadError }}</span>
      <button type="button" @click="loadDashboard">重新加载</button>
    </div>

    <footer class="dashboard-footer">
      <span><i class="footer-signal"></i>数据更新时间 {{ lastUpdatedLabel }}</span>
      <span>中控节点 · {{ healthyServices }}/{{ totalServices }} 项数据源在线</span>
    </footer>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getAllAccounts,
  getAllGames,
  getAllRegionInventories,
  getAllWebsites,
  getMachines,
  getOrderCheckStatus,
  getOrders,
  getSystemControls,
} from '../api'
import { useManualAlertStore } from '../stores/manualAlerts'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

const router = useRouter()
const manualAlerts = useManualAlertStore()

const orders = ref([])
const machines = ref([])
const accounts = ref([])
const websites = ref([])
const games = ref([])
const inventories = ref([])
const monitorStatus = ref({})
const systemControls = ref({ auto_game_trade_enabled: false })
const loading = ref(false)
const loadError = ref('')
const lastUpdatedAt = ref(null)
const clockNow = ref(new Date())
const isFullscreen = ref(Boolean(document.fullscreenElement))
const healthyServices = ref(0)
const totalServices = 8

const trendChartRef = ref(null)
const statusChartRef = ref(null)
const platformChartRef = ref(null)
const inventoryChartRef = ref(null)
const charts = new Map()
let clockTimer = null
let refreshTimer = null
let resizeObserver = null

const STATUS_COLORS = {
  pending: '#f4b860',
  assigned: '#46c7f4',
  processing: '#8b9fff',
  completed: '#59d6a1',
  cancelled: '#60788a',
  abnormal: '#ff6b6b',
}

const PLATFORM_COLORS = ['#46c7f4', '#f4b860', '#9f8cff', '#59d6a1', '#ff7d8c', '#5f91ff']

const todayOrders = computed(() => {
  const today = dateKey(new Date())
  return orders.value.filter(order => dateKey(new Date(order.created_at)) === today)
})

const onlineMachines = computed(() => machines.value.filter(machine => machine.status === 'online').length)
const alertTotal = computed(() => manualAlerts.total || 0)
const activeOrders = computed(() => orders.value.filter(order => !['completed', 'cancelled'].includes(order.status)).length)
const stockedInventoryCount = computed(() => inventories.value.filter(item => numberValue(item.stock) > 0).length)
const runningMonitors = computed(() => Object.values(monitorStatus.value || {}).filter(item => item?.status === 'running').length)
const completionRate = computed(() => {
  const effective = orders.value.filter(order => order.status !== 'cancelled')
  if (!effective.length) return 0
  return Math.round((effective.filter(order => order.status === 'completed').length / effective.length) * 100)
})

const clockTime = computed(() => clockNow.value.toLocaleTimeString('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
}))

const clockDate = computed(() => clockNow.value.toLocaleDateString('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  weekday: 'short',
}))

const lastUpdatedLabel = computed(() => {
  if (!lastUpdatedAt.value) return '等待同步'
  return lastUpdatedAt.value.toLocaleTimeString('zh-CN', { hour12: false })
})

const flowSteps = computed(() => {
  const byDelivery = (...statuses) => orders.value.filter(order => statuses.includes(order.delivery_status)).length
  const processing = orders.value.filter(order => (
    ['assigned', 'processing'].includes(order.status)
    || ['assigned', 'trading', 'game_delivered', 'wait_web_confirm'].includes(order.delivery_status)
  )).length
  return [
    { key: 'detected', label: '订单接入', hint: '平台采集', count: orders.value.length },
    { key: 'greeting', label: '客户招呼', hint: '建立联系', count: byDelivery('detected', 'greeting', 'greeted') },
    { key: 'assignment', label: '资源分配', hint: '机器与账号', count: byDelivery('waiting_assignment', 'queued', 'offered') },
    { key: 'trading', label: '游戏交易', hint: '自动交付', count: processing },
    { key: 'completed', label: '完成确认', hint: '平台回执', count: orders.value.filter(order => order.status === 'completed').length },
  ]
})

const recentOrders = computed(() => [...orders.value]
  .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
  .slice(0, 5))

function numberValue(value) {
  const result = Number(value)
  return Number.isFinite(result) ? result : 0
}

function compactNumber(value) {
  const amount = numberValue(value)
  if (Math.abs(amount) >= 100000000) return `${(amount / 100000000).toFixed(amount >= 1000000000 ? 0 : 1)}亿`
  if (Math.abs(amount) >= 10000) return `${(amount / 10000).toFixed(amount >= 100000 ? 0 : 1)}万`
  return String(Math.round(amount))
}

function dateKey(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function platformName(id) {
  return websites.value.find(item => Number(item.id) === Number(id))?.name || '未知平台'
}

function platformColor(id) {
  const index = Math.max(0, websites.value.findIndex(item => Number(item.id) === Number(id)))
  return PLATFORM_COLORS[index % PLATFORM_COLORS.length]
}

function platformMarkStyle(id) {
  const color = platformColor(id)
  return { background: color, boxShadow: `0 0 12px ${color}99` }
}

function shortOrderNo(order) {
  const value = String(order.source_order_no || order.order_no || order.id || '')
  return value.length > 13 ? `${value.slice(0, 7)}…${value.slice(-4)}` : value
}

function statusLabel(status) {
  return {
    pending: '待处理',
    assigned: '已分配',
    processing: '交易中',
    completed: '已完成',
    cancelled: '已取消',
    abnormal: '异常',
  }[status] || '处理中'
}

function statusTone(status) {
  return ['completed', 'cancelled', 'abnormal'].includes(status) ? `tone-${status}` : 'tone-active'
}

function relativeTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`
  return `${Math.floor(seconds / 86400)} 天前`
}

function openOrder(order) {
  router.push({ path: '/orders', query: { alert_order_id: order.id, alert_nonce: Date.now() } })
}

function chartBaseOption() {
  return {
    animationDuration: 700,
    textStyle: { fontFamily: 'Bahnschrift, "Microsoft YaHei", sans-serif', color: '#b6c9d6' },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(5, 25, 39, .96)',
      borderColor: '#28526a',
      borderWidth: 1,
      textStyle: { color: '#e8f4fa', fontSize: 12 },
      extraCssText: 'box-shadow: 0 12px 32px rgba(0,0,0,.28); border-radius: 6px;',
    },
  }
}

function trendOption() {
  const days = []
  for (let offset = 6; offset >= 0; offset -= 1) {
    const date = new Date()
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() - offset)
    days.push({
      key: dateKey(date),
      label: `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`,
    })
  }
  const total = days.map(day => orders.value.filter(order => dateKey(new Date(order.created_at)) === day.key).length)
  const completed = days.map(day => orders.value.filter(order => (
    order.status === 'completed' && dateKey(new Date(order.created_at)) === day.key
  )).length)
  return {
    ...chartBaseOption(),
    grid: { left: 8, right: 10, top: 22, bottom: 2, containLabel: true },
    xAxis: {
      type: 'category',
      data: days.map(day => day.label),
      axisLine: { lineStyle: { color: '#214458' } },
      axisTick: { show: false },
      axisLabel: { color: '#7390a2', fontSize: 11, margin: 12 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#678497', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(87, 132, 156, .15)', type: 'dashed' } },
    },
    series: [
      {
        name: '接单',
        type: 'bar',
        data: total,
        barWidth: 13,
        itemStyle: { color: '#1e759a', borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '完成',
        type: 'line',
        data: completed,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5, color: '#59d6a1' },
        itemStyle: { color: '#b8ffe2', borderColor: '#59d6a1', borderWidth: 2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(89, 214, 161, .24)' },
              { offset: 1, color: 'rgba(89, 214, 161, 0)' },
            ],
          },
        },
      },
    ],
  }
}

function statusOption() {
  const data = Object.keys(STATUS_COLORS).map(status => ({
    name: statusLabel(status),
    value: orders.value.filter(order => order.status === status).length,
    itemStyle: { color: STATUS_COLORS[status] },
  })).filter(item => item.value > 0)
  const safeData = data.length ? data : [{ name: '暂无订单', value: 1, itemStyle: { color: '#1a394b' } }]
  return {
    ...chartBaseOption(),
    tooltip: { ...chartBaseOption().tooltip, trigger: 'item' },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 4,
      top: 'middle',
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 12,
      textStyle: { color: '#8fa9b8', fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['54%', '76%'],
      center: ['37%', '52%'],
      minAngle: 8,
      label: { show: false },
      itemStyle: { borderColor: '#0b2536', borderWidth: 3, borderRadius: 4 },
      data: safeData,
    }],
  }
}

function platformOption() {
  const rows = websites.value.map((website, index) => ({
    id: website.id,
    name: website.name,
    accounts: accounts.value.filter(account => Number(account.website_id) === Number(website.id)).length,
    orders: orders.value.filter(order => Number(order.website_id) === Number(website.id)).length,
    color: PLATFORM_COLORS[index % PLATFORM_COLORS.length],
  })).sort((a, b) => (b.accounts + b.orders) - (a.accounts + a.orders)).slice(0, 5)
  return {
    ...chartBaseOption(),
    grid: { left: 10, right: 12, top: 6, bottom: 0, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#678497', fontSize: 10, formatter: compactNumber },
      splitLine: { lineStyle: { color: 'rgba(87, 132, 156, .13)', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map(row => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#b6c9d6', width: 76, overflow: 'truncate', fontSize: 11 },
    },
    series: [
      {
        name: '账号',
        type: 'bar',
        stack: 'platform',
        barWidth: 10,
        data: rows.map(row => ({ value: row.accounts, itemStyle: { color: row.color, borderRadius: [3, 0, 0, 3] } })),
      },
      {
        name: '订单',
        type: 'bar',
        stack: 'platform',
        barWidth: 10,
        data: rows.map(row => ({ value: row.orders, itemStyle: { color: `${row.color}66`, borderRadius: [0, 3, 3, 0] } })),
      },
    ],
  }
}

function inventoryOption() {
  const gameMap = new Map(games.value.map(game => [Number(game.id), game.name]))
  const grouped = new Map()
  inventories.value.forEach(item => {
    const gameId = Number(item.game_id)
    const entry = grouped.get(gameId) || { name: gameMap.get(gameId) || `游戏 ${gameId}`, stock: 0, records: 0 }
    entry.stock += numberValue(item.stock)
    entry.records += 1
    grouped.set(gameId, entry)
  })
  const rows = [...grouped.values()].sort((a, b) => b.stock - a.stock).slice(0, 5)
  const displayValues = rows.map(row => row.stock > 0 ? row.stock : row.records)
  return {
    ...chartBaseOption(),
    grid: { left: 10, right: 12, top: 6, bottom: 0, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#678497', fontSize: 10, formatter: compactNumber },
      splitLine: { lineStyle: { color: 'rgba(87, 132, 156, .13)', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map(row => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#b6c9d6', width: 82, overflow: 'truncate', fontSize: 11 },
    },
    series: [{
      name: rows.some(row => row.stock > 0) ? '库存' : '库存记录',
      type: 'bar',
      barWidth: 10,
      showBackground: true,
      backgroundStyle: { color: 'rgba(84, 125, 147, .11)', borderRadius: 4 },
      data: displayValues.map((value, index) => ({
        value,
        itemStyle: {
          color: index === 0 ? '#59d6a1' : '#2f8fa8',
          borderRadius: 4,
        },
      })),
    }],
  }
}

function ensureChart(elementRef, key) {
  if (!elementRef.value) return null
  let chart = charts.get(key)
  if (!chart || chart.isDisposed()) {
    chart = echarts.init(elementRef.value, null, { renderer: 'canvas' })
    charts.set(key, chart)
  }
  return chart
}

function renderCharts() {
  ensureChart(trendChartRef, 'trend')?.setOption(trendOption(), true)
  ensureChart(statusChartRef, 'status')?.setOption(statusOption(), true)
  ensureChart(platformChartRef, 'platform')?.setOption(platformOption(), true)
  ensureChart(inventoryChartRef, 'inventory')?.setOption(inventoryOption(), true)
}

async function loadDashboard() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  const requests = [
    getOrders({ page: 1, page_size: 1000 }),
    getMachines({ page: 1, page_size: 1000 }),
    getAllAccounts(),
    getAllWebsites(),
    getAllGames(),
    getAllRegionInventories(),
    getOrderCheckStatus(),
    getSystemControls(),
  ]
  try {
    const results = await Promise.allSettled(requests)
    healthyServices.value = results.filter(result => result.status === 'fulfilled').length
    const values = results.map(result => result.status === 'fulfilled' ? result.value : null)
    orders.value = Array.isArray(values[0]?.items) ? values[0].items : []
    machines.value = Array.isArray(values[1]?.items) ? values[1].items : []
    accounts.value = Array.isArray(values[2]) ? values[2] : []
    websites.value = Array.isArray(values[3]) ? values[3] : []
    games.value = Array.isArray(values[4]) ? values[4] : []
    inventories.value = Array.isArray(values[5]) ? values[5] : []
    monitorStatus.value = values[6] && typeof values[6] === 'object' ? values[6] : {}
    systemControls.value = values[7] || { auto_game_trade_enabled: false }
    if (healthyServices.value < totalServices) {
      loadError.value = `${totalServices - healthyServices.value} 项数据暂未同步，页面已保留其余实时数据`
    }
    lastUpdatedAt.value = new Date()
    await nextTick()
    renderCharts()
  } catch (error) {
    loadError.value = error.message || '大屏数据加载失败'
  } finally {
    loading.value = false
  }
}

async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch (_error) {
    loadError.value = '浏览器未允许进入全屏，请检查页面权限'
  }
}

function handleFullscreenChange() {
  isFullscreen.value = Boolean(document.fullscreenElement)
  nextTick(() => charts.forEach(chart => chart.resize()))
}

onMounted(() => {
  clockTimer = window.setInterval(() => { clockNow.value = new Date() }, 1000)
  refreshTimer = window.setInterval(loadDashboard, 30000)
  resizeObserver = new ResizeObserver(() => charts.forEach(chart => chart.resize()))
  ;[trendChartRef, statusChartRef, platformChartRef, inventoryChartRef].forEach(item => {
    if (item.value) resizeObserver.observe(item.value)
  })
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  loadDashboard()
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  window.clearInterval(refreshTimer)
  resizeObserver?.disconnect()
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  charts.forEach(chart => chart.dispose())
  charts.clear()
})
</script>

<style scoped>
.dashboard-page {
  --dash-bg: #071b2b;
  --dash-panel: rgba(11, 37, 54, .88);
  --dash-line: rgba(111, 169, 198, .19);
  --dash-text: #e8f4fa;
  --dash-muted: #7895a6;
  position: relative;
  display: grid;
  grid-template-rows: 64px 116px minmax(0, 1fr) 20px;
  gap: 10px;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  padding: 12px 14px 8px;
  overflow: hidden;
  border: 1px solid rgba(80, 145, 177, .22);
  border-radius: 12px;
  color: var(--dash-text);
  background:
    radial-gradient(circle at 64% -20%, rgba(43, 128, 159, .24), transparent 38%),
    linear-gradient(rgba(54, 102, 127, .055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(54, 102, 127, .055) 1px, transparent 1px),
    var(--dash-bg);
  background-size: auto, 32px 32px, 32px 32px, auto;
  box-shadow: 0 18px 50px rgba(5, 24, 36, .15);
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

.dashboard-page::before {
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, #46c7f4 35%, #59d6a1 62%, transparent);
  content: '';
  opacity: .75;
}

.dashboard-header {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 22px;
  padding: 0 4px 0 2px;
  border-bottom: 1px solid var(--dash-line);
}

.dashboard-heading { min-width: 232px; }
.dashboard-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6ea9c5;
  font: 600 10px/1 Bahnschrift, "Segoe UI", sans-serif;
  letter-spacing: .16em;
}
.dashboard-heading h1 {
  margin: 5px 0 0;
  color: #f4fbff;
  font: 600 23px/1.1 Bahnschrift, "PingFang SC", sans-serif;
  letter-spacing: .02em;
}
.live-beacon,
.footer-signal {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #59d6a1;
  box-shadow: 0 0 0 4px rgba(89, 214, 161, .12), 0 0 12px #59d6a1;
}

.header-vitals {
  display: grid;
  min-width: 0;
  max-width: 610px;
  flex: 1;
  grid-template-columns: repeat(4, minmax(86px, 1fr));
}
.vital-item {
  display: flex;
  min-width: 0;
  height: 42px;
  flex-direction: column;
  justify-content: center;
  padding: 0 18px;
  border-left: 1px solid var(--dash-line);
}
.vital-item span { color: var(--dash-muted); font-size: 10px; }
.vital-item strong {
  margin-top: 3px;
  color: #effaff;
  font: 600 20px/1 Bahnschrift, "Microsoft YaHei", sans-serif;
}
.vital-item small { margin-left: 2px; color: #7895a6; font-size: 10px; }
.vital-alert.active strong { color: #ff7d7d; text-shadow: 0 0 18px rgba(255, 107, 107, .3); }

.header-tools { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.system-clock { display: flex; min-width: 100px; flex-direction: column; align-items: flex-end; margin-right: 6px; }
.system-clock strong { font: 600 18px/1 Bahnschrift, monospace; letter-spacing: .05em; }
.system-clock span { margin-top: 5px; color: var(--dash-muted); font-size: 10px; }
.icon-tool,
.refresh-tool,
.text-link {
  border: 0;
  color: #98b7c7;
  background: transparent;
  cursor: pointer;
}
.icon-tool,
.refresh-tool {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--dash-line);
  border-radius: 6px;
  background: rgba(18, 58, 78, .55);
}
.icon-tool { width: 34px; }
.refresh-tool { gap: 5px; padding: 0 11px; font-size: 12px; }
.icon-tool:hover,
.refresh-tool:hover { border-color: #3a829f; color: #dff7ff; background: rgba(31, 92, 116, .62); }
.refresh-tool:disabled { cursor: wait; opacity: .68; }
.icon-tool:focus-visible,
.refresh-tool:focus-visible,
.text-link:focus-visible,
.activity-row:focus-visible { outline: 2px solid #46c7f4; outline-offset: 2px; }
.spinning { animation: spin .8s linear infinite; }

.flow-rail {
  display: grid;
  min-width: 0;
  grid-template-columns: 140px minmax(0, 1fr) 130px;
  align-items: stretch;
  border: 1px solid rgba(74, 139, 169, .27);
  border-radius: 8px;
  background: linear-gradient(100deg, rgba(13, 47, 65, .96), rgba(9, 32, 47, .82));
  box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
  overflow: hidden;
}
.flow-rail__label {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 18px;
  border-right: 1px solid var(--dash-line);
}
.flow-rail__label span { color: #7596a8; font-size: 11px; }
.flow-rail__label strong { margin-top: 8px; color: #46c7f4; font-size: 14px; font-weight: 600; }
.flow-track { display: grid; min-width: 0; grid-template-columns: repeat(5, minmax(92px, 1fr)); align-items: center; padding: 0 12px; }
.flow-step { position: relative; display: flex; min-width: 0; align-items: center; gap: 10px; }
.flow-node {
  position: relative;
  z-index: 2;
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #2f657e;
  border-radius: 50%;
  color: #8daaba;
  background: #0a2638;
  font: 600 15px/1 Bahnschrift, sans-serif;
  box-shadow: 0 0 0 5px rgba(34, 83, 106, .16);
}
.flow-node__pulse { position: absolute; inset: -5px; border: 1px solid transparent; border-radius: 50%; }
.flow-step.active .flow-node { border-color: #46c7f4; color: #effbff; box-shadow: 0 0 0 5px rgba(70, 199, 244, .09), 0 0 18px rgba(70, 199, 244, .18); }
.flow-step.active .flow-node__pulse { border-color: rgba(70, 199, 244, .34); animation: node-pulse 2s ease-out infinite; }
.flow-step.complete .flow-node { border-color: #59d6a1; box-shadow: 0 0 0 5px rgba(89, 214, 161, .09), 0 0 18px rgba(89, 214, 161, .2); }
.flow-copy { display: flex; min-width: 0; flex-direction: column; }
.flow-copy span { color: #c5d7e1; font-size: 12px; font-weight: 600; white-space: nowrap; }
.flow-copy small { margin-top: 5px; color: #647f8f; font-size: 9px; white-space: nowrap; }
.flow-connector { position: absolute; z-index: 1; top: 20px; left: 42px; width: calc(100% - 36px); height: 1px; background: #244b60; }
.flow-connector span { display: block; width: 30%; height: 1px; background: linear-gradient(90deg, transparent, #46c7f4, transparent); animation: rail-scan 2.5s linear infinite; }
.flow-health { display: flex; flex-direction: column; justify-content: center; padding: 0 16px; border-left: 1px solid var(--dash-line); }
.flow-health span { color: #7596a8; font-size: 10px; }
.flow-health strong { margin: 5px 0; font-size: 14px; }
.flow-health .is-ok { color: #59d6a1; }
.flow-health .is-paused { color: #f4b860; }
.flow-health small { color: #647f8f; font-size: 9px; }

.dashboard-grid {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-columns: minmax(0, 1.22fr) minmax(0, .92fr) minmax(270px, .92fr);
  grid-template-rows: minmax(0, 1.08fr) minmax(0, .92fr);
  gap: 10px;
}
.panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 13px 14px 10px;
  border: 1px solid var(--dash-line);
  border-radius: 8px;
  background: var(--dash-panel);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.02);
  overflow: hidden;
}
.trend-panel { grid-column: 1 / 3; }
.panel-heading { display: flex; flex: 0 0 auto; align-items: flex-start; justify-content: space-between; gap: 12px; }
.panel-kicker { display: block; margin-bottom: 3px; color: #56829a; font-size: 9px; letter-spacing: .14em; }
.panel h2 { margin: 0; color: #dcebf2; font-size: 13px; font-weight: 600; }
.panel-total { color: #7596a8; font: 11px/1.4 Bahnschrift, "Microsoft YaHei", sans-serif; }
.panel-legend { display: flex; gap: 12px; color: #7895a6; font-size: 10px; }
.panel-legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend-dot { width: 7px; height: 7px; border-radius: 2px; }
.legend-dot.total { background: #1e759a; }
.legend-dot.complete { border-radius: 50%; background: #59d6a1; box-shadow: 0 0 7px rgba(89,214,161,.45); }
.chart-canvas { width: 100%; min-height: 0; flex: 1; }
.text-link { padding: 2px 0; color: #46c7f4; font-size: 10px; }
.text-link:hover { color: #a9eaff; }

.activity-list { display: flex; min-height: 0; flex: 1; flex-direction: column; justify-content: space-evenly; margin-top: 5px; }
.activity-row {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: 5px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 7px 4px;
  border: 0;
  border-bottom: 1px solid rgba(93, 143, 166, .12);
  color: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
}
.activity-row:hover { background: rgba(54, 116, 143, .09); }
.activity-row:last-child { border-bottom: 0; }
.platform-mark { width: 3px; height: 24px; border-radius: 2px; }
.activity-main,
.activity-meta { display: flex; min-width: 0; flex-direction: column; }
.activity-main strong { overflow: hidden; color: #cbdde6; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.activity-main small,
.activity-meta small { margin-top: 4px; color: #607f90; font-size: 9px; }
.activity-meta { align-items: flex-end; }
.activity-meta em { font-size: 10px; font-style: normal; }
.tone-active { color: #46c7f4; }
.tone-completed { color: #59d6a1; }
.tone-cancelled { color: #7895a6; }
.tone-abnormal { color: #ff6b6b; }
.empty-activity { display: flex; min-height: 0; flex: 1; flex-direction: column; align-items: center; justify-content: center; color: #607f90; }
.empty-activity strong { margin-top: 9px; color: #9db6c3; font-size: 12px; font-weight: 500; }
.empty-activity > span { margin-top: 5px; font-size: 9px; }
.empty-radar { position: relative; width: 44px; height: 44px; border: 1px solid #28546a; border-radius: 50%; }
.empty-radar::before,
.empty-radar::after { position: absolute; background: #28546a; content: ''; }
.empty-radar::before { top: 50%; left: 5px; width: 32px; height: 1px; }
.empty-radar::after { top: 5px; left: 50%; width: 1px; height: 32px; }
.empty-radar span { position: absolute; inset: 5px; border-radius: 50%; background: conic-gradient(from 30deg, rgba(70,199,244,.28), transparent 28%); animation: spin 2.8s linear infinite; }

.dashboard-error {
  position: absolute;
  z-index: 5;
  right: 18px;
  bottom: 32px;
  display: flex;
  max-width: 420px;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border: 1px solid rgba(244, 184, 96, .38);
  border-radius: 6px;
  color: #f5c77f;
  background: rgba(44, 37, 26, .96);
  box-shadow: 0 12px 28px rgba(0,0,0,.24);
  font-size: 11px;
}
.dashboard-error button { margin-left: auto; border: 0; color: #ffe0a6; background: transparent; cursor: pointer; }
.dashboard-footer { display: flex; align-items: center; justify-content: space-between; color: #4f7183; font: 9px/1 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .03em; }
.dashboard-footer span:first-child { display: inline-flex; align-items: center; gap: 7px; }
.footer-signal { width: 5px; height: 5px; box-shadow: 0 0 8px #59d6a1; }

.is-loading .panel { opacity: .78; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes node-pulse { 0% { transform: scale(.88); opacity: .8; } 75%, 100% { transform: scale(1.28); opacity: 0; } }
@keyframes rail-scan { from { transform: translateX(-100%); } to { transform: translateX(340%); } }

@media (max-width: 1420px) {
  .dashboard-heading { min-width: 200px; }
  .dashboard-heading h1 { font-size: 20px; }
  .vital-item { padding: 0 12px; }
  .system-clock { display: none; }
  .flow-rail { grid-template-columns: 120px minmax(0, 1fr) 112px; }
  .flow-copy small { display: none; }
  .dashboard-grid { grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr) minmax(245px, .9fr); }
}

@media (max-width: 1180px), (max-height: 690px) {
  .dashboard-page { min-width: 940px; min-height: 650px; overflow: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .flow-step.active .flow-node__pulse,
  .flow-connector span,
  .empty-radar span,
  .spinning { animation: none; }
}
</style>
