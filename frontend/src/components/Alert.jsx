import {
  IconAlertTriangle,
  IconCheckCircle,
  IconInfo,
  IconXCircle,
} from "./Icons.jsx";

const variantIcons = {
  error: IconXCircle,
  warning: IconAlertTriangle,
  success: IconCheckCircle,
  info: IconInfo,
};

export default function Alert({ children, variant = "info" }) {
  const role = variant === "error" ? "alert" : "status";
  const Icon = variantIcons[variant] ?? IconInfo;

  return (
    <div className={`alert alert-${variant}`} role={role}>
      <span className="alert-icon">
        <Icon size={18} />
      </span>
      <div className="alert-body">{children}</div>
    </div>
  );
}
