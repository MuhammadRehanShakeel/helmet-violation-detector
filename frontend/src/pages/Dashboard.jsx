/**
 * Dashboard.jsx - Numbers at a glance: violations, review progress, fines, busiest hours and cameras.
 */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { Alert, Box, Button, Chip, Stack, Grid, LinearProgress, Paper, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import api, { downloadFile } from '../services/api';
import PageHeader from '../components/PageHeader';
import { colors } from '../theme';
import { rupees } from '../utils/format';

function Stat({ label, value, hint, color }) {
  return (
    <Paper sx={{ p: 2.2, height: '100%' }}>
      <Typography color="text.secondary" fontSize={12.5} sx={{ textTransform: 'uppercase', letterSpacing: 0.8 }}>
        {label}
      </Typography>
      <Typography variant="h3" sx={{ fontSize: 38, color: color || colors.text, mt: 0.5 }}>{value}</Typography>
      {hint && <Typography color="text.secondary" fontSize={12.5}>{hint}</Typography>}
    </Paper>
  );
}

function ChartCard({ title, children, height = 260 }) {
  return (
    <Paper sx={{ p: 2.2, height: '100%' }}>
      <Typography variant="h6" sx={{ mb: 1.5 }}>{title}</Typography>
      <Box sx={{ height }}>{children}</Box>
    </Paper>
  );
}

const tooltipStyle = { contentStyle: { background: colors.panelHigh, border: `1px solid ${colors.line}`, borderRadius: 8 } };

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const role = useSelector((s) => s.auth.user.role);
  const tick = useSelector((s) => s.notifications.tick);       // new violation arrived -> refresh

  useEffect(() => {
    api.get('/stats/summary', { params: { days } }).then((r) => setData(r.data)).catch((e) => setError(e.message));
  }, [days, tick]);

  const report = (kind) => downloadFile(`/reports/${kind}?days=${days}`,
    kind === 'summary.pdf' ? `roadguard_report_${days}d.pdf` : `roadguard_violations_${days}d.csv`).catch((e) => setError(e.message));

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!data) return <LinearProgress />;

  // per-day rows: { day, NO_HELMET, TRIPLE_RIDING }
  const daily = Object.values(data.by_day.reduce((acc, r) => {
    acc[r.day] = acc[r.day] || { day: r.day.slice(5), NO_HELMET: 0, TRIPLE_RIDING: 0 };
    acc[r.day][r.type] = r.n;
    return acc;
  }, {}));
  const hours = Array.from({ length: 24 }, (_, h) => ({ hour: `${h}`, n: data.by_hour.find((x) => x.hour === h)?.n || 0 }));

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Violations detected by the AI and checked by officers"
        action={(
          <Stack direction="row" spacing={1} alignItems="center">
            {role !== 'viewer' && <Button size="small" variant="outlined" onClick={() => report('summary.pdf')}>PDF report</Button>}
            {role !== 'viewer' && <Button size="small" variant="outlined" onClick={() => report('violations.csv')}>Excel (CSV)</Button>}
            <ToggleButtonGroup size="small" exclusive value={days} onChange={(e, v) => v && setDays(v)}>
              {[7, 30, 90].map((d) => <ToggleButton key={d} value={d}>{d} days</ToggleButton>)}
            </ToggleButtonGroup>
          </Stack>
        )}
      />
      <Grid container spacing={2}>
        <Grid item xs={6} md={3}><Stat label="Violations" value={data.violations} hint={`${data.motorcyclists} motorcyclists analysed`} color={colors.amber} /></Grid>
        <Grid item xs={6} md={3}><Stat label="Waiting for review" value={data.pending} hint={`${data.approved} approved · ${data.rejected} rejected`} /></Grid>
        <Grid item xs={6} md={3}>
          <Stat label="Officer agreement" value={data.officer_agreement === null ? '-' : `${data.officer_agreement}%`}
            hint="Approved ÷ reviewed (real-world precision)" color={colors.green} />
        </Grid>
        <Grid item xs={6} md={3}><Stat label="E-challans" value={data.challans} hint={`${rupees(data.fines_amount)} in fines`} /></Grid>

        <Grid item xs={12} lg={8}>
          <ChartCard title="Violations per day">
            <ResponsiveContainer>
              <BarChart data={daily}>
                <CartesianGrid stroke={colors.line} vertical={false} />
                <XAxis dataKey="day" stroke={colors.muted} fontSize={12} />
                <YAxis allowDecimals={false} stroke={colors.muted} fontSize={12} />
                <Tooltip {...tooltipStyle} />
                <Legend />
                <Bar isAnimationActive={false} dataKey="NO_HELMET" name="No helmet" stackId="a" fill={colors.red} />
                <Bar isAnimationActive={false} dataKey="TRIPLE_RIDING" name="Triple riding" stackId="a" fill={colors.amber} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 2.2, height: '100%' }}>
            <Typography variant="h6" sx={{ mb: 1.5 }}>Repeat offenders</Typography>
            {data.repeat_offenders.length === 0 && <Typography color="text.secondary">No plate seen twice yet.</Typography>}
            {data.repeat_offenders.map((r) => (
              <Box key={r.plate} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1,
                borderBottom: `1px solid ${colors.line}` }}>
                <Box sx={{ fontFamily: 'monospace', fontSize: 16, fontWeight: 700, bgcolor: '#f4f4f0', color: '#111',
                  px: 1.2, py: 0.3, borderRadius: 1, border: '2px solid #111' }}>{r.plate}</Box>
                <Chip size="small" color="error" label={`${r.n} violations`} />
              </Box>
            ))}
            <Typography color="text.secondary" fontSize={12.5} sx={{ mt: 2 }}>
              Plates read automatically: {data.plates_read_percent ?? '-'}%
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={7}>
          <ChartCard title="Busiest hours (when violations happen)" height={220}>
            <ResponsiveContainer>
              <BarChart data={hours}>
                <CartesianGrid stroke={colors.line} vertical={false} />
                <XAxis dataKey="hour" stroke={colors.muted} fontSize={11} />
                <YAxis allowDecimals={false} stroke={colors.muted} fontSize={12} />
                <Tooltip {...tooltipStyle} />
                <Bar isAnimationActive={false} dataKey="n" name="Violations" fill={colors.blue} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12} md={5}>
          <ChartCard title="By camera" height={220}>
            <ResponsiveContainer>
              <BarChart data={data.by_camera} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" allowDecimals={false} stroke={colors.muted} fontSize={12} />
                <YAxis type="category" dataKey="camera" stroke={colors.muted} fontSize={12} width={130} />
                <Tooltip {...tooltipStyle} />
                <Bar isAnimationActive={false} dataKey="n" name="Violations" fill={colors.amber} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
      </Grid>
    </>
  );
}
