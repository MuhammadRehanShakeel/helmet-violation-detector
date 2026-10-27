/** Shows an evidence photo that needs the login token (see loadPrivateImage in api.js). */
import { useEffect, useState } from 'react';
import { Box, Skeleton } from '@mui/material';
import ImageNotSupportedIcon from '@mui/icons-material/ImageNotSupportedOutlined';
import { loadPrivateImage } from '../services/api';

export default function PrivateImage({ path, alt, sx, height = 180, onClick }) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setUrl(null);
    setFailed(false);
    loadPrivateImage(path).then((u) => alive && setUrl(u)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, [path]);

  if (failed) {
    return (
      <Box sx={{ height, display: 'grid', placeItems: 'center', bgcolor: 'background.default', color: 'text.secondary', ...sx }}>
        <ImageNotSupportedIcon />
      </Box>
    );
  }
  if (!url) return <Skeleton variant="rectangular" height={height} sx={sx} />;
  return <Box component="img" src={url} alt={alt} onClick={onClick}
    sx={{ width: '100%', height, objectFit: 'cover', display: 'block', ...sx }} />;
}
