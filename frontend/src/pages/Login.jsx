/**
 * Login.jsx - There is no public sign-up: accounts are created by an admin (Users page).
 */
import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Navigate } from 'react-router-dom';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { clearError, login } from '../store/authSlice';
import Logo from '../components/Logo';
import { colors } from '../theme';

export default function Login() {
  const dispatch = useDispatch();
  const { user, loading, error } = useSelector((s) => s.auth);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => { dispatch(clearError()); }, [dispatch]);
  if (user) return <Navigate to="/" replace />;

  const submit = (e) => {
    e.preventDefault();
    dispatch(login({ email: email.trim(), password }));
  };

  return (
    <Box sx={{
      minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2,
      background: `radial-gradient(ellipse at 20% 10%, rgba(245,179,1,0.10), transparent 45%),
                   repeating-linear-gradient(-45deg, transparent 0 22px, rgba(255,255,255,0.015) 22px 44px), ${colors.bg}`,
    }}>
      <Paper component="form" onSubmit={submit} sx={{ width: '100%', maxWidth: 400, p: { xs: 3, sm: 4 } }}>
        <Logo />
        <Typography variant="h5" sx={{ mt: 3 }}>Officer sign in</Typography>
        <Typography color="text.secondary" fontSize={14} sx={{ mb: 2.5 }}>
          Accounts are created by your RoadGuard admin.
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField label="Email" type="email" fullWidth required autoComplete="username" value={email}
          onChange={(e) => setEmail(e.target.value)} sx={{ mb: 2 }} />
        <TextField label="Password" type="password" fullWidth required autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)} sx={{ mb: 3 }} />
        <Button type="submit" variant="contained" size="large" fullWidth disabled={loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </Button>
        <Typography color="text.secondary" fontSize={12} sx={{ mt: 2.5, textAlign: 'center' }}>
          5 wrong passwords lock the account for 15 minutes.
        </Typography>
      </Paper>
    </Box>
  );
}
