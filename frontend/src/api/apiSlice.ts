import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

// ---------------------------------------------------------------------------
// Wire types — mirror the already-shipped /api responses exactly (api/__init__).
// ---------------------------------------------------------------------------
export type Severity = 'HIGH' | 'MEDIUM' | 'LOW';
export type AnomalyStatus = 'open' | 'acknowledged';
export type RcaStatus = 'open' | 'in_progress' | 'resolved';

export interface Kpi {
  name: string;
  value: string;
  unit: string;
}

export interface Anomaly {
  id: number;
  description: string;
  severity: Severity;
  status: string;
  timestamp: string;
}

export interface RcaRecord {
  id: number;
  title: string;
  status: RcaStatus;
  root_cause: string;
  recommendation: string;
}

export interface ChartDataset {
  labels: string[];
  values: number[];
}

export interface ChartsResponse {
  by_vendor: ChartDataset;
  by_severity: ChartDataset;
  over_time: ChartDataset;
}

export interface PmFile {
  key: string;
  vendor: string;
  size: number;
  stage: string;
  records: number | null;
}

export interface Ticket {
  ticket_id: string;
  ticket_type: string;
  vendor: string;
  window_start: string;
  summary: string;
}

export interface IngestionResponse {
  pm_files: PmFile[];
  tickets: Ticket[];
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  props?: Record<string, unknown>;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: string;
  props?: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SessionResponse {
  authenticated: boolean;
  user?: string;
  mode?: 'live' | 'demo';
  refresh_seconds?: number;
}

export interface LoginResponse {
  authenticated: boolean;
  user?: string;
  error?: string;
}

export interface DashboardResponse {
  kpis: Kpi[];
}

export interface AnomaliesResponse {
  anomalies: Anomaly[];
}

export interface RcaListResponse {
  records: RcaRecord[];
}

export interface DateRangeArg {
  date_from?: string;
  date_to?: string;
}

// ---------------------------------------------------------------------------
// API slice (design §3). Cache-tag invalidation is EXACT per the design:
//  - acknowledge invalidates Anomalies + Anomaly + Charts + Dashboard
//  - updateRcaStatus invalidates RcaList + Rca
// ---------------------------------------------------------------------------
export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
    credentials: 'include',
  }),
  tagTypes: [
    'Dashboard',
    'Charts',
    'Anomalies',
    'Anomaly',
    'RcaList',
    'Rca',
    'RcaGraph',
    'Ingestion',
    'Session',
  ],
  endpoints: (b) => ({
    getSession: b.query<SessionResponse, void>({
      query: () => 'session',
      providesTags: ['Session'],
    }),
    getDashboard: b.query<DashboardResponse, DateRangeArg | void>({
      query: (args) => ({ url: 'dashboard', params: (args ?? {}) as DateRangeArg }),
      providesTags: ['Dashboard'],
    }),
    getCharts: b.query<ChartsResponse, DateRangeArg | void>({
      query: (args) => ({ url: 'charts', params: (args ?? {}) as DateRangeArg }),
      providesTags: ['Charts'],
    }),
    getAnomalies: b.query<AnomaliesResponse, { severity?: string } | void>({
      query: (args) => ({ url: 'anomalies', params: (args ?? {}) as { severity?: string } }),
      providesTags: ['Anomalies'],
    }),
    getAnomaly: b.query<{ anomaly: Anomaly }, number>({
      query: (id) => `anomalies/${id}`,
      providesTags: (_r, _e, id) => [{ type: 'Anomaly', id }],
    }),
    acknowledgeAnomaly: b.mutation<{ id: number; status: string }, number>({
      query: (id) => ({ url: `anomalies/${id}/acknowledge`, method: 'POST' }),
      invalidatesTags: (_r, _e, id) => [
        'Anomalies',
        { type: 'Anomaly', id },
        'Charts',
        'Dashboard',
      ],
    }),
    getRcaList: b.query<RcaListResponse, { status?: string } | void>({
      query: (args) => ({ url: 'rca', params: (args ?? {}) as { status?: string } }),
      providesTags: ['RcaList'],
    }),
    getRca: b.query<{ rca: RcaRecord }, number>({
      query: (id) => `rca/${id}`,
      providesTags: (_r, _e, id) => [{ type: 'Rca', id }],
    }),
    getRcaGraph: b.query<GraphResponse, number>({
      query: (id) => `rca/${id}/graph`,
      providesTags: (_r, _e, id) => [{ type: 'RcaGraph', id }],
    }),
    updateRcaStatus: b.mutation<{ id: number; status: string }, { id: number; status: string }>({
      query: ({ id, status }) => ({ url: `rca/${id}/status`, method: 'POST', body: { status } }),
      invalidatesTags: (_r, _e, { id }) => ['RcaList', { type: 'Rca', id }],
    }),
    login: b.mutation<LoginResponse, { username: string; password: string }>({
      query: (body) => ({ url: 'login', method: 'POST', body }),
      invalidatesTags: ['Session'],
    }),
    logout: b.mutation<{ authenticated: boolean }, void>({
      query: () => ({ url: 'logout', method: 'POST' }),
      invalidatesTags: ['Session'],
    }),
    getIngestion: b.query<IngestionResponse, void>({
      query: () => 'ingestion',
      providesTags: ['Ingestion'],
    }),
  }),
});

export const {
  useGetSessionQuery,
  useGetDashboardQuery,
  useGetChartsQuery,
  useGetAnomaliesQuery,
  useGetAnomalyQuery,
  useAcknowledgeAnomalyMutation,
  useGetRcaListQuery,
  useGetRcaQuery,
  useGetRcaGraphQuery,
  useUpdateRcaStatusMutation,
  useLoginMutation,
  useLogoutMutation,
  useGetIngestionQuery,
} = api;
