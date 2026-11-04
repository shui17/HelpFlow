<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { getDashboardSummary } from '../api/dashboard.js'
import { statuses } from '../constants/index.js'
import { errorMessage } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'
import PageState from '../components/PageState.vue'
import TicketTag from '../components/TicketTag.vue'
import AppIcon from '../components/AppIcon.vue'
import { slaListTarget } from '../utils/sla.js'
const auth = useAuthStore(), router = useRouter()
const loading = ref(true), error = ref(''), data = ref({ counts: {}, recent: [] })
const total = computed(() => Object.keys(statuses).reduce((sum, status) => sum + (data.value.counts[status] || 0), 0))
const settled = computed(() => (data.value.counts.resolved || 0) + (data.value.counts.closed || 0))
const rate = computed(() => total.value ? Math.round(settled.value / total.value * 100) : 0)
const dateLabel = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())
async function load() { loading.value = true; error.value = ''; try { data.value = await getDashboardSummary(auth.currentUser) } catch (err) { error.value = errorMessage(err) } finally { loading.value = false } }
onMounted(load)
</script>
<template><div class="page-heading"><div><div class="eyebrow">OVERVIEW</div><h1>{{ auth.currentUser.username }}，您好</h1><p class="muted">在这里了解工单进展，开始今天的工作。</p></div><el-button v-if="auth.role === 'user'" type="primary" @click="router.push('/user/tickets/create')">＋ 创建工单</el-button><el-button v-else @click="load">刷新概览</el-button></div>
  <PageState :loading="loading" :error="error" @retry="load">
    <section class="dashboard-banner"><div class="banner-copy"><span class="banner-kicker"><AppIcon name="leaf" :size="16" /> 服务，让每一次连接更好</span><h2>有条不紊，回应每一个问题。</h2><p>从第一条提问，到最后一次确认，所有进展尽在掌握。</p><span class="banner-date">{{ dateLabel }}</span></div><div class="banner-progress"><div class="progress-ring" :style="{ '--progress': `${rate}%` }"><div><strong>{{ rate }}<small>%</small></strong><span>已解决及关闭</span></div></div><span class="progress-caption">{{ settled }} / {{ total }} 张{{ auth.role === 'agent' ? '本人负责的' : '' }}工单</span></div></section>
    <div class="section-heading overview-heading"><h2>工单概况 <span class="section-caption">{{ auth.role === 'admin' ? '全局数据' : auth.role === 'agent' ? '本人负责' : '我的工单' }}</span></h2><span class="muted">共 {{ total }} 张</span></div>
    <div class="stats-grid"><div v-for="(label, status) in statuses" :key="status" class="stat-card" :class="`stat-${status}`"><span>{{ auth.role === 'agent' ? '本人' : '' }}{{ label }}</span><span class="stat-icon"><AppIcon :name="status === 'open' ? 'ticket' : status === 'in_progress' ? 'clock' : 'check'" /></span><strong>{{ data.counts[status] }}</strong><span class="stat-foot">{{ label === '已解决' ? '等待用户确认' : label === '已关闭' ? '每一次回应，都有结果' : label === '处理中' ? '让问题持续向前推进' : '准备好迎接新的问题' }}</span></div></div>
    <div v-if="auth.role !== 'user'" class="summary-strip"><template v-if="auth.role === 'agent'"><span>待领取工单 <b>{{ data.counts.unassigned }}</b></span><router-link to="/agent/tickets/unassigned">前往领取 →</router-link></template><template v-else><span>启用用户 <b>{{ data.counts.users }}</b></span><span>启用客服 <b>{{ data.counts.agents }}</b></span><router-link to="/admin/users">管理用户 →</router-link></template></div>
    <div class="summary-strip"><span>首次响应 <b>{{ data.counts.due_soon || 0 }}</b> 张即将超时</span><router-link :to="slaListTarget(auth.role, 'due_soon')">查看即将超时 →</router-link><span><b>{{ data.counts.overdue || 0 }}</b> 张已超时</span><router-link :to="slaListTarget(auth.role, 'overdue')">查看已超时 →</router-link></div>
    <section class="panel"><div class="section-heading"><h2>最近工单</h2><router-link :to="auth.role === 'agent' ? '/agent/tickets/mine' : `/${auth.role}/tickets`">查看全部 →</router-link></div><el-table v-if="data.recent.length" :data="data.recent" @row-click="row => router.push(`/${auth.role}/tickets/${row.id}`)" class="clickable-table"><el-table-column prop="id" label="编号" width="85" /><el-table-column prop="title" label="工单标题" min-width="200" show-overflow-tooltip /><el-table-column label="状态" width="115"><template #default="{ row }"><TicketTag :value="row.status" /></template></el-table-column><el-table-column label="创建时间" width="190"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><el-table-column width="80"><template #default="{ row }"><el-button link type="primary" @click.stop="router.push(`/${auth.role}/tickets/${row.id}`)">查看</el-button></template></el-table-column></el-table><el-empty v-else description="暂无工单，新的进展会出现在这里" /></section>
  </PageState>
</template>
