import type { ReactNode } from 'react';

export type BannerVariant = 'success' | 'error' | 'empty';

export interface BannerProps {
  variant: BannerVariant;
  children: ReactNode;
  testid?: string;
  className?: string;
}

const VARIANT_CLASS: Record<BannerVariant, string> = {
  success: 'success',
  error: 'error',
  empty: 'empty-state',
};

// Renders a .success / .error / .empty-state banner. EmptyState is an alias for
// the 'empty' variant (design §4 groups Banner/EmptyState).
export function Banner({ variant, children, testid, className }: BannerProps) {
  return (
    <div
      className={[VARIANT_CLASS[variant], className ?? ''].filter(Boolean).join(' ')}
      data-testid={testid}
    >
      {children}
    </div>
  );
}

export interface EmptyStateProps {
  children: ReactNode;
  testid?: string;
  className?: string;
}

export function EmptyState({ children, testid, className }: EmptyStateProps) {
  return (
    <Banner variant="empty" testid={testid} className={className}>
      {children}
    </Banner>
  );
}
