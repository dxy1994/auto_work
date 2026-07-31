<template>
  <div class="sales-products-page">
    <header class="page-heading">
      <div>
        <div class="heading-kicker">LIVE LISTING LEDGER</div>
        <h1>平台在售商品</h1>
        <p>核对平台实际在售记录与系统解析结果。只有完整快照确认后，列表才会新增、更新或移除。</p>
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
      >
        <el-table-column label="平台 / 账号" width="160" fixed="left">
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
        <el-table-column label="平台商品 ID" width="150">
          <template #default="{ row }">
            <span class="product-id">{{ row.platform_product_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="游戏 / 大区" width="170">
          <template #default="{ row }">
            <div class="location-cell">
              <strong>{{ row.game_name || '-' }}</strong>
              <span>{{ row.region_name || '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="平台标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="实际商品" width="135" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'muted-value': !row.parsed_item_name }">
              {{ row.parsed_item_name || '未解析' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="quantity_text" label="数量" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.quantity_text || '-' }}</template>
        </el-table-column>
        <el-table-column prop="price_text" label="平台价格" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="price-value">{{ row.price_text || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" width="128" align="center">
          <template #default="{ row }">
            <el-tooltip
              :content="row.parse_error || '游戏、大区和实际商品均已匹配'"
              placement="top"
            >
              <el-tag :type="parseStatusType(row.parse_status)" size="small">
                {{ parseStatusLabel(row.parse_status) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="platform_registered_at" label="平台登记时间" width="150">
          <template #default="{ row }">{{ row.platform_registered_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="同步时间" width="160">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div class="table-footer">
      <span>平台商品消失后，会在下一次成功的完整快照中从此处同步移除。</span>
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
import { ElMessage } from 'element-plus'
import {
  getAllAccounts,
  getAllGames,
  getAllWebsites,
  getPlatformSalesProducts,
} from '../api'

const websites = ref([])
const accounts = ref([])
const games = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)

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

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
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
  min-height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 2px 2px 0;
}

.heading-kicker {
  margin-bottom: 5px;
  color: var(--ledger-blue);
  font: 700 11px/1.2 "SFMono-Regular", Consolas, monospace;
  letter-spacing: .16em;
}

.page-heading h1 {
  margin: 0;
  color: var(--ledger-ink);
  font-size: 25px;
  line-height: 1.25;
  letter-spacing: -.02em;
}

.page-heading p {
  margin: 7px 0 0;
  color: #606b78;
  font-size: 13px;
  line-height: 1.6;
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
  padding: 14px 18px;
  border-right: 1px solid #e6ebf1;
}

.ledger-cell:last-child { border-right: 0; }
.ledger-cell span, .ledger-cell small { display: block; }
.ledger-cell span { color: #7a8592; font-size: 12px; }
.ledger-cell strong {
  display: inline-block;
  margin: 5px 0 3px;
  color: var(--ledger-navy);
  font-size: 24px;
  line-height: 1;
}
.ledger-cell small {
  overflow: hidden;
  color: #98a1ac;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ledger-cell .matched-number { color: var(--ledger-green); }
.ledger-cell .warning-number { color: var(--ledger-amber); }
.ledger-time strong { font: 700 15px/1.6 "SFMono-Regular", Consolas, monospace; }

.filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px;
  border: 1px solid #e0e5eb;
  border-radius: 8px;
  background: #fff;
}

.filter-control { width: 160px; }
.filter-account { width: 210px; }
.keyword-input { min-width: 250px; flex: 1; }

.table-shell {
  min-height: 360px;
  flex: 1;
  overflow: hidden;
  border: 1px solid #dfe4ea;
  border-radius: 8px;
  background: #fff;
}

.sales-table { width: 100%; }
.source-cell, .location-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.source-cell > span:last-child,
.location-cell span {
  overflow: hidden;
  color: #697481;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.location-cell strong {
  overflow: hidden;
  color: #263241;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-chip {
  width: fit-content;
  padding: 2px 7px;
  border-radius: 3px;
  background: #eaf2fb;
  color: #245f99;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.35;
}
.platform-chip[data-platform="itemmania"] { background: #fff1e6; color: #a84f12; }
.platform-chip[data-platform="itembay"] { background: #edf2ff; color: #3f51a2; }
.platform-chip[data-platform="barotem"] { background: #e8f7f0; color: #217657; }

.product-id {
  color: #253750;
  font: 600 12px/1.4 "SFMono-Regular", Consolas, monospace;
}
.price-value { color: #8b4b13; font-weight: 650; }
.muted-value { color: #a4acb5; }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  color: #7d8792;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .sync-ledger { grid-template-columns: repeat(2, 1fr); }
  .ledger-cell:nth-child(2) { border-right: 0; }
  .ledger-cell:nth-child(-n+2) { border-bottom: 1px solid #e6ebf1; }
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
