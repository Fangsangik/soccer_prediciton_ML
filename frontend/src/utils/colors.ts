export const TEAM_COLORS: Record<string, { primary: string; secondary: string }> = {
  ARS: { primary: '#EF0107', secondary: '#FFFFFF' },
  MCI: { primary: '#6CABDD', secondary: '#1C2C5B' },
  LIV: { primary: '#C8102E', secondary: '#00B2A9' },
  CHE: { primary: '#034694', secondary: '#DBA111' },
  MUN: { primary: '#DA291C', secondary: '#FBE122' },
  TOT: { primary: '#132257', secondary: '#FFFFFF' },
  NEW: { primary: '#241F20', secondary: '#FFFFFF' },
  AVL: { primary: '#670E36', secondary: '#95BFE5' },
  BHA: { primary: '#0057B8', secondary: '#FFFFFF' },
  WHU: { primary: '#7A263A', secondary: '#1BB1E7' },
  CRY: { primary: '#1B458F', secondary: '#C4122E' },
  BRE: { primary: '#E30613', secondary: '#FBB800' },
  FUL: { primary: '#000000', secondary: '#FFFFFF' },
  WOL: { primary: '#FDB913', secondary: '#231F20' },
  BOU: { primary: '#DA291C', secondary: '#000000' },
  NFO: { primary: '#DD0000', secondary: '#FFFFFF' },
  EVE: { primary: '#003399', secondary: '#FFFFFF' },
  LUT: { primary: '#F78F1E', secondary: '#002D62' },
  BUR: { primary: '#6C1D45', secondary: '#99D6EA' },
  SHU: { primary: '#EE2737', secondary: '#000000' },
};

export const RESULT_COLORS = {
  W: { bg: 'bg-emerald-500', text: 'text-emerald-400', border: 'border-emerald-500' },
  D: { bg: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500' },
  L: { bg: 'bg-red-500', text: 'text-red-400', border: 'border-red-500' },
} as const;

export const VERDICT_COLORS = {
  strong_value: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/40' },
  value: { bg: 'bg-emerald-500/10', text: 'text-emerald-500', border: 'border-emerald-500/30' },
  marginal: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
  no_value: { bg: 'bg-slate-700/50', text: 'text-slate-500', border: 'border-slate-600/30' },
} as const;

export const PROBABILITY_COLORS = {
  home: '#10b981',  // emerald-500
  draw: '#64748b',  // slate-500
  away: '#ef4444',  // red-500
};

export const POSITION_COLORS: Record<string, string> = {
  GKP: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  DEF: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  MID: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  FWD: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export const DIFFICULTY_COLORS: Record<number, string> = {
  1: 'bg-emerald-500/80',
  2: 'bg-emerald-500/50',
  3: 'bg-amber-500/50',
  4: 'bg-red-500/50',
  5: 'bg-red-600/80',
};
