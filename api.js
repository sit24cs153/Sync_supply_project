import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function getOrCreateDeviceId() {
  let id = localStorage.getItem("syncsupply_device_id");
  if (!id) {
    id = "dev-" + crypto.randomUUID();
    localStorage.setItem("syncsupply_device_id", id);
  }
  return id;
}

const client = axios.create({ baseURL: BASE_URL, timeout: 15000, withCredentials: true });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("syncsupply_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  config.headers["X-Device-Id"] = getOrCreateDeviceId();
  return config;
});

export const api = {
  client,
  getOrCreateDeviceId,

  async startTrial() {
    const device_id = getOrCreateDeviceId();
    const { data } = await client.post("/api/auth/trial", { device_id });
    localStorage.setItem("syncsupply_token", data.access_token);
    localStorage.setItem("syncsupply_user_id", data.user_id);
    return data;
  },

  async requestOtp(identifier) {
    const { data } = await client.post("/api/auth/otp/request", { identifier });
    return data;
  },

  async verifyOtp(identifier, code) {
    const device_id = getOrCreateDeviceId();
    const { data } = await client.post("/api/auth/otp/verify", { identifier, code, device_id });
    localStorage.setItem("syncsupply_token", data.access_token);
    localStorage.setItem("syncsupply_user_id", data.user_id);
    return data;
  },

  logout() {
    localStorage.removeItem("syncsupply_token");
    localStorage.removeItem("syncsupply_user_id");
  },

  getProfile: () => client.get("/api/profile").then((r) => r.data),
  saveProfile: (payload) => client.put("/api/profile", payload).then((r) => r.data),
  getHealth: () => client.get("/api/profile/health").then((r) => r.data),
  saveHealth: (payload) => client.put("/api/profile/health", payload).then((r) => r.data),

  getConsent: () => client.get("/api/profile/consent").then((r) => r.data),
  setConsent: (consent_store_history) => client.put("/api/profile/consent", { consent_store_history }).then((r) => r.data),
  deleteHistory: () => client.delete("/api/profile/history").then((r) => r.data),
  exportMyData: () => client.get("/api/profile/export").then((r) => r.data),
  deleteAccount: () => client.delete("/api/profile/account").then((r) => r.data),

  matchSymptoms: (payload) => client.post("/api/symptoms/match", payload).then((r) => r.data),
  history: () => client.get("/api/symptoms/history").then((r) => r.data),

  nearby: (payload) => client.post("/api/places/nearby", payload).then((r) => r.data),

  listHerbs: () => client.get("/api/reference/herbs").then((r) => r.data),
};

export default api;
