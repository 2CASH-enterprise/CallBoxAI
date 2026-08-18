import type { LucideIcon } from "lucide-react";
import styles from "./KpiCard.module.css";

type Accent = "signal" | "amber" | "violet" | "red" | "navy";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  accent = "navy",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  accent?: Accent;
}) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.label}>{label}</span>
        {Icon && (
          <span className={`${styles.iconBadge} ${styles[`accent-${accent}`]}`}>
            <Icon size={15} strokeWidth={2.25} />
          </span>
        )}
      </div>
      <span className={styles.value}>{value}</span>
      {hint && <span className={styles.trend}>{hint}</span>}
    </div>
  );
}
