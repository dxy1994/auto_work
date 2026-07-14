<template>
  <el-dialog v-model="dialogVisible" title="输入验证码" width="400px" :close-on-click-modal="false" destroy-on-close>
    <div style="text-align:center; margin-bottom: 16px">
      <p style="color:#606266">请在浏览器窗口查看验证码，然后输入下方：</p>
    </div>
    <el-input
      v-model="captchaValue"
      placeholder="请输入验证码"
      size="large"
      autofocus
      @keyup.enter="handleSubmit"
    />
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!captchaValue" @click="handleSubmit">
        提交验证码
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  taskId: String,
})
const emit = defineEmits(['update:visible', 'submit'])

const captchaValue = ref('')
const submitting = ref(false)
const dialogVisible = ref(false)

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v) captchaValue.value = ''
})
watch(dialogVisible, (v) => {
  emit('update:visible', v)
})

async function handleSubmit() {
  if (!captchaValue.value) return
  submitting.value = true
  try {
    // 通过 WebSocket 发送验证码
    const wsUrl = `ws://${window.location.host}/api/automation/ws/captcha/${props.taskId}`
    const ws = new WebSocket(wsUrl)
    await new Promise((resolve, reject) => {
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'captcha_input', value: captchaValue.value }))
        resolve()
      }
      ws.onerror = reject
      setTimeout(() => reject(new Error('WebSocket 连接超时')), 5000)
    })
    ws.close()
    emit('submit')
    dialogVisible.value = false
  } catch (e) {
    console.error('验证码提交失败', e)
  } finally {
    submitting.value = false
  }
}
</script>
