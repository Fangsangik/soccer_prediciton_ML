import axios from 'axios';

const client = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status: number | undefined = error.response?.status;

    if (!error.response) {
      // Network error or request never sent
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        return Promise.reject(new Error('Request timed out'));
      }
      return Promise.reject(new Error('Unable to connect to server'));
    }

    if (status === 401) {
      localStorage.removeItem('auth_token');
      return Promise.reject(new Error('Session expired, please login again'));
    }

    if (status !== undefined && status >= 500) {
      return Promise.reject(new Error('Server error, please try again'));
    }

    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

export default client;
