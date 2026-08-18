"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, Check, X, Plus, CalendarClock } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Appointment, Contact } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./appointments.module.css";

const STATUS_CLASS: Record<string, string> = {
  scheduled: styles.statusScheduled,
  confirmed: styles.statusConfirmed,
  cancelled: styles.statusCancelled,
  completed: styles.statusCompleted,
};

const STATUS_LABEL: Record<string, string> = {
  scheduled: "À confirmer",
  confirmed: "Confirmé",
  cancelled: "Annulé",
  completed: "Terminé",
};

function formatDay(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

export default function AppointmentsPage() {
  const { currentOrg } = useOrganization();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ contact_id: "", date: "", time: "10:00", duration_minutes: "30", notes: "" });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([api.listAppointments(currentOrg.organization_id), api.listContacts(currentOrg.organization_id)])
      .then(([a, c]) => {
        setAppointments(a);
        setContacts(c);
        if (c.length > 0) setForm((f) => ({ ...f, contact_id: f.contact_id || c[0].id }));
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  function contactLabel(contactId: string): string {
    const c = contacts.find((c) => c.id === contactId);
    if (!c) return "Contact supprimé";
    return [c.first_name, c.last_name].filter(Boolean).join(" ") || c.phone;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.contact_id || !form.date) return;
    setSubmitting(true);
    try {
      const scheduled_at = new Date(`${form.date}T${form.time}:00`).toISOString();
      await api.createAppointment(currentOrg.organization_id, {
        contact_id: form.contact_id,
        scheduled_at,
        duration_minutes: parseInt(form.duration_minutes, 10) || 30,
        notes: form.notes.trim() || undefined,
      });
      setModalOpen(false);
      setForm({ ...form, date: "", notes: "" });
      load();
    } finally {
      setSubmitting(false);
    }
  }

  async function updateStatus(id: string, status: string) {
    if (!currentOrg) return;
    await api.updateAppointment(currentOrg.organization_id, id, { status });
    load();
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  const upcoming = appointments.filter((a) => a.status !== "cancelled" && new Date(a.scheduled_at) >= new Date(new Date().toDateString()));
  const scheduled = appointments.filter((a) => a.status === "scheduled").length;
  const confirmed = appointments.filter((a) => a.status === "confirmed").length;

  const grouped = upcoming.reduce<Record<string, Appointment[]>>((acc, appt) => {
    const day = new Date(appt.scheduled_at).toDateString();
    acc[day] = acc[day] || [];
    acc[day].push(appt);
    return acc;
  }, {});

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Rendez-vous</h1>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)} disabled={contacts.length === 0}>
          <Plus size={14} /> Nouveau rendez-vous
        </button>
      </div>

      <div className={styles.grid}>
        <KpiCard label="À venir" value={upcoming.length} icon={CalendarClock} accent="navy" />
        <KpiCard label="À confirmer" value={scheduled} icon={Clock} accent="amber" />
        <KpiCard label="Confirmés" value={confirmed} icon={Check} accent="signal" />
      </div>

      {loading ? (
        <div className="surface-card">
          <SkeletonRow /><SkeletonRow /><SkeletonRow />
        </div>
      ) : upcoming.length === 0 ? (
        <div className="surface-card">
          <div className={styles.emptyState}>
            <Calendar size={26} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>
              Aucun rendez-vous à venir. Ils apparaissent ici automatiquement quand un appel
              de prospection aboutit à une prise de rendez-vous, ou créez-en un manuellement.
            </p>
          </div>
        </div>
      ) : (
        Object.entries(grouped)
          .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
          .map(([day, items]) => (
            <div key={day} className={styles.dayGroup}>
              <div className={styles.dayLabel}>{formatDay(items[0].scheduled_at)}</div>
              {items
                .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
                .map((appt) => (
                  <div key={appt.id} className={styles.card}>
                    <div className={styles.time}>
                      {formatTime(appt.scheduled_at)}
                      <span className={styles.duration}>{appt.duration_minutes} min</span>
                    </div>
                    <div className={styles.details}>
                      <div className={styles.contactName}>{contactLabel(appt.contact_id)}</div>
                      {appt.notes && <div className={styles.notes}>{appt.notes}</div>}
                    </div>
                    <span className={`${styles.statusTag} ${STATUS_CLASS[appt.status]}`}>
                      {STATUS_LABEL[appt.status] || appt.status}
                    </span>
                    <div className={styles.actions}>
                      {appt.status !== "confirmed" && (
                        <button className={styles.iconButton} title="Confirmer" onClick={() => updateStatus(appt.id, "confirmed")}>
                          <Check size={14} />
                        </button>
                      )}
                      {appt.status !== "cancelled" && (
                        <button className={styles.iconButton} title="Annuler" onClick={() => updateStatus(appt.id, "cancelled")}>
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          ))
      )}

      {modalOpen && (
        <div className={styles.modalOverlay} onClick={() => setModalOpen(false)}>
          <form className={styles.modal} onClick={(e) => e.stopPropagation()} onSubmit={handleCreate}>
            <h2>Nouveau rendez-vous</h2>
            <div className={styles.form}>
              <select value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })} required>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {[c.first_name, c.last_name].filter(Boolean).join(" ") || c.phone}
                  </option>
                ))}
              </select>
              <input type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              <input type="time" required value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
              <input
                type="number"
                min={15}
                step={15}
                placeholder="Durée (minutes)"
                value={form.duration_minutes}
                onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
              />
              <textarea
                rows={3}
                placeholder="Notes (optionnel)"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
            <div className={styles.modalActions}>
              <button type="button" className="btn btn-ghost" onClick={() => setModalOpen(false)}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "Création…" : "Créer le rendez-vous"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
