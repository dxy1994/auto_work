<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索网站名称..."
        clearable
        style="width: 240px"
        @input="handleSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-select v-model="category" placeholder="全部分类" clearable style="width: 140px" @change="handleSearch">
        <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
      </el-select>

      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon> 新增网站
      </el-button>
    </div>

    <el-row :gutter="16">
      <el-col v-for="w in list" :key="w.id" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card shadow="hover" class="site-card">
          <template #header>
            <div class="card-header">
              <span class="site-name">{{ w.name }}</span>
              <el-tag size="small" :type="tagType(w.login_type)">{{ typeLabel(w.login_type) }}</el-tag>
            </div>
          </template>
          <div class="site-url" :title="w.url">{{ w.url }}</div>
          <div class="site-meta">
            <el-tag v-if="w.category" size="small" type="info">{{ w.category }}</el-tag>
            <span class="sort-badge" v-if="w.sort_order">排序: {{ w.sort_order }}</span>
          </div>
          <div class="card-actions">
            <el-button size="small" @click="openDialog(w)">编辑</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!list.length" description="暂无网站，请先添加" />

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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑网站' : '新增网站'" width="760px" destroy-on-close top="4vh">
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="网站名称" prop="name">
          <el-input v-model="form.name" placeholder="如：GitHub" />
        </el-form-item>
        <el-form-item label="登录URL" prop="url">
          <el-input v-model="form.url" placeholder="https://github.com/login" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="办公/社交/开发" />
        </el-form-item>
        <el-form-item label="登录类型">
          <el-select v-model="form.login_type" style="width:100%">
            <el-option label="表单登录" value="form" />
            <el-option label="需要验证码" value="captcha" />
          </el-select>
        </el-form-item>
        <el-form-item label="图标URL">
          <el-input v-model="form.icon" placeholder="可选" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" rows="2" />
        </el-form-item>

        <el-divider>登录选择器配置（CSS Selector）</el-divider>
        <el-form-item label="用户名选择器">
          <el-input v-model="loginCfg.username_selector" placeholder="#username" />
        </el-form-item>
        <el-form-item label="密码选择器">
          <el-input v-model="loginCfg.password_selector" placeholder="#password" />
        </el-form-item>
        <el-form-item label="提交按钮选择器">
          <el-input v-model="loginCfg.submit_selector" placeholder="button[type='submit']" />
        </el-form-item>
        <el-form-item label="成功URL(可选)">
          <el-input v-model="loginCfg.success_url" placeholder="/dashboard" />
        </el-form-item>
        <template v-if="form.login_type === 'captcha'">
          <el-form-item label="验证码图片选择器">
            <el-input v-model="loginCfg.captcha_selector" placeholder=".captcha-img" />
          </el-form-item>
          <el-form-item label="验证码输入选择器">
            <el-input v-model="loginCfg.captcha_input_selector" placeholder="#captcha-input" />
          </el-form-item>
        </template>

        <el-divider>订单聊天配置</el-divider>
        <el-alert
          type="info"
          :closable="false"
          class="chat-config-tip"
          title="聊天地址必须包含 {order_no}；ItemMania 可留空使用内置配置，其他平台需按实际页面填写。"
        />
        <el-form-item label="聊天地址模板">
          <el-input
            v-model="chatCfg.url_template"
            placeholder="https://example.com/chat?order={order_no}"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="输入框选择器">
              <el-input v-model="chatCfg.input_selector" placeholder="#chat-input" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发送按钮选择器">
              <el-input v-model="chatCfg.send_selector" placeholder="#send-button" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="图片控件选择器">
          <el-input v-model="chatCfg.file_selector" placeholder="input[type='file']" />
        </el-form-item>
        <el-form-item label="上传即发送">
          <el-switch
            v-model="chatCfg.upload_auto_send"
            active-text="是"
            inactive-text="否，需点击发送"
          />
        </el-form-item>
        <el-form-item v-if="!chatCfg.upload_auto_send" label="图片发送选择器">
          <el-input v-model="chatCfg.upload_send_selector" placeholder=".upload-confirm" />
        </el-form-item>
        <el-form-item label="上传层关闭选择器">
          <el-input v-model="chatCfg.upload_close_selector" placeholder="可选，如 .upload-dialog .close" />
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
import { getWebsites, createWebsite, updateWebsite, deleteWebsite, getCategories } from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const category = ref('')
const categories = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)

const defaultForm = () => ({
  name: '', url: '', icon: '', category: '', login_type: 'form',
  remark: '', sort_order: 0,
})
const defaultLoginCfg = () => ({
  username_selector: '', password_selector: '', submit_selector: '',
  success_url: '', captcha_selector: '', captcha_input_selector: '',
})
const defaultChatCfg = () => ({
  url_template: '',
  input_selector: '',
  send_selector: '',
  file_selector: '',
  upload_auto_send: true,
  upload_send_selector: '',
  upload_close_selector: '',
})

const form = reactive(defaultForm())
const loginCfg = reactive(defaultLoginCfg())
const chatCfg = reactive(defaultChatCfg())

const rules = {
  name: [{ required: true, message: '请输入网站名称', trigger: 'blur' }],
  url:  [{ required: true, message: '请输入登录URL',  trigger: 'blur' }],
}

function typeLabel(t) {
  return { form: '表单登录', captcha: '验证码', oauth: 'OAuth' }[t] || t
}
function tagType(t) {
  return { form: 'success', captcha: 'warning', oauth: 'info' }[t] || ''
}

async function fetchList() {
  const res = await getWebsites({ page: page.value, page_size: pageSize, keyword: keyword.value, category: category.value })
  list.value = res.items
  total.value = res.total
}
async function fetchCategories() {
  categories.value = await getCategories()
}
function handleSearch() {
  page.value = 1
  fetchList()
}

function openDialog(w = null) {
  isEdit.value = !!w
  editId.value = w?.id ?? null
  Object.assign(form, w ? { ...w } : defaultForm())
  const savedLoginCfg = w?.login_config || {}
  const { chat_config: savedChatCfg, ...plainLoginCfg } = savedLoginCfg
  Object.assign(loginCfg, defaultLoginCfg(), plainLoginCfg)
  Object.assign(chatCfg, defaultChatCfg(), savedChatCfg || {})
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const data = {
      ...form,
      login_config: {
        ...loginCfg,
        chat_config: { ...chatCfg },
      },
    }
    if (isEdit.value) {
      await updateWebsite(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createWebsite(data)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchList()
    fetchCategories()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchList()
  fetchCategories()
})
</script>

<style scoped>
.page-container { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.toolbar .el-button { margin-left: auto; }
.site-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.site-name { font-weight: 600; font-size: 15px; }
.site-url { color: #606266; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 8px; }
.site-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.sort-badge { font-size: 12px; color: #909399; }
.card-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
.chat-config-tip { margin-bottom: 18px; }
</style>
