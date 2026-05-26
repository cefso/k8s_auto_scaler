import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/features/auth/LoginPage'
import ClusterListPage from '@/features/clusters/ClusterListPage'
import ClusterDetailPage from '@/features/clusters/ClusterDetailPage'
import WorkloadDetailPage from '@/features/workloads/WorkloadDetailPage'
import ScheduleListPage from '@/features/schedules/ScheduleListPage'
import AuditLogPage from '@/features/audit/AuditLogPage'
import UsersPage from '@/features/admin/UsersPage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <ClusterListPage /> },
          { path: 'cluster/:id', element: <ClusterDetailPage /> },
          { path: 'cluster/:clusterId/workload', element: <WorkloadDetailPage /> },
          { path: 'schedules', element: <ScheduleListPage /> },
          { path: 'audit', element: <AuditLogPage /> },
          { path: 'users', element: <UsersPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
