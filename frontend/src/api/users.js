import request from '../utils/request.js'
export const getUsers = (params) => request.get('/users', { params })
export const getUserDetail = (id) => request.get(`/users/${id}`)
export const changeUserRole = (id, role) => request.patch(`/users/${id}/role`, { role })
export const changeUserStatus = (id, is_active) => request.patch(`/users/${id}/status`, { is_active })
