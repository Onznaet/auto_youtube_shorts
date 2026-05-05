import React, { useState, useEffect, useRef, useContext } from 'react';
import { Box, Typography, Card, CardContent, TextField, Select, MenuItem, FormControl, InputLabel, Button, Grid, Divider, CircularProgress, Chip, Snackbar, Alert, Switch, FormControlLabel, Link, IconButton, InputAdornment } from '@mui/material';
import { RefreshCw, ExternalLink, RotateCcw } from 'lucide-react';
import axios from 'axios';
import VideoTaskCard from '../components/VideoTaskCard';

import { useToast } from '../contexts/ToastContext';
import { GlobalUpdateContext } from '../App';

export default function Queue() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingIds, setLoadingIds] = useState(new Set());
  const [fieldLoadingIds, setFieldLoadingIds] = useState(new Set());
  const { showToast } = useToast();
  const [localDurations, setLocalDurations] = useState({});

  const fetchQueue = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/queue');
      setTasks(res.data);
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch queue", error);
      setLoading(false);
    }
  };

  const globalUpdateTs = useContext(GlobalUpdateContext);
  const [autoGenerate, setAutoGenerate] = useState(false);

  useEffect(() => {
    fetchQueue();
    fetchSettings();
  }, [globalUpdateTs]);

  const fetchSettings = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/settings');
      if (res.data.auto_generate === 'true') {
        setAutoGenerate(true);
      } else {
        setAutoGenerate(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAutoGenerateToggle = async (e) => {
    const checked = e.target.checked;
    setAutoGenerate(checked);
    try {
      await axios.post('http://localhost:8000/api/settings', {
        settings: { auto_generate: checked ? 'true' : 'false' }
      });
      showToast(`Автогенерация ${checked ? 'включена' : 'выключена'}`, 'info');
    } catch (error) {
      showToast('Ошибка сохранения настроек', 'error');
    }
  };

  const handleRemove = async (taskId) => {
     try {
       await axios.delete(`http://localhost:8000/api/queue/${taskId}`);
       setTasks(tasks.filter(t => t.task_id !== taskId));
       showToast('Удалено из очереди', 'success');
     } catch (error) {
       console.error("Failed to delete task", error);
       showToast('Ошибка при удалении', 'error');
     }
  };

  const handleRegenerate = async (taskId, currentDuration) => {
    setLoadingIds(prev => new Set(prev).add(taskId));
    const newDuration = localDurations[taskId] !== undefined ? localDurations[taskId] : currentDuration;
    try {
      const response = await axios.post(`http://localhost:8000/api/queue/${taskId}/regenerate?duration=${newDuration}`);
      if (response.data.is_mocked) {
        showToast('Все лимиты исчерпаны. Установлена заглушка.', 'warning');
      } else {
        showToast('Текст успешно перегенерирован!', 'success');
      }
      fetchQueue();
    } catch (error) {
      console.error("Regenerate error", error);
      const msg = error.response?.data?.detail || "Ошибка перегенерации";
      showToast(msg, 'error');
      fetchQueue(); // Refresh in case it saved a mock text
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    }
  };

  const handleFieldRegenerate = async (taskId, field) => {
    const loadingKey = `${taskId}-${field}`;
    setFieldLoadingIds(prev => new Set(prev).add(loadingKey));
    try {
      const response = await axios.post(`http://localhost:8000/api/queue/${taskId}/regenerate_field`, { field });
      if (response.data.is_mocked) {
        showToast('Все лимиты исчерпаны. Установлена заглушка.', 'warning');
      } else {
        showToast('Поле успешно перегенерировано!', 'success');
      }
      fetchQueue();
    } catch (error) {
      console.error("Field regenerate error", error);
      const msg = error.response?.data?.detail || "Ошибка перегенерации поля";
      showToast(msg, 'error');
    } finally {
      setFieldLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(loadingKey);
        return next;
      });
    }
  };

  const saveTimeouts = useRef({});

  const handleAutoSave = (formElement, taskId) => {
    if (saveTimeouts.current[taskId]) {
      clearTimeout(saveTimeouts.current[taskId]);
    }
    
    // We clone FormData immediately because formElement state is needed right now
    const formData = new FormData(formElement);
    const payload = Object.fromEntries(formData);
    
    // Checkbox is only present in formData if checked
    payload.delete_temp_files = formData.get('delete_temp_files') === 'on';
    
    const platforms = [];
    if (formData.get('platform_youtube') === 'on') platforms.push('youtube');
    if (formData.get('platform_telegram') === 'on') platforms.push('telegram');
    if (formData.get('platform_vk') === 'on') platforms.push('vk');
    payload.target_platforms = JSON.stringify(platforms);
    
    // Parse toggles
    payload.use_rewrite = formData.get('use_rewrite') === 'on';
    payload.use_cta = formData.get('use_cta') === 'on';
    
    // Parse ints
    if (payload.duration !== undefined) payload.duration = parseInt(payload.duration, 10) || 30;
    if (payload.music_volume !== undefined) payload.music_volume = parseInt(payload.music_volume, 10) || 30;
    if (payload.image_zoom !== undefined) payload.image_zoom = parseInt(payload.image_zoom, 10) || 5;

    saveTimeouts.current[taskId] = setTimeout(async () => {
      try {
        await axios.post(`http://localhost:8000/api/queue/${taskId}/save`, payload);
        // Не показываем уведомление для автосохранения, чтобы не спамить
        // Не делаем fetchQueue(), чтобы не сбивать фокус ввода текста
      } catch (error) {
        console.error("Auto-save error", error);
      }
    }, 800); // Сохраняем через 800мс после последнего изменения
  };

  const handleRestoreSource = async (taskId, newsLink) => {
    try {
      await axios.post(`http://localhost:8000/api/queue/${taskId}/save`, { source_url: newsLink });
      fetchQueue();
      showToast('Ссылка на источник восстановлена', 'success');
    } catch (e) {
      showToast('Ошибка восстановления', 'error');
    }
  };

  const handleGenerateAllMedia = async () => {
    const tasksToProcess = tasks.filter(t => t.status !== 'GENERATING' && t.status !== 'ASSEMBLING');
    if (tasksToProcess.length === 0) return;
    
    // Process tasks sequentially (but they return instantly now)
    for (const task of tasksToProcess) {
      try {
        const response = await axios.post(`http://localhost:8000/api/queue/${task.task_id}/generate_media`);
        if (response.data.status === "ok") {
          showToast(`Видео для "${task.news_title}" поставлено в очередь сборки!`, 'success');
        }
      } catch (error) {
        showToast(`Ошибка отправки на сборку "${task.news_title}"`, 'error');
      }
    }
    fetchQueue();
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}><CircularProgress /></Box>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', mb: 3, position: 'sticky', top: '48px', zIndex: 1100, bgcolor: 'background.default', pt: 2, pb: 2, mt: -2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <Typography variant="h5">Очередь на генерацию</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <FormControlLabel
              control={<Switch checked={autoGenerate} onChange={handleAutoGenerateToggle} size="small" />}
              label="Автогенерация"
              sx={{ m: 0 }}
            />
            <Button 
              variant="contained" 
              color="success" 
              disabled={tasks.filter(t => t.status !== 'GENERATING' && t.status !== 'ASSEMBLING').length === 0}
              onClick={handleGenerateAllMedia}
            >
              Запустить сборку
            </Button>
          </Box>
        </Box>
      </Box>

      {tasks.length === 0 && (
        <Typography>Очередь пуста. Выберите новости во вкладке "Лента новостей" и нажмите "В очередь".</Typography>
      )}

      {tasks.map((task) => (
        <VideoTaskCard
          key={task.task_id}
          task={task}
          type="queue"
          onAutoSave={handleAutoSave}
          onFieldRegenerate={handleFieldRegenerate}
          onRestoreSource={handleRestoreSource}
          onRegenerateAll={handleRegenerate}
          onRemove={handleRemove}
          fieldLoadingIds={fieldLoadingIds}
        />
      ))}
    </Box>
  );
}
