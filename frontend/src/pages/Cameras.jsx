/**
 * Cameras.jsx - (admin) Camera locations + their CCTV / IP camera stream.
 * Stream address examples:
 *   rtsp://user:password@192.168.1.20:554/stream1   (most CCTV cameras)
 *   http://192.168.1.30:8080/video                  (phone with the free "IP Webcam" app)
 *   demo:demo_traffic.mp4                           (a video in backend/data/demo_streams, looped)
 */
import { useEffect, useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Paper, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import api from '../services/api';
import PageHeader from '../components/PageHeader';

const EMPTY = { name: '', location: '', latitude: '', longitude: '', is_active: true, stream_url: '', stream_enabled: false };
const STATUS = { live: 'success', starting: 'info', reconnecting: 'warning', error: 'error' };

export default function Cameras() {
  const [rows, setRows] = useState([]);
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => api.get('/cameras').then((r) => setRows(r.data));
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const save = async () => {
    setError('');
    setBusy(true);
    const body = { name: edit.name, location: edit.location, is_active: edit.is_active,
      latitude: edit.latitude === '' ? null : Number(edit.latitude), longitude: edit.longitude === '' ? null : Number(edit.longitude) };
    try {
      let id = edit.camera_id;
      if (id) await api.put(`/cameras/${id}`, body);
      else id = (await api.post('/cameras', body)).data.camera_id;
      await api.put(`/cameras/${id}/stream`, { stream_url: edit.stream_url || null, stream_enabled: edit.stream_enabled });
      setEdit(null);
      load();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  return (
    <>
      <PageHeader title="Cameras" subtitle="Locations and CCTV / IP camera streams watched by the AI"
        action={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setEdit(EMPTY)}>Add camera</Button>} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>Name</TableCell><TableCell>Location</TableCell><TableCell>GPS</TableCell>
              <TableCell>Stream</TableCell><TableCell align="right">Violations</TableCell><TableCell>Status</TableCell></TableRow>
          </TableHead>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.camera_id} hover sx={{ cursor: 'pointer' }}
                onClick={() => setEdit({ ...c, latitude: c.latitude ?? '', longitude: c.longitude ?? '', stream_url: c.stream_url || '' })}>
                <TableCell>{c.name}</TableCell>
                <TableCell>{c.location}</TableCell>
                <TableCell>{c.latitude ? `${Number(c.latitude).toFixed(4)}, ${Number(c.longitude).toFixed(4)}` : '-'}</TableCell>
                <TableCell sx={{ maxWidth: 260 }}>
                  <Typography noWrap fontSize={13} color="text.secondary">{c.stream_url || '-'}</Typography>
                </TableCell>
                <TableCell align="right">{c.violations}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5}>
                    <Chip size="small" label={c.is_active ? 'Active' : 'Off'} color={c.is_active ? 'success' : 'default'} variant="outlined" />
                    {c.stream && <Chip size="small" label={`CCTV ${c.stream.status}`} color={STATUS[c.stream.status] || 'default'} />}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Dialog open={Boolean(edit)} onClose={() => setEdit(null)} fullWidth maxWidth="sm">
        <DialogTitle>{edit?.camera_id ? 'Edit camera' : 'New camera'}</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {edit && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="Name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
              <TextField label="Location" value={edit.location || ''} onChange={(e) => setEdit({ ...edit, location: e.target.value })} />
              <Stack direction="row" spacing={2}>
                <TextField label="Latitude" value={edit.latitude} onChange={(e) => setEdit({ ...edit, latitude: e.target.value })} />
                <TextField label="Longitude" value={edit.longitude} onChange={(e) => setEdit({ ...edit, longitude: e.target.value })} />
              </Stack>
              <FormControlLabel control={<Switch checked={edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} />} label="Active" />
              <TextField label="Stream address (optional)" value={edit.stream_url}
                placeholder="rtsp://user:pass@192.168.1.20:554/stream1"
                helperText={'CCTV: rtsp://...  ·  Phone with "IP Webcam" app: http://<phone-ip>:8080/video  ·  Demo: demo:demo_traffic.mp4. Passwords are never shown again.'}
                onChange={(e) => setEdit({ ...edit, stream_url: e.target.value })} />
              <FormControlLabel control={<Switch checked={edit.stream_enabled}
                onChange={(e) => setEdit({ ...edit, stream_enabled: e.target.checked })} />}
                label="Watch this camera 24/7 (the AI analyses 2 frames per second)" />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEdit(null)}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Save'}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
