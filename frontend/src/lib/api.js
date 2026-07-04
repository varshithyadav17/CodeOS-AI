import axios from "axios";

const BACKEND = import.meta.env.VITE_BACKEND_URL;

export const API = `${BACKEND}/api`;

// Auth is handled entirely via an HttpOnly cookie set by the backend
// (withCredentials sends it automatically). There is no localStorage token:
// storing an auth token in localStorage would be readable by any injected
// script and would defeat the point of using an HttpOnly cookie, so no
// Authorization-header interceptor is used here on purpose.
export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});
