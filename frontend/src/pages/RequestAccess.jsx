/**
 * RequestAccess.jsx - PUBLIC: "I am an officer, please give me an account". An admin approves it.
 * The hidden "website" field is a trap for spam bots (people never see it).
 */
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Alert, Box, Button, Link, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import api from '../services/api';
import Logo from '../components/Logo';

export default function RequestAccess() {
  const [form, setForm] = useState({ full_name: '', email: '', organisation: '', reason: '', requested_role: 'officer', website: '' });
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try { await api.post('/access-requests', form); setDone(true); } catch (err) { setError(err.message); }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2 }}>
      <Paper component="form" onSubmit={submit} sx={{ width: '100%', maxWidth: 460, p: { xs: 3, sm: 4 } }}>
        <Logo />
        <Typography variant="h5" sx={{ mt: 3 }}>Request an account</Typography>
        <Typography color="text.secondary" fontSize={14} sx={{ mb: 2.5 }}>
          An admin checks every request. If approved, the admin gives you a temporary password.
        </Typography>
        {done ? (
          <Alert severity="success">Request received. Your admin will contact you.</Alert>
        ) : (
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField label="Full name" required value={form.full_name} onChange={set('full_name')} />
            <TextField label="Official email" type="email" required value={form.email} onChange={set('email')} />
            <TextField label="Department / organisation" value={form.organisation} onChange={set('organisation')} />
            <TextField select label="Access needed" value={form.requested_role} onChange={set('requested_role')}>
              <MenuItem value="officer">Officer: review violations, issue e-challans</MenuItem>
              <MenuItem value="viewer">Viewer: read-only dashboard</MenuItem>
            </TextField>
            <TextField label="Why do you need access?" multiline minRows={2} value={form.reason} onChange={set('reason')} />
            <input type="text" name="website" value={form.website} onChange={set('website')} tabIndex={-1}
              autoComplete="off" style={{ position: 'absolute', left: '-9999px' }} aria-hidden="true" />
            <Button type="submit" variant="contained" size="large">Send request</Button>
          </Stack>
        )}
        <Link component={RouterLink} to="/login" sx={{ display: 'block', mt: 2.5, fontSize: 14 }}>Back to sign in</Link>
      </Paper>
    </Box>
  );
}
