/** Cameras.jsx - (admin) The places where photos and videos come from. */
import { useEffect, useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Paper, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import api from '../services/api';
import PageHeader from '../components/PageHeader';

const EMPTY = { name: '', location: '', latitude: '', longitude: '', is_active: true };

export default function Cameras() {
  const [rows, setRows] = useState([]);
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState('');

  const load = () => api.get('/cameras').then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    setError('');
    const body = { ...edit, latitude: edit.latitude === '' ? null : Number(edit.latitude),
      longitude: edit.longitude === '' ? null : Number(edit.longitude) };
    try {
      if (edit.camera_id) await api.put(`/cameras/${edit.camera_id}`, body);
      else await api.post('/cameras', body);
      setEdit(null);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <>
      <PageHeader title="Cameras" subtitle="Locations used for analyses, live sessions and the dashboard"
        action={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setEdit(EMPTY)}>Add camera</Button>} />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>Name</TableCell><TableCell>Location</TableCell><TableCell>GPS</TableCell>
              <TableCell align="right">Violations</TableCell><TableCell>Status</TableCell></TableRow>
          </TableHead>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.camera_id} hover sx={{ cursor: 'pointer' }}
                onClick={() => setEdit({ ...c, latitude: c.latitude ?? '', longitude: c.longitude ?? '' })}>
                <TableCell>{c.name}</TableCell>
                <TableCell>{c.location}</TableCell>
                <TableCell>{c.latitude ? `${Number(c.latitude).toFixed(4)}, ${Number(c.longitude).toFixed(4)}` : '-'}</TableCell>
                <TableCell align="right">{c.violations}</TableCell>
                <TableCell><Chip size="small" label={c.is_active ? 'Active' : 'Off'} color={c.is_active ? 'success' : 'default'} /></TableCell>
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
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEdit(null)}>Cancel</Button>
          <Button variant="contained" onClick={save}>Save</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
