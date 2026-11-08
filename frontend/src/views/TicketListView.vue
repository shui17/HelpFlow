<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { useAuthStore } from '../stores/auth.js'
import { getTickets, claimTicket } from '../api/tickets.js'
import { getUsers } from '../api/users.js'

import { statuses, priorities, categories } from '../constants/index.js'
import { errorMessage, confirmAction, notifyError } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'
import PageState from '../components/PageState.vue'
import AppPagination from '../components/AppPagination.vue'
import TicketTag from '../components/TicketTag.vue'
import { slaLabels } from '../utils/sla.js'
const route = useRoute(), router = useRouter(), auth = useAuthStore()
const filters = reactive({ keyword: '', status: '', priority: '', category: '', sort_order: 'desc', assignee: '', sla: ['due_soon', 'overdue'].includes(route.query.sla) ? route.query.sla : '' })
const loading = ref(true), error = ref(''), items = ref([]), total = ref(0), page = ref(1), busy = ref(false)
const agents = ref([])
const scope = computed(() => route.meta.scope)
let generation = 0
async function load(target = page.value) {
  const current = ++generation
  page.value = target; loading.value = true; error.value = ''
  const params = { sla: filters.sla || undefined, keyword: filters.keyword.trim() || undefined, status: scope.value === 'unassigned' ? 'open' : filters.status || undefined, priority: filters.priority || undefined, category: filters.category || undefined, sort_order: filters.sort_order }
  try {
    const result = await getTickets({ ...params, scope: scope.value,
      assignee_id: filters.assignee && filters.assignee !== 'unassigned' ? Number(filters.assignee) : undefined,
      unassigned: filters.assignee === 'unassigned', page: target, page_size: 10 })
    if (current === generation) { items.value = result.items; total.value = result.total }
  } catch (err) { if (current === generation) error.value = errorMessage(err) }
  finally { if (current === generation) loading.value = false }
}
function reset() { Object.assign(filters, { keyword: '', status: '', priority: '', category: '', sort_order: 'desc', assignee: '', sla: '' }); load(1) }
async function claim(row) {
  if (busy.value) return
  busy.value = true
  try {
    if (!await confirmAction(`领取工单 #${row.id} 后，您将成为该工单的负责人。确认领取？`)) return
    await claimTicket(row.id); ElMessage.success('领取成功'); await load(1)
  } catch (err) { notifyError(err); if (err.response?.status === 409) await load(1) }
  finally { busy.value = false }
}
async function searchAgents(keyword = '') {
  try { agents.value = (await getUsers({ role: 'agent', keyword, page_size: 30 })).items }
  catch (err) { notifyError(err) }
}
watch(() => route.query.sla, value => { filters.sla = ['due_soon', 'overdue'].includes(value) ? value : ''; load(1) })
onMounted(async () => {
  load()
  if (auth.role === 'admin') {
    await searchAgents()
  }
})
</script>
<template><div class="page-heading"><div><div class="eyebrow">TICKETS</div><h1>{{ route.meta.title }}</h1><p class="muted">按状态、分类或响应时限查找工单。</p></div><el-button v-if="auth.role === 'user'" type="primary" @click="router.push('/user/tickets/create')">＋ 创建工单</el-button><el-button v-else @click="load()">刷新列表</el-button></div>
  <section class="panel"><el-form class="filter-form" inline @submit.prevent="load(1)"><el-form-item label="搜索"><el-input v-model="filters.keyword" maxlength="200" clearable placeholder="标题或工单编号" /></el-form-item><el-form-item v-if="scope !== 'unassigned'" label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(label, value) in statuses" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="filters.priority" clearable placeholder="全部优先级"><el-option v-for="(label, value) in priorities" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="分类"><el-select v-model="filters.category" clearable placeholder="全部分类"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="响应时限"><el-select v-model="filters.sla" clearable placeholder="全部时限"><el-option label="即将超时" value="due_soon" /><el-option label="已超时" value="overdue" /></el-select></el-form-item><el-form-item label="排序"><el-select v-model="filters.sort_order"><el-option label="最新创建优先" value="desc" /><el-option label="最早创建优先" value="asc" /></el-select></el-form-item><el-form-item v-if="auth.role === 'admin'" label="负责人"><el-select v-model="filters.assignee" clearable filterable remote :remote-method="searchAgents" placeholder="全部负责人"><el-option label="暂未分配" value="unassigned" /><el-option v-for="agent in agents" :key="agent.id" :label="agent.username" :value="String(agent.id)" /></el-select></el-form-item><el-form-item><el-button type="primary" native-type="submit">查询</el-button><el-button @click="reset">重置</el-button></el-form-item></el-form>
  <PageState :loading="loading" :error="error" @retry="load()"><el-table v-if="items.length" :data="items"><el-table-column prop="id" label="编号" width="80" /><el-table-column label="工单标题" min-width="210"><template #default="{ row }"><router-link :to="`/${auth.role}/tickets/${row.id}`">{{ row.title }}</router-link></template></el-table-column><el-table-column label="分类" width="115"><template #default="{ row }">{{ categories[row.category] }}</template></el-table-column><el-table-column label="状态" width="110"><template #default="{ row }"><TicketTag :value="row.status" /></template></el-table-column><el-table-column label="优先级" width="100"><template #default="{ row }"><TicketTag :value="row.priority" priority /></template></el-table-column><el-table-column label="负责人" width="120"><template #default="{ row }">{{ row.assignee_id ? `客服 #${row.assignee_id}` : '暂未分配' }}</template></el-table-column><el-table-column label="首次响应" width="130"><template #default="{ row }"><el-tag v-if="row.sla" :type="row.sla.state === 'overdue' ? 'danger' : row.sla.state === 'due_soon' ? 'warning' : 'info'">{{ slaLabels[row.sla.state] }}</el-tag><span v-else class="muted">未启用 SLA</span></template></el-table-column><el-table-column label="创建时间" width="185"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><el-table-column label="操作" :width="scope === 'unassigned' ? 135 : 75" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/${auth.role}/tickets/${row.id}`)">查看</el-button><el-button v-if="scope === 'unassigned'" link type="primary" :disabled="busy" @click="claim(row)">领取</el-button></template></el-table-column></el-table><el-empty v-else description="没有符合条件的工单"><el-button @click="reset">清空筛选</el-button></el-empty><AppPagination :page="page" :total="total" @change="load" /></PageState></section>
</template>
