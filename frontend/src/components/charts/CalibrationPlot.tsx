import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface CalibrationPlotProps {
  data: Array<{ predicted: number; observed: number; count: number }>;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs space-y-1">
      <p className="text-slate-400">Predicted: <span className="font-mono text-slate-200">{label}</span></p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <span className="font-mono">{typeof p.value === 'number' ? p.value.toFixed(3) : p.value}</span>
        </p>
      ))}
    </div>
  );
}

export default function CalibrationPlot({ data }: CalibrationPlotProps) {
  const chartData = data.map((d) => ({
    predicted: d.predicted.toFixed(2),
    observed: d.observed,
    count: d.count,
    perfect: d.predicted,
  }));

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 24, left: 16 }}>
          <CartesianGrid stroke="#1e293b" strokeWidth={0.5} />
          <XAxis
            dataKey="predicted"
            tick={{ fill: '#475569', fontSize: 9 }}
            axisLine={{ stroke: '#334155' }}
            tickLine={false}
            label={{ value: 'Predicted Probability', position: 'insideBottom', offset: -12, fill: '#475569', fontSize: 10 }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#475569', fontSize: 9 }}
            axisLine={{ stroke: '#334155' }}
            tickLine={false}
            label={{ value: 'Observed Frequency', angle: -90, position: 'insideLeft', offset: 10, fill: '#475569', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />
          {/* Bin count bars — subtle background */}
          <Bar dataKey="count" name="Count" fill="#1e293b" opacity={0.6} yAxisId={0} hide />
          {/* Perfect calibration reference line (dashed diagonal) */}
          <ReferenceLine
            segment={[{ x: '0.00', y: 0 }, { x: '1.00', y: 1 }]}
            stroke="#475569"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          {/* Actual calibration curve */}
          <Line
            type="monotone"
            dataKey="observed"
            name="Observed"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ r: 3, fill: '#10b981', stroke: '#065f46', strokeWidth: 1 }}
            activeDot={{ r: 4, fill: '#34d399' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
