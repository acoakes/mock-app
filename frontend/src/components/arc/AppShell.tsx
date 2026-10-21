import type { ReactNode } from 'react';
import { NavBar, type NavLinkItem } from './NavBar';

export interface AppShellProps {
  brand: string;
  nav: NavLinkItem[];
  // when false, the navbar is hidden (e.g. the login route) — mirrors base.html
  // only rendering the navbar when a user is in session.
  showNav?: boolean;
  children: ReactNode;
}

// Composes NavBar + the .container content wrapper, mirroring base.html.
export function AppShell({ brand, nav, showNav = true, children }: AppShellProps) {
  return (
    <>
      {showNav ? <NavBar brand={brand} links={nav} /> : null}
      <div className="container">{children}</div>
    </>
  );
}
