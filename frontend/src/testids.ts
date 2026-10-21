// Single source of truth for data-testid values (design §7). These strings are
// a HARD contract: the BDD Playwright page objects select on them (with CSS /
// structural fallbacks). Every value is harvested character-for-character from
// the existing Jinja templates.
export const TESTIDS = {
  // login
  loginForm: 'login-form',
  usernameInput: 'username-input',
  passwordInput: 'password-input',
  loginButton: 'login-button',
  errorMessage: 'error-message',

  // dashboard
  kpiCard: 'kpi-card',
  kpiName: 'kpi-name',
  kpiValue: 'kpi-value',
  dashboardChart: 'dashboard-chart',
  dateFilterForm: 'date-filter-form',
  dateFrom: 'date-from',
  dateTo: 'date-to',
  applyFilter: 'apply-filter',
  emptyState: 'empty-state',

  // anomalies
  anomalyTable: 'anomaly-table',
  anomalyRow: 'anomaly-row',
  anomalySeverity: 'anomaly-severity',
  anomalyStatus: 'anomaly-status',
  severityFilter: 'severity-filter',
  acknowledgeButton: 'acknowledge-button',
  anomalyDetailPanel: 'anomaly-detail-panel',
  anomalyDescription: 'anomaly-description',

  // rca
  rcaTable: 'rca-table',
  rcaRow: 'rca-row',
  rcaStatus: 'rca-status',
  statusFilter: 'status-filter',
  rcaDetailPanel: 'rca-detail-panel',
  rootCauseDescription: 'root-cause-description',
  recommendationText: 'recommendation-text',
  statusUpdateSelect: 'status-update-select',
  saveStatusButton: 'save-status-button',
  successMessage: 'success-message',
  rcaGraphPanel: 'rca-graph-panel',
  rcaGraph: 'rca-graph',
  rcaGraphUnavailable: 'rca-graph-unavailable',

  // ingestion
  pmFileTable: 'pm-file-table',
  pmFileRow: 'pm-file-row',
  pmFileStage: 'pm-file-stage',
  pmFileEmpty: 'pm-file-empty',
  ticketTable: 'ticket-table',
  ticketRow: 'ticket-row',
  ticketType: 'ticket-type',
  ticketEmpty: 'ticket-empty',
  ingestionLiveNote: 'ingestion-live-note',
  ingestionDemoNote: 'ingestion-demo-note',
} as const;

export type TestId = (typeof TESTIDS)[keyof typeof TESTIDS];
