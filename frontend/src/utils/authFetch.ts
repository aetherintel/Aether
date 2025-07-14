// utils/authFetch.ts
export function authFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: token ? `Bearer ${token}` : '',
    },
  });
}
