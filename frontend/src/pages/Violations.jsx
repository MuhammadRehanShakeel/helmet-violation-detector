/**
 * Violations.jsx - The review queue. Every AI detection waits here until an officer approves or rejects it.
 */
import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  Alert, Box, Card, CardActionArea, Chip, FormControlLabel, Grid, LinearProgress, MenuItem, Pagination,
  Paper, Stack, Switch, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import { fetchViolations, setFilter, setPage } from '../store/violationsSlice';
import PageHeader from '../components/PageHeader';
import PrivateImage from '../components/PrivateImage';
import PlateBadge from '../components/PlateBadge';
import CameraSelect from '../components/CameraSelect';
import ViolationDialog from '../components/ViolationDialog';
import { colors } from '../theme';
import { dateTime, percent, STATUS_COLOR, VIOLATION_LABEL } from '../utils/format';

export default function Violations() {
  const dispatch = useDispatch();
  const { items, total, page, loading, error, filters } = useSelector((s) => s.violations);
  const role = useSelector((s) => s.auth.user.role);
  const [openId, setOpenId] = useState(null);
  const tick = useSelector((s) => s.notifications.tick);       // live: new detections appear by themselves

  useEffect(() => { dispatch(fetchViolations()); }, [dispatch, filters, page, tick]);

  return (
    <>
      <PageHeader title="Review queue" subtitle="Every AI detection is checked by a human before a challan is issued" />
      <Paper sx={{ px: 2, pt: 1, pb: 2, mb: 2.5 }}>
        <Tabs value={filters.status} onChange={(e, v) => dispatch(setFilter({ status: v }))} variant="scrollable" sx={{ mb: 1.5 }}>
          <Tab value="pending" label="Pending" />
          <Tab value="approved" label="Approved" />
          <Tab value="rejected" label="Rejected" />
          <Tab value="" label="All" />
        </Tabs>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
          <TextField select size="small" label="Type" value={filters.violation_type} sx={{ minWidth: 170 }}
            onChange={(e) => dispatch(setFilter({ violation_type: e.target.value }))}>
            <MenuItem value="">All types</MenuItem>
            <MenuItem value="NO_HELMET">No helmet</MenuItem>
            <MenuItem value="TRIPLE_RIDING">Triple riding</MenuItem>
          </TextField>
          <CameraSelect allowAll value={filters.camera_id} onChange={(v) => dispatch(setFilter({ camera_id: v }))} />
          {role !== 'viewer' && (
            <TextField size="small" label="Plate" value={filters.plate} placeholder="LEA-1234"
              onChange={(e) => dispatch(setFilter({ plate: e.target.value }))} />
          )}
          <FormControlLabel control={<Switch checked={filters.low_confidence}
            onChange={(e) => dispatch(setFilter({ low_confidence: e.target.checked }))} />} label="Low confidence only" />
          {filters.job_id && (
            <Chip label={`Analysis #${filters.job_id}`} onDelete={() => dispatch(setFilter({ job_id: '' }))} />
          )}
        </Stack>
      </Paper>

      {loading && <LinearProgress sx={{ mb: 2 }} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!loading && items.length === 0 && <Typography color="text.secondary">No violations match these filters.</Typography>}

      <Grid container spacing={2}>
        {items.map((v) => (
          <Grid item xs={12} sm={6} lg={4} xl={3} key={v.violation_id}>
            <Card sx={{ border: `1px solid ${v.status === 'pending' ? colors.line : colors.line}` }}>
              <CardActionArea onClick={() => setOpenId(v.violation_id)}>
                <Box sx={{ position: 'relative' }}>
                  <PrivateImage path={`/violations/${v.violation_id}/image/crop`} alt="" height={190}
                    sx={{ objectFit: 'contain', bgcolor: '#000' }} />
                  <Chip size="small" label={VIOLATION_LABEL[v.violation_type]}
                    sx={{ position: 'absolute', top: 8, left: 8, bgcolor: v.violation_type === 'NO_HELMET' ? colors.red : colors.amber,
                      color: v.violation_type === 'NO_HELMET' ? '#fff' : '#111' }} />
                  {v.low_confidence && (
                    <Chip size="small" label="Check" color="warning" sx={{ position: 'absolute', top: 8, right: 8 }} />
                  )}
                </Box>
                <Box sx={{ p: 1.5 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <PlateBadge plate={v.plate_text} />
                    <Chip size="small" label={v.status} color={STATUS_COLOR[v.status]} sx={{ textTransform: 'capitalize' }} />
                  </Stack>
                  <Typography fontSize={12.5} color="text.secondary" sx={{ mt: 1 }}>
                    #{v.violation_id} · {v.camera_name || 'Uploaded'} · {dateTime(v.created_at)} · AI {percent(v.confidence)}
                  </Typography>
                </Box>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
      {total > 24 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={Math.ceil(total / 24)} page={page} onChange={(e, p) => dispatch(setPage(p))} />
        </Box>
      )}
      <ViolationDialog id={openId} onClose={() => setOpenId(null)} onChanged={() => dispatch(fetchViolations())} />
    </>
  );
}
