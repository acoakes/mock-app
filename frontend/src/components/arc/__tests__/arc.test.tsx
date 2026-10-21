import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TextField } from '../TextField';
import { Button } from '../Button';
import { DataTable, type Column } from '../DataTable';
import { DetailPanel, type DetailRow } from '../DetailPanel';
import { Badge } from '../Badge';
import { KpiCard } from '../KpiCard';
import { EmptyState } from '../Banner';
import { NavBar } from '../NavBar';

describe('TextField', () => {
  it('renders a native input with the given name (load-bearing)', () => {
    render(
      <TextField name="username" value="" onChange={() => {}} testid="username-input" />,
    );
    const input = document.querySelector('input[name="username"]');
    expect(input).toBeInTheDocument();
    expect(input?.tagName).toBe('INPUT');
    expect(screen.getByTestId('username-input')).toBe(input);
  });
});

describe('Button', () => {
  it('renders a real <button type="submit"> when type is submit', () => {
    render(
      <Button type="submit" testid="login-button">
        Login
      </Button>,
    );
    const btn = screen.getByTestId('login-button');
    expect(btn.tagName).toBe('BUTTON');
    expect(btn).toHaveAttribute('type', 'submit');
  });

  it('fires onClick', () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} testid="b">
        Go
      </Button>,
    );
    screen.getByTestId('b').click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});

interface Row {
  id: number;
  name: string;
}

describe('DataTable', () => {
  const columns: Column<Row>[] = [
    { header: 'ID', cell: (r) => r.id },
    { header: 'Name', cell: (r) => r.name },
  ];

  it('renders a semantic tbody tr per row (page objects count tbody tr)', () => {
    render(
      <DataTable
        columns={columns}
        rows={[
          { id: 1, name: 'a' },
          { id: 2, name: 'b' },
        ]}
        rowKey={(r) => r.id}
        emptyText="empty"
        testid="tbl"
      />,
    );
    const table = screen.getByTestId('tbl');
    expect(table.tagName).toBe('TABLE');
    expect(table.querySelectorAll('tbody tr')).toHaveLength(2);
    // header row is in thead, so it is not counted in tbody tr
    expect(table.querySelectorAll('thead tr')).toHaveLength(1);
  });

  it('renders an empty-state row with its testid when there are no rows', () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        emptyText="No data."
        testid="tbl"
        emptyTestid="pm-file-empty"
      />,
    );
    expect(screen.getByTestId('pm-file-empty')).toBeInTheDocument();
    expect(screen.getByText('No data.')).toBeInTheDocument();
  });
});

describe('DetailPanel', () => {
  it('emits .detail-label/.detail-value with exact label text', () => {
    const rows: DetailRow[] = [
      { label: 'Status', value: 'open' },
      { label: 'Title', value: 'x' },
    ];
    const { container } = render(<DetailPanel testid="rca-detail-panel" rows={rows} />);
    const labels = Array.from(container.querySelectorAll('.detail-label')).map(
      (el) => el.textContent,
    );
    expect(labels).toContain('Status');
    const statusRow = container.querySelector(
      '.detail-row:has(.detail-label) .detail-value',
    );
    expect(statusRow).toBeInTheDocument();
  });
});

describe('Badge', () => {
  it('applies the kind-value class', () => {
    render(<Badge kind="severity" value="HIGH" testid="sev" />);
    expect(screen.getByTestId('sev')).toHaveClass('severity-high');
  });
});

describe('KpiCard', () => {
  it('forwards the kpi testids and renders name + value + unit', () => {
    render(<KpiCard name="Throughput" value="94.2" unit="%" />);
    expect(screen.getByTestId('kpi-card')).toBeInTheDocument();
    expect(screen.getByTestId('kpi-name')).toHaveTextContent('Throughput');
    expect(screen.getByTestId('kpi-value')).toHaveTextContent('94.2%');
  });
});

describe('EmptyState', () => {
  it('renders the empty-state class and forwards testid', () => {
    render(<EmptyState testid="empty-state">nothing</EmptyState>);
    expect(screen.getByTestId('empty-state')).toHaveClass('empty-state');
  });
});

describe('NavBar', () => {
  it('renders the logout control as an <a href="/logout">', () => {
    render(
      <MemoryRouter>
        <NavBar
          brand="Analytics Platform"
          links={[
            { href: '/dashboard', label: 'Dashboard' },
            { href: '/logout', label: 'Logout', logout: true, onClick: () => {} },
          ]}
        />
      </MemoryRouter>,
    );
    const logout = screen.getByText('Logout');
    expect(logout.tagName).toBe('A');
    expect(logout).toHaveAttribute('href', '/logout');
  });
});
