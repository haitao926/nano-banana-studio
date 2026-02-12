import api from './api'

let cachedModels = null
let inflight = null

export const fetchModelCatalog = async () => {
  if (cachedModels) return cachedModels
  if (inflight) return inflight
  inflight = api
    .get('/api/models')
    .then((res) => {
      const models = Array.isArray(res?.data?.models) ? res.data.models : (Array.isArray(res?.data) ? res.data : [])
      cachedModels = models
      return models
    })
    .catch((err) => {
      cachedModels = []
      throw err
    })
    .finally(() => {
      inflight = null
    })
  return inflight
}

export const clearModelCatalogCache = () => {
  cachedModels = null
}
