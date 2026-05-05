import React, { useState, useEffect, createContext } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Box, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Toolbar, Typography, AppBar, CircularProgress, Select, MenuItem, IconButton, FormControl, InputLabel, Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Chip } from '@mui/material';
import { LayoutDashboard, Newspaper, ListVideo, Settings, PlaySquare, Check, Folder, PlusCircle, Activity } from 'lucide-react';
import axios from 'axios';

import Dashboard from './pages/Dashboard';
import NewsList from './pages/NewsList';
import Queue from './pages/Queue';
import SettingsPage from './pages/Settings';
import SystemSettingsPage from './pages/SystemSettings';
import ReadyVideos from './pages/ReadyVideos';
import Scheduler from './pages/Scheduler';

const drawerWidth = 240;

export const GlobalUpdateContext = createContext(0);

function App() {
  const location = useLocation();
  const [globalStatus, setGlobalStatus] = useState("Ожидание задач...");
  const [currentModel, setCurrentModel] = useState("");
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  
  const [currentVoiceEngine, setCurrentVoiceEngine] = useState("");
  const [availableVoiceEngines, setAvailableVoiceEngines] = useState([]);
  const [selectedVoiceEngine, setSelectedVoiceEngine] = useState("");
  
  const [globalUpdateTs, setGlobalUpdateTs] = useState(0);

  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(
    localStorage.getItem('selectedProjectId') || 1
  );

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");

  useEffect(() => {
    // Устанавливаем заголовок по умолчанию для всех запросов axios
    axios.defaults.headers.common['X-Project-Id'] = selectedProjectId;
    localStorage.setItem('selectedProjectId', selectedProjectId);
    setGlobalUpdateTs(Date.now()); // Форсируем обновление всех страниц
  }, [selectedProjectId]);

  const fetchProjects = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/projects');
      setProjects(res.data);
      if (res.data.length === 0) {
        setCreateDialogOpen(true);
      } else if (!res.data.find(p => p.id == selectedProjectId)) {
        // If current selected project doesn't exist anymore, pick the first one
        setSelectedProjectId(res.data[0].id);
      }
    } catch (e) {
      console.error("Ошибка загрузки проектов", e);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      const res = await axios.post('http://localhost:8000/api/projects', { name: newProjectName });
      await fetchProjects();
      setSelectedProjectId(res.data.id);
      setCreateDialogOpen(false);
      setNewProjectName("");
    } catch (e) {
      console.error("Ошибка создания проекта", e);
    }
  };

  useEffect(() => {
    const intervalId = setInterval(async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/status');
        setGlobalStatus(res.data.status);
        if (res.data.model) {
          setCurrentModel(res.data.model);
        }
        if (res.data.available_models && JSON.stringify(res.data.available_models) !== JSON.stringify(availableModels)) {
          setAvailableModels(res.data.available_models);
        }
        if (res.data.voice_engine) {
          setCurrentVoiceEngine(res.data.voice_engine);
        }
        if (res.data.available_voice_engines && JSON.stringify(res.data.available_voice_engines) !== JSON.stringify(availableVoiceEngines)) {
          setAvailableVoiceEngines(res.data.available_voice_engines);
        }
        if (res.data.last_update && res.data.last_update !== globalUpdateTs) {
          setGlobalUpdateTs(res.data.last_update);
        }
      } catch (e) {
        // Игнорируем ошибки при поллинге
      }
    }, 1000);
    return () => clearInterval(intervalId);
  }, [globalUpdateTs, availableModels]);

  const isIdle = globalStatus.includes("Ожидание") || globalStatus.includes("завершен");

  const menuItems = [
    { text: 'Дашборд', icon: <LayoutDashboard />, path: '/' },
    { text: 'Лента новостей', icon: <Newspaper />, path: '/news' },
    { text: 'Очередь', icon: <ListVideo />, path: '/queue' },
    { text: 'Готовые видео', icon: <PlaySquare />, path: '/ready' },
    { text: 'Планировщик', icon: <Activity />, path: '/scheduler' },
    { text: 'Настройки проекта', icon: <Settings />, path: '/settings' },
    { text: 'Системные настройки', icon: <Settings />, path: '/system-settings' },
  ];

  const handleForceModel = async (model) => {
    if (!model) return;
    setSelectedModel(model);
    try {
      await axios.post('http://localhost:8000/api/set_model', { model });
      setCurrentModel(model);
    } catch (e) {
      console.error("Error setting model", e);
    }
  };

  const handleForceVoiceEngine = async (engine) => {
    if (!engine) return;
    setSelectedVoiceEngine(engine);
    try {
      await axios.post('http://localhost:8000/api/set_voice_engine', { engine });
      setCurrentVoiceEngine(engine);
    } catch (e) {
      console.error("Error setting voice engine", e);
    }
  };

  return (
    <GlobalUpdateContext.Provider value={globalUpdateTs}>
      <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1, bgcolor: '#1a1a1a', borderBottom: '1px solid #333' }}>
        <Toolbar>
          <Box sx={{ display: 'flex', justifyContent: 'flex-start', gap: 6, width: '100%', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 'bold' }}>
                Auto Shorts
              </Typography>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Folder size={20} style={{ color: '#90caf9' }} />
                <FormControl size="small" variant="standard" sx={{ minWidth: 200 }}>
                  <Select
                    value={projects.some(p => p.id == selectedProjectId) ? selectedProjectId : ''}
                    onChange={(e) => {
                      if (e.target.value === 'new') {
                        setCreateDialogOpen(true);
                      } else {
                        setSelectedProjectId(e.target.value);
                      }
                    }}
                    sx={{ color: 'white', '& .MuiSvgIcon-root': { color: 'white' }, '&::before': { borderBottom: '1px solid rgba(255,255,255,0.4)' } }}
                  >
                    {projects.map(p => (
                      <MenuItem key={p.id} value={p.id}>
                        {p.name}
                      </MenuItem>
                    ))}
                    <MenuItem value="new" sx={{ borderTop: '1px solid rgba(255,255,255,0.1)', mt: 1, pt: 1, color: '#90caf9' }}>
                      <PlusCircle size={16} style={{ marginRight: '8px' }}/> Создать проект...
                    </MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, bgcolor: 'rgba(0,0,0,0.3)', px: 2, py: 0.5, borderRadius: 2, maxWidth: '600px' }}>
              {!isIdle && <CircularProgress size={16} color="inherit" sx={{ flexShrink: 0 }} />}
              <Typography variant="body2" sx={{ fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {globalStatus}
              </Typography>
            </Box>
          </Box>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' },
        }}
      >
        <Toolbar variant="dense" />
        <Box sx={{ overflow: 'auto', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <List sx={{ flexGrow: 1 }}>
            {menuItems.map((item) => (
              <ListItem key={item.text} disablePadding>
                <ListItemButton component={Link} to={item.path} selected={location.pathname === item.path}>
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.text} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
          
          <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              Движок озвучки:
            </Typography>
            {availableVoiceEngines.length > 0 ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Select
                  size="small"
                  value={selectedVoiceEngine || currentVoiceEngine || availableVoiceEngines[0]}
                  onChange={(e) => handleForceVoiceEngine(e.target.value)}
                  sx={{ 
                    flexGrow: 1, 
                    minWidth: 0,
                    fontSize: '0.8rem', 
                    fontFamily: 'monospace',
                    color: currentVoiceEngine ? '#90caf9' : 'gray',
                    height: 30
                  }}
                >
                  {availableVoiceEngines.map(m => (
                    <MenuItem key={m} value={m} sx={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                      {m}
                    </MenuItem>
                  ))}
                </Select>
              </Box>
            ) : (
              <Typography variant="body2" sx={{ 
                fontWeight: 'bold', 
                fontFamily: currentVoiceEngine ? 'monospace' : 'inherit', 
                color: currentVoiceEngine ? '#90caf9' : 'gray',
                fontStyle: currentVoiceEngine ? 'normal' : 'italic',
                mb: 2
              }}>
                {currentVoiceEngine || "Ожидание..."}
              </Typography>
            )}
            
            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              Активная нейросеть:
            </Typography>
            {availableModels.length > 0 ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Select
                  size="small"
                  value={selectedModel || currentModel || availableModels[0]}
                  onChange={(e) => handleForceModel(e.target.value)}
                  sx={{ 
                    flexGrow: 1, 
                    minWidth: 0,
                    fontSize: '0.8rem', 
                    fontFamily: 'monospace',
                    color: currentModel ? '#90caf9' : 'gray',
                    height: 30
                  }}
                >
                  {availableModels.map(m => (
                    <MenuItem key={m} value={m} sx={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                      {m}
                    </MenuItem>
                  ))}
                </Select>
              </Box>
            ) : (
              <Typography variant="body2" sx={{ 
                fontWeight: 'bold', 
                fontFamily: currentModel ? 'monospace' : 'inherit', 
                color: currentModel ? '#90caf9' : 'gray',
                fontStyle: currentModel ? 'normal' : 'italic'
              }}>
                {currentModel || "Идет поиск..."}
              </Typography>
            )}
          </Box>
        </Box>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar variant="dense" />
        <GlobalUpdateContext.Provider value={globalUpdateTs}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/news" element={<NewsList />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/ready" element={<ReadyVideos />} />
            <Route path="/scheduler" element={<Scheduler />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/system-settings" element={<SystemSettingsPage />} />
          </Routes>
        </GlobalUpdateContext.Provider>
      </Box>

      {/* Модальное окно создания проекта */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} PaperProps={{ sx: { bgcolor: '#1e1e1e', color: 'white' } }}>
        <DialogTitle>Создать новый проект</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Название проекта"
            fullWidth
            variant="outlined"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            sx={{ mt: 1, input: { color: 'white' }, label: { color: 'gray' } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 0 }}>
          {projects.length > 0 && (
            <Button onClick={() => setCreateDialogOpen(false)} sx={{ color: 'gray' }}>Отмена</Button>
          )}
          <Button onClick={handleCreateProject} variant="contained" disabled={!newProjectName.trim()}>
            Создать
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
    </GlobalUpdateContext.Provider>
  );
}

export default App;
