<script setup>
import { ref, onMounted } from 'vue'
import { getTicketNotes, createTicketNote } from '../api/tickets.js'
import { errorMessage, notifyError } from '../utils/error.js'
import { formatDate } from '../utils/datetime.js'
import PageState from './PageState.vue'
const props = defineProps({ ticketId: Number, readonly: Boolean })
const rows = ref([]), loading = ref(true), error = ref(''), busy = ref(false), more = ref(false), text = ref('')
async function load(earlier = false) {
  error.value = ''
  try {
    const result = await getTicketNotes(props.ticketId, earlier ? { before_id: rows.value[0].id } : {})
    rows.value = earlier ? [...result, ...rows.value] : result; more.value = result.length === 50
  } catch (err) { error.value = errorMessage(err) }
  finally { loading.value = false }
}
async function send() {
  if (busy.value || !text.value.trim()) return
  busy.value = true
  try { await createTicketNote(props.ticketId, text.value.trim()); text.value = ''; await load() }
  catch (err) { notifyError(err); if ([403, 409].includes(err.response?.status)) await load() }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template><section class="panel"><h2>内部备注</h2><p class="muted">仅当前负责客服和管理员可见。</p>
  <PageState :loading="loading" :error="error" @retry="load()">
    <el-button v-if="more" :disabled="busy" @click="load(true)">加载更早备注</el-button>
    <div v-for="row in rows" :key="row.id" class="comment"><div class="comment-meta"><strong>成员 #{{ row.author_id }}</strong><time>{{ formatDate(row.created_at) }}</time></div><p class="plain-text">{{ row.content }}</p></div>
    <el-empty v-if="!rows.length" description="暂无内部备注" :image-size="70" />
    <el-form v-if="!readonly" label-position="top" @submit.prevent="send"><el-form-item label="添加内部备注"><el-input v-model="text" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item><el-button native-type="submit" :loading="busy" :disabled="!text.trim()">保存内部备注</el-button></el-form>
  </PageState>
</section></template>
