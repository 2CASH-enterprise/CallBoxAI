"use client";

import { useEffect, useState } from "react";
import {
  Phone, PhoneIncoming, PhoneOutgoing, CheckCircle2, UserCheck2,
  Bot, ArrowRight, PhoneCall,
} from "lucide-react";
import Link from "next/link";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Call, Agent } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { SkeletonRow, Skeleton } from "@/components/Skeleton";
import styles from "./dashboard.module.css";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Bonjour";
  if (hour < 18) return "Bon après-midi";
  return "Bonsoir";
}

export default function DashboardPage() {
  const { currentOrg, loading: orgLoading } = useOrganization();
  const [calls, setCalls] = useState<Call[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([api.listCalls(currentOrg.organization_id), api.listAgents(currentOrg.organization_id)])
      .then(([c, a]) => {
        setCalls(c);
        setAgents(a);
      })
      .finally(() => setLoading(false));
  }, [currentOrg]);

  if (orgLoading) {
    return (
      <div>
        <Skeleton height={32} width={280} />
        <div className={styles.grid} style={{ marginTop: 24 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={92} radius={12} />
          ))}
        </div>
      </div>
    );
  }

  if (!currentOrg) {
    return (
      <div className={styles.section}>
        <div className={styles.emptyState}>
          <PhoneCall size={28} strokeWidth={1.5} className={styles.emptyIcon} />
          <p>Aucune organisation pour l'instant. Créez-en une depuis la barre du haut pour commencer.</p>
        </div>
      </div>
    );
  }

  const inbound = calls.filter((c) => c.direction === "inbound").length;
  const outbound = calls.filter((c) => c.direction === "outbound").length;
  const completed = calls.filter((c) => c.status === "completed").length;
  const transferred = calls.filter((c) => c.status === "transferred").length;

  return (
    <div>
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>{greeting()}</p>
          <h1 className={styles.title}>{currentOrg.organization_name}</h1>
        </div>
        <Link href="/calls" className="btn btn-signal">
          <Phone size={14} /> Simuler un appel
        </Link>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Appels au total" value={calls.length} icon={Phone} accent="navy" />
        <KpiCard label="Entrants" value={inbound} icon={PhoneIncoming} accent="signal" />
        <KpiCard label="Sortants" value={outbound} icon={PhoneOutgoing} accent="violet" />
        <KpiCard label="Réussis" value={completed} icon={CheckCircle2} accent="signal" />
        <KpiCard label="Transferts humains" value={transferred} icon={UserCheck2} accent="amber" />
        <KpiCard label="Agents actifs" value={agents.length} icon={Bot} accent="navy" />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span>Derniers appels</span>
          <Link href="/calls" className={styles.seeAll}>
            Tout voir <ArrowRight size={13} />
          </Link>
        </div>
        {loading ? (
          <>
            <SkeletonRow /><SkeletonRow /><SkeletonRow />
          </>
        ) : calls.length === 0 ? (
          <div className={styles.emptyState}>
            <PhoneCall size={28} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>
              Aucun appel pour l'instant. Rendez-vous sur la page « Appels » pour en simuler un
              (mode Mock, sans coût).
            </p>
          </div>
        ) : (
          calls.slice(0, 8).map((call) => (
            <div key={call.id} className={styles.callRow}>
              <span className={`${styles.badge} ${call.direction === "inbound" ? styles.badgeInbound : styles.badgeOutbound}`}>
                {call.direction === "inbound" ? <PhoneIncoming size={12} /> : <PhoneOutgoing size={12} />}
                {call.direction === "inbound" ? "Entrant" : "Sortant"}
              </span>
              <span className={styles.callSummary}>{call.summary || "Sans résumé"}</span>
              <span className={styles.callProvider}>{call.provider}</span>
              <span className={`${styles.callStatus} ${call.status === "transferred" ? styles.callStatusAmber : styles.callStatusSignal}`}>
                <span className={styles.liveDot} />
                {call.status}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
