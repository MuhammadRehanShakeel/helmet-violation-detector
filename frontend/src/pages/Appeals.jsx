/**
 * Appeals.jsx - Officers decide citizen appeals. Accepting one cancels the challan.
 */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Alert, Box, Button, Card, Chip, Grid, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import PrivateImage from '../components/PrivateImage';
import PlateBadge from '../components/PlateBadge';
import { dateTime, percent, rupees } from '../utils/format';

function AppealCard({ a, onDone }) {
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');
  const decide = async (decision) => {
    setError('');
    try { await api.post(`/appeals/${a.appeal_id}/decide`, { decision, response }); onDone(); } catch (e) { setError(e.message); }
  };
  return (
    <Card sx={{ p: 2 }}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <PrivateImage path={`/violations/${a.violation_id}/image/evidence`} alt="Evidence" height={220}
            sx={{ borderRadius: 2, objectFit: 'contain', bgcolor: '#000' }} />
        </Grid>
        <Grid item xs={12} md={7}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="h6">{a.challan_no}</Typography>
            <PlateBadge plate={a.plate_text} />
            <Chip size="small" label={a.offence} color="error" />
            <Chip size="small" label={`AI ${percent(a.confidence)}`} variant="outlined" />
          </Stack>
          <Typography color="text.secondary" fontSize={13} sx={{ mt: 0.5 }}>
            Fine {rupees(a.fine_amount)} · appeal sent {dateTime(a.created_at)}{a.contact ? ` · contact: ${a.contact}` : ''}
          </Typography>
          <Box sx={{ mt: 1.5, p: 1.5, bgcolor: 'background.default', borderRadius: 2 }}>
            <Typography fontSize={14}>"{a.reason}"</Typography>
          </Box>
          {a.status === 'pending' ? (
            <>
              {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
              <TextField fullWidth size="small" sx={{ mt: 1.5 }} label="Answer to the citizen (required)" value={response}
                onChange={(e) => setResponse(e.target.value)} />
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button variant="contained" color="success" disabled={response.trim().length < 3} onClick={() => decide('accepted')}>
                  Accept (cancel challan)
                </Button>
                <Button variant="outlined" color="inherit" disabled={response.trim().length < 3} onClick={() => decide('rejected')}>
                  Reject
                </Button>
              </Stack>
            </>
          ) : (
            <Typography sx={{ mt: 1.5 }} fontSize={14}>
              <b>{a.status}</b> by {a.decided_by_name}, {dateTime(a.decided_at)}: "{a.response}"
            </Typography>
          )}
        </Grid>
      </Grid>
    </Card>
  );
}

export default function Appeals() {
  const tick = useSelector((s) => s.notifications.tick);
  const [status, setStatus] = useState('pending');
  const [items, setItems] = useState([]);
  const load = () => api.get('/appeals', { params: { status } }).then((r) => setItems(r.data));
  useEffect(() => { load(); }, [status, tick]); // eslint-disable-line

  return (
    <>
      <PageHeader title="Appeals" subtitle="Citizens who think their challan is wrong. Check the photo and decide." />
      <Tabs value={status} onChange={(e, v) => setStatus(v)} sx={{ mb: 2 }}>
        <Tab value="pending" label="Waiting" />
        <Tab value="accepted" label="Accepted" />
        <Tab value="rejected" label="Rejected" />
      </Tabs>
      {items.length === 0 && <Typography color="text.secondary">No appeals here.</Typography>}
      <Stack spacing={2}>
        {items.map((a) => <AppealCard key={a.appeal_id} a={a} onDone={load} />)}
      </Stack>
    </>
  );
}
