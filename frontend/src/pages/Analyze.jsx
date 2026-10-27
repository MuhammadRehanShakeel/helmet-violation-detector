/**
 * Analyze.jsx - Upload road photos or videos. Each upload becomes a background job;
 * this page polls the jobs every 2 seconds while any of them is still running.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, LinearProgress, Paper, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUploadOutlined';
import { fetchJobs, uploadMedia } from '../store/jobsSlice';
import { setFilter } from '../store/violationsSlice';
import PageHeader from '../components/PageHeader';
import CameraSelect from '../components/CameraSelect';
import { colors } from '../theme';
import { dateTime } from '../utils/format';

const STATUS = { queued: 'default', running: 'info', done: 'success', failed: 'error' };

export default function Analyze() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const jobs = useSelector((s) => s.jobs.items);
  const [cameraId, setCameraId] = useState('');
  const [uploading, setUploading] = useState(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const input = useRef();

  const busy = jobs.some((j) => j.status === 'queued' || j.status === 'running');
  const tick = useSelector((s) => s.notifications.tick);
  useEffect(() => { dispatch(fetchJobs()); }, [dispatch, tick]);
  useEffect(() => {
    if (!busy) return undefined;
    const t = setInterval(() => dispatch(fetchJobs()), 2000);
    return () => clearInterval(t);
  }, [busy, dispatch]);

  const upload = useCallback(async (files) => {
    setError('');
    for (const file of files) {
      setUploading({ name: file.name, progress: 0 });
      const res = await dispatch(uploadMedia({
        file, cameraId, onProgress: (p) => setUploading({ name: file.name, progress: p }),
      }));
      if (res.error) setError(`${file.name}: ${res.payload}`);
    }
    setUploading(null);
    dispatch(fetchJobs());
  }, [cameraId, dispatch]);

  const openViolations = (job) => {
    dispatch(setFilter({ job_id: job.job_id, status: '' }));
    navigate('/violations');
  };

  return (
    <>
      <PageHeader title="Analyse media" subtitle="Upload photos or videos from traffic cameras or a phone" />
      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <CameraSelect value={cameraId} onChange={setCameraId} />
        </Stack>
        <Box
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); upload([...e.dataTransfer.files]); }}
          onClick={() => input.current.click()}
          sx={{
            border: `2px dashed ${dragging ? colors.amber : colors.line}`, borderRadius: 3, p: { xs: 3, md: 5 },
            textAlign: 'center', cursor: 'pointer', bgcolor: dragging ? 'rgba(245,179,1,0.06)' : 'transparent',
            transition: '0.15s', '&:hover': { borderColor: colors.amber },
          }}
        >
          <CloudUploadIcon sx={{ fontSize: 46, color: colors.amber }} />
          <Typography variant="h6" sx={{ mt: 1 }}>Drop photos or videos here, or click to choose</Typography>
          <Typography color="text.secondary" fontSize={13.5}>
            JPG, PNG, WEBP up to 15 MB · MP4, MOV, AVI, MKV, WEBM up to 300 MB and 10 minutes
          </Typography>
          <input ref={input} type="file" hidden multiple accept="image/jpeg,image/png,image/webp,video/*"
            onChange={(e) => { upload([...e.target.files]); e.target.value = ''; }} />
        </Box>
        {uploading && (
          <Box sx={{ mt: 2 }}>
            <Typography fontSize={13.5}>Uploading {uploading.name} ... {uploading.progress}%</Typography>
            <LinearProgress variant="determinate" value={uploading.progress} sx={{ mt: 0.5 }} />
          </Box>
        )}
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </Paper>

      <Typography variant="h6" sx={{ mb: 1.5 }}>Recent analyses</Typography>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>File</TableCell>
              <TableCell>Camera</TableCell>
              <TableCell sx={{ minWidth: 200 }}>Progress</TableCell>
              <TableCell align="right">Bikes</TableCell>
              <TableCell align="right">Violations</TableCell>
              <TableCell>Time</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {jobs.length === 0 && (
              <TableRow><TableCell colSpan={7} sx={{ color: 'text.secondary' }}>Nothing analysed yet.</TableCell></TableRow>
            )}
            {jobs.map((j) => (
              <TableRow key={j.job_id} hover>
                <TableCell sx={{ maxWidth: 220 }}>
                  <Typography noWrap fontSize={14}>{j.original_name}</Typography>
                  <Typography fontSize={12} color="text.secondary">{j.kind} · {dateTime(j.created_at)}</Typography>
                </TableCell>
                <TableCell>{j.camera_name || '-'}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip size="small" label={j.status} color={STATUS[j.status]} />
                    {j.status === 'running' && <Typography fontSize={12} color="text.secondary">{j.stage}</Typography>}
                  </Stack>
                  {j.status === 'running' && <LinearProgress variant="determinate" value={j.progress} sx={{ mt: 0.7 }} />}
                  {j.status === 'failed' && <Typography fontSize={12} color="error">{j.error}</Typography>}
                </TableCell>
                <TableCell align="right">{j.motorcyclists}</TableCell>
                <TableCell align="right">
                  <Typography fontWeight={700} color={j.violations ? colors.red : 'text.secondary'}>{j.violations}</Typography>
                </TableCell>
                <TableCell>{j.seconds_taken ? `${j.seconds_taken}s` : '-'}</TableCell>
                <TableCell>
                  {j.status === 'done' && j.violations > 0 && (
                    <Button size="small" onClick={() => openViolations(j)}>Review</Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
