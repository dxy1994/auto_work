<template>
  <div class="page-container">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <el-select v-model="filterWebsite" placeholder="全部网站" clearable style="width: 200px" @change="handleSearch">
        <el-option v-for="w in allWebsites" :key="w.id" :label="w.name" :value="w.id" />
      </el-select>
      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon> 新增账号
      </el-button>
    </div>

    <!-- 账号表格 -->
    <el-table :data="list" border stripe highlight-current-row @current-change="onCurrentChange" row-key="id" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="所属网站" min-width="120">
        <template #default="{ row }">
          {{ websiteName(row.website_id) }}
        </template>
      </el-table-column>
      <el-table-column prop="label" label="账号标签" min-width="120" />
      <el-table-column prop="username" label="用户名" min-width="150" />
      <el-table-column label="密码" min-width="210">
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
      <el-table-column label="默认" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="订单检查状态" width="120" align="center">
        <template #default="{ row }">
          <template v-if="getCheckStatus(row.id) === 'running'">
            <el-tag type="warning" size="small">
              <el-icon class="is-loading"><Loading /></el-icon> 监控中
            </el-tag>
          </template>
          <template v-else-if="getCheckStatus(row.id) === 'stopping'">
            <el-tag type="danger" size="small">终止中...</el-tag>
          </template>
          <template v-else>
            <span style="color:#909399;font-size:12px">未运行</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320" align="center">
        <template #default="{ row }">
          <template v-if="getCheckStatus(row.id) === 'running' || getCheckStatus(row.id) === 'stopping'">
            <el-button size="small" type="danger" :loading="cancellingId === row.id" @click="handleCancelCheck(row)">
              终止查询
            </el-button>
          </template>
          <template v-else>
            <el-button size="small" type="info" :loading="orderCheckingId === row.id" @click="handleOrderCheck(row)">
              订单查询
            </el-button>
          </template>
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!list.length" description="暂无账号" />

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchList"
      />
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑账号' : '新增账号'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="90px" ref="formRef" :rules="rules">
        <el-form-item label="所属网站" prop="website_id">
          <el-select v-model="form.website_id" placeholder="选择网站" style="width:100%">
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
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAccounts, getAccountPassword, createAccount, updateAccount, deleteAccount,
  getAllWebsites, orderCheck, getOrderCheckStatus, cancelOrderCheck,
} from '../api'

const allWebsites = ref([])
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filterWebsite = ref(null)
const dialogVisible = ref(false)
const submitting = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const revealedPasswords = ref({})
const passwordLoading = reactive({})

const orderCheckingId = ref(null)
const cancellingId = ref(null)

// 订单检查状态轮询
const orderCheckStatuses = ref({})  // { accountId: { status, message, start_time } }
let statusPollTimer = null
const STATUS_REFRESH_INTERVAL_MS = 5000

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

function getCheckStatus(accountId) {
  const s = orderCheckStatuses.value[accountId]
  return s ? s.status : 'idle'
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
  website_id: [{ required: true, message: '请选择网站', trigger: 'change' }],
  label:      [{ required: true, message: '请输入标签', trigger: 'blur' }],
  username:   [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password:   [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function websiteName(id) {
  return allWebsites.value.find(w => w.id === id)?.name || id
}

async function fetchList() {
  clearRevealedPasswords()
  const params = { page: page.value, page_size: pageSize }
  if (filterWebsite.value) params.website_id = filterWebsite.value
  const res = await getAccounts(params)
  list.value = res.items
  total.value = res.total
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
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.toolbar .el-button { margin-left: auto; }
.password-cell { display: flex; align-items: center; gap: 4px; min-width: 0; }
.password-value {
  display: block;
  flex: 1;
  min-width: 0;
  color: #303133;
  font-family: Consolas, "SFMono-Regular", monospace;
  line-height: 20px;
  overflow-wrap: anywhere;
  user-select: text;
  white-space: normal;
  word-break: break-all;
}
.password-value.masked { color: #909399; letter-spacing: 2px; white-space: nowrap; }
.password-cell .el-button { flex-shrink: 0; margin-left: 0; padding: 4px; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
</style>
