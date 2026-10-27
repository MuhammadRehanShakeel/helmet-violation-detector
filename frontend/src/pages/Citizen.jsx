/**
 * Citizen.jsx - PUBLIC citizen portal (no account).
 * A vehicle owner types the number plate AND the challan number from the paper/SMS challan,
 * then can see the evidence photo, pay (DEMO) or appeal. Appeals go to the officers' Appeals page.
 */
import { useEffect, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Divider, Grid, Link, Paper, Stack, TextField, Typography,
} from '@mui/material';
import api, { API_URL } from '../services/api';
import Logo from '../components/Logo';
import PlateBadge from '../components/PlateBadge';
import { colors } from '../theme';
import { dateTime, rupees } from '../utils/format';

const STATUS = { unpaid: 'warning', paid: 'success', cancelled: 'default' };

export default function Citizen() {
  const [params] = useSearchParams();
  const [form, setForm] = useState({ plate: params.get('plate') || '', challan_no: params.get('challan') || '' });
  const [challan, setChallan] = useState(null);
  const [error, setError] = useState('');
  const [appealText, setAppealText] = useState('');
  const [contact, setContact] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const lookup = async (e) => {
    e?.preventDefault();
    setError('');
    setNotice('');
    try {
      setChallan((await api.post('/public/challans/lookup', form)).data);
    } catch (err) {
      setChallan(null);
      setError(err.message);
    }
  };
  useEffect(() => { if (form.plate && form.challan_no) lookup(); }, []); // eslint-disable-line

  const pay = async () => {
    setBusy(true);
    try {
      const { data } = await api.post('/public/challans/pay', { token: challan.token });
      setNotice(`Paid (demo). Reference ${data.payment_ref}`);
      await lookup();
    } catch (err) { setError(err.message); }
    setBusy(false);
  };

  const appeal = async () => {
    setBusy(true);
    try {
      await api.post('/public/challans/appeal', { token: challan.token, reason: appealText, contact: contact || null });
      setNotice('Your appeal was sent. An officer will review it. Check back here with the same details.');
      setAppealText('');
      await lookup();
    } catch (err) { setError(err.message); }
    setBusy(false);
  };

  const appealOpen = challan && challan.status === 'unpaid' && !challan.appeal;

  return (
    <Box sx={{ minHeight: '100vh', p: { xs: 2, md: 4 }, maxWidth: 980, mx: 'auto' }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Logo />
        <Link component={RouterLink} to="/login" fontSize={14}>Officer sign in</Link>
      </Stack>
      <Typography variant="h4">Check your e-challan</Typography>
      <Typography color="text.secondary" sx={{ mb: 2.5 }}>
        Enter the number plate and the challan number printed on your challan. You can see the photo,
        pay, or appeal if you think it is wrong.
      </Typography>

      <Paper component="form" onSubmit={lookup} sx={{ p: 2, mb: 2.5 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField size="small" label="Number plate" placeholder="LEA-1234" required value={form.plate}
            onChange={(e) => setForm({ ...form, plate: e.target.value.toUpperCase() })} />
          <TextField size="small" label="Challan number" placeholder="RG-20261027-00010" required fullWidth
            value={form.challan_no} onChange={(e) => setForm({ ...form, challan_no: e.target.value.toUpperCase() })} />
          <Button type="submit" variant="contained">Find</Button>
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}

      {challan && (
        <Paper sx={{ p: { xs: 2, md: 3 } }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={7}>
              {challan.has_evidence && (
                <Box component="img" alt="Evidence"
                  src={`${API_URL}/public/challans/evidence?token=${encodeURIComponent(challan.token)}`}
                  sx={{ width: '100%', borderRadius: 2, bgcolor: '#000', maxHeight: 420, objectFit: 'contain' }} />
              )}
              <Typography color="text.secondary" fontSize={12.5} sx={{ mt: 1 }}>
                Other people in the photo are blurred to protect their privacy.
              </Typography>
            </Grid>
            <Grid item xs={12} md={5}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="h5">{challan.challan_no}</Typography>
                <Chip size="small" label={challan.status} color={STATUS[challan.status]} sx={{ textTransform: 'capitalize' }} />
              </Stack>
              <PlateBadge plate={challan.plate} size={20} />
              <Typography sx={{ mt: 2 }}><b>{challan.offence}</b></Typography>
              <Typography sx={{ mt: 0.5 }}>Fine: <b>{rupees(challan.fine)}</b></Typography>
              <Typography color="text.secondary" fontSize={14} sx={{ mt: 0.5 }}>
                {challan.camera}{challan.location ? ` · ${challan.location}` : ''}<br />
                Detected {dateTime(challan.detected_at)} · Issued {dateTime(challan.issued_at)}
              </Typography>
              {challan.status === 'paid' && (
                <Alert severity="success" sx={{ mt: 2 }}>Paid {dateTime(challan.paid_at)} · Ref {challan.payment_ref}</Alert>
              )}
              {challan.appeal && (
                <Alert severity={challan.appeal.status === 'accepted' ? 'success' : challan.appeal.status === 'rejected' ? 'error' : 'info'} sx={{ mt: 2 }}>
                  Appeal {challan.appeal.status}
                  {challan.appeal.response ? `: "${challan.appeal.response}"` : ' - an officer is reviewing it.'}
                </Alert>
              )}

              {challan.status === 'unpaid' && (!challan.appeal || challan.appeal.status === 'rejected') && (
                <>
                  <Divider sx={{ my: 2.5 }} />
                  <Button fullWidth variant="contained" color="success" disabled={busy} onClick={pay}>
                    Pay {rupees(challan.fine)} (demo)
                  </Button>
                  <Typography color="text.secondary" fontSize={12} sx={{ mt: 0.8 }}>
                    Demo only: no money moves and no card details are asked for. A real system would open
                    1Link / JazzCash / Easypaisa here.
                  </Typography>
                </>
              )}
              {appealOpen && (
                <Box sx={{ mt: 2.5, p: 2, border: `1px solid ${colors.line}`, borderRadius: 2 }}>
                  <Typography fontWeight={700}>Think this is wrong? Appeal</Typography>
                  <TextField fullWidth multiline minRows={3} size="small" sx={{ mt: 1 }} value={appealText}
                    onChange={(e) => setAppealText(e.target.value)}
                    placeholder="Explain why, e.g. 'I was wearing a helmet, it is visible in the photo.'" />
                  <TextField fullWidth size="small" sx={{ mt: 1 }} label="Phone or email (optional)" value={contact}
                    onChange={(e) => setContact(e.target.value)} />
                  <Button sx={{ mt: 1 }} variant="outlined" disabled={busy || appealText.trim().length < 10} onClick={appeal}>
                    Send appeal
                  </Button>
                </Box>
              )}
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
}
