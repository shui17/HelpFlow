<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { useAuthStore } from '../stores/auth.js'
import { errorMessage } from '../utils/error.js'
const auth = useAuthStore(), router = useRouter(), formRef = ref(), submitting = ref(false), error = ref('')
const form = reactive({ current_password: '', new_password: '', confirm_password: '' })
const rules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [{ required: true, min: 8, max: 64, message: '新密码需要 8～64 个字符', trigger: 'blur' }, { validator: (_, value, cb) => cb(/\p{L}/u.test(value) && /\p{N}/u.test(value) ? undefined : new Error('密码至少包含一个字母和一个数字')), trigger: 'blur' }],
  confirm_password: [{ required: true, message: '请再次输入新密码', trigger: 'blur' }, { validator: (_, value, cb) => cb(value && value === form.new_password ? undefined : new Error('两次新密码不一致')), trigger: 'blur' }],
}
async function submit() {
  if (submitting.value || !await formRef.value.validate().catch(() => false)) return
  submitting.value = true; error.value = ''
  try { await auth.changePassword({ ...form }); ElMessage.success('密码已修改，请重新登录'); router.replace('/login') }
  catch (err) { error.value = errorMessage(err) }
  finally { Object.assign(form, { current_password: '', new_password: '', confirm_password: '' }); submitting.value = false }
}
</script>
<template><div class="page-heading"><div><div class="eyebrow">SECURITY</div><h1>修改密码</h1><p class="muted">密码修改成功后，需要重新登录。</p></div></div><section class="panel form-panel"><el-alert v-if="error" :title="error" type="error" :closable="false" class="space-bottom" /><el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit"><el-form-item label="当前密码" prop="current_password"><el-input v-model="form.current_password" type="password" show-password autocomplete="current-password" maxlength="64" /></el-form-item><el-form-item label="新密码" prop="new_password"><el-input v-model="form.new_password" type="password" show-password autocomplete="new-password" maxlength="64" placeholder="8～64 个字符，包含字母和数字" /></el-form-item><el-form-item label="确认新密码" prop="confirm_password"><el-input v-model="form.confirm_password" type="password" show-password autocomplete="new-password" maxlength="64" /></el-form-item><el-button type="primary" native-type="submit" :loading="submitting">保存新密码</el-button></el-form></section></template>
