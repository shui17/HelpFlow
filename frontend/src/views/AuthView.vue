<script setup>
import { computed, reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { useAuthStore } from '../stores/auth.js'
import { homePath } from '../constants/index.js'
import { errorMessage } from '../utils/error.js'
const route = useRoute(), router = useRouter(), auth = useAuthStore()
const registering = computed(() => route.path === '/register')
const formRef = ref(), submitting = ref(false), error = ref('')
const form = reactive({ username: '', email: '', password: '', confirm_password: '' })
const rules = computed(() => ({
  username: [{ required: true, min: 2, max: 30, message: '用户名需要 2～30 个字符', trigger: 'blur' }],
  email: [{ required: true, type: 'email', message: '请输入有效邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, ...(registering.value ? [{ min: 8, max: 64, message: '密码需要 8～64 个字符', trigger: 'blur' }, { validator: (_, value, cb) => cb(/\p{L}/u.test(value) && /\p{N}/u.test(value) ? undefined : new Error('密码至少包含一个字母和一个数字')), trigger: 'blur' }] : [])],
  confirm_password: [{ required: true, message: '请再次输入密码', trigger: 'blur' }, { validator: (_, value, cb) => cb(value === form.password ? undefined : new Error('两次密码不一致')), trigger: 'blur' }],
}))
watch(() => route.path, async () => {
  error.value = ''
  Object.assign(form, { username: '', email: '', password: '', confirm_password: '' })
  await nextTick()
  formRef.value?.clearValidate()
})
async function submit() {
  if (submitting.value || !await formRef.value.validate().catch(() => false)) return
  submitting.value = true; error.value = ''
  try {
    if (registering.value) { await auth.register({ ...form }); ElMessage.success('注册成功，请登录'); await router.replace('/login') }
    else {
      await auth.login({ email: form.email.trim(), password: form.password })
      const redirect = route.query.redirect
      await router.replace(typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//') && !['/login', '/register'].includes(redirect.split('?')[0]) ? redirect : homePath(auth.role))
    }
  } catch (err) { error.value = errorMessage(err) }
  finally { form.password = ''; form.confirm_password = ''; submitting.value = false }
}
</script>
<template><div class="auth-page"><section class="auth-story"><div class="brand"><span class="brand-mark">H</span>HelpFlow</div><div><div class="eyebrow">CUSTOMER SUPPORT, SIMPLIFIED</div><h1>每一个问题，<br>都值得被认真解决。</h1><p>从提交到解决，让沟通清晰，让服务有序。</p><div class="story-line"><span>01 提交问题</span><span>02 协作处理</span><span>03 确认解决</span></div></div><small>HelpFlow · 客服工单管理系统</small></section>
  <section class="auth-form-area"><div class="auth-card"><div class="eyebrow">欢迎来到 HELPFLOW</div><h2>{{ registering ? '创建您的账号' : '登录工作空间' }}</h2><p class="muted">{{ registering ? '注册普通用户账号，随时跟进您的问题。' : '登录账号，继续跟进您的工单。' }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="space-bottom" />
    <el-form ref="formRef" :model="form" :rules="rules" :validate-on-rule-change="false" label-position="top" @submit.prevent="submit">
      <el-form-item v-if="registering" label="用户名" prop="username"><el-input v-model.trim="form.username" autocomplete="username" maxlength="30" /></el-form-item>
      <el-form-item label="邮箱" prop="email"><el-input v-model.trim="form.email" type="email" autocomplete="email" maxlength="255" placeholder="you@example.com" /></el-form-item>
      <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password :autocomplete="registering ? 'new-password' : 'current-password'" maxlength="64" /></el-form-item>
      <el-form-item v-if="registering" label="确认密码" prop="confirm_password"><el-input v-model="form.confirm_password" type="password" show-password autocomplete="new-password" maxlength="64" /></el-form-item>
      <el-button type="primary" native-type="submit" class="full-width" :loading="submitting">{{ registering ? '创建账号' : '登录' }}</el-button>
    </el-form><p class="auth-switch">{{ registering ? '已有账号？' : '还没有账号？' }} <router-link :to="registering ? '/login' : '/register'">{{ registering ? '立即登录' : '注册账号' }}</router-link></p>
  </div></section></div></template>
