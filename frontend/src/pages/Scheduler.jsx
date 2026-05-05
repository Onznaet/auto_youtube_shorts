import React, { useState, useEffect } from 'react';
import { Box, Typography, Card, CardContent, Chip, CircularProgress, Paper, Divider } from '@mui/material';
import { Activity, Clock, CheckCircle, AlertTriangle } from 'lucide-react';
import axios from 'axios';

export default function Scheduler() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/scheduler/status');
      setStatus(res.data);
      setLoading(false);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}><CircularProgress /></Box>;
  }

  const isRunning = status?.is_running;

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Activity size={24} />
          Мониторинг Планировщика
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Здесь отображается статус глобального демона, который управляет автоматизацией.
        </Typography>
      </Box>

      <Card sx={{ mb: 4, bgcolor: isRunning ? 'success.light' : 'error.light', color: isRunning ? 'success.contrastText' : 'error.contrastText' }}>
        <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="h6">
              Статус демона: {isRunning ? 'Активен (Работает в фоне)' : 'Остановлен'}
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.8, mt: 1 }}>
              {isRunning 
                ? 'Планировщик запущен и автоматически проверяет задачи всех проектов по расписанию.' 
                : 'Скрипт scheduler.py сейчас не запущен. Автоматические задачи не выполняются.'}
            </Typography>
          </Box>
          {isRunning ? <CheckCircle size={48} opacity={0.8} /> : <AlertTriangle size={48} opacity={0.8} />}
        </CardContent>
      </Card>

      <Typography variant="h6" sx={{ mb: 2 }}>Как запустить?</Typography>
      <Paper sx={{ p: 3, bgcolor: 'background.default' }}>
        <Typography variant="body1" sx={{ mb: 2 }}>
          Демон планировщика — это отдельный скрипт, который нужно запустить в фоновом режиме.
        </Typography>
        <Box sx={{ bgcolor: 'black', color: '#00ff00', p: 2, borderRadius: 1, fontFamily: 'monospace', mb: 2 }}>
          cd backend<br/>
          venv\Scripts\python scheduler.py
        </Box>
        <Typography variant="body2" color="text.secondary">
          В будущем мы настроим его автоматический запуск вместе с Windows при старте системы (Фаза 6).
        </Typography>
      </Paper>
    </Box>
  );
}
