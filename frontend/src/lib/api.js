import axios from "axios";

// Same-origin API by default: Vite proxies locally; nginx proxies in Docker.
const backend = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/+$/, "");
export const API = backend ? `${backend.replace(/\/api$/, "")}/api` : "/api";
export const api = axios.create({ baseURL: API, withCredentials: true, timeout: 120000 });
api.interceptors.response.use((response) => response, (error) => {
  const data = error.response?.data;
  if (data && Array.isArray(data.detail)) {
    data.detail = data.detail.map((item) => `${(item.loc || []).slice(1).join(".")}: ${item.msg}`).join("; ");
  }
  return Promise.reject(error);
});
