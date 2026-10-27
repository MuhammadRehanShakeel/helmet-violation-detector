/**
 * ViolationDialog.jsx - The officer's decision screen for one violation.
 * Shows the evidence, lets the officer fix the number plate, approve or reject,
 * and issue the PDF e-challan for approved violations.
 */
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Alert, Box, Button, Chip, Dialog, DialogContent, DialogTitle, Grid, IconButton, Stack, TextField, Typography,
  useMediaQuery,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/CheckCircleOutline';
import BlockIcon from '@mui/icons-material/DoNotDisturbOnOutlined';
import ReceiptIcon from '@mui/icons-material/ReceiptLongOutlined';
import WarningIcon from '@mui/icons-material/WarningAmberRounded';
import api, { downloadFile } from '../services/api';
import PrivateImage from './PrivateImage';
import PlateBadge from './PlateBadge';
import { colors } from '../theme';
import { canReview, dateTime, percent, rupees, STATUS_COLOR } from '../utils/format';

function Fact({ label, children }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.8, borderBottom: `1px solid ${colors.line}`, gap: 2 }}>
      <Typography color="text.secondary" fontSize={13.5}>{label}</Typography>
      <Box sx={{ fontSize: 14, fontWeight: 600, textAlign: 'right' }}>{children}</Box>
    </Box>
  );
}

export default function ViolationDialog({ id, onClose, onChanged }) {
  const user = useSelector((s) => s.auth.user);
  const [v, setV] = useState(null);
  const [plate, setPlate] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const phone = useMediaQuery('(max-width:600px)');

  const load = () => api.get(`/violations/${id}`).then((r) => { setV(r.data); setPlate(r.data.plate_text || ''); })
    .catch((e) => setError(e.message));
  useEffect(() => { if (id) { setV(null); setError(''); setNote(''); load(); } }, [id]); // eslint-disable-line

  const review = async (decision) => {
    setBusy(true);
    setError('');
    try {
      await api.put(`/violations/${id}/review`, {
        decision, note: note || null, plate_text: plate !== (v.plate_text || '') ? plate : null,
      });
      await load();
      onChanged?.();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const challan = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post(`/violations/${id}/challan`);
      await downloadFile(`/challans/${data.challan_id}/pdf`, `${data.challan_no}.pdf`);
      await load();
      onChanged?.();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const officer = canReview(user);
  const locked = v?.challan_id;

  return (
    <Dialog open={Boolean(id)} onClose={onClose} maxWidth="lg" fullWidth fullScreen={phone} scroll="body">
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        <Typography variant="h5" component="span">Violation #{id}</Typography>
        {v && <Chip label={v.violation_label} color="error" size="small" />}
        {v && <Chip label={v.status} color={STATUS_COLOR[v.status]} size="small" sx={{ textTransform: 'capitalize' }} />}
        {v?.low_confidence && <Chip icon={<WarningIcon />} label="Low AI confidence: check carefully" color="warning" size="small" variant="outlined" />}
        <IconButton onClick={onClose} sx={{ ml: 'auto' }}><CloseIcon /></IconButton>
      </DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {v && (
          <Grid container spacing={2.5}>
            <Grid item xs={12} md={8}>
              <PrivateImage path={`/violations/${id}/image/evidence`} alt="Evidence" height="auto"
                sx={{ borderRadius: 2, maxHeight: 520, objectFit: 'contain', bgcolor: '#000' }} />
              <Typography color="text.secondary" fontSize={12.5} sx={{ mt: 1 }}>
                Other road users' faces and number plates are blurred automatically.
              </Typography>
              <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
                <Grid item xs={6}>
                  <Typography fontSize={12.5} color="text.secondary" sx={{ mb: 0.5 }}>Motorcyclist</Typography>
                  <PrivateImage path={`/violations/${id}/image/crop`} alt="Motorcyclist" height={200}
                    sx={{ borderRadius: 2, objectFit: 'contain', bgcolor: '#000' }} />
                </Grid>
                {user.role !== 'viewer' && v.plate_available && (
                  <Grid item xs={6}>
                    <Typography fontSize={12.5} color="text.secondary" sx={{ mb: 0.5 }}>Number plate</Typography>
                    <PrivateImage path={`/violations/${id}/image/plate`} alt="Plate" height={110}
                      sx={{ borderRadius: 2, objectFit: 'contain', bgcolor: '#000' }} />
                  </Grid>
                )}
              </Grid>
            </Grid>
            <Grid item xs={12} md={4}>
              <Fact label="Number plate"><PlateBadge plate={v.plate_text} /></Fact>
              {v.plate_raw && <Fact label="OCR read">{v.plate_raw} ({percent(v.plate_confidence)})</Fact>}
              <Fact label="AI confidence">{percent(v.confidence)}</Fact>
              <Fact label="People on bike">{v.riders} ({v.no_helmet_count} without helmet)</Fact>
              <Fact label="Camera">{v.camera_name || 'Uploaded media'}</Fact>
              {v.frame_time !== null && <Fact label="Video time">{v.frame_time}s</Fact>}
              <Fact label="Detected">{dateTime(v.created_at)}</Fact>
              <Fact label="Fine">{rupees(v.fine)}</Fact>
              {v.previous_violations > 0 && (
                <Alert severity="error" icon={<WarningIcon />} sx={{ mt: 1.5 }}>
                  Repeat offender: {v.previous_violations} other violation(s) with this plate.
                </Alert>
              )}
              {v.reviewed_by_name && (
                <Typography color="text.secondary" fontSize={13} sx={{ mt: 1.5 }}>
                  {v.status === 'approved' ? 'Approved' : 'Rejected'} by {v.reviewed_by_name}, {dateTime(v.reviewed_at)}
                  {v.review_note ? `: "${v.review_note}"` : ''}
                </Typography>
              )}

              {officer && !locked && (
                <Stack spacing={1.5} sx={{ mt: 2.5 }}>
                  <TextField size="small" label="Number plate (correct it if the AI misread it)" value={plate}
                    onChange={(e) => setPlate(e.target.value.toUpperCase())} placeholder="LEA-1234" />
                  <TextField size="small" label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                  <Stack direction="row" spacing={1}>
                    <Button fullWidth variant="contained" color="success" startIcon={<CheckIcon />} disabled={busy}
                      onClick={() => review('approved')}>Approve</Button>
                    <Button fullWidth variant="outlined" color="inherit" startIcon={<BlockIcon />} disabled={busy}
                      onClick={() => review('rejected')}>Reject</Button>
                  </Stack>
                </Stack>
              )}
              {officer && v.status === 'approved' && (
                <Button fullWidth variant="contained" startIcon={<ReceiptIcon />} sx={{ mt: 2 }} disabled={busy} onClick={challan}>
                  {locked ? `Download e-challan ${v.challan_no}` : 'Issue e-challan (PDF)'}
                </Button>
              )}
            </Grid>
          </Grid>
        )}
      </DialogContent>
    </Dialog>
  );
}
