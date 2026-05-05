import React, { useState, useEffect } from 'react';
import { Grid, Card, CardContent, Typography, Box, Chip } from '@mui/material';
import axios from 'axios';

export default function Dashboard() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    axios.get('http://localhost:8000/api/health')
      .then(res => setHealth(res.data))
      .catch(err => setHealth({ status: 'error' }));
  }, []);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Статусы системы</Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>Backend API</Typography>
              <Typography variant="h6">
                {health?.status === 'ok' ? <Chip label="Online" color="success" size="small" /> : <Chip label="Offline" color="error" size="small" />}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>YouTube API</Typography>
              <Typography variant="h6"><Chip label="Не авторизован" color="warning" size="small" /></Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>В очереди на генерацию</Typography>
              <Typography variant="h4">0</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
