const STORAGE_KEY = "ARGUS_AUTH_SESSION";


async function requestAuth(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || response.statusText);
  }
  return body;
}


export function saveSession(session) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  return session;
}


export function readStoredSession() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}


export function clearSession() {
  window.localStorage.removeItem(STORAGE_KEY);
}


export async function signIn(credentials) {
  const session = await requestAuth("/api/auth/signin", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  return saveSession(session);
}


export async function signUp(credentials) {
  const session = await requestAuth("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  return saveSession(session);
}


export async function restoreSession() {
  const session = readStoredSession();
  if (!session?.access_token) return null;

  try {
    const body = await requestAuth("/api/auth/session", {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    return saveSession({ ...session, user: body.user });
  } catch {
    clearSession();
    return null;
  }
}


export async function logout(accessToken) {
  if (accessToken) {
    await requestAuth("/api/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    }).catch(() => {});
  }
  clearSession();
}
