const apiUrl = import.meta.env.VITE_API_URL;
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string; // adapt if your backend returns a different structure
  token_type: string;
}

export const keycloakLogin = async (credentials: LoginCredentials): Promise<LoginResponse> => {
  const body = new URLSearchParams();
  body.append('username', credentials.username);
  body.append('password', credentials.password);

  const response = await fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  if (!response.ok) {
    throw new Error('application/json');
  }

  return response.json();
};
