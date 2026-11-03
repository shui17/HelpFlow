<script setup>
import { statuses, priorities, statusColors, priorityColors } from '../constants/index.js'
defineProps({ value: String, priority: Boolean })
</script>
<template><el-tag :type="(priority ? priorityColors : statusColors)[value] || undefined" effect="light" round>{{ (priority ? priorities : statuses)[value] || value }}</el-tag></template>
