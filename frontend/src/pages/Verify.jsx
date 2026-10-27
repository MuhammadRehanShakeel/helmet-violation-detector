/** Verify.jsx - PUBLIC page opened from the QR code on a paper e-challan. Shows only what the ticket shows. */
import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Box, Button, Chip, Paper, Typography } from '@mui/material';
import VerifiedIcon from '@mui/icons-material/VerifiedOutlined';
import api from '../services/api';
import Logo from '../components/Logo';
import PlateBadge from '../components/PlateBadge';
import { colors } from '../theme';
import { dateTime, rupees } from '../utils/format';

export default function Verify() {
  const { code } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.get(`/challans/verify/${code}`).then((r) => setData(r.data)).catch((e) => setError(e.message)); }, [code]);

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 420, width: '100%' }}>
        <Logo />
        {error && <Alert severity="error" sx={{ mt: 3 }}>{error}</Alert>}
        {data && (
          <Box sx={{ mt: 3 }}>
            <Typography sx={{ display: 'flex', alignItems: 'center', gap: 1, color: colors.green, fontWeight: 700 }}>
              <VerifiedIcon /> This e-challan is genuine
            </Typography>
            <Typography variant="h5" sx={{ mt: 2 }}>{data.challan_no}</Typography>
            <Typography sx={{ mt: 1 }}>{data.offence}</Typography>
            <Typography sx={{ mt: 1 }}>Fine: <b>{rupees(data.fine)}</b></Typography>
            <Typography sx={{ mt: 1 }}>Issued: {dateTime(data.issued_at)}</Typography>
            <Box sx={{ mt: 1.5 }}><PlateBadge plate={data.plate} size={20} /></Box>
            <Chip sx={{ mt: 2, textTransform: 'capitalize' }} label={data.status}
              color={{ paid: 'success', cancelled: 'default', unpaid: 'warning' }[data.status] || 'default'} />
            <Button component={RouterLink} to="/citizen" fullWidth variant="contained" sx={{ mt: 3 }}>
              See the photo, pay or appeal
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
