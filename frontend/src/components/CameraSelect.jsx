import { useEffect, useState } from 'react';
import { MenuItem, TextField } from '@mui/material';
import api from '../services/api';

export default function CameraSelect({ value, onChange, label = 'Camera / location', allowAll, sx }) {
  const [cameras, setCameras] = useState([]);
  useEffect(() => { api.get('/cameras').then((r) => setCameras(r.data.filter((c) => c.is_active))); }, []);
  return (
    <TextField select size="small" label={label} value={value ?? ''} onChange={(e) => onChange(e.target.value)}
      sx={{ minWidth: 220, ...sx }}>
      <MenuItem value="">{allowAll ? 'All cameras' : 'Not specified'}</MenuItem>
      {cameras.map((c) => <MenuItem key={c.camera_id} value={c.camera_id}>{c.name}</MenuItem>)}
    </TextField>
  );
}
