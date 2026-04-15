import { useState } from 'react';
import clsx from 'clsx';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { SkeletonRow } from './Skeleton';

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (value: unknown, row: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  skeletonRows?: number;
  onRowClick?: (row: T) => void;
  rowKey?: (row: T) => string | number;
  emptyMessage?: string;
  compact?: boolean;
}

type SortDir = 'asc' | 'desc' | null;

export default function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  loading = false,
  skeletonRows = 5,
  onRowClick,
  rowKey,
  emptyMessage = 'No data available',
  compact = false,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : d === 'desc' ? null : 'asc'));
      if (sortDir === 'desc') setSortKey(null);
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortedData = [...data].sort((a, b) => {
    if (!sortKey || !sortDir) return 0;
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const cellPad = compact ? 'px-3 py-2' : 'px-4 py-3';

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/50">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-800 border-b border-slate-700/50">
            {columns.map((col) => (
              <th
                key={col.key}
                style={col.width ? { width: col.width } : undefined}
                className={clsx(
                  cellPad,
                  'text-xs font-semibold text-slate-400 uppercase tracking-wide whitespace-nowrap',
                  col.align === 'right' && 'text-right',
                  col.align === 'center' && 'text-center',
                  col.align !== 'right' && col.align !== 'center' && 'text-left',
                  col.sortable && 'cursor-pointer select-none hover:text-slate-200 transition-colors'
                )}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && (
                    <span className="text-slate-600">
                      {sortKey === col.key && sortDir === 'asc' ? (
                        <ChevronUp className="w-3 h-3 text-emerald-400" />
                      ) : sortKey === col.key && sortDir === 'desc' ? (
                        <ChevronDown className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <ChevronsUpDown className="w-3 h-3" />
                      )}
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: skeletonRows }).map((_, i) => (
              <SkeletonRow key={i} cols={columns.length} />
            ))
          ) : sortedData.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-center py-10 text-slate-500 text-sm">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, idx) => (
              <tr
                key={rowKey ? rowKey(row) : idx}
                className={clsx(
                  'border-b border-slate-700/30 transition-colors',
                  idx % 2 === 0 ? 'bg-slate-900/30' : 'bg-slate-800/20',
                  onRowClick && 'cursor-pointer hover:bg-slate-700/30'
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={clsx(
                      cellPad,
                      'text-slate-300',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center'
                    )}
                  >
                    {col.render
                      ? col.render(row[col.key], row)
                      : (row[col.key] as React.ReactNode) ?? '—'}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
