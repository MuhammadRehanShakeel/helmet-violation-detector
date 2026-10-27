/**
 * PlateSearch.jsx - Type a number plate, see every violation of that vehicle (repeat offenders).
 */
import { useState } from 'react';
import {
  Alert, Box, Button, Chip, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import PlateBadge from '../components/PlateBadge';
import ViolationDialog from '../components/ViolationDialog';
import { dateTime, rupees, STATUS_COLOR } from '../utils/format';

export default function PlateSearch() {
  const [plate, setPlate] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);

  const search = async (e) => {
    e?.preventDefault();
    setError('');
    try {
      setResult((await api.get(`/plates/${encodeURIComponent(plate.trim())}`)).data);
    } catch (err) {
      setResult(null);
      setError(err.message);
    }
  };

  return (
    <>
      <PageHeader title="Plate search" subtitle="Full history of one vehicle. Spaces and dashes don't matter." />
      <Paper component="form" onSubmit={search} sx={{ p: 2, mb: 2.5 }}>
        <Stack direction="row" spacing={1.5}>
          <TextField size="small" fullWidth label="Number plate" placeholder="LEA-1234" value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())} />
          <Button type="submit" variant="contained" startIcon={<SearchIcon />} disabled={plate.trim().length < 3}>Search</Button>
        </Stack>
      </Paper>
      {error && <Alert severity="error">{error}</Alert>}
      {result && (
        <>
          <Paper sx={{ p: 2.5, mb: 2, display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
            <PlateBadge plate={result.plate} size={26} />
            <Box>
              <Typography color="text.secondary" fontSize={12}>VIOLATIONS</Typography>
              <Typography variant="h5">{result.total}</Typography>
            </Box>
            <Box>
              <Typography color="text.secondary" fontSize={12}>APPROVED FINES</Typography>
              <Typography variant="h5">{rupees(result.unpaid_fines)}</Typography>
            </Box>
            {result.repeat_offender && <Chip color="error" label="Repeat offender" />}
          </Paper>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell><TableCell>Offence</TableCell><TableCell>Camera</TableCell>
                  <TableCell>Date</TableCell><TableCell>Status</TableCell><TableCell>Challan</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.items.length === 0 && <TableRow><TableCell colSpan={6}>No violations for this plate.</TableCell></TableRow>}
                {result.items.map((v) => (
                  <TableRow key={v.violation_id} hover sx={{ cursor: 'pointer' }} onClick={() => setOpenId(v.violation_id)}>
                    <TableCell>{v.violation_id}</TableCell>
                    <TableCell>{v.violation_label}</TableCell>
                    <TableCell>{v.camera_name || 'Uploaded'}</TableCell>
                    <TableCell>{dateTime(v.created_at)}</TableCell>
                    <TableCell><Chip size="small" label={v.status} color={STATUS_COLOR[v.status]} /></TableCell>
                    <TableCell>{v.challan_no || '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
      <ViolationDialog id={openId} onClose={() => setOpenId(null)} onChanged={search} />
    </>
  );
}
