export function ticketPermissions(ticket, user) {
  // 退出登录和 401 重定向时，详情组件可能尚未卸载。
  user ??= {}
  const owner = user.role === 'user' && ticket.creator_id === user.id
  const agent = user.role === 'agent' && ticket.assignee_id === user.id
  const unassigned = ticket.status === 'open' && ticket.assignee_id === null
  return {
    edit: owner && unassigned,
    claim: user.role === 'agent' && unassigned,
    assign: user.role === 'admin' && ticket.status !== 'closed',
    reply: (owner || agent) && ticket.status !== 'closed',
    start: agent && ticket.status === 'open',
    resolve: agent && ticket.status === 'in_progress',
    reopen: owner && ticket.status === 'resolved',
    close: owner && ticket.status === 'resolved',
  }
}
