<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { getUsers, changeUserRole, changeUserStatus } from '../api/users.js'
import { useAuthStore } from '../stores/auth.js'
import { roles } from '../constants/index.js'
import { formatDate } from '../utils/datetime.js'
import { confirmAction, notifyError, errorMessage } from '../utils/error.js'
import PageState from '../components/PageState.vue'
import AppPagination from '../components/AppPagination.vue'
const auth = useAuthStore()
const filters = reactive({ keyword: '', role: '', is_active: '' })
const loading = ref(true), error = ref(''), busy = ref(false), items = ref([]), total = ref(0), page = ref(1)
let generation = 0
async function load(target = page.value) {
  const current = ++generation; page.value = target; loading.value = true; error.value = ''
  try { const result = await getUsers({ page: target, page_size: 10, keyword: filters.keyword.trim() || undefined, role: filters.role || undefined, is_active: filters.is_active === '' ? undefined : filters.is_active }); if (generation === current) { items.value = result.items; total.value = result.total } }
  catch (err) { if (generation === current) error.value = errorMessage(err) }
  finally { if (generation === current) loading.value = false }
}
function reset() { Object.assign(filters, { keyword: '', role: '', is_active: '' }); load(1) }
async function change(row, kind) {
  if (busy.value) return
  busy.value = true
  const role = row.role === 'user' ? 'agent' : 'user'
  const message = kind === 'role' ? `将 ${row.username} 的角色调整为${roles[role]}？有未关闭工单的客服无法降级。` : `确认${row.is_active ? '禁用' : '启用'} ${row.username}？${row.is_active ? '禁用后该用户将无法登录和访问系统。' : ''}`
  try {
    if (!await confirmAction(message)) return
    if (kind === 'role') await changeUserRole(row.id, role)
    else await changeUserStatus(row.id, !row.is_active)
    ElMessage.success('用户信息已更新'); await load()
  } catch (err) { notifyError(err); if (err.response?.status === 409) await load() }
  finally { busy.value = false }
}
onMounted(() => load())
</script>
<template><div class="page-heading"><div><div class="eyebrow">PEOPLE</div><h1>用户管理</h1><p class="muted">查看用户角色、账号状态和注册时间。</p></div><el-button @click="load()">刷新列表</el-button></div><section class="panel"><el-form inline class="filter-form" @submit.prevent="load(1)"><el-form-item label="搜索"><el-input v-model="filters.keyword" clearable maxlength="255" placeholder="用户名或邮箱" /></el-form-item><el-form-item label="角色"><el-select v-model="filters.role" clearable placeholder="全部角色"><el-option v-for="(label, value) in roles" :key="value" :value="value" :label="label" /></el-select></el-form-item><el-form-item label="账号状态"><el-select v-model="filters.is_active" clearable placeholder="全部状态"><el-option label="启用" :value="true" /><el-option label="禁用" :value="false" /></el-select></el-form-item><el-form-item><el-button type="primary" native-type="submit">查询</el-button><el-button @click="reset">重置</el-button></el-form-item></el-form>
  <PageState :loading="loading" :error="error" @retry="load()"><el-table v-if="items.length" :data="items"><el-table-column prop="id" label="ID" width="70" /><el-table-column prop="username" label="用户名" min-width="140" /><el-table-column prop="email" label="邮箱" min-width="220" /><el-table-column label="角色" width="110"><template #default="{ row }">{{ roles[row.role] }}</template></el-table-column><el-table-column label="账号状态" width="110"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column><el-table-column label="注册时间" width="185"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="230" fixed="right"><template #default="{ row }"><el-button v-if="row.role !== 'admin'" link type="primary" :disabled="busy" @click="change(row, 'role')">{{ row.role === 'user' ? '设为客服' : '设为普通用户' }}</el-button><el-button link :type="row.is_active ? 'danger' : 'primary'" :disabled="busy || row.id === auth.currentUser.id" @click="change(row, 'status')">{{ row.is_active ? '禁用' : '启用' }}</el-button></template></el-table-column></el-table><el-empty v-else description="没有符合条件的用户" /><AppPagination :page="page" :total="total" @change="load" /></PageState></section></template>
