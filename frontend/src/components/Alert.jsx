export default function Alert({ children, variant = "info" }) {
  const role = variant === "error" ? "alert" : "status";

  return (
    <div className={`alert alert-${variant}`} role={role}>
      {children}
    </div>
  );
}
