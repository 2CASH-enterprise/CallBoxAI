import { BedDouble, Target, Headphones } from "lucide-react";
import styles from "./DashboardPreview.module.css";

const SAMPLE_AGENTS = [
  { name: "Agent Réceptionniste Hôtel", category: "Hôtellerie", icon: BedDouble, bg: "#E3F8EF", color: "#12B886" },
  { name: "Agent Prospection Commerciale", category: "Prospection", icon: Target, bg: "#EBE9FC", color: "#6E62E5" },
  { name: "Agent Service Client", category: "Service client", icon: Headphones, bg: "#FBF0DF", color: "#E8A23D" },
];

export function DashboardPreview() {
  return (
    <div className={styles.frame}>
      <div className={styles.frameBar}>
        <span className={styles.dot} style={{ background: "#E0554F" }} />
        <span className={styles.dot} style={{ background: "#E8A23D" }} />
        <span className={styles.dot} style={{ background: "#12B886" }} />
        <span className={styles.frameLabel}>Agents IA</span>
      </div>
      <div className={styles.frameBody}>
        {SAMPLE_AGENTS.map((agent) => (
          <div key={agent.name} className={styles.card}>
            <div className={styles.cardTop}>
              <span className={styles.avatar} style={{ background: agent.bg }}>
                <agent.icon size={17} color={agent.color} strokeWidth={2} />
              </span>
              <span className={styles.activeDot} />
            </div>
            <div className={styles.cardName}>{agent.name}</div>
            <div className={styles.cardCategory}>{agent.category}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
