import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { DemoCallWidget } from "@/components/DemoCallWidget";
import { CallWaveIllustration } from "@/components/CallWaveIllustration";
import { DashboardPreview } from "@/components/DashboardPreview";
import styles from "./landing.module.css";

const USE_CASES = [
  { title: "Hôtellerie", text: "Réservations en direct, modification, annulation, confirmation par email et SMS — 24h/24, dans la langue du client." },
  { title: "Service client", text: "Répond aux demandes de niveau 1, transfère à un humain quand c'est nécessaire, jamais l'inverse." },
  { title: "Prospection commerciale", text: "Qualifie vos prospects, prend rendez-vous, relance automatiquement jusqu'à conversion." },
  { title: "Télésecrétariat", text: "Décroche au nom de votre entreprise, prend un message clair, transfère au bon service." },
  { title: "Opérateurs télécom", text: "Qualifie, envoie le lien de vérification d'identité du partenaire, relance jusqu'à activation." },
];

const FEATURES = [
  { title: "Multilingue automatique", text: "Détection et bascule entre 55 langues, sans configuration par appel." },
  { title: "Des actions réelles, pas des réponses", text: "L'agent consulte une vraie disponibilité et crée une vraie réservation — pendant l'appel, pas après." },
  { title: "Relances jusqu'à conversion", text: "Un contact intéressé mais pas encore converti est rappelé automatiquement, jusqu'à un plafond que vous définissez." },
  { title: "Disponible en continu", text: "Aucun appel manqué, même la nuit — avec un résumé chaque matin de ce qui s'est passé." },
];

const FAQ = [
  { q: "L'agent peut-il vraiment agir, pas seulement répondre ?", a: "Oui. Selon votre métier, il consulte une disponibilité, crée une réservation, envoie un lien par SMS ou programme un rendez-vous, en direct pendant l'appel." },
  { q: "Faut-il des compétences techniques pour démarrer ?", a: "Non. Vous décrivez votre besoin, nous configurons l'agent avec vous, et il est opérationnel en quelques jours." },
  { q: "Que se passe-t-il si l'agent ne sait pas répondre ?", a: "Vous définissez les cas de transfert vers un opérateur humain — réclamation, urgence, ou toute situation hors de son champ." },
  { q: "Dans quels pays l'agent peut-il répondre ?", a: "La plateforme fonctionne pour des entreprises en France, en Suisse, en Belgique et ailleurs, avec un numéro adapté à votre marché." },
];

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/logo-header.png" alt="CallBoxAI" className={styles.logo} />
        <div className={styles.headerActions}>
          <Link href="/login" className={styles.headerLink}>Connexion</Link>
          <Link href="/register" className={styles.headerCta}>Créer mon compte</Link>
        </div>
      </header>

      <section className={styles.hero}>
        <p className={styles.kicker}>Standard téléphonique intelligent</p>
        <h1 className={styles.h1}>
          Concentrez-vous sur votre métier.
          <span className={styles.accent}>On répond à vos appels.</span>
        </h1>
        <p className={styles.subhead}>
          Un agent vocal qui décroche au nom de votre entreprise, comprend la demande, agit —
          réservation, prise de message, qualification — et vous laisse le dernier mot.
        </p>
        <div className={styles.heroCtas}>
          <Link href="/register" className={styles.primaryBtn}>
            Créer mon compte <ArrowRight size={16} />
          </Link>
          <a href="#cas-usage" className={styles.secondaryBtn}>Voir les cas d'usage</a>
        </div>
        <div className={styles.reassurance}>
          <span className={styles.reassuranceItem}>Configuré avec vous</span>
          <span className={styles.reassuranceItem}>Sans engagement</span>
          <span className={styles.reassuranceItem}>Opérationnel en quelques jours</span>
        </div>
      </section>

      <div className={styles.previewWrap}>
        <div className={styles.preview}>
          <div className={styles.previewInner}>
            <div className={styles.previewLine}>
              <span className={styles.previewSpeaker}>agent</span>
              <span className={styles.previewText}>Bonjour, hôtel Belmont, comment puis-je vous aider ?</span>
            </div>
            <div className={styles.previewLine}>
              <span className={styles.previewSpeakerUser}>client</span>
              <span className={styles.previewText}>Une chambre pour deux, du 12 au 14 septembre ?</span>
            </div>
            <div className={styles.previewLine}>
              <span className={styles.previewSpeaker}>agent</span>
              <span className={styles.previewText}>Il reste une chambre supérieure à 129€/nuit. Je vous la réserve ?</span>
            </div>
          </div>
        </div>
      </div>

      <section className={styles.availabilitySection}>
        <div className={styles.availabilityText}>
          <p className={styles.sectionKicker}>Toujours joignable</p>
          <h2 className={styles.sectionTitle}>Le téléphone sonne. Quelqu'un répond. Toujours.</h2>
          <p className={styles.availabilityBody}>
            Nuit, week-end, jour férié, ligne occupée — l'agent décroche pendant que vous êtes ailleurs,
            et vous transmet ce qui compte vraiment.
          </p>
        </div>
        <div className={styles.availabilityVisual}>
          <CallWaveIllustration />
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className={styles.sectionKicker}>Comment ça marche</p>
          <h2 className={styles.sectionTitle}>Trois étapes, aucune ligne de code</h2>
        </div>
        <div className={styles.steps}>
          <div className={styles.step}>
            <div className={styles.stepNumber}>01</div>
            <div className={styles.stepTitle}>Décrivez votre besoin</div>
            <div className={styles.stepText}>Hôtel, cabinet, commerce, service client — nous configurons l'agent avec vous, adapté à votre métier.</div>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>02</div>
            <div className={styles.stepTitle}>Connectez un numéro</div>
            <div className={styles.stepText}>Le vôtre, ou un numéro dédié — votre agent devient joignable en quelques jours.</div>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>03</div>
            <div className={styles.stepTitle}>L'agent répond, en continu</div>
            <div className={styles.stepText}>Chaque appel est transcrit et remonté dans votre tableau de bord, jour et nuit.</div>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className={styles.sectionKicker}>Le tableau de bord</p>
          <h2 className={styles.sectionTitle}>Vos agents, en un coup d'œil</h2>
        </div>
        <DashboardPreview />
      </section>

      <section className={styles.section} id="cas-usage">
        <div className={styles.sectionHead}>
          <p className={styles.sectionKicker}>Cas d'usage</p>
          <h2 className={styles.sectionTitle}>Un métier, un agent déjà pensé pour lui</h2>
        </div>
        <div className={styles.useCaseList}>
          {USE_CASES.map((uc) => (
            <div key={uc.title} className={styles.useCase}>
              <div className={styles.useCaseTitle}>{uc.title}</div>
              <div className={styles.useCaseText}>{uc.text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className={styles.sectionKicker}>Ce qui change vraiment</p>
          <h2 className={styles.sectionTitle}>Pas juste un répondeur qui parle</h2>
        </div>
        <div className={styles.featureGrid}>
          {FEATURES.map((f, i) => (
            <div key={f.title}>
              <div className={styles.featureIndex}>{String(i + 1).padStart(2, "0")}</div>
              <div className={styles.featureTitle}>{f.title}</div>
              <p className={styles.featureText}>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className={styles.sectionKicker}>Questions fréquentes</p>
          <h2 className={styles.sectionTitle}>Ce qu'on nous demande le plus</h2>
        </div>
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
        <p className={styles.finalCtaText}>Créez votre compte et configurons votre agent ensemble.</p>
        <Link href="/register" className={styles.primaryBtn}>
          Créer mon compte <ArrowRight size={16} />
        </Link>
      </section>

      <footer className={styles.footer}>
        <span>© {new Date().getFullYear()} CallBoxAI</span>
        <span>France · Suisse · Belgique</span>
      </footer>

      <DemoCallWidget />
    </div>
  );
}
