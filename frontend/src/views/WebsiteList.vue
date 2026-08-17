<template>
  <div class="page-container">
    <section class="platform-directory">
      <header class="directory-header">
        <div>
          <span class="directory-eyebrow">平台接入</span>
          <div class="directory-title-line">
            <h1>交易平台</h1>
            <span>{{ total }} 个</span>
          </div>
          <p>集中维护登录入口、页面识别规则与订单聊天能力。</p>
        </div>
        <el-button type="primary" @click="openDialog()">
          <el-icon><Plus /></el-icon>新增平台
        </el-button>
      </header>

      <div class="directory-filters">
        <el-input
          v-model="keyword"
          class="platform-search"
          placeholder="搜索平台名称"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="category" class="category-filter" placeholder="全部分类" clearable @change="handleSearch">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" plain @click="handleSearch">查询</el-button>
        <el-button :disabled="!keyword && !category" @click="resetFilters">重置</el-button>
      </div>

      <div class="site-grid-viewport" v-loading="loading">
        <div v-if="list.length" class="site-grid">
          <article v-for="w in list" :key="w.id" class="site-card" :class="platformToneClass(w.id)">
            <header class="site-card__header">
              <div class="site-brand">
                <el-avatar :size="34" shape="square" :src="w.icon || undefined">{{ siteInitial(w.name) }}</el-avatar>
                <div>
                  <strong :title="w.name">{{ w.name }}</strong>
                  <span>{{ w.category || '未分类' }} · ID {{ w.id }}</span>
                </div>
              </div>
              <el-tag size="small" effect="plain" :type="tagType(w.login_type)">{{ typeLabel(w.login_type) }}</el-tag>
            </header>
            <div class="site-url">
              <span>登录入口</span>
              <code :title="w.url">{{ displayUrl(w.url) }}</code>
            </div>
            <div class="site-readiness">
              <span :class="{ 'is-ready': loginConfigurationReady(w) }">
                <i></i>{{ loginConfigurationReady(w) ? '登录配置就绪' : '登录配置待补充' }}
              </span>
              <span :class="{ 'is-ready': chatConfigurationReady(w) }">
                <i></i>{{ chatConfigurationReady(w) ? '聊天配置就绪' : '聊天配置待补充' }}
              </span>
            </div>
            <footer class="site-card__footer">
              <span>排序 {{ w.sort_order || 0 }}</span>
              <el-button link type="primary" @click="openDialog(w)">编辑配置</el-button>
            </footer>
          </article>
        </div>
        <el-empty v-else :description="keyword || category ? '没有匹配的平台' : '当前还没有交易平台'" :image-size="84">
          <el-button v-if="!keyword && !category" type="primary" @click="openDialog()">新增第一个平台</el-button>
        </el-empty>
      </div>

      <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[12, 20, 40, 80]"
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑平台' : '新增平台'" width="760px" destroy-on-close top="4vh">
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="平台名称" prop="name">
          <el-input v-model="form.name" placeholder="如：ItemMania" />
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
const pageSize = ref(20)
const keyword = ref('')
const category = ref('')
const categories = ref([])
const loading = ref(false)
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
  name: [{ required: true, message: '请输入平台名称', trigger: 'blur' }],
  url:  [{ required: true, message: '请输入登录URL',  trigger: 'blur' }],
}

function typeLabel(t) {
  return { form: '表单登录', captcha: '验证码', oauth: 'OAuth' }[t] || t
}
function tagType(t) {
  return { form: 'success', captcha: 'warning', oauth: 'info' }[t] || ''
}

function siteInitial(name) {
  return String(name || '?').trim().slice(0, 1).toUpperCase()
}

function displayUrl(value) {
  if (!value) return '未填写'
  try {
    const url = new URL(value)
    return `${url.host}${url.pathname === '/' ? '' : url.pathname}`
  } catch {
    return value
  }
}

function platformToneClass(id) {
  const tones = ['blue', 'violet', 'amber', 'teal', 'rose', 'slate']
  const index = Math.max(0, (Number(id) || 1) - 1) % tones.length
  return `tone-${tones[index]}`
}

function loginConfigurationReady(website) {
  const config = website.login_config || {}
  const baseReady = Boolean(config.username_selector && config.password_selector && config.submit_selector)
  if (website.login_type !== 'captcha') return baseReady
  return baseReady && Boolean(config.captcha_selector && config.captcha_input_selector)
}

function chatConfigurationReady(website) {
  if (String(website.name || '').toLowerCase().includes('itemmania')) return true
  const config = website.login_config?.chat_config || {}
  return Boolean(config.url_template && config.input_selector && config.send_selector)
}

async function fetchList() {
  loading.value = true
  try {
    const res = await getWebsites({ page: page.value, page_size: pageSize.value, keyword: keyword.value.trim(), category: category.value })
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}
async function fetchCategories() {
  categories.value = await getCategories()
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
  keyword.value = ''
  category.value = ''
  handleSearch()
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
.page-container { display: flex; height: 100%; min-height: 0; flex-direction: column; overflow: hidden; padding: 0; }
.platform-directory { display: flex; min-height: 0; flex: 1; flex-direction: column; overflow: hidden; border: 1px solid #dfe6ee; border-radius: 10px; background: #fff; }
.directory-header { display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; gap: 20px; padding: 16px 18px 14px; }
.directory-eyebrow { color: #3d83ca; font-size: 10px; font-weight: 700; letter-spacing: .12em; }
.directory-title-line { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.directory-title-line h1 { margin: 0; color: #23384f; font-size: 21px; line-height: 1.2; }
.directory-title-line > span { padding: 2px 8px; color: #708196; border: 1px solid #dce4ec; border-radius: 999px; background: #f7f9fb; font-size: 11px; }
.directory-header p { margin: 4px 0 0; color: #8491a2; font-size: 12px; }
.directory-filters { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; padding: 8px 12px; border-top: 1px solid #edf1f5; border-bottom: 1px solid #e3e9f0; background: #f8fafc; }
.platform-search { width: 260px; }
.category-filter { width: 150px; }
.site-grid-viewport { min-height: 0; flex: 1; padding: 12px; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.site-card { position: relative; min-width: 0; overflow: hidden; border: 1px solid #e0e6ed; border-radius: 9px; background: #fff; box-shadow: 0 2px 8px rgba(34, 54, 77, .04); transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.site-card::before { position: absolute; top: 0; right: 0; left: 0; height: 3px; content: ''; background: var(--site-accent); }
.site-card:hover { border-color: var(--site-border); box-shadow: 0 8px 22px rgba(34, 54, 77, .1); transform: translateY(-1px); }
.site-card.tone-blue { --site-accent: #4386ce; --site-border: #b9d4ef; }
.site-card.tone-violet { --site-accent: #8b6bc1; --site-border: #d6c8eb; }
.site-card.tone-amber { --site-accent: #ce8a35; --site-border: #ecd3ae; }
.site-card.tone-teal { --site-accent: #319487; --site-border: #b9ded8; }
.site-card.tone-rose { --site-accent: #c76d8a; --site-border: #eac5d2; }
.site-card.tone-slate { --site-accent: #73879e; --site-border: #cdd7e1; }
.site-card__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; padding: 15px 14px 10px; }
.site-brand { display: flex; min-width: 0; align-items: center; gap: 9px; }
.site-brand :deep(.el-avatar) { flex: 0 0 34px; color: #fff; border-radius: 7px; background: var(--site-accent); font-weight: 700; }
.site-brand > div { display: grid; min-width: 0; gap: 2px; }
.site-brand strong { overflow: hidden; color: #2d4259; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.site-brand span { color: #8995a4; font-size: 10px; }
.site-url { display: grid; min-width: 0; gap: 3px; padding: 0 14px 10px; }
.site-url > span { color: #9aa5b2; font-size: 10px; }
.site-url code { overflow: hidden; color: #52677e; font: 11px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.site-readiness { display: flex; align-items: center; gap: 7px; padding: 8px 14px; border-top: 1px solid #eef2f6; border-bottom: 1px solid #eef2f6; background: #fafbfd; }
.site-readiness > span { display: inline-flex; align-items: center; gap: 4px; color: #9a6b32; font-size: 10px; white-space: nowrap; }
.site-readiness i { width: 5px; height: 5px; border-radius: 50%; background: #d69b4f; }
.site-readiness > span.is-ready { color: #34765d; }
.site-readiness > span.is-ready i { background: #42a378; }
.site-card__footer { display: flex; align-items: center; justify-content: space-between; padding: 7px 12px 7px 14px; color: #94a0ae; font-size: 10px; }
.pagination-wrap { display: flex; min-height: 52px; flex: 0 0 auto; align-items: center; justify-content: flex-end; padding: 9px 14px; border-top: 1px solid #e6ebf1; background: #fff; }
.chat-config-tip { margin-bottom: 18px; }
@media (max-width: 760px) {
  .directory-header { align-items: flex-start; flex-direction: column; }
  .directory-filters { align-items: stretch; flex-wrap: wrap; }
  .platform-search { flex: 1 1 100%; width: 100%; }
  .category-filter { flex: 1 1 160px; width: auto; }
  .site-grid { grid-template-columns: 1fr; }
  .pagination-wrap { justify-content: flex-start; overflow-x: auto; }
}
@media (prefers-reduced-motion: reduce) { .site-card { transition: none; } }
</style>
