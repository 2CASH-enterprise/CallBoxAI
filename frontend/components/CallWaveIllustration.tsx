export function CallWaveIllustration() {
  return (
    <svg viewBox="0 0 320 320" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Téléphone recevant un appel">
      <circle cx="160" cy="160" r="140" fill="none" stroke="var(--color-signal)" strokeOpacity="0.14" strokeWidth="1.5">
        <animate attributeName="r" values="70;140" dur="2.4s" repeatCount="indefinite" />
        <animate attributeName="stroke-opacity" values="0.35;0" dur="2.4s" repeatCount="indefinite" />
      </circle>
      <circle cx="160" cy="160" r="140" fill="none" stroke="var(--color-signal)" strokeOpacity="0.14" strokeWidth="1.5">
        <animate attributeName="r" values="70;140" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
        <animate attributeName="stroke-opacity" values="0.35;0" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
      </circle>
      <circle cx="160" cy="160" r="140" fill="none" stroke="var(--color-signal)" strokeOpacity="0.14" strokeWidth="1.5">
        <animate attributeName="r" values="70;140" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
        <animate attributeName="stroke-opacity" values="0.35;0" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
      </circle>

      <circle cx="160" cy="160" r="64" fill="var(--color-navy)" />

      <g transform="translate(133,131)">
        <path
          d="M4 0C1.8 0 0 1.8 0 4v10c0 34.8 28.2 63 63 63h10c2.2 0 4-1.8 4-4V60.6c0-2-1.5-3.7-3.5-4L54 53.4c-1.7-.2-3.4.5-4.4 1.9l-6.3 8.6c-13-6.3-23.6-16.9-29.9-29.9l8.6-6.3c1.4-1 2.1-2.7 1.9-4.4L20.6 3.5c-.3-2-2-3.5-4-3.5H4Z"
          fill="white"
        />
      </g>
    </svg>
  );
}
