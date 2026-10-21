import {
  Chart as ChartJS,
  BarElement,
  ArcElement,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
  type ChartOptions,
} from 'chart.js';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import type { ChartsResponse, ChartDataset } from '../api/apiSlice';
import { TESTIDS } from '../testids';

ChartJS.register(
  BarElement,
  ArcElement,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
);

// Colours ported verbatim from static/dashboard_charts.js.
const PALETTE = ['#2563eb', '#7c3aed', '#1b9e4b', '#e0a73a', '#e06a6a', '#5bc0de'];
const SEVERITY_COLOURS: Record<string, string> = {
  HIGH: '#c0392b',
  MEDIUM: '#e67e22',
  LOW: '#27ae60',
};

const EMPTY: ChartDataset = { labels: [], values: [] };

const barOptions: ChartOptions<'bar'> = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
};

const doughnutOptions: ChartOptions<'doughnut'> = {
  responsive: true,
  plugins: { legend: { position: 'bottom' } },
};

const lineOptions: ChartOptions<'line'> = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
};

export interface DashboardChartsProps {
  data?: ChartsResponse;
}

// Three react-chartjs-2 charts fed by the charts query, inside a container
// carrying data-testid="dashboard-chart" (the dashboard BDD scenario matches
// `[data-testid='dashboard-chart'], canvas`). Fails safe: renders empty charts
// while loading / on error (never crashes).
export function DashboardCharts({ data }: DashboardChartsProps) {
  const byVendor = data?.by_vendor ?? EMPTY;
  const bySeverity = data?.by_severity ?? EMPTY;
  const overTime = data?.over_time ?? EMPTY;

  return (
    <div data-testid={TESTIDS.dashboardChart} className="chart-section">
      <div className="chart-card">
        <h3>Anomalies by Vendor</h3>
        <Bar
          id="chart-by-vendor"
          height={220}
          options={barOptions}
          data={{
            labels: byVendor.labels,
            datasets: [
              {
                label: 'Anomalies',
                data: byVendor.values,
                backgroundColor: byVendor.labels.map((_, i) => PALETTE[i % PALETTE.length]),
              },
            ],
          }}
        />
      </div>
      <div className="chart-card">
        <h3>Anomalies by Severity</h3>
        <Doughnut
          id="chart-by-severity"
          height={220}
          options={doughnutOptions}
          data={{
            labels: bySeverity.labels,
            datasets: [
              {
                data: bySeverity.values,
                backgroundColor: bySeverity.labels.map(
                  (label, i) => SEVERITY_COLOURS[label] || PALETTE[i % PALETTE.length],
                ),
              },
            ],
          }}
        />
      </div>
      <div className="chart-card chart-card-wide">
        <h3>Anomalies Over Time</h3>
        <Line
          id="chart-over-time"
          height={220}
          options={lineOptions}
          data={{
            labels: overTime.labels,
            datasets: [
              {
                label: 'Anomalies',
                data: overTime.values,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37,99,235,0.15)',
                fill: true,
                tension: 0.25,
                pointRadius: 3,
              },
            ],
          }}
        />
      </div>
    </div>
  );
}
