/** Users.jsx - (admin) Create officers and viewers, change roles, disable accounts. */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, Switch, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
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

export default function Users() {
  const me = useSelector((s) => s.auth.user);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState('');

  const load = () => api.get('/users').then((r) => setRows(r.data)).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const change = async (u, body) => {
    setError('');
    try { await api.put(`/users/${u.user_id}`, body); load(); } catch (e) { setError(e.message); }
  };

  const create = async () => {
    setError('');
    try { await api.post('/users', form); setForm(null); load(); } catch (e) { setError(e.message); }
  };

  return (
    <>
      <PageHeader title="Users" subtitle="Only admins create accounts. There is no public sign-up."
        action={<Button variant="contained" startIcon={<AddIcon />}
          onClick={() => setForm({ full_name: '', email: '', password: '', role: 'officer' })}>Add user</Button>} />
      {error && !form && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>Name</TableCell><TableCell>Email</TableCell><TableCell>Role</TableCell>
              <TableCell>Last login</TableCell><TableCell>Active</TableCell></TableRow>
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
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
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
              <Typography color="text.secondary" fontSize={12.5}>Every change is written to the audit log.</Typography>
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
