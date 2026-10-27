/**
 * Profile.jsx - My account: name, change password, log out everywhere, my recent actions.
 * After an admin reset (temporary password) the user is sent here and must change it first.
 */
import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Button, Chip, Grid, List, ListItem, ListItemText, Paper, Stack, TextField, Typography,
} from '@mui/material';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import { logout, setSession, updateUser } from '../store/authSlice';
import { stopEvents } from '../services/events';
import { dateTime } from '../utils/format';

export default function Profile() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const user = useSelector((s) => s.auth.user);
  const [me, setMe] = useState(null);
  const [name, setName] = useState(user.full_name);
  const [pw, setPw] = useState({ old_password: '', new_password: '', confirm: '' });
  const [msg, setMsg] = useState(null);

  useEffect(() => { api.get('/auth/me').then((r) => setMe(r.data)).catch(() => {}); }, []);

  const saveName = async () => {
    try {
      await api.put('/auth/profile', { full_name: name });
      dispatch(updateUser({ full_name: name.trim() }));
      setMsg({ type: 'success', text: 'Name saved.' });
    } catch (e) { setMsg({ type: 'error', text: e.message }); }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    if (pw.new_password !== pw.confirm) { setMsg({ type: 'error', text: 'The two new passwords are different.' }); return; }
    try {
      const { data } = await api.post('/auth/change-password', { old_password: pw.old_password, new_password: pw.new_password });
      dispatch(setSession(data));
      setPw({ old_password: '', new_password: '', confirm: '' });
      setMsg({ type: 'success', text: 'Password changed. Your other sessions (other browsers / phones) were logged out.' });
      if (user.must_change_password) navigate('/');
    } catch (err) { setMsg({ type: 'error', text: err.message }); }
  };

  const logoutEverywhere = async () => {
    await api.post('/auth/logout-everywhere').catch(() => {});
    stopEvents();
    dispatch(logout());
    navigate('/login');
  };

  return (
    <>
      <PageHeader title="My profile" subtitle={`${user.email} · ${user.role}`} />
      {user.must_change_password && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          You are using a temporary password from an admin. Please choose your own password to continue.
        </Alert>
      )}
      {msg && <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg.text}</Alert>}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper component="form" onSubmit={changePassword} sx={{ p: 2.5 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Change password</Typography>
            <Stack spacing={2}>
              <TextField type="password" label="Current password" required value={pw.old_password}
                autoComplete="current-password" onChange={(e) => setPw({ ...pw, old_password: e.target.value })} />
              <TextField type="password" label="New password" required value={pw.new_password} autoComplete="new-password"
                helperText="8+ characters with a letter and a number" onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
              <TextField type="password" label="New password again" required value={pw.confirm} autoComplete="new-password"
                onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
              <Button type="submit" variant="contained">Change password</Button>
            </Stack>
          </Paper>
        </Grid>
        {!user.must_change_password && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2.5, mb: 2 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Account</Typography>
              <Stack direction="row" spacing={1.5}>
                <TextField size="small" fullWidth label="Full name" value={name} onChange={(e) => setName(e.target.value)} />
                <Button variant="outlined" onClick={saveName} disabled={name.trim().length < 2}>Save</Button>
              </Stack>
              <Stack direction="row" spacing={1} sx={{ mt: 2 }} alignItems="center">
                <Chip label={user.role} sx={{ textTransform: 'capitalize' }} />
                {me?.last_login && <Typography color="text.secondary" fontSize={13}>Last login {dateTime(me.last_login)}</Typography>}
              </Stack>
              <Button color="error" variant="outlined" sx={{ mt: 2 }} onClick={logoutEverywhere}>
                Log out on all devices
              </Button>
              <Typography color="text.secondary" fontSize={12.5} sx={{ mt: 1 }}>
                Use this if you logged in on a shared computer or lost your phone.
              </Typography>
            </Paper>
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="h6">My recent actions</Typography>
              <List dense>
                {(me?.recent_activity || []).map((a, i) => (
                  <ListItem key={i} disableGutters>
                    <ListItemText primary={`${a.action.replace(/_/g, ' ')}${a.target ? ` · ${a.target}` : ''}`} secondary={dateTime(a.created_at)} />
                  </ListItem>
                ))}
              </List>
            </Paper>
          </Grid>
        )}
      </Grid>
    </>
  );
}
