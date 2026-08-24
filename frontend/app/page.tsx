"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Phone, PhoneCall, ArrowRight, Bot, Target, Headphones, BedDouble,
  PhoneIncoming, Smartphone, Globe, KeyRound, RefreshCw, Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import styles from "./landing.module.css";

type CallState = "idle" | "dialing" | "success" | "error";

const USE_CASES = [
  { icon: Target, color: "var(--color-violet)", bg: "var(--color-violet-soft)", title: "Prospection commerciale", text: "Qualifie vos prospects, prend rendez-vous, relance automatiquement jusqu'à conversion." },
  { icon: Headphones, color: "var(--color-amber)", bg: "var(--color-amber-soft)", title: "Service client", text: "Répond aux demandes de niveau 1, transfère à un humain quand c'est nécessaire." },
  { icon: BedDouble, color: "var(--color-signal)", bg: "var(--color-signal-soft)", title: "Réceptionniste hôtel", text: "Réservations en direct, modification, annulation, confirmation par email et SMS." },
  { icon: PhoneIncoming, color: "var(--color-muted)", bg: "var(--color-bg)", title: "Télésecrétariat", text: "Décroche au nom de votre entreprise, prend un message, transfère au bon service." },
  { icon: Smartphone, color: "var(--color-red)", bg: "var(--color-red-soft)", title: "Opérateur télécom", text: "Qualifie, envoie le lien de vérification d'identité du partenaire, relance." },
  { icon: Bot, color: "var(--color-navy)", bg: "var(--color-bg)", title: "Standard téléphonique", text: "Accueil au nom de l'entreprise, orientation, prise de message ou rendez-vous." },
];

const FEATURES = [
  { icon: Globe, title: "Multilingue automatique", text: "Détection et bascule automatique entre 55 langues, sans configuration par appel." },
  { icon: KeyRound, title: "Actions réelles en direct", text: "L'agent consulte une vraie disponibilité, crée une vraie réservation, envoie un vrai lien de vérification — pendant l'appel, pas après." },
  { icon: RefreshCw, title: "Relances jusqu'à conversion", text: "Un contact intéressé mais pas encore converti est automatiquement rappelé, jusqu'à un plafond que vous définissez." },
  { icon: Clock, title: "Disponible 24h/24", text: "Aucun appel manqué, même la nuit ou le week-end — avec un résumé chaque matin de ce qui s'est passé." },
];

const FAQ = [
  { q: "Est-ce que l'agent peut vraiment agir, pas juste répondre ?", a: "Oui — selon votre cas d'usage, l'agent peut consulter une disponibilité, créer une réservation, envoyer un lien par SMS, ou programmer un rendez-vous, en direct pendant l'appel." },
  { q: "Faut-il des compétences techniques pour créer un agent ?", a: "Non. Choisissez un modèle prêt à l'emploi adapté à votre métier, personnalisez le prompt et la voix, et votre agent est opérationnel." },
  { q: "Que se passe-t-il si l'agent ne sait pas répondre ?", a: "Vous définissez les cas de transfert vers un opérateur humain — réclamation, urgence, ou toute situation hors de son champ." },
  { q: "Le numéro de démo va-t-il me rappeler plusieurs fois ?", a: "Non, un seul appel de démonstration par numéro et par jour, pour éviter tout abus." },
];

export default function LandingPage() {
  const [phone, setPhone] = useState("");
  const [callState, setCallState] = useState<CallState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleDemoCall(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim()) return;
    setCallState("dialing");
    setErrorMessage("");
    try {
      await api.requestDemoCall(phone.trim());
      setCallState("success");
    } catch (err) {
      setCallState("error");
      setErrorMessage(err instanceof Error ? err.message : "Échec du déclenchement de l'appel.");
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.logo}>CallBoxAI</span>
        <div className={styles.headerActions}>
          <Link href="/login" className={styles.headerLink}>Connexion</Link>
          <Link href="/register" className={styles.headerCta}>Créer mon agent</Link>
        </div>
      </header>

      <section className={styles.hero}>
        <div>
          <div className={styles.eyebrow}><span className={styles.dot} /> Agents vocaux IA pour l'Afrique francophone</div>
          <h1 className={styles.h1}>Votre standard téléphonique <span>ne dort jamais</span></h1>
          <p className={styles.subhead}>
            Un agent vocal IA qui répond, qualifie, réserve et relance vos clients 24h/24 — en français,
            et dans 54 autres langues si besoin. Composez votre numéro ci-contre, l'agent vous appelle en direct.
          </p>
          <div className={styles.heroCtas}>
            <Link href="/register" className={styles.primaryBtn}>
              Créer mon agent <ArrowRight size={16} />
            </Link>
            <a href="#cas-usage" className={styles.secondaryBtn}>Voir les cas d'usage</a>
          </div>
        </div>

        <div className={styles.callCard}>
          <div className={styles.callCardGlow} />
          <div className={styles.callHeader}>
            <div className={`${styles.callAvatar} ${callState === "dialing" ? styles.ringing : ""}`}>
              <Phone size={18} color="white" />
            </div>
            <div>
              <div className={styles.callTitle}>Testez l'agent CallBoxAI</div>
              <div className={styles.callSubtitle}>appel réel · aucune inscription requise</div>
            </div>
          </div>

          <div className={styles.callBody}>
            {callState === "idle" || callState === "error" ? (
              <form className={styles.callForm} onSubmit={handleDemoCall}>
                <input
                  type="tel"
                  required
                  placeholder="+221 77 000 00 00"
                  className={styles.callInput}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <button type="submit" className={styles.callButton}>
                  Recevoir un appel test
                </button>
                {callState === "error" && <div className={styles.callError}>{errorMessage}</div>}
                <p className={styles.callDisclaimer}>
                  En composant, vous acceptez de recevoir un appel de démonstration de CallBoxAI. Un seul appel par numéro et par jour.
                </p>
              </form>
            ) : callState === "dialing" ? (
              <div className={styles.callStatus}>
                <span className={styles.ringDot} /> Composition en cours vers {phone}…
              </div>
            ) : (
              <div className={styles.callStatus}>
                <PhoneCall size={16} color="var(--color-signal)" /> Vous allez recevoir un appel dans quelques instants !
              </div>
            )}
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionEyebrow}>Comment ça marche</div>
        <h2 className={styles.sectionTitle}>Trois étapes, aucune ligne de code</h2>
        <div className={styles.steps}>
          <div className={styles.step}>
            <div className={styles.stepNumber}>01</div>
            <div className={styles.stepTitle}>Choisissez un modèle</div>
            <div className={styles.stepText}>Hôtel, service client, prospection, télécom… un prompt et des outils déjà adaptés à votre métier.</div>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>02</div>
            <div className={styles.stepTitle}>Connectez un numéro</div>
            <div className={styles.stepText}>Le vôtre, ou un numéro dédié — votre agent devient joignable en quelques minutes.</div>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>03</div>
            <div className={styles.stepTitle}>L'agent répond, 24h/24</div>
            <div className={styles.stepText}>Chaque appel est transcrit, classifié, et remonté dans votre tableau de bord.</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="cas-usage">
        <div className={styles.sectionEyebrow}>Cas d'usage</div>
        <h2 className={styles.sectionTitle}>Un métier, un agent déjà prêt</h2>
        <div className={styles.useCaseGrid}>
          {USE_CASES.map((uc) => (
            <div key={uc.title} className={styles.useCase}>
              <div className={styles.useCaseIcon} style={{ background: uc.bg }}>
                <uc.icon size={19} color={uc.color} strokeWidth={2} />
              </div>
              <div className={styles.useCaseTitle}>{uc.title}</div>
              <div className={styles.useCaseText}>{uc.text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionEyebrow}>Ce qui change vraiment</div>
        <h2 className={styles.sectionTitle}>Pas juste un répondeur qui parle</h2>
        <div className={styles.featureGrid}>
          {FEATURES.map((f) => (
            <div key={f.title} className={styles.feature}>
              <f.icon size={20} color="var(--color-navy)" style={{ marginBottom: 12 }} />
              <div className={styles.featureTitle}>{f.title}</div>
              <div className={styles.featureText}>{f.text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionEyebrow}>Questions fréquentes</div>
        <h2 className={styles.sectionTitle}>Ce qu'on nous demande le plus</h2>
        <div className={styles.faqList}>
          {FAQ.map((item) => (
            <div key={item.q} className={styles.faqItem}>
              <div className={styles.faqQuestion}>{item.q}</div>
              <div className={styles.faqAnswer}>{item.a}</div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.finalCta}>
        <h2 className={styles.finalCtaTitle}>Prêt à ne plus manquer un appel ?</h2>
        <p className={styles.finalCtaText}>Créez votre premier agent en quelques minutes.</p>
        <Link href="/register" className={styles.primaryBtn} style={{ background: "var(--color-signal)", color: "var(--color-navy)" }}>
          Créer mon agent <ArrowRight size={16} />
        </Link>
      </section>

      <footer className={styles.footer}>
        <span>© {new Date().getFullYear()} CallBoxAI</span>
        <span>Fait pour l'Afrique francophone</span>
      </footer>
    </div>
  );
}
