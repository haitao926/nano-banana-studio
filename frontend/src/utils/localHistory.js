const DEFAULT_LIMIT = 50

const safeParse = (raw) => {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed
    if (parsed && Array.isArray(parsed.items)) return parsed.items
  } catch (e) {
    return []
  }
  return []
}

export const loadLocalHistory = (key) => {
  if (typeof localStorage === 'undefined') return []
  return safeParse(localStorage.getItem(key))
}

export const saveLocalHistory = (key, items, limit = DEFAULT_LIMIT) => {
  if (typeof localStorage === 'undefined') return Array.isArray(items) ? items : []
  const list = Array.isArray(items) ? items : []
  const trimmed = list.slice(0, Math.max(1, Number(limit) || DEFAULT_LIMIT))
  localStorage.setItem(key, JSON.stringify(trimmed))
  return trimmed
}

export const prependLocalHistory = (key, item, options = {}) => {
  const limit = Number(options.limit) || DEFAULT_LIMIT
  const idResolver = options.idResolver || ((val) => val?.id)
  const list = loadLocalHistory(key)
  const id = idResolver(item)
  const filtered = id ? list.filter((entry) => idResolver(entry) !== id) : list
  return saveLocalHistory(key, [item, ...filtered], limit)
}

export const mergeLocalHistory = (primary, secondary, options = {}) => {
  const idResolver = options.idResolver || ((val) => val?.id || val?.url)
  const map = new Map()
  const addList = (list) => {
    if (!Array.isArray(list)) return
    list.forEach((item) => {
      const key = idResolver(item)
      if (!key) return
      if (!map.has(key)) map.set(key, item)
    })
  }
  addList(primary)
  addList(secondary)
  return Array.from(map.values())
}
