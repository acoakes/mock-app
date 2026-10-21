// ARC stand-in component library barrel. Import via the `@arc` alias
// (vite.config.ts + tsconfig paths) so the real ARC package can later drop in
// by re-pointing the alias. Every component is presentational (no Redux, no
// data fetching) and forwards a data-testid.
export { AppShell } from './AppShell';
export type { AppShellProps } from './AppShell';
export { NavBar } from './NavBar';
export type { NavBarProps, NavLinkItem } from './NavBar';
export { PageHeading } from './PageHeading';
export type { PageHeadingProps } from './PageHeading';
export { KpiCard } from './KpiCard';
export type { KpiCardProps } from './KpiCard';
export { KpiGrid } from './KpiGrid';
export type { KpiGridProps } from './KpiGrid';
export { DataTable } from './DataTable';
export type { DataTableProps, Column } from './DataTable';
export { DetailPanel } from './DetailPanel';
export type { DetailPanelProps, DetailRow } from './DetailPanel';
export { Select } from './Select';
export type { SelectProps, SelectOption } from './Select';
export { TextField } from './TextField';
export type { TextFieldProps } from './TextField';
export { Button } from './Button';
export type { ButtonProps, ButtonVariant } from './Button';
export { DateRangeFilter } from './DateRangeFilter';
export type { DateRangeFilterProps } from './DateRangeFilter';
export { Banner, EmptyState } from './Banner';
export type { BannerProps, BannerVariant, EmptyStateProps } from './Banner';
export { Badge } from './Badge';
export type { BadgeProps, BadgeKind } from './Badge';
