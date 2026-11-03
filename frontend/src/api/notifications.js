import request from '../utils/request.js'
export const getNotifications = (params) => request.get('/notifications', { params })
export const getUnreadCount = () => request.get('/notifications/unread-count')
export const markNotificationRead = (id) => request.patch(`/notifications/${id}/read`)
