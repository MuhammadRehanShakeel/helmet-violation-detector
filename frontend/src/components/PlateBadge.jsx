/** A number plate drawn like a real Pakistani plate (white, black border). */
import { Box } from '@mui/material';

export default function PlateBadge({ plate, size = 15 }) {
  if (!plate) return <Box component="span" sx={{ color: 'text.secondary', fontSize: size - 2 }}>plate not read</Box>;
  return (
    <Box component="span" sx={{
      fontFamily: '"Barlow Condensed", monospace', fontWeight: 700, fontSize: size, letterSpacing: 1,
      bgcolor: '#f4f4f0', color: '#111', px: 1, py: 0.1, borderRadius: 0.8, border: '2px solid #111',
      whiteSpace: 'nowrap',
    }}>
      {plate}
    </Box>
  );
}
