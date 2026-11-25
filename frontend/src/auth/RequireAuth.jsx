import useAuth from "./useAuth.js";

export default function RequireAuth({
  children,
  allowedRoles,
  fallback = null,
  loadingFallback = null,
}) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return loadingFallback;
  }

  if (!isAuthenticated) {
    return fallback;
  }

  if (allowedRoles && !allowedRoles.includes(user.rol)) {
    return fallback;
  }

  return children;
}
