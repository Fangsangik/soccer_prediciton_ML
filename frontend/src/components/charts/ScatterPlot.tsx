import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface ScatterPlotProps {
  data: Array<{ x: number; y: number; label: string; player_id: number; highlighted?: boolean }>;
  onPlayerClick?: (player_id: number) => void;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { label: string; x: number; y: number } }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs">
      <p className="font-medium text-slate-200">{point.label}</p>
      <p className="text-slate-500 font-mono text-[10px]">
        {point.x.toFixed(2)}, {point.y.toFixed(2)}
      </p>
    </div>
  );
}

export default function ScatterPlot({ data, onPlayerClick }: ScatterPlotProps) {
  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#1e293b" strokeWidth={0.5} />
          <XAxis
            dataKey="x"
            type="number"
            tick={{ fill: '#475569', fontSize: 9 }}
            axisLine={{ stroke: '#334155' }}
            tickLine={false}
            label={{ value: 'UMAP-1', position: 'insideBottom', offset: -4, fill: '#475569', fontSize: 9 }}
          />
          <YAxis
            dataKey="y"
            type="number"
            tick={{ fill: '#475569', fontSize: 9 }}
            axisLine={{ stroke: '#334155' }}
            tickLine={false}
            label={{ value: 'UMAP-2', angle: -90, position: 'insideLeft', fill: '#475569', fontSize: 9 }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#475569' }} />
          <Scatter
            data={data}
            onClick={(d) => onPlayerClick && onPlayerClick(d.player_id)}
            style={{ cursor: onPlayerClick ? 'pointer' : 'default' }}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.highlighted ? '#10b981' : '#475569'}
                fillOpacity={entry.highlighted ? 1 : 0.5}
                stroke={entry.highlighted ? '#34d399' : 'none'}
                strokeWidth={entry.highlighted ? 1.5 : 0}
                r={entry.highlighted ? 6 : 4}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
