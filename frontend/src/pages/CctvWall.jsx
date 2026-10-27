/**
 * CctvWall.jsx - Every CCTV / IP camera being watched, with its latest analysed picture
 * (refreshed every second), live status and counters. Admins switch cameras on/off on the Cameras page.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { Alert, Box, Button, Card, Chip, Grid, Stack, Typography } from '@mui/material';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import { colors } from '../theme';

const STATUS = { live: 'success', starting: 'info', reconnecting: 'warning', error: 'error', stopped: 'default' };

function LiveImage({ cameraId }) {
  const [url, setUrl] = useState(null);
  const last = useRef(null);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.get(`/cameras/${cameraId}/snapshot`, { responseType: 'blob', params: { t: Date.now() } });
        if (!alive) return;
        const next = URL.createObjectURL(res.data);
        setUrl(next);
        if (last.current) URL.revokeObjectURL(last.current);
        last.current = next;
      } catch { /* camera not ready yet */ }
    };
    load();
    const timer = setInterval(load, 1000);
    return () => { alive = false; clearInterval(timer); if (last.current) URL.revokeObjectURL(last.current); };
  }, [cameraId]);
  return url
    ? <Box component="img" src={url} alt="" sx={{ width: '100%', aspectRatio: '16 / 9', objectFit: 'contain', bgcolor: '#000', display: 'block' }} />
    : <Box sx={{ aspectRatio: '16 / 9', bgcolor: '#000', display: 'grid', placeItems: 'center', color: colors.muted }}>Waiting for picture...</Box>;
}

export default function CctvWall() {
  const navigate = useNavigate();
  const user = useSelector((s) => s.auth.user);
  const [streams, setStreams] = useState([]);
  useEffect(() => {
    const load = () => api.get('/cameras/streams/status').then((r) => setStreams(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <PageHeader title="CCTV wall" subtitle="Cameras watched in the background, 24/7. New violations pop up as notifications."
        action={user.role === 'admin' && <Button variant="outlined" onClick={() => navigate('/cameras')}>Manage cameras</Button>} />
      {streams.length === 0 && (
        <Alert severity="info">
          No camera is being watched. {user.role === 'admin' ? 'Open Cameras, add a stream address and switch "Watch" on.' : 'Ask an admin to switch a camera on.'}
          {' '}For a quick test use your phone with the free "IP Webcam" app, or <b>demo:demo_traffic.mp4</b>.
        </Alert>
      )}
      <Grid container spacing={2}>
        {streams.map((s) => (
          <Grid item xs={12} md={6} xl={4} key={s.camera_id}>
            <Card>
              <LiveImage cameraId={s.camera_id} />
              <Box sx={{ p: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography fontWeight={700}>{s.name}</Typography>
                  <Chip size="small" label={s.status} color={STATUS[s.status] || 'default'} />
                </Stack>
                <Typography color="text.secondary" fontSize={13} sx={{ mt: 0.5 }}>
                  {s.violations} violations · {s.motorcyclists} bikes · {s.frames_analysed} frames
                  {s.ms_per_frame ? ` · ${s.ms_per_frame} ms/frame` : ''} · running {Math.round(s.running_seconds / 60)} min
                </Typography>
                {s.error && <Typography color="warning.main" fontSize={13}>{s.error}</Typography>}
              </Box>
            </Card>
          </Grid>
        ))}
      </Grid>
    </>
  );
}
