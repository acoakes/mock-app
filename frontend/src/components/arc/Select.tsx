import type { ChangeEvent } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  name: string;
  value: string;
  options: SelectOption[];
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
  label?: string;
  id?: string;
  testid?: string;
  className?: string;
}

// Renders a native <select name=...> with <option>s.
export function Select({
  name,
  value,
  options,
  onChange,
  label,
  id,
  testid,
  className,
}: SelectProps) {
  const selectId = id ?? name;
  return (
    <div className="form-group form-inline">
      {label ? <label htmlFor={selectId}>{label}</label> : null}
      <select
        id={selectId}
        name={name}
        value={value}
        onChange={onChange}
        data-testid={testid}
        className={['form-control', className ?? ''].filter(Boolean).join(' ')}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
