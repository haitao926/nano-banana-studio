const STORAGE_KEY = 'user_key_pools'

const PROVIDER_ALIASES = {
  openai: 'openai',
  gpt: 'openai',
  gemini: 'gemini',
  google: 'gemini',
  ark: 'ark',
  volcengine: 'ark',
  volc: 'ark',
  方舟: 'ark',
  火山: 'ark',
  bailian: 'bailian',
  dashscope: 'bailian',
  aliyun: 'bailian',
  qwen: 'bailian',
  wanx: 'bailian',
  other: 'other'
}

const DEFAULT_SERVICES = ['image', 'audio', 'video']

const normalizeServices = (value) => {
  if (!value) return DEFAULT_SERVICES
  if (Array.isArray(value)) return value.map((v) => String(v).trim().toLowerCase()).filter(Boolean)
  return String(value)
    .split(/[,;]+/)
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean)
}

const normalizeModels = (value) => {
  if (!value) return []
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  return String(value)
    .split(/[,;]+/)
    .map((v) => v.trim())
    .filter(Boolean)
}

const normalizeProvider = (value) => {
  if (!value) return ''
  const text = String(value).trim().toLowerCase()
  if (!text || ['any', 'all', '*', '不限'].includes(text)) return ''
  return PROVIDER_ALIASES[text] || text
}

const inferProvider = (model) => {
  if (!model) return ''
  const text = String(model).trim().toLowerCase()
  if (!text) return ''
  if (text.includes('ark') || text.includes('volc') || text.includes('wan2-') || text.includes('doubao') || text.includes('seedance') || text.includes('seedream')) return 'ark'
  if (text.includes('gemini') || text.includes('imagen') || text.includes('veo') || text.includes('sora')) return 'gemini'
  if (text.includes('gpt') || text.includes('openai') || text.startsWith('o1') || text.startsWith('o3') || text.startsWith('o4')) return 'openai'
  if (['bailian', 'dashscope', 'aliyun', 'tongyi', 'qwen', 'wanx', 'wan'].some((t) => text.includes(t))) return 'bailian'
  return ''
}

const normalizePoolItem = (pool) => ({
  key: String(pool?.key || '').trim(),
  base_url: String(pool?.base_url || '').trim(),
  models: normalizeModels(pool?.models),
  services: normalizeServices(pool?.services || pool?.service),
  provider: normalizeProvider(pool?.provider),
  backup_keys: normalizeModels(pool?.backup_keys),
  priority: Number.isFinite(Number(pool?.priority)) ? Number(pool.priority) : 100,
  enabled: pool?.enabled !== false
})

export const readUserKeyPools = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    if (!Array.isArray(data)) return []
    return data.map(normalizePoolItem).filter((p) => p.key)
  } catch (e) {
    return []
  }
}

export const saveUserKeyPools = (pools) => {
  const payload = Array.isArray(pools) ? pools.map(normalizePoolItem) : []
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

const selectFromPools = (pools, service, model) => {
  if (!Array.isArray(pools) || !pools.length) return null
  const reqService = String(service || '').trim().toLowerCase()
  const reqProvider = inferProvider(model)
  const modelLower = model ? String(model).trim().toLowerCase() : ''
  const candidates = pools.filter((pool) => {
    if (!pool.enabled) return false
    if (reqService && !pool.services.includes(reqService)) return false
    if (pool.provider && reqProvider && pool.provider !== reqProvider) return false
    if (pool.models.length && modelLower) {
      return pool.models.some((m) => String(m).trim().toLowerCase() === modelLower)
    }
    return true
  })
  if (!candidates.length) return null
  candidates.sort((a, b) => (a.priority || 100) - (b.priority || 100))
  const first = candidates[0]
  return {
    key: first.key,
    base_url: first.base_url || '',
    provider: first.provider || ''
  }
}

export const selectUserPool = (service, model, poolsOverride) => {
  const pools = Array.isArray(poolsOverride) ? poolsOverride : readUserKeyPools()
  return selectFromPools(pools, service, model)
}

export const selectUserPoolWithFallback = (service, model, options = {}) => {
  let pools = readUserKeyPools()
  if (!pools.length) {
    const legacy = buildLegacyPools()
    if (legacy.length) {
      const normalizedLegacy = legacy.map(normalizePoolItem)
      if (options.migrate) saveUserKeyPools(normalizedLegacy)
      pools = normalizedLegacy
    }
  }
  return selectFromPools(pools, service, model)
}

export const buildLegacyPools = () => {
  const pools = []
  const modelKey = localStorage.getItem('user_model_key')
  if (modelKey) {
    pools.push({
      key: modelKey,
      base_url: localStorage.getItem('user_model_base_url') || '',
      services: ['image'],
      provider: '',
      models: [],
      priority: 10,
      enabled: true
    })
  }
  const videoKey = localStorage.getItem('user_video_key')
  if (videoKey) {
    pools.push({
      key: videoKey,
      base_url: localStorage.getItem('user_video_base_url') || '',
      services: ['video'],
      provider: '',
      models: [],
      priority: 20,
      enabled: true
    })
  }
  const ttsKey = localStorage.getItem('user_tts_key')
  if (ttsKey) {
    pools.push({
      key: ttsKey,
      base_url: '',
      services: ['audio'],
      provider: '',
      models: [],
      priority: 30,
      enabled: true
    })
  }
  return pools
}
