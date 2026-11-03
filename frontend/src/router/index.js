import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes.js'
import { useAuthStore } from '../stores/auth.js'
import { routeAccess } from './access.js'

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.path === '/session-unavailable') return true
  try { await auth.initialize() }
  catch { return { path: '/session-unavailable', query: { redirect: to.fullPath } } }
  return routeAccess(to, auth)
})
router.afterEach((to) => { document.title = `${to.meta.title || '客服工单'} · HelpFlow` })
export default router
