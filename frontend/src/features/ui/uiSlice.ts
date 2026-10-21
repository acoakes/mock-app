import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type SeverityFilter = '' | 'HIGH' | 'MEDIUM' | 'LOW';
export type RcaStatusFilter = '' | 'open' | 'in_progress' | 'resolved';

export interface UiState {
  anomalySeverityFilter: SeverityFilter;
  rcaStatusFilter: RcaStatusFilter;
  dateFrom: string;
  dateTo: string;
}

const initialState: UiState = {
  anomalySeverityFilter: '',
  rcaStatusFilter: '',
  dateFrom: '',
  dateTo: '',
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setAnomalySeverityFilter(state, action: PayloadAction<SeverityFilter>) {
      state.anomalySeverityFilter = action.payload;
    },
    setRcaStatusFilter(state, action: PayloadAction<RcaStatusFilter>) {
      state.rcaStatusFilter = action.payload;
    },
    setDateRange(state, action: PayloadAction<{ dateFrom: string; dateTo: string }>) {
      state.dateFrom = action.payload.dateFrom;
      state.dateTo = action.payload.dateTo;
    },
  },
});

export const { setAnomalySeverityFilter, setRcaStatusFilter, setDateRange } = uiSlice.actions;
export default uiSlice.reducer;
