const ACCESS_TOKEN_KEY = "access_token";
let accessToken =
  typeof window === "undefined"
    ? null
    : window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
const listeners = new Set();

function notifyListeners() {
  for (const listener of listeners) {
    listener(accessToken);
  }
}

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token;
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  }
  notifyListeners();
}

export function clearAccessToken() {
  if (accessToken === null) {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    }
    return;
  }

  accessToken = null;
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  }
  notifyListeners();
}

export function subscribeToTokenChanges(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
