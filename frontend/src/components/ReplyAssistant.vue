<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { generateReplySuggestion } from '../api/tickets.js'
import { errorMessage, confirmAction } from '../utils/error.js'
const props = defineProps({ ticketId: { type: Number, required: true }, existingReply: { type: String, default: '' } })
const emit = defineEmits(['adopt'])
const busy = ref(false), result = ref(null), error = ref('')
let generation = 0
function reset() { generation++; result.value = null; error.value = ''; busy.value = false }
watch(() => props.ticketId, reset)
onBeforeUnmount(reset)
async function generate() {
  if (busy.value) return
  const version = ++generation
  busy.value = true; error.value = ''; result.value = null
  try { const data = await generateReplySuggestion(props.ticketId); if (version === generation) result.value = data }
  catch (err) { if (version === generation) error.value = errorMessage(err) }
  finally { if (version === generation) busy.value = false }
}
async function adopt() {
  const version = generation, draft = result.value?.draft
  if (!draft) return
  if (props.existingReply.trim() && !await confirmAction('回复框已有内容，确认使用 AI 草稿替换？')) return
  if (version === generation) emit('adopt', draft)
}
</script>

<template>
  <section class="panel" aria-label="AI 回复助手">
    <h2>AI 回复助手</h2>
    <p class="muted">根据公开知识资料生成建议，请核对来源并编辑后发送。</p>
    <el-button :loading="busy" :disabled="busy" @click="generate">{{ error ? '重新生成建议' : '生成回复建议' }}</el-button>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" />
    <el-alert v-if="result?.status === 'insufficient_evidence'" title="知识资料不足，请补充问题信息或手动回复。" type="info" :closable="false" />
    <template v-if="result?.status === 'ok'">
      <p class="plain-text">{{ result.draft }}</p>
      <details v-for="source in result.sources" :key="source.chunk_id">
        <summary>{{ source.title }} · 版本 {{ source.version }}</summary>
        <p class="plain-text">{{ source.content }}</p>
      </details>
      <el-button @click="adopt">采用草稿到回复框</el-button>
    </template>
  </section>
</template>
