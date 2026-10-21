import { Badge, DataTable, type Column } from '@arc';
import { useGetIngestionQuery, type PmFile, type Ticket } from '../api/apiSlice';
import { useLivePolling } from '../features/live/useLiveQuery';
import { TESTIDS } from '../testids';

export default function IngestionPage() {
  const { pollingInterval, mode } = useLivePolling();
  const { data } = useGetIngestionQuery(undefined, { pollingInterval });

  const pmFiles = data?.pm_files ?? [];
  const tickets = data?.tickets ?? [];

  const pmColumns: Column<PmFile>[] = [
    { header: 'File', cell: (f) => f.key },
    { header: 'Vendor', cell: (f) => f.vendor },
    { header: 'Size (bytes)', cell: (f) => f.size },
    { header: 'Stage', cell: (f) => f.stage },
    { header: 'Records', cell: (f) => f.records },
  ];

  const ticketColumns: Column<Ticket>[] = [
    { header: 'Ticket', cell: (t) => t.ticket_id },
    { header: 'Type', cell: (t) => t.ticket_type },
    { header: 'Vendor', cell: (t) => t.vendor },
    { header: 'Window', cell: (t) => t.window_start },
    { header: 'Summary', cell: (t) => t.summary },
  ];

  return (
    <>
      <h1>Live Ingestion Feed</h1>

      {mode === 'live' ? (
        <p className="muted" data-testid={TESTIDS.ingestionLiveNote}>
          Live mode — refreshing periodically.
        </p>
      ) : (
        <p className="muted" data-testid={TESTIDS.ingestionDemoNote}>
          Demo mode — showing sample data (start live mode to see real ingestion).
        </p>
      )}

      <h2>PM Files</h2>
      <DataTable
        columns={pmColumns}
        rows={pmFiles}
        rowKey={(f) => f.key}
        emptyText="No PM files ingested yet."
        testid={TESTIDS.pmFileTable}
        emptyTestid={TESTIDS.pmFileEmpty}
        renderRow={(f) => (
          <tr key={f.key} data-testid={TESTIDS.pmFileRow} data-key={f.key}>
            <td>{f.key}</td>
            <td>{f.vendor}</td>
            <td>{f.size}</td>
            <td data-testid={TESTIDS.pmFileStage}>
              <Badge kind="stage" value={f.stage} />
            </td>
            <td>{f.records ?? '—'}</td>
          </tr>
        )}
      />

      <h2>Incident / Change Tickets</h2>
      <DataTable
        columns={ticketColumns}
        rows={tickets}
        rowKey={(t) => t.ticket_id}
        emptyText="No tickets yet."
        testid={TESTIDS.ticketTable}
        emptyTestid={TESTIDS.ticketEmpty}
        renderRow={(t) => (
          <tr key={t.ticket_id} data-testid={TESTIDS.ticketRow} data-id={t.ticket_id}>
            <td>{t.ticket_id}</td>
            <td data-testid={TESTIDS.ticketType}>
              <Badge kind="ticket" value={t.ticket_type} />
            </td>
            <td>{t.vendor}</td>
            <td>{t.window_start}</td>
            <td>{t.summary}</td>
          </tr>
        )}
      />
    </>
  );
}
