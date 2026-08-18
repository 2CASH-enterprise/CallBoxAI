export function Skeleton({ height = 14, width = "100%", radius }: { height?: number; width?: string | number; radius?: number }) {
  return (
    <div
      className="skeleton"
      style={{ height, width, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonRow({ columns = 4 }: { columns?: number }) {
  return (
    <div style={{ display: "flex", gap: 16, padding: "14px 20px", alignItems: "center" }}>
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={i} height={12} width={i === 0 ? "20%" : `${60 / columns}%`} />
      ))}
    </div>
  );
}
