import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <>
      <h1>Page Not Found</h1>
      <p>The page you requested does not exist.</p>
      <Link to="/dashboard" className="btn btn-secondary">
        ← Back to Dashboard
      </Link>
    </>
  );
}
