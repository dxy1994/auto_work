<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 160px" @change="onGameChange">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterRegionId" placeholder="选择大区" clearable style="width: 160px" :disabled="!filterGameId" @change="handleSearch">
        <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-select v-model="filterItemId" placeholder="选择物品" clearable filterable style="width: 180px" :disabled="!filterGameId" @change="handleSearch">
        <el-option v-for="i in itemList" :key="i.id" :label="`${i.name} (${i.code})`" :value="i.id" />
      </el-select>
      <el-select v-model="filterHasStock" placeholder="有无库存" clearable style="width: 120px" @change="handleSearch">
        <el-option label="有库存" :value="1" />
        <el-option label="无库存" :value="0" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索物品名称..." clearable style="width: 180px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" :loading="saving" :disabled="changedIds.size === 0" @click="handleBatchSave">
        <el-icon><Check /></el-icon> 保存库存
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" row-key="id" style="min-width: 1100px">
      <el-table-column v-if="!filterRegionId" prop="region_name" label="大区" width="120" />
      <el-table-column prop="item_name" label="物品名称" min-width="200" />
      <el-table-column label="库存" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.stock"
            :min="0"
            :step="1"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="进货价" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.purchase_price"
            :min="0"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="出货价" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.selling_price"
            :min="0"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="最低价" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.min_selling_price"
            :min="0"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="最高价" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.max_selling_price"
            :min="0"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="波动(额)" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.max_fluctuation"
            :min="0"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="波动(%)" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.max_fluctuation_rate"
            :min="0"
            :max="100"
            :precision="2"
            :controls-position="'right'"
            size="small"
            style="width: 90px"
            @change="onFieldChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="150" align="center">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllGames, getAllRegions, getAllItems, getRegionInventories, updateRegionInventoryBatch } from '../api'

const gameList = ref([])
const regionList = ref([])
const itemList = ref([])
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
const saving = ref(false)

const changedIds = ref(new Set())

async function fetchGames() {
  gameList.value = await getAllGames()
}

async function onGameChange() {
  filterRegionId.value = null
  filterItemId.value = null
  regionList.value = []
  itemList.value = []
  list.value = []
  total.value = 0
  changedIds.value.clear()
  if (!filterGameId.value) return
  regionList.value = await getAllRegions(filterGameId.value)
  itemList.value = await getAllItems({ game_id: filterGameId.value })
  fetchList()
}

function handleSearch() {
  page.value = 1
  changedIds.value.clear()
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

function onFieldChange(row) {
  changedIds.value.add(row.id)
}

async function handleBatchSave() {
  const ids = Array.from(changedIds.value)
  if (ids.length === 0) return
  saving.value = true
  try {
    const items = ids.map(id => {
      const row = list.value.find(r => r.id === id)
      if (!row) return null
      return {
        id,
        stock: row.stock,
        purchase_price: row.purchase_price,
        selling_price: row.selling_price,
        min_selling_price: row.min_selling_price,
        max_selling_price: row.max_selling_price,
        max_fluctuation: row.max_fluctuation,
        max_fluctuation_rate: row.max_fluctuation_rate,
      }
    }).filter(Boolean)
    await updateRegionInventoryBatch({ items })
    ElMessage.success(`已保存 ${ids.length} 条库存记录`)
    changedIds.value.clear()
    fetchList()
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

function formatTime(val) {
  if (!val) return '-'
  const d = new Date(val)
  return isNaN(d.getTime()) ? val : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function pad(n) {
  return n < 10 ? '0' + n : n
}

onMounted(fetchGames)
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
</style>
