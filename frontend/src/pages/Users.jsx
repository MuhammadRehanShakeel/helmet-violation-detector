/** Users.jsx - (admin) Accounts, password resets and access requests from the login page. */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Alert, Badge, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, Switch, Tab,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/PersonAddAlt1Outlined';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import { dateTime } from '../utils/format';

const ROLES = {
  admin: 'Admin: everything, incl. users and cameras',
  officer: 'Officer: analyse, review, issue e-challans',
  viewer: 'Viewer: read-only, plates partly hidden',
};

function SecretDialog({ secret, onClose }) {
  return (
    <Dialog open={Boolean(secret)} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Temporary password</DialogTitle>
      <DialogContent>
        <Typography fontSize={14}>Give this to <b>{secret?.email}</b> privately (not by email).
          It is shown only once. They must choose their own password at the first login.</Typography>
        <Typography sx={{ mt: 2, p: 1.5, bgcolor: 'background.default', borderRadius: 1, fontFamily: 'monospace', fontSize: 18 }}>
          {secret?.temporary_password}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => navigator.clipboard?.writeText(secret.temporary_password)}>Copy</Button>
        <Button variant="contained" onClick={onClose}>Done</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function Users() {
  const me = useSelector((s) => s.auth.user);
  const tick = useSelector((s) => s.notifications.items.length);
  const [tab, setTab] = useState('users');
  const [rows, setRows] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState(null);
  const [secret, setSecret] = useState(null);
  const [error, setError] = useState('');

  const load = () => {
    api.get('/users').then((r) => setRows(r.data)).catch((e) => setError(e.message));
    api.get('/access-requests').then((r) => setRequests(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [tick]);

  const change = async (u, body) => {
    setError('');
    try { await api.put(`/users/${u.user_id}`, body); load(); } catch (e) { setError(e.message); }
  };
  const reset = async (u) => {
    setError('');
    try { setSecret((await api.post(`/users/${u.user_id}/reset-password`)).data); } catch (e) { setError(e.message); }
  };
  const create = async () => {
    setError('');
    try { await api.post('/users', form); setForm(null); load(); } catch (e) { setError(e.message); }
  };
  const decide = async (r, decision, role) => {
    setError('');
    try {
      const { data } = await api.post(`/access-requests/${r.request_id}/decide`, { decision, role });
      if (data.temporary_password) setSecret(data);
      load();
    } catch (e) { setError(e.message); }
  };

  return (
    <>
      <PageHeader title="Users" subtitle="Only admins give accounts. People can ask for one from the login page."
        action={<Button variant="contained" startIcon={<AddIcon />}
          onClick={() => setForm({ full_name: '', email: '', password: '', role: 'officer' })}>Add user</Button>} />
      {error && !form && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="users" label="Users" />
        <Tab value="requests" label={<Badge color="error" badgeContent={requests.length} sx={{ pr: 1.5 }}>Access requests</Badge>} />
      </Tabs>
      {tab === 'users' ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>Name</TableCell><TableCell>Email</TableCell><TableCell>Role</TableCell>
                <TableCell>Last login</TableCell><TableCell>Active</TableCell><TableCell /></TableRow>
            </TableHead>
            <TableBody>
              {rows.map((u) => (
                <TableRow key={u.user_id}>
                  <TableCell>{u.full_name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>
                    <TextField select size="small" value={u.role} disabled={u.user_id === me.user_id}
                      onChange={(e) => change(u, { role: e.target.value })} sx={{ minWidth: 120 }}>
                      {Object.keys(ROLES).map((r) => <MenuItem key={r} value={r} sx={{ textTransform: 'capitalize' }}>{r}</MenuItem>)}
                    </TextField>
                  </TableCell>
                  <TableCell>{dateTime(u.last_login)}</TableCell>
                  <TableCell>
                    <Switch checked={Boolean(u.is_active)} disabled={u.user_id === me.user_id}
                      onChange={(e) => change(u, { is_active: e.target.checked })} />
                  </TableCell>
                  <TableCell>
                    {u.user_id !== me.user_id && <Button size="small" onClick={() => reset(u)}>Reset password</Button>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Stack spacing={1.5}>
          {requests.length === 0 && <Typography color="text.secondary">No waiting requests.</Typography>}
          {requests.map((r) => (
            <Paper key={r.request_id} sx={{ p: 2 }}>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between">
                <div>
                  <Typography fontWeight={700}>{r.full_name} <Chip size="small" label={r.requested_role} sx={{ ml: 1 }} /></Typography>
                  <Typography color="text.secondary" fontSize={14}>{r.email}{r.organisation ? ` · ${r.organisation}` : ''} · {dateTime(r.created_at)}</Typography>
                  {r.reason && <Typography fontSize={14} sx={{ mt: 0.5 }}>"{r.reason}"</Typography>}
                </div>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Button variant="contained" color="success" onClick={() => decide(r, 'approved')}>Approve</Button>
                  <Button variant="outlined" color="inherit" onClick={() => decide(r, 'rejected')}>Reject</Button>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
      <SecretDialog secret={secret} onClose={() => setSecret(null)} />
      <Dialog open={Boolean(form)} onClose={() => setForm(null)} fullWidth maxWidth="sm">
        <DialogTitle>New user</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {form && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              <TextField label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              <TextField label="Temporary password" type="password" value={form.password}
                helperText="8+ characters with a letter and a number. Share it privately."
                onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <TextField select label="Role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {Object.entries(ROLES).map(([r, text]) => <MenuItem key={r} value={r}>{text}</MenuItem>)}
              </TextField>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setForm(null)}>Cancel</Button>
          <Button variant="contained" onClick={create}>Create</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
