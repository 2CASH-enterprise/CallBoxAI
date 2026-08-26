/**
 * Modèles d'agents prêts à l'emploi (section 41 du cahier des charges).
 * Extraits ici pour être réutilisés à la fois par le client (choix du
 * métier lors d'une demande de création) et par le Super Admin (pré-remplir
 * le formulaire de création réelle) — sans dupliquer ces prompts, calibrés
 * au fil de nombreux tests en conditions réelles.
 */

export interface AgentTemplateFields {
  name: string;
  objective: string;
  system_prompt: string;
  language: string;
  transfer_enabled: boolean;
  transfer_number: string;
  transfer_instructions: string;
  voice_id: string;
  business_hours_start: string;
  business_hours_end: string;
  ticketing_enabled: boolean;
  pms_enabled: boolean;
  kyc_enabled: boolean;
  kyc_link_url: string;
  category: string;
}

export interface AgentTemplate {
  key: string;
  label: string;
  description: string;
  locked?: boolean; // section 41 : "Standard Téléphonique" verrouillé, badge "Bientôt"
  fields: AgentTemplateFields;
}

export const AGENT_TEMPLATES: AgentTemplate[] = [
  {
    key: "prospection",
    label: "Prospection commerciale",
    description: "Qualifie les prospects, prend des rendez-vous, relance jusqu'à conversion.",
    fields: {
      name: "Agent Prospection Commerciale",
      objective: "Qualifier les prospects et prendre des rendez-vous",
      system_prompt:
        "Tu es l'assistant commercial de l'entreprise.\n\n" +
        "Ton objectif est de qualifier les prospects et de prendre des rendez-vous.\n\n" +
        "Tu dois toujours :\n" +
        "- être poli ;\n" +
        "- parler naturellement ;\n" +
        "- poser les questions dans l'ordre : besoin, budget, échéance ;\n" +
        "- ne jamais inventer une information ;\n" +
        "- proposer un rendez-vous dès que le prospect montre de l'intérêt ;\n" +
        "- transférer au responsable commercial lorsqu'une demande dépasse tes compétences " +
        "(négociation tarifaire complexe, réclamation, demande hors sujet).",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+221339000000",
      transfer_instructions: "Négociation tarifaire complexe, réclamation, ou demande hors du champ commercial standard.",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: false,
      pms_enabled: false,
      kyc_enabled: false,
      kyc_link_url: "",
      category: "prospection",
    },
  },
  {
    key: "service_client",
    label: "Service Client",
    description: "Répond aux demandes de niveau 1, escalade si nécessaire.",
    fields: {
      name: "Agent Service Client",
      objective: "Répondre aux demandes de niveau 1 et escalader si besoin",
      system_prompt:
        "Tu es l'assistant du service client de l'entreprise.\n\n" +
        "Ton objectif est de répondre aux questions courantes (horaires, tarifs, suivi de dossier) " +
        "en t'appuyant sur la base de connaissances, et de résoudre les demandes de premier niveau.\n\n" +
        "Tu dois toujours :\n" +
        "- être poli et rassurant, surtout si le client est mécontent ;\n" +
        "- vérifier la base de connaissances avant de répondre ;\n" +
        "- ne jamais inventer une information ;\n" +
        "- consigner clairement le motif de l'appel pour le suivi ;\n" +
        "- transférer au responsable dès que la demande dépasse tes compétences " +
        "(réclamation grave, litige, demande juridique).",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+221339000000",
      transfer_instructions: "Réclamation grave, litige, ou demande dépassant le support de niveau 1.",
      voice_id: "",
      business_hours_start: "08:00",
      business_hours_end: "18:00",
      ticketing_enabled: true,
      pms_enabled: false,
      kyc_enabled: false,
      kyc_link_url: "",
      category: "service_client",
    },
  },
  {
    key: "hotellerie",
    label: "Réceptionniste Hôtel",
    description: "Réservations en direct, modification, annulation, confirmations email/SMS.",
    fields: {
      name: "Agent Réceptionniste Hôtel",
      objective: "Répondre aux demandes des clients et de l'hôtel, prendre les réservations, transférer si besoin",
      system_prompt:
        "Tu es la réceptionniste virtuelle de l'hôtel.\n\n" +
        "Ton objectif est de répondre aux demandes des clients (informations, réservations, questions " +
        "pratiques) et de transférer à la réception physique quand une intervention humaine est nécessaire.\n\n" +
        "RÈGLES ABSOLUES, jamais négociables :\n" +
        "- Tu ne dis JAMAIS qu'une réservation est confirmée sans avoir reçu un vrai numéro de confirmation " +
        "de l'outil de réservation. Si l'outil échoue ou renvoie une erreur, explique honnêtement le problème " +
        "au client (ex. \"cette date semble déjà passée, pouvez-vous préciser l'année ?\") — n'invente JAMAIS " +
        "une confirmation, même pour paraître serviable.\n" +
        "- Tu ne dis JAMAIS qu'un email ou un SMS de confirmation a été envoyé sans que l'outil te l'ait " +
        "confirmé explicitement.\n" +
        "- Quand un client donne une date sans préciser l'année, demande-lui de confirmer l'année avant " +
        "de vérifier la disponibilité — ne suppose jamais l'année toi-même.\n\n" +
        "Tu dois toujours :\n" +
        "- accueillir chaleureusement, en français ou en anglais selon la langue du client ;\n" +
        "- t'appuyer sur la base de connaissances pour les horaires, tarifs, équipements, politique d'annulation ;\n" +
        "- ne jamais inventer une disponibilité ou un tarif que tu ne connais pas ;\n" +
        "- proposer une réservation dès que le client exprime une intention claire de dates (avec l'année confirmée) ;\n" +
        "- demander l'adresse email du client avant de finaliser la réservation, pour lui envoyer sa confirmation " +
        "(s'il refuse de la donner, continue quand même la réservation sans email) ;\n" +
        "- IMPORTANT : une fois l'email donné, le RÉPÉTER en l'épelant lettre par lettre (\"a comme Alice, " +
        "b comme Bertrand...\") et demander confirmation explicite avant de finaliser — les adresses email sont " +
        "difficiles à comprendre à l'oral, ne jamais l'utiliser sans cette confirmation ;\n" +
        "- IMPORTANT : demande aussi le numéro de téléphone du client, et RÉPÈTE-le chiffre par chiffre " +
        "(\"zéro, sept, huit, trois...\") pour confirmation explicite avant de finaliser — comme pour l'email, " +
        "un numéro mal compris à l'oral est fréquent, ne jamais l'utiliser sans cette confirmation ; assure-toi " +
        "qu'il comporte bien 10 chiffres avant de le considérer complet ;\n" +
        "- si le client veut modifier ou annuler une réservation existante, retrouve-la d'abord avec son numéro " +
        "de téléphone, confirme les détails avec lui avant toute modification ou annulation ;\n" +
        "- transférer à la réception uniquement pour une réclamation ou une demande urgente " +
        "(problème dans la chambre, sécurité) — pas pour une simple modification de réservation, que tu peux gérer toi-même ;\n" +
        "- rester concise, les clients appellent souvent depuis leur téléphone en déplacement.",
      language: "multi",
      transfer_enabled: true,
      transfer_number: "+33100000000",
      transfer_instructions: "Réclamation, ou demande urgente (problème dans la chambre, sécurité).",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: true,
      pms_enabled: true,
      kyc_enabled: false,
      kyc_link_url: "",
      category: "hotellerie",
    },
  },
  {
    key: "telesecretariat",
    label: "Standard Téléphonique",
    description: "Accueil au nom de l'entreprise, orientation, prise de message ou rendez-vous.",
    locked: true,
    fields: {
      name: "Standard Téléphonique",
      objective: "Accueillir les appels au nom de l'entreprise, orienter, prendre message ou rendez-vous",
      system_prompt:
        "Tu es le standard téléphonique virtuel de l'entreprise. Tu décroches au nom de l'entreprise et " +
        "remplaces l'accueil téléphonique traditionnel.\n\n" +
        "Ton objectif est de comprendre la demande de l'appelant, répondre aux questions fréquentes grâce " +
        "à la base de connaissances, transférer vers la bonne personne si nécessaire, prendre un message " +
        "si personne n'est disponible, et proposer un rendez-vous si la demande s'y prête.\n\n" +
        "Tu dois toujours :\n" +
        "- décrocher en te présentant au nom de l'entreprise ;\n" +
        "- identifier rapidement le motif de l'appel ;\n" +
        "- répondre aux questions courantes à partir de la base de connaissances ;\n" +
        "- transférer vers la bonne personne ou le bon service quand la demande le nécessite ;\n" +
        "- prendre un message clair si personne n'est disponible pour répondre ;\n" +
        "- proposer un rendez-vous si la demande s'y prête ;\n" +
        "- ne jamais inventer une information (tarif, disponibilité, personne) que tu ne connais pas.",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+33100000000",
      transfer_instructions: "Demande nécessitant l'intervention d'un salarié précis, ou urgence.",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: true,
      pms_enabled: false,
      kyc_enabled: false,
      kyc_link_url: "",
      category: "telesecretariat",
    },
  },
  {
    key: "telecom",
    label: "Opérateur Télécom",
    description: "Qualifie, programme l'activation, envoie le lien KYC, relance jusqu'à conversion.",
    fields: {
      name: "Agent Opérateur Télécom",
      objective: "Qualifier, programmer l'activation, envoyer le lien KYC, et relancer jusqu'à conversion",
      system_prompt:
        "Tu es l'assistant commercial d'un opérateur de téléphonie mobile. Tu appelles TOI-MÊME des prospects " +
        "(prospection sortante) — ce n'est pas eux qui t'appellent.\n\n" +
        "Ton objectif suit ce parcours : qualifier le besoin du client (acquisition), déterminer s'il est " +
        "prêt à activer une offre ou un service (conversion), envoyer le lien de vérification d'identité " +
        "(KYC) une fois qu'il confirme vouloir avancer (activation).\n\n" +
        "IMPORTANT sur l'ouverture de l'appel : comme c'est TOI qui appelles, ne commence JAMAIS par " +
        "\"Comment puis-je vous aider ?\" (ça n'a de sens que si le client t'appelle). Présente-toi, dis " +
        "clairement de la part de qui tu appelles, et explique en une phrase la raison de l'appel " +
        "(ex. \"Bonjour, je vous appelle de la part de [opérateur] au sujet de nos offres mobile money, " +
        "avez-vous deux minutes ?\").\n\n" +
        "Tu dois toujours :\n" +
        "- ouvrir l'appel de façon proactive comme décrit ci-dessus, jamais de façon réactive ;\n" +
        "- t'appuyer sur la base de connaissances pour les tarifs et conditions des offres ;\n" +
        "- ne jamais inventer un tarif ou une condition que tu ne connais pas ;\n" +
        "- dès que le client confirme vouloir activer, demander son numéro de téléphone (répète-le chiffre " +
        "par chiffre pour confirmation), puis envoyer le lien KYC du partenaire par SMS ;\n" +
        "- expliquer clairement que ce lien lui permet de finaliser sa vérification d'identité chez le partenaire ;\n" +
        "- si le client hésite ou n'a pas le temps, proposer un rappel plutôt que d'insister ;\n" +
        "- transférer à un conseiller humain pour toute réclamation ou situation que tu ne peux pas résoudre.",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+221339000000",
      transfer_instructions: "Réclamation, litige sur facturation, ou situation ne pouvant pas être résolue par l'agent.",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: true,
      pms_enabled: false,
      kyc_enabled: true,
      kyc_link_url: "",
      category: "telecom",
    },
  },
  {
    key: "generique",
    label: "Générique",
    description: "Point de départ neutre, à décrire librement dans votre demande.",
    fields: {
      name: "Agent",
      objective: "",
      system_prompt: "",
      language: "fr",
      transfer_enabled: false,
      transfer_number: "",
      transfer_instructions: "",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: false,
      pms_enabled: false,
      kyc_enabled: false,
      kyc_link_url: "",
      category: "generique",
    },
  },
];
