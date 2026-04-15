import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';

interface RadarChartProps {
  data: Array<{ stat: string; value: number; fullMark: number }>;
  comparisonData?: Array<{ stat: string; value: number; fullMark: number }>;
  playerName?: string;
  comparisonName?: string;
}

export default function RadarChart({
  data,
  comparisonData,
  playerName = 'Player',
  comparisonName = 'Comparison',
}: RadarChartProps) {
  const merged = data.map((d, i) => ({
    stat: d.stat,
    primary: d.value,
    fullMark: d.fullMark,
    comparison: comparisonData ? comparisonData[i]?.value ?? 0 : undefined,
  }));

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsRadarChart cx="50%" cy="50%" outerRadius="70%" data={merged}>
          <PolarGrid stroke="#334155" strokeWidth={0.5} />
          <PolarAngleAxis
            dataKey="stat"
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'inherit' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: '#475569', fontSize: 9 }}
            tickCount={4}
            axisLine={false}
          />
          <Radar
            name={playerName}
            dataKey="primary"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.25}
            strokeWidth={1.5}
            dot={{ r: 2, fill: '#10b981' }}
          />
          {comparisonData && (
            <Radar
              name={comparisonName}
              dataKey="comparison"
              stroke="#f59e0b"
              fill="#f59e0b"
              fillOpacity={0.15}
              strokeWidth={1.5}
              dot={{ r: 2, fill: '#f59e0b' }}
            />
          )}
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '6px',
              fontSize: '11px',
              color: '#e2e8f0',
            }}
            formatter={(value: number) => [`${value}`, '']}
          />
          {comparisonData && (
            <Legend
              iconType="circle"
              iconSize={6}
              wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }}
            />
          )}
        </RechartsRadarChart>
      </ResponsiveContainer>
    </div>
  );
}
