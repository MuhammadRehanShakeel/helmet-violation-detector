import { Box, Typography } from '@mui/material';

export default function PageHeader({ title, subtitle, action }) {
  return (
    <Box sx={{ display: 'flex', alignItems: { sm: 'flex-end' }, justifyContent: 'space-between', gap: 2, mb: 3,
      flexDirection: { xs: 'column', sm: 'row' } }}>
      <Box>
        <Typography variant="h4" sx={{ fontSize: { xs: 28, md: 34 } }}>{title}</Typography>
        {subtitle && <Typography color="text.secondary" sx={{ mt: 0.3 }}>{subtitle}</Typography>}
      </Box>
      {action}
    </Box>
  );
}
