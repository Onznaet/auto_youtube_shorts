import React, { useState, useEffect, useContext } from 'react';
import { Box, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Button, Checkbox, TablePagination, Chip, Snackbar, Alert, Link, Tabs, Tab, Dialog, DialogTitle, DialogContent, DialogActions, TextField, IconButton, Switch, FormControlLabel } from '@mui/material';
import { Trash2, Plus, Edit2 } from 'lucide-react';
import axios from 'axios';

import { useToast } from '../contexts/ToastContext';
import { GlobalUpdateContext } from '../App';

export default function NewsList() {
  const [sources, setSources] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState(null);
  
  const [news, setNews] = useState([]);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [total, setTotal] = useState(0);
  const { showToast } = useToast();
  const [loadingIds, setLoadingIds] = useState(new Set());
  const [fetchingRss, setFetchingRss] = useState(false);
  const [lastRssUpdate, setLastRssUpdate] = useState(localStorage.getItem('lastRssUpdate') || '');
  const [hideProcessed, setHideProcessed] = useState(false);

  const [sourceDialogOpen, setSourceDialogOpen] = useState(false);
  const [editingSourceId, setEditingSourceId] = useState(null);
  const [initialSourceData, setInitialSourceData] = useState(null);
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceUrl, setNewSourceUrl] = useState('');
  const [newSourceIsAggregator, setNewSourceIsAggregator] = useState(false);

  const [autoParse, setAutoParse] = useState(false);

  const globalUpdateTs = useContext(GlobalUpdateContext);

  useEffect(() => {
    fetchSources();
    axios.get('http://localhost:8000/api/settings')
      .then(res => {
        if (res.data.auto_parse) {
          setAutoParse(res.data.auto_parse === 'true');
        }
        if (res.data.last_rss_update) {
          setLastRssUpdate(res.data.last_rss_update);
          localStorage.setItem('lastRssUpdate', res.data.last_rss_update);
        } else {
          const stored = localStorage.getItem('lastRssUpdate');
          if (stored) setLastRssUpdate(stored);
        }
      })
      .catch(err => console.error(err));
  }, [globalUpdateTs]);

  const handleAutoParseToggle = async (e) => {
    const checked = e.target.checked;
    setAutoParse(checked);
    try {
      await axios.post('http://localhost:8000/api/settings', {
        settings: { auto_parse: checked ? 'true' : 'false' }
      });
      showToast(`Автопарсинг ${checked ? 'включен' : 'выключен'}`, 'info');
    } catch (error) {
      showToast('Ошибка сохранения настроек', 'error');
    }
  };

  useEffect(() => {
    if (sources.length > 0) {
        if (!selectedSourceId || !sources.find(s => s.id === selectedSourceId)) {
            setSelectedSourceId(sources[0].id);
        }
    } else {
        setSelectedSourceId(null);
    }
  }, [sources]);

  useEffect(() => {
    if (selectedSourceId !== null || sources.length === 0) {
      fetchNews();
    }
  }, [page, rowsPerPage, selectedSourceId, hideProcessed, globalUpdateTs]);

  const fetchSources = async () => {
      try {
          const res = await axios.get('http://localhost:8000/api/sources');
          setSources(res.data);
      } catch (e) {
          console.error(e);
      }
  };

  const fetchNews = async () => {
    try {
      let url = `http://localhost:8000/api/news?skip=${page * rowsPerPage}&limit=${rowsPerPage}`;
      if (selectedSourceId) {
          url += `&source_id=${selectedSourceId}`;
      }
      if (hideProcessed) {
          url += `&hide_processed=true`;
      }
      const res = await axios.get(url);
      setNews(res.data.items);
      setTotal(res.data.total);
    } catch (error) {
      console.error("Error fetching news", error);
    }
  };

  const handleFetchForce = async () => {
    setFetchingRss(true);
    try {
      const res = await axios.post('http://localhost:8000/api/news/fetch');
      if (res.data.added > 0) {
        const now = new Date().toLocaleString();
        setLastRssUpdate(now);
        localStorage.setItem('lastRssUpdate', now);
        showToast(`Найдено новых новостей: ${res.data.added}`, 'success');
      } else {
        showToast(`Новых новостей пока нет.`, 'info');
      }
      fetchNews();
    } catch (error) {
      console.error("Error parsing rss", error);
      showToast("Ошибка парсинга RSS", 'error');
    } finally {
      setFetchingRss(false);
    }
  };

  const openEditDialog = (source, e) => {
      e.stopPropagation();
      setEditingSourceId(source.id);
      setNewSourceName(source.name);
      setNewSourceUrl(source.url);
      setNewSourceIsAggregator(source.is_aggregator || false);
      setInitialSourceData({ name: source.name, url: source.url, is_aggregator: source.is_aggregator || false });
      setSourceDialogOpen(true);
  };
  
  const openAddDialog = () => {
      setEditingSourceId(null);
      setNewSourceName('');
      setNewSourceUrl('');
      setNewSourceIsAggregator(false);
      setInitialSourceData(null);
      setSourceDialogOpen(true);
  };

  const handleSaveSource = async () => {
      try {
          if (editingSourceId) {
              await axios.put(`http://localhost:8000/api/sources/${editingSourceId}`, {
                  name: newSourceName,
                  url: newSourceUrl,
                  is_aggregator: newSourceIsAggregator
              });
              showToast('Источник обновлен', 'success');
          } else {
              await axios.post('http://localhost:8000/api/sources', {
                  name: newSourceName,
                  url: newSourceUrl,
                  is_aggregator: newSourceIsAggregator
              });
              showToast('Источник добавлен', 'success');
          }
          setSourceDialogOpen(false);
          fetchSources();
      } catch (e) {
          showToast('Ошибка сохранения', 'error');
      }
  };

  const handleDeleteSource = async (id, e) => {
      e.stopPropagation();
      if (!window.confirm("Удалить источник и все его новости?")) return;
      try {
          await axios.delete(`http://localhost:8000/api/sources/${id}`);
          showToast('Источник удален', 'success');
          setSourceDialogOpen(false);
          fetchSources();
      } catch (e) {
          showToast('Ошибка при удалении', 'error');
      }
  };

  const handleAddToQueue = async (id, format) => {
    const loadingKey = `${id}-${format}`;
    setLoadingIds(prev => new Set(prev).add(loadingKey));
    try {
      await axios.post(`http://localhost:8000/api/queue/add/${id}?format=${format}`);
      showToast(`Отправлено в очередь (${format === 'vertical' ? 'Vertical' : 'Видео'})!`, 'success');
      fetchNews();
    } catch (error) {
      const msg = error.response?.data?.detail || "Ошибка при добавлении в очередь";
      showToast(msg, 'error');
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(loadingKey);
        return next;
      });
    }
  };

  const handleRemoveFromQueue = async (id, format) => {
    const loadingKey = `${id}-${format}`;
    setLoadingIds(prev => new Set(prev).add(loadingKey));
    try {
      await axios.delete(`http://localhost:8000/api/queue/by_news/${id}?format=${format}`);
      showToast(`Удалено из очереди (${format === 'vertical' ? 'Vertical' : 'Видео'})!`, 'success');
      fetchNews();
    } catch (error) {
      const msg = error.response?.data?.detail || "Ошибка при удалении из очереди";
      showToast(msg, 'error');
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(loadingKey);
        return next;
      });
    }
  };

  return (
    <Box>
      <Box sx={{ position: 'sticky', top: '48px', zIndex: 1100, bgcolor: 'background.default', pt: 2, pb: 1, mt: -2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1, alignItems: 'flex-start' }}>
          <Typography variant="h5">Свежие новости</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <FormControlLabel
                control={<Switch checked={autoParse} onChange={handleAutoParseToggle} size="small" />}
                label="Автопарсинг"
                sx={{ m: 0 }}
              />
              <Button variant="contained" onClick={handleFetchForce} disabled={fetchingRss}>
                 {fetchingRss ? 'Ожидание...' : 'Спарсить RSS'}
              </Button>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mt: 1 }}>
              <FormControlLabel
                control={<Switch checked={hideProcessed} onChange={(e) => setHideProcessed(e.target.checked)} size="small" />}
                label="Только в работе"
                sx={{ m: 0 }}
              />
              {lastRssUpdate && (
                <Typography variant="caption" color="text.secondary">
                  Обновлено: {lastRssUpdate}
                </Typography>
              )}
            </Box>
          </Box>
        </Box>

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 0, display: 'flex', alignItems: 'center' }}>
          <Tabs value={selectedSourceId || false} onChange={(e, val) => { setPage(0); setSelectedSourceId(val); }} variant="scrollable" scrollButtons="auto" sx={{ minHeight: '48px' }}>
              {sources.map(s => (
                  <Tab 
                    key={s.id} 
                    value={s.id} 
                    label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {s.name}
                            {s.is_aggregator && (
                                <Chip size="small" label="Агрегатор" color="secondary" variant="outlined" sx={{ height: 20, fontSize: '0.65rem', ml: 0.5 }} />
                            )}
                            {s.active_count > 0 && (
                                <Chip size="small" label={s.active_count} color="primary" sx={{ height: 20, minWidth: 20, fontSize: '0.7rem' }} />
                            )}
                            <IconButton component="span" size="small" onClick={(e) => { e.stopPropagation(); openEditDialog(s, e); }} sx={{ p: 0.5 }}>
                                <Edit2 size={14} color="gray" />
                            </IconButton>
                        </Box>
                    } 
                  />
              ))}
          </Tabs>
          <Button size="small" startIcon={<Plus size={16} />} onClick={openAddDialog} sx={{ ml: 2, whiteSpace: 'nowrap' }}>
              Добавить
          </Button>
        </Box>
      </Box>
      
      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Дата</TableCell>
              <TableCell>Заголовок</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Действие</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {news.map((item) => {
              const shortsTask = item.queued_tasks?.find(t => t.format === 'VERTICAL');
              const isVerticalActive = shortsTask && (shortsTask.status === 'GENERATING' || shortsTask.status === 'ASSEMBLING');
              
              const videoTask = item.queued_tasks?.find(t => t.format === 'HORIZONTAL');
              const isVideoActive = videoTask && (videoTask.status === 'GENERATING' || videoTask.status === 'ASSEMBLING');
              
              let chipColor = 'default';
              if (item.status === 'NEW') chipColor = 'primary';
              else if (item.status === 'GENERATING' || item.status === 'UPLOADING') chipColor = 'warning';
              else if (item.status === 'READY') chipColor = 'info';
              else if (item.status === 'PUBLISHED') chipColor = 'success';

              return (
              <TableRow key={item.id}>
                <TableCell>{new Date(item.pub_date).toLocaleString()}</TableCell>
                <TableCell>
                  <Link href={item.link} target="_blank" rel="noopener noreferrer" color="inherit" underline="hover">
                    {item.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <Chip label={item.status} size="small" color={chipColor} />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
                    {item.queued_formats?.includes('VERTICAL') ? (
                      <Button 
                        size="small" 
                        variant="outlined" 
                        color={shortsTask?.status === 'PUBLISHED' ? 'success' : 'error'}
                        onClick={() => handleRemoveFromQueue(item.id, 'vertical')} 
                        disabled={loadingIds.has(`${item.id}-vertical`) || isVerticalActive}
                      >
                        {loadingIds.has(`${item.id}-vertical`) ? 'Ожидание...' : (shortsTask?.status === 'PUBLISHED' ? 'На ютубе (Удалить)' : (shortsTask?.status === 'READY' ? 'Готово (Удалить)' : 'Удалить Вертикальное'))}
                      </Button>
                    ) : (
                      <Button 
                        size="small" 
                        variant="outlined" 
                        onClick={() => handleAddToQueue(item.id, 'vertical')} 
                        disabled={loadingIds.has(`${item.id}-vertical`)}
                      >
                        {loadingIds.has(`${item.id}-vertical`) ? 'Ожидание...' : 'Вертикальное в очередь'}
                      </Button>
                    )}
                    
                    {item.queued_formats?.includes('HORIZONTAL') ? (
                      <Button 
                        size="small" 
                        variant="outlined" 
                        color={videoTask?.status === 'PUBLISHED' ? 'success' : 'error'}
                        onClick={() => handleRemoveFromQueue(item.id, 'horizontal')} 
                        disabled={loadingIds.has(`${item.id}-horizontal`) || isVideoActive}
                      >
                        {loadingIds.has(`${item.id}-horizontal`) ? 'Ожидание...' : (videoTask?.status === 'PUBLISHED' ? 'На ютубе (Удалить)' : (videoTask?.status === 'READY' ? 'Готово (Удалить)' : 'Удалить Горизонтальное'))}
                      </Button>
                    ) : (
                      <Button 
                        size="small" 
                        variant="outlined" 
                        color="secondary"
                        onClick={() => handleAddToQueue(item.id, 'horizontal')} 
                        disabled={loadingIds.has(`${item.id}-horizontal`)}
                      >
                        {loadingIds.has(`${item.id}-horizontal`) ? 'Ожидание...' : 'Горизонтальное в очередь'}
                      </Button>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            )})}
            {news.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 3 }}>Нет новостей для этого источника.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(e, newPage) => setPage(newPage)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
        }}
        labelRowsPerPage="Строк на странице:"
      />

      <Dialog open={sourceDialogOpen} onClose={() => setSourceDialogOpen(false)}>
        <DialogTitle>{editingSourceId ? 'Редактировать источник' : 'Добавить источник RSS'}</DialogTitle>
        <DialogContent>
            <TextField
                autoFocus
                margin="dense"
                label="Название (например, Lenta.ru)"
                fullWidth
                variant="outlined"
                value={newSourceName}
                onChange={e => setNewSourceName(e.target.value)}
                sx={{ mb: 2, mt: 1 }}
            />
            <TextField
                margin="dense"
                label="URL RSS потока"
                fullWidth
                variant="outlined"
                value={newSourceUrl}
                onChange={e => setNewSourceUrl(e.target.value)}
            />
            <FormControlLabel
                control={<Checkbox checked={newSourceIsAggregator} onChange={e => setNewSourceIsAggregator(e.target.checked)} />}
                label="Это агрегатор новостей (например, Yandex/Google News)"
                sx={{ mt: 1 }}
            />
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'space-between', px: 3 }}>
            <Box>
                {editingSourceId && (
                    <Button color="error" onClick={(e) => handleDeleteSource(editingSourceId, e)}>Удалить источник</Button>
                )}
            </Box>
            <Box>
                <Button onClick={() => setSourceDialogOpen(false)}>Закрыть</Button>
                {(!editingSourceId || newSourceName !== initialSourceData?.name || newSourceUrl !== initialSourceData?.url || newSourceIsAggregator !== initialSourceData?.is_aggregator) && (
                    <Button variant="contained" onClick={handleSaveSource} disabled={!newSourceName || !newSourceUrl} sx={{ ml: 1 }}>Сохранить</Button>
                )}
            </Box>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
