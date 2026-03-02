import { defineStore } from 'pinia'
import { ref } from 'vue'
import { clusterApi, type Cluster } from '@/api'

export const useClusterStore = defineStore('cluster', () => {
  const clusters = ref<Cluster[]>([])
  const loading = ref(false)

  async function fetchClusters() {
    loading.value = true
    try {
      const res = await clusterApi.list()
      clusters.value = res.data
      return clusters.value
    } finally {
      loading.value = false
    }
  }

  function getClusterById(id: number) {
    return clusters.value.find((c) => c.id === id)
  }

  return { clusters, loading, fetchClusters, getClusterById }
})
