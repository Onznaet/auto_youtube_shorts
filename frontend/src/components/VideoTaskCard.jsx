import React, { useState } from 'react';
import { 
  Box, Typography, Button, TextField, Card, CardContent, InputAdornment, 
  IconButton, CircularProgress, Chip, Grid, FormControl, InputLabel, Select, MenuItem, Divider, FormControlLabel, Switch, Link,
  Checkbox, FormGroup, FormLabel
} from '@mui/material';
import { ExternalLink, RefreshCw, RotateCcw } from 'lucide-react';

export default function VideoTaskCard({ 
  task, 
  type = 'queue', // 'queue' or 'ready'
  onAutoSave, 
  onFieldRegenerate, 
  onRestoreSource, 
  onRegenerateAll, 
  onRemove, 
  fieldLoadingIds,
  onOpenFile
}) {
  const isMocked = task.video_title && (task.video_title.includes('(Лимит API)') || task.video_title.includes('Сбой API'));
  
  // Local state for generation toggles
  const [useRewrite, setUseRewrite] = useState(task.use_rewrite !== false);


  // Local state for duration to show regenerate button when changed
  const [localDuration, setLocalDuration] = useState(task.duration || 30);
  const isDurationChanged = localDuration !== (task.duration || 30);
  const showRegenerate = type === 'queue' && (isMocked || isDurationChanged);
  
  const isUploading = task.status === 'UPLOADING';
  const isGenerating = task.status === 'GENERATING';
  const isAssembling = task.status === 'ASSEMBLING';
  const isBusy = isGenerating || isAssembling || isUploading;

  const platformsStr = task.target_platforms || '["youtube"]';
  let selectedPlatforms = [];
  try {
    selectedPlatforms = JSON.parse(platformsStr);
  } catch(e) {
    selectedPlatforms = ["youtube"];
  }

  const hasFile = type === 'ready' && task.video_path && task.video_path !== "error";

  let borderColor = 'rgba(255, 255, 255, 0.12)';
  if (isMocked) borderColor = '#f44336';
  else if (isGenerating) borderColor = '#ff9800';
  else if (isAssembling) borderColor = '#2196f3';
  else if (isUploading) borderColor = '#9c27b0';

  return (
    <Card sx={{ mb: 3, position: 'relative', border: `4px solid ${borderColor}` }}>
      <Box component="form" data-task-id={task.task_id} onChange={(e) => onAutoSave(e.currentTarget, task.task_id)}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <TextField 
              key={`video_title-${task.task_id}-${useRewrite ? task.video_title : (task.custom_title || task.news_title)}-${useRewrite}`}
              fullWidth 
              name={useRewrite ? "video_title" : "custom_title"}
              label={useRewrite ? `[${task.video_format === 'VERTICAL' ? 'Вертикальное' : 'Горизонтальное'}] Заголовок (Рерайт)` : `[${task.video_format === 'VERTICAL' ? 'Вертикальное' : 'Горизонтальное'}] Заголовок (Оригинал)`}
              defaultValue={useRewrite ? task.video_title : (task.custom_title || task.news_title)} 
              variant="outlined" 
              size="small"
              sx={{ flexGrow: 1 }}
              disabled={isBusy}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <IconButton 
                        onClick={() => {
                          if (useRewrite) {
                            onFieldRegenerate(task.task_id, 'video_title');
                          } else {
                            // Restore custom_title to news_title via standard auto-save
                            const form = document.querySelector(`form[data-task-id="${task.task_id}"]`);
                            if (form) {
                              const input = form.querySelector('input[name="custom_title"]');
                              if (input) input.value = task.news_title;
                              onAutoSave(form, task.task_id);
                            }
                          }
                        }}
                        disabled={fieldLoadingIds.has(`${task.task_id}-video_title`) || isBusy}
                        size="small"
                        title={useRewrite ? "Сгенерировать другой заголовок" : "Восстановить оригинальный заголовок из источника"}
                      >
                        {fieldLoadingIds.has(`${task.task_id}-video_title`) ? <CircularProgress size={16} /> : (useRewrite ? <RefreshCw size={16} /> : <RotateCcw size={16} />)}
                      </IconButton>
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton 
                        component="a" 
                        href={task.news_link} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        size="small"
                        title="Открыть оригинал новости"
                      >
                        <ExternalLink size={16} />
                      </IconButton>
                    </InputAdornment>
                  ),
                }
              }}
            />
          </Box>
          <Box sx={{ mb: 2, mt: -1, ml: 1 }}>
            <FormControlLabel 
              control={<Switch name="use_rewrite" disabled={isBusy} defaultChecked={task.use_rewrite !== false} onChange={(e) => setUseRewrite(e.target.checked)} size="small" />} 
              label={<Typography variant="body2" color="text.secondary">Использовать рерайт заголовка</Typography>} 
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            {isMocked && <Chip label="Сбой API (Заглушка)" color="error" size="small" />}
            {isGenerating && <Chip label="Нейросеть пишет текст..." color="warning" size="small" />}
            {isAssembling && <Chip label="Идет сборка финального видео (ждите)..." color="info" size="small" />}
            
            {type === 'ready' && !hasFile && <Chip label="Файл видео не найден на диске!" color="error" size="small" />}
            {type === 'ready' && isUploading && <Chip label="Загрузка на YouTube..." color="info" size="small" />}
          </Box>

          {type === 'ready' && task.video_path && (
            <Typography variant="body2" color={hasFile ? "text.secondary" : "error"} sx={{ mb: 2, fontFamily: 'monospace' }}>
              Файл:{' '}
              {hasFile ? (
                <Link 
                  component="button" 
                  variant="body2" 
                  onClick={(e) => { e.preventDefault(); if(onOpenFile) onOpenFile(task.task_id); }}
                  sx={{ fontFamily: 'monospace', textAlign: 'left', wordBreak: 'break-all' }}
                >
                  {task.video_path}
                </Link>
              ) : (
                <>{task.video_path} (не найден на диске)</>
              )}
            </Typography>
          )}

          <Box sx={{ pointerEvents: isBusy ? 'none' : 'auto', opacity: isBusy ? 0.6 : 1, width: '100%', display: 'flex', flexDirection: 'column' }}>
            
                <TextField 
                  key={`source-${task.source_url}`}
                  fullWidth 
                  name="source_url"
                  label="Источник" 
                  defaultValue={task.source_url || ""} 
                  variant="outlined" 
                  size="small"
                  sx={{ mb: 2 }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start" sx={{ mt: '-20px' }}>
                          <IconButton 
                            onClick={() => onRestoreSource(task.task_id, task.news_link)}
                            disabled={isBusy}
                            size="small"
                            title="Восстановить исходную ссылку"
                          >
                            <RotateCcw size={16} />
                          </IconButton>
                        </InputAdornment>
                      ),
                    }
                  }}
                />
                
                {/* Only queue needs prompt */}
                {type === 'queue' && (
                  <>
                    <TextField 
                      key={'prompt-' + task.task_id + '-' + task.prompt}
                      fullWidth 
                      name="prompt"
                      label="Текст для диктора" 
                      multiline 
                      rows={3} 
                      defaultValue={task.prompt} 
                      variant="outlined" 
                      size="small"
                      sx={{ 
                        mb: 2, 
                        '& textarea': { resize: 'vertical', overflow: 'auto !important' } 
                      }}
                      slotProps={{
                        input: {
                          startAdornment: (
                            <InputAdornment position="start" sx={{ mt: '-40px' }}>
                              <IconButton 
                                onClick={() => onFieldRegenerate(task.task_id, 'prompt')}
                                disabled={fieldLoadingIds.has(`${task.task_id}-prompt`)}
                                size="small"
                              >
                                {fieldLoadingIds.has(`${task.task_id}-prompt`) ? <CircularProgress size={16} /> : <RefreshCw size={16} />}
                              </IconButton>
                            </InputAdornment>
                          ),
                        }
                      }}
                    />

                  </>
                )}

                <TextField 
                  key={`desc-${task.task_id}-${task.video_description}`}
                  fullWidth 
                  name="video_description"
                  label="Описание" 
                  multiline 
                  rows={type === 'queue' ? 2 : 3} 
                  defaultValue={task.video_description} 
                  variant="outlined" 
                  size="small"
                  disabled={isBusy}
                  sx={{ 
                    mb: 2, 
                    '& textarea': { resize: 'vertical', overflow: 'auto !important' } 
                  }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start" sx={{ mt: type === 'queue' ? '-20px' : '-30px' }}>
                          <IconButton 
                            onClick={() => onFieldRegenerate(task.task_id, 'video_description')}
                            disabled={fieldLoadingIds.has(`${task.task_id}-video_description`) || isBusy}
                            size="small"
                          >
                            {fieldLoadingIds.has(`${task.task_id}-video_description`) ? <CircularProgress size={16} /> : <RefreshCw size={16} />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }
                  }}
                />
                 <TextField 
                  key={`tags-${task.task_id}-${task.video_tags}`}
                  fullWidth 
                  name="video_tags"
                  label="Теги" 
                  multiline
                  rows={2}
                  defaultValue={task.video_tags} 
                  variant="outlined" 
                  size="small"
                  disabled={isBusy}
                  sx={{ 
                    mb: 2, 
                    '& textarea': { resize: 'vertical', overflow: 'auto !important' } 
                  }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start" sx={{ mt: '-20px' }}>
                          <IconButton 
                            onClick={() => onFieldRegenerate(task.task_id, 'video_tags')}
                            disabled={fieldLoadingIds.has(`${task.task_id}-video_tags`) || isBusy}
                            size="small"
                          >
                            {fieldLoadingIds.has(`${task.task_id}-video_tags`) ? <CircularProgress size={16} /> : <RefreshCw size={16} />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }
                  }}
                />
                
                {/* Only queue needs keywords */}
                {type === 'queue' && (
                  <TextField 
                    key={'img-' + task.task_id + '-' + task.image_keywords}
                    fullWidth 
                    name="image_keywords"
                    label="Ключевые слова для картинок" 
                    defaultValue={task.image_keywords} 
                    variant="outlined" 
                    size="small"
                    sx={{ mb: 2 }}
                    slotProps={{
                      input: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <IconButton 
                              onClick={() => onFieldRegenerate(task.task_id, 'image_keywords')}
                              disabled={fieldLoadingIds.has(`${task.task_id}-image_keywords`)}
                              size="small"
                            >
                              {fieldLoadingIds.has(`${task.task_id}-image_keywords`) ? <CircularProgress size={16} /> : <RefreshCw size={16} />}
                            </IconButton>
                          </InputAdornment>
                        ),
                      }
                    }}
                  />
                )}
              {type === 'queue' && (
                  <Box sx={{ p: 2, border: "1px solid rgba(255,255,255,0.1)", borderRadius: 1 }}>
                    <Typography variant="subtitle2" sx={{ mb: 2, color: "text.secondary" }}>Настройки видео</Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6} md={3}>
                        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                          <InputLabel>Формат видео</InputLabel>
                          <Select key={'fmt-' + task.task_id + '-' + task.video_format} name="video_format" defaultValue={task.video_format || "VERTICAL"} label="Формат видео" onChange={(e) => setTimeout(() => onAutoSave(document.querySelector(`form[data-task-id="${task.task_id}"]`), task.task_id), 0)}>
                            <MenuItem value="VERTICAL">Вертикальное (9:16)</MenuItem>
                            <MenuItem value="HORIZONTAL">Горизонтальное (16:9)</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                          <InputLabel>Голос озвучки</InputLabel>
                          <Select key={'voice-' + task.task_id + '-' + task.voice} name="voice" defaultValue={task.voice || "female"} label="Голос озвучки" onChange={(e) => setTimeout(() => onAutoSave(document.querySelector(`form[data-task-id="${task.task_id}"]`), task.task_id), 0)}>
                            <MenuItem value="female">Женский</MenuItem>
                            <MenuItem value="male">Мужской</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                          <FormControl fullWidth size="small">
                            <InputLabel>Фоновая музыка</InputLabel>
                            <Select key={`music-${task.background_music}`} name="background_music" defaultValue={task.background_music || "default"} label="Фоновая музыка" onChange={(e) => setTimeout(() => onAutoSave(document.querySelector(`form[data-task-id="${task.task_id}"]`), task.task_id), 0)}>
                              <MenuItem value="default">По умолчанию</MenuItem>
                              <MenuItem value="none">Без музыки</MenuItem>
                              {task.background_music && task.background_music !== 'default' && task.background_music !== 'none' && (
                                  <MenuItem value={task.background_music}>Своя музыка (Файл)</MenuItem>
                              )}
                            </Select>
                          </FormControl>
                          <TextField 
                            name="music_volume"
                            label="Громкость (%)" 
                            type="number"
                            defaultValue={task.music_volume !== undefined ? task.music_volume : 30} 
                            variant="outlined" 
                            size="small"
                            sx={{ width: '120px' }}
                            slotProps={{ htmlInput: { min: 0, max: 100 } }}
                          />
                        </Box>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                          <InputLabel>Водяной знак</InputLabel>
                          <Select key={`wm-${task.watermark_path}`} name="watermark_path" defaultValue={task.watermark_path || "default"} label="Водяной знак" onChange={(e) => setTimeout(() => onAutoSave(document.querySelector(`form[data-task-id="${task.task_id}"]`), task.task_id), 0)}>
                            <MenuItem value="default">По умолчанию</MenuItem>
                            <MenuItem value="none">Без знака</MenuItem>
                            {task.watermark_path && task.watermark_path !== 'default' && task.watermark_path !== 'none' && (
                                <MenuItem value={task.watermark_path}>Свой знак (Файл)</MenuItem>
                            )}
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                          <TextField 
                            fullWidth 
                            name="duration"
                            label="Длительность (сек)" 
                            type="number"
                            value={localDuration} 
                            onChange={(e) => setLocalDuration(parseInt(e.target.value) || 30)} 
                            variant="outlined" 
                            size="small"
                          />
                          <TextField 
                            name="image_zoom"
                            label="Зум (%)" 
                            type="number"
                            defaultValue={task.image_zoom !== undefined ? task.image_zoom : 5} 
                            variant="outlined" 
                            size="small"
                            sx={{ width: '120px' }}
                            slotProps={{ htmlInput: { min: 0, max: 50 } }}
                          />
                        </Box>
                        <FormControlLabel
                          control={
                            <Switch
                              name="delete_temp_files"
                              defaultChecked={task.delete_temp_files !== false} 
                            />
                          }
                          label="Удалить временные файлы"
                        />
                      </Grid>
                    </Grid>
                  </Box>
                )}
          </Box>

          <Box sx={{ p: 2, mt: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>Площадки для публикации</Typography>
            <FormGroup row onChange={(e) => onAutoSave(e.currentTarget.closest('form'), task.task_id)}>
              <FormControlLabel control={<Checkbox name="platform_youtube" defaultChecked={selectedPlatforms.includes('youtube')} size="small" />} label="YouTube" />
              <FormControlLabel control={<Checkbox name="platform_telegram" defaultChecked={selectedPlatforms.includes('telegram')} size="small" />} label="Telegram" />
              <FormControlLabel control={<Checkbox name="platform_vk" defaultChecked={selectedPlatforms.includes('vk')} size="small" />} label="ВКонтакте" />
            </FormGroup>
          </Box>

          <Divider sx={{ my: 2 }} />
          
          <Box sx={{ display: 'flex', justifyContent: 'flex-start', gap: 2, mt: 2 }}>
            {type === 'queue' && showRegenerate && (
              <Button 
                variant="contained" 
                color={isMocked ? "warning" : "primary"}
                onClick={() => onRegenerateAll(task.task_id, localDuration)}
                disabled={isBusy}
              >
                {isMocked ? "Перегенерировать (без ИИ)" : "Перегенерировать (полностью)"}
              </Button>
            )}
            
            {type === 'queue' ? (
              <Button variant="outlined" color="error" onClick={() => onRemove(task.task_id)} disabled={isBusy}>
                Удалить из очереди
              </Button>
            ) : (
              <Button variant="outlined" color="error" onClick={() => onRemove(task.task_id)} disabled={isBusy}>
                Удалить видео
              </Button>
            )}
          </Box>
        </CardContent>
      </Box>
      {isAssembling && (
        <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 999, cursor: 'not-allowed' }} />
      )}
    </Card>
  );
}
