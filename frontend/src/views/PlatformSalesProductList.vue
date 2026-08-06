<template>
  <div class="sales-products-page">
    <header class="page-heading">
      <div>
        <div class="heading-kicker">LIVE LISTING LEDGER</div>
        <h1>平台在售商品</h1>
        <p>仅核对平台“上架中”的商品；范围库存按最高值比对，可将平台抓取值同步到系统库存。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="fetchList">
        <el-icon><Refresh /></el-icon>
        刷新列表
      </el-button>
    </header>

    <section class="sync-ledger" aria-label="当前查询概况">
      <div class="ledger-cell ledger-total">
        <span>符合条件</span>
        <strong>{{ total }}</strong>
        <small>条平台在售记录</small>
      </div>
      <div class="ledger-cell">
        <span>当前页已匹配</span>
        <strong class="matched-number">{{ currentMatched }}</strong>
        <small>游戏、大区和物品均已关联</small>
      </div>
      <div class="ledger-cell">
        <span>当前页待处理</span>
        <strong class="warning-number">{{ currentUnmatched }}</strong>
        <small>保留原始数据，等待配置或标题修正</small>
      </div>
      <div class="ledger-cell ledger-time">
        <span>当前页最近同步</span>
        <strong>{{ latestSyncTime }}</strong>
        <small>由平台监控任务自动维护</small>
      </div>
    </section>

    <section class="filter-panel" aria-label="在售商品筛选">
      <el-select
        v-model="filterWebsiteId"
        placeholder="全部平台"
        clearable
        class="filter-control"
        @change="handleWebsiteChange"
      >
        <el-option
          v-for="website in websites"
          :key="website.id"
          :label="website.name"
          :value="website.id"
        />
      </el-select>
      <el-select
        v-model="filterAccountId"
        placeholder="全部平台账号"
        clearable
        filterable
        class="filter-control filter-account"
        @change="handleSearch"
      >
        <el-option
          v-for="account in filteredAccounts"
          :key="account.id"
          :label="accountOptionLabel(account)"
          :value="account.id"
        />
      </el-select>
      <el-select
        v-model="filterGameId"
        placeholder="全部游戏"
        clearable
        filterable
        class="filter-control"
        @change="handleSearch"
      >
        <el-option
          v-for="game in games"
          :key="game.id"
          :label="game.name"
          :value="game.id"
        />
      </el-select>
      <el-select
        v-model="filterParseStatus"
        placeholder="全部解析状态"
        clearable
        class="filter-control"
        @change="handleSearch"
      >
        <el-option label="已匹配" value="matched" />
        <el-option label="标题解析失败" value="title_parse_failed" />
        <el-option label="游戏未匹配" value="game_unmatched" />
        <el-option label="大区未匹配" value="region_unmatched" />
        <el-option label="物品未匹配" value="item_unmatched" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="商品 ID、标题、游戏、大区或物品"
        clearable
        class="keyword-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button @click="handleSearch">查询</el-button>
    </section>

    <div class="table-shell">
      <el-table
        :data="list"
        border
        stripe
        row-key="id"
        v-loading="loading"
        height="100%"
        class="sales-table"
        :row-class-name="salesRowClassName"
      >
        <el-table-column label="来源" width="125" fixed="left">
          <template #default="{ row }">
            <div class="source-cell">
              <span class="platform-chip" :data-platform="row.platform">
                {{ platformName(row) }}
              </span>
              <span :title="accountName(row.platform_account_id)">
                {{ accountName(row.platform_account_id) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="平台商品" min-width="230">
          <template #default="{ row }">
            <div class="listing-cell">
              <strong :title="row.title || ''">{{ row.title || '未提供平台标题' }}</strong>
              <code :title="row.platform_product_id">{{ row.platform_product_id }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="匹配范围" min-width="160">
          <template #default="{ row }">
            <div class="location-cell">
              <strong :title="row.game_name || ''">{{ row.game_name || '-' }}</strong>
              <span :title="row.region_name || ''">{{ row.region_name || '-' }}</span>
              <span :title="row.parsed_item_name || ''" :class="['actual-item', { 'is-unmatched': !row.parsed_item_name }]">{{ row.parsed_item_name || '物品未解析' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="平台数据" width="135" align="right">
          <template #default="{ row }">
            <div class="platform-data-cell">
              <strong :title="row.quantity_text || ''">{{ row.quantity_text || '-' }}</strong>
              <small v-if="row.parsed_quantity !== null && row.parsed_quantity !== undefined">
                数量 {{ formatStock(row.parsed_quantity) }}
              </small>
              <span :title="row.price_text || ''">{{ row.price_text || '价格未记录' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="系统库存" width="125" align="center">
          <template #default="{ row }">
            <div class="inventory-cell">
              <strong v-if="row.inventory_stock !== null && row.inventory_stock !== undefined">
                {{ formatStock(row.inventory_stock) }}
              </strong>
              <span v-else>-</span>
              <el-tag
                v-if="row.parse_status === 'matched'"
                :type="inventoryStatusType(row.inventory_comparison_status)"
                size="small"
                effect="plain"
              >
                {{ inventoryStatusLabel(row.inventory_comparison_status) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态 / 时间" width="130">
          <template #default="{ row }">
            <div class="parse-state-cell">
              <el-tooltip :content="row.parse_error || '游戏、大区和实际商品均已匹配'" placement="top">
                <span :class="['parse-state', `is-${parseVisualTone(row.parse_status)}`]">{{ parseStatusLabel(row.parse_status) }}</span>
              </el-tooltip>
              <small :title="row.platform_registered_at || ''">登记 {{ compactTime(row.platform_registered_at) }}</small>
              <small :title="row.updated_at || ''">同步 {{ compactTime(row.updated_at) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="104" align="center" fixed="right">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.parse_status === 'matched'"
              :content="syncButtonHint(row)"
              placement="left"
            >
              <span>
                <el-button
                  type="warning"
                  plain
                  size="small"
                  :loading="syncingId === row.id"
                  :disabled="row.inventory_comparison_status !== 'mismatch'"
                  @click="handleSyncInventory(row)"
                >
                  同步库存
                </el-button>
              </span>
            </el-tooltip>
            <span v-else class="muted-value">待解析</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="table-footer">
      <span>下架或隐藏商品会在下一次成功的完整快照中移除；“同步库存”会以平台抓取值覆盖系统库存。</span>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="handlePageSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAllAccounts,
  getAllGames,
  getAllWebsites,
  getPlatformSalesProducts,
  syncPlatformSalesProductInventory,
} from '../api'

const websites = ref([])
const accounts = ref([])
const games = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const syncingId = ref(null)

const filterWebsiteId = ref(null)
const filterAccountId = ref(null)
const filterGameId = ref(null)
const filterParseStatus = ref('')
const keyword = ref('')

const websiteMap = computed(() =>
  Object.fromEntries(websites.value.map(item => [item.id, item.name])))
const accountMap = computed(() =>
  Object.fromEntries(accounts.value.map(item => [item.id, item])))
const filteredAccounts = computed(() => {
  if (!filterWebsiteId.value) return accounts.value
  return accounts.value.filter(
    account => account.website_id === filterWebsiteId.value)
})
const currentMatched = computed(() =>
  list.value.filter(item => item.parse_status === 'matched').length)
const currentUnmatched = computed(() =>
  list.value.length - currentMatched.value)
const latestSyncTime = computed(() => {
  const values = list.value
    .map(item => item.updated_at)
    .filter(Boolean)
    .sort()
  return values.length ? formatTime(values.at(-1)) : '-'
})

function platformName(row) {
  return websiteMap.value[row.website_id]
    || {
      itemmania: 'ItemMania',
      itembay: 'ItemBay',
      barotem: 'Barotem',
    }[row.platform]
    || row.platform
    || '-'
}

function accountName(accountId) {
  const account = accountMap.value[accountId]
  return account?.label || account?.username || `账号 #${accountId}`
}

function accountOptionLabel(account) {
  const platform = websiteMap.value[account.website_id] || '未知平台'
  const name = account.label || account.username || `账号 #${account.id}`
  return `${platform} · ${name}`
}

function parseStatusLabel(status) {
  return {
    matched: '已匹配',
    title_parse_failed: '标题解析失败',
    game_unmatched: '游戏未匹配',
    region_unmatched: '大区未匹配',
    item_unmatched: '物品未匹配',
  }[status] || status || '未知'
}

function parseStatusType(status) {
  return {
    matched: 'success',
    title_parse_failed: 'danger',
    game_unmatched: 'warning',
    region_unmatched: 'warning',
    item_unmatched: 'warning',
  }[status] || 'info'
}

function parseVisualTone(status) {
  if (status === 'matched') return 'success'
  if (status === 'title_parse_failed') return 'danger'
  return 'warning'
}

function salesRowClassName({ row }) {
  if (row.inventory_comparison_status === 'mismatch' || row.parse_status === 'title_parse_failed') return 'sales-row--danger'
  if (row.parse_status === 'matched') return 'sales-row--success'
  return 'sales-row--warning'
}

function inventoryStatusLabel(status) {
  return {
    matched: '一致',
    mismatch: '不一致',
    quantity_unavailable: '数量未解析',
    inventory_missing: '库存未配置',
    not_matched: '待解析',
  }[status] || '未核对'
}

function inventoryStatusType(status) {
  return {
    matched: 'success',
    mismatch: 'danger',
    quantity_unavailable: 'info',
    inventory_missing: 'warning',
  }[status] || 'info'
}

function formatStock(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value ?? '-')
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: 0,
  }).format(numeric)
}

function syncButtonHint(row) {
  return {
    matched: '平台库存与系统库存一致，无需同步',
    mismatch: '以平台抓取库存覆盖系统库存',
    quantity_unavailable: '平台数量无法解析，不能同步',
    inventory_missing: '未配置对应的大区物品库存，不能同步',
  }[row.inventory_comparison_status] || '当前商品不能同步库存'
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function compactTime(value) {
  if (!value) return '-'
  const normalized = String(value).replace('T', ' ')
  return normalized.length >= 16 ? normalized.slice(5, 16) : normalized
}

async function loadReferences() {
  const [websiteData, accountData, gameData] = await Promise.all([
    getAllWebsites(),
    getAllAccounts(),
    getAllGames(),
  ])
  websites.value = websiteData
  accounts.value = accountData
  games.value = gameData
}

async function fetchList() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterWebsiteId.value) params.website_id = filterWebsiteId.value
    if (filterAccountId.value) {
      params.platform_account_id = filterAccountId.value
    }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterParseStatus.value) {
      params.parse_status = filterParseStatus.value
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const response = await getPlatformSalesProducts(params)
    list.value = response.items || []
    total.value = Number(response.total || 0)
  } catch (error) {
    list.value = []
    total.value = 0
    ElMessage.error(`加载在售商品失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchList()
}

function handleWebsiteChange() {
  const selectedAccount = accountMap.value[filterAccountId.value]
  if (
    selectedAccount
    && filterWebsiteId.value
    && selectedAccount.website_id !== filterWebsiteId.value
  ) {
    filterAccountId.value = null
  }
  handleSearch()
}

function handlePageSizeChange() {
  page.value = 1
  fetchList()
}

async function handleSyncInventory(row) {
  if (row.inventory_comparison_status !== 'mismatch') return
  const platformStock = formatStock(row.parsed_quantity)
  const systemStock = formatStock(row.inventory_stock)
  try {
    await ElMessageBox.confirm(
      `确认以平台抓取库存 ${platformStock} 覆盖当前系统库存 ${systemStock}？若平台数量是范围，已取最高值。`,
      '同步系统库存',
      {
        type: 'warning',
        confirmButtonText: '确认同步',
        cancelButtonText: '取消',
      },
    )
  } catch (_error) {
    return
  }

  syncingId.value = row.id
  try {
    await syncPlatformSalesProductInventory(row.id)
    ElMessage.success(`库存已同步为 ${platformStock}`)
    await fetchList()
  } catch (error) {
    ElMessage.error(`同步库存失败：${error.message}`)
  } finally {
    syncingId.value = null
  }
}

onMounted(async () => {
  try {
    await loadReferences()
  } catch (error) {
    ElMessage.warning(`筛选项加载失败：${error.message}`)
  }
  await fetchList()
})
</script>

<style scoped>
.sales-products-page {
  --ledger-navy: #0b2748;
  --ledger-blue: #2468a9;
  --ledger-green: #2f855a;
  --ledger-amber: #b7791f;
  --ledger-ink: #182230;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 2px;
}

.heading-kicker {
  margin-bottom: 2px;
  color: var(--ledger-blue);
  font: 700 10px/1.2 "SFMono-Regular", Consolas, monospace;
  letter-spacing: .16em;
}

.page-heading h1 {
  margin: 0;
  color: var(--ledger-ink);
  font-size: 22px;
  line-height: 1.25;
  letter-spacing: -.02em;
}

.page-heading p {
  margin: 3px 0 0;
  color: #606b78;
  font-size: 12px;
  line-height: 1.45;
}

.sync-ledger {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1.35fr;
  overflow: hidden;
  border: 1px solid #d7e0ea;
  border-left: 5px solid var(--ledger-blue);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(21, 48, 76, .06);
}

.ledger-cell {
  min-width: 0;
  padding: 7px 14px;
  border-right: 1px solid #e6ebf1;
}

.ledger-cell:last-child { border-right: 0; }
.ledger-cell span, .ledger-cell small { display: block; }
.ledger-cell span { color: #7a8592; font-size: 10px; }
.ledger-cell strong {
  display: inline-block;
  margin: 2px 0;
  color: var(--ledger-navy);
  font-size: 19px;
  line-height: 1;
}
.ledger-cell small {
  overflow: hidden;
  color: #98a1ac;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ledger-cell .matched-number { color: var(--ledger-green); }
.ledger-cell .warning-number { color: var(--ledger-amber); }
.ledger-time strong { font: 700 13px/1.35 "SFMono-Regular", Consolas, monospace; }

.filter-panel {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid #e0e5eb;
  border-radius: 8px;
  background: #fff;
}

.filter-control { width: 122px; }
.filter-account { width: 168px; }
.keyword-input { min-width: 190px; flex: 1; }

.table-shell {
  min-height: 0;
  flex: 1;
  overflow: hidden;
  border: 1px solid #dfe4ea;
  border-radius: 8px;
  background: #fff;
}

.sales-table { width: 100%; }
.sales-table :deep(.el-table__header th.el-table__cell) { height: 40px; color: #596879; background: #f5f8fb; font-size: 12px; }
.sales-table :deep(.cell) { line-height: 1.35; }
.sales-table :deep(.el-table__body td.el-table__cell) { padding: 5px 0; }
.sales-table :deep(.sales-row--danger > td:first-child) { box-shadow: inset 3px 0 0 #d84a4a; }
.sales-table :deep(.sales-row--warning > td:first-child) { box-shadow: inset 3px 0 0 #d69a2d; }
.sales-table :deep(.sales-row--success > td:first-child) { box-shadow: inset 3px 0 0 #2b9669; }
.source-cell, .location-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.source-cell > span:last-child,
.location-cell span {
  overflow: hidden;
  color: #697481;
  font-size: 11px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.location-cell strong {
  overflow: hidden;
  color: #263241;
  font-size: 12px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-chip {
  width: fit-content;
  padding: 2px 7px;
  border-radius: 3px;
  background: #eaf2fb;
  color: #245f99;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.35;
}
.platform-chip[data-platform="itemmania"] { background: #fff1e6; color: #a84f12; }
.platform-chip[data-platform="itembay"] { background: #edf2ff; color: #3f51a2; }
.platform-chip[data-platform="barotem"] { background: #e8f7f0; color: #217657; }

.muted-value { color: #a4acb5; }
.listing-cell,
.platform-data-cell,
.parse-state-cell,
.inventory-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.listing-cell strong { display: -webkit-box; overflow: hidden; color: #26364a; font-size: 12px; line-height: 1.35; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.listing-cell code { overflow: hidden; color: #54708d; font: 600 10px/1.3 "SFMono-Regular", Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.actual-item { color: #28765a !important; font-weight: 600; }
.actual-item.is-unmatched { color: #b66c18 !important; font-weight: 600; }
.platform-data-cell { align-items: flex-end; }
.platform-data-cell strong { max-width: 100%; overflow: hidden; color: #26364a; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.platform-data-cell small { color: #7d8792; font-size: 9px; }
.platform-data-cell span { max-width: 100%; overflow: hidden; color: #8b4b13; font-size: 10px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.inventory-cell { align-items: center; }
.inventory-cell strong {
  color: var(--ledger-navy);
  font: 650 12px/1.4 "SFMono-Regular", Consolas, monospace;
}
.parse-state-cell { align-items: flex-start; }
.parse-state {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 3px 7px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.parse-state.is-success { color: #247a56; border-color: #bfe0cf; background: #edf8f2; }
.parse-state.is-warning { color: #a86d12; border-color: #ecd4a5; background: #fff8e8; }
.parse-state.is-danger { color: #b93838; border-color: #efc3c3; background: #fff1f0; }
.parse-state-cell small { color: #8c98a5; font-size: 9px; line-height: 1.2; white-space: nowrap; }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  gap: 14px;
  color: #7d8792;
  font-size: 11px;
}

@media (max-width: 1100px) {
  .sync-ledger { grid-template-columns: repeat(2, 1fr); }
  .ledger-cell:nth-child(2) { border-right: 0; }
  .ledger-cell:nth-child(-n+2) { border-bottom: 1px solid #e6ebf1; }
  .filter-panel { flex-wrap: wrap; }
  .table-footer { align-items: flex-start; flex-direction: column; }
}

@media (max-width: 720px) {
  .page-heading { align-items: stretch; flex-direction: column; }
  .sync-ledger { grid-template-columns: 1fr; }
  .ledger-cell { border-right: 0; border-bottom: 1px solid #e6ebf1; }
  .ledger-cell:last-child { border-bottom: 0; }
  .filter-control, .filter-account, .keyword-input { width: 100%; min-width: 100%; }
}
</style>
