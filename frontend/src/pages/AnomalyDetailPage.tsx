import { Link, useParams } from 'react-router-dom';
import { Badge, Button, DetailPanel, PageHeading, type DetailRow } from '@arc';
import { useAcknowledgeAnomalyMutation, useGetAnomalyQuery } from '../api/apiSlice';
import { TESTIDS } from '../testids';

export default function AnomalyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const anomalyId = Number(id);
  const { data, isError } = useGetAnomalyQuery(anomalyId);
  const [acknowledge] = useAcknowledgeAnomalyMutation();

  const backAction = (
    <Link to="/anomalies" className="btn btn-secondary">
      ← Back to Anomalies
    </Link>
  );

  const anomaly = data?.anomaly;
  if (!anomaly) {
    return (
      <>
        <PageHeading title="Anomaly Detail" actions={backAction} />
        {isError ? <p>Anomaly not found.</p> : <p>Loading…</p>}
      </>
    );
  }

  const rows: DetailRow[] = [
    { label: 'ID', value: anomaly.id },
    {
      label: 'Description',
      value: anomaly.description,
      valueTestid: TESTIDS.anomalyDescription,
      paragraph: true,
    },
    { label: 'Severity', value: <Badge kind="severity" value={anomaly.severity} /> },
    { label: 'Status', value: anomaly.status },
    { label: 'Timestamp', value: anomaly.timestamp },
  ];

  return (
    <>
      <PageHeading title="Anomaly Detail" actions={backAction} />
      <DetailPanel testid={TESTIDS.anomalyDetailPanel} rows={rows}>
        <div className="detail-actions">
          <Button
            type="button"
            variant="primary"
            testid={TESTIDS.acknowledgeButton}
            onClick={() => acknowledge(anomaly.id)}
          >
            Acknowledge
          </Button>
        </div>
      </DetailPanel>
    </>
  );
}
