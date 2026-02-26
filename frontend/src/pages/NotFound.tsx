import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="dashboard">
      <div className="not-found">
        <h1>404</h1>
        <h2>Page Not Found</h2>
        <p>The page you are looking for does not exist.</p>
        <Link to="/" className="btn btn-primary">
          Back to Discovery
        </Link>
      </div>
    </div>
  );
}
