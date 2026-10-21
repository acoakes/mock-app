import { useState, type FormEvent } from 'react';
import { TextField } from './TextField';
import { Button } from './Button';
import { TESTIDS } from '../../testids';

export interface DateRangeFilterProps {
  from: string;
  to: string;
  // called with the applied range when the form is submitted
  onApply: (range: { from: string; to: string }) => void;
}

// The dashboard date filter form (date-filter-form with date-from / date-to /
// apply-filter). Keeps local input state and reports the applied range on
// submit so the page can push it to the ui slice / query string.
export function DateRangeFilter({ from, to, onApply }: DateRangeFilterProps) {
  const [localFrom, setLocalFrom] = useState(from);
  const [localTo, setLocalTo] = useState(to);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onApply({ from: localFrom, to: localTo });
  };

  return (
    <div className="filter-section">
      <h2>Date Filter</h2>
      <form data-testid={TESTIDS.dateFilterForm} className="filter-form" onSubmit={handleSubmit}>
        <TextField
          name="date_from"
          type="date"
          label="From"
          value={localFrom}
          onChange={(e) => setLocalFrom(e.target.value)}
          testid={TESTIDS.dateFrom}
        />
        <TextField
          name="date_to"
          type="date"
          label="To"
          value={localTo}
          onChange={(e) => setLocalTo(e.target.value)}
          testid={TESTIDS.dateTo}
        />
        <Button type="submit" variant="primary" testid={TESTIDS.applyFilter}>
          Apply
        </Button>
      </form>
    </div>
  );
}
