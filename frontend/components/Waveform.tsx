import styles from "./Waveform.module.css";

/**
 * Élément signature de l'interface : une onde sonore stylisée, rappel direct
 * du produit (agents vocaux). Utilisée avec parcimonie : indicateur "en
 * direct" dans la barre du haut, et accent décoratif à côté des titres.
 */
export function Waveform({ live = false }: { live?: boolean }) {
  return (
    <span className={`${styles.waveform} ${live ? styles.live : ""}`} aria-hidden="true">
      <span className={styles.bar} />
      <span className={styles.bar} />
      <span className={styles.bar} />
      <span className={styles.bar} />
      <span className={styles.bar} />
    </span>
  );
}
