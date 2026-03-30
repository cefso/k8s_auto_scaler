import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import ClusterListPage from '@/features/clusters/ClusterListPage'
import ClusterDetailPage from '@/features/clusters/ClusterDetailPage'
import WorkloadDetailPage from '@/features/workloads/WorkloadDetailPage'
import ScheduleListPage from '@/features/schedules/ScheduleListPage'
import AuditLogPage from '@/features/audit/AuditLogPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <ClusterListPage />,
      },
      {
        path: 'cluster/:id',
        element: <ClusterDetailPage />,
      },
      {
        path: 'cluster/:clusterId/workload',
        element: <WorkloadDetailPage />,
      },
      {
        path: 'schedules',
        element: <ScheduleListPage />,
      },
      {
        path: 'audit',
        element: <AuditLogPage />,
      },
    ],
  },
])
