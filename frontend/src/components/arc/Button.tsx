import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  sm?: boolean;
  children: ReactNode;
  testid?: string;
}

// Renders a REAL <button>. A submit button (type="submit") is load-bearing for
// login_page.py's `button[type='submit']` fallback.
export function Button({
  variant = 'primary',
  sm = false,
  type = 'button',
  className,
  testid,
  children,
  ...rest
}: ButtonProps) {
  const classes = ['btn', `btn-${variant}`, sm ? 'btn-sm' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return (
    <button type={type} className={classes} data-testid={testid} {...rest}>
      {children}
    </button>
  );
}
