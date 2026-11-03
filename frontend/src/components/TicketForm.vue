<script setup>
import { reactive, ref } from 'vue'
import { priorities, categories } from '../constants/index.js'
const props = defineProps({ initial: Object, submitting: Boolean })
const emit = defineEmits(['submit', 'cancel'])
const formRef = ref()
const form = reactive({ title: props.initial?.title || '', description: props.initial?.description || '', priority: props.initial?.priority || 'normal', category: props.initial?.category || 'other' })
const rules = {
  title: [{ required: true, whitespace: true, message: '请填写工单标题', trigger: 'blur' }, { max: 200, message: '标题最多 200 个字符', trigger: 'blur' }],
  description: [{ required: true, whitespace: true, message: '请描述遇到的问题', trigger: 'blur' }, { max: 5000, message: '描述最多 5000 个字符', trigger: 'blur' }],
}
async function submit() { if (props.submitting || !await formRef.value.validate().catch(() => false)) return; emit('submit', { ...form, title: form.title.trim(), description: form.description.trim() }) }
</script>
<template><el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
  <el-form-item label="工单标题" prop="title"><el-input v-model="form.title" maxlength="200" show-word-limit placeholder="用一句话说明遇到的问题" /></el-form-item>
  <el-form-item label="优先级" prop="priority"><el-select v-model="form.priority"><el-option v-for="(label, value) in priorities" :key="value" :label="label" :value="value" /></el-select></el-form-item>
  <el-form-item label="分类" prop="category"><el-select v-model="form.category"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select></el-form-item>
  <el-form-item label="问题描述" prop="description"><el-input v-model="form.description" type="textarea" :rows="7" maxlength="5000" show-word-limit placeholder="请描述问题现象、发生时间与您尝试过的解决方式。" /></el-form-item>
  <div class="form-actions"><el-button type="primary" native-type="submit" :loading="submitting">{{ initial ? '保存修改' : '提交工单' }}</el-button><el-button :disabled="submitting" @click="emit('cancel')">取消</el-button></div>
</el-form></template>
