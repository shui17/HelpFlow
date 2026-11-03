<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { createTicket } from '../api/tickets.js'
import { errorMessage } from '../utils/error.js'
import TicketForm from '../components/TicketForm.vue'
const router = useRouter(), submitting = ref(false), error = ref('')
async function submit(payload) { submitting.value = true; error.value = ''; try { const ticket = await createTicket(payload); ElMessage.success('工单已创建'); router.replace(`/user/tickets/${ticket.id}`) } catch (err) { error.value = errorMessage(err) } finally { submitting.value = false } }
</script>
<template><div class="page-heading"><div><div class="eyebrow">NEW TICKET</div><h1>创建工单</h1><p class="muted">详细的问题描述，有助于我们更快地提供帮助。</p></div></div><section class="panel form-panel"><el-alert v-if="error" :title="error" type="error" :closable="false" class="space-bottom" /><TicketForm :submitting="submitting" @submit="submit" @cancel="router.push('/user/tickets')" /></section></template>
