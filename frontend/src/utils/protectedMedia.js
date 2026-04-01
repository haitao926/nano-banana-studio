export const isProtectedStaticUrl = (url) => typeof url === 'string' && url.startsWith('/static/')

export const createProtectedMediaLoader = (api) => {
    const objectUrlCache = new Map()

    const revokeUrl = (objectUrl) => {
        if (!objectUrl || !String(objectUrl).startsWith('blob:')) return
        try {
            URL.revokeObjectURL(objectUrl)
        } catch (_) {}
    }

    const revokeAll = () => {
        objectUrlCache.forEach((objectUrl) => revokeUrl(objectUrl))
        objectUrlCache.clear()
    }

    const resolveUrl = async (url) => {
        if (!isProtectedStaticUrl(url)) return url
        const cached = objectUrlCache.get(url)
        if (cached) return cached
        try {
            const res = await api.get(url, { responseType: 'blob' })
            const objectUrl = URL.createObjectURL(res.data)
            objectUrlCache.set(url, objectUrl)
            return objectUrl
        } catch (_) {
            return url
        }
    }

    return {
        resolveUrl,
        revokeUrl,
        revokeAll
    }
}
