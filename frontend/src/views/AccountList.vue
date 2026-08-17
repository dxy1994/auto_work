<template>
  <div class="page-container">
    <section class="account-directory">
      <header class="directory-header">
        <div>
          <span class="directory-eyebrow">登录资产</span>
          <div class="directory-title-line">
            <h1>平台账号</h1>
            <span>{{ total }} 个</span>
          </div>
          <p>维护平台凭据，并查看每个账号的订单监控状态。</p>
        </div>
        <div class="directory-header__actions">
          <span class="monitor-summary"><i></i>{{ monitoringCount }} 个监控中</span>
          <el-button type="primary" @click="openDialog()">
            <el-icon><Plus /></el-icon>新增账号
          </el-button>
        </div>
      </header>

      <div class="directory-filters">
        <el-select v-model="filterWebsite" class="website-filter" placeholder="全部平台" clearable filterable @change="handleSearch">
          <el-option v-for="w in allWebsites" :key="w.id" :label="w.name" :value="w.id" />
        </el-select>
        <el-button :disabled="!filterWebsite" @click="resetFilters">重置</el-button>
        <span>监控状态每 5 秒自动同步</span>
      </div>

      <div class="list-table-viewport">
      <el-table
        class="account-table"
        :data="list"
        border
        stripe
        height="100%"
        v-loading="loading"
        highlight-current-row
        :row-class-name="accountRowClassName"
        @current-change="onCurrentChange"
        row-key="id"
        aria-label="平台账号列表"
      >
      <el-table-column label="所属平台" width="150">
        <template #default="{ row }">
          <span class="platform-badge" :class="platformToneClass(row.website_id)" :title="websiteName(row.website_id)">
            <i></i>{{ websiteName(row.website_id) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="账号身份" min-width="230">
        <template #default="{ row }">
          <div class="account-identity">
            <div>
              <strong :title="row.label">{{ row.label || '未命名账号' }}</strong>
              <el-tag v-if="row.is_default" type="success" effect="plain" size="small">默认</el-tag>
            </div>
            <span :title="row.username">{{ row.username || '未填写用户名' }} · ID {{ row.id }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="登录密码" min-width="190">
        <template #default="{ row }">
          <div class="password-cell">
            <span
              class="password-value"
              :class="{ masked: !hasRevealedPassword(row.id) }"
              :title="hasRevealedPassword(row.id) ? revealedPasswords[row.id] : '密码已隐藏'"
            >
              {{ hasRevealedPassword(row.id) ? revealedPasswords[row.id] : '••••••••' }}
            </span>
            <el-button
              link
              type="primary"
              :loading="passwordLoading[row.id]"
              :title="hasRevealedPassword(row.id) ? '隐藏密码' : '查看密码'"
              @click.stop="togglePassword(row)"
            >
              <el-icon>
                <Hide v-if="hasRevealedPassword(row.id)" />
                <View v-else />
              </el-icon>
            </el-button>
            <el-button
              link
              type="primary"
              :loading="passwordLoading[row.id]"
              title="复制密码"
              @click.stop="copyPassword(row)"
            >
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="订单监控" width="150">
        <template #default="{ row }">
          <div class="account-run-state" :class="`state-${getCheckStatus(row.id)}`">
            <div><i></i><strong>{{ checkStatusLabel(row.id) }}</strong></div>
            <span>{{ checkStatusHint(row.id) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" align="right">
        <template #default="{ row }">
          <template v-if="getCheckStatus(row.id) === 'running' || getCheckStatus(row.id) === 'stopping'">
            <el-button size="small" type="danger" plain :loading="cancellingId === row.id" @click="handleCancelCheck(row)">
              终止查询
            </el-button>
          </template>
          <template v-else>
            <el-button size="small" type="primary" plain :loading="orderCheckingId === row.id" @click="handleOrderCheck(row)">
              订单查询
            </el-button>
          </template>
          <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty :description="filterWebsite ? '该平台还没有账号' : '当前还没有平台账号'" :image-size="84" /></template>
    </el-table>
      </div>

      <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        :pager-count="5"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="fetchList"
        @size-change="handlePageSizeChange"
      />
      </div>
    </section>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑账号' : '新增账号'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-form-item label="所属平台" prop="website_id">
          <el-select v-model="form.website_id" placeholder="选择平台" style="width:100%">
            <el-option v-for="w in allWebsites" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号标签" prop="label">
          <el-input v-model="form.label" placeholder="如：个人、公司" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" :prop="isEdit ? '' : 'password'">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="isEdit ? '留空则不修改' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAccounts, getAccountPassword, createAccount, updateAccount, deleteAccount,
  getAllWebsites, orderCheck, getOrderCheckStatus, cancelOrderCheck,
} from '../api'

const allWebsites = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterWebsite = ref(null)
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const revealedPasswords = ref({})
const passwordLoading = reactive({})

const orderCheckingId = ref(null)
const cancellingId = ref(null)

// 订单监控状态轮询
const orderCheckStatuses = ref({})  // { accountId: { status, message, start_time } }
let statusPollTimer = null
const STATUS_REFRESH_INTERVAL_MS = 5000

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

function getCheckStatus(accountId) {
  const s = orderCheckStatuses.value[accountId]
  return s ? s.status : 'idle'
}

const monitoringCount = computed(() => list.value.filter(account => getCheckStatus(account.id) === 'running').length)

function checkStatusLabel(accountId) {
  return { running: '监控中', stopping: '终止中', idle: '未运行' }[getCheckStatus(accountId)] || '未运行'
}

function checkStatusHint(accountId) {
  return {
    running: '持续检查订单',
    stopping: '等待任务退出',
    idle: '可启动查询',
  }[getCheckStatus(accountId)] || '可启动查询'
}

function platformToneClass(id) {
  const tones = ['blue', 'violet', 'amber', 'teal', 'rose', 'slate']
  const index = Math.max(0, (Number(id) || 1) - 1) % tones.length
  return `tone-${tones[index]}`
}

function accountRowClassName({ row }) {
  const status = getCheckStatus(row.id)
  return status === 'running' ? 'account-row--running' : status === 'stopping' ? 'account-row--stopping' : ''
}

async function pollStatus() {
  try {
    const res = await getOrderCheckStatus()
    // 构建新的状态映射：合并已有 running/stopping 状态，移除已完成的
    const newMap = {}
    for (const [key, info] of Object.entries(res)) {
      if (info.status === 'running' || info.status === 'stopping') {
        newMap[Number(key)] = info
      }
    }
    orderCheckStatuses.value = newMap
  } catch (e) {
    // 静默忽略轮询错误
  }
}

const defaultForm = () => ({
  website_id: null, label: '', username: '', password: '', is_default: 0,
})
const form = reactive(defaultForm())

const rules = {
  website_id: [{ required: true, message: '请选择平台', trigger: 'change' }],
  label:      [{ required: true, message: '请输入标签', trigger: 'blur' }],
  username:   [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password:   [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function websiteName(id) {
  return allWebsites.value.find(w => w.id === id)?.name || id
}

async function fetchList() {
  clearRevealedPasswords()
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterWebsite.value) params.website_id = filterWebsite.value
    const res = await getAccounts(params)
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function hasRevealedPassword(accountId) {
  return Object.prototype.hasOwnProperty.call(revealedPasswords.value, accountId)
}

function clearRevealedPasswords() {
  revealedPasswords.value = {}
}

async function loadPassword(accountId) {
  passwordLoading[accountId] = true
  try {
    const result = await getAccountPassword(accountId)
    const password = String(result?.password ?? '')
    if (!password) throw new Error('账号密码为空')
    return password
  } finally {
    delete passwordLoading[accountId]
  }
}

async function togglePassword(row) {
  if (hasRevealedPassword(row.id)) {
    const nextPasswords = { ...revealedPasswords.value }
    delete nextPasswords[row.id]
    revealedPasswords.value = nextPasswords
    return
  }
  try {
    const password = await loadPassword(row.id)
    revealedPasswords.value = {
      ...revealedPasswords.value,
      [row.id]: password,
    }
  } catch (e) {
    ElMessage.error('查看密码失败: ' + e.message)
  }
}

async function writeClipboard(text) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    if (!document.execCommand('copy')) throw new Error('浏览器拒绝复制')
  } finally {
    textarea.remove()
  }
}

async function copyPassword(row) {
  try {
    const password = hasRevealedPassword(row.id)
      ? revealedPasswords.value[row.id]
      : await loadPassword(row.id)
    await writeClipboard(password)
    ElMessage.success('密码已复制')
  } catch (e) {
    ElMessage.error('复制密码失败: ' + e.message)
  }
}

async function fetchAllWebsites() {
  allWebsites.value = await getAllWebsites()
}

function handleSearch() {
  page.value = 1
  fetchList()
}
function handlePageSizeChange() {
  page.value = 1
  fetchList()
}
function resetFilters() {
  filterWebsite.value = null
  handleSearch()
}

function openDialog(a = null) {
  isEdit.value = !!a
  editId.value = a?.id ?? null
  Object.assign(form, a
    ? { website_id: a.website_id, label: a.label, username: a.username, password: '', is_default: a.is_default ?? 0 }
    : defaultForm()
  )
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      const data = { label: form.label, username: form.username, is_default: form.is_default }
      if (form.password) data.password = form.password
      await updateAccount(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createAccount({ ...form })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  await deleteAccount(id)
  ElMessage.success('删除成功')
  fetchList()
}

// ── 订单查询 ──
async function handleOrderCheck(row) {
  orderCheckingId.value = row.id
  try {
    const res = await orderCheck(row.id)
    if (res.status === 'started') {
      ElMessage.success(res.message)
      // 立即更新本地状态
      orderCheckStatuses.value[row.id] = {
        status: 'running',
        message: '订单监控运行中...',
        start_time: Date.now() / 1000,
      }
      // 立即再向后端同步一次，随后保持统一的 5 秒刷新。
      pollStatus()
    } else {
      ElMessage.warning(res.message || res.status)
    }
  } catch (e) {
    ElMessage.error('订单查询失败: ' + e.message)
  } finally {
    orderCheckingId.value = null
  }
}

// ── 终止订单查询 ──
async function handleCancelCheck(row) {
  cancellingId.value = row.id
  try {
    const res = await cancelOrderCheck(row.id)
    if (res.status === 'stopping') {
      ElMessage.success(res.message)
      // 立即更新本地状态
      orderCheckStatuses.value[row.id] = {
        ...orderCheckStatuses.value[row.id],
        status: 'stopping',
        message: '正在终止...',
      }
    } else {
      ElMessage.info(res.message)
    }
  } catch (e) {
    ElMessage.error('终止失败: ' + e.message)
  } finally {
    cancellingId.value = null
  }
}

onMounted(() => {
  fetchAllWebsites()
  fetchList()
  // 默认开启自动刷新，进入页面立即同步，之后每 5 秒刷新。
  pollStatus()
  statusPollTimer = setInterval(pollStatus, STATUS_REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  clearRevealedPasswords()
  if (statusPollTimer) {
    clearInterval(statusPollTimer)
    statusPollTimer = null
  }
})
</script>

<style scoped>
.page-container { display: flex; height: 100%; min-height: 0; flex-direction: column; overflow: hidden; padding: 0; }
.account-directory { display: flex; min-height: 0; flex: 1; flex-direction: column; overflow: hidden; border: 1px solid #dfe6ee; border-radius: 10px; background: #fff; }
.directory-header { display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; gap: 20px; padding: 16px 18px 14px; }
.directory-eyebrow { color: #3d83ca; font-size: 10px; font-weight: 700; letter-spacing: .12em; }
.directory-title-line { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.directory-title-line h1 { margin: 0; color: #23384f; font-size: 21px; line-height: 1.2; }
.directory-title-line > span { padding: 2px 8px; color: #708196; border: 1px solid #dce4ec; border-radius: 999px; background: #f7f9fb; font-size: 11px; }
.directory-header p { margin: 4px 0 0; color: #8491a2; font-size: 12px; }
.directory-header__actions { display: flex; align-items: center; gap: 12px; }
.monitor-summary { display: inline-flex; align-items: center; gap: 6px; color: #627287; font-size: 11px; }
.monitor-summary i { width: 7px; height: 7px; border-radius: 50%; background: #38a978; box-shadow: 0 0 0 4px rgba(56, 169, 120, .1); }
.directory-filters { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; padding: 8px 12px; border-top: 1px solid #edf1f5; border-bottom: 1px solid #e3e9f0; background: #f8fafc; }
.directory-filters > span { margin-left: auto; color: #909dab; font-size: 10px; }
.website-filter { width: 210px; }
.list-table-viewport { min-height: 0; flex: 1; overflow: hidden; }
.account-table { width: 100%; border-right: 0; border-left: 0; }
.account-table :deep(.el-table__header th.el-table__cell) { height: 40px; color: #65768b; background: #f7f9fc; font-size: 12px; font-weight: 600; }
.account-table :deep(.el-table__body td.el-table__cell) { padding: 9px 0; }
.account-table :deep(.account-row--running > td:first-child) { box-shadow: inset 3px 0 #36a475; }
.account-table :deep(.account-row--stopping > td:first-child) { box-shadow: inset 3px 0 #d06a6a; }
.platform-badge { display: inline-flex; max-width: 118px; align-items: center; gap: 5px; padding: 3px 7px; overflow: hidden; border-radius: 5px; font-size: 11px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.platform-badge i { width: 5px; height: 5px; flex: 0 0 5px; border-radius: 50%; background: currentColor; opacity: .8; }
.platform-badge.tone-blue { color: #286cae; background: #edf5ff; }
.platform-badge.tone-violet { color: #7651a8; background: #f5f0fc; }
.platform-badge.tone-amber { color: #98601f; background: #fff5e6; }
.platform-badge.tone-teal { color: #16756c; background: #edf8f6; }
.platform-badge.tone-rose { color: #a24c69; background: #fff0f5; }
.platform-badge.tone-slate { color: #52657d; background: #f1f5f8; }
.account-identity { display: grid; min-width: 0; gap: 4px; }
.account-identity > div { display: flex; min-width: 0; align-items: center; gap: 7px; }
.account-identity strong { overflow: hidden; color: #2d4259; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.account-identity span { overflow: hidden; color: #8b98a8; font: 10px/1.35 ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.account-identity :deep(.el-tag) { height: 18px; flex: 0 0 auto; padding: 0 5px; font-size: 9px; }
.password-cell { display: flex; align-items: center; gap: 4px; min-width: 0; }
.password-value {
  display: block;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: #40546a;
  font: 11px/20px Consolas, "SFMono-Regular", monospace;
  text-overflow: ellipsis;
  user-select: text;
  white-space: nowrap;
}
.password-value.masked { color: #909399; letter-spacing: 2px; white-space: nowrap; }
.password-cell .el-button { flex-shrink: 0; margin-left: 0; padding: 4px; }
.account-run-state { display: grid; gap: 3px; }
.account-run-state > div { display: flex; align-items: center; gap: 6px; }
.account-run-state i { width: 6px; height: 6px; border-radius: 50%; background: #aab3bf; }
.account-run-state strong { color: #657387; font-size: 11px; }
.account-run-state > span { padding-left: 12px; color: #9aa4b0; font-size: 9px; }
.account-run-state.state-running i { background: #35a676; box-shadow: 0 0 0 3px rgba(53, 166, 118, .1); }
.account-run-state.state-running strong { color: #277a56; }
.account-run-state.state-stopping i { background: #d56464; }
.account-run-state.state-stopping strong { color: #a34646; }
.pagination-wrap { display: flex; min-height: 52px; flex: 0 0 auto; align-items: center; justify-content: flex-end; padding: 9px 14px; border-top: 1px solid #e6ebf1; background: #fff; }
@media (max-width: 760px) {
  .directory-header { align-items: flex-start; flex-direction: column; }
  .directory-header__actions { width: 100%; justify-content: space-between; }
  .directory-filters { flex-wrap: wrap; }
  .directory-filters > span { width: 100%; margin-left: 0; }
  .website-filter { flex: 1 1 180px; width: auto; }
  .pagination-wrap { justify-content: flex-start; overflow-x: auto; }
}
</style>
