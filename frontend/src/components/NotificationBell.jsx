/**
 * NotificationBell.jsx - Live notifications: a bell with a counter + a short pop-up (toast) for each new event.
 */
import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Badge, Box, IconButton, List, ListItemButton, ListItemText, Popover, Snackbar, Tooltip, Typography,
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { onEvent, startEvents, stopEvents } from '../services/events';
import { markRead, received, setConnection } from '../store/notificationsSlice';
import { colors } from '../theme';
import { dateTime } from '../utils/format';

function describe(e) {
  switch (e.type) {
    case 'violation':
      return { text: `${e.label} · ${e.camera}${e.plate ? ` · ${e.plate}` : ''}`, severity: 'error', link: '/violations' };
    case 'appeal':
      return { text: `New appeal for challan ${e.challan_no}`, severity: 'warning', link: '/appeals' };
    case 'payment':
      return { text: `Challan ${e.challan_no} paid (demo)`, severity: 'success', link: '/violations' };
    case 'access_request':
      return { text: `${e.name} asked for an account`, severity: 'info', link: '/users' };
    case 'stream':
      return { text: `Camera ${e.camera}: ${e.status}${e.error ? ` (${e.error})` : ''}`,
        severity: e.status === 'live' ? 'success' : 'warning', link: '/cctv' };
    default:
      return null;
  }
}

export default function NotificationBell() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { items, unread, connection } = useSelector((s) => s.notifications);
  const [anchor, setAnchor] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const off = onEvent((e) => {
      dispatch(received(e));
      const d = describe(e);
      if (d) setToast({ ...d, key: Date.now() });
    });
    startEvents((status) => dispatch(setConnection(status)));
    return () => { off(); stopEvents(); };
  }, [dispatch]);

  return (
    <>
      <Tooltip title={connection === 'connected' ? 'Live updates on' : 'Connecting to live updates...'}>
        <IconButton aria-label="Notifications" onClick={(e) => { setAnchor(e.currentTarget); dispatch(markRead()); }} size="small">
          <Badge badgeContent={unread} color="error" max={99}>
            <NotificationsIcon sx={{ color: connection === 'connected' ? colors.text : colors.muted }} />
          </Badge>
        </IconButton>
      </Tooltip>
      <Popover open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <Box sx={{ width: 340, maxHeight: 420, overflow: 'auto' }}>
          <Typography variant="h6" sx={{ px: 2, pt: 1.5 }}>Live notifications</Typography>
          {items.length === 0 && <Typography color="text.secondary" sx={{ p: 2 }} fontSize={14}>Nothing yet. New violations appear here instantly.</Typography>}
          <List dense>
            {items.map((e) => {
              const d = describe(e);
              return (
                <ListItemButton key={e.id} onClick={() => { setAnchor(null); navigate(d.link); }}>
                  <ListItemText primary={d.text} secondary={dateTime(e.at)} />
                </ListItemButton>
              );
            })}
          </List>
        </Box>
      </Popover>
      <Snackbar key={toast?.key} open={Boolean(toast)} autoHideDuration={6000} onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        {toast ? (
          <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)} sx={{ cursor: 'pointer' }}
            onClick={() => { setToast(null); navigate(toast.link); }}>
            {toast.text}
          </Alert>
        ) : <span />}
      </Snackbar>
    </>
  );
}
