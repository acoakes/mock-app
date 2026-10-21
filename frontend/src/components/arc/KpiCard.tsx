import { TESTIDS } from '../../testids';

export interface KpiCardProps {
  name: string;
  value: string;
  unit?: string;
  testid?: string;
}

// Mirrors the dashboard KPI card: kpi-card wrapper with kpi-name + kpi-value,
// the unit rendered inline as a .kpi-unit span.
export function KpiCard({ name, value, unit, testid = TESTIDS.kpiCard }: KpiCardProps) {
  return (
    <div className="kpi-card" data-testid={testid}>
      <div className="kpi-name" data-testid={TESTIDS.kpiName}>
        {name}
      </div>
      <div className="kpi-value" data-testid={TESTIDS.kpiValue}>
        {value}
        {unit ? <span className="kpi-unit">{unit}</span> : null}
      </div>
    </div>
  );
}
