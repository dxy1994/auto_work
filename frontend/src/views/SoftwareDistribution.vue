<template>
  <div class="distribution-page">
    <header class="distribution-hero">
      <div class="hero-copy">
        <div class="eyebrow">INTRANET RELEASE DESK</div>
        <h1>把文件放到离机器最近的地方</h1>
        <p>在总控发布一次，内网中的每台电脑都能从这里直接下载。</p>
      </div>
      <div class="release-rail" aria-hidden="true">
        <div class="rail-node rail-node-source">
          <el-icon><UploadFilled /></el-icon>
          <span>总控发布</span>
        </div>
        <div class="rail-line">
          <i></i><i></i><i></i>
        </div>
        <div class="rail-node rail-node-target">
          <el-icon><Monitor /></el-icon>
          <span>内网机器</span>
        </div>
      </div>
    </header>

    <div class="distribution-workspace">
      <aside class="publish-panel">
        <div class="section-heading">
          <span class="section-kicker">发布入口</span>
          <h2>上传新版本</h2>
          <p>支持上传任意类型的文件，单个文件最大 2GB。</p>
        </div>

        <el-upload
          ref="uploadRef"
          class="package-uploader"
          drag
          :auto-upload="false"
          :limit="1"
          :disabled="uploading"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-icon class="upload-glyph"><UploadFilled /></el-icon>
          <div class="upload-title">拖入需要分发的文件</div>
          <div class="upload-hint">或点击选择任意类型文件</div>
        </el-upload>

        <el-form class="release-form" label-position="top" @submit.prevent="publishPackage">
          <el-form-item label="版本号">
            <el-input
              v-model="form.version"
              :disabled="uploading"
              maxlength="60"
              placeholder="例如 1.4.2"
            />
          </el-form-item>
          <el-form-item label="版本说明">
            <el-input
              v-model="form.notes"
              :disabled="uploading"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="说明本次更新内容或安装注意事项"
            />
          </el-form-item>
          <div v-if="autoFillHint" class="auto-fill-hint">
            <el-icon><InfoFilled /></el-icon>
            {{ autoFillHint }}
          </div>
          <el-button
            class="publish-button"
            type="primary"
            native-type="submit"
            :loading="uploading"
            :disabled="!selectedFile"
          >
            <el-icon><Promotion /></el-icon>
            {{ uploading ? '正在发布…' : '发布到内网' }}
          </el-button>
        </el-form>

        <div v-if="uploading" class="upload-progress">
          <div>
            <span>正在传送 {{ selectedFile?.name }}</span>
            <strong>{{ uploadProgress }}%</strong>
          </div>
          <el-progress :percentage="uploadProgress" :show-text="false" :stroke-width="8" />
          <small>请保持页面开启，完成后会自动出现在右侧列表。</small>
        </div>
      </aside>

      <main class="package-catalog">
        <div class="catalog-heading">
          <div>
            <span class="section-kicker">内网下载目录</span>
            <h2>已发布软件 <em>{{ packages.length }}</em></h2>
          </div>
          <el-button :loading="loading" plain @click="loadPackages">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>

        <el-skeleton v-if="loading && !packages.length" :rows="4" animated />

        <el-empty
          v-else-if="!packages.length"
          description="还没有发布文件，请从左侧上传第一个文件"
        />

        <div v-else class="package-list">
          <article
            v-for="(item, index) in packages"
            :key="item.id"
            class="package-card"
            :class="{ 'is-latest': index === 0 }"
          >
            <div class="file-mark" :data-kind="fileKind(item.file_name)">
              <el-icon><FolderOpened /></el-icon>
              <span>{{ fileKind(item.file_name) }}</span>
            </div>

            <div class="package-main">
              <div class="package-title-line">
                <h3 :title="item.file_name">{{ item.file_name }}</h3>
                <span v-if="index === 0" class="latest-label">最新发布</span>
                <el-tag v-if="item.version" size="small" effect="plain">
                  v{{ item.version }}
                </el-tag>
              </div>
              <p v-if="item.notes" class="package-notes">{{ item.notes }}</p>
              <p v-else class="package-notes is-empty">未填写版本说明</p>

              <div class="package-meta">
                <span><el-icon><Calendar /></el-icon>{{ formatDate(item.uploaded_at) }}</span>
                <span><el-icon><Coin /></el-icon>{{ formatSize(item.size) }}</span>
                <span class="checksum" :title="item.sha256">
                  <el-icon><Lock /></el-icon>SHA-256 {{ shortHash(item.sha256) }}
                </span>
              </div>
            </div>

            <div class="package-actions">
              <a class="download-action" :href="downloadUrl(item.id)">
                <el-icon><Download /></el-icon>
                下载
              </a>
              <el-button
                class="delete-action"
                link
                type="danger"
                :loading="deletingId === item.id"
                @click="removePackage(item)"
              >
                删除
              </el-button>
            </div>
          </article>
        </div>

        <div class="catalog-footnote">
          <el-icon><InfoFilled /></el-icon>
          下载内容来自总控对象存储；SHA-256 可用于确认文件在传输过程中未损坏。
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteSoftwarePackage,
  getSoftwarePackages,
  softwarePackageDownloadUrl,
  uploadSoftwarePackage,
} from '../api'
import { suggestReleaseMetadata } from '../utils/softwareRelease'

const maxFileSize = 2 * 1024 * 1024 * 1024

const uploadRef = ref(null)
const selectedFile = ref(null)
const packages = ref([])
const loading = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const deletingId = ref(null)
const autoFillHint = ref('')
const form = reactive({ version: '', notes: '' })

function handleFileChange(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > maxFileSize) {
    ElMessage.error('单个文件不能超过 2GB')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    resetSuggestedMetadata()
    return
  }
  selectedFile.value = raw
  applySuggestedMetadata()
}

function handleFileRemove() {
  selectedFile.value = null
  resetSuggestedMetadata()
}

function resetSuggestedMetadata() {
  form.version = ''
  form.notes = ''
  autoFillHint.value = ''
}

function applySuggestedMetadata() {
  if (!selectedFile.value) return
  const suggestion = suggestReleaseMetadata(selectedFile.value.name, packages.value)
  form.version = suggestion.version
  form.notes = suggestion.notes

  if (suggestion.versionFromFileName) {
    autoFillHint.value = suggestion.notes
      ? `已从包名识别版本 ${suggestion.version}，并复用该软件之前的描述`
      : `已从包名识别版本 ${suggestion.version}`
  } else if (suggestion.previous) {
    autoFillHint.value = suggestion.notes
      ? `已生成下一版本 ${suggestion.version}，并复用该软件之前的描述`
      : `已根据该软件上一版本生成 ${suggestion.version}`
  } else {
    autoFillHint.value = '未找到同名历史包，版本号从 1.0.0 开始'
  }
}

async function loadPackages() {
  loading.value = true
  try {
    packages.value = await getSoftwarePackages()
    applySuggestedMetadata()
  } catch (error) {
    ElMessage.error(error.message || '软件目录加载失败')
  } finally {
    loading.value = false
  }
}

async function publishPackage() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadProgress.value = 0
  try {
    await uploadSoftwarePackage(selectedFile.value, form, (progress) => {
      uploadProgress.value = progress
    })
    uploadProgress.value = 100
    ElMessage.success('文件已发布到内网')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    resetSuggestedMetadata()
    await loadPackages()
  } catch (error) {
    ElMessage.error(error.message || '文件发布失败')
  } finally {
    uploading.value = false
  }
}

async function removePackage(item) {
  try {
    await ElMessageBox.confirm(
      `删除“${item.file_name}”后，内网中的其他电脑将无法继续下载。`,
      '删除文件',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '保留',
        type: 'warning',
      },
    )
    deletingId.value = item.id
    await deleteSoftwarePackage(item.id)
    ElMessage.success('文件已删除')
    await loadPackages()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.message || '删除失败')
    }
  } finally {
    deletingId.value = null
  }
}

function downloadUrl(id) {
  return softwarePackageDownloadUrl(id)
}

function fileKind(fileName) {
  const lowerName = String(fileName || '').toLowerCase()
  if (lowerName.endsWith('.msix')) return 'MSIX'
  if (lowerName.endsWith('.msi')) return 'MSI'
  if (lowerName.endsWith('.exe')) return 'EXE'
  if (lowerName.endsWith('.tar.gz')) return 'TGZ'
  const extension = lowerName.split('.').pop()
  return extension ? extension.toUpperCase() : 'FILE'
}

function formatSize(bytes) {
  const value = Number(bytes)
  if (!Number.isFinite(value) || value < 0) return '-'
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = value / 1024
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size >= 100 ? size.toFixed(0) : size.toFixed(1)} ${units[unitIndex]}`
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function shortHash(value) {
  if (!value) return '计算中'
  return `${value.slice(0, 8)}…${value.slice(-6)}`
}

onMounted(loadPackages)
</script>

<style scoped>
.distribution-page {
  --ink: #102a43;
  --ink-soft: #486581;
  --paper: #ffffff;
  --mist: #edf3f8;
  --blue: #2f6fed;
  --blue-deep: #1f54bd;
  --teal: #0f9d84;
  min-height: calc(100vh - 40px);
  color: var(--ink);
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.distribution-hero {
  position: relative;
  display: flex;
  min-height: 190px;
  padding: 34px 38px;
  overflow: hidden;
  border-radius: 18px 18px 4px 4px;
  background:
    linear-gradient(115deg, rgba(255,255,255,.97) 0 52%, rgba(237,243,248,.92) 52% 100%),
    repeating-linear-gradient(90deg, transparent 0 47px, rgba(47,111,237,.08) 48px);
  box-shadow: inset 0 0 0 1px rgba(16,42,67,.08);
}

.distribution-hero::after {
  position: absolute;
  right: -70px;
  bottom: -96px;
  width: 280px;
  height: 180px;
  border: 42px solid rgba(47,111,237,.08);
  border-radius: 50%;
  content: "";
  transform: rotate(-14deg);
}

.hero-copy { position: relative; z-index: 1; max-width: 570px; }
.eyebrow, .section-kicker {
  color: var(--blue);
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .15em;
}
.hero-copy h1 {
  margin: 14px 0 10px;
  font-size: clamp(27px, 3vw, 42px);
  font-weight: 800;
  letter-spacing: -.04em;
  line-height: 1.2;
}
.hero-copy p { margin: 0; color: var(--ink-soft); font-size: 15px; line-height: 1.7; }

.release-rail {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  align-self: center;
  margin-left: auto;
  padding-left: 32px;
}
.rail-node {
  display: grid;
  width: 96px;
  height: 92px;
  place-items: center;
  align-content: center;
  gap: 8px;
  border: 1px solid #cbd9e6;
  border-radius: 14px;
  background: rgba(255,255,255,.88);
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 12px 28px rgba(16,42,67,.08);
}
.rail-node .el-icon { font-size: 27px; }
.rail-node-source { color: var(--blue); }
.rail-node-target { color: var(--teal); }
.rail-line {
  position: relative;
  display: flex;
  width: clamp(80px, 9vw, 150px);
  align-items: center;
  justify-content: space-around;
  border-top: 2px dashed #9fb3c8;
}
.rail-line i {
  width: 7px;
  height: 7px;
  margin-top: -4px;
  border-radius: 50%;
  background: var(--blue);
  box-shadow: 0 0 0 4px #e4ecf6;
}

.distribution-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 365px) minmax(520px, 1fr);
  gap: 18px;
  margin-top: 18px;
}
.publish-panel, .package-catalog {
  border: 1px solid #dbe5ee;
  border-radius: 12px;
  background: var(--paper);
  box-shadow: 0 8px 24px rgba(16,42,67,.05);
}
.publish-panel { padding: 24px; }
.package-catalog { min-width: 0; padding: 24px; }
.section-heading h2, .catalog-heading h2 {
  margin: 7px 0 5px;
  color: var(--ink);
  font-size: 21px;
  letter-spacing: -.02em;
}
.section-heading p { margin: 0 0 20px; color: #74889b; font-size: 13px; line-height: 1.6; }

.package-uploader :deep(.el-upload) { width: 100%; }
.package-uploader :deep(.el-upload-dragger) {
  width: 100%;
  padding: 24px 16px;
  border: 1px dashed #9fb3c8;
  border-radius: 10px;
  background: #f7fafc;
  transition: border-color .2s, background .2s, transform .2s;
}
.package-uploader :deep(.el-upload-dragger:hover) {
  border-color: var(--blue);
  background: #f1f6ff;
  transform: translateY(-1px);
}
.upload-glyph { color: var(--blue); font-size: 34px; }
.upload-title { margin-top: 9px; color: var(--ink); font-weight: 700; }
.upload-hint { margin-top: 5px; color: #829ab1; font-size: 12px; }
.release-form { margin-top: 20px; }
.release-form :deep(.el-form-item__label) { color: #486581; font-size: 13px; font-weight: 700; }
.auto-fill-hint {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  margin: -4px 0 14px;
  padding: 9px 10px;
  border-radius: 7px;
  background: #eef8f5;
  color: #33766a;
  font-size: 12px;
  line-height: 1.5;
}
.auto-fill-hint .el-icon { flex: none; margin-top: 2px; }
.publish-button { width: 100%; height: 42px; font-weight: 700; }
.upload-progress {
  margin-top: 18px;
  padding: 14px;
  border-radius: 9px;
  background: #eef5ff;
}
.upload-progress > div { display: flex; gap: 12px; justify-content: space-between; margin-bottom: 9px; font-size: 12px; }
.upload-progress span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-progress strong { color: var(--blue); }
.upload-progress small { display: block; margin-top: 8px; color: #74889b; line-height: 1.5; }

.catalog-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
.catalog-heading h2 em {
  display: inline-grid;
  min-width: 26px;
  height: 26px;
  margin-left: 6px;
  place-items: center;
  border-radius: 13px;
  background: var(--mist);
  color: var(--ink-soft);
  font-family: Consolas, monospace;
  font-size: 12px;
  font-style: normal;
}
.package-list { display: grid; gap: 10px; }
.package-card {
  position: relative;
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  min-height: 116px;
  padding: 18px;
  overflow: hidden;
  border: 1px solid #dbe5ee;
  border-radius: 10px;
  background: #fff;
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.package-card:hover {
  border-color: #b8cae0;
  box-shadow: 0 10px 24px rgba(16,42,67,.08);
  transform: translateY(-1px);
}
.package-card.is-latest { border-left: 4px solid var(--blue); }
.file-mark {
  display: grid;
  width: 58px;
  height: 62px;
  place-items: center;
  align-content: center;
  gap: 4px;
  border-radius: 9px;
  background: #eaf1ff;
  color: var(--blue-deep);
}
.file-mark .el-icon { font-size: 23px; }
.file-mark span { font-family: Consolas, monospace; font-size: 10px; font-weight: 800; }
.package-main { min-width: 0; }
.package-title-line { display: flex; min-width: 0; align-items: center; gap: 8px; }
.package-title-line h3 {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--ink);
  font-size: 15px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.latest-label {
  flex: none;
  padding: 3px 7px;
  border-radius: 4px;
  background: var(--blue);
  color: white;
  font-size: 10px;
  font-weight: 700;
}
.package-notes {
  margin: 8px 0 10px;
  overflow: hidden;
  color: #526d82;
  font-size: 13px;
  line-height: 1.55;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.package-notes.is-empty { color: #9aabba; }
.package-meta { display: flex; flex-wrap: wrap; gap: 13px; color: #829ab1; font-size: 11px; }
.package-meta span { display: inline-flex; align-items: center; gap: 4px; }
.checksum { font-family: Consolas, monospace; }
.package-actions { display: grid; min-width: 82px; justify-items: center; gap: 6px; }
.download-action {
  display: inline-flex;
  min-width: 82px;
  height: 36px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 7px;
  background: var(--blue);
  color: white;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  transition: background .2s, transform .2s;
}
.download-action:hover { background: var(--blue-deep); transform: translateY(-1px); }
.download-action:focus-visible { outline: 3px solid rgba(47,111,237,.25); outline-offset: 2px; }
.delete-action { font-size: 12px; }
.catalog-footnote {
  display: flex;
  gap: 7px;
  align-items: flex-start;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
  color: #829ab1;
  font-size: 11px;
  line-height: 1.6;
}
.catalog-footnote .el-icon { flex: none; margin-top: 2px; color: var(--teal); }

@media (max-width: 1100px) {
  .release-rail { display: none; }
  .distribution-workspace { grid-template-columns: 330px minmax(0, 1fr); }
  .package-meta .checksum { display: none; }
}

@media (max-width: 820px) {
  .distribution-hero { min-height: auto; padding: 28px 24px; }
  .distribution-workspace { grid-template-columns: 1fr; }
  .package-card { grid-template-columns: 52px minmax(0, 1fr); }
  .package-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; }
}

@media (max-width: 560px) {
  .distribution-hero { border-radius: 12px 12px 4px 4px; }
  .hero-copy h1 { font-size: 27px; }
  .publish-panel, .package-catalog { padding: 18px; }
  .package-card { padding: 14px; }
  .package-title-line { align-items: flex-start; flex-wrap: wrap; }
  .package-title-line h3 { flex-basis: 100%; }
  .package-meta { gap: 8px; }
}

@media (prefers-reduced-motion: reduce) {
  .package-card, .download-action, .package-uploader :deep(.el-upload-dragger) { transition: none; }
}
</style>
