import type { ReactNode } from 'react';

export interface PageHeadingProps {
  title: string;
  actions?: ReactNode;
  testid?: string;
}

// When actions are present, renders the .page-header flex layout the detail
// templates use; otherwise a plain <h1>.
export function PageHeading({ title, actions, testid }: PageHeadingProps) {
  if (actions) {
    return (
      <div className="page-header" data-testid={testid}>
        <h1>{title}</h1>
        {actions}
      </div>
    );
  }
  return (
    <h1 data-testid={testid}>{title}</h1>
  );
}
