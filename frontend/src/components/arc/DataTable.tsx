import type { ReactNode } from 'react';

export interface Column<T> {
  header: string;
  // render a cell for the row
  cell: (row: T) => ReactNode;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  // optional custom <tr> renderer (lets pages attach data-id / testid / nested
  // action controls). When omitted, a plain row of column cells is rendered.
  renderRow?: (row: T) => ReactNode;
  emptyText: string;
  // testid for the <table> and for the empty-state cell (e.g. pm-file-empty)
  testid?: string;
  emptyTestid?: string;
  className?: string;
}

// Renders a SEMANTIC <table><thead><tr><th>...</thead><tbody><tr>...</tbody></table>.
// The BDD page objects count `tbody tr` and subtract one header row, so a real
// table body is load-bearing. When there are no rows, a single empty <tr> with a
// full-width <td> carrying `emptyTestid` is rendered (ingestion needs
// pm-file-empty / ticket-empty).
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  renderRow,
  emptyText,
  testid,
  emptyTestid,
  className,
}: DataTableProps<T>) {
  return (
    <table
      data-testid={testid}
      className={['data-table', className ?? ''].filter(Boolean).join(' ')}
    >
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.header}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={columns.length} className="empty-state" data-testid={emptyTestid}>
              {emptyText}
            </td>
          </tr>
        ) : (
          rows.map((row) =>
            renderRow ? (
              renderRow(row)
            ) : (
              <tr key={rowKey(row)}>
                {columns.map((col) => (
                  <td key={col.header}>{col.cell(row)}</td>
                ))}
              </tr>
            ),
          )
        )}
      </tbody>
    </table>
  );
}
