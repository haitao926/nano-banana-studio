import api from './api'
import { readUserKeyPools } from '../utils/userKeyPools'

const normalizeService = (value) => {
  const text = String(value || '').trim().toLowerCase()
  if (['image', 'audio', 'video', 'digital_human', 'prompt'].includes(text)) return text
  return ''
}

const inferPlatformFromBaseUrl = (value) => {
  const text = String(value || '').toLowerCase()
  if (text.includes('vectorengine.ai')) return 'vector'
  if (text.includes('dashscope.aliyuncs.com')) return 'bailian'
  if (text.includes('ark.cn-beijing') || text.includes('volcengine')) return 'ark'
  return ''
}

const inferPlatformFromModel = (model) => {
  const text = String(model || '').trim().toLowerCase()
  if (!text) return ''
  if (text.includes('seedream') || text.includes('seedance') || text.includes('doubao') || text.includes('wan2-')) return 'ark'
  if (text.includes('wanx') || text.includes('wan2.')) return 'bailian'
  if (text.includes('veo') || text.includes('sora')) return 'vector'
  return ''
}

const buildUserModels = () => {
  const pools = readUserKeyPools()
  if (!Array.isArray(pools) || !pools.length) return []
  const output = []
  pools.forEach((pool) => {
    const models = Array.isArray(pool.models) ? pool.models : []
    if (!models.length) return
    const services = Array.isArray(pool.services) && pool.services.length ? pool.services : []
    const provider = String(pool.provider || '').trim().toLowerCase()
    const baseUrl = String(pool.base_url || '').trim()
    models.forEach((model) => {
      const modelId = String(model || '').trim()
      if (!modelId) return
      const platform = provider || inferPlatformFromBaseUrl(baseUrl) || inferPlatformFromModel(modelId)
      if (services.length) {
        services.forEach((service) => {
          const normalizedService = normalizeService(service)
          if (!normalizedService) return
          output.push({
            model: modelId,
            label: `${modelId}（个人）`,
            service: normalizedService,
            platform
          })
        })
      } else {
        output.push({
          model: modelId,
          label: `${modelId}（个人）`,
          service: 'image',
          platform
        })
      }
    })
  })
  return output
}

let cachedModels = null
let inflight = null

export const fetchModelCatalog = async () => {
  if (cachedModels) return cachedModels
  if (inflight) return inflight
  inflight = api
    .get('/api/models')
    .then((res) => {
      const models = Array.isArray(res?.data?.models) ? res.data.models : (Array.isArray(res?.data) ? res.data : [])
      const userModels = buildUserModels()
      if (!userModels.length) {
        cachedModels = models
        return models
      }
      const merged = Array.isArray(models) ? [...models] : []
      const seen = new Set(merged.map((item) => `${item?.service || ''}::${item?.model || ''}`))
      userModels.forEach((item) => {
        const key = `${item?.service || ''}::${item?.model || ''}`
        if (!seen.has(key)) {
          seen.add(key)
          merged.push(item)
        }
      })
      cachedModels = merged
      return merged
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
