import styles from "./politique.module.css";

export const metadata = {
  title: "Politique de confidentialité — CallBoxAI",
};

export default function PolitiqueConfidentialitePage() {
  return (
    <div className={styles.wrap}>
      <h1 className={styles.title}>Politique de confidentialité</h1>
      <p className={styles.updated}>Dernière mise à jour : septembre 2026</p>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>1. Qui nous sommes</h2>
        <p>
          CallBoxAI est une solution développée par <strong>SAS 2 Cash Enterprise (Holding)</strong>, dont le siège
          social est situé au 1 Rue Hartz Huel, 22500 Kerfot, France, et exploitée sous la marque{" "}
          <strong>Agen'C AI</strong>, basée à Abidjan, Côte d'Ivoire. CallBoxAI fournit une plateforme d'agents
          vocaux intelligents permettant à des entreprises clientes d'automatiser la réception et l'émission
          d'appels téléphoniques (accueil client, prospection commerciale, prise de rendez-vous, service client).
          La présente politique explique comment nous traitons les données personnelles des personnes contactées
          par nos agents, ainsi que celles de nos clients eux-mêmes.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>2. Les appels impliquent une intelligence artificielle</h2>
        <p>
          Les appels passés ou reçus par les agents CallBoxAI sont assurés par une intelligence artificielle, et non
          par un être humain. Cette information est communiquée explicitement dès le début de chaque appel.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>3. Données que nous traitons</h2>
        <ul>
          <li>Identité et coordonnées : nom, numéro de téléphone, adresse email, fonction/entreprise le cas échéant</li>
          <li>Contenu des échanges : enregistrement audio et transcription des appels, messages échangés par WhatsApp ou SMS</li>
          <li>Informations issues des formulaires publicitaires (ex. Facebook Lead Ads), y compris la réponse à toute question de consentement</li>
          <li>Historique de qualification et de suivi commercial (statut, rendez-vous, tickets de support)</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>4. Pourquoi nous traitons ces données</h2>
        <ul>
          <li>Fournir le service demandé par nos clients (répondre à un appel, qualifier un prospect, prendre un rendez-vous)</li>
          <li>Assurer le suivi et la qualité du service (analyse des appels, amélioration des agents)</li>
          <li>Respecter nos obligations légales et démontrer notre conformité</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>5. Base légale</h2>
        <p>
          Pour la prospection commerciale auprès de particuliers (B2C), nous nous appuyons sur le consentement
          préalable et explicite de la personne contactée, recueilli avant tout appel. Pour la prospection auprès
          d'entreprises (B2B) et pour la gestion des demandes entrantes (service client, réservations), nous nous
          appuyons sur l'intérêt légitime de nos clients à développer et gérer leur activité, ou sur l'exécution
          d'une relation contractuelle. Toute personne conserve, dans tous les cas, un droit d'opposition.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>6. Avec qui les données sont partagées</h2>
        <p>Les données sont partagées uniquement avec :</p>
        <ul>
          <li>L'entreprise cliente pour le compte de laquelle l'agent intervient</li>
          <li>Nos sous-traitants techniques strictement nécessaires au fonctionnement du service (fourniture de la voix et de l'intelligence artificielle conversationnelle, opérateurs de téléphonie, messagerie WhatsApp/SMS)</li>
          <li>Meta, lorsque le client utilise l'intégration Facebook Lead Ads, pour la réception des formulaires de prospects</li>
        </ul>
        <p>Nous ne vendons jamais de données personnelles à des tiers.</p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>7. Durée de conservation</h2>
        <ul>
          <li>Enregistrements audio et transcriptions : 6 mois, sauf litige en cours nécessitant une conservation plus longue</li>
          <li>Coordonnées et historique de relation commerciale : durée de la relation avec l'entreprise cliente, puis 3 ans</li>
          <li>Preuve de consentement (le cas échéant) : conservée séparément et durablement, comme preuve en cas de contrôle</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>8. Vos droits</h2>
        <p>Toute personne dont les données sont traitées peut demander :</p>
        <ul>
          <li>L'accès à ses données et une copie de celles-ci</li>
          <li>La rectification de données inexactes</li>
          <li>L'effacement de ses données, dans les limites permises par la loi</li>
          <li>Le retrait de son consentement ou son opposition à être recontacté, à tout moment</li>
        </ul>
        <p>
          Pour exercer ces droits, contactez-nous à l'adresse indiquée à la section 10. Vous pouvez également adresser
          une réclamation à l'autorité de protection des données compétente (par exemple la CNIL en France, ou l'ARTCI
          en Côte d'Ivoire).
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>9. Sécurité</h2>
        <p>
          Nous mettons en œuvre des mesures techniques et organisationnelles raisonnables pour protéger les données
          contre l'accès non autorisé, la perte ou la divulgation, notamment le chiffrement des communications et un
          accès restreint aux données par nos équipes.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>10. Contact</h2>
        <p>
          Pour toute question relative à cette politique ou à vos données personnelles, contactez-nous à :{" "}
          <a href="mailto:contact@callbox-ai.com">contact@callbox-ai.com</a>.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>11. Modifications</h2>
        <p>
          Cette politique peut être mise à jour pour refléter l'évolution de notre service ou de la réglementation
          applicable. La date de dernière mise à jour figure en haut de cette page.
        </p>
      </div>

      <p className={styles.legalMention}>
        © 2026 SAS 2 Cash Enterprise (Holding) — 1 Rue Hartz Huel, 22500 Kerfot, France.
        <br />
        Exploitation : Agen'C AI — Abidjan, Côte d'Ivoire.
      </p>
    </div>
  );
}
