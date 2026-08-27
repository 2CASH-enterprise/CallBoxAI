"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, Check, X, Plus, CalendarClock, BedDouble, Search, List, LayoutGrid } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Appointment, Contact, AvailabilityOffer } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { SkeletonRow } from "@/components/Skeleton";
import { AppointmentsCalendar } from "@/components/AppointmentsCalendar";
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

function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

export default function AppointmentsPage() {
  const { currentOrg } = useOrganization();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"list" | "calendar">("calendar");
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ contact_id: "", date: "", time: "10:00", duration_minutes: "30", notes: "" });
  const [submitting, setSubmitting] = useState(false);

  // Bloc réservation hôtel (PMS)
  const [pmsOpen, setPmsOpen] = useState(false);
  const [pmsForm, setPmsForm] = useState({ contact_id: "", check_in: "", check_out: "" });
  const [offers, setOffers] = useState<AvailabilityOffer[] | null>(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);
  const [bookingRoomType, setBookingRoomType] = useState<string | null>(null);
  const [pmsMessage, setPmsMessage] = useState<string | null>(null);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([api.listAppointments(currentOrg.organization_id), api.listContacts(currentOrg.organization_id)])
      .then(([a, c]) => {
        setAppointments(a);
        setContacts(c);
        if (c.length > 0) {
          setForm((f) => ({ ...f, contact_id: f.contact_id || c[0].id }));
          setPmsForm((f) => ({ ...f, contact_id: f.contact_id || c[0].id }));
        }
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

  async function handleCheckAvailability(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !pmsForm.check_in || !pmsForm.check_out) return;
    setCheckingAvailability(true);
    setPmsMessage(null);
    try {
      const results = await api.checkPmsAvailability(currentOrg.organization_id, {
        check_in: pmsForm.check_in,
        check_out: pmsForm.check_out,
      });
      setOffers(results);
    } catch {
      setPmsMessage("Dates invalides — vérifiez que le départ est après l'arrivée.");
    } finally {
      setCheckingAvailability(false);
    }
  }

  async function handleBook(roomType: string) {
    if (!currentOrg || !pmsForm.contact_id) return;
    setBookingRoomType(roomType);
    setPmsMessage(null);
    try {
      const reservation = await api.createPmsReservation(currentOrg.organization_id, {
        contact_id: pmsForm.contact_id,
        check_in: pmsForm.check_in,
        check_out: pmsForm.check_out,
        room_type: roomType,
      });
      const notices = [];
      if (reservation.confirmation_email_sent) notices.push("email");
      if (reservation.confirmation_sms_sent) notices.push("SMS");
      const notice = notices.length > 0 ? ` (confirmation envoyée par ${notices.join(" et ")})` : "";
      setPmsMessage(`Réservation confirmée — ${reservation.pms_confirmation_number}${notice}`);
      setOffers(null);
      load();
    } catch {
      setPmsMessage("Cette chambre vient d'être prise — relancez une recherche de disponibilité.");
    } finally {
      setBookingRoomType(null);
    }
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
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ display: "flex", border: "1px solid var(--color-line)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
            <button
              onClick={() => setView("calendar")}
              style={{ padding: "8px 12px", background: view === "calendar" ? "var(--color-navy)" : "transparent", color: view === "calendar" ? "white" : "var(--color-muted)", border: "none" }}
            >
              <LayoutGrid size={14} />
            </button>
            <button
              onClick={() => setView("list")}
              style={{ padding: "8px 12px", background: view === "list" ? "var(--color-navy)" : "transparent", color: view === "list" ? "white" : "var(--color-muted)", border: "none" }}
            >
              <List size={14} />
            </button>
          </div>
          <button className="btn btn-ghost" onClick={() => setPmsOpen((v) => !v)} disabled={contacts.length === 0}>
            <BedDouble size={14} /> Réservation hôtel (PMS)
          </button>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)} disabled={contacts.length === 0}>
            <Plus size={14} /> Nouveau rendez-vous
          </button>
        </div>
      </div>

      {view === "calendar" && !loading && (
        <div style={{ marginBottom: 20 }}>
          <AppointmentsCalendar appointments={appointments} onSelect={setSelectedAppointment} />
        </div>
      )}

      {selectedAppointment && (
        <div className={styles.modalOverlay} onClick={() => setSelectedAppointment(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()} style={{ maxWidth: 380 }}>
            <h2>{selectedAppointment.contact_name || selectedAppointment.contact_phone}</h2>
            <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 4 }}>
              {new Date(selectedAppointment.scheduled_at).toLocaleString("fr-FR", { dateStyle: "full", timeStyle: "short" })}
            </p>
            <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 4 }}>{selectedAppointment.contact_phone}</p>
            {selectedAppointment.qualification && (
              <p style={{ fontSize: 13, marginBottom: 4 }}>Qualification : <strong>{selectedAppointment.qualification}</strong></p>
            )}
            {selectedAppointment.room_type && (
              <p style={{ fontSize: 13, marginBottom: 4 }}>Chambre : {selectedAppointment.room_type}</p>
            )}
            {selectedAppointment.notes && (
              <p style={{ fontSize: 13, color: "var(--color-muted)", marginTop: 10, whiteSpace: "pre-wrap" }}>{selectedAppointment.notes}</p>
            )}
            <div className={styles.modalActions}>
              <button className="btn btn-ghost" onClick={() => setSelectedAppointment(null)}>Fermer</button>
            </div>
          </div>
        </div>
      )}

      {view === "list" && (
      <>
      {pmsOpen && (
        <div className="surface-card" style={{ padding: 20, marginBottom: 20 }}>
          <div className={styles.dayLabel} style={{ marginBottom: 12 }}>Vérifier une disponibilité</div>
          <form onSubmit={handleCheckAvailability} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
            <select value={pmsForm.contact_id} onChange={(e) => setPmsForm({ ...pmsForm, contact_id: e.target.value })}>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {[c.first_name, c.last_name].filter(Boolean).join(" ") || c.phone}
                </option>
              ))}
            </select>
            <input type="date" required value={pmsForm.check_in} onChange={(e) => setPmsForm({ ...pmsForm, check_in: e.target.value })} />
            <span style={{ color: "var(--color-muted)", fontSize: 13 }}>→</span>
            <input type="date" required value={pmsForm.check_out} onChange={(e) => setPmsForm({ ...pmsForm, check_out: e.target.value })} />
            <button type="submit" className="btn btn-primary" disabled={checkingAvailability}>
              <Search size={13} /> {checkingAvailability ? "Recherche…" : "Vérifier"}
            </button>
          </form>

          {pmsMessage && (
            <p style={{ fontSize: 13, color: "var(--color-signal)", marginBottom: 12 }}>{pmsMessage}</p>
          )}

          {offers && (
            offers.length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--color-muted)" }}>Aucune chambre disponible pour ces dates.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {offers.map((offer) => (
                  <div
                    key={offer.room_type}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      border: "1px solid var(--color-line)", borderRadius: "var(--radius-sm)", padding: "10px 14px",
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: 13 }}>{offer.room_type}</strong>
                      <div style={{ fontSize: 12, color: "var(--color-muted)" }}>
                        {offer.rate_per_night} {offer.currency}/nuit · {offer.rooms_available} chambre(s) restante(s) ·
                        total {offer.total_price} {offer.currency}
                      </div>
                    </div>
                    <button className="btn btn-signal" onClick={() => handleBook(offer.room_type)} disabled={bookingRoomType === offer.room_type}>
                      {bookingRoomType === offer.room_type ? "Réservation…" : "Réserver"}
                    </button>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      )}

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
              de prospection aboutit à une prise de rendez-vous, quand une réservation hôtel est
              confirmée, ou créez-en un manuellement.
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
                      {appt.room_type ? formatShortDate(appt.scheduled_at) : formatTime(appt.scheduled_at)}
                      <span className={styles.duration}>
                        {appt.room_type ? (appt.check_out_at ? `→ ${formatShortDate(appt.check_out_at)}` : "") : `${appt.duration_minutes} min`}
                      </span>
                    </div>
                    <div className={styles.details}>
                      <div className={styles.contactName}>
                        {contactLabel(appt.contact_id)}
                        {appt.room_type && (
                          <span style={{ marginLeft: 8, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-violet)" }}>
                            {appt.room_type}
                          </span>
                        )}
                      </div>
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
      </>
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
