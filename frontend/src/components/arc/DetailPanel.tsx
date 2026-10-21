import type { ReactNode } from 'react';

export interface DetailRow {
  label: string;
  value: ReactNode;
  // optional testid applied to the value element (e.g. anomaly-description)
  valueTestid?: string;
  // render the value as a <p> (matches the templates' description/recommendation)
  paragraph?: boolean;
}

export interface DetailPanelProps {
  rows: DetailRow[];
  children?: ReactNode;
  testid?: string;
  className?: string;
}

// Renders .detail-row blocks each with an exact .detail-label text and a
// .detail-value. rca_page.py selects the Status row via
// `.detail-row:has(.detail-label:text-is('Status')) .detail-value`, so the
// label text must be exact.
export function DetailPanel({ rows, children, testid, className }: DetailPanelProps) {
  return (
    <div
      data-testid={testid}
      className={['detail-panel', className ?? ''].filter(Boolean).join(' ')}
    >
      {rows.map((row) => (
        <div className="detail-row" key={row.label}>
          <span className="detail-label">{row.label}</span>
          {row.paragraph ? (
            <p className="detail-value" data-testid={row.valueTestid}>
              {row.value}
            </p>
          ) : (
            <span className="detail-value" data-testid={row.valueTestid}>
              {row.value}
            </span>
          )}
        </div>
      ))}
      {children}
    </div>
  );
}
