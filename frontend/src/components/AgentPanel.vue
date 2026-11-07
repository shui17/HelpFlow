<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import * as api from '../api/agent.js'
import { errorMessage, confirmAction } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'

const props = defineProps({ ticketId: { type: Number, required: true } })
const emit = defineEmits(['changed'])
const defaults = { internal_summary: '整理问题、已尝试步骤、当前结论和待办，未知内容明确标注，提出内部备注草稿。', public_reply: '读取公开沟通记录，检索相关知识，提出有依据的公开回复草稿。' }
const mode = ref('internal_summary'), instruction = ref(defaults.internal_summary)
const task = ref(null), history = ref([]), draft = ref(''), error = ref(''), busy = ref(false), running = ref(false)
const more = ref(false), confirming = ref(false)
let epoch = 0, readSequence = 0, timer, pendingRequest
const labels = { pending: '准备就绪', running: '正在处理', waiting_confirmation: '等待客服确认',
  needs_input: '需要补充信息', completed: '只读任务已结束（未写入）', succeeded: '已执行',
  failed: '执行失败', rejected: '已拒绝', cancelled: '已取消', expired: '确认已过期', stale: '工单或资料已变化' }
const tools = { get_ticket: '查询工单', read_records: '读取沟通记录', search_knowledge: '检索公开知识', propose_action: '提出草稿', finish: '结束查询' }
const dirty = computed(() => draft.value !== task.value?.content)
const waiting = computed(() => task.value?.status === 'waiting_confirmation')
const active = computed(() => ['pending', 'running'].includes(task.value?.status))

function accept(value) {
  const old = task.value
  if (!old || old.id !== value.id || old.proposal_version !== value.proposal_version) draft.value = value.content
  task.value = value
  history.value = history.value.some(t => t.id === value.id)
    ? history.value.map(t => t.id === value.id ? value : t) : [value, ...history.value]
}
function reset() { epoch++; clearTimeout(timer); task.value = null; history.value = []; draft.value = ''; error.value = ''; busy.value = false; running.value = false; confirming.value = false; pendingRequest = null }
async function handleError(err, version) {
  if (version !== epoch) return
  error.value = errorMessage(err)
  if ([401, 403, 404].includes(err.response?.status)) { task.value = null; history.value = []; draft.value = ''; clearTimeout(timer) }
}
async function refresh() {
  if (!task.value) return
  const version = epoch, id = task.value.id, sequence = ++readSequence
  try { const value = await api.getTask(id); if (version === epoch && sequence === readSequence && task.value?.id === id) accept(value) }
  catch (err) { await handleError(err, version) }
}
function poll() {
  clearTimeout(timer)
  const version = epoch
  timer = setTimeout(async () => { await refresh(); if (version === epoch && active.value) poll() }, 2000)
}
async function load(earlier = false) {
  const version = epoch
  try {
    const rows = await api.listTasks(props.ticketId, earlier ? history.value.at(-1)?.id : undefined)
    if (version !== epoch) return
    history.value = earlier ? [...history.value, ...rows] : rows; more.value = rows.length === 10
    if (!earlier && rows.length) { accept(rows[0]); await refresh(); if (active.value) poll() }
  } catch (err) { await handleError(err, version) }
}
async function select(id) {
  if (busy.value || running.value || confirming.value) return
  epoch++; clearTimeout(timer); error.value = ''
  const version = epoch
  try { const value = await api.getTask(id); if (version === epoch) { accept(value); if (active.value) poll() } }
  catch (err) { await handleError(err, version) }
}
async function run() {
  if (!task.value || running.value) return
  const version = epoch, id = task.value.id
  running.value = true; error.value = ''; poll()
  try { const value = await api.runTask(id); if (version === epoch) accept(value) }
  catch (err) { await handleError(err, version); if (version === epoch) await refresh() }
  finally { if (version === epoch) { running.value = false; if (active.value) poll(); else clearTimeout(timer) } }
}
async function create() {
  if (busy.value || running.value || !instruction.value.trim()) return
  const version = epoch
  busy.value = true; error.value = ''
  const payload = { mode: mode.value, instruction: instruction.value.trim() }
  const signature = JSON.stringify(payload)
  if (pendingRequest?.signature !== signature) pendingRequest = { signature, id: crypto.randomUUID() }
  try {
    const value = await api.createTask(props.ticketId, { ...payload, request_id: pendingRequest.id })
    if (version !== epoch) return
    pendingRequest = null; accept(value); busy.value = false; await run()
  } catch (err) { await handleError(err, version) }
  finally { if (version === epoch) busy.value = false }
}
async function mutate(operation, changed = false) {
  if (!task.value || busy.value) return
  const version = epoch, id = task.value.id
  readSequence++
  busy.value = true; error.value = ''
  try {
    const value = await operation(id)
    if (version === epoch) { readSequence++; accept(value); if (changed && value.status === 'succeeded') emit('changed') }
  } catch (err) {
    await handleError(err, version)
    if (version === epoch) { await refresh(); if (changed && task.value?.status === 'succeeded') emit('changed') }
  } finally { if (version === epoch) busy.value = false }
}
async function confirm() {
  if (!waiting.value || dirty.value || busy.value || confirming.value) return
  confirming.value = true
  const version = epoch, id = task.value.id, proposalVersion = task.value.proposal_version, content = task.value.content
  const target = task.value.mode === 'public_reply' ? '公开发送给用户' : '保存为内部备注'
  try {
    if (!await confirmAction(`工单 #${props.ticketId} · ${target} · 版本 ${proposalVersion}\n\n${content}\n\n确认执行以上内容？`, { customClass: 'agent-confirmation' })) return
    if (version !== epoch || task.value?.id !== id || task.value.proposal_version !== proposalVersion || dirty.value) return
    await mutate(id => api.confirmProposal(id, proposalVersion), true)
  } finally { if (version === epoch) confirming.value = false }
}
watch(() => props.ticketId, () => { reset(); load() }, { immediate: true })
watch(mode, (value, previous) => { if (instruction.value === defaults[previous]) instruction.value = defaults[value] })
onBeforeUnmount(reset)
</script>

<template>
  <section class="panel agent-panel" aria-label="客服任务助手">
    <h2>客服任务助手</h2>
    <p class="muted">查询与整理后生成提案；保存备注或公开发送前，需要您核对并确认。</p>
    <el-form label-position="top" @submit.prevent="create">
      <el-form-item label="任务用途"><el-select v-model="mode" aria-label="任务用途" :disabled="busy || running">
        <el-option label="整理内部交接摘要" value="internal_summary" /><el-option label="拟公开回复" value="public_reply" />
      </el-select></el-form-item>
      <el-form-item label="任务要求"><el-input v-model="instruction" aria-label="任务要求" type="textarea" :rows="2" maxlength="2000" :disabled="busy || running" /></el-form-item>
      <el-button native-type="submit" type="primary" :loading="busy || running" :disabled="active || !instruction.trim() || confirming">新建并运行任务</el-button>
    </el-form>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" />
    <div v-if="history.length" class="agent-history">
      <label>历史任务 <select aria-label="历史任务" :value="task?.id" :disabled="busy || running || confirming" @change="select($event.target.value)">
        <option v-for="item in history" :key="item.id" :value="item.id">{{ formatDate(item.created_at) }} · {{ item.mode === 'public_reply' ? '公开回复' : '内部摘要' }} · {{ labels[item.status] }}</option>
      </select></label>
      <el-button v-if="more" :disabled="busy" @click="load(true)">更早任务</el-button>
    </div>
    <template v-if="task">
      <h3>{{ labels[task.status] }}</h3>
      <p class="muted">工单 #{{ task.ticket_id }} · {{ task.mode === 'public_reply' ? '公开回复，用户可见' : '内部备注，仅客服及管理员可见' }} · 模型 {{ task.rounds }}/6 · 工具 {{ task.tool_calls }}/8</p>
      <p>要求：{{ task.instruction }}</p>
      <ol v-if="task.trace.length"><li v-for="(event, index) in task.trace" :key="index">{{ tools[event.tool] }} · {{ event.elapsed_ms }} ms<span v-if="event.count !== undefined"> · {{ event.count }} 条</span><span v-if="event.has_more">（尚有更早记录）</span></li></ol>
      <el-alert v-if="task.error" :title="task.error" type="warning" :closable="false" />
      <template v-if="waiting">
        <p class="muted">提案版本 {{ task.proposal_version }} · 有效至 {{ formatDate(task.expires_at) }}</p>
        <el-input v-model="draft" aria-label="待确认内容" type="textarea" :rows="7" maxlength="2000" show-word-limit :disabled="busy || confirming" />
        <p v-if="dirty" class="muted">内容已修改，请先保存新版本，再确认执行。</p>
        <div class="agent-actions">
          <el-button :disabled="!dirty || !draft.trim() || busy || confirming" @click="mutate(id => api.editProposal(id, task.proposal_version, draft.trim()))">保存修改</el-button>
          <el-button type="primary" :disabled="dirty || busy || confirming" @click="confirm">{{ task.mode === 'public_reply' ? '确认公开发送' : '确认保存内部备注' }}</el-button>
          <el-button :disabled="busy || confirming" @click="mutate(api.rejectTask)">拒绝提案</el-button>
        </div>
      </template>
      <p v-else-if="task.content" class="plain-text">{{ task.content }}</p>
      <details v-for="source in task.sources" :key="source.chunk_id"><summary>{{ source.title }} · 版本 {{ source.version }}</summary><p class="plain-text">{{ source.content }}</p></details>
      <p v-if="task.status === 'succeeded'" role="status">{{ task.mode === 'public_reply' ? '公开回复已发送' : '内部备注已保存' }}，记录 #{{ task.result_id }}。</p>
      <p v-if="task.status === 'needs_input'" class="muted">补充工单信息或任务要求后，新建任务继续。</p>
      <div class="agent-actions">
        <el-button :disabled="busy || confirming" @click="refresh">查询任务状态</el-button>
        <el-button v-if="['pending', 'failed', 'running'].includes(task.status)" :disabled="busy || running" @click="run">继续运行</el-button>
        <el-button v-if="['pending', 'running', 'failed'].includes(task.status)" :disabled="busy" @click="mutate(api.cancelTask)">取消任务</el-button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.agent-panel { min-width: 0; }
.agent-panel h3 { margin-top: 1.2rem; }
.agent-panel ol { padding-left: 1.4rem; }
.agent-history { margin-top: 1rem; }
.agent-history select { max-width: 100%; padding: .45rem; border: 1px solid #dce4dd; border-radius: 6px; background: white; }
.agent-actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
.agent-actions .el-button { margin-left: 0; }
</style>

<style>
.agent-confirmation .el-message-box__message p { white-space: pre-wrap; max-height: 55vh; overflow-y: auto; }
</style>
