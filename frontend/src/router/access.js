import { homePath } from '../constants/index.js'

export function routeAccess(to, auth) {
  if (to.path === '/') return homePath(auth.role)
  if (to.meta.requiresAuth && !auth.isAuthenticated) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) return '/403'
  if (to.meta.guest && auth.isAuthenticated) return homePath(auth.role)
  return true
}
