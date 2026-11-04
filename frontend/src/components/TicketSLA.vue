<script setup>
import { ref, watch } from 'vue'
import { getTicketSLAEvents } from '../api/tickets.js'
import { formatDate } from '../utils/datetime.js'
import { slaLabels } from '../utils/sla.js'
import { errorMessage } from '../utils/error.js'
const props = defineProps({ ticketId: { type: Number, required: true }, summary: { type: Object, default: null } })
const events = ref([]), error = ref(''), loading = ref(false)
let generation = 0
async function load() {
  const current = ++generation
  events.value = []; error.value = ''
  if (!props.summary) return
  loading.value = true
  try { const rows = await getTicketSLAEvents(props.ticketId); if (current === generation) events.value = rows }
  catch (err) { if (current === generation) error.value = errorMessage(err) }
  finally { if (current === generation) loading.value = false }
}
watch(() => props.summary, load, { immediate: true })
</script>
<template><section class="panel"><div class="section-heading"><h2>首次响应时限</h2><el-tag v-if="summary" :type="summary.state === 'overdue' ? 'danger' : summary.state === 'due_soon' ? 'warning' : 'info'">{{ slaLabels[summary.state] }}</el-tag></div>
  <template v-if="summary"><el-descriptions :column="1"><el-descriptions-item label="响应截止时间">{{ formatDate(summary.due_at) }}</el-descriptions-item><el-descriptions-item label="首次客服响应">{{ summary.first_response_at ? formatDate(summary.first_response_at) : '尚未响应' }}</el-descriptions-item><el-descriptions-item label="约定时限">{{ summary.response_seconds / 60 }} 分钟 · 规则版本 {{ summary.version }}</el-descriptions-item></el-descriptions>
    <p class="muted">内部备注不计入首次响应；转交、修改优先级或重新打开不重置时限。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error" @click="load">重试加载提醒记录</el-button>
    <p v-if="loading" class="muted">正在加载提醒记录…</p>
    <ul v-else-if="events.length"><li v-for="event in events" :key="event.id">{{ event.kind === 'overdue' ? '超时升级' : '即将超时提醒' }} · {{ formatDate(event.occurred_at) }}</li></ul>
    <p v-else-if="!error" class="muted">暂无提醒或升级记录</p>
  </template><p v-else class="muted">未启用 SLA（升级前创建的工单）</p>
</section></template>
