"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, BedDouble } from "lucide-react";
import { Appointment } from "@/lib/api";
import styles from "./AppointmentsCalendar.module.css";

const DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const START_HOUR = 7;
const END_HOUR = 20;
const HOUR_HEIGHT = 56; // px

interface ColorInfo {
  bg: string;
  border: string;
  text: string;
  label: string;
}

// Code couleur par statut de prospect (section 42) — une réservation
// hôtelière (room_type renseigné) n'a pas de qualification commerciale,
// traitée à part avec sa propre couleur neutre.
function getColorInfo(appt: Appointment): ColorInfo {
  if (appt.room_type) {
    return { bg: "var(--color-signal-soft)", border: "var(--color-signal)", text: "var(--color-signal)", label: "Réservation" };
  }
  switch (appt.qualification) {
    case "Prospect chaud":
      return { bg: "var(--color-signal-soft)", border: "var(--color-signal)", text: "var(--color-signal)", label: "Prospect chaud" };
    case "Prospect tiède":
      return { bg: "var(--color-amber-soft)", border: "var(--color-amber)", text: "var(--color-amber)", label: "Prospect tiède" };
    case "Pas intéressé":
      return { bg: "var(--color-red-soft)", border: "var(--color-red)", text: "var(--color-red)", label: "Pas intéressé" };
    case "À suivre par un humain":
      return { bg: "var(--color-violet-soft)", border: "var(--color-violet)", text: "var(--color-violet)", label: "À suivre par un humain" };
    default:
      return { bg: "var(--color-bg)", border: "var(--color-line)", text: "var(--color-muted)", label: "Rendez-vous" };
  }
}

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0 = dimanche
  const diff = day === 0 ? -6 : 1 - day; // ramène au lundi
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

interface Props {
  appointments: Appointment[];
  onSelect: (appointment: Appointment) => void;
}

export function AppointmentsCalendar({ appointments, onSelect }: Props) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      return d;
    });
  }, [weekStart]);

  const hours = useMemo(() => {
    const list: number[] = [];
    for (let h = START_HOUR; h < END_HOUR; h++) list.push(h);
    return list;
  }, []);

  const appointmentsByDay = useMemo(() => {
    const map: Record<string, Appointment[]> = {};
    for (const day of days) {
      map[day.toDateString()] = [];
    }
    for (const appt of appointments) {
      if (appt.status === "cancelled") continue;
      const apptDate = new Date(appt.scheduled_at);
      const key = apptDate.toDateString();
      if (map[key]) map[key].push(appt);
    }
    return map;
  }, [appointments, days]);

  const weekLabel = `${days[0].toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} – ${days[6].toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <div className={styles.nav}>
          <button onClick={() => setWeekStart((d) => { const n = new Date(d); n.setDate(n.getDate() - 7); return n; })}>
            <ChevronLeft size={16} />
          </button>
          <button className={styles.todayButton} onClick={() => setWeekStart(startOfWeek(new Date()))}>
            Aujourd'hui
          </button>
          <button onClick={() => setWeekStart((d) => { const n = new Date(d); n.setDate(n.getDate() + 7); return n; })}>
            <ChevronRight size={16} />
          </button>
          <span className={styles.weekLabel}>{weekLabel}</span>
        </div>
        <div className={styles.legend}>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: "var(--color-signal)" }} /> Chaud / Réservation</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: "var(--color-amber)" }} /> Tiède</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: "var(--color-violet)" }} /> À suivre</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: "var(--color-red)" }} /> Pas intéressé</span>
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.timeColumn}>
          <div className={styles.dayHeaderSpacer} />
          {hours.map((h) => (
            <div key={h} className={styles.hourLabel} style={{ height: HOUR_HEIGHT }}>{h}:00</div>
          ))}
        </div>

        {days.map((day, i) => {
          const isToday = day.toDateString() === new Date().toDateString();
          return (
            <div key={day.toDateString()} className={styles.dayColumn}>
              <div className={`${styles.dayHeader} ${isToday ? styles.dayHeaderToday : ""}`}>
                <span className={styles.dayLabel}>{DAY_LABELS[i]}</span>
                <span className={styles.dayNumber}>{day.getDate()}</span>
              </div>
              <div className={styles.dayBody} style={{ height: hours.length * HOUR_HEIGHT }}>
                {hours.map((h) => (
                  <div key={h} className={styles.hourSlot} style={{ height: HOUR_HEIGHT }} />
                ))}
                {(appointmentsByDay[day.toDateString()] || []).map((appt) => {
                  const apptDate = new Date(appt.scheduled_at);
                  const hourFraction = apptDate.getHours() + apptDate.getMinutes() / 60;
                  const top = Math.max(0, (hourFraction - START_HOUR) * HOUR_HEIGHT);
                  const height = Math.max(24, (appt.duration_minutes / 60) * HOUR_HEIGHT);
                  const color = getColorInfo(appt);
                  return (
                    <button
                      key={appt.id}
                      className={styles.appointmentBlock}
                      style={{ top, height, background: color.bg, borderLeft: `3px solid ${color.border}` }}
                      onClick={() => onSelect(appt)}
                      title={`${appt.contact_name || appt.contact_phone} — ${color.label}`}
                    >
                      {appt.room_type && <BedDouble size={11} color={color.text} />}
                      <span className={styles.blockTime} style={{ color: color.text }}>{formatTime(appt.scheduled_at)}</span>
                      <span className={styles.blockName}>{appt.contact_name || appt.contact_phone}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
