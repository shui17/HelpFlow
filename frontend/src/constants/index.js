export const roles = { user: '普通用户', agent: '客服', admin: '管理员' }
export const statuses = { open: '待处理', in_progress: '处理中', resolved: '已解决', closed: '已关闭' }
export const priorities = { low: '低', normal: '普通', high: '高', urgent: '紧急' }
export const categories = { account: '账号问题', product: '产品问题', payment: '支付问题', technical: '技术问题', other: '其他' }
export const statusColors = { open: 'info', in_progress: 'primary', resolved: 'success', closed: 'info' }
export const priorityColors = { low: 'info', normal: '', high: 'warning', urgent: 'danger' }
export const actions = { created: '创建工单', updated: '编辑工单', cancelled: '撤销工单', claimed: '领取工单', assigned: '分配工单', reassigned: '重新分配', status_changed: '状态变更', reopened: '重新打开', closed: '关闭工单' }
export const homePath = (role) => `/${['user', 'agent', 'admin'].includes(role) ? role : 'user'}/dashboard`
