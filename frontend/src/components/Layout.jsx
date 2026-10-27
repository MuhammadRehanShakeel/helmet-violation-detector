/**
 * Layout.jsx - Side menu (desktop) / drawer (phone) around every page.
 * Menu items are filtered by role, but the BACKEND enforces the real permissions.
 */
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import {
  AppBar, Avatar, Box, Chip, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText,
  Toolbar, Tooltip, Typography, useMediaQuery,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/SpaceDashboardOutlined';
import UploadIcon from '@mui/icons-material/CloudUploadOutlined';
import LiveIcon from '@mui/icons-material/VideocamOutlined';
import ReviewIcon from '@mui/icons-material/FactCheckOutlined';
import PlateIcon from '@mui/icons-material/PinOutlined';
import CameraIcon from '@mui/icons-material/PlaceOutlined';
import UsersIcon from '@mui/icons-material/GroupOutlined';
import AuditIcon from '@mui/icons-material/HistoryOutlined';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/LogoutOutlined';
import { logout } from '../store/authSlice';
import { colors } from '../theme';
import Logo from './Logo';

const WIDTH = 236;
const MENU = [
  { to: '/', label: 'Dashboard', icon: <DashboardIcon />, roles: ['admin', 'officer', 'viewer'] },
  { to: '/analyze', label: 'Analyse media', icon: <UploadIcon />, roles: ['admin', 'officer'] },
  { to: '/live', label: 'Live camera', icon: <LiveIcon />, roles: ['admin', 'officer'] },
  { to: '/violations', label: 'Review queue', icon: <ReviewIcon />, roles: ['admin', 'officer', 'viewer'] },
  { to: '/plates', label: 'Plate search', icon: <PlateIcon />, roles: ['admin', 'officer'] },
  { to: '/cameras', label: 'Cameras', icon: <CameraIcon />, roles: ['admin'] },
  { to: '/users', label: 'Users', icon: <UsersIcon />, roles: ['admin'] },
  { to: '/audit', label: 'Audit log', icon: <AuditIcon />, roles: ['admin'] },
];

export default function Layout() {
  const user = useSelector((s) => s.auth.user);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const desktop = useMediaQuery('(min-width:900px)');
  const [open, setOpen] = useState(false);

  const menu = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: colors.panel }}>
      <Box sx={{ px: 2.5, py: 2.2 }}>
        <Logo />
      </Box>
      <List sx={{ px: 1.2, flex: 1 }}>
        {MENU.filter((m) => m.roles.includes(user.role)).map((m) => (
          <ListItemButton
            key={m.to}
            component={NavLink}
            to={m.to}
            end={m.to === '/'}
            onClick={() => setOpen(false)}
            sx={{
              borderRadius: 2, mb: 0.4, color: colors.muted,
              '&.active': { bgcolor: 'rgba(245,179,1,0.12)', color: colors.amber, '& svg': { color: colors.amber } },
            }}
          >
            <ListItemIcon sx={{ minWidth: 38, color: 'inherit' }}>{m.icon}</ListItemIcon>
            <ListItemText primary={m.label} primaryTypographyProps={{ fontSize: 14.5, fontWeight: 600 }} />
          </ListItemButton>
        ))}
      </List>
      <Box sx={{ p: 2, borderTop: `1px solid ${colors.line}`, display: 'flex', alignItems: 'center', gap: 1.2 }}>
        <Avatar sx={{ bgcolor: colors.panelHigh, color: colors.amber, width: 36, height: 36, fontWeight: 700 }}>
          {user.full_name?.[0]?.toUpperCase()}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography noWrap fontSize={14} fontWeight={600}>{user.full_name}</Typography>
          <Chip label={user.role} size="small" sx={{ height: 18, fontSize: 11, textTransform: 'capitalize' }} />
        </Box>
        <Tooltip title="Log out">
          <IconButton onClick={() => { dispatch(logout()); navigate('/login'); }} size="small">
            <LogoutIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {desktop ? (
        <Drawer variant="permanent" sx={{ width: WIDTH, '& .MuiDrawer-paper': { width: WIDTH, border: 0, borderRight: `1px solid ${colors.line}` } }}>
          {menu}
        </Drawer>
      ) : (
        <>
          <AppBar position="fixed" elevation={0} sx={{ bgcolor: colors.panel, borderBottom: `1px solid ${colors.line}` }}>
            <Toolbar>
              <IconButton edge="start" onClick={() => setOpen(true)} sx={{ mr: 1 }}><MenuIcon /></IconButton>
              <Logo small />
            </Toolbar>
          </AppBar>
          <Drawer open={open} onClose={() => setOpen(false)} sx={{ '& .MuiDrawer-paper': { width: WIDTH } }}>
            {menu}
          </Drawer>
        </>
      )}
      <Box component="main" sx={{ flex: 1, minWidth: 0, p: { xs: 2, md: 3.5 }, pt: { xs: 10, md: 3.5 } }}>
        <Outlet />
      </Box>
    </Box>
  );
}
