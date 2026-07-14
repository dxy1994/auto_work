<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 180px" @change="onGameChange">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterRegionId" placeholder="选择大区" clearable style="width: 180px" :disabled="!filterGameId" @change="handleSearch">
        <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索物品名称..." clearable style="width: 200px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" :loading="saving" :disabled="changedRows.length === 0" @click="handleBatchSave">
        <el-icon><Check /></el-icon> 保存库存
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" row-key="id">
      <el-table-column prop="item_code" label="物品编码" width="140" />
      <el-table-column prop="item_name" label="物品名称" min-width="180" />
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <el-image v-if="row.item_image" :src="row.item_image" :preview-src-list="[row.item_image]" style="width:40px;height:40px" fit="cover" />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="库存数量" width="160" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.stock"
            :min="0"
            :step="1"
            :controls-position="'right'"
            style="width: 110px"
            @change="onStockChange(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="160" align="center">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllGames, getAllRegions, getRegionInventories, updateRegionInventory } from '../api'

const gameList = ref([])
const regionList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const keyword = ref('')
const filterGameId = ref(null)
const filterRegionId = ref(null)
const loading = ref(false)
const saving = ref(false)

// 记录被修改过的行 { id: originalStock }
const originalStocks = ref(new Map())
const changedRows = computed(() =>
  Array.from(originalStocks.value.keys()).filter((id) => {
    const row = list.value.find((r) => r.id === id)
    return row && row.stock !== originalStocks.value.get(id)
  })
)

async function fetchGames() {
  gameList.value = await getAllGames()
}

async function onGameChange() {
  filterRegionId.value = null
  regionList.value = []
  list.value = []
  total.value = 0
  originalStocks.value.clear()
  if (!filterGameId.value) return
  regionList.value = await getAllRegions(filterGameId.value)
  if (regionList.value.length > 0) {
    filterRegionId.value = regionList.value[0].id
    fetchList()
  }
}

function handleSearch() {
  page.value = 1
  originalStocks.value.clear()
  fetchList()
}

async function fetchList() {
  if (!filterRegionId.value) {
    list.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize,
      keyword: keyword.value,
      game_id: filterGameId.value,
      region_id: filterRegionId.value,
    }
    const res = await getRegionInventories(params)
    list.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error('加载库存失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function onStockChange(row) {
  if (!originalStocks.value.has(row.id)) {
    originalStocks.value.set(row.id, row.stock)
  }
}

async function handleBatchSave() {
  if (changedRows.value.length === 0) return
  saving.value = true
  try {
    for (const id of changedRows.value) {
      const row = list.value.find((r) => r.id === id)
      if (!row) continue
      await updateRegionInventory(id, { stock: row.stock })
    }
    ElMessage.success(`已保存 ${changedRows.value.length} 条库存记录`)
    originalStocks.value.clear()
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
