<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable class="filter-game" @change="onGameChange">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterRegionId" placeholder="选择大区" clearable class="filter-region" @change="handleSearch">
        <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable multiple collapse-tags class="filter-status" @change="handleSearch">
        <el-option label="空闲" value="idle" />
        <el-option label="使用中" value="in_use" />
        <el-option label="锁定" value="locked" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索账号名/昵称..." clearable class="filter-search" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon> 新增账号
      </el-button>
    </div>

    <div class="split-layout">
      <section class="left-panel" aria-label="游戏账号目录">
        <div class="panel-heading">
          <div>
            <span class="panel-eyebrow">游戏账号</span>
            <strong>账号目录</strong>
          </div>
          <span class="result-count">{{ total }} 个</span>
        </div>

        <div class="table-shell">
          <el-table
            ref="accountTableRef"
            :data="list"
            border
            v-loading="loading"
            highlight-current-row
            height="100%"
            row-key="id"
            @current-change="onCurrentChange"
          >
            <el-table-column label="账号" min-width="190">
              <template #default="{ row }">
                <div class="account-list-identity">
                  <strong>{{ row.account_name }}</strong>
                  <span>{{ row.account_no }}</span>
                  <small>{{ row.nickname || '未设置游戏昵称' }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="游戏" width="106" show-overflow-tooltip>
              <template #default="{ row }">{{ gameNameMap[row.game_id] || `#${row.game_id}` }}</template>
            </el-table-column>
            <el-table-column label="状态" width="76" align="center">
              <template #default="{ row }">
                <span class="account-status" :class="`status-${row.status}`">
                  <i aria-hidden="true"></i>{{ statusLabel(row.status) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="大区" width="66" align="center">
              <template #default="{ row }">
                <span class="region-count">{{ row.region_ids?.length || 0 }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrap" v-if="total > pageSize">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            @current-change="fetchList"
          />
        </div>
      </section>

      <section class="right-panel" aria-label="游戏账号详情">
        <template v-if="currentRow">
          <div class="account-profile-card">
            <div class="account-profile-heading">
              <div class="account-avatar" :class="`status-${currentRow.status}`">
                <el-icon><User /></el-icon>
              </div>
              <div class="account-profile-title">
                <span class="profile-kicker">GAME ACCOUNT #{{ currentRow.id }}</span>
                <h2>{{ currentRow.account_name }}</h2>
                <p>{{ gameNameMap[currentRow.game_id] || `游戏 #${currentRow.game_id}` }} · {{ currentRow.nickname || '未设置游戏昵称' }}</p>
              </div>
              <div class="account-profile-tags">
                <el-tag :type="statusTagType(currentRow.status)" effect="dark" size="small">{{ statusLabel(currentRow.status) }}</el-tag>
                <el-tag effect="plain" size="small">{{ gameNameMap[currentRow.game_id] || `#${currentRow.game_id}` }}</el-tag>
              </div>
            </div>

            <div class="account-meta-grid">
              <div><span>登录账号</span><strong class="mono-value">{{ currentRow.account_no || '-' }}</strong></div>
              <div><span>游戏昵称</span><strong>{{ currentRow.nickname || '未设置' }}</strong></div>
              <div><span>角色等级</span><strong>{{ currentRow.level || '未设置' }}</strong></div>
              <div><span>关联大区</span><strong>{{ currentRow.region_ids?.length || 0 }} 个</strong></div>
              <div><span>创建时间</span><strong>{{ formatDateTime(currentRow.created_at) }}</strong></div>
              <div><span>更新时间</span><strong>{{ formatDateTime(currentRow.updated_at) }}</strong></div>
            </div>
          </div>

          <div class="account-detail-actions">
            <el-button type="primary" plain @click="openRegionDialog(currentRow)">
              <el-icon><Connection /></el-icon>关联大区
            </el-button>
            <el-button @click="openDialog(currentRow)">
              <el-icon><EditPen /></el-icon>编辑账号
            </el-button>
            <el-popconfirm title="确认删除该游戏账号？" @confirm="handleDelete(currentRow.id)">
              <template #reference>
                <el-button type="danger" link>删除账号</el-button>
              </template>
            </el-popconfirm>
          </div>

          <div class="account-availability" :class="`status-${currentRow.status}`">
            <span class="availability-dot" aria-hidden="true"></span>
            <div>
              <strong>{{ statusLabel(currentRow.status) }}</strong>
              <p>{{ statusDescription(currentRow.status) }}</p>
            </div>
          </div>

          <div class="detail-section-heading">
            <div>
              <span class="panel-eyebrow">REGION ACCESS</span>
              <strong>已关联大区</strong>
            </div>
            <span>账号可在以下大区执行游戏任务</span>
          </div>

          <div v-if="selectedRegions.length" class="region-access-grid">
            <article v-for="region in selectedRegions" :key="region.id" class="region-access-card">
              <div class="region-icon"><el-icon><Location /></el-icon></div>
              <div class="region-access-copy">
                <strong>{{ region.name }}</strong>
                <small>大区 ID #{{ region.id }}</small>
              </div>
              <el-button class="region-script-link" link type="warning" @click="openRegionScriptManager(region)">
                <el-icon><ChatDotRound /></el-icon>大区话术
              </el-button>
            </article>
          </div>
          <el-empty v-else description="尚未关联大区">
            <el-button type="primary" plain @click="openRegionDialog(currentRow)">立即关联</el-button>
          </el-empty>

          <template v-if="extraFieldEntries.length">
            <div class="detail-section-heading extra-heading">
              <div>
                <span class="panel-eyebrow">EXTENDED DATA</span>
                <strong>扩展信息</strong>
              </div>
            </div>
            <div class="extra-field-grid">
              <div v-for="item in extraFieldEntries" :key="item.key">
                <span>{{ item.key }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </template>
        </template>

        <div v-else class="empty-detail">
          <el-empty description="从左侧选择一个游戏账号查看详情" />
        </div>
      </section>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑游戏账号' : '新增游戏账号'" width="550px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-form-item label="所属游戏" prop="game_id">
          <el-select v-model="form.game_id" placeholder="选择游戏" style="width:100%" @change="onFormGameChange">
            <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isEdit" label="所属大区">
          <el-select v-model="form.region_ids" placeholder="选择大区(可多选)" clearable multiple collapse-tags style="width:100%">
            <el-option v-for="r in formRegionList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
          <div class="form-region-hint">可暂不选择，创建后再通过“关联大区”设置；候选项会排除其他账号已绑定的大区</div>
        </el-form-item>
        <el-form-item label="账号名" prop="account_name">
          <el-input v-model="form.account_name" />
        </el-form-item>
        <el-form-item label="账号" prop="account_no">
          <el-input v-model="form.account_no" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空则不修改' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="游戏昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="等级">
          <el-input v-model="form.level" />
        </el-form-item>
        <el-form-item v-if="isEdit" label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="空闲" value="idle" />
            <el-option label="使用中" value="in_use" />
            <el-option label="锁定" value="locked" />
            <el-option label="禁用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关联大区弹窗 -->
    <el-dialog
      v-model="regionDialogVisible"
      :title="`关联大区 - ${regionAccount?.account_name || ''}`"
      width="680px"
      destroy-on-close
      class="region-link-dialog"
    >
      <div v-loading="linkRegionLoading" class="region-picker">
        <div class="region-picker-summary">
          <div class="region-picker-game">
            <span class="region-picker-icon"><el-icon><Trophy /></el-icon></span>
            <div>
              <small>所属游戏</small>
              <strong>{{ gameNameMap[regionAccount?.game_id] || '-' }}</strong>
            </div>
          </div>
          <div class="region-picker-metrics">
            <div><strong>{{ linkedRegionIds.length }}</strong><span>已选择</span></div>
            <div><strong>{{ linkRegionList.length }}</strong><span>可选择</span></div>
            <div><strong>{{ occupiedRegionCount }}</strong><span>其他账号占用</span></div>
          </div>
        </div>

        <div class="region-script-reminder">
          <el-icon><Warning /></el-icon>
          <div>
            <strong>关联后请检查大区话术</strong>
            <span>大区专属招呼、促单或售后内容不会随账号关联自动生成；保存后可从账号详情直接进入配置。</span>
          </div>
        </div>

        <div class="region-picker-heading">
          <div>
            <strong>选择可用大区</strong>
            <span>点击卡片即可选择或取消，每行展示两个大区</span>
          </div>
          <span v-if="occupiedRegionCount">已自动隐藏 {{ occupiedRegionCount }} 个占用大区</span>
        </div>

        <div v-if="linkRegionList.length" class="region-picker-grid">
          <button
            v-for="region in linkRegionList"
            :key="region.id"
            type="button"
            class="region-picker-card"
            :class="{ 'is-selected': linkedRegionIds.includes(region.id) }"
            :aria-pressed="linkedRegionIds.includes(region.id)"
            @click="toggleLinkedRegion(region.id)"
          >
            <span class="region-picker-card-icon"><el-icon><Location /></el-icon></span>
            <span class="region-picker-card-copy">
              <strong>{{ region.name }}</strong>
              <small>排序 {{ region.sort_order ?? '-' }} · 编码 {{ region.code || '未设置' }}</small>
            </span>
            <span class="region-picker-check">
              <el-icon v-if="linkedRegionIds.includes(region.id)"><Check /></el-icon>
              <el-icon v-else><Plus /></el-icon>
            </span>
          </button>
        </div>
        <el-empty v-else-if="!linkRegionLoading" description="当前游戏没有可关联的大区" :image-size="72" />
      </div>
      <template #footer>
        <el-button @click="regionDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="regionSubmitting"
          :disabled="linkRegionLoading || !linkedRegionIds.length"
          @click="saveLinkedRegions"
        >
          保存关联
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import {
  getAllGames, getAllRegions,
  getGameAccounts, createGameAccount, updateGameAccount, deleteGameAccount,
} from '../api'

const router = useRouter()

const gameList = ref([])
const regionList = ref([])
const allRegionList = ref([])
const formRegionList = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const filterGameId = ref(null)
const filterRegionId = ref(null)
const filterStatus = ref([])
const loading = ref(false)
const accountTableRef = ref(null)

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegionList.value.map(r => [r.id, r.name])))
function statusLabel(s) { return { idle: '空闲', in_use: '使用中', locked: '锁定', disabled: '禁用' }[s] || s }
function statusTagType(s) { return { idle: 'success', in_use: 'warning', locked: 'danger', disabled: 'info' }[s] || '' }
function statusDescription(s) {
  return {
    idle: '账号当前空闲，可参与新的游戏执行任务。',
    in_use: '账号正在执行任务，请避免同时修改关键配置。',
    locked: '账号已锁定，解除锁定前不会参与任务调度。',
    disabled: '账号已禁用，不会参与任务调度。',
  }[s] || '账号状态等待更新。'
}
function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }
const selectedRegions = computed(() => {
  const regionIds = currentRow.value?.region_ids || []
  return regionIds.map(id => ({
    id,
    name: regionNameMap.value[id] || `大区 #${id}`,
  }))
})
const extraFieldEntries = computed(() => Object.entries(currentRow.value?.extra_fields || {}).map(([key, value]) => ({
  key,
  value: value === null || value === undefined || value === '' ? '-' : String(value),
})))

function openRegionScriptManager(region) {
  if (!currentRow.value?.game_id || !region?.id) return
  router.push({
    path: '/games',
    query: {
      script_game_id: currentRow.value.game_id,
      script_region_id: region.id,
    },
  })
}

function remindRegionScripts(regionIds) {
  const names = regionIds
    .map(id => regionNameMap.value[id] || linkRegionList.value.find(region => region.id === id)?.name || `大区 #${id}`)
    .join('、')
  ElNotification({
    title: '请继续完善大区话术',
    message: `${names} 已完成关联。请在账号详情点击“大区话术”，检查或补充该大区的专属内容。`,
    type: 'warning',
    duration: 7000,
    position: 'bottom-right',
  })
}

async function fetchList() {
  loading.value = true
  try {
    const selectedId = currentRow.value?.id
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterRegionId.value) params.region_id = filterRegionId.value
    if (filterStatus.value && filterStatus.value.length) params.status = filterStatus.value.join(',')
    const res = await getGameAccounts(params)
    list.value = res.items
    total.value = res.total
    currentRow.value = list.value.find(item => item.id === selectedId) || list.value[0] || null
    await nextTick()
    accountTableRef.value?.setCurrentRow(currentRow.value)
  } finally { loading.value = false }
}
function handleSearch() { page.value = 1; fetchList() }

async function onGameChange() {
  filterRegionId.value = null
  regionList.value = filterGameId.value ? await getAllRegions(filterGameId.value) : []
  handleSearch()
}
async function onFormGameChange() {
  form.region_ids = []
  if (!form.game_id) {
    formRegionList.value = []
    return
  }
  const availability = await loadRegionAvailability(form.game_id)
  formRegionList.value = availability.regions
}

function compareRegionsByOrder(left, right) {
  const leftSort = Number.isFinite(Number(left.sort_order)) ? Number(left.sort_order) : Number.MAX_SAFE_INTEGER
  const rightSort = Number.isFinite(Number(right.sort_order)) ? Number(right.sort_order) : Number.MAX_SAFE_INTEGER
  if (leftSort !== rightSort) return leftSort - rightSort
  return Number(left.id) - Number(right.id)
}

async function loadRegionAvailability(gameId, currentAccountId = null, currentRegionIds = []) {
  if (!gameId) return { regions: [], occupiedCount: 0 }
  const [regions, accountResult] = await Promise.all([
    getAllRegions(gameId),
    getGameAccounts({ game_id: gameId, page: 1, page_size: 1000 }),
  ])
  const occupiedIds = new Set()
  for (const account of accountResult.items || []) {
    if (account.id === currentAccountId) continue
    for (const regionId of account.region_ids || []) occupiedIds.add(regionId)
  }
  const currentIds = new Set(currentRegionIds)
  const availableRegions = regions
    .filter(region => !occupiedIds.has(region.id) || currentIds.has(region.id))
    .sort(compareRegionsByOrder)
  return {
    regions: availableRegions,
    occupiedCount: regions.length - availableRegions.length,
  }
}

// ── 编辑 ──
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const rules = {
  game_id: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  account_name: [{ required: true, message: '请输入账号名', trigger: 'blur' }],
  account_no: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const defaultForm = () => ({
  game_id: null, region_ids: [],
  account_name: '', account_no: '', password: '', nickname: '', level: '', status: 'idle',
})
const form = reactive(defaultForm())

async function openDialog(row = null) {
  isEdit.value = !!row; editId.value = row?.id ?? null
  Object.assign(form, row ? { ...row, password: '', region_ids: row.region_ids || [] } : defaultForm())
  formRegionList.value = []
  dialogVisible.value = true
}

async function handleSubmit() {
  // 编辑模式下密码可选
  if (!isEdit.value) await formRef.value?.validate()
  submitting.value = true
  try {
    const data = { ...form }
    if (isEdit.value) {
      delete data.region_ids
      if (!data.password) delete data.password
    }
    if (isEdit.value) {
      await updateGameAccount(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createGameAccount(data)
      ElMessage.success('添加成功')
      if (data.region_ids?.length) remindRegionScripts(data.region_ids)
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}

async function handleDelete(id) {
  try {
    await deleteGameAccount(id)
    if (currentRow.value?.id === id) currentRow.value = null
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

// ── 关联大区 ──
const regionDialogVisible = ref(false)
const regionSubmitting = ref(false)
const regionAccount = ref(null)
const linkedRegionIds = ref([])
const linkRegionList = ref([])
const linkRegionLoading = ref(false)
const occupiedRegionCount = ref(0)

async function openRegionDialog(row) {
  regionAccount.value = row
  linkedRegionIds.value = [...(row.region_ids || [])]
  regionDialogVisible.value = true
  linkRegionList.value = []
  occupiedRegionCount.value = 0
  linkRegionLoading.value = true
  try {
    const availability = await loadRegionAvailability(row.game_id, row.id, row.region_ids || [])
    linkRegionList.value = [...availability.regions].sort(compareRegionsByOrder)
    occupiedRegionCount.value = availability.occupiedCount
  } catch (e) {
    ElMessage.error(e.message)
    regionDialogVisible.value = false
  } finally {
    linkRegionLoading.value = false
  }
}

function toggleLinkedRegion(regionId) {
  const index = linkedRegionIds.value.indexOf(regionId)
  if (index >= 0) linkedRegionIds.value.splice(index, 1)
  else linkedRegionIds.value.push(regionId)
}

async function saveLinkedRegions() {
  if (!linkedRegionIds.value.length) {
    ElMessage.warning('请至少选择一个大区')
    return
  }
  regionSubmitting.value = true
  try {
    const previousIds = new Set(regionAccount.value.region_ids || [])
    const addedRegionIds = linkedRegionIds.value.filter(id => !previousIds.has(id))
    await updateGameAccount(regionAccount.value.id, { region_ids: linkedRegionIds.value })
    ElMessage.success('大区关联已更新')
    regionDialogVisible.value = false
    await fetchList()
    if (addedRegionIds.length) remindRegionScripts(addedRegionIds)
  } catch (e) { ElMessage.error(e.message) } finally { regionSubmitting.value = false }
}

onMounted(async () => {
  gameList.value = await getAllGames()
  allRegionList.value = await getAllRegions()
  fetchList()
})
</script>

<style scoped>
.page-container {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  flex-shrink: 0;
  gap: 10px;
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.filter-game { width: 160px; }
.filter-region { width: 140px; }
.filter-status { width: 190px; }
.filter-search {
  width: 210px;
  margin-left: auto;
}
.toolbar .el-button { margin-left: 0; }

.split-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(410px, .9fr) minmax(500px, 1.18fr);
  gap: 14px;
  min-height: 0;
  overflow: hidden;
}
.left-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.panel-heading {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid #ebeef5;
}
.panel-heading > div,
.detail-section-heading > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.panel-heading strong,
.detail-section-heading strong {
  color: #303133;
  font-size: 15px;
  line-height: 20px;
}
.panel-eyebrow {
  color: #909399;
  font-size: 10px;
  line-height: 16px;
  letter-spacing: .1em;
}
.result-count {
  flex-shrink: 0;
  padding: 3px 9px;
  border-radius: 12px;
  background: #f0efff;
  color: #6257b8;
  font-size: 12px;
  line-height: 18px;
}
.table-shell {
  flex: 1;
  min-height: 0;
}
.left-panel :deep(.el-table) {
  border-right: 0;
  border-left: 0;
}
.left-panel :deep(.el-table__header th.el-table__cell) {
  background: #f7f8fb;
  color: #606266;
}
.left-panel :deep(.el-table__body tr.current-row > td.el-table__cell) {
  background: #f0efff;
}
.account-list-identity {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  padding: 3px 0;
}
.account-list-identity strong,
.account-list-identity span,
.account-list-identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-list-identity strong {
  color: #263445;
  font-size: 13px;
}
.account-list-identity span {
  color: #697487;
  font: 10px/1.45 Consolas, "SFMono-Regular", monospace;
}
.account-list-identity small {
  color: #9aa3ae;
  font-size: 10px;
}
.account-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #6f7883;
  font-size: 11px;
  white-space: nowrap;
}
.account-status i {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: #a7afb8;
}
.account-status.status-idle { color: #267a4a; }
.account-status.status-idle i {
  background: #35a265;
  box-shadow: 0 0 0 3px rgba(53, 162, 101, .12);
}
.account-status.status-in_use { color: #a26918; }
.account-status.status-in_use i { background: #d89225; }
.account-status.status-locked { color: #b74242; }
.account-status.status-locked i { background: #d45757; }
.region-count {
  display: inline-flex;
  min-width: 24px;
  height: 22px;
  align-items: center;
  justify-content: center;
  padding: 0 7px;
  border: 1px solid #dcd9f3;
  border-radius: 11px;
  background: #f8f7ff;
  color: #6257a6;
  font: 11px/1 Consolas, "SFMono-Regular", monospace;
}
.pagination-wrap {
  display: flex;
  flex-shrink: 0;
  justify-content: center;
  padding: 10px 8px;
  border-top: 1px solid #ebeef5;
}

.right-panel {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(31, 45, 61, .04);
}
.empty-detail {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.account-profile-card {
  overflow: hidden;
  border: 1px solid #dddaf3;
  border-left: 4px solid #6a5cc4;
  border-radius: 8px;
  background: linear-gradient(108deg, #f2f0ff 0%, #faf9ff 65%, #fff 100%);
}
.account-profile-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 16px 13px;
}
.account-avatar {
  width: 44px;
  height: 44px;
  display: flex;
  flex: 0 0 44px;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: #e5e1fa;
  color: #6558ad;
  font-size: 22px;
}
.account-avatar.status-idle {
  background: #ddf2e6;
  color: #288052;
}
.account-avatar.status-in_use {
  background: #fff0d8;
  color: #ac6b18;
}
.account-avatar.status-locked {
  background: #fbe3e3;
  color: #b44444;
}
.account-avatar.status-disabled {
  background: #eceef1;
  color: #777f88;
}
.account-profile-title { min-width: 0; }
.profile-kicker {
  display: block;
  color: #7a70ba;
  font: 700 9px/1.2 Consolas, "SFMono-Regular", monospace;
  letter-spacing: .12em;
}
.account-profile-title h2 {
  overflow: hidden;
  margin: 3px 0;
  color: #242f3d;
  font-size: 18px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-profile-title p {
  overflow: hidden;
  margin: 0;
  color: #727d8e;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-profile-tags {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
  margin-left: auto;
}
.account-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid #e3e0f2;
  background: rgba(255, 255, 255, .7);
}
.account-meta-grid > div {
  min-width: 0;
  padding: 10px 13px;
  border-right: 1px solid #e9e7f2;
  border-bottom: 1px solid #e9e7f2;
}
.account-meta-grid > div:nth-child(3n) { border-right: 0; }
.account-meta-grid > div:nth-last-child(-n+3) { border-bottom: 0; }
.account-meta-grid span,
.account-meta-grid strong {
  display: block;
}
.account-meta-grid span {
  color: #8c95a2;
  font-size: 10px;
}
.account-meta-grid strong {
  overflow: hidden;
  margin-top: 4px;
  color: #3b4654;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono-value {
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 11px !important;
}
.account-detail-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #e4e8ed;
  border-radius: 7px;
  background: #fafbfc;
}
.account-detail-actions .el-button { margin-left: 0; }
.account-availability {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 15px;
  border: 1px solid #dfe3e8;
  border-left: 4px solid #89929d;
  border-radius: 8px;
  background: #f8f9fa;
}
.availability-dot {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 50%;
  background: #89929d;
  box-shadow: 0 0 0 5px rgba(137, 146, 157, .12);
}
.account-availability strong {
  color: #34404e;
  font-size: 14px;
}
.account-availability p {
  margin: 3px 0 0;
  color: #7c8590;
  font-size: 11px;
}
.account-availability.status-idle {
  border-color: #bfe3ce;
  border-left-color: #35a265;
  background: #f1faf5;
}
.account-availability.status-idle .availability-dot {
  background: #35a265;
  box-shadow: 0 0 0 5px rgba(53, 162, 101, .12);
}
.account-availability.status-in_use {
  border-color: #ecd6b7;
  border-left-color: #d89225;
  background: #fff9ef;
}
.account-availability.status-in_use .availability-dot {
  background: #d89225;
  box-shadow: 0 0 0 5px rgba(216, 146, 37, .12);
}
.account-availability.status-locked {
  border-color: #edc5c5;
  border-left-color: #d45757;
  background: #fff5f5;
}
.account-availability.status-locked .availability-dot {
  background: #d45757;
  box-shadow: 0 0 0 5px rgba(212, 87, 87, .12);
}
.detail-section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin: 22px 2px 10px;
}
.detail-section-heading > span {
  color: #9aa2ad;
  font-size: 11px;
}
.region-access-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.region-access-card {
  display: grid;
  min-width: 0;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 11px;
  padding: 12px 13px;
  border: 1px solid #e1e3eb;
  border-radius: 8px;
  background: #fbfbfd;
}
.region-access-card:hover {
  border-color: #c9c4e8;
  background: #f8f7ff;
}
.region-icon {
  width: 34px;
  height: 34px;
  display: flex;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #ebe8fb;
  color: #675bb0;
  font-size: 17px;
}
.region-access-copy { min-width: 0; }
.region-access-card strong,
.region-access-card small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.region-access-card strong {
  color: #354151;
  font-size: 13px;
}
.region-access-card small {
  margin-top: 4px;
  color: #929aa5;
  font: 10px/1.3 Consolas, "SFMono-Regular", monospace;
}
.region-script-link {
  margin-left: 0 !important;
  padding: 5px 3px !important;
  font-size: 11px;
  white-space: nowrap;
}
.region-script-link .el-icon { margin-right: 3px; }
.extra-heading { margin-top: 24px; }
.extra-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafbfc;
}
.extra-field-grid > div {
  min-width: 0;
  padding: 10px 13px;
  border-right: 1px solid #e7e9ed;
  border-bottom: 1px solid #e7e9ed;
}
.extra-field-grid > div:nth-child(2n) { border-right: 0; }
.extra-field-grid > div:nth-last-child(-n+2) { border-bottom: 0; }
.extra-field-grid span,
.extra-field-grid strong { display: block; }
.extra-field-grid span { color: #929aa5; font-size: 10px; }
.extra-field-grid strong {
  overflow: hidden;
  margin-top: 3px;
  color: #3d4855;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-region-hint {
  margin-top: 5px;
  color: #9098a4;
  font-size: 11px;
  line-height: 1.5;
}

.region-picker {
  min-height: 240px;
}
.region-picker-summary {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  padding: 13px 15px;
  border: 1px solid #dddaf3;
  border-left: 4px solid #6a5cc4;
  border-radius: 8px;
  background: linear-gradient(105deg, #f3f1ff 0%, #faf9ff 64%, #fff 100%);
}
.region-picker-game {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
}
.region-script-reminder {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid #f0d7a9;
  border-radius: 7px;
  color: #a66515;
  background: #fff9ec;
}
.region-script-reminder > .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
  font-size: 16px;
}
.region-script-reminder div { min-width: 0; }
.region-script-reminder strong,
.region-script-reminder span { display: block; }
.region-script-reminder strong { font-size: 12px; }
.region-script-reminder span { margin-top: 3px; color: #9a784a; font-size: 10px; line-height: 1.5; }
.region-picker-icon {
  width: 36px;
  height: 36px;
  display: flex;
  flex: 0 0 36px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: #e6e2fa;
  color: #6559ad;
  font-size: 18px;
}
.region-picker-game small,
.region-picker-game strong {
  display: block;
}
.region-picker-game small {
  color: #8c94a0;
  font-size: 10px;
}
.region-picker-game strong {
  overflow: hidden;
  margin-top: 3px;
  color: #313d4c;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.region-picker-metrics {
  display: grid;
  flex-shrink: 0;
  grid-template-columns: repeat(3, minmax(62px, 1fr));
  border-left: 1px solid #e3e0f1;
}
.region-picker-metrics > div {
  display: flex;
  min-width: 68px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 0 10px;
  border-right: 1px solid #e3e0f1;
}
.region-picker-metrics > div:last-child { border-right: 0; }
.region-picker-metrics strong {
  color: #5f53a6;
  font: 700 16px/1.2 Consolas, "SFMono-Regular", monospace;
}
.region-picker-metrics span {
  margin-top: 4px;
  color: #9299a4;
  font-size: 9px;
  white-space: nowrap;
}
.region-picker-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin: 19px 2px 10px;
}
.region-picker-heading > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.region-picker-heading strong {
  color: #303b49;
  font-size: 14px;
}
.region-picker-heading span {
  color: #949ca7;
  font-size: 10px;
}
.region-picker-heading > span {
  flex-shrink: 0;
  color: #b06c18;
}
.region-picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  max-height: 380px;
  overflow-y: auto;
  padding: 1px 3px 3px 1px;
}
.region-picker-card {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
  padding: 12px;
  border: 1px solid #dfe2e8;
  border-radius: 8px;
  background: #fff;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color .16s ease, background-color .16s ease, box-shadow .16s ease, transform .16s ease;
}
.region-picker-card:hover {
  border-color: #bdb7e2;
  background: #faf9ff;
  transform: translateY(-1px);
}
.region-picker-card:focus-visible {
  outline: 3px solid rgba(106, 92, 196, .2);
  outline-offset: 1px;
}
.region-picker-card.is-selected {
  border-color: #7164c2;
  background: #f3f1ff;
  box-shadow: 0 0 0 2px rgba(113, 100, 194, .1);
}
.region-picker-card-icon {
  width: 34px;
  height: 34px;
  display: flex;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #eef0f4;
  color: #737d89;
  font-size: 16px;
}
.region-picker-card.is-selected .region-picker-card-icon {
  background: #ddd8f7;
  color: #6256ac;
}
.region-picker-card-copy {
  display: block;
  min-width: 0;
  flex: 1;
}
.region-picker-card-copy strong,
.region-picker-card-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.region-picker-card-copy strong {
  color: #354151;
  font-size: 13px;
}
.region-picker-card-copy small {
  margin-top: 4px;
  color: #969da7;
  font: 10px/1.3 Consolas, "SFMono-Regular", monospace;
}
.region-picker-check {
  width: 23px;
  height: 23px;
  display: flex;
  flex: 0 0 23px;
  align-items: center;
  justify-content: center;
  border: 1px solid #d9dde3;
  border-radius: 50%;
  color: #9ba2aa;
  font-size: 12px;
}
.region-picker-card.is-selected .region-picker-check {
  border-color: #6e61bd;
  background: #6e61bd;
  color: #fff;
}

@media (max-width: 1180px) {
  .page-container {
    height: auto;
    min-height: 100%;
  }
  .split-layout {
    display: flex;
    flex-direction: column;
    overflow: visible;
  }
  .left-panel {
    height: 470px;
    flex: none;
  }
  .right-panel {
    min-height: 560px;
    flex: none;
    overflow: visible;
  }
}
@media (max-width: 760px) {
  .toolbar { align-items: stretch; }
  .filter-game,
  .filter-region,
  .filter-status,
  .filter-search {
    width: 100%;
    margin-left: 0;
  }
  .toolbar .el-button { width: 100%; }
  .right-panel { padding: 12px; }
  .account-profile-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .account-profile-tags {
    width: 100%;
    margin-left: 56px;
  }
  .account-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .account-meta-grid > div:nth-child(3n) { border-right: 1px solid #e9e7f2; }
  .account-meta-grid > div:nth-child(2n) { border-right: 0; }
  .account-meta-grid > div:nth-last-child(-n+3) { border-bottom: 1px solid #e9e7f2; }
  .account-meta-grid > div:nth-last-child(-n+2) { border-bottom: 0; }
  .detail-section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .region-access-grid,
  .extra-field-grid {
    grid-template-columns: 1fr;
  }
  .extra-field-grid > div {
    border-right: 0;
    border-bottom: 1px solid #e7e9ed;
  }
  .extra-field-grid > div:nth-last-child(-n+2) { border-bottom: 1px solid #e7e9ed; }
  .extra-field-grid > div:last-child { border-bottom: 0; }
  .region-picker-summary {
    align-items: stretch;
    flex-direction: column;
  }
  .region-picker-metrics {
    min-height: 54px;
    border-top: 1px solid #e3e0f1;
    border-left: 0;
  }
  .region-picker-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .region-picker-grid { grid-template-columns: 1fr; }
}
</style>
