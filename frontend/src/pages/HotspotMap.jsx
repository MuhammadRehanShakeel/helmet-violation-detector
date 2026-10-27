/**
 * HotspotMap.jsx - Where violations happen: every camera on a map, bigger + redder = more violations.
 * Map tiles come from OpenStreetMap (free; needs internet). Everything else works offline.
 */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Box, Paper, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import { colors } from '../theme';
import { dateTime } from '../utils/format';

export default function HotspotMap() {
  const tick = useSelector((s) => s.notifications.tick);
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get('/stats/map', { params: { days } }).then((r) => setRows(r.data)); }, [days, tick]);

  const max = Math.max(1, ...rows.map((r) => r.total));
  const center = rows.length ? [rows.reduce((s, r) => s + r.latitude, 0) / rows.length,
    rows.reduce((s, r) => s + r.longitude, 0) / rows.length] : [33.64, 73.07];

  return (
    <>
      <PageHeader title="Hotspot map" subtitle="Cameras sized and coloured by number of violations"
        action={(
          <ToggleButtonGroup size="small" exclusive value={days} onChange={(e, v) => v && setDays(v)}>
            {[7, 30, 90].map((d) => <ToggleButton key={d} value={d}>{d} days</ToggleButton>)}
          </ToggleButtonGroup>
        )} />
      <Paper sx={{ p: 1, height: { xs: 460, md: 'calc(100vh - 190px)' }, minHeight: 420 }}>
        <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%', borderRadius: 8 }} key={rows.length}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {rows.map((r) => {
            const share = r.total / max;
            const colour = r.total === 0 ? colors.green : share > 0.6 ? colors.red : colors.amber;
            return (
              <CircleMarker key={r.camera_id} center={[r.latitude, r.longitude]} radius={10 + share * 28}
                pathOptions={{ color: colour, fillColor: colour, fillOpacity: 0.45, weight: 2 }}>
                <Tooltip permanent direction="top" offset={[0, -8]}>{r.name}: {r.total}</Tooltip>
                <Popup>
                  <b>{r.name}</b><br />{r.location}<br />
                  No helmet: {r.no_helmet} · Triple riding: {r.triple_riding}<br />
                  {r.last_violation ? `Last: ${dateTime(r.last_violation)}` : 'No violations'}
                  {r.stream_enabled ? <><br />● CCTV watching</> : null}
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </Paper>
      <Stack direction="row" spacing={2} sx={{ mt: 1.5 }}>
        {[['None', colors.green], ['Some', colors.amber], ['Most', colors.red]].map(([t, c]) => (
          <Stack key={t} direction="row" spacing={0.8} alignItems="center">
            <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: c }} />
            <Typography fontSize={13} color="text.secondary">{t}</Typography>
          </Stack>
        ))}
        <Typography fontSize={13} color="text.secondary">Add GPS positions on the Cameras page.</Typography>
      </Stack>
    </>
  );
}
