<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span style="font-weight:600; font-size:16px">快速登录</span>
      </template>

      <el-form label-width="90px" style="max-width: 500px">
        <el-form-item label="选择网站">
          <el-select v-model="selectedWebsite" placeholder="请选择网站" style="width:100%" @change="onWebsiteChange">
            <el-option v-for="w in allWebsites" :key="w.id" :label="w.name" :value="w.id">
              <el-tag v-if="w.category" size="small" type="info" style="float:right">{{ w.category }}</el-tag>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="选择账号">
          <el-select v-model="selectedAccount" placeholder="请选择账号" style="width:100%" :disabled="!selectedWebsite">
            <el-option v-for="a in accountList" :key="a.id" :label="`${a.label} - ${a.username}`" :value="a.id">
              <el-tag v-if="a.is_default" size="small" type="success" style="margin-left:8px">默认</el-tag>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="logging"
            :disabled="!selectedWebsite || !selectedAccount"
            @click="handleLogin"
          >
            <el-icon><Promotion /></el-icon>&nbsp; 开始登录
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 登录结果 -->
      <el-result
        v-if="loginResult"
        :icon="resultIcon"
        :title="loginResult.status === 'success' ? '登录成功' : '登录失败'"
        :sub-title="loginResult.message"
      >
        <template #extra>
          <span v-if="loginResult.duration_ms" style="color:#909399;font-size:13px">
            耗时: {{ loginResult.duration_ms }}ms
          </span>
        </template>
      </el-result>
    </el-card>

    <!-- 登录日志 -->
    <el-card style="margin-top:20px">
      <template #header><span style="font-weight:600">最近登录日志</span></template>
      <el-table :data="logs" border stripe size="small">
        <el-table-column label="网站" width="120">
          <template #default="{ row }">{{ websiteName(row.website_id) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="信息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="duration_ms" label="耗时(ms)" width="100" align="center" />
        <el-table-column prop="created_at" label="时间" width="170" />
      </el-table>
      <el-empty v-if="!logs.length" description="暂无日志" />
    </el-card>

    <!-- 验证码弹窗 -->
    <CaptchaDialog v-model:visible="captchaVisible" :task-id="currentTaskId" @submit="onCaptchaSubmit" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllWebsites, getAccounts, triggerLogin, getLoginLogs } from '../api'
import CaptchaDialog from '../components/CaptchaDialog.vue'

const allWebsites = ref([])
const accountList = ref([])
const selectedWebsite = ref(null)
const selectedAccount = ref(null)
const logging = ref(false)
const loginResult = ref(null)
const logs = ref([])
const captchaVisible = ref(false)
const currentTaskId = ref('')
let manualLoginWs = null  // 手动登录 WebSocket 连接

const resultIcon = computed(() =>
  loginResult.value?.status === 'success' ? 'success' : 'error'
)

function websiteName(id) {
  return allWebsites.value.find(w => w.id === id)?.name || id
}
function statusType(s) {
  return { success: 'success', failed: 'danger', captcha_required: 'warning', timeout: 'info' }[s] || 'info'
}
function statusLabel(s) {
  return { success: '成功', failed: '失败', captcha_required: '需要验证码', timeout: '超时' }[s] || s
}

async function fetchWebsites() {
  allWebsites.value = await getAllWebsites()
}

async function onWebsiteChange() {
  selectedAccount.value = null
  if (!selectedWebsite.value) {
    accountList.value = []
    return
  }
  const res = await getAccounts({ website_id: selectedWebsite.value, page_size: 100 })
  accountList.value = res.items
  // 自动选择默认账号
  const def = accountList.value.find(a => a.is_default)
  if (def) selectedAccount.value = def.id
}

function getLoginType() {
  if (!selectedWebsite.value) return 'form'
  const website = allWebsites.value.find(w => w.id === selectedWebsite.value)
  return website?.login_type || 'form'
}

async function handleLogin() {
  logging.value = true
  loginResult.value = null

  const loginType = getLoginType()
  const taskId = `${selectedWebsite.value}_${selectedAccount.value}_${Date.now()}`
  currentTaskId.value = taskId

  try {
    // captcha 类型：先生成 task_id 并建立 WebSocket 接收实时通知
    if (loginType === 'captcha') {
      connectManualLoginWs(taskId)
    }

    const res = await triggerLogin(selectedWebsite.value, selectedAccount.value, loginType === 'captcha' ? taskId : null)
    loginResult.value = res

    if (res.status === 'success') {
      ElMessage.success('登录成功！')
    } else if (res.status === 'captcha_required') {
      captchaVisible.value = true
    } else {
      ElMessage.warning(res.message || '登录失败')
    }
    fetchLogs()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    logging.value = false
    // captcha 手动登录 WebSocket 在收到最终结果后关闭
    if (loginType !== 'captcha' || loginResult.value) {
      closeManualLoginWs()
    }
  }
}

function connectManualLoginWs(taskId) {
  closeManualLoginWs()
  const wsUrl = `ws://${window.location.host}/api/automation/ws/captcha/${taskId}`
  manualLoginWs = new WebSocket(wsUrl)
  manualLoginWs.onopen = () => {
    console.log('[ManualLogin] WebSocket 已连接')
  }
  manualLoginWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'manual_login_ready') {
        ElMessage.info('表单已填充，请在浏览器中手动完成验证码并登录')
      } else if (msg.type === 'login_success') {
        ElMessage.success(msg.message || '登录成功！')
        loginResult.value = { status: 'success', message: msg.message }
        closeManualLoginWs()
      } else if (msg.type === 'login_timeout') {
        ElMessage.warning(msg.message || '手动登录超时')
        loginResult.value = { status: 'timeout', message: msg.message }
        closeManualLoginWs()
      } else if (msg.type === 'login_failed') {
        ElMessage.error(msg.message || '登录失败')
        loginResult.value = { status: 'failed', message: msg.message }
        closeManualLoginWs()
      }
    } catch (e) {
      console.error('[ManualLogin] WebSocket 消息解析失败:', e)
    }
  }
  manualLoginWs.onerror = () => {
    console.error('[ManualLogin] WebSocket 连接错误')
  }
  manualLoginWs.onclose = () => {
    console.log('[ManualLogin] WebSocket 已关闭')
  }
}

function closeManualLoginWs() {
  if (manualLoginWs) {
    manualLoginWs.close()
    manualLoginWs = null
  }
}

function onCaptchaSubmit() {
  // 验证码提交后，后端会继续执行登录流程
  // 实际的登录结果需要轮询或通过 WebSocket 通知
  ElMessage.info('验证码已提交，请等待登录完成')
}

async function fetchLogs() {
  logs.value = await getLoginLogs({ limit: 20 })
}

onMounted(() => {
  fetchWebsites()
  fetchLogs()
})
</script>

<style scoped>
.page-container { padding: 0; }
</style>
