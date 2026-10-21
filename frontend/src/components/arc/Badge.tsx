export type BadgeKind = 'severity' | 'stage' | 'ticket';

export interface BadgeProps {
  kind: BadgeKind;
  // the raw value, e.g. 'HIGH' | 'ingested' | 'incident'. The class is
  // `${kind}-${value.toLowerCase()}` (severity-high, stage-ingested, ...).
  value: string;
  label?: string;
  testid?: string;
  className?: string;
}

// Applies severity-*/stage-*/ticket-* colour classes by kind + value, matching
// the ported CSS and the templates' class names.
export function Badge({ kind, value, label, testid, className }: BadgeProps) {
  const cls = `${kind}-${value.toLowerCase()}`;
  return (
    <span className={[cls, className ?? ''].filter(Boolean).join(' ')} data-testid={testid}>
      {label ?? value}
    </span>
  );
}
