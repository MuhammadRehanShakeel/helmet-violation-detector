/**
 * LiveCamera.jsx - Use this phone/laptop camera as a traffic camera.
 *
 * Every ~1 second: take a frame from the camera -> send it as a JPEG to /live/{id}/frame
 * -> draw the boxes the backend returns on top of the video.
 * The next frame is only sent after the previous answer arrives, so a slow CPU never piles up requests.
 */
import { useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, Chip, Grid, List, ListItem, ListItemText, Paper, Stack, Typography,
} from '@mui/material';
import PlayIcon from '@mui/icons-material/PlayArrowRounded';
import StopIcon from '@mui/icons-material/StopRounded';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import CameraSelect from '../components/CameraSelect';
import { colors } from '../theme';
import { VIOLATION_LABEL } from '../utils/format';

const FRAME_EVERY_MS = 1000;
const ROLE_COLOR = { helmet: colors.green, no_helmet: colors.red };

function drawBoxes(canvas, video, result) {
  const ctx = canvas.getContext('2d');
  canvas.width = video.clientWidth;
  canvas.height = video.clientHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!result) return;
  const sx = canvas.width / result.width;
  const sy = canvas.height / result.height;
  const rect = (b, color, width) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.strokeRect(b[0] * sx, b[1] * sy, (b[2] - b[0]) * sx, (b[3] - b[1]) * sy);
  };
  result.bikes.forEach((bike) => {
    const bad = bike.status === 'violation';
    rect(bike.box, bad ? colors.red : colors.green, 3);
    ctx.fillStyle = bad ? colors.red : colors.green;
    ctx.font = '600 13px Inter, sans-serif';
    const label = bad ? bike.violations.map((v) => VIOLATION_LABEL[v.type]).join(' + ') : `${bike.riders} rider(s) OK`;
    ctx.fillRect(bike.box[0] * sx, bike.box[1] * sy - 20, ctx.measureText(label).width + 10, 20);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, bike.box[0] * sx + 5, bike.box[1] * sy - 6);
    bike.heads.forEach((h) => rect(h.box, ROLE_COLOR[h.role], 2));
    bike.plates.forEach((p) => rect(p.box, colors.amber, 2));
  });
}

export default function LiveCamera() {
  const video = useRef();
  const canvas = useRef();
  const grab = useRef(document.createElement('canvas'));
  const running = useRef(false);
  const [cameraId, setCameraId] = useState('');
  const [jobId, setJobId] = useState(null);
  const [stats, setStats] = useState({ motorcyclists: 0, total_violations: 0, ms: 0 });
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');

  const stopCamera = () => {
    running.current = false;
    const stream = video.current?.srcObject;
    stream?.getTracks().forEach((t) => t.stop());
    if (video.current) video.current.srcObject = null;
  };

  useEffect(() => () => stopCamera(), []);

  const loop = async (id) => {
    while (running.current) {
      const started = performance.now();
      const v = video.current;
      if (v && v.videoWidth) {
        const c = grab.current;
        const scale = Math.min(1, 960 / v.videoWidth);               // smaller frames = faster on CPU
        c.width = v.videoWidth * scale;
        c.height = v.videoHeight * scale;
        c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
        const blob = await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.8));
        const form = new FormData();
        form.append('frame', blob, 'frame.jpg');
        try {
          const { data } = await api.post(`/live/${id}/frame`, form);
          drawBoxes(canvas.current, v, data);
          setStats({ motorcyclists: data.motorcyclists, total_violations: data.total_violations,
            ms: Math.round(performance.now() - started) });
          if (data.new_violations.length) {
            setEvents((old) => [...data.new_violations.map((x) => ({ ...x, at: new Date() })), ...old].slice(0, 30));
          }
        } catch (e) {
          setError(e.message);
          running.current = false;
        }
      }
      const wait = FRAME_EVERY_MS - (performance.now() - started);
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    }
  };

  const start = async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
      });
      video.current.srcObject = stream;
      await video.current.play();
      const { data } = await api.post('/live/start', { camera_id: cameraId || null });
      setJobId(data.job_id);
      setEvents([]);
      running.current = true;
      loop(data.job_id);
    } catch (e) {
      stopCamera();
      setError(e.name === 'NotAllowedError' ? 'Camera permission was denied.' : e.message);
    }
  };

  const stop = async () => {
    stopCamera();
    if (jobId) await api.post(`/live/${jobId}/stop`).catch(() => {});
    setJobId(null);
    drawBoxes(canvas.current, video.current, null);
  };

  return (
    <>
      <PageHeader title="Live camera" subtitle="Point the camera at the road. About one frame per second is analysed on this computer's CPU." />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Grid container spacing={2}>
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 1.5 }}>
            <Box sx={{ position: 'relative', bgcolor: '#000', borderRadius: 2, overflow: 'hidden', aspectRatio: '16 / 9' }}>
              <video ref={video} playsInline muted style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
              <canvas ref={canvas} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
              {!jobId && (
                <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: colors.muted }}>
                  Camera is off
                </Box>
              )}
              {jobId && (
                <Chip label="● LIVE" size="small" sx={{ position: 'absolute', top: 10, left: 10, bgcolor: colors.red, color: '#fff' }} />
              )}
            </Box>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 1.5 }} alignItems={{ sm: 'center' }}>
              <CameraSelect value={cameraId} onChange={setCameraId} />
              {!jobId
                ? <Button variant="contained" startIcon={<PlayIcon />} onClick={start}>Start</Button>
                : <Button variant="outlined" color="error" startIcon={<StopIcon />} onClick={stop}>Stop</Button>}
              {jobId && <Typography color="text.secondary" fontSize={13}>{stats.ms} ms per frame</Typography>}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Stack direction="row" spacing={3} sx={{ mb: 2 }}>
              <Box>
                <Typography color="text.secondary" fontSize={12}>MOTORCYCLISTS</Typography>
                <Typography variant="h4">{stats.motorcyclists}</Typography>
              </Box>
              <Box>
                <Typography color="text.secondary" fontSize={12}>VIOLATIONS</Typography>
                <Typography variant="h4" sx={{ color: colors.red }}>{stats.total_violations}</Typography>
              </Box>
            </Stack>
            <Typography variant="h6">New violations</Typography>
            <Typography color="text.secondary" fontSize={12.5}>Saved to the review queue automatically.</Typography>
            <List dense>
              {events.map((e) => (
                <ListItem key={e.violation_id} disableGutters>
                  <ListItemText primary={`${VIOLATION_LABEL[e.type]} · ${e.plate || 'plate not read'}`}
                    secondary={e.at.toLocaleTimeString()} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </>
  );
}
