import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('../views/Dashboard.vue'),
        },
        {
          path: 'providers',
          name: 'Providers',
          component: () => import('../views/Providers.vue'),
        },
        {
          path: 'pools',
          name: 'Pools',
          component: () => import('../views/Pools.vue'),
        },
        {
          path: 'keys',
          name: 'Keys',
          component: () => import('../views/Keys.vue'),
        },
        {
          path: 'logs',
          name: 'Logs',
          component: () => import('../views/Logs.vue'),
        },
        {
          path: 'stats',
          name: 'Stats',
          component: () => import('../views/Stats.vue'),
        },
        {
          path: 'health',
          name: 'Health',
          component: () => import('../views/Health.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const adminKey = localStorage.getItem('admin_key')
  if (to.name !== 'Login' && !adminKey) {
    return { name: 'Login' }
  }
})

export default router