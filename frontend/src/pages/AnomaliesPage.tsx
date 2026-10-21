import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Badge, Button, DataTable, Select, type Column } from '@arc';
import {
  useAcknowledgeAnomalyMutation,
  useGetAnomaliesQuery,
  type Anomaly,
} from '../api/apiSlice';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { setAnomalySeverityFilter, type SeverityFilter } from '../features/ui/uiSlice';
import { useLivePolling } from '../features/live/useLiveQuery';
import { TESTIDS } from '../testids';

const SEVERITY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'HIGH', label: 'HIGH' },
  { value: 'MEDIUM', label: 'MEDIUM' },
  { value: 'LOW', label: 'LOW' },
];

export default function AnomaliesPage() {
  const dispatch = useAppDispatch();
  const [searchParams, setSearchParams] = useSearchParams();
  const severity = useAppSelector((s) => s.ui.anomalySeverityFilter);
  const { pollingInterval } = useLivePolling();

  // Hydrate the ui filter from the query string on load / URL change.
  const urlSeverity = (searchParams.get('severity') ?? '') as SeverityFilter;
  useEffect(() => {
    if (urlSeverity !== severity) {
      dispatch(setAnomalySeverityFilter(urlSeverity));
    }
  }, [urlSeverity, severity, dispatch]);

  const { data } = useGetAnomaliesQuery(
    severity ? { severity } : undefined,
    { pollingInterval },
  );
  const [acknowledge] = useAcknowledgeAnomalyMutation();

  const rows = data?.anomalies ?? [];

  // Applying the filter pushes /anomalies?severity=<value> so the page object's
  // wait_for_url("**/anomalies?*") matches; the ui slice stays in sync via the
  // hydration effect above.
  const onFilterChange = (value: string) => {
    if (value) {
      setSearchParams({ severity: value });
    } else {
      setSearchParams({});
    }
  };

  const columns: Column<Anomaly>[] = [
    { header: 'ID', cell: (r) => r.id },
    { header: 'Description', cell: (r) => r.description },
    { header: 'Severity', cell: (r) => r.severity },
    { header: 'Status', cell: (r) => r.status },
    { header: 'Timestamp', cell: (r) => r.timestamp },
    { header: 'Actions', cell: () => null },
  ];

  return (
    <>
      <h1>Anomaly Detection</h1>

      <div className="filter-section">
        <form className="filter-form" onSubmit={(e) => e.preventDefault()}>
          <Select
            name="severity"
            label="Severity"
            value={severity}
            options={SEVERITY_OPTIONS}
            onChange={(e) => onFilterChange(e.target.value)}
            testid={TESTIDS.severityFilter}
          />
        </form>
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        emptyText="No anomalies."
        testid={TESTIDS.anomalyTable}
        renderRow={(a) => (
          <tr key={a.id} data-testid={TESTIDS.anomalyRow} data-id={a.id}>
            <td>{a.id}</td>
            <td>{a.description}</td>
            <td data-testid={TESTIDS.anomalySeverity}>
              <Badge kind="severity" value={a.severity} />
            </td>
            <td data-testid={TESTIDS.anomalyStatus}>{a.status}</td>
            <td>{a.timestamp}</td>
            <td className="actions-cell">
              {/* Real anchor: a[href^='/anomalies/'] (React Router Link). */}
              <Link to={`/anomalies/${a.id}`} className="btn btn-sm btn-secondary">
                View
              </Link>
              {/* Acknowledge stays on /anomalies; cache invalidation refreshes. */}
              <Button
                sm
                variant="primary"
                testid={TESTIDS.acknowledgeButton}
                onClick={() => acknowledge(a.id)}
              >
                Acknowledge
              </Button>
            </td>
          </tr>
        )}
      />
    </>
  );
}
