import { useCallback, useEffect, useMemo, useState } from "react";

import { getCurrentUser, login as loginRequest } from "../api/authService.js";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
  subscribeToTokenChanges,
} from "./tokenStore.js";
import { AuthContext } from "./authContext.js";

export default function AuthProvider({ children }) {
  const [accessToken, setCurrentToken] = useState(getAccessToken);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(
    () =>
      subscribeToTokenChanges((token) => {
        setCurrentToken(token);
        if (!token) {
          setUser(null);
        }
      }),
    [],
  );

  const login = useCallback(async (username, password) => {
    setIsLoading(true);
    setError(null);
    setUser(null);

    try {
      const tokenResponse = await loginRequest(username, password);
      setAccessToken(tokenResponse.access_token);
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (loginError) {
      clearAccessToken();
      setError(loginError);
      throw loginError;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setError(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      return null;
    }

    setIsLoading(true);
    setError(null);
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (refreshError) {
      setError(refreshError);
      throw refreshError;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      error,
      isAuthenticated: Boolean(accessToken && user),
      login,
      logout,
      refreshUser,
    }),
    [accessToken, error, isLoading, login, logout, refreshUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
