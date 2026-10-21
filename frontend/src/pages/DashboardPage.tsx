import { EmptyState, KpiCard, KpiGrid, DateRangeFilter } from '@arc';
import { useGetChartsQuery, useGetDashboardQuery } from '../api/apiSlice';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { setDateRange } from '../features/ui/uiSlice';
import { useLivePolling } from '../features/live/useLiveQuery';
import { DashboardCharts } from '../charts/DashboardCharts';
import { TESTIDS } from '../testids';

export default function DashboardPage() {
  const dispatch = useAppDispatch();
  const { dateFrom, dateTo } = useAppSelector((s) => s.ui);
  const { pollingInterval } = useLivePolling();

  const params = { date_from: dateFrom, date_to: dateTo };
  const { data: dashboard } = useGetDashboardQuery(params, { pollingInterval });
  const { data: charts } = useGetChartsQuery(params, { pollingInterval });

  const kpis = dashboard?.kpis ?? [];
  const isEmpty = dashboard !== undefined && kpis.length === 0;

  return (
    <>
      <h1>KPI Dashboard</h1>

      <KpiGrid>
        {kpis.map((kpi) => (
          <KpiCard key={kpi.name} name={kpi.name} value={kpi.value} unit={kpi.unit} />
        ))}
      </KpiGrid>

      <DashboardCharts data={charts} />

      <DateRangeFilter
        from={dateFrom}
        to={dateTo}
        onApply={({ from, to }) => dispatch(setDateRange({ dateFrom: from, dateTo: to }))}
      />

      {isEmpty ? (
        <EmptyState testid={TESTIDS.emptyState}>No data available for selected range</EmptyState>
      ) : null}
    </>
  );
}
