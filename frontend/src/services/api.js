import axios from 'axios'

const api = axios.create({
  timeout: 600000
})

export default api
