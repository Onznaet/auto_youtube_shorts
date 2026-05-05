import React, { useState, useEffect, useRef, useContext } from 'react';
import { Box, Typography, Card, CardContent, TextField, Button, Grid, Divider, CircularProgress, Link, Chip, IconButton, InputAdornment, Switch, FormControlLabel } from '@mui/material';
import { RefreshCw, ExternalLink, RotateCcw } from 'lucide-react';
import axios from 'axios';
import VideoTaskCard from '../components/VideoTaskCard';
import { useToast } from '../contexts/ToastContext';
import { GlobalUpdateContext } from '../App';

export default function ReadyVideos() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadingId, setUploadingId] = useState(null);
  const [fieldLoadingIds, setFieldLoadingIds] = useState(new Set());
  const { showToast } = useToast();
  const saveTimeouts = useRef({});

  const globalUpdateTs = useContext(GlobalUpdateContext);
  const [autoPublish, setAutoPublish] = useState(false);

  useEffect(() => {
    fetchReady();
    fetchSettings();
  }, [globalUpdateTs]);

  const fetchSettings = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/settings');
      if (res.data.auto_publish === 'true') {
        setAutoPublish(true);
      } else {
        setAutoPublish(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAutoPublishToggle = async (e) => {
    const checked = e.target.checked;
    setAutoPublish(checked);
    try {
      await axios.post('http://localhost:8000/api/settings', {
        settings: { auto_publish: checked ? 'true' : 'false' }
      });
      showToast(`Автопубликация ${checked ? 'включена' : 'выключена'}`, 'info');
    } catch (error) {
      showToast('Ошибка сохранения настроек', 'error');
    }
  };

  const fetchReady = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/ready');
      setTasks(res.data);
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch ready videos", error);
      setLoading(false);
    }
  };

  const handleRemove = async (taskId) => {
     try {
       await axios.delete(`http://localhost:8000/api/queue/${taskId}`);
       setTasks(tasks.filter(t => t.task_id !== taskId));
       showToast('Удалено из готовых', 'success');
     } catch (error) {
       console.error("Failed to delete task", error);
       showToast('Ошибка при удалении', 'error');
     }
  };

  const handleAutoSave = (form, taskId) => {
    if (saveTimeouts.current[taskId]) {
      clearTimeout(saveTimeouts.current[taskId]);
    }

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    
    const platforms = [];
    if (formData.get('platform_youtube') === 'on') platforms.push('youtube');
    if (formData.get('platform_telegram') === 'on') platforms.push('telegram');
    if (formData.get('platform_vk') === 'on') platforms.push('vk');
    payload.target_platforms = JSON.stringify(platforms);

    // Parse toggles
    payload.use_rewrite = formData.get('use_rewrite') === 'on';
    payload.use_cta = formData.get('use_cta') === 'on';

    saveTimeouts.current[taskId] = setTimeout(async () => {
      try {
        await axios.post(`http://localhost:8000/api/queue/${taskId}/save`, payload);
      } catch (error) {
        console.error("Auto-save error", error);
      }
    }, 800);
  };

  const handleFieldRegenerate = async (taskId, field) => {
    setFieldLoadingIds(prev => new Set(prev).add(`${taskId}-${field}`));
    try {
      const response = await axios.post(`http://localhost:8000/api/queue/${taskId}/regenerate_field`, { field });
      if (response.data.status === "ok") {
        fetchReady();
        showToast(`Поле "${field}" успешно перегенерировано!`, 'success');
      }
    } catch (error) {
      showToast('Ошибка при перегенерации поля.', 'error');
    } finally {
      setFieldLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(`${taskId}-${field}`);
        return next;
      });
    }
  };

  const handleRestoreSource = async (taskId, newsLink) => {
    try {
      await axios.post(`http://localhost:8000/api/queue/${taskId}/save`, { source_url: newsLink });
      fetchReady();
      showToast('Ссылка на источник восстановлена', 'success');
    } catch (e) {
      showToast('Ошибка восстановления', 'error');
    }
  };

  const handleOpenFile = async (taskId) => {
    try {
      await axios.post(`http://localhost:8000/api/ready/${taskId}/open`);
    } catch (error) {
      showToast('Не удалось открыть файл', 'error');
    }
  };

  const handleUploadAll = async () => {
    const validTasks = tasks.filter(t => t.file_exists && t.status === 'READY');
    if (validTasks.length === 0) return;
    
    setUploadingId('ALL');
    let hasError = false;
    for (const task of validTasks) {
      try {
        await axios.post(`http://localhost:8000/api/queue/${task.task_id}/upload`);
      } catch (error) {
        if (error.response && error.response.status === 400) {
          showToast(error.response.data.detail, 'error');
        } else {
          showToast(`Ошибка запуска загрузки "${task.video_title}"`, 'error');
        }
        hasError = true;
      }
    }
    setUploadingId(null);
    if (!hasError) {
      showToast("Задачи на загрузку отправлены в очередь!", 'success');
    }
    fetchReady();
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}><CircularProgress /></Box>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, position: 'sticky', top: '48px', zIndex: 1100, bgcolor: 'background.default', pt: 2, pb: 2, mt: -2 }}>
        <Typography variant="h5">Готовые видео</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <FormControlLabel
            control={<Switch checked={autoPublish} onChange={handleAutoPublishToggle} size="small" />}
            label="Автопубликация"
            sx={{ m: 0 }}
          />
          <Button 
            variant="contained" 
            color="success" 
            disabled={tasks.filter(t => t.file_exists && t.status === 'READY').length === 0 || tasks.some(t => t.status === 'UPLOADING')}
            onClick={handleUploadAll}
          >
            {tasks.some(t => t.status === 'UPLOADING') ? 'Идет заливка...' : 'Залить'}
          </Button>
        </Box>
      </Box>

      {tasks.length === 0 && (
        <Typography>Нет готовых видео.</Typography>
      )}

      {tasks.map((task) => (
        <VideoTaskCard
          key={task.task_id}
          task={task}
          type="ready"
          onAutoSave={handleAutoSave}
          onFieldRegenerate={handleFieldRegenerate}
          onRestoreSource={handleRestoreSource}
          onRemove={handleRemove}
          onOpenFile={handleOpenFile}
          fieldLoadingIds={fieldLoadingIds}
        />
      ))}
    </Box>
  );
}
