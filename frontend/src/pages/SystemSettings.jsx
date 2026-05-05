import React, { useState, useEffect } from 'react';
import { Box, Typography, TextField, Button, Card, CardContent, Grid, Chip } from '@mui/material';
import axios from 'axios';
import { useToast } from '../contexts/ToastContext';

export default function SystemSettings() {
  const [settings, setSettings] = useState({
    gemini_api_key: '',
    gemini_models: 'gemini-2.5-flash\ngemini-2.5-pro\ngemini-2.0-flash',
    groq_api_key: '',
    groq_models: 'llama-3.3-70b-versatile\nllama-3.1-8b-instant\nopenai/gpt-oss-120b\nopenai/gpt-oss-20b\nopenai/gpt-oss-safeguard-20b\nqwen/qwen3-32b',
    openrouter_api_key: '',
    openrouter_models: '',
    api_requests_per_minute: 3
  });
  const { showToast } = useToast();

  useEffect(() => {
    axios.get('http://localhost:8000/api/system_settings')
      .then(res => {
        setSettings(prev => ({ ...prev, ...res.data }));
      })
      .catch(err => console.error("Failed to load global settings"));
  }, []);

  const handleChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    try {
      await axios.post('http://localhost:8000/api/system_settings', { settings });
      showToast('Системные настройки успешно сохранены!', 'success');
    } catch (err) {
      showToast('Ошибка при сохранении.', 'error');
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, position: 'sticky', top: '48px', zIndex: 1100, bgcolor: 'background.default', pt: 2, pb: 2, mt: -2 }}>
        <Typography variant="h5">Глобальные системные настройки</Typography>
        <Button variant="contained" color="primary" onClick={handleSave}>
          Сохранить системные настройки
        </Button>
      </Box>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Единый шлюз нейросетей (AI Router)</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                При ошибке или исчерпании лимитов, роутер будет идти по спискам сверху вниз: сначала все модели Gemini, затем Groq, затем OpenRouter. 
                Неподходящие по типу задачи модели будут автоматически пропущен nominal.
              </Typography>
              
              <Grid container spacing={2}>
                {/* Колоннка Gemini */}
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'rgba(25, 118, 210, 0.05)', borderRadius: 1, border: '1px solid rgba(25, 118, 210, 0.2)' }}>
                    <Typography variant="subtitle2" sx={{ color: '#90caf9', mb: 1 }}>Провайдер: Google Gemini</Typography>
                    <TextField
                      fullWidth
                      label="API Key"
                      name="gemini_api_key"
                      value={settings.gemini_api_key || ''}
                      onChange={handleChange}
                      variant="outlined"
                      size="small"
                      type="password"
                      autoComplete="new-password"
                      sx={{ mb: 2 }}
                    />
                    <TextField
                      fullWidth
                      label="Модели (одна на строку)"
                      name="gemini_models"
                      value={settings.gemini_models || 'gemini-2.5-flash\ngemini-2.5-pro\ngemini-2.0-flash'}
                      onChange={handleChange}
                      variant="outlined"
                      multiline
                      rows={5}
                      InputProps={{ style: { fontSize: '0.8rem', fontFamily: 'monospace' } }}
                    />
                  </Box>
                </Grid>

                {/* Колоннка Groq */}
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'rgba(245, 124, 0, 0.05)', borderRadius: 1, border: '1px solid rgba(245, 124, 0, 0.2)' }}>
                    <Typography variant="subtitle2" sx={{ color: '#ffb74d', mb: 1 }}>Провайдер: Groq</Typography>
                    <TextField
                      fullWidth
                      label="API Key"
                      name="groq_api_key"
                      value={settings.groq_api_key || ''}
                      onChange={handleChange}
                      variant="outlined"
                      size="small"
                      type="password"
                      autoComplete="new-password"
                      sx={{ mb: 2 }}
                    />
                    <TextField
                      fullWidth
                      label="Модели (одна на строку)"
                      name="groq_models"
                      value={settings.groq_models || 'llama-3.3-70b-versatile\nllama-3.1-8b-instant'}
                      onChange={handleChange}
                      variant="outlined"
                      multiline
                      rows={5}
                      InputProps={{ style: { fontSize: '0.8rem', fontFamily: 'monospace' } }}
                    />
                  </Box>
                </Grid>

                {/* Колоннка OpenRouter */}
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'rgba(156, 39, 176, 0.05)', borderRadius: 1, border: '1px solid rgba(156, 39, 176, 0.2)' }}>
                    <Typography variant="subtitle2" sx={{ color: '#ce93d8', mb: 1 }}>Провайдер: OpenRouter</Typography>
                    <TextField
                      fullWidth
                      label="API Key"
                      name="openrouter_api_key"
                      value={settings.openrouter_api_key || ''}
                      onChange={handleChange}
                      variant="outlined"
                      size="small"
                      type="password"
                      autoComplete="new-password"
                      sx={{ mb: 2 }}
                    />
                    <TextField
                      fullWidth
                      label="Модели (одна на строку)"
                      name="openrouter_models"
                      value={settings.openrouter_models || ''}
                      onChange={handleChange}
                      variant="outlined"
                      multiline
                      rows={5}
                      placeholder="openai/gpt-4o-mini&#10;anthropic/claude-3.5-sonnet"
                      InputProps={{ style: { fontSize: '0.8rem', fontFamily: 'monospace' } }}
                    />
                  </Box>
                </Grid>
              </Grid>
              <TextField
                fullWidth
                label="Лимит запросов к API в минуту"
                name="api_requests_per_minute"
                type="number"
                value={settings.api_requests_per_minute || 3}
                onChange={handleChange}
                variant="outlined"
                margin="normal"
                slotProps={{ htmlInput: { min: 1, max: 60 } }}
                helperText="Общий лимит генераций текстов в минуту (для обхода ограничений Groq). Оптимально: 3 (каждые 20 секунд)."
              />
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Движки озвучки (Voice Engines)</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                При ошибке генерации голоса роутер будет пробовать следующий движок из списка.
              </Typography>
              <TextField
                fullWidth
                label="Движки (один на строку)"
                name="voice_engines"
                value={settings.voice_engines !== undefined ? settings.voice_engines : 'edge-tts\nyandex-speechkit'}
                onChange={handleChange}
                variant="outlined"
                multiline
                rows={3}
                InputProps={{ style: { fontSize: '0.8rem', fontFamily: 'monospace' } }}
              />
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Внешние сервисы (Глобальные API)
              </Typography>
              <Typography variant="subtitle2" sx={{ mb: 1, mt: 2, color: 'text.secondary' }}>Интеграция Yandex Cloud (Картинки и Озвучка)</Typography>
              <Box sx={{ pl: 2, mb: 3, borderLeft: '2px solid #ccc' }}>
                <TextField 
                  label="Yandex Cloud API Key" 
                  name="yandex_api_key"
                  type="password"
                  fullWidth 
                  value={settings.yandex_api_key || ''} 
                  onChange={handleChange} 
                  size="small"
                  sx={{ mb: 2 }}
                />
                <TextField 
                  label="Yandex Folder ID" 
                  name="yandex_folder_id"
                  fullWidth 
                  value={settings.yandex_folder_id || ''} 
                  onChange={handleChange} 
                  size="small"
                />
                <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                  <TextField 
                    label="Голос Яндекс (Мужской)" 
                    name="yandex_voice_male"
                    fullWidth 
                    value={settings.yandex_voice_male || 'filipp'} 
                    onChange={handleChange} 
                    size="small"
                  />
                  <TextField 
                    label="Голос Яндекс (Женский)" 
                    name="yandex_voice_female"
                    fullWidth 
                    value={settings.yandex_voice_female || 'alena'} 
                    onChange={handleChange} 
                    size="small"
                  />
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Популярные мужские: filipp, zahar, ermil, madirus. Женские: alena, jane, omazh.
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
