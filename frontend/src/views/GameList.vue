<template>
  <div class="page-container">
    <section class="game-directory">
      <header class="game-directory__header">
        <div class="game-directory__intro">
          <span class="game-directory__eyebrow">游戏目录</span>
          <div class="game-directory__title-line">
            <h1>游戏配置</h1>
            <span class="game-directory__count">{{ total }} 款</span>
          </div>
          <p>维护基础信息，并进入对应游戏的大区与话术配置。</p>
        </div>
        <div class="game-directory__actions">
          <el-input v-model="keyword" class="game-search" placeholder="搜索游戏名称" clearable @input="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="openGameDialog()">
            <el-icon><Plus /></el-icon> 新增游戏
          </el-button>
        </div>
      </header>

      <div class="game-table-viewport">
      <el-table
        class="game-table"
        :data="list"
        border
        stripe
        height="100%"
        v-loading="loading"
        highlight-current-row
        @current-change="onCurrentChange"
        row-key="id"
      >
        <el-table-column label="游戏" min-width="250">
          <template #default="{ row }">
            <div class="game-identity">
              <el-avatar :size="42" shape="square" :src="row.icon || undefined" class="game-identity__avatar">
                {{ gameInitial(row.name) }}
              </el-avatar>
              <div class="game-identity__copy">
                <strong>{{ row.name }}</strong>
                <code>{{ row.code }}</code>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="平台" width="92" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="platformTagType(row.platform)">{{ row.platform || '未设置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="交易配置" min-width="150">
          <template #default="{ row }">
            <div class="trade-config">
              <strong>{{ tradeTypeLabel(row.trade_type) }}</strong>
              <span>{{ row.trade_timeout_seconds ?? 600 }} 秒超时</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="68" align="center" />
        <el-table-column label="备注" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="['game-remark', { 'is-empty': !row.remark }]">{{ row.remark || '暂无备注' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="配置与操作" width="262" fixed="right" align="right">
          <template #default="{ row }">
            <div class="game-row-actions">
              <el-button size="small" link type="primary" @click="openGameDialog(row)">
                <el-icon><EditPen /></el-icon> 编辑
              </el-button>
              <el-button size="small" link type="success" @click="openRegionDialog(row)">
                <el-icon><Grid /></el-icon> 大区
              </el-button>
              <el-button size="small" link type="warning" @click="openScriptDrawer(row)">
                <el-icon><ChatDotRound /></el-icon> 话术
              </el-button>
              <el-popconfirm title="确认删除？" @confirm="handleDeleteGame(row.id)">
                <template #reference>
                  <el-button size="small" link type="danger"><el-icon><Delete /></el-icon> 删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="keyword ? '没有匹配的游戏' : '还没有游戏，点击右上角新增'" :image-size="80" />
        </template>
      </el-table>
      </div>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="fetchList" />
      </div>
    </section>

    <!-- 游戏编辑弹窗 -->
    <el-dialog v-model="gameDialogVisible" :title="gameIsEdit ? '编辑游戏' : '新增游戏'" width="500px" destroy-on-close>
      <el-form :model="gameForm" label-width="80px" ref="gameFormRef" :rules="gameRules">
        <el-form-item label="游戏名称" prop="name">
          <el-input v-model="gameForm.name" placeholder="如：DNF" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="gameForm.code" placeholder="唯一编码，如 dnf" :disabled="gameIsEdit" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="gameForm.platform" placeholder="选择平台" clearable style="width:100%">
            <el-option label="PC" value="PC" />
            <el-option label="手游" value="手游" />
            <el-option label="主机" value="主机" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易执行">
          <el-select v-model="gameForm.trade_type" placeholder="选择交易执行方式" style="width:100%">
            <el-option label="脚本" value="script" />
            <el-option label="Web" value="web" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易超时">
          <el-input-number
            v-model="gameForm.trade_timeout_seconds"
            :min="30"
            :max="7200"
            :step="30"
            controls-position="right"
          />
          <span style="margin-left:8px;color:#909399">秒（等待买家交易申请）</span>
        </el-form-item>
        <el-form-item label="游戏图标">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleGameIconChange"
            :on-remove="handleGameIconRemove"
            :file-list="gameIconFileList"
            list-type="picture"
          >
            <el-button size="small" type="primary">选择图片</el-button>
            <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
          </el-upload>
          <el-input v-if="gameForm.icon" v-model="gameForm.icon" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="gameForm.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="gameForm.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="gameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleGameSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 大区管理抽屉 -->
    <el-drawer v-model="regionDrawerVisible" :title="`大区管理 - ${currentGame?.name || ''}`" size="680px" destroy-on-close>
      <div class="region-toolbar">
        <el-button type="primary" size="small" @click="openRegionEdit()">
          <el-icon><Plus /></el-icon> 新增大区
        </el-button>
      </div>
      <el-table :data="regionList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="大区名称" min-width="150" />
        <el-table-column prop="select_page" label="页码" width="65" align="center" />
        <el-table-column label="选区坐标" width="100" align="center">
          <template #default="{ row }">
            {{ row.select_x != null && row.select_y != null ? `${row.select_x}, ${row.select_y}` : '未配置' }}
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="70" align="center" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openRegionEdit(row)">编辑</el-button>
            <el-button size="small" link type="success" @click="openRegionScriptEntry(row)">话术</el-button>
            <el-popconfirm title="确认删除？" @confirm="handleDeleteRegion(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 大区编辑弹窗 -->
      <el-dialog v-model="regionEditVisible" :title="regionIsEdit ? '编辑大区' : '新增大区'" width="520px" append-to-body destroy-on-close>
        <el-form :model="regionForm" label-width="80px" ref="regionFormRef" :rules="regionRules">
          <el-form-item label="大区名称" prop="name">
            <el-input v-model="regionForm.name" placeholder="如：华东一区" />
          </el-form-item>
          <el-form-item label="编码" prop="code">
            <el-input v-model="regionForm.code" placeholder="如 huadong_1" />
          </el-form-item>
          <el-form-item label="所在页码" prop="select_page">
            <el-input-number v-model="regionForm.select_page" :min="1" :max="999" :step="1" step-strictly />
          </el-form-item>
          <el-form-item label="选区坐标">
            <div class="coordinate-inputs">
              <el-form-item prop="select_x">
                <el-input-number v-model="regionForm.select_x" :min="0" :max="1279" :step="1" placeholder="X" />
              </el-form-item>
              <span>×</span>
              <el-form-item prop="select_y">
                <el-input-number v-model="regionForm.select_y" :min="0" :max="959" :step="1" placeholder="Y" />
              </el-form-item>
            </div>
          </el-form-item>
          <el-alert title="坐标按 1280×960 游戏客户区填写；页码从 1 开始，工作机会先进入对应页，再使用配置坐标或 OCR 选择大区" type="info" :closable="false" show-icon />
          <el-form-item v-if="regionIsEdit" label="排序">
            <el-input-number v-model="regionForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="regionEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="regionSubmitting" @click="handleRegionSubmit">保存</el-button>
        </template>
      </el-dialog>
    </el-drawer>

    <!-- 话术管理抽屉（游戏话术 + 大区话术联动） -->
    <el-drawer
      v-model="scriptDrawerVisible"
      :title="`话术管理 - ${scriptGame?.name || ''}`"
      size="min(980px, 94vw)"
      destroy-on-close
    >
      <el-tabs v-model="scriptActiveTab" @tab-change="handleScriptTabChange">
        <!-- 游戏默认话术 -->
        <el-tab-pane label="游戏默认话术" name="game">
          <div class="region-toolbar">
            <el-button type="primary" size="small" @click="openScriptEdit()">
              <el-icon><Plus /></el-icon> 新增话术
            </el-button>
          </div>
          <el-table :data="gameScriptList" border stripe size="small" highlight-current-row @current-change="onCurrentChange" row-key="id">
            <el-table-column prop="title" label="标题" min-width="140" />
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
            <el-table-column label="图片" width="70">
              <template #default="{ row }">
                <el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" style="width:36px;height:36px" fit="cover" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="60" align="center" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openScriptEdit(row)">编辑</el-button>
                <el-popconfirm title="确认删除？" @confirm="handleDeleteScript(row.id)">
                  <template #reference><el-button size="small" link type="danger">删除</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 大区话术 -->
        <el-tab-pane label="大区话术" name="region">
          <div class="region-script-workspace">
            <aside class="region-script-sidebar" aria-label="大区列表">
              <div class="region-script-sidebar__heading">
                <div>
                  <span>大区目录</span>
                  <small>点击直接切换话术</small>
                </div>
                <strong>{{ regionList.length }}</strong>
              </div>

              <div v-if="regionList.length" class="region-script-nav">
                <button
                  v-for="region in regionList"
                  :key="region.id"
                  type="button"
                  class="region-script-nav__item"
                  :class="{ 'is-active': scriptRegionId === region.id }"
                  :aria-pressed="scriptRegionId === region.id"
                  @click="selectScriptRegion(region)"
                >
                  <span class="region-script-nav__copy">
                    <strong>{{ region.name }}</strong>
                    <code>{{ region.code || `ID ${region.id}` }}</code>
                  </span>
                  <span class="region-script-nav__arrow" aria-hidden="true">›</span>
                </button>
              </div>
              <el-empty v-else description="当前游戏暂无大区" :image-size="54" />
            </aside>

            <section class="region-script-content">
              <div v-if="activeScriptRegion" class="region-script-content__heading">
                <div>
                  <span class="region-script-eyebrow">当前大区</span>
                  <div class="region-script-title-line">
                    <h3>{{ activeScriptRegion.name }}</h3>
                    <code>{{ activeScriptRegion.code || `ID ${activeScriptRegion.id}` }}</code>
                    <el-tag size="small" effect="plain">{{ regionScriptList.length }} 条话术</el-tag>
                  </div>
                  <p>左侧切换大区，右侧立即显示该大区的专属话术。</p>
                </div>
                <el-button type="primary" size="small" @click="openRegionScriptEdit()">
                  <el-icon><Plus /></el-icon> 新增大区话术
                </el-button>
              </div>

              <div v-if="regionScriptLoading" class="region-script-loading">
                <el-skeleton :rows="6" animated />
              </div>
              <el-empty
                v-else-if="!activeScriptRegion"
                :description="regionList.length ? '请选择左侧大区查看话术' : '请先在大区管理中添加大区'"
                :image-size="96"
                class="region-script-empty"
              />
              <el-empty
                v-else-if="!regionScriptList.length"
                description="该大区还没有专属话术"
                :image-size="96"
                class="region-script-empty"
              >
                <el-button type="primary" size="small" @click="openRegionScriptEdit()">新增第一条话术</el-button>
              </el-empty>
              <el-table
                v-else
                :data="regionScriptList"
                border
                stripe
                size="small"
                highlight-current-row
                @current-change="onCurrentChange"
                row-key="id"
              >
                <el-table-column prop="title" label="标题" min-width="130" />
                <el-table-column prop="category" label="分类" width="90" />
                <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
                <el-table-column label="图片" width="72">
                  <template #default="{ row }">
                    <el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" style="width:40px;height:40px" fit="cover" />
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="184">
                  <template #default="{ row }">
                    <el-button size="small" link type="primary" @click="openRegionScriptEdit(row)">编辑</el-button>
                    <el-button size="small" link type="success" @click="copyRegionScript(row)">复制</el-button>
                    <el-popconfirm title="确认删除？" @confirm="handleDeleteRegionScript(row.id)">
                      <template #reference><el-button size="small" link type="danger">删除</el-button></template>
                    </el-popconfirm>
                  </template>
                </el-table-column>
              </el-table>
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 游戏话术编辑弹窗 -->
      <el-dialog
        v-model="scriptEditVisible"
        :title="scriptIsEdit ? '编辑话术' : '新增话术'"
        width="min(560px, calc(100vw - 32px))"
        class="script-editor-dialog"
        append-to-body
        destroy-on-close
      >
        <el-form
          ref="scriptFormRef"
          class="script-editor-form"
          :model="scriptForm"
          :rules="scriptRules"
          label-width="112px"
        >
          <el-form-item label="标题" prop="title">
            <el-input v-model="scriptForm.title" />
          </el-form-item>
          <el-form-item label="分类" prop="category">
            <el-select v-model="scriptForm.category" placeholder="请选择分类" clearable filterable allow-create style="width:100%">
              <el-option label="招呼" value="招呼" />
              <el-option label="确认" value="确认" />
              <el-option label="交易完成" value="交易完成" />
              <el-option label="促单" value="促单" />
              <el-option label="售后" value="售后" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容" prop="content">
            <el-input v-model="scriptForm.content" type="textarea" :rows="4" placeholder="话术内容..." />
          </el-form-item>
          <el-form-item label="图片">
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :on-change="handleScriptImageChange"
              :on-remove="handleScriptImageRemove"
              :file-list="scriptImageFileList"
              list-type="picture"
            >
              <el-button size="small" type="primary">选择图片</el-button>
              <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
            </el-upload>
            <el-input v-if="scriptForm.image_url" v-model="scriptForm.image_url" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="scriptForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scriptEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="scriptSubmitting" @click="handleScriptSubmit">保存</el-button>
        </template>
      </el-dialog>

      <!-- 大区话术编辑弹窗 -->
      <el-dialog
        v-model="regionScriptEditVisible"
        :title="regionScriptIsEdit ? '编辑大区话术' : '新增大区话术'"
        width="min(560px, calc(100vw - 32px))"
        class="script-editor-dialog"
        append-to-body
        destroy-on-close
      >
        <div v-if="activeScriptRegion" class="script-editor-context">
          <span>当前大区</span>
          <strong>{{ activeScriptRegion.name }}</strong>
          <code>{{ activeScriptRegion.code || `ID ${activeScriptRegion.id}` }}</code>
        </div>
        <el-form
          ref="regionScriptFormRef"
          class="script-editor-form"
          :model="regionScriptForm"
          :rules="regionScriptRules"
          label-width="112px"
        >
          <el-form-item label="标题" prop="title">
            <el-input v-model="regionScriptForm.title" />
          </el-form-item>
          <el-form-item label="关联游戏话术">
            <el-select v-model="regionScriptForm.game_script_id" placeholder="可选，继承默认话术" clearable style="width:100%">
              <el-option v-for="s in gameScriptList" :key="s.id" :label="s.title" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="分类" prop="category">
            <el-select v-model="regionScriptForm.category" placeholder="请选择分类" clearable filterable allow-create style="width:100%">
              <el-option label="招呼" value="招呼" />
              <el-option label="确认" value="确认" />
              <el-option label="交易完成" value="交易完成" />
              <el-option label="促单" value="促单" />
              <el-option label="售后" value="售后" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容" prop="content">
            <el-input v-model="regionScriptForm.content" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="图片">
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :on-change="handleRegionScriptImageChange"
              :on-remove="handleRegionScriptImageRemove"
              :file-list="regionScriptImageFileList"
              list-type="picture"
            >
              <el-button size="small" type="primary">选择图片</el-button>
              <template #tip><div class="el-upload__tip">支持 jpg/png/gif/webp</div></template>
            </el-upload>
            <el-input v-if="regionScriptForm.image_url" v-model="regionScriptForm.image_url" placeholder="或直接输入URL" size="small" style="margin-top:6px" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="regionScriptForm.sort_order" :min="0" :max="999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="regionScriptEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="regionScriptSubmitting" @click="handleRegionScriptSubmit">保存</el-button>
        </template>
      </el-dialog>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getGames, getGame, createGame, updateGame, deleteGame, getGameRegions, createRegion, updateRegion, deleteRegion, getGameScripts, getAllGameScripts, createGameScript, updateGameScript, deleteGameScript, getRegionScripts, createRegionScript, updateRegionScript, deleteRegionScript, uploadFile } from '../api'

const route = useRoute()
const router = useRouter()

// ── 游戏列表 ──
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const loading = ref(false)

const currentRow = ref(null)
function onCurrentChange(row) { currentRow.value = row }

async function fetchList() {
  loading.value = true
  try {
    const res = await getGames({ page: page.value, page_size: pageSize, keyword: keyword.value })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() { page.value = 1; fetchList() }

function gameInitial(name) {
  return String(name || '?').trim().slice(0, 1).toUpperCase()
}

function tradeTypeLabel(value) {
  return value === 'web' ? 'Web' : '脚本'
}

function platformTagType(platform) {
  return { '手游': 'success', '主机': 'warning' }[platform] || 'info'
}

// ── 游戏编辑 ──
const gameDialogVisible = ref(false)
const gameIsEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const gameFormRef = ref(null)
const gameRules = {
  name: [{ required: true, message: '请输入游戏名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
}

const defaultGameForm = () => ({
  name: '', code: '', platform: '', trade_type: 'script',
  trade_timeout_seconds: 600, icon: '', sort_order: 0, remark: '',
})
const gameForm = reactive(defaultGameForm())

// 游戏图标上传
const gameIconFileList = ref([])
const gameIconFile = ref(null)

function handleGameIconChange(file) {
  gameIconFile.value = file.raw
  gameIconFileList.value = [file]
}

function handleGameIconRemove() {
  gameIconFile.value = null
  gameIconFileList.value = []
  gameForm.icon = ''
}

function openGameDialog(row = null) {
  gameIsEdit.value = !!row
  editId.value = row?.id ?? null
  gameIconFile.value = null
  if (row?.icon) {
    gameIconFileList.value = [{ name: row.icon.split('/').pop() || 'icon.png', url: row.icon }]
  } else {
    gameIconFileList.value = []
  }
  Object.assign(gameForm, row ? { ...row } : defaultGameForm())
  gameDialogVisible.value = true
}

async function handleGameSubmit() {
  await gameFormRef.value?.validate()
  submitting.value = true
  try {
    // 先上传图标文件
    if (gameIconFile.value) {
      const res = await uploadFile(gameIconFile.value)
      if (res.code === 0) gameForm.icon = res.url
    }
    if (gameIsEdit.value) {
      await updateGame(editId.value, { ...gameForm })
      ElMessage.success('更新成功')
    } else {
      await createGame({ ...gameForm })
      ElMessage.success('添加成功')
    }
    gameDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDeleteGame(id) {
  try {
    await deleteGame(id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { ElMessage.error(e.message) }
}

// ── 大区管理（抽屉联动） ──
const regionDrawerVisible = ref(false)
const currentGame = ref(null)
const regionList = ref([])

async function openRegionDialog(game) {
  currentGame.value = game
  regionDrawerVisible.value = true
  await fetchRegions()
}

async function fetchRegions(game = null) {
  const g = game || currentGame.value
  if (!g) return
  try {
    const res = await getGameRegions({ game_id: g.id, page_size: 1000 })
    regionList.value = res.items
  } catch (e) {
    ElMessage.error('加载大区列表失败: ' + e.message)
  }
}

// ── 大区编辑 ──
const regionEditVisible = ref(false)
const regionIsEdit = ref(false)
const regionEditId = ref(null)
const regionSubmitting = ref(false)
const regionFormRef = ref(null)
const validateCoordinatePair = (_rule, _value, callback) => {
  const onlyOneProvided = (regionForm.select_x == null) !== (regionForm.select_y == null)
  if (onlyOneProvided) callback(new Error('X、Y 坐标必须同时填写或同时留空'))
  else callback()
}
const regionRules = {
  name: [{ required: true, message: '请输入大区名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  select_page: [{ required: true, message: '请输入所在页码', trigger: 'change' }],
  select_x: [{ validator: validateCoordinatePair, trigger: 'change' }],
  select_y: [{ validator: validateCoordinatePair, trigger: 'change' }],
}
const defaultRegionForm = () => ({ name: '', code: '', select_page: 1, select_x: null, select_y: null })
const regionForm = reactive(defaultRegionForm())

// 生成随机大区编码（8位大写字母+数字，如 A3K9M7XQ）
function genRegionCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 8; i++) {
    code += chars[Math.floor(Math.random() * chars.length)]
  }
  return code
}

function openRegionEdit(row = null) {
  regionIsEdit.value = !!row
  regionEditId.value = row?.id ?? null
  Object.assign(regionForm, row ? { ...row } : { ...defaultRegionForm(), code: genRegionCode() })
  regionEditVisible.value = true
}

async function handleRegionSubmit() {
  await regionFormRef.value?.validate()
  regionSubmitting.value = true
  try {
    if (regionIsEdit.value) {
      await updateRegion(regionEditId.value, { ...regionForm })
      ElMessage.success('更新成功')
    } else {
      const { sort_order, ...createPayload } = regionForm
      await createRegion({ ...createPayload, game_id: currentGame.value.id })
      ElMessage.success('添加成功')
    }
    regionEditVisible.value = false
    fetchRegions()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    regionSubmitting.value = false
  }
}

async function handleDeleteRegion(id) {
  try {
    await deleteRegion(id)
    ElMessage.success('已删除')
    fetchRegions()
  } catch (e) { ElMessage.error(e.message) }
}

// 从大区列表进入话术
async function openRegionScriptEntry(region) {
  scriptGame.value = currentGame.value
  scriptDrawerVisible.value = true
  scriptActiveTab.value = 'region'
  scriptRegionId.value = region.id
  await fetchGameScripts()
  await fetchRegionScripts()
}

// ── 话术管理（抽屉联动） ──
const scriptDrawerVisible = ref(false)
const scriptGame = ref(null)
const scriptActiveTab = ref('game')
const gameScriptList = ref([])
const regionScriptList = ref([])
const scriptRegionId = ref(null)
const regionScriptLoading = ref(false)
let regionScriptRequestToken = 0
const activeScriptRegion = computed(() => (
  regionList.value.find(region => region.id === scriptRegionId.value) || null
))

async function openScriptDrawer(game) {
  scriptGame.value = game
  currentGame.value = game
  scriptActiveTab.value = 'game'
  scriptRegionId.value = null
  regionScriptList.value = []
  scriptDrawerVisible.value = true
  // 加载大区和游戏话术
  await fetchRegions(game)
  await fetchGameScripts()
}

async function handleScriptTabChange(tabName) {
  if (tabName !== 'region' || !regionList.value.length) return
  const selected = activeScriptRegion.value || regionList.value[0]
  await selectScriptRegion(selected)
}

async function fetchGameScripts() {
  if (!scriptGame.value) return
  gameScriptList.value = await getAllGameScripts(scriptGame.value.id)
}

async function fetchRegionScripts() {
  if (!scriptRegionId.value) {
    regionScriptList.value = []
    regionScriptLoading.value = false
    return
  }
  const requestedRegionId = scriptRegionId.value
  const requestToken = ++regionScriptRequestToken
  regionScriptLoading.value = true
  regionScriptList.value = []
  try {
    const res = await getRegionScripts({ region_id: requestedRegionId, page_size: 1000 })
    if (requestToken === regionScriptRequestToken && requestedRegionId === scriptRegionId.value) {
      regionScriptList.value = res.items
    }
  } catch (e) {
    if (requestToken === regionScriptRequestToken) {
      ElMessage.error('加载大区话术失败: ' + e.message)
    }
  } finally {
    if (requestToken === regionScriptRequestToken) {
      regionScriptLoading.value = false
    }
  }
}

async function selectScriptRegion(region) {
  if (!region || region.id == null) return
  if (scriptRegionId.value === region.id && !regionScriptLoading.value && regionScriptList.value.length) return
  scriptRegionId.value = region.id
  await fetchRegionScripts()
}

// ── 游戏话术编辑 ──
const scriptEditVisible = ref(false)
const scriptIsEdit = ref(false)
const scriptEditId = ref(null)
const scriptSubmitting = ref(false)
const scriptFormRef = ref(null)
const scriptRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: false, message: '请输入内容', trigger: 'blur' }],
}
const defaultScriptForm = () => ({ title: '', content: '', image_url: '', category: '', sort_order: 0 })
const scriptForm = reactive(defaultScriptForm())

// 游戏话术图片上传
const scriptImageFileList = ref([])
const scriptImageFile = ref(null)

function handleScriptImageChange(file) {
  scriptImageFile.value = file.raw
  scriptImageFileList.value = [file]
}

function handleScriptImageRemove() {
  scriptImageFile.value = null
  scriptImageFileList.value = []
  scriptForm.image_url = ''
}

function openScriptEdit(row = null) {
  scriptIsEdit.value = !!row; scriptEditId.value = row?.id ?? null
  scriptImageFile.value = null
  if (row?.image_url) {
    scriptImageFileList.value = [{ name: row.image_url.split('/').pop() || 'image.png', url: row.image_url }]
  } else {
    scriptImageFileList.value = []
  }
  Object.assign(scriptForm, row ? { ...row } : defaultScriptForm())
  scriptEditVisible.value = true
}

async function handleScriptSubmit() {
  await scriptFormRef.value?.validate(); scriptSubmitting.value = true
  try {
    // 先上传图片文件
    if (scriptImageFile.value) {
      const res = await uploadFile(scriptImageFile.value)
      if (res.code === 0) scriptForm.image_url = res.url
    }
    if (scriptIsEdit.value) { await updateGameScript(scriptEditId.value, { ...scriptForm }); ElMessage.success('更新成功') }
    else { await createGameScript({ ...scriptForm, game_id: scriptGame.value.id }); ElMessage.success('添加成功') }
    scriptEditVisible.value = false; fetchGameScripts()
  } catch (e) { ElMessage.error(e.message) } finally { scriptSubmitting.value = false }
}

async function handleDeleteScript(id) {
  try { await deleteGameScript(id); ElMessage.success('已删除'); fetchGameScripts() } catch (e) { ElMessage.error(e.message) }
}

// ── 大区话术编辑 ──
const regionScriptEditVisible = ref(false)
const regionScriptIsEdit = ref(false)
const regionScriptEditId = ref(null)
const regionScriptSubmitting = ref(false)
const regionScriptFormRef = ref(null)
const regionScriptRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: false, message: '请输入内容', trigger: 'blur' }],
}
const defaultRegionScriptForm = () => ({ title: '', content: '', image_url: '', game_script_id: null, category: '', sort_order: 0 })
const regionScriptForm = reactive(defaultRegionScriptForm())

// 图片上传
const regionScriptImageFileList = ref([])
const regionScriptImageFile = ref(null)

function handleRegionScriptImageChange(file) {
  regionScriptImageFile.value = file.raw
  regionScriptImageFileList.value = [file]
}

function handleRegionScriptImageRemove() {
  regionScriptImageFile.value = null
  regionScriptImageFileList.value = []
  regionScriptForm.image_url = ''
}

function openRegionScriptEdit(row = null) {
  regionScriptIsEdit.value = !!row; regionScriptEditId.value = row?.id ?? null
  regionScriptImageFile.value = null
  if (row?.image_url) {
    regionScriptImageFileList.value = [{ name: row.image_url.split('/').pop() || 'image.png', url: row.image_url }]
  } else {
    regionScriptImageFileList.value = []
  }
  Object.assign(regionScriptForm, row ? { ...row } : defaultRegionScriptForm())
  regionScriptEditVisible.value = true
}

async function handleRegionScriptSubmit() {
  await regionScriptFormRef.value?.validate(); regionScriptSubmitting.value = true
  try {
    // 先上传图片文件
    if (regionScriptImageFile.value) {
      const res = await uploadFile(regionScriptImageFile.value)
      if (res.code === 0) regionScriptForm.image_url = res.url
    }
    if (regionScriptIsEdit.value) { await updateRegionScript(regionScriptEditId.value, { ...regionScriptForm }); ElMessage.success('更新成功') }
    else { await createRegionScript({ ...regionScriptForm, region_id: scriptRegionId.value }); ElMessage.success('添加成功') }
    regionScriptEditVisible.value = false; fetchRegionScripts()
  } catch (e) { ElMessage.error(e.message) } finally { regionScriptSubmitting.value = false }
}

async function handleDeleteRegionScript(id) {
  try { await deleteRegionScript(id); ElMessage.success('已删除'); fetchRegionScripts() } catch (e) { ElMessage.error(e.message) }
}

function copyRegionScript(row) {
  openRegionScriptEdit({ ...row, id: null })
  regionScriptIsEdit.value = false
}

function positiveRouteId(value) {
  const raw = Array.isArray(value) ? value[0] : value
  const id = Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
}

async function openRegionScriptsFromRoute() {
  const gameId = positiveRouteId(route.query.script_game_id)
  const regionId = positiveRouteId(route.query.script_region_id)
  if (!gameId || !regionId) return

  try {
    const game = list.value.find(item => Number(item.id) === gameId) || await getGame(gameId)
    scriptGame.value = game
    currentGame.value = game
    scriptActiveTab.value = 'region'
    scriptRegionId.value = regionId
    regionScriptList.value = []
    scriptDrawerVisible.value = true
    await Promise.all([fetchRegions(game), fetchGameScripts()])
    const targetRegion = regionList.value.find(region => Number(region.id) === regionId)
    if (!targetRegion) {
      ElMessage.warning('该大区已不存在或不属于当前游戏')
      return
    }
    await fetchRegionScripts()
  } catch (e) {
    ElMessage.error('打开大区话术失败: ' + e.message)
  } finally {
    const nextQuery = { ...route.query }
    delete nextQuery.script_game_id
    delete nextQuery.script_region_id
    router.replace({ query: nextQuery })
  }
}

onMounted(async () => {
  await fetchList()
  await openRegionScriptsFromRoute()
})
</script>

<style scoped>
.page-container { padding: 0; }
.game-directory {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 2px 8px rgb(31 45 61 / 4%);
}
.game-directory__header {
  display: flex;
  min-height: 94px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 20px;
  border-bottom: 1px solid #e7ebf0;
  background: linear-gradient(100deg, #fff 0%, #f8fbff 100%);
}
.game-directory__intro { min-width: 0; }
.game-directory__eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #4c78b8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .1em;
}
.game-directory__title-line { display: flex; align-items: center; gap: 10px; }
.game-directory__title-line h1 { margin: 0; color: #25364a; font-size: 21px; line-height: 1.3; }
.game-directory__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eaf2ff;
  color: #3d6eae;
  font-size: 12px;
  font-weight: 700;
}
.game-directory__intro p { margin: 6px 0 0; color: #8793a3; font-size: 13px; }
.game-directory__actions { display: flex; flex: 0 0 auto; align-items: center; gap: 10px; }
.game-search { width: 260px; }
.game-table-viewport { min-height: 0; flex: 1; overflow: hidden; }
.game-table { width: 100%; border-right: 0; border-left: 0; }
.game-table :deep(.el-table__header th.el-table__cell) {
  height: 44px;
  background: #f7f9fc;
  color: #5d6a7a;
  font-weight: 600;
}
.game-table :deep(.el-table__body td.el-table__cell) { padding: 12px 0; }
.game-identity { display: flex; min-width: 0; align-items: center; gap: 12px; }
.game-identity__avatar {
  flex: 0 0 auto;
  border: 1px solid #d8e4f4;
  border-radius: 10px;
  background: #eaf2ff;
  color: #315f9f;
  font-size: 16px;
  font-weight: 700;
}
.game-identity__copy { min-width: 0; }
.game-identity__copy strong,
.game-identity__copy code { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.game-identity__copy strong { color: #25364a; font-size: 14px; line-height: 1.4; }
.game-identity__copy code { margin-top: 4px; color: #8794a5; font-size: 11px; }
.trade-config strong,
.trade-config span { display: block; }
.trade-config strong { color: #34465b; font-size: 13px; }
.trade-config span { margin-top: 3px; color: #8a96a5; font-size: 12px; }
.game-remark { color: #596779; }
.game-remark.is-empty { color: #a8b0ba; }
.game-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; white-space: nowrap; }
.game-row-actions :deep(.el-button + .el-button) { margin-left: 0; }
.pagination-wrap {
  display: flex;
  justify-content: center;
  padding: 14px 18px;
  border-top: 1px solid #e7ebf0;
}
.region-toolbar { margin-bottom: 12px; }
.coordinate-inputs {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.coordinate-inputs .el-input-number { width: 120px; }

.region-script-workspace {
  display: grid;
  grid-template-columns: 216px minmax(0, 1fr);
  height: calc(100vh - 170px);
  min-height: 320px;
  overflow: hidden;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #fff;
}

.region-script-sidebar {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 14px 10px;
  border-right: 1px solid #dfe6ef;
  background: #f5f8fc;
}

.region-script-sidebar__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 8px 12px;
  color: #25364a;
}

.region-script-sidebar__heading > div,
.region-script-sidebar__heading span,
.region-script-sidebar__heading small { display: block; }
.region-script-sidebar__heading span { font-size: 13px; font-weight: 700; }
.region-script-sidebar__heading small { margin-top: 3px; color: #8694a6; font-size: 11px; font-weight: 400; }
.region-script-sidebar__heading strong {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #e7eef8;
  color: #496078;
  font-size: 12px;
}

.region-script-nav {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  overflow-y: auto;
  padding-right: 2px;
}

.region-script-nav__item {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 10px 10px 14px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #33465b;
  cursor: pointer;
  text-align: left;
  transition: background-color .16s ease, border-color .16s ease, color .16s ease;
}

.region-script-nav__item::before {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: transparent;
  content: '';
}

.region-script-nav__item:hover { border-color: #d5e0ee; background: #fff; }
.region-script-nav__item:focus-visible { outline: 2px solid #7da8ee; outline-offset: 1px; }
.region-script-nav__item.is-active {
  border-color: #c9daf5;
  background: #fff;
  color: #1f5fbf;
  box-shadow: 0 5px 16px rgb(39 91 156 / 9%);
}
.region-script-nav__item.is-active::before { background: #2f6fed; }
.region-script-nav__copy { min-width: 0; }
.region-script-nav__copy strong,
.region-script-nav__copy code { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.region-script-nav__copy strong { font-size: 13px; line-height: 1.35; }
.region-script-nav__copy code { margin-top: 5px; color: #8a98a9; font-size: 10px; }
.region-script-nav__arrow { color: #a3afbd; font-size: 20px; line-height: 1; }
.region-script-nav__item.is-active .region-script-nav__arrow { color: #2f6fed; transform: translateX(1px); }

.region-script-content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: auto;
  padding: 18px;
}
.region-script-content__heading {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  min-height: 76px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e8edf3;
}
.region-script-eyebrow { color: #2f6fed; font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.region-script-title-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 5px; }
.region-script-title-line h3 { margin: 0; color: #223247; font-size: 19px; line-height: 1.35; }
.region-script-title-line code { color: #7d8b9c; font-size: 11px; }
.region-script-content__heading p { margin: 6px 0 0; color: #8a96a5; font-size: 12px; }
.region-script-loading { padding: 8px 4px; }
.region-script-empty { min-height: 0; flex: 1; padding: 0 0 18px; }
.region-script-content > .el-table { flex: 0 0 auto; }

.script-editor-context {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -2px 0 20px;
  padding: 10px 12px;
  border: 1px solid #d9e5f6;
  border-radius: 8px;
  background: #f4f8fe;
}
.script-editor-context span { color: #7b8ba1; font-size: 12px; }
.script-editor-context strong { min-width: 0; overflow: hidden; color: #29405f; text-overflow: ellipsis; white-space: nowrap; }
.script-editor-context code { margin-left: auto; color: #5e7190; font-size: 11px; white-space: nowrap; }
.script-editor-form :deep(.el-form-item__label) { white-space: nowrap; }
.script-editor-form :deep(.el-textarea__inner) { min-height: 108px !important; resize: vertical; }
.script-editor-form :deep(.el-input-number) { width: 150px; }

@media (max-width: 900px) {
  .region-script-workspace { display: block; height: auto; min-height: 0; overflow: visible; }
  .region-script-sidebar { border-right: 0; border-bottom: 1px solid #dfe6ef; }
  .region-script-sidebar__heading { padding-bottom: 9px; }
  .region-script-nav { max-height: none; flex-direction: row; overflow-x: auto; padding-bottom: 4px; }
  .region-script-nav__item { min-width: 168px; }
  .region-script-content { padding: 14px; }
  .region-script-content__heading { align-items: stretch; flex-direction: column; }
  .region-script-content__heading .el-button { align-self: flex-start; }
}

@media (max-width: 760px) {
  .game-directory__header { align-items: stretch; flex-direction: column; gap: 14px; }
  .game-directory__actions { width: 100%; }
  .game-search { width: auto; flex: 1; }
}

@media (max-width: 520px) {
  .game-directory__actions { align-items: stretch; flex-direction: column; }
  .game-search,
  .game-directory__actions .el-button { width: 100%; }
}

@media (max-width: 600px) {
  .script-editor-form { --el-form-label-font-size: 13px; }
  .script-editor-form :deep(.el-form-item) { display: block; }
  .script-editor-form :deep(.el-form-item__label) {
    display: block;
    width: auto !important;
    height: auto;
    margin-bottom: 7px;
    line-height: 1.4;
    text-align: left;
  }
  .script-editor-form :deep(.el-form-item__content) { margin-left: 0 !important; }
  .script-editor-context { align-items: flex-start; flex-wrap: wrap; }
  .script-editor-context code { width: 100%; margin-left: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .region-script-nav__item { transition: none; }
}
</style>
