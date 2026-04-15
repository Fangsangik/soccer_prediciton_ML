// Lightweight date utilities — native JS, no external dependency

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

export function formatPercent(n: number, decimals = 1): string {
  return `${(n * 100).toFixed(decimals)}%`;
}

export function formatOdds(n: number): string {
  return n.toFixed(2);
}

export function formatCurrency(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${(n / 1_000).toFixed(0)}K`;
  return `€${n}`;
}

export function formatDate(d: string): string {
  try {
    const date = new Date(d);
    return `${pad(date.getDate())} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
  } catch {
    return d;
  }
}

export function formatKickoff(d: string): string {
  try {
    const date = new Date(d);
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const timeStr = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    if (isSameDay(date, now)) return `Today ${timeStr}`;
    if (isSameDay(date, tomorrow)) return `Tomorrow ${timeStr}`;
    return `${DAYS[date.getDay()]} ${pad(date.getDate())} ${MONTHS[date.getMonth()]} ${timeStr}`;
  } catch {
    return d;
  }
}

export function formatMatchday(n: number): string {
  return `GW${n}`;
}

export function formatEV(ev: number): string {
  const sign = ev >= 0 ? '+' : '';
  return `${sign}${(ev * 100).toFixed(1)}%`;
}

export function formatMarketValue(eur: number): string {
  if (eur >= 100_000_000) return `€${(eur / 1_000_000).toFixed(0)}M`;
  if (eur >= 1_000_000) return `€${(eur / 1_000_000).toFixed(1)}M`;
  if (eur >= 1_000) return `€${(eur / 1_000).toFixed(0)}K`;
  return `€${eur}`;
}

export function formatStat(n: number, decimals = 2): string {
  return n.toFixed(decimals);
}
