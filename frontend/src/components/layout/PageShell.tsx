import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

interface PageShellProps {
  children: ReactNode;
}

export default function PageShell({ children }: PageShellProps) {
  return (
    <div className="min-h-screen bg-slate-950">
      <Sidebar />
      <TopBar />
      <main className="ml-60 pt-14 min-h-screen">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
