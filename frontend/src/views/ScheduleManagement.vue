<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索账号标签/用户名..."
        clearable
        style="width: 240px"
        @input="handleSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-select v-model="scheduleTypeFilter" placeholder="定时类型" clearable style="width: 140px" @change="handleSearch">
        <el-option label="不执行" value="none" />
        <el-option label="仅执行一次" value="once" />
        <el-option label="周期执行" value="scheduled" />
      </el-select>

      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon> 新增配置
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="account_label" label="账号标签" min-width="100" />
      <el-table-column prop="account_username" label="用户名" min-width="120" />
      <el-table-column prop="website_name" label="所属网站" min-width="120" />
      <el-table-column prop="website_url" label="网站URL" min-width="200" show-overflow-tooltip />
      <el-table-column prop="name" label="子功能名" width="120" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column label="定时类型" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="scheduleTagType(row.schedule_type)" size="small">
            {{ scheduleTypeLabel(row.schedule_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="执行时间" width="170" align="center">
        <template #default="{ row }">
          <span v-if="row.schedule_type === 'once' && row.schedule_time" class="text-muted">{{ row.schedule_time }}</span>
          <span v-else-if="row.schedule_type === 'scheduled' && row.schedule_cron" class="text-muted">{{ row.schedule_cron }} 秒</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="提醒音频" width="150" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.alert_audio_path" type="success" size="small">已配置</el-tag>
          <span v-else class="text-muted">未配置</span>
        </template>
      </el-table-column>
      <el-table-column label="启用状态" width="100" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="!!row.is_enabled"
            size="small"
            @change="(val) => handleToggleEnabled(row, val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="success" @click="openCopyDialog(row)">复制</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !list.length" description="暂无调度配置" />

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isNew ? '新增调度配置' : '编辑调度配置'" width="520px" destroy-on-close>
      <div v-if="!isNew" class="dialog-info">
        <span class="label">目标账号：</span>
        <span class="value">{{ editTarget?.account_label }} ({{ editTarget?.account_username }})</span>
      </div>
      <el-form-item v-else label="选择账号" label-width="100px" style="margin-bottom: 16px">
        <el-select v-model="selectedAccountId" placeholder="请选择要配置的账号" style="width: 100%" filterable>
          <el-option
            v-for="a in accountList"
            :key="a.id"
            :label="`${a.label} (${a.username}) - ${websiteName(a.website_id)}`"
            :value="a.id"
          />
        </el-select>
      </el-form-item>
      <el-form :model="scheduleForm" label-width="100px">
        <el-form-item label="子功能名" prop="name">
          <el-input v-model="scheduleForm.name" placeholder="请输入子功能名" :disabled="!isNew" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="scheduleForm.code" placeholder="请输入编码" :disabled="!isNew" />
          <div v-if="!isNew" class="form-hint">编码创建后不可修改</div>
        </el-form-item>
        <el-form-item label="定时类型">
          <el-select v-model="scheduleForm.schedule_type" style="width:100%">
            <el-option label="不执行" value="none" />
            <el-option label="仅执行一次" value="once" />
            <el-option label="周期执行" value="scheduled" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行时间" v-if="scheduleForm.schedule_type === 'once'">
          <el-date-picker
            v-model="scheduleForm.schedule_time"
            type="datetime"
            placeholder="选择执行时间"
            style="width:100%"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="执行间隔" v-if="scheduleForm.schedule_type === 'scheduled'">
          <el-input-number v-model="scheduleForm.schedule_cron" :min="1" :max="86400" style="width:100%" />
          <div class="form-hint">单位：秒，如 3600 = 每小时执行一次</div>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="scheduleForm.is_enabled" />
        </el-form-item>
        <el-divider>提醒音频（可选）</el-divider>
        <el-form-item label="上传音频">
          <div class="audio-upload-row">
            <el-upload
              ref="audioUploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".mp3,.wav,.ogg,.flac,.m4a,.wma"
              :on-change="handleAudioFileChange"
              :on-remove="handleAudioFileRemove"
              :file-list="audioFileList"
            >
              <el-button size="small" type="primary">选择音频文件</el-button>
              <template #tip>
                <div class="el-upload__tip">支持 mp3 / wav / ogg / flac，最大 10MB</div>
              </template>
            </el-upload>
            <el-button
              v-if="pendingAudioFile"
              size="small"
              type="success"
              :loading="uploadingAudio"
              @click="handleAudioUpload"
              style="margin-left:8px"
            >
              上传
            </el-button>
          </div>
          <div v-if="scheduleForm.alert_audio_path" class="audio-current">
            <span class="audio-label">当前音频：</span>
            <span class="audio-path">{{ scheduleForm.alert_audio_path }}</span>
            <el-button size="small" type="danger" text @click="handleRemoveAudio">移除</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="scheduleSaving" :disabled="isNew && !selectedAccountId" @click="handleScheduleSave">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- 复制弹窗 -->
    <el-dialog v-model="copyDialogVisible" title="复制配置到其他账号" width="520px" destroy-on-close>
      <div class="dialog-info">
        <span class="label">源账号：</span>
        <span class="value">{{ copyTarget?.account_label }} ({{ copyTarget?.account_username }})</span>
        <span style="margin-left: 12px; color: #909399">
          子功能「{{ copyTarget?.name }}」编码「{{ copyTarget?.code }}」
        </span>
      </div>
      <el-form-item label="目标账号" label-width="90px">
        <el-select
          v-model="copySelectedIds"
          placeholder="请选择目标账号（可多选）"
          style="width: 100%"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
        >
          <el-option
            v-for="a in copyAccountList"
            :key="a.id"
            :label="`${a.label} (${a.username}) - ${websiteName(a.website_id)}`"
            :value="a.id"
          />
        </el-select>
        <div class="form-hint">仅显示尚未配置的账号，编码将自动随机生成</div>
      </el-form-item>
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="copying" :disabled="!copySelectedIds.length" @click="handleCopySubmit">
          确认复制
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllSchedules, getAllWebsites, getAccounts, upsertSchedule, uploadAlertAudio, copySchedule } from '../api'

const list = ref([])
const loading = ref(false)
const keyword = ref('')
const scheduleTypeFilter = ref('')

const dialogVisible = ref(false)
const editTarget = ref(null)
const scheduleSaving = ref(false)
const isNew = ref(false)
const accountList = ref([])
const selectedAccountId = ref(null)
const allWebsites = ref([])

const scheduleForm = reactive({
  name: '',
  code: '',
  refresh_interval: -1,
  schedule_type: 'none',
  schedule_time: null,
  schedule_cron: '',
  alert_audio_path: null,
  is_enabled: true,
})

// 音频上传相关
const audioUploadRef = ref(null)
const pendingAudioFile = ref(null)
const audioFileList = ref([])
const uploadingAudio = ref(false)

// 复制配置相关
const copyDialogVisible = ref(false)
const copyTarget = ref(null)
const copyAccountList = ref([])
const copySelectedIds = ref([])
const copying = ref(false)

function scheduleTypeLabel(t) {
  return { none: '不执行', once: '仅执行一次', scheduled: '周期执行' }[t] || t
}

function scheduleTagType(t) {
  return { none: 'info', once: 'warning', scheduled: 'success' }[t] || ''
}

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (keyword.value) params.keyword = keyword.value
    if (scheduleTypeFilter.value) params.schedule_type = scheduleTypeFilter.value
    list.value = await getAllSchedules(params)
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  fetchList()
}

function websiteName(id) {
  return allWebsites.value.find(w => w.id === id)?.name || ''
}

function openEditDialog(row) {
  isNew.value = false
  editTarget.value = row
  selectedAccountId.value = null
  dialogVisible.value = true
  pendingAudioFile.value = null
  audioFileList.value = []
  Object.assign(scheduleForm, {
    name: row.name || '',
    code: row.code || '',
    refresh_interval: row.refresh_interval,
    schedule_type: row.schedule_type,
    schedule_time: row.schedule_time,
    schedule_cron: row.schedule_cron || '',
    alert_audio_path: row.alert_audio_path || null,
    is_enabled: !!row.is_enabled,
  })
}

function generateCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 8; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return code
}

async function openAddDialog() {
  isNew.value = true
  editTarget.value = null
  selectedAccountId.value = null
  dialogVisible.value = true
  pendingAudioFile.value = null
  audioFileList.value = []
  Object.assign(scheduleForm, {
    name: '',
    code: generateCode(),
    refresh_interval: -1,
    schedule_type: 'none',
    schedule_time: null,
    schedule_cron: '',
    alert_audio_path: null,
    is_enabled: true,
  })
  // 加载所有账号，过滤掉已有配置的
  try {
    const [accountsData, websitesData] = await Promise.all([
      getAccounts({ page_size: 1000 }),
      getAllWebsites(),
    ])
    allWebsites.value = websitesData
    const existingIds = new Set(list.value.map(s => s.account_id))
    accountList.value = accountsData.items.filter(a => !existingIds.has(a.id))
  } catch (e) {
    ElMessage.error('加载账号列表失败: ' + e.message)
  }
}

async function handleScheduleSave() {
  const targetId = isNew.value ? selectedAccountId.value : editTarget.value.account_id
  if (isNew.value && !targetId) return
  scheduleSaving.value = true
  try {
    const data = { ...scheduleForm }
    await upsertSchedule(targetId, data)
    ElMessage.success('定时配置保存成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    scheduleSaving.value = false
  }
}

async function handleToggleEnabled(row, val) {
  try {
    const data = {
      refresh_interval: row.refresh_interval,
      schedule_type: row.schedule_type,
      schedule_time: row.schedule_time,
      schedule_cron: row.schedule_cron || '',
      alert_audio_path: row.alert_audio_path || null,
      is_enabled: val,
    }
    await upsertSchedule(row.account_id, data)
    row.is_enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已停用')
  } catch (e) {
    ElMessage.error('操作失败: ' + e.message)
  }
}

// ── 复制配置 ──
async function openCopyDialog(row) {
  copyTarget.value = row
  copySelectedIds.value = []
  copyDialogVisible.value = true
  // 加载所有账号，过滤掉已有配置的 + 排除源账号自身
  try {
    const [accountsData, websitesData] = await Promise.all([
      getAccounts({ page_size: 1000 }),
      getAllWebsites(),
    ])
    allWebsites.value = websitesData
    const existingIds = new Set(list.value.map(s => s.account_id))
    copyAccountList.value = accountsData.items.filter(
      a => !existingIds.has(a.id) && a.id !== row.account_id
    )
  } catch (e) {
    ElMessage.error('加载账号列表失败: ' + e.message)
  }
}

async function handleCopySubmit() {
  if (!copySelectedIds.value.length) return
  copying.value = true
  try {
    const res = await copySchedule(copyTarget.value.account_id, copySelectedIds.value)
    ElMessage.success(`复制成功：${res.copied_count} 个账号已创建配置` + (res.skipped_count ? `，${res.skipped_count} 个跳过` : ''))
    copyDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('复制失败: ' + e.message)
  } finally {
    copying.value = false
  }
}

// ── 音频上传 ──
function handleAudioFileChange(file) {
  pendingAudioFile.value = file.raw
  audioFileList.value = [file]
}

function handleAudioFileRemove() {
  pendingAudioFile.value = null
  audioFileList.value = []
}

function getCurrentAccountId() {
  return isNew.value ? selectedAccountId.value : editTarget.value?.account_id
}

async function handleAudioUpload() {
  if (!pendingAudioFile.value) return
  const accountId = getCurrentAccountId()
  if (!accountId) return
  uploadingAudio.value = true
  try {
    const res = await uploadAlertAudio(accountId, pendingAudioFile.value)
    scheduleForm.alert_audio_path = res.alert_audio_path
    pendingAudioFile.value = null
    audioFileList.value = []
    ElMessage.success('音频上传成功')
  } catch (e) {
    ElMessage.error('音频上传失败: ' + e.message)
  } finally {
    uploadingAudio.value = false
  }
}

async function handleRemoveAudio() {
  scheduleForm.alert_audio_path = null
  try {
    const data = { ...scheduleForm }
    const accountId = getCurrentAccountId()
    await upsertSchedule(accountId, data)
    ElMessage.success('音频已移除')
  } catch (e) {
    ElMessage.error('移除音频失败: ' + e.message)
  }
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.toolbar .el-button { margin-left: auto; }
.text-muted { color: #909399; font-size: 13px; }
.dialog-info { margin-bottom: 16px; padding: 12px; background: #f5f7fa; border-radius: 6px; }
.dialog-info .label { color: #909399; }
.dialog-info .value { font-weight: 600; }
.form-hint { font-size: 12px; color: #909399; margin-top: 4px; }
.audio-upload-row { display: flex; align-items: center; }
.audio-current { margin-top: 8px; font-size: 13px; color: #606266; display: flex; align-items: center; gap: 6px; }
.audio-current .audio-label { color: #909399; }
.audio-current .audio-path { color: #409eff; word-break: break-all; }
</style>
