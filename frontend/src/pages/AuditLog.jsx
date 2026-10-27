/** AuditLog.jsx - (admin) Who did what and when: logins, approvals, challans, user changes. */
import { useEffect, useState } from 'react';
import { Chip, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import api from '../services/api';
import PageHeader from '../components/PageHeader';
import { dateTime } from '../utils/format';

const COLOR = { login_failed: 'error', violation_rejected: 'default', violation_approved: 'success', challan_issued: 'warning' };

export default function AuditLog() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get('/audit').then((r) => setRows(r.data)); }, []);
  return (
    <>
      <PageHeader title="Audit log" subtitle="The last 200 actions. Needed to investigate misuse." />
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>When</TableCell><TableCell>User</TableCell><TableCell>Action</TableCell>
              <TableCell>Target</TableCell><TableCell>Details</TableCell><TableCell>IP</TableCell></TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.audit_id}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{dateTime(r.created_at)}</TableCell>
                <TableCell>{r.user_name || '-'}</TableCell>
                <TableCell><Chip size="small" label={r.action.replace(/_/g, ' ')} color={COLOR[r.action] || 'default'} variant="outlined" /></TableCell>
                <TableCell>{r.target}</TableCell>
                <TableCell>{r.details}</TableCell>
                <TableCell>{r.ip_address}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
