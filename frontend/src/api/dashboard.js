import request from '../utils/request.js'
export const getDashboardSummary = () => request.get('/tickets/summary')
