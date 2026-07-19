<template>
  <div class="page-container">
    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 140px" @change="onGameChange">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterRegionId" placeholder="选择大区" clearable style="width: 140px" :disabled="!filterGameId" @change="handleSearch">
        <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-select v-model="filterItemId" placeholder="选择物品" clearable filterable style="width: 160px" :disabled="!filterGameId" @change="handleSearch">
        <el-option v-for="i in itemList" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
      </el-select>
      <el-select v-model="filterHasStock" placeholder="有无库存" clearable style="width: 110px" @change="handleSearch">
        <el-option label="有库存" :value="1" />
        <el-option label="无库存" :value="0" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索物品名称..." clearable style="width: 180px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- 左右分栏 -->
    <div class="split-layout">
      <!-- 左面板：库存列表 -->
      <div class="left-panel">
        <el-table
          :data="list" border stripe v-loading="loading" row-key="id"
          highlight-current-row @current-change="onCurrentChange"
          :max-height="tableMaxHeight"
        >
          <el-table-column v-if="!filterRegionId" prop="region_name" label="大区" width="100" />
          <el-table-column prop="item_name" label="物品名称" min-width="150" show-overflow-tooltip />
          <el-table-column label="库存" width="70" align="center">
            <template #default="{ row }">
              <span :class="row.stock > 0 ? 'stock-positive' : 'stock-zero'">{{ row.stock }}</span>
            </template>
          </el-table-column>
          <el-table-column label="进货均价" width="100" align="center">
            <template #default="{ row }">{{ formatPrice(row.purchase_price) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="130" align="center">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrap" v-if="total > 0">
          <el-pagination
            v-model:current-page="page" :page-size="pageSize" :total="total"
            layout="total, prev, pager, next" @current-change="fetchList"
          />
        </div>
      </div>

      <!-- 右面板：详情 -->
      <div class="right-panel">
        <!-- 空状态 -->
        <div v-if="!currentRow" class="empty-detail">
          <el-empty description="请选择左侧物品查看详情" />
        </div>

        <!-- 详情内容 -->
        <template v-else>
          <!-- 物品信息卡片 -->
          <div class="info-card">
            <div class="info-card-title">{{ currentRow.item_name }}</div>
            <div class="info-card-body">
              <div class="info-item">
                <span class="info-label">编码</span>
                <span class="info-value">{{ currentRow.item_code || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">大区</span>
                <span class="info-value">{{ currentRow.region_name || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">库存</span>
                <span class="info-value" :class="currentRow.stock > 0 ? 'stock-positive' : 'stock-zero'">{{ currentRow.stock }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">进货均价</span>
                <span class="info-value">{{ formatPrice(currentRow.purchase_price) }}</span>
              </div>
            </div>
          </div>

          <!-- Tab 切换 -->
          <el-tabs v-model="activeTab" class="detail-tabs">
            <!-- Tab 1: 商铺定价 -->
            <el-tab-pane label="商铺定价" name="pricing">
              <div class="tab-toolbar">
                <el-button type="primary" size="small" :loading="savingPrice" :disabled="changedPriceIds.size === 0" @click="handleSaveShopPrices">
                  <el-icon><Check /></el-icon> 保存定价
                </el-button>
              </div>
              <el-table :data="shopPrices" border stripe size="small" v-loading="shopPriceLoading" max-height="300">
                <el-table-column label="商铺" min-width="140">
                  <template #default="{ row }">
                    <span>{{ getAccountLabel(row.account_id) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="出货价" width="130" align="center">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.selling_price"
                      :min="0" :precision="2" :controls-position="'right'"
                      size="small" style="width: 105px"
                      @change="onShopPriceChange(row)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="最低价" width="130" align="center">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.min_selling_price"
                      :min="0" :precision="2" :controls-position="'right'"
                      size="small" style="width: 105px"
                      @change="onShopPriceChange(row)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="最高价" width="130" align="center">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.max_selling_price"
                      :min="0" :precision="2" :controls-position="'right'"
                      size="small" style="width: 105px"
                      @change="onShopPriceChange(row)"
                    />
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- Tab 2: 出入库 -->
            <el-tab-pane label="出入库" name="stock">
              <div class="stock-forms">
                <!-- 入库 -->
                <el-card shadow="never" class="stock-card">
                  <template #header><span class="card-title">入库</span></template>
                  <el-form :model="stockInForm" label-width="80px" size="small">
                    <el-form-item label="入库数量">
                      <el-input-number v-model="stockInForm.quantity" :min="1" :step="1" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="入库单价">
                      <el-input-number v-model="stockInForm.unit_price" :min="0" :precision="2" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="预计均价">
                      <span class="calc-price">{{ calcNewAvg }}</span>
                    </el-form-item>
                    <el-form-item>
                      <el-button type="success" :loading="stockInLoading" @click="doStockIn">确认入库</el-button>
                    </el-form-item>
                  </el-form>
                </el-card>

                <!-- 出库 -->
                <el-card shadow="never" class="stock-card">
                  <template #header><span class="card-title">出库</span></template>
                  <el-form :model="stockOutForm" label-width="80px" size="small">
                    <el-form-item label="出库数量">
                      <el-input-number v-model="stockOutForm.quantity" :min="1" :max="stockOutForm.current_stock" :step="1" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="出库原因">
                      <el-input v-model="stockOutForm.reason" type="textarea" :rows="3" placeholder="必填：请说明出库原因" />
                    </el-form-item>
                    <el-form-item>
                      <el-button type="danger" :loading="stockOutLoading" @click="doStockOut">确认出库</el-button>
                    </el-form-item>
                  </el-form>
                </el-card>
              </div>
            </el-tab-pane>

            <!-- Tab 3: 风控参数 -->
            <el-tab-pane label="风控参数" name="risk">
              <el-form label-width="100px" size="default" class="risk-form">
                <el-form-item label="波动(额)">
                  <el-input-number
                    v-model="riskForm.max_fluctuation"
                    :min="0" :precision="2" :controls-position="'right'"
                    style="width: 200px"
                  />
                </el-form-item>
                <el-form-item label="波动(%)">
                  <el-input-number
                    v-model="riskForm.max_fluctuation_rate"
                    :min="0" :max="100" :precision="2" :controls-position="'right'"
                    style="width: 200px"
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="savingRisk" @click="handleSaveRisk">保存风控参数</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <!-- Tab 4: 变更记录 -->
            <el-tab-pane label="变更记录" name="logs">
              <el-timeline v-if="changeLogs.length > 0">
                <el-timeline-item
                  v-for="log in changeLogs" :key="log.id"
                  :timestamp="formatTime(log.created_at)"
                  :type="logType(log.change_type)"
                >
                  {{ formatLog(log) }}
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else description="暂无变更记录" />
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAllGames, getAllRegions, getAllItems, getRegionInventories,
  updateRegionInventoryBatch, updateShopPricesBatch, stockIn, stockOut,
  getInventoryChangeLogs, getInventoryShopPrices, getAllAccounts, getAllWebsites
} from '../api'

// ── 筛选状态 ──
const gameList = ref([])
const regionList = ref([])
const itemList = ref([])
const allAccounts = ref([])
const allWebsites = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const keyword = ref('')
const filterGameId = ref(null)
const filterRegionId = ref(null)
const filterItemId = ref(null)
const filterHasStock = ref(1)
const loading = ref(false)

// ── 表格高度 ──
const tableMaxHeight = ref(600)

// ── 当前选中行 ──
const currentRow = ref(null)
function onCurrentChange(row) {
  currentRow.value = row
}

// ── 右面板 Tab ──
const activeTab = ref('pricing')

// ── 商铺定价 ──
const shopPrices = ref([])
const shopPriceLoading = ref(false)
const savingPrice = ref(false)
const changedPriceIds = ref(new Set())

async function loadShopPrices() {
  if (!currentRow.value) return
  shopPriceLoading.value = true
  try {
    const data = await getInventoryShopPrices(currentRow.value.id)
    // 确保数值字段为数字类型，方便 el-input-number 绑定
    shopPrices.value = data.map(sp => ({
      ...sp,
      selling_price: Number(sp.selling_price || 0),
      min_selling_price: Number(sp.min_selling_price || 0),
      max_selling_price: Number(sp.max_selling_price || 0),
    }))
    changedPriceIds.value.clear()
  } catch (e) {
    ElMessage.error('加载商铺定价失败: ' + e.message)
  } finally {
    shopPriceLoading.value = false
  }
}

function getAccountLabel(accountId) {
  const acc = allAccounts.value.find(a => a.id === accountId)
  if (!acc) return '未知商铺'
  const w = allWebsites.value.find(s => s.id === acc.website_id)
  return w ? `${w.name} - ${acc.label}` : acc.label
}

function onShopPriceChange(row) {
  changedPriceIds.value.add(row.id)
}

async function handleSaveShopPrices() {
  const ids = Array.from(changedPriceIds.value)
  if (ids.length === 0) return
  savingPrice.value = true
  try {
    const items = ids.map(id => {
      const sp = shopPrices.value.find(r => r.id === id)
      if (!sp) return null
      return {
        shop_price_id: sp.id,
        selling_price: sp.selling_price,
        min_selling_price: sp.min_selling_price,
        max_selling_price: sp.max_selling_price,
      }
    }).filter(Boolean)
    await updateShopPricesBatch({ items })
    ElMessage.success(`已保存 ${ids.length} 条商铺定价`)
    changedPriceIds.value.clear()
    loadShopPrices()
  } catch (e) {
    ElMessage.error('保存定价失败: ' + e.message)
  } finally {
    savingPrice.value = false
  }
}

// ── 出入库 ──
const stockInLoading = ref(false)
const stockInForm = ref({ quantity: 1, unit_price: 0 })

const calcNewAvg = computed(() => {
  const oldStock = currentRow.value?.stock || 0
  const oldAvg = Number(currentRow.value?.purchase_price || 0)
  const qty = stockInForm.value.quantity || 0
  const price = stockInForm.value.unit_price || 0
  if (qty <= 0) return formatPrice(oldAvg)
  const totalOld = oldStock * oldAvg
  const totalNew = qty * price
  const newAvg = (totalOld + totalNew) / (oldStock + qty)
  return newAvg.toFixed(4)
})

async function doStockIn() {
  const f = stockInForm.value
  if (!f.quantity || f.quantity <= 0) { ElMessage.warning('请输入入库数量'); return }
  if (f.unit_price == null || f.unit_price < 0) { ElMessage.warning('请输入入库单价'); return }
  stockInLoading.value = true
  try {
    await stockIn({ inventory_id: currentRow.value.id, quantity: f.quantity, unit_price: f.unit_price })
    ElMessage.success('入库成功')
    stockInForm.value = { quantity: 1, unit_price: 0 }
    refreshCurrentRow()
  } catch (e) {
    ElMessage.error('入库失败: ' + e.message)
  } finally {
    stockInLoading.value = false
  }
}

const stockOutLoading = ref(false)
const stockOutForm = ref({ quantity: 1, reason: '' })

async function doStockOut() {
  const f = stockOutForm.value
  if (!f.quantity || f.quantity <= 0) { ElMessage.warning('请输入出库数量'); return }
  if (!f.reason || !f.reason.trim()) { ElMessage.warning('请输入出库原因'); return }
  stockOutLoading.value = true
  try {
    await stockOut({ inventory_id: currentRow.value.id, quantity: f.quantity, reason: f.reason.trim() })
    ElMessage.success('出库成功')
    stockOutForm.value = { quantity: 1, reason: '', current_stock: f.current_stock - f.quantity }
    refreshCurrentRow()
  } catch (e) {
    ElMessage.error('出库失败: ' + e.message)
  } finally {
    stockOutLoading.value = false
  }
}

// ── 风控参数 ──
const savingRisk = ref(false)
const riskForm = ref({ max_fluctuation: 0, max_fluctuation_rate: 0 })

async function handleSaveRisk() {
  savingRisk.value = true
  try {
    await updateRegionInventoryBatch({
      items: [{
        id: currentRow.value.id,
        max_fluctuation: riskForm.value.max_fluctuation,
        max_fluctuation_rate: riskForm.value.max_fluctuation_rate,
      }]
    })
    ElMessage.success('风控参数已保存')
    refreshCurrentRow()
  } catch (e) {
    ElMessage.error('保存风控参数失败: ' + e.message)
  } finally {
    savingRisk.value = false
  }
}

// ── 变更记录 ──
const changeLogs = ref([])

async function loadChangeLogs() {
  if (!currentRow.value) return
  try {
    changeLogs.value = await getInventoryChangeLogs(currentRow.value.id)
  } catch (e) {
    ElMessage.error('加载变更记录失败: ' + e.message)
  }
}

function logType(type) {
  if (type === 'stock_in') return 'success'
  if (type === 'stock_out') return 'danger'
  if (type === 'fluctuation_update') return 'warning'
  return 'info'
}

function formatLog(log) {
  if (log.change_type === 'stock_in') {
    return `入库 +${log.stock_delta}，单价 ¥${log.unit_price}，均价 ¥${log.avg_price_before} → ¥${log.avg_price_after}`
  }
  if (log.change_type === 'stock_out') {
    return `出库 -${Math.abs(log.stock_delta)}，库存 ${log.stock_before} → ${log.stock_after}，原因: ${log.change_reason || '-'}`
  }
  if (log.change_type === 'fluctuation_update') {
    return log.change_reason || '风控参数变更'
  }
  return log.change_type + (log.change_reason ? ': ' + log.change_reason : '')
}

// ── 刷新当前行数据 ──
async function refreshCurrentRow() {
  if (!currentRow.value) return
  const invId = currentRow.value.id
  await fetchList()
  // 重新选中对应行
  await nextTick()
  const row = list.value.find(r => r.id === invId)
  if (row) {
    currentRow.value = row
    // 同步风控参数表单
    riskForm.value = {
      max_fluctuation: Number(row.max_fluctuation || 0),
      max_fluctuation_rate: Number(row.max_fluctuation_rate || 0),
    }
  }
  // 刷新变更记录
  loadChangeLogs()
}

// ── 查询 ──
async function fetchGames() {
  gameList.value = await getAllGames()
  const [accounts, sites] = await Promise.all([getAllAccounts(), getAllWebsites()])
  allAccounts.value = accounts
  allWebsites.value = sites
}

async function onGameChange() {
  filterRegionId.value = null
  filterItemId.value = null
  regionList.value = []
  itemList.value = []
  list.value = []
  total.value = 0
  currentRow.value = null
  shopPrices.value = []
  changeLogs.value = []
  if (!filterGameId.value) return
  regionList.value = await getAllRegions(filterGameId.value)
  itemList.value = await getAllItems({ game_id: filterGameId.value })
  fetchList()
}

function handleSearch() {
  page.value = 1
  currentRow.value = null
  shopPrices.value = []
  changeLogs.value = []
  fetchList()
}

async function fetchList() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize,
      keyword: keyword.value,
      game_id: filterGameId.value,
    }
    if (filterRegionId.value) params.region_id = filterRegionId.value
    if (filterItemId.value) params.item_id = filterItemId.value
    if (filterHasStock.value !== null && filterHasStock.value !== '') params.has_stock = filterHasStock.value
    const res = await getRegionInventories(params)
    list.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error('加载库存失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// ── 监听选中行变化，加载详情 ──
watch(currentRow, async (row) => {
  if (!row) {
    shopPrices.value = []
    changeLogs.value = []
    return
  }
  // 同步风控参数表单
  riskForm.value = {
    max_fluctuation: Number(row.max_fluctuation || 0),
    max_fluctuation_rate: Number(row.max_fluctuation_rate || 0),
  }
  // 同步出入库表单
  stockInForm.value = { quantity: 1, unit_price: 0 }
  stockOutForm.value = { quantity: 1, reason: '', current_stock: row.stock }
  // 加载详情
  activeTab.value = 'pricing'
  await Promise.all([loadShopPrices(), loadChangeLogs()])
})

// ── 格式化 ──
function formatPrice(val) {
  if (val == null || val === 0) return '-'
  return '¥' + Number(val).toFixed(2)
}

function formatTime(val) {
  if (!val) return '-'
  const d = new Date(val)
  return isNaN(d.getTime()) ? val : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function pad(n) {
  return n < 10 ? '0' + n : n
}

// ── 响应式高度 ──
function calcTableHeight() {
  tableMaxHeight.value = window.innerHeight - 260
}

onMounted(() => {
  fetchGames()
  calcTableHeight()
  window.addEventListener('resize', calcTableHeight)
})
</script>

<style scoped>
.page-container {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

/* 筛选工具栏 */
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  align-items: center;
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* 左右分栏 */
.split-layout {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  overflow: hidden;
}

/* 左面板 */
.left-panel {
  flex: 0 0 420px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.left-panel .el-table {
  flex: 1;
}
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 10px;
  flex-shrink: 0;
}

/* 右面板 */
.right-panel {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 16px;
}
.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* 物品信息卡片 */
.info-card {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}
.info-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.info-card-body {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-label {
  font-size: 12px;
  color: #909399;
}
.info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

/* Tab 样式 */
.detail-tabs {
  margin-top: 0;
}
.detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

/* Tab 工具栏 */
.tab-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

/* 出入库表单 */
.stock-forms {
  display: flex;
  gap: 16px;
}
.stock-card {
  flex: 1;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
}

/* 风控表单 */
.risk-form {
  max-width: 400px;
}

/* 库存样式 */
.stock-positive { color: #67c23a; font-weight: bold; font-size: 15px; }
.stock-zero { color: #f56c6c; font-weight: bold; font-size: 15px; }

/* 均价预览 */
.calc-price { color: #409eff; font-weight: bold; }
</style>
