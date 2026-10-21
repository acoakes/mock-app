import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

export interface NavLinkItem {
  href: string;
  label: string;
  // logout is a real <a href> whose onClick is intercepted (see AppShell).
  logout?: boolean;
  onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
  testid?: string;
}

export interface NavBarProps {
  brand: string;
  links: NavLinkItem[];
}

// Renders the top navbar. Internal links use React Router <Link> so they emit
// real anchors with the route href; the logout link MUST stay a native <a
// href="/logout"> (a[href*='logout'] is how login_page.py finds logout).
export function NavBar({ brand, links }: NavBarProps): ReactNode {
  return (
    <nav className="navbar">
      <div className="nav-container">
        <span className="nav-brand">{brand}</span>
        <div className="nav-links">
          {links.map((link) =>
            link.logout ? (
              <a
                key={link.href}
                href={link.href}
                className="nav-link nav-link-logout"
                onClick={link.onClick}
                data-testid={link.testid}
              >
                {link.label}
              </a>
            ) : (
              <Link
                key={link.href}
                to={link.href}
                className="nav-link"
                data-testid={link.testid}
              >
                {link.label}
              </Link>
            ),
          )}
        </div>
      </div>
    </nav>
  );
}
