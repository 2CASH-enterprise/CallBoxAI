"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth, ApiError } from "@/lib/AuthContext";
import styles from "./register.module.css";

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    organization_name: "",
    organization_country: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        organization_name: form.organization_name,
        organization_country: form.organization_country || undefined,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError("Un compte existe déjà avec cet email.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError("Le mot de passe doit contenir au moins 8 caractères.");
      } else {
        setError("Impossible de créer le compte. Vérifiez que le serveur est joignable.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>●</span>
          CallBoxAI
        </div>
        <h1 className={styles.title}>Créer votre entreprise</h1>
        <p className={styles.subtitle}>Un compte, une entreprise, prêt en une minute.</p>

        {error && <div className={styles.error}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="full_name">Votre nom</label>
            <input
              id="full_name"
              required
              autoFocus
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password">Mot de passe (8 caractères minimum)</label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="organization_name">Nom de l'entreprise</label>
            <input
              id="organization_name"
              required
              value={form.organization_name}
              onChange={(e) => setForm({ ...form, organization_name: e.target.value })}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="organization_country">Pays (optionnel)</label>
            <input
              id="organization_country"
              value={form.organization_country}
              onChange={(e) => setForm({ ...form, organization_country: e.target.value })}
              placeholder="Sénégal"
            />
          </div>
          <button type="submit" className={styles.submit} disabled={submitting}>
            {submitting ? "Création…" : "Créer mon compte"}
          </button>
        </form>

        <p className={styles.switchLink}>
          Déjà un compte ? <Link href="/login">Se connecter</Link>
        </p>
      </div>
    </div>
  );
}
