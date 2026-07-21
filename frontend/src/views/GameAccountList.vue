<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filterGameId" placeholder="选择游戏" clearable style="width: 160px" @change="onGameChange">
        <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="filterRegionId" placeholder="选择大区" clearable style="width: 140px" @change="handleSearch">
        <el-option v-for="r in regionList" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable multiple collapse-tags style="width: 200px" @change="handleSearch">
        <el-option label="空闲" value="idle" />
        <el-option label="使用中" value="in_use" />
        <el-option label="锁定" value="locked" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索账号名/昵称..." clearable style="width: 200px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon> 新增账号
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" highlight-current-row @current-change="onCurrentChange" row-key="id">
      <el-table-column prop="account_name" label="账号名" min-width="140" />
      <el-table-column label="游戏" width="120">
        <template #default="{ row }">{{ gameNameMap[row.game_id] || row.game_id }}</template>
      </el-table-column>
      <el-table-column label="大区" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="row.region_ids && row.region_ids.length">
            <el-tag v-for="rid in row.region_ids" :key="rid" size="small" style="margin-right:4px">{{ regionNameMap[rid] || rid }}</el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="nickname" label="昵称" width="120" />
      <el-table-column prop="level" label="等级" width="80" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openRegionDialog(row)">关联大区</el-button>
          <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDelete(row.id)">
            <template #reference><el-button size="small" link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑游戏账号' : '新增游戏账号'" width="550px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-form-item label="所属游戏" prop="game_id">
          <el-select v-model="form.game_id" placeholder="选择游戏" style="width:100%" @change="onFormGameChange">
            <el-option v-for="g in gameList" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属大区" prop="region_ids">
          <el-select v-model="form.region_ids" placeholder="选择大区(可多选)" clearable multiple collapse-tags style="width:100%">
            <el-option v-for="r in formRegionList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
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
    <el-dialog v-model="regionDialogVisible" :title="`关联大区 - ${regionAccount?.account_name || ''}`" width="480px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="所属游戏">
          <el-input :model-value="gameNameMap[regionAccount?.game_id] || '-'" disabled />
        </el-form-item>
        <el-form-item label="关联大区" required>
          <el-select v-model="linkedRegionIds" placeholder="请选择大区" multiple collapse-tags filterable style="width:100%">
            <el-option v-for="r in linkRegionList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="regionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="regionSubmitting" @click="saveLinkedRegions">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAllGames, getAllRegions,
  getGameAccounts, createGameAccount, updateGameAccount, deleteGameAccount,
} from '../api'

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

const gameNameMap = computed(() => Object.fromEntries(gameList.value.map(g => [g.id, g.name])))
const regionNameMap = computed(() => Object.fromEntries(allRegionList.value.map(r => [r.id, r.name])))
function statusLabel(s) { return { idle: '空闲', in_use: '使用中', locked: '锁定', disabled: '禁用' }[s] || s }
function statusTagType(s) { return { idle: 'success', in_use: 'warning', locked: 'danger', disabled: 'info' }[s] || '' }

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, keyword: keyword.value }
    if (filterGameId.value) params.game_id = filterGameId.value
    if (filterRegionId.value) params.region_id = filterRegionId.value
    if (filterStatus.value && filterStatus.value.length) params.status = filterStatus.value.join(',')
    const res = await getGameAccounts(params)
    list.value = res.items; total.value = res.total
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
  formRegionList.value = form.game_id ? await getAllRegions(form.game_id) : []
}

// ── 编辑 ──
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const rules = {
  game_id: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  region_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一个大区', trigger: 'change' }],
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
  formRegionList.value = row?.game_id ? await getAllRegions(row.game_id) : []
  dialogVisible.value = true
}

async function handleSubmit() {
  // 编辑模式下密码可选
  if (!isEdit.value) await formRef.value?.validate()
  submitting.value = true
  try {
    const data = { ...form }
    if (isEdit.value && !data.password) delete data.password
    if (isEdit.value) { await updateGameAccount(editId.value, data); ElMessage.success('更新成功') }
    else { await createGameAccount(data); ElMessage.success('添加成功') }
    dialogVisible.value = false; fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { submitting.value = false }
}

async function handleDelete(id) {
  try { await deleteGameAccount(id); ElMessage.success('已删除'); fetchList() } catch (e) { ElMessage.error(e.message) }
}

// ── 关联大区 ──
const regionDialogVisible = ref(false)
const regionSubmitting = ref(false)
const regionAccount = ref(null)
const linkedRegionIds = ref([])
const linkRegionList = ref([])

async function openRegionDialog(row) {
  regionAccount.value = row
  linkedRegionIds.value = [...(row.region_ids || [])]
  linkRegionList.value = await getAllRegions(row.game_id)
  regionDialogVisible.value = true
}

async function saveLinkedRegions() {
  if (!linkedRegionIds.value.length) {
    ElMessage.warning('请至少选择一个大区')
    return
  }
  regionSubmitting.value = true
  try {
    await updateGameAccount(regionAccount.value.id, { region_ids: linkedRegionIds.value })
    ElMessage.success('大区关联已更新')
    regionDialogVisible.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.message) } finally { regionSubmitting.value = false }
}

onMounted(async () => {
  gameList.value = await getAllGames()
  allRegionList.value = await getAllRegions()
  fetchList()
})
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
</style>
