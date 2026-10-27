import { Box, Typography } from '@mui/material';
import { colors } from '../theme';

export default function Logo({ small }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}>
      <Box component="img" src="/icon.svg" alt="" sx={{ width: small ? 28 : 34, height: small ? 28 : 34 }} />
      <Box>
        <Typography variant="h5" sx={{ lineHeight: 1, fontSize: small ? 20 : 24, color: colors.text }}>
          ROAD<span style={{ color: colors.amber }}>GUARD</span>
        </Typography>
        {!small && (
          <Typography sx={{ fontSize: 10.5, color: colors.muted, letterSpacing: 1.2, textTransform: 'uppercase' }}>
            Helmet & plate enforcement
          </Typography>
        )}
      </Box>
    </Box>
  );
}
