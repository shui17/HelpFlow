export const slaLabels = { waiting: '等待首次响应', due_soon: '即将超时', overdue: '已超时', on_time: '按时响应', terminated: '已终止' }
export function slaListTarget(role, sla) {
  return { path: role === 'agent' ? '/agent/tickets/mine' : `/${role}/tickets`, query: { sla } }
}
