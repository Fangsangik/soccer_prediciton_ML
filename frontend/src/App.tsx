import { Routes, Route, Navigate } from 'react-router-dom';
import { LeagueProvider } from '@/contexts/LeagueContext';
import { UserProvider } from '@/contexts/UserContext';
import PageShell from '@/components/layout/PageShell';
import Dashboard from '@/pages/Dashboard';
import MatchPrediction from '@/pages/MatchPrediction';
import BettingEV from '@/pages/BettingEV';
import FPLOptimizer from '@/pages/FPLOptimizer';
import PlayerScouting from '@/pages/PlayerScouting';
import ModelPerformance from '@/pages/ModelPerformance';
import Profile from '@/pages/Profile';
import Standings from '@/pages/Standings';

export default function App() {
  return (
    <LeagueProvider>
    <UserProvider>
    <PageShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/standings" element={<Standings />} />
        <Route path="/matches" element={<MatchPrediction />} />
        <Route path="/betting" element={<BettingEV />} />
        <Route path="/fpl" element={<FPLOptimizer />} />
        <Route path="/scouting" element={<PlayerScouting />} />
        <Route path="/performance" element={<ModelPerformance />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </PageShell>
    </UserProvider>
    </LeagueProvider>
  );
}
