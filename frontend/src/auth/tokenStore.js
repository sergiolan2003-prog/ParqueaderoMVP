let accessToken = null;
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
  notifyListeners();
}

export function clearAccessToken() {
  if (accessToken === null) {
    return;
  }

  accessToken = null;
  notifyListeners();
}

export function subscribeToTokenChanges(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
