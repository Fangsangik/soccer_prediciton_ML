import { useState, useRef, type ReactNode } from 'react';
import clsx from 'clsx';

interface TooltipProps {
  content: string | ReactNode;
  children: ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function Tooltip({ content, children, position = 'top' }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const posClass = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1.5',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1.5',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1.5',
  }[position];

  return (
    <div
      ref={ref}
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          className={clsx(
            'absolute z-50 pointer-events-none',
            'bg-slate-700 border border-slate-600 rounded px-2 py-1',
            'text-xs text-slate-200 whitespace-nowrap shadow-lg',
            posClass
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
