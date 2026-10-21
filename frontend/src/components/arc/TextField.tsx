import type { ChangeEvent } from 'react';

export interface TextFieldProps {
  name: string;
  type?: 'text' | 'password' | 'date';
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  label?: string;
  placeholder?: string;
  id?: string;
  autoComplete?: string;
  testid?: string;
  className?: string;
}

// Renders a NATIVE <input name=...>. The `name` attribute is load-bearing:
// login_page.py binds via input[name='username'] / input[name='password'].
export function TextField({
  name,
  type = 'text',
  value,
  onChange,
  label,
  placeholder,
  id,
  autoComplete,
  testid,
  className,
}: TextFieldProps) {
  const inputId = id ?? name;
  return (
    <div className="form-group">
      {label ? <label htmlFor={inputId}>{label}</label> : null}
      <input
        type={type}
        id={inputId}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        data-testid={testid}
        className={['form-control', className ?? ''].filter(Boolean).join(' ')}
      />
    </div>
  );
}
