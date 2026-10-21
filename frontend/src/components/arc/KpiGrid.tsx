import type { ReactNode } from 'react';

export interface KpiGridProps {
  children: ReactNode;
  testid?: string;
}

export function KpiGrid({ children, testid }: KpiGridProps) {
  return (
    <div className="kpi-grid" data-testid={testid}>
      {children}
    </div>
  );
}
