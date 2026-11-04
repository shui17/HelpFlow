<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { useAuthStore } from '../stores/auth.js'
import * as api from '../api/tickets.js'
import InternalNotes from '../components/InternalNotes.vue'
import TicketSLA from '../components/TicketSLA.vue'

import { ticketPermissions } from '../utils/permissions.js'
import { errorMessage, notifyError, confirmAction } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'
import { statuses, actions, categories } from '../constants/index.js'
import PageState from '../components/PageState.vue'
import TicketTag from '../components/TicketTag.vue'
import TicketForm from '../components/TicketForm.vue'
const route = useRoute(), router = useRouter(), auth = useAuthStore()
const id = Number(route.params.id)
const loading = ref(true), error = ref(''), busy = ref(false), ticket = ref(null), comments = ref([]), activities = ref([])
const commentMore = ref(false), activityMore = ref(false), recordBusy = ref(false)
const editing = ref(false), assigning = ref(false), agents = ref([]), assignee = ref(null), agentLoading = ref(false), agentError = ref(''), reply = ref('')
const transferring = ref(false), transferReason = ref('')
const permissions = computed(() => ticket.value ? ticketPermissions(ticket.value, auth.currentUser) : {})
async function load() {
  loading.value = true; error.value = ''
  try { const result = await Promise.all([api.getTicketDetail(id), api.getTicketComments(id), api.getTicketActivities(id)]); [ticket.value, comments.value, activities.value] = result; commentMore.value = comments.value.length === 50; activityMore.value = activities.value.length === 50 }
  catch (err) { error.value = errorMessage(err) }
  finally { loading.value = false }
}
async function loadEarlier(kind) {
  if (recordBusy.value) return
  recordBusy.value = true
  const records = kind === 'comments' ? comments : activities
  const more = kind === 'comments' ? commentMore : activityMore
  try {
    const fetch = kind === 'comments' ? api.getTicketComments : api.getTicketActivities
    const rows = await fetch(id, { before_id: records.value[0].id, limit: 50 })
    records.value = [...rows, ...records.value]; more.value = rows.length === 50
  } catch (err) { notifyError(err) }
  finally { recordBusy.value = false }
}
async function action(operation, message, success) {
  if (busy.value) return
  busy.value = true
  try {
    if (message && !await confirmAction(message)) return
    await operation(); ElMessage.success(success); editing.value = false; assigning.value = false; transferring.value = false; if (Number(route.params.id) === id) await load()
  } catch (err) {
    notifyError(err)
    if ([403, 404, 409].includes(err.response?.status)) { editing.value = false; assigning.value = false; transferring.value = false; await load() }
  } finally { busy.value = false }
}
async function sendReply() {
  const text = reply.value.trim()
  if (!text || text.length > 2000 || busy.value) return
  await action(async () => { await api.createTicketComment(id, text); reply.value = '' }, null, '回复已发送')
}
async function loadAgents(keyword = '') {
  agentLoading.value = true; agentError.value = ''
  try { agents.value = await api.getAgents(keyword) }
  catch (err) { agentError.value = errorMessage(err) }
  finally { agentLoading.value = false }
}
async function openTransfer() { assignee.value = null; transferReason.value = ''; transferring.value = true; await loadAgents() }
function transfer() {
  if (!assignee.value || !transferReason.value.trim()) return
  action(async () => { await api.transferTicket(id, assignee.value, transferReason.value.trim()); await router.replace('/agent/tickets/mine') }, '确认将工单转交给所选客服？转交后您将无法继续处理。', '工单已转交')
}
async function openAssign() { assignee.value = null; assigning.value = true; await loadAgents() }
function assign() {
  if (!assignee.value) return
  action(() => api.assignTicket(id, assignee.value), '分配后由所选客服负责该工单，原负责人将无法继续处理。确认分配？', '工单已分配')
}
onMounted(load)
</script>
<template><div class="page-heading"><div><div class="eyebrow">TICKET / #{{ id }}</div><h1>工单详情</h1><p class="muted">查看问题、沟通记录与完整处理进展。</p></div><div><el-button :disabled="busy" @click="router.push(auth.role === 'agent' ? '/agent/tickets/mine' : `/${auth.role}/tickets`)">返回列表</el-button><el-button :disabled="busy" @click="load">刷新</el-button></div></div>
  <PageState :loading="loading" :error="error" @retry="load"><div v-if="ticket" class="detail-grid"><div class="detail-main">
    <section class="panel"><div class="section-heading"><span class="muted">工单 #{{ ticket.id }}</span><div class="inline-tags"><TicketTag :value="ticket.status" /><TicketTag :value="ticket.priority" priority /></div></div><h2 class="ticket-title">{{ ticket.title }}</h2><p class="plain-text ticket-description">{{ ticket.description }}</p><el-descriptions :column="2"><el-descriptions-item label="分类">{{ categories[ticket.category] }}</el-descriptions-item><el-descriptions-item label="创建人">用户 #{{ ticket.creator_id }}</el-descriptions-item><el-descriptions-item label="负责人">{{ ticket.assignee_id ? `客服 #${ticket.assignee_id}` : '暂未分配' }}</el-descriptions-item><el-descriptions-item label="创建时间">{{ formatDate(ticket.created_at) }}</el-descriptions-item><el-descriptions-item label="更新时间">{{ formatDate(ticket.updated_at) }}</el-descriptions-item><el-descriptions-item v-if="ticket.assigned_at" label="分配时间">{{ formatDate(ticket.assigned_at) }}</el-descriptions-item><el-descriptions-item v-if="ticket.closed_at" label="关闭时间">{{ formatDate(ticket.closed_at) }}</el-descriptions-item></el-descriptions>
      <div class="ticket-actions"><el-button v-if="permissions.transfer" :disabled="busy" @click="openTransfer">转交工单</el-button><el-button v-if="permissions.edit" :disabled="busy" @click="editing = true">编辑工单</el-button><el-button v-if="permissions.edit" type="danger" plain :disabled="busy" @click="action(() => api.cancelTicket(id), '撤销后工单将关闭，无法继续编辑或回复。确认撤销？', '工单已撤销')">撤销工单</el-button><el-button v-if="permissions.claim" type="primary" :loading="busy" @click="action(() => api.claimTicket(id), '领取后您将成为该工单的负责人。确认领取？', '领取成功')">领取工单</el-button><el-button v-if="permissions.assign" type="primary" :disabled="busy" @click="openAssign">{{ ticket.assignee_id ? '重新分配' : '分配客服' }}</el-button><el-button v-if="permissions.start" type="primary" :loading="busy" @click="action(() => api.changeTicketStatus(id, 'in_progress'), '确认开始处理该工单？', '已开始处理')">开始处理</el-button><el-button v-if="permissions.resolve" type="success" :loading="busy" @click="action(() => api.changeTicketStatus(id, 'resolved'), '确认问题已经解决？工单将等待用户确认解决。', '已标记为解决')">标记为已解决</el-button><el-button v-if="permissions.reopen" :disabled="busy" @click="action(() => api.changeTicketStatus(id, 'in_progress'), '重新打开后，工单将回到处理中。确认继续？', '工单已重新打开')">重新打开</el-button><el-button v-if="permissions.close" type="primary" :loading="busy" @click="action(() => api.changeTicketStatus(id, 'closed'), '关闭后无法再次回复或重新打开。确认问题已解决并关闭工单？', '工单已关闭')">确认关闭</el-button></div>
    </section>
    <TicketSLA :ticket-id="id" :summary="ticket.sla" />
    <section class="panel"><div class="section-heading"><h2>沟通记录</h2><span class="muted">已加载 {{ comments.length }} 条回复</span></div><el-button v-if="commentMore" :loading="recordBusy" @click="loadEarlier('comments')">加载更早回复</el-button><div v-for="comment in comments" :key="comment.id" class="comment" :class="{ 'comment-self': comment.author_id === auth.currentUser.id }"><div class="comment-meta"><strong>{{ comment.author_id === auth.currentUser.id ? '我' : `用户 #${comment.author_id}` }}</strong><time>{{ formatDate(comment.created_at) }}</time></div><p class="plain-text">{{ comment.content }}</p></div><el-empty v-if="!comments.length" description="暂无回复" :image-size="70" />
      <el-form v-if="permissions.reply" label-position="top" @submit.prevent="sendReply"><el-form-item label="添加回复"><el-input v-model="reply" type="textarea" :rows="4" maxlength="2000" show-word-limit placeholder="请输入回复内容，支持纯文本。" /></el-form-item><el-button type="primary" native-type="submit" :disabled="!reply.trim()" :loading="busy">发送回复</el-button></el-form><el-alert v-else :title="ticket.status === 'closed' ? '工单已关闭，无法继续回复。' : '当前角色可查看沟通记录，无法添加回复。'" type="info" :closable="false" />
    </section>
    <InternalNotes v-if="permissions.notes" :ticket-id="id" :readonly="ticket.status === 'closed'" />
  </div><aside class="panel timeline-panel"><h2>处理时间线</h2><el-button v-if="activityMore" :loading="recordBusy" @click="loadEarlier('activities')">加载更早记录</el-button><el-timeline v-if="activities.length"><el-timeline-item v-for="activity in activities" :key="activity.id" :timestamp="formatDate(activity.created_at)" placement="top"><strong>{{ actions[activity.action] || activity.action }}</strong><p>操作人 #{{ activity.operator_id }}</p><p v-if="activity.new_status">{{ activity.old_status ? `${statuses[activity.old_status]} → ` : '' }}{{ statuses[activity.new_status] }}</p><p v-if="activity.new_assignee_id">{{ activity.old_assignee_id ? `客服 #${activity.old_assignee_id} → ` : '' }}客服 #{{ activity.new_assignee_id }}</p><p v-if="activity.description" class="plain-text">{{ activity.description }}</p></el-timeline-item></el-timeline><el-empty v-else description="暂无处理记录" :image-size="70" /></aside></div></PageState>
  <el-dialog v-model="editing" title="编辑工单" width="min(640px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close><TicketForm v-if="ticket" :initial="ticket" :submitting="busy" @submit="payload => action(() => api.updateTicket(id, payload), null, '修改已保存')" @cancel="editing = false" /></el-dialog>
  <el-dialog v-model="assigning" title="选择负责客服" width="min(480px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy"><PageState :loading="false" :error="agentError" @retry="loadAgents"><el-form label-position="top"><el-form-item label="启用中的客服"><el-select v-model="assignee" :loading="agentLoading" filterable remote :remote-method="loadAgents" placeholder="请选择客服" class="full-width"><el-option v-for="agent in agents" :key="agent.id" :label="`${agent.username} · #${agent.id}`" :value="agent.id" :disabled="agent.id === ticket?.assignee_id" /></el-select></el-form-item></el-form><el-empty v-if="!agents.length" description="暂无可分配的客服，请先在用户管理中设置" /></PageState><template #footer><el-button :disabled="busy" @click="assigning = false">取消</el-button><el-button type="primary" :disabled="!assignee || agentLoading || Boolean(agentError)" :loading="busy" @click="assign">确认分配</el-button></template></el-dialog>
  <el-dialog v-model="transferring" title="转交工单" width="min(480px, 94vw)" :close-on-click-modal="false" :show-close="!busy" :close-on-press-escape="!busy">
    <PageState :loading="false" :error="agentError" @retry="loadAgents"><el-form label-position="top">
      <el-form-item label="目标客服"><el-select v-model="assignee" :loading="agentLoading" filterable remote :remote-method="loadAgents" placeholder="按客服名称搜索" class="full-width"><el-option v-for="agent in agents" :key="agent.id" :label="`${agent.username} · #${agent.id}`" :value="agent.id" :disabled="agent.id === ticket?.assignee_id" /></el-select></el-form-item>
      <el-form-item label="转交原因"><el-input v-model="transferReason" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item>
    </el-form></PageState><template #footer><el-button :disabled="busy" @click="transferring = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="!assignee || !transferReason.trim() || agentLoading || Boolean(agentError)" @click="transfer">确认转交</el-button></template>
  </el-dialog>
</template>
