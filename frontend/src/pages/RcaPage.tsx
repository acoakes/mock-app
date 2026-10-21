import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DataTable, Select, type Column } from '@arc';
import { useGetRcaListQuery, type RcaRecord } from '../api/apiSlice';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { setRcaStatusFilter, type RcaStatusFilter } from '../features/ui/uiSlice';
import { useLivePolling } from '../features/live/useLiveQuery';
import { TESTIDS } from '../testids';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'open', label: 'open' },
  { value: 'in_progress', label: 'in_progress' },
  { value: 'resolved', label: 'resolved' },
];

export default function RcaPage() {
  const dispatch = useAppDispatch();
  const [searchParams, setSearchParams] = useSearchParams();
  const status = useAppSelector((s) => s.ui.rcaStatusFilter);
  const { pollingInterval } = useLivePolling();

  const urlStatus = (searchParams.get('status') ?? '') as RcaStatusFilter;
  useEffect(() => {
    if (urlStatus !== status) {
      dispatch(setRcaStatusFilter(urlStatus));
    }
  }, [urlStatus, status, dispatch]);

  const { data } = useGetRcaListQuery(status ? { status } : undefined, { pollingInterval });
  const rows = data?.records ?? [];

  // Applying the filter pushes /rca?status=<value> (wait_for_url("**/rca?*")).
  const onFilterChange = (value: string) => {
    if (value) {
      setSearchParams({ status: value });
    } else {
      setSearchParams({});
    }
  };

  const columns: Column<RcaRecord>[] = [
    { header: 'ID', cell: (r) => r.id },
    { header: 'Title', cell: (r) => r.title },
    { header: 'Status', cell: (r) => r.status },
    { header: 'Actions', cell: () => null },
  ];

  return (
    <>
      <h1>Root Cause Analysis</h1>

      <div className="filter-section">
        <form className="filter-form" onSubmit={(e) => e.preventDefault()}>
          <Select
            name="status"
            label="Status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={(e) => onFilterChange(e.target.value)}
            testid={TESTIDS.statusFilter}
          />
        </form>
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        emptyText="No RCA records."
        testid={TESTIDS.rcaTable}
        renderRow={(r) => (
          <tr key={r.id} data-testid={TESTIDS.rcaRow} data-id={r.id}>
            <td>{r.id}</td>
            <td>{r.title}</td>
            <td data-testid={TESTIDS.rcaStatus}>{r.status}</td>
            <td>
              {/* Real anchor: a[href^='/rca/'] (React Router Link). */}
              <Link to={`/rca/${r.id}`} className="btn btn-sm btn-secondary">
                View
              </Link>
            </td>
          </tr>
        )}
      />
    </>
  );
}
