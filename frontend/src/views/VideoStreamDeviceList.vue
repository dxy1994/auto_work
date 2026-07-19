<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索设备名称..." clearable style="width: 220px" @input="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon> 新增设备
      </el-button>
    </div>

    <el-table :data="list" border stripe v-loading="loading" row-key="id">
      <el-table-column prop="id" label="ID" width="70" align="center" />
      <el-table-column prop="name" label="设备名称" min-width="150" />
      <el-table-column prop="device_type" label="设备类型" width="120" />
      <el-table-column prop="device_info" label="设备信息" min-width="200" show-overflow-tooltip />
      <el-table-column prop="machine_name" label="关联机器" width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.machine_name || '未关联' }}</template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确认删除？" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchList" />
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑视频流设备' : '新增视频流设备'" width="500px" destroy-on-close>
      <el-form :model="form" label-width="80px" ref="formRef" :rules="rules">
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="如：海康 DS-01" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="form.device_type" placeholder="选择设备类型" clearable filterable allow-create style="width:100%">
            <el-option label="RTSP" value="RTSP" />
            <el-option label="USB摄像头" value="USB摄像头" />
            <el-option label="HDMI采集卡" value="HDMI采集卡" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备信息" prop="device_info">
          <el-input v-model="form.device_info" type="textarea" rows="3" placeholder="设备详细信息，如流地址..." />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" rows="2" placeholder="备注信息..." />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getVsDevices, createVsDevice, updateVsDevice, deleteVsDevice } from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const loading = ref(false)

async function fetchList() {
  loading.value = true
  try {
    const res = await getVsDevices({ page: page.value, page_size: pageSize, keyword: keyword.value })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() { page.value = 1; fetchList() }

// ── 编辑 ──
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const rules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择或输入设备类型', trigger: 'blur' }],
  device_info: [{ required: true, message: '请输入设备信息', trigger: 'blur' }],
}

const defaultForm = () => ({ name: '', device_type: '', device_info: '', remark: '', is_active: 1 })
const form = reactive(defaultForm())

function openDialog(row = null) {
  isEdit.value = !!row
  editId.value = row?.id ?? null
  Object.assign(form, row ? { ...row } : defaultForm())
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateVsDevice(editId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createVsDevice({ ...form })
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
  try {
    await deleteVsDevice(id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(fetchList)
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.toolbar .el-button { margin-left: auto; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
</style>
