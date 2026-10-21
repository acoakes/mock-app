import { useEffect, useState, type FormEvent } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Banner, Button, DetailPanel, PageHeading, Select, type DetailRow } from '@arc';
import {
  useGetRcaGraphQuery,
  useGetRcaQuery,
  useUpdateRcaStatusMutation,
} from '../api/apiSlice';
import { RcaGraph } from '../graph/RcaGraph';
import { TESTIDS } from '../testids';

const STATUS_OPTIONS = [
  { value: 'open', label: 'open' },
  { value: 'in_progress', label: 'in_progress' },
  { value: 'resolved', label: 'resolved' },
];

export default function RcaDetailPage() {
  const { id } = useParams<{ id: string }>();
  const rcaId = Number(id);
  const [searchParams, setSearchParams] = useSearchParams();

  const { data, isError } = useGetRcaQuery(rcaId);
  const {
    data: graph,
    isLoading: graphLoading,
    isError: graphError,
  } = useGetRcaGraphQuery(rcaId);
  const [updateStatus] = useUpdateRcaStatusMutation();

  const [statusValue, setStatusValue] = useState('');
  // success-message is shown whenever success=1 is present in the URL (the glob
  // the page object waits for is **success=1**).
  const showSuccess = searchParams.get('success') === '1';

  const rca = data?.rca;
  useEffect(() => {
    if (rca) {
      setStatusValue(rca.status);
    }
  }, [rca]);

  const backAction = (
    <Link to="/rca" className="btn btn-secondary">
      ← Back to RCA
    </Link>
  );

  if (!rca) {
    return (
      <>
        <PageHeading title="RCA Detail" actions={backAction} />
        {isError ? <p>RCA record not found.</p> : <p>Loading…</p>}
      </>
    );
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await updateStatus({ id: rca.id, status: statusValue }).unwrap();
      // HARD contract: navigate to a URL containing success=1 (update_status
      // waits for **success=1**).
      setSearchParams({ success: '1' });
    } catch {
      // leave the form as-is on failure
    }
  };

  const rows: DetailRow[] = [
    { label: 'ID', value: rca.id },
    { label: 'Title', value: rca.title },
    { label: 'Status', value: rca.status },
    {
      label: 'Root Cause',
      value: rca.root_cause,
      valueTestid: TESTIDS.rootCauseDescription,
      paragraph: true,
    },
    {
      label: 'Recommendation',
      value: rca.recommendation,
      valueTestid: TESTIDS.recommendationText,
      paragraph: true,
    },
  ];

  return (
    <>
      <PageHeading title="RCA Detail" actions={backAction} />

      <DetailPanel testid={TESTIDS.rcaDetailPanel} rows={rows}>
        {showSuccess ? (
          <Banner variant="success" testid={TESTIDS.successMessage}>
            Status updated successfully
          </Banner>
        ) : null}

        <div className="detail-actions">
          <h3>Update Status</h3>
          <form className="filter-form" onSubmit={handleSubmit}>
            <Select
              name="status"
              label="Status"
              value={statusValue}
              options={STATUS_OPTIONS}
              onChange={(e) => setStatusValue(e.target.value)}
              testid={TESTIDS.statusUpdateSelect}
            />
            <Button type="submit" variant="primary" testid={TESTIDS.saveStatusButton}>
              Save
            </Button>
          </form>
        </div>
      </DetailPanel>

      <RcaGraph data={graph} isLoading={graphLoading} isError={graphError} />
    </>
  );
}
