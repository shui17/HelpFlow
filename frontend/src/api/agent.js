import request from '../utils/request.js'
export const listTasks = (ticket, before) => request.get(`/tickets/${ticket}/agent-tasks`, { params: { before } })
export const createTask = (ticket, data) => request.post(`/tickets/${ticket}/agent-tasks`, data)
export const getTask = (id) => request.get(`/agent-tasks/${id}`)
export const runTask = (id) => request.post(`/agent-tasks/${id}/run`, {}, { timeout: 330000 })
export const editProposal = (id, version, content) => request.patch(`/agent-tasks/${id}/proposal`, { version, content })
export const confirmProposal = (id, version) => request.post(`/agent-tasks/${id}/confirm`, { version })
export const rejectTask = (id) => request.post(`/agent-tasks/${id}/reject`)
export const cancelTask = (id) => request.post(`/agent-tasks/${id}/cancel`)
