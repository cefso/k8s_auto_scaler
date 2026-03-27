/**
 * Vue Router 配置
 *
 * 集群管理、集群详情、定时扩缩容三个主页面
 */
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../views/ClusterList.vue'), meta: { title: '集群' } },
    { path: '/cluster/:id', component: () => import('../views/ClusterDetail.vue'), meta: { title: '集群详情' } },
    { path: '/cluster/:clusterId/workload', component: () => import('../views/WorkloadDetail.vue'), meta: { title: '工作负载详情' } },
    { path: '/schedules', component: () => import('../views/ScheduleList.vue'), meta: { title: '定时扩缩容' } },
  ],
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - K8s Auto Scaler` : 'K8s Auto Scaler'
})

export default router
