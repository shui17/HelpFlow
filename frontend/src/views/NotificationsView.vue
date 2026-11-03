<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { getNotifications, markNotificationRead } from '../api/notifications.js'
import { getTicketDetail } from '../api/tickets.js'
import { errorMessage, notifyError } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'
import PageState from '../components/PageState.vue'
const router = useRouter(), auth = useAuthStore()
const rows = ref([]), loading = ref(true), error = ref(''), more = ref(false), busy = ref(false)
let poll
async function load(earlier = false) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const result = await getNotifications(earlier ? { before_id: rows.value.at(-1).id } : {})
    rows.value = earlier ? [...rows.value, ...result] : result; more.value = result.length === 20
  } catch (err) { error.value = errorMessage(err) }
  finally { loading.value = false; busy.value = false }
}
async function read(row, open = false) {
  try {
    const updated = await markNotificationRead(row.id); row.read_at = updated.read_at
    window.dispatchEvent(new Event('notifications-read'))
    if (open) { await getTicketDetail(row.ticket_id); await router.push(`/${auth.role}/tickets/${row.ticket_id}`) }
  } catch (err) { notifyError(err) }
}
onMounted(() => { load(); poll = setInterval(() => { if (rows.value.length <= 20) load() }, 30000) })
onUnmounted(() => clearInterval(poll))
</script>
<template>
  <div class="page-heading"><div><h1>站内通知</h1><p class="muted">分配、转交和公开回复的消息记录，每 30 秒刷新。</p></div><el-button :loading="busy" @click="load()">刷新</el-button></div>
  <PageState :loading="loading" :error="error" @retry="load()"><section class="panel">
    <el-empty v-if="!rows.length" description="暂无通知" />
    <div v-for="row in rows" :key="row.id" class="comment">
      <div class="section-heading"><strong>{{ row.message }} · #{{ row.ticket_id }}</strong><el-tag v-if="!row.read_at">未读</el-tag><span v-else class="muted">已读</span></div>
      <p class="muted">{{ formatDate(row.created_at) }}</p>
      <el-button v-if="!row.read_at" @click="read(row)">标记已读</el-button><el-button type="primary" plain @click="read(row, true)">查看工单</el-button>
    </div>
    <el-button v-if="more" :loading="busy" @click="load(true)">加载更早通知</el-button>
  </section></PageState>
</template>
