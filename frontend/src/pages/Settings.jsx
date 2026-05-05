import React, { useState, useEffect, useContext } from 'react';
import { Box, Typography, TextField, Button, Card, CardContent, Grid, CircularProgress, Switch, FormControlLabel, FormControl, InputLabel, Select, MenuItem, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Chip } from '@mui/material';
import { UploadCloud, Trash2, Save } from 'lucide-react';
import axios from 'axios';
import { useToast } from '../contexts/ToastContext';
import { GlobalUpdateContext } from '../App';

const DEFAULT_SYSTEM_PROMPT = `Ты профессиональный сценарист для YouTube. Твоя задача обработать следующую новость.
Сделай выжимку самого главного и интересного для озвучки ролика.
ВАЖНО: Твоя задача — объективно и нейтрально пересказать новость, убрав любые манипуляции, кликбейт и оценочные суждения автора статьи. Излагай только факты.
ВАЖНО: Ориентировочная длительность ролика должна составлять {duration} секунд.
Постарайся написать текст такой длины, чтобы при нормальном темпе чтения (около 2 слов в секунду) диктор уложился ровно в это время.
Если запрошенная длительность большая (более 60 секунд), добавляй больше подробностей из текста, контекста и аналитики, чтобы текста хватило. Если текста новости мало, добавь нейтральную историческую справку по теме.
ВАЖНО: Текст для озвучки, заголовок и описание должны быть СТРОГО на РУССКОМ языке.
Сгенерируй кликбейтный заголовок, описание с хештегами и список тегов через запятую (теги тоже на русском). 
ВАЖНО: Выдели ровно {image_count} ключевых слов (или словосочетаний) для поиска картинок. Они также должны быть на РУССКОМ языке. Эти слова должны соответствовать хронологии текста, чтобы картинки менялись в тему по мере рассказа.`;
const DEFAULT_MODERATOR_PROMPT = `Оцени, подходит ли это изображение для новостного ролика на тему "{query}". 
Изображение НЕ должно содержать водяных знаков, странных артефактов, элементов интерфейса (кнопок, меню) или неуместного контента.
Ответь строго одним словом: ДА или НЕТ.`;

export default function Settings() {
  const [settings, setSettings] = useState({
    default_music_path: '',
    default_music_volume: 30,
    default_image_zoom: 5,
    default_watermark_path: '',
    image_moderator_enabled: 'false',
    image_moderator_prompt: DEFAULT_MODERATOR_PROMPT,
    image_moderator_rpm: 10,
  });
  const [youtubeAuth, setYoutubeAuth] = useState({ authorized: false, checking: true, authenticating: false });
  const { showToast } = useToast();
  const [uploading, setUploading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const currentProjectId = axios.defaults.headers.common['X-Project-Id'] || 1;
  const globalUpdateTs = useContext(GlobalUpdateContext);

  const checkYoutubeAuth = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/auth/youtube');
      setYoutubeAuth({ authorized: res.data.authorized, checking: false, authenticating: false });
    } catch (e) {
      setYoutubeAuth({ authorized: false, checking: false, authenticating: false });
    }
  };

  useEffect(() => {
    // При переключении проекта сбрасываем локальный стейт, чтобы не сохранить старые данные в новый проект случайно
    setSettings({
      default_music_path: '',
      default_music_volume: 30,
      default_image_zoom: 5,
      default_watermark_path: '',
      image_moderator_enabled: 'false',
      image_moderator_prompt: DEFAULT_MODERATOR_PROMPT,
      image_moderator_rpm: 10,
      system_prompt: DEFAULT_SYSTEM_PROMPT
    });
    setYoutubeAuth({ authorized: false, checking: true, authenticating: false });

    axios.get('http://localhost:8000/api/settings')
      .then(res => {
        const data = res.data;
        if (!data.system_prompt) {
          data.system_prompt = DEFAULT_SYSTEM_PROMPT;
        }
        if (!data.image_moderator_prompt) {
          data.image_moderator_prompt = DEFAULT_MODERATOR_PROMPT;
        }
        if (data.image_moderator_rpm === undefined) {
          data.image_moderator_rpm = 10;
        }
        setSettings(prev => ({ ...prev, ...data }));
      })
      .catch(err => console.error("Failed to load settings"));
      
    checkYoutubeAuth();
  }, [globalUpdateTs]);

  const handleChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
  };

  const handleSwitchChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.checked ? 'true' : 'false' });
  };

  const handleSave = async () => {
    try {
      await axios.post('http://localhost:8000/api/settings', { settings });
      showToast('Настройки сохранены', 'success');
    } catch (error) {
      showToast('Ошибка сохранения', 'error');
    }
  };

  const handleDeleteProject = async () => {
    try {
      await axios.delete(`http://localhost:8000/api/projects/${currentProjectId}`);
      showToast('Проект успешно удален', 'success');
      setDeleteDialogOpen(false);
      
      // Удаляем ID удаленного проекта и идем на главную
      localStorage.removeItem('selectedProjectId');
      setTimeout(() => {
        window.location.href = '/';
      }, 1000);
    } catch (error) {
      showToast(error.response?.data?.detail || 'Ошибка удаления проекта', 'error');
    }
  };

  const handleFileUpload = async (event, field_name) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('field_name', field_name);

    setUploading(true);
    try {
      const res = await axios.post('http://localhost:8000/api/upload_setting_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSettings({ ...settings, [field_name]: res.data.file_path });
      showToast('Файл загружен', 'success');
    } catch (error) {
      showToast('Ошибка загрузки файла', 'error');
    } finally {
      setUploading(false);
      event.target.value = null; // reset input
    }
  };

  const handleConnectYoutube = async () => {
    setYoutubeAuth(prev => ({ ...prev, authenticating: true }));
    try {
      await axios.post('http://localhost:8000/api/auth/youtube');
      showToast('Браузер открыт. Пожалуйста, выполните вход и закройте окно.', 'info');
      // Запускаем поллинг статуса
      const interval = setInterval(async () => {
        try {
          const res = await axios.get('http://localhost:8000/api/auth/youtube');
          if (res.data.authorized) {
            clearInterval(interval);
            setYoutubeAuth({ authorized: true, checking: false, authenticating: false });
            showToast('Успешная авторизация YouTube!', 'success');
          }
        } catch(e) {}
      }, 3000);
      
      // Stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(interval);
        setYoutubeAuth(prev => ({ ...prev, authenticating: false }));
      }, 300000);
    } catch (e) {
      showToast('Ошибка запуска браузера', 'error');
      setYoutubeAuth(prev => ({ ...prev, authenticating: false }));
    }
  };

  return (
    <Box sx={{ pb: 6 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, position: 'sticky', top: '48px', zIndex: 1100, bgcolor: 'background.default', pt: 2, pb: 2, mt: -2 }}>
        <Typography variant="h5">Настройки проекта</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button 
            variant="outlined" 
            color="error" 
            startIcon={<Trash2 size={18} />} 
            onClick={() => setDeleteDialogOpen(true)}
          >
            Удалить проект
          </Button>
          <Button 
            variant="contained" 
            color="primary" 
            startIcon={<Save size={18} />} 
            onClick={handleSave}
          >
            Сохранить настройки
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card sx={{ mb: 3, position: 'relative', border: '4px solid rgba(255, 255, 255, 0.12)', bgcolor: '#1e1e1e', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3, color: '#e0e0e0' }}>Шаблон новой задачи (по умолчанию)</Typography>
              
              <Box sx={{ mb: 2 }}>
                <TextField 
                  fullWidth 
                  disabled
                  label="Заголовок видео" 
                  defaultValue="[Генерируется нейросетью на основе источника]" 
                  variant="outlined" 
                  size="small"
                />
              </Box>
              <Box sx={{ mb: 3, mt: -1, ml: 1 }}>
                <FormControlLabel 
                  control={<Switch name="rewrite_title" checked={settings.rewrite_title !== 'false'} onChange={handleSwitchChange} size="small" />} 
                  label={<Typography variant="body2" color="text.secondary">Использовать рерайт заголовка</Typography>} 
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <TextField
                  multiline
                  rows={10}
                  fullWidth
                  name="system_prompt"
                  label="Текст для диктора (Системный Prompt)"
                  value={settings.system_prompt || ''}
                  onChange={handleChange}
                  variant="outlined"
                  size="small"
                  sx={{ '& .MuiInputBase-root': { fontFamily: 'monospace', fontSize: '0.85rem' } }}
                />
                <Box sx={{ mt: 0.5, ml: 1, display: 'flex', justifyContent: 'flex-start' }}>
                  <Typography variant="caption" color="text.secondary">
                    Переменные: {'{duration}'}, {'{image_count}'}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ mb: 3, mt: -1, ml: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <FormControlLabel 
                  control={<Switch name="add_cta" checked={settings.add_cta === 'true'} onChange={handleSwitchChange} size="small" />} 
                  label={<Typography variant="body2" color="text.secondary">Призыв к действию</Typography>} 
                />
              </Box>
              {settings.add_cta === 'true' && (
                <Box sx={{ mb: 3, ml: 1, mt: -2 }}>
                  <TextField
                    fullWidth
                    name="cta_text"
                    label="Текст призыва (будет добавлен в конец голоса)"
                    value={settings.cta_text || ''}
                    onChange={handleChange}
                    variant="outlined"
                    size="small"
                    placeholder="Например: Подписывайтесь на канал и ставьте лайки!"
                  />
                </Box>
              )}

              <Box sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, mb: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 2, color: "text.secondary" }}>Исключения для поиска картинок Яндекса</Typography>
                <TextField
                  fullWidth
                  name="yandex_negative_keywords"
                  label="Минус-слова и сайты (через запятую)"
                  value={settings.yandex_negative_keywords || ''}
                  onChange={handleChange}
                  variant="outlined"
                  size="small"
                  placeholder="Например: новость, текст, site:ria.ru, site:lenta.ru"
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Эти слова будут автоматически добавлены со знаком минус (например: -новость -site:ria.ru) к каждому поисковому запросу.
                </Typography>
              </Box>

              <Box sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, mb: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 2, color: "text.secondary" }}>AI-Модератор картинок (Gemini Vision)</Typography>
                <Box sx={{ mb: 2, ml: 1 }}>
                  <FormControlLabel 
                    control={<Switch name="image_moderator_enabled" checked={settings.image_moderator_enabled === 'true'} onChange={handleSwitchChange} size="small" />} 
                    label={<Typography variant="body2" color="text.secondary">Включить отбраковку плохих картинок</Typography>} 
                  />
                </Box>
                {settings.image_moderator_enabled === 'true' && (
                  <Box sx={{ mb: 2 }}>
                    <TextField
                      multiline
                      rows={4}
                      fullWidth
                      name="image_moderator_prompt"
                      label="Промпт для Vision-модели"
                      value={settings.image_moderator_prompt || ''}
                      onChange={handleChange}
                      variant="outlined"
                      size="small"
                      sx={{ mb: 2, '& .MuiInputBase-root': { fontFamily: 'monospace', fontSize: '0.85rem' } }}
                    />
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                      <TextField
                        type="number"
                        name="image_moderator_rpm"
                        label="Лимит запросов в минуту (RPM)"
                        value={settings.image_moderator_rpm}
                        onChange={handleChange}
                        variant="outlined"
                        size="small"
                        sx={{ width: 250 }}
                      />
                      <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                        Если у вас бесплатный ключ, ставьте 10-15. Скрипт будет ждать между запросами.
                      </Typography>
                    </Box>
                  </Box>
                )}
              </Box>

              <Box sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 2, color: "text.secondary" }}>Настройки видео (по умолчанию)</Typography>
                
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={12} sm={6}>
                    <FormControlLabel
                      control={<Switch checked={settings.alternate_voices === 'true'} onChange={handleSwitchChange} name="alternate_voices" color="primary" size="small" />}
                      label="Чередовать мужской/женский голос"
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControlLabel
                      control={<Switch checked={settings.default_delete_temp_files === 'true'} onChange={handleSwitchChange} name="default_delete_temp_files" color="primary" size="small" />}
                      label="Удалять временные файлы"
                    />
                  </Grid>
                </Grid>

                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={12} sm={8}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <TextField 
                        label="Фоновая музыка (путь)" 
                        name="default_music_path"
                        fullWidth 
                        value={settings.default_music_path || ''} 
                        onChange={handleChange} 
                        size="small"
                      />
                      <Button component="label" variant="outlined" sx={{ minWidth: 'auto', p: 1 }}>
                        <UploadCloud size={20} />
                        <input type="file" hidden accept="audio/mpeg" onChange={(e) => handleFileUpload(e, 'default_music_path')} />
                      </Button>
                    </Box>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField 
                      label="Громкость (%)" 
                      name="default_music_volume"
                      type="number" 
                      fullWidth 
                      value={settings.default_music_volume || 30} 
                      onChange={handleChange} 
                      size="small"
                      slotProps={{ htmlInput: { min: 0, max: 100 } }}
                    />
                  </Grid>
                </Grid>

                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={12} sm={8}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <TextField 
                        label="Водяной знак (PNG)" 
                        name="default_watermark_path"
                        fullWidth 
                        value={settings.default_watermark_path || ''} 
                        onChange={handleChange} 
                        size="small"
                      />
                      <Button component="label" variant="outlined" sx={{ minWidth: 'auto', p: 1 }}>
                        <UploadCloud size={20} />
                        <input type="file" hidden accept="image/png" onChange={(e) => handleFileUpload(e, 'default_watermark_path')} />
                      </Button>
                    </Box>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField 
                      label="Зум (%)" 
                      name="default_image_zoom"
                      type="number" 
                      fullWidth 
                      value={settings.default_image_zoom || 5} 
                      onChange={handleChange} 
                      size="small"
                      slotProps={{ htmlInput: { min: 0, max: 50 } }}
                    />
                  </Grid>
                </Grid>

                <Typography variant="caption" sx={{ color: "text.secondary", display: 'block', mb: 1 }}>Длительность и частота картинок</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <TextField label="Длит. Vertical" name="default_duration_vertical" type="number" fullWidth value={settings.default_duration_vertical || 30} onChange={handleChange} size="small" />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField label="Длит. Video" name="default_duration_video" type="number" fullWidth value={settings.default_duration_video || 60} onChange={handleChange} size="small" />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField label="Кадры Vertical" name="image_change_speed_vertical" type="number" fullWidth value={settings.image_change_speed_vertical || 4} onChange={handleChange} size="small" slotProps={{ htmlInput: { step: 0.5 } }} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <TextField label="Кадры Video" name="image_change_speed_video" type="number" fullWidth value={settings.image_change_speed_video || 5} onChange={handleChange} size="small" slotProps={{ htmlInput: { step: 0.5 } }} />
                  </Grid>
                </Grid>
              </Box>

              <Box sx={{ p: 2, mt: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>Площадки для публикации по умолчанию</Typography>
                <Box sx={{ display: 'flex', gap: 3 }}>
                  <FormControlLabel control={<Switch name="default_publish_youtube" checked={settings.default_publish_youtube === 'true'} onChange={handleSwitchChange} size="small" />} label="YouTube" />
                  <FormControlLabel control={<Switch name="default_publish_telegram" checked={settings.default_publish_telegram === 'true'} onChange={handleSwitchChange} size="small" />} label="Telegram" />
                  <FormControlLabel control={<Switch name="default_publish_vk" checked={settings.default_publish_vk === 'true'} onChange={handleSwitchChange} size="small" />} label="VK" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ mb: 3, bgcolor: '#1e1e1e', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ color: '#e0e0e0', display: 'flex', alignItems: 'center', gap: 1 }}>
                  Подключение YouTube
                  {youtubeAuth.checking ? (
                    <CircularProgress size={16} />
                  ) : youtubeAuth.authorized ? (
                    <Chip label="Подключено" color="success" size="small" />
                  ) : (
                    <Chip label="Не подключено" color="error" size="small" />
                  )}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#aaa', mb: 3 }}>
                Для автоматической публикации видео вам нужно один раз авторизоваться в Google аккаунте.
              </Typography>
              <Button 
                variant={youtubeAuth.authorized ? "outlined" : "contained"} 
                color={youtubeAuth.authorized ? "primary" : "error"} 
                onClick={handleConnectYoutube}
                disabled={youtubeAuth.authenticating}
                fullWidth
              >
                {youtubeAuth.authenticating ? "Ожидание..." : (youtubeAuth.authorized ? "Переподключить YouTube" : "Подключить YouTube")}
              </Button>
            </CardContent>
          </Card>

          <Card sx={{ mb: 3, bgcolor: '#1e1e1e', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
            <CardContent>
              <Typography variant="h6" sx={{ color: '#e0e0e0', mb: 2 }}>
                Подключение Telegram
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField 
                  label="Bot Token (токен бота)" 
                  name="telegram_bot_token"
                  fullWidth 
                  value={settings.telegram_bot_token || ''} 
                  onChange={handleChange} 
                  size="small"
                  variant="outlined"
                  type="text"
                  autoComplete="off"
                />
                <TextField 
                  label="ID или @username канала" 
                  name="telegram_channel_id"
                  fullWidth 
                  value={settings.telegram_channel_id || ''} 
                  onChange={handleChange} 
                  size="small"
                  variant="outlined"
                />
              </Box>
            </CardContent>
          </Card>

          <Card sx={{ bgcolor: '#1e1e1e', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, color: '#e0e0e0' }}>Настройки автопарсинга RSS</Typography>
              <Typography variant="body2" sx={{ mb: 2, color: '#aaa' }}>
                Параметры для фонового сбора новостей (включение/отключение находится на вкладке "Новости").
              </Typography>
              
              <Box sx={{ pl: 2, borderLeft: '2px solid #333' }}>
                <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                  <InputLabel>Режим автообновления</InputLabel>
                  <Select
                    name="rss_auto_fetch_mode"
                    value={settings.rss_auto_fetch_mode || 'interval'}
                    label="Режим автообновления"
                    onChange={handleChange}
                  >
                    <MenuItem value="interval">С интервалом (в минутах)</MenuItem>
                    <MenuItem value="time">Точное время суток (ЧЧ:ММ)</MenuItem>
                  </Select>
                </FormControl>
                
                {settings.rss_auto_fetch_mode === 'time' ? (
                  <TextField
                    fullWidth
                    label="Время обновления"
                    name="rss_auto_fetch_time"
                    value={settings.rss_auto_fetch_time || '09:00'}
                    onChange={handleChange}
                    variant="outlined"
                    size="small"
                    type="time"
                    slotProps={{ inputLabel: { shrink: true } }}
                  />
                ) : (
                  <TextField
                    fullWidth
                    label="Интервал (в минутах)"
                    name="rss_auto_fetch_interval"
                    value={settings.rss_auto_fetch_interval || '60'}
                    onChange={handleChange}
                    variant="outlined"
                    size="small"
                    type="number"
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Окно подтверждения удаления */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        PaperProps={{ sx: { bgcolor: '#1e1e1e', color: 'white' } }}
      >
        <DialogTitle sx={{ color: '#f44336' }}>Удаление проекта</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: '#e0e0e0' }}>
            Вы уверены, что хотите безвозвратно удалить этот проект?
            <br/><br/>
            Будут удалены все настройки, списки новостей, очередь задач и <strong>все сгенерированные видеофайлы</strong> этого проекта с жесткого диска.
            Это действие нельзя отменить!
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 0 }}>
          <Button onClick={() => setDeleteDialogOpen(false)} sx={{ color: 'gray' }}>Отмена</Button>
          <Button onClick={handleDeleteProject} variant="contained" color="error" autoFocus>
            Да, удалить навсегда
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
