import React, { useState, useEffect, useRef } from 'react';
import {
  Play, Pause, RefreshCw, UploadCloud, FolderGit2, Trash2, CheckCircle2,
  AlertCircle, Clock, Video, Users, Tag, Sparkles, Download, Key,
  ExternalLink, Search, Filter, ShieldCheck, Film, ChevronRight, X,
  Scissors, Flame, Copy, Check, Share2
} from 'lucide-react';
import './App.css';

function extractViralClipInfo(analysis) {
  if (!analysis) return null;
  if (analysis.viral_clip && analysis.viral_clip.start_time) {
    return analysis.viral_clip;
  }

  // Fallback: parse timestamps from highlights or decision_recommendation
  const text = (analysis.highlights || '') + ' ' + (analysis.decision_recommendation || '') + ' ' + (analysis.actions_summary || '');
  const match = text.match(/(\d{1,2}:\d{2})\s*(?:a|hasta|-)\s*(\d{1,2}:\d{2})/);
  if (match) {
    const startStr = match[1];
    const endStr = match[2];
    const toSec = (t) => {
      const parts = t.split(':').map(Number);
      return (parts[0] || 0) * 60 + (parts[1] || 0);
    };
    const sSec = toSec(startStr);
    const eSec = toSec(endStr);
    return {
      start_time: startStr,
      end_time: endStr,
      start_seconds: sSec,
      end_seconds: eSec,
      duration_seconds: Math.max(0, eSec - sSec),
      hook_caption_es: analysis.highlights ? `¡El mejor momento del partido! (${startStr} - ${endStr}) 🔥⚡` : "¡Mira este rally épico en la red! ⚡😱",
      hook_caption_en: "Wait for the fastest hands at the net... ⚡🔥",
      suggested_hashtags: ["#pickleball", "#dinking", "#kitchenbattle", "#reels", "#pickleballhighlights"],
      dead_time_cut_advice: "Corta los tiempos muertos previos y deja solo la acción continua para retención del 100%."
    };
  }
  return null;
}

function parseStartTimeToSeconds(timestampStr) {
  if (timestampStr === undefined || timestampStr === null) return 0;
  if (typeof timestampStr === 'number') return timestampStr;
  const str = String(timestampStr).trim();
  // Match any hh:mm:ss or mm:ss pattern inside the text
  const match = str.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/);
  if (match) {
    if (match[3] !== undefined) {
      // hh:mm:ss
      return parseInt(match[1], 10) * 3600 + parseInt(match[2], 10) * 60 + parseInt(match[3], 10);
    } else {
      // mm:ss
      return parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
    }
  }
  const parsed = parseInt(str, 10);
  return isNaN(parsed) ? 0 : parsed;
}

function renderInteractiveTimestamps(text, onJump) {
  if (!text) return null;
  const strText = String(text);
  const regex = /(\[?\b\d{1,2}:\d{2}(?::\d{2})?\b(?:\s*(?:-|a|hasta)\s*\b\d{1,2}:\d{2}(?::\d{2})?\b)?\]?)/gi;

  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(strText)) !== null) {
    const matchStr = match[0];
    const matchIndex = match.index;

    if (matchIndex > lastIndex) {
      parts.push(strText.substring(lastIndex, matchIndex));
    }

    const sec = parseStartTimeToSeconds(matchStr);

    parts.push(
      <button
        key={`${matchIndex}-${matchStr}`}
        type="button"
        className="timestamp-badge-btn"
        onClick={(e) => {
          e.stopPropagation();
          onJump(sec);
        }}
        title={`Saltar el video al segundo ${sec} (${matchStr})`}
      >
        <Play size={10} fill="currentColor" style={{ marginRight: 3, display: 'inline-block' }} />
        {matchStr.replace(/^\[|\]$/g, '')}
      </button>
    );

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < strText.length) {
    parts.push(strText.substring(lastIndex));
  }

  return parts.length > 0 ? parts : strText;
}


function formatFullCapCutScript(capcut, title) {
  if (!capcut) return '';
  let out = `🎬 GUION DE EDICIÓN EN CAPCUT\n`;
  out += `Video: ${title || 'Pickleball Reel'}\n`;
  out += `Formato: ${capcut.aspect_ratio || '9:16 (Vertical)'}\n`;
  if (capcut.target_platforms) {
    out += `Plataformas: ${capcut.target_platforms.join(', ')}\n`;
  }
  if (capcut.sound_suggestion) {
    out += `Audio sugerido: ${capcut.sound_suggestion}\n`;
  }
  out += `\n--- GUION POR TOMAS (TIMELINE) ---\n`;
  (capcut.timeline_steps || []).forEach(step => {
    out += `\n▶️ [${step.timestamp}] (${step.duration || ''}) - ${step.action}\n`;
    out += `  • Texto en pantalla: "${step.on_screen_text}"\n`;
    if (step.text_style) out += `  • Estilo de texto: ${step.text_style}\n`;
    if (step.effect_or_transition) out += `  • Efecto / Transición: ${step.effect_or_transition}\n`;
    if (step.capcut_tool) out += `  • Herramienta CapCut: ${step.capcut_tool}\n`;
  });
  if (capcut.call_to_action) {
    out += `\n💬 LLAMADO A LA ACCIÓN (CTA):\n"${capcut.call_to_action}"\n`;
  }
  if (capcut.export_settings) {
    out += `\n⚙️ AJUSTES DE EXPORTACIÓN EN CAPCUT:\n${capcut.export_settings}\n`;
  }
  return out;
}

export default function App() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [driveUrl, setDriveUrl] = useState('');
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [activeTab, setActiveTab] = useState('drive'); // 'drive' or 'upload'
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [filterFormat, setFilterFormat] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadFiles, setUploadFiles] = useState([]);
  const [alertMsg, setAlertMsg] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  const fileInputRef = useRef(null);
  const modalVideoRef = useRef(null);

  const handleJumpToClip = (seconds) => {
    if (modalVideoRef.current) {
      const vid = modalVideoRef.current;
      const targetSec = Math.max(0, Number(seconds) || 0);
      try {
        vid.currentTime = targetSec;
        const playPromise = vid.play();
        if (playPromise !== undefined) {
          playPromise.catch((e) => {
            console.log("Play handled:", e);
          });
        }
      } catch (err) {
        console.warn("Error seeking video:", err);
      }
    }
  };

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  // Poll videos & system status
  const fetchVideos = async () => {
    try {
      const res = await fetch('/api/videos');
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
      }
    } catch (e) {
      console.error("Error fetching videos:", e);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (e) {
      console.error("Error fetching status:", e);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchVideos();
    const interval = setInterval(() => {
      fetchVideos();
      fetchStatus();
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const showAlert = (text, type = 'info') => {
    setAlertMsg({ text, type });
    setTimeout(() => setAlertMsg(null), 6000);
  };

  // Handle Google Drive Scan
  const handleDriveScan = async (e) => {
    e.preventDefault();
    if (!driveUrl.trim()) {
      showAlert('Por favor ingresa un enlace de Google Drive.', 'error');
      return;
    }
    setLoading(true);
    showAlert('Conectando a Google Drive y descargando los videos... Esto puede tardar según el tamaño.', 'info');
    try {
      const res = await fetch('/api/drive/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: driveUrl, auto_analyze: autoAnalyze })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al procesar la carpeta de Google Drive');
      showAlert(data.message, 'success');
      setDriveUrl('');
      fetchVideos();
      fetchStatus();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Handle Direct Upload
  const handleDirectUpload = async (e) => {
    e.preventDefault();
    if (!uploadFiles || uploadFiles.length === 0) {
      showAlert('Selecciona al menos un archivo de video.', 'error');
      return;
    }
    setLoading(true);
    showAlert(`Subiendo ${uploadFiles.length} video(s)...`, 'info');
    try {
      const formData = new FormData();
      for (let i = 0; i < uploadFiles.length; i++) {
        formData.append('files', uploadFiles[i]);
      }
      formData.append('auto_analyze', autoAnalyze);

      const res = await fetch('/api/videos/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al subir los videos');
      showAlert(data.message, 'success');
      setUploadFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchVideos();
      fetchStatus();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Analyze single video
  const handleAnalyzeVideo = async (videoId) => {
    try {
      const res = await fetch(`/api/videos/${videoId}/analyze`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al solicitar análisis');
      showAlert('Análisis con IA en curso para este video...', 'info');
      fetchVideos();
    } catch (err) {
      showAlert(err.message, 'error');
    }
  };

  // Analyze all pending
  const handleAnalyzeAll = async () => {
    try {
      const res = await fetch('/api/videos/analyze-all', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error');
      showAlert(data.message, 'info');
      fetchVideos();
    } catch (err) {
      showAlert(err.message, 'error');
    }
  };

  // Delete video
  const handleDeleteVideo = async (videoId) => {
    if (!window.confirm('¿Seguro que deseas eliminar este video y su análisis?')) return;
    try {
      const res = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedVideo?.id === videoId) setSelectedVideo(null);
        showAlert('Video eliminado.', 'success');
        fetchVideos();
        fetchStatus();
      }
    } catch (err) {
      showAlert(err.message, 'error');
    }
  };

  // Save API Key
  const handleSaveApiKey = async (e) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: apiKeyInput.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error guardando API Key');
      showAlert('API Key configurada correctamente!', 'success');
      setShowKeyModal(false);
      setApiKeyInput('');
      fetchStatus();
    } catch (err) {
      showAlert(err.message, 'error');
    }
  };

  // Filtering logic
  const filteredVideos = videos.filter((v) => {
    const analysis = v.analysis || {};
    const matchesSearch =
      v.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (analysis.title && analysis.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (analysis.actions_summary && analysis.actions_summary.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (analysis.pickleball_techniques && analysis.pickleball_techniques.some(t => t.toLowerCase().includes(searchQuery.toLowerCase())));

    const matchesFormat =
      filterFormat === 'all' ||
      (analysis.game_format && analysis.game_format.toLowerCase().includes(filterFormat.toLowerCase()));

    const matchesCategory =
      filterCategory === 'all' ||
      (analysis.classification_tag && analysis.classification_tag.toLowerCase().includes(filterCategory.toLowerCase()));

    return matchesSearch && matchesFormat && matchesCategory;
  });

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <header className="navbar glass-panel">
        <div className="nav-brand">
          <div className="brand-icon">🎾</div>
          <div>
            <div className="brand-title">PickleScout <span className="brand-badge">AI VISION</span></div>
            <div className="brand-subtitle">Analizador y Clasificador Inteligente de Videos de Pickleball</div>
          </div>
        </div>

        <div className="nav-actions">
          {/* API Key Status Button */}
          <button
            className={`btn btn-secondary ${systemStatus?.has_api_key ? 'key-active' : 'key-missing'}`}
            onClick={() => setShowKeyModal(true)}
            title="Configurar clave Gemini API"
          >
            <Key size={16} />
            <span>{systemStatus?.has_api_key ? 'Gemini API: Conectada' : '⚠️ Configurar API Key'}</span>
          </button>

          {/* Export Buttons */}
          <a href="/api/export?export_format=csv" download className="btn btn-secondary" title="Descargar reporte en CSV">
            <Download size={16} /> CSV
          </a>
          <a href="/api/export?export_format=json" download className="btn btn-secondary" title="Descargar datos en JSON">
            <Download size={16} /> JSON
          </a>
        </div>
      </header>

      {/* Alert banner */}
      {alertMsg && (
        <div className={`alert-toast alert-${alertMsg.type}`}>
          {alertMsg.type === 'error' && <AlertCircle size={20} />}
          {alertMsg.type === 'success' && <CheckCircle2 size={20} />}
          {alertMsg.type === 'info' && <RefreshCw size={20} className="animate-spin" />}
          <span>{alertMsg.text}</span>
          <button onClick={() => setAlertMsg(null)} className="alert-close"><X size={16} /></button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="main-content">
        {/* Ingestion Box */}
        <section className="ingestion-section glass-panel">
          <div className="ingestion-tabs">
            <button
              className={`tab-btn ${activeTab === 'drive' ? 'active' : ''}`}
              onClick={() => setActiveTab('drive')}
            >
              <FolderGit2 size={18} />
              <span>Importar desde Google Drive</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              <UploadCloud size={18} />
              <span>Subir Videos Locales (Lote / Drag & Drop)</span>
            </button>
          </div>

          <div className="ingestion-body">
            {activeTab === 'drive' ? (
              <form onSubmit={handleDriveScan} className="drive-form">
                <p className="tab-hint">
                  Pega el enlace de la carpeta de Google Drive que contiene los videos de Pickleball.
                  Asegúrate de que la carpeta esté configurada con <strong>"Cualquiera con el enlace puede ver"</strong>.
                </p>
                <div className="input-group">
                  <input
                    type="url"
                    className="input-field"
                    placeholder="https://drive.google.com/drive/folders/1A2B3C4D5E... o enlace de video"
                    value={driveUrl}
                    onChange={(e) => setDriveUrl(e.target.value)}
                    disabled={loading}
                    required
                  />
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? <RefreshCw size={18} className="animate-spin" /> : <FolderGit2 size={18} />}
                    <span>{loading ? 'Descargando...' : 'Escanear Carpeta de Drive'}</span>
                  </button>
                </div>
                <div className="checkbox-row">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={autoAnalyze}
                      onChange={(e) => setAutoAnalyze(e.target.checked)}
                    />
                    <span>Analizar videos con Inteligencia Artificial inmediatamente después de descargarlos</span>
                  </label>
                </div>
              </form>
            ) : (
              <form onSubmit={handleDirectUpload} className="upload-form">
                <p className="tab-hint">
                  Selecciona o arrastra múltiples videos (.mp4, .mov, .webm) directamente desde tu computadora (pueden ser 8, 15, 30 o más).
                </p>
                <div className="upload-dropzone" onClick={() => fileInputRef.current?.click()}>
                  <UploadCloud size={40} className="dropzone-icon" />
                  <div className="dropzone-text">
                    {uploadFiles.length > 0
                      ? `Has seleccionado ${uploadFiles.length} archivo(s)`
                      : 'Haz clic aquí o arrastra los videos de Pickleball'}
                  </div>
                  <div className="dropzone-sub">Formatos soportados: MP4, MOV, WEBM, MKV</div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    multiple
                    accept="video/*"
                    style={{ display: 'none' }}
                    onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
                  />
                </div>
                <div className="upload-actions-row">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={autoAnalyze}
                      onChange={(e) => setAutoAnalyze(e.target.checked)}
                    />
                    <span>Analizar con IA automáticamente al terminar la subida</span>
                  </label>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading || uploadFiles.length === 0}
                  >
                    {loading ? <RefreshCw size={18} className="animate-spin" /> : <Film size={18} />}
                    <span>Subir y Procesar {uploadFiles.length > 0 ? `(${uploadFiles.length})` : ''}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </section>

        {/* Toolbar & Filter Bar */}
        <section className="toolbar-section">
          <div className="search-bar">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              placeholder="Buscar por jugada, técnica (dinks, drop, remate), jugadores, o nombre..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field search-input"
            />
          </div>

          <div className="filters-group">
            <select
              className="input-field filter-select"
              value={filterFormat}
              onChange={(e) => setFilterFormat(e.target.value)}
            >
              <option value="all">Todos los Formatos</option>
              <option value="dobles">Dobles (2 vs 2)</option>
              <option value="singles">Singles (1 vs 1)</option>
              <option value="entrenamiento">Entrenamiento / Drills</option>
              <option value="peloteo">Peloteo Recreativo</option>
            </select>

            <select
              className="input-field filter-select"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            >
              <option value="all">Todas las Categorías</option>
              <option value="redes">⭐ Destacado Redes / Reels</option>
              <option value="técnico">🎯 Análisis Técnico</option>
              <option value="partido">🎾 Partido Completo</option>
              <option value="drill">💡 Drill / Entrenamiento</option>
              <option value="descartar">⚠️ Descartar</option>
            </select>

            <button
              className="btn btn-secondary"
              onClick={handleAnalyzeAll}
              title="Analiza todos los videos pendientes"
            >
              <Sparkles size={16} /> Analizar Pendientes
            </button>
          </div>
        </section>

        {/* Video Grid Section */}
        <section className="videos-section">
          <div className="section-header">
            <h2>
              Videos Disponibles <span className="counter-pill">{filteredVideos.length}</span>
            </h2>
            <div className="stats-badges">
              <span className="badge badge-analyzed">
                Analizados: {videos.filter(v => v.status === 'analyzed').length}
              </span>
              <span className="badge badge-pending">
                Pendientes: {videos.filter(v => v.status === 'pending').length}
              </span>
            </div>
          </div>

          {filteredVideos.length === 0 ? (
            <div className="empty-state glass-panel">
              <Film size={48} className="empty-icon" />
              <h3>No hay videos en la galería</h3>
              <p>Pega un enlace de Google Drive arriba o sube tus archivos de video para comenzar el análisis.</p>
            </div>
          ) : (
            <div className="video-grid">
              {filteredVideos.map((vid) => {
                const a = vid.analysis;
                const isAnalyzed = vid.status === 'analyzed' && a;
                const isProcessing = vid.status === 'processing';
                const isFailed = vid.status === 'failed';
                const viralClip = isAnalyzed ? extractViralClipInfo(a) : null;

                return (
                  <div key={vid.id} className={`video-card glass-panel ${selectedVideo?.id === vid.id ? 'active-card' : ''}`}>
                    {/* Video Player / Thumbnail Preview */}
                    <div className="card-media-wrapper" onClick={() => setSelectedVideo(vid)}>
                      <video
                        src={`/api/videos/${vid.id}/stream`}
                        preload="metadata"
                        className="card-video-preview"
                        controls={false}
                      />
                      <div className="media-overlay">
                        <button className="play-overlay-btn">
                          <Play size={24} fill="#fff" />
                        </button>
                        <span className="duration-tag">{vid.size_mb} MB • {vid.format}</span>
                      </div>
                      <div className="status-badge-overlay">
                        {isAnalyzed && <span className="badge badge-analyzed">✓ Analizado</span>}
                        {isProcessing && <span className="badge badge-processing">⚡ {vid.progress_step || 'Procesando...'}</span>}
                        {vid.status === 'pending' && <span className="badge badge-pending">⏳ Pendiente</span>}
                        {isFailed && <span className="badge badge-failed">⚠️ Error</span>}
                      </div>
                    </div>

                    {/* Card Content */}
                    <div className="card-body">
                      <h4 className="video-title" title={isAnalyzed ? a.title : vid.filename}>
                        {isAnalyzed ? a.title : vid.filename}
                      </h4>

                      {isAnalyzed ? (
                        <>
                          {/* Viral Moment Pill */}
                          {viralClip && (
                            <div className="viral-card-pill">
                              <Flame size={14} className="flame-icon" />
                              <span>Reel: <strong>{viralClip.start_time} - {viralClip.end_time}</strong> ({viralClip.duration_seconds}s)</span>
                            </div>
                          )}

                          {/* CapCut Script Pill */}
                          {a.capcut_recommendation && (
                            <div className="capcut-card-pill">
                              <Scissors size={13} className="capcut-pill-icon" />
                              <span>CapCut: <strong>{a.capcut_recommendation.timeline_steps?.length || 3} tomas y textos listos</strong></span>
                            </div>
                          )}

                          {/* Quick AI Specs */}
                          <div className="specs-row">
                            <span className="spec-item"><Users size={14} /> {a.people_count} personas ({a.game_format})</span>
                          </div>

                          {/* Human Decision Banner */}
                          <div className="decision-banner">
                            <div className="decision-header">
                              <span className="decision-tag">{a.classification_tag}</span>
                              <span className="confidence-pill">{a.confidence_score}% certeza</span>
                            </div>
                            <p className="decision-text">
                              <strong>¿Para qué sirve?</strong> {a.decision_recommendation}
                            </p>
                          </div>

                          {/* Pickleball Techniques Tags */}
                          {a.pickleball_techniques && a.pickleball_techniques.length > 0 && (
                            <div className="tags-container">
                              {a.pickleball_techniques.slice(0, 4).map((tech, idx) => (
                                <span key={idx} className="tech-chip">{tech}</span>
                              ))}
                              {a.pickleball_techniques.length > 4 && (
                                <span className="tech-chip more">+{a.pickleball_techniques.length - 4}</span>
                              )}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="unprocessed-notice">
                          {isProcessing ? (
                            <p className="processing-text">
                              <RefreshCw size={14} className="animate-spin" />
                              {vid.progress_step || 'Gemini está procesando el video...'}
                            </p>
                          ) : isFailed ? (
                            <p className="error-text">Fallo: {vid.error_message || 'Verifica la API Key'}</p>
                          ) : (
                            <p className="pending-text">Video listo para ser analizado por la IA.</p>
                          )}
                        </div>
                      )}

                      {/* Card Footer Actions */}
                      <div className="card-footer">
                        <button
                          className="btn btn-secondary card-btn"
                          onClick={() => setSelectedVideo(vid)}
                        >
                          <Play size={14} /> Ver Video & Análisis
                        </button>
                        {!isProcessing && (
                          <button
                            className="btn btn-secondary icon-btn"
                            onClick={() => handleAnalyzeVideo(vid.id)}
                            title="Re-analizar con IA"
                          >
                            <RefreshCw size={14} />
                          </button>
                        )}
                        <button
                          className="btn btn-danger icon-btn"
                          onClick={() => handleDeleteVideo(vid.id)}
                          title="Eliminar video"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>

      {/* Full Video Inspection Modal */}
      {selectedVideo && (
        <div className="modal-backdrop" onClick={() => setSelectedVideo(null)}>
          <div className="modal-content glass-panel-elevated" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedVideo.analysis?.title || selectedVideo.filename}</h3>
                <span className="modal-sub">{selectedVideo.filename} • {selectedVideo.size_mb} MB</span>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedVideo(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body-split">
              {/* Left Column: Video Player with Speed Control */}
              <div className="modal-player-pane">
                <video
                  key={selectedVideo.id}
                  ref={modalVideoRef}
                  src={`/api/videos/${selectedVideo.id}/stream`}
                  controls
                  playsInline
                  preload="auto"
                  className="main-modal-video"
                />
                <div className="player-hints">
                  💡 Tip: Puedes usar el botón "Reproducir Clip" de la derecha para saltar directamente a la jugada viral recomendada.
                </div>
              </div>

              {/* Right Column: Deep AI Breakdown */}
              <div className="modal-analysis-pane">
                {selectedVideo.status === 'analyzed' && selectedVideo.analysis ? (
                  <div className="analysis-report">
                    {/* Viral Studio Section */}
                    {(() => {
                      const clip = extractViralClipInfo(selectedVideo.analysis);
                      const a = selectedVideo.analysis;
                      if (!clip && !a.viral_score && !a.viral_archetypes) return null;

                      return (
                        <div className="viral-studio-box">
                          <div className="viral-studio-header">
                            <div className="viral-header-left">
                              <Flame size={20} className="flame-neon-icon" />
                              <h4>Estudio de Viralidad & Recorte para Reels / TikTok</h4>
                            </div>
                            <span className="viral-score-badge">
                              🔥 {a.viral_score || 95}/100 Potencial Viral
                            </span>
                          </div>

                          {/* Detected Viral Archetypes */}
                          {a.viral_archetypes && a.viral_archetypes.length > 0 && (
                            <div className="viral-archetypes-row">
                              <span className="archetypes-label">Jugadas Virales Detectadas:</span>
                              <div className="archetypes-chips">
                                {a.viral_archetypes.map((arch, idx) => (
                                  <span key={idx} className="archetype-pill">⚡ {arch}</span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Point outcome reason */}
                          {a.point_outcome_reason && (
                            <div className="outcome-reason-box">
                              <strong>🎾 Desenlace Táctico del Punto:</strong> {renderInteractiveTimestamps(a.point_outcome_reason, handleJumpToClip)}
                            </div>
                          )}

                          {/* Clip Recommendation Banner */}
                          {clip && (
                            <div className="clip-recommendation-card">
                              <div className="clip-time-bar">
                                <div className="clip-time-info">
                                  <Scissors size={18} className="scissors-icon" />
                                  <span>
                                    Corte sugerido: <strong>{clip.start_time} ➔ {clip.end_time}</strong>
                                    <span className="duration-pill">({clip.duration_seconds} segs)</span>
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="btn btn-jump-clip"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleJumpToClip(clip.start_seconds);
                                  }}
                                  title="Ir al inicio de la jugada viral en el reproductor"
                                >
                                  <Play size={14} fill="#fff" /> Reproducir Clip
                                </button>
                              </div>

                              {/* Dead time notice */}
                              {clip.dead_time_cut_advice && (
                                <p className="dead-time-advice">
                                  ✂️ <em>Consejo de edición:</em> {renderInteractiveTimestamps(clip.dead_time_cut_advice, handleJumpToClip)}
                                </p>
                              )}

                              {/* Social Hook Copy Area */}
                              <div className="hook-captions-grid">
                                <div className="hook-box">
                                  <div className="hook-box-header">
                                    <span>Gancho para Redes (Español):</span>
                                    <button
                                      className="copy-mini-btn"
                                      onClick={() => copyToClipboard(clip.hook_caption_es, 'hook_es')}
                                    >
                                      {copiedKey === 'hook_es' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                                      {copiedKey === 'hook_es' ? 'Copiado!' : 'Copiar'}
                                    </button>
                                  </div>
                                  <div className="hook-text">"{clip.hook_caption_es}"</div>
                                </div>

                                <div className="hook-box">
                                  <div className="hook-box-header">
                                    <span>Viral Hook (English / US Audience):</span>
                                    <button
                                      className="copy-mini-btn"
                                      onClick={() => copyToClipboard(clip.hook_caption_en, 'hook_en')}
                                    >
                                      {copiedKey === 'hook_en' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                                      {copiedKey === 'hook_en' ? 'Copiado!' : 'Copiar'}
                                    </button>
                                  </div>
                                  <div className="hook-text">"{clip.hook_caption_en}"</div>
                                </div>
                              </div>

                              {/* Hashtags */}
                              {clip.suggested_hashtags && (
                                <div className="hashtags-row">
                                  <div className="hashtags-list">
                                    {clip.suggested_hashtags.map((h, idx) => (
                                      <span key={idx} className="hashtag-chip">{h}</span>
                                    ))}
                                  </div>
                                  <button
                                    className="copy-mini-btn"
                                    onClick={() => copyToClipboard(clip.suggested_hashtags.join(' '), 'tags')}
                                  >
                                    {copiedKey === 'tags' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                                    {copiedKey === 'tags' ? 'Copiados!' : 'Copiar Hashtags'}
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* CapCut Editing Recommendation & Storyboard */}
                    {(() => {
                      const a = selectedVideo.analysis;
                      const capcut = a.capcut_recommendation;
                      if (!capcut) return null;

                      return (
                        <div className="capcut-guide-box">
                          <div className="capcut-guide-header">
                            <div className="capcut-header-left">
                              <div className="capcut-logo-badge">
                                <Scissors size={18} />
                              </div>
                              <div>
                                <h4 className="capcut-title">Recomendación de Edición en CapCut</h4>
                                <span className="capcut-subtitle">
                                  Guion técnico paso a paso con textos para Instagram Reels, TikTok, Shorts y Facebook
                                </span>
                              </div>
                            </div>
                            <button
                              className="btn btn-copy-script"
                              onClick={() => copyToClipboard(formatFullCapCutScript(capcut, a.title), 'capcut_full')}
                              title="Copiar guion completo formateado para tu editor"
                            >
                              {copiedKey === 'capcut_full' ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                              {copiedKey === 'capcut_full' ? '¡Guion Copiado!' : 'Copiar Guion Completo'}
                            </button>
                          </div>

                          {/* Technical Specs Bar */}
                          <div className="capcut-meta-bar">
                            <div className="capcut-meta-item">
                              <span className="meta-k">📐 Formato:</span>
                              <span className="meta-v">{capcut.aspect_ratio || '9:16 (Vertical)'}</span>
                            </div>
                            <div className="capcut-meta-item">
                              <span className="meta-k">🎵 Audio sugerido:</span>
                              <span className="meta-v">{capcut.sound_suggestion}</span>
                            </div>
                            {capcut.target_platforms && (
                              <div className="capcut-meta-item">
                                <span className="meta-k">📱 Plataformas:</span>
                                <span className="meta-v">{capcut.target_platforms.join(' • ')}</span>
                              </div>
                            )}
                          </div>

                          {/* Step-by-Step Storyboard */}
                          <div className="capcut-timeline-list">
                            <div className="timeline-title-row">
                              <span>🎬 Guion Cronológico por Tomas (Segundo a Segundo):</span>
                            </div>
                            {(capcut.timeline_steps || []).map((step, idx) => {
                              const stepSec = parseStartTimeToSeconds(step.timestamp);
                              const copyKey = `step_${idx}`;
                              return (
                                <div key={idx} className="capcut-step-card">
                                  <div className="step-card-top">
                                    <div className="step-badge-group">
                                      <span className="step-index-badge">Paso {step.step_number || idx + 1}</span>
                                      <span className="step-action-name">{step.action}</span>
                                      <span className="step-time-pill">⏱️ {step.timestamp} ({step.duration})</span>
                                    </div>
                                    <button
                                      type="button"
                                      className="btn btn-jump-mini"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleJumpToClip(stepSec);
                                      }}
                                      title={`Saltar el video al segundo de inicio (${step.timestamp})`}
                                    >
                                      <Play size={12} fill="#fff" /> Ir al segundo
                                    </button>
                                  </div>

                                  {/* Text on Screen */}
                                  <div className="step-text-row">
                                    <div className="step-text-label">
                                      <span>💬 Texto en Pantalla (Overlay en CapCut):</span>
                                      <button
                                        className="copy-mini-btn"
                                        onClick={() => copyToClipboard(step.on_screen_text, copyKey)}
                                        title="Copiar solo este texto"
                                      >
                                        {copiedKey === copyKey ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                        {copiedKey === copyKey ? 'Copiado!' : 'Copiar Texto'}
                                      </button>
                                    </div>
                                    <div className="step-screen-preview">
                                      "{step.on_screen_text}"
                                    </div>
                                    {step.text_style && (
                                      <div className="step-style-hint">
                                        🎨 <em>Estilo recomendado:</em> {step.text_style}
                                      </div>
                                    )}
                                  </div>

                                  {/* Transitions and tools */}
                                  <div className="step-tools-row">
                                    <div className="step-tool-col">
                                      <span className="tool-lbl">✨ Efecto o Transición:</span>
                                      <span className="tool-val">{step.effect_or_transition}</span>
                                    </div>
                                    <div className="step-tool-col">
                                      <span className="tool-lbl">🛠️ Herramienta en CapCut:</span>
                                      <span className="tool-val code-val">{step.capcut_tool}</span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>

                          {/* CTA Call to Action Box */}
                          {capcut.call_to_action && (
                            <div className="capcut-cta-box">
                              <div className="cta-header">
                                <span>📢 Llamado a la Acción (CTA para Comentarios & Algoritmo):</span>
                                <button
                                  className="copy-mini-btn"
                                  onClick={() => copyToClipboard(capcut.call_to_action, 'cta_capcut')}
                                >
                                  {copiedKey === 'cta_capcut' ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                  {copiedKey === 'cta_capcut' ? 'Copiado!' : 'Copiar CTA'}
                                </button>
                              </div>
                              <p className="cta-content">"{capcut.call_to_action}"</p>
                            </div>
                          )}

                          {/* Export Settings Note */}
                          {capcut.export_settings && (
                            <div className="capcut-export-note">
                              ⚙️ <strong>Exportación en CapCut:</strong> {capcut.export_settings}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Big Decision Box */}
                    <div className="report-decision-box">
                      <div className="decision-box-top">
                        <span className="report-badge-tag">{selectedVideo.analysis.classification_tag}</span>
                        <span className="confidence-pill">{selectedVideo.analysis.confidence_score}% confianza</span>
                      </div>
                      <div className="decision-title">🎯 Decisión y Recomendación:</div>
                      <p className="decision-body">{selectedVideo.analysis.decision_recommendation}</p>
                    </div>

                    {/* Metadata Grid */}
                    <div className="report-stats-grid">
                      <div className="stat-card">
                        <div className="stat-label">Jugadores Visibles</div>
                        <div className="stat-val">{selectedVideo.analysis.people_count}</div>
                        <div className="stat-sub">{selectedVideo.analysis.players_description}</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-label">Formato</div>
                        <div className="stat-val">{selectedVideo.analysis.game_format}</div>
                        <div className="stat-sub">{selectedVideo.analysis.camera_setup}</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-label">Calidad & Audio</div>
                        <div className="stat-val">{selectedVideo.analysis.video_quality}</div>
                        <div className="stat-sub">{selectedVideo.analysis.audio_analysis}</div>
                      </div>
                    </div>

                    {/* Action Chronicle */}
                    <div className="report-section">
                      <h4>📋 Crónica y Resumen de la Jugada</h4>
                      <p className="narrative-text">{renderInteractiveTimestamps(selectedVideo.analysis.actions_summary, handleJumpToClip)}</p>
                    </div>

                    {/* Techniques Observed */}
                    {selectedVideo.analysis.pickleball_techniques && (
                      <div className="report-section">
                        <h4>🎾 Técnicas & Golpes Identificados</h4>
                        <div className="tags-container">
                          {selectedVideo.analysis.pickleball_techniques.map((tech, i) => (
                            <span key={i} className="tech-chip-large">{tech}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Highlights */}
                    {selectedVideo.analysis.highlights && (
                      <div className="report-section">
                        <h4>🌟 Momentos Destacados</h4>
                        <p className="highlight-text">{renderInteractiveTimestamps(selectedVideo.analysis.highlights, handleJumpToClip)}</p>
                      </div>
                    )}

                    {/* Mistakes / Notes */}
                    {selectedVideo.analysis.mistakes_or_issues && (
                      <div className="report-section">
                        <h4>⚠️ Errores o Fallos Observados</h4>
                        <p className="mistake-text">{renderInteractiveTimestamps(selectedVideo.analysis.mistakes_or_issues, handleJumpToClip)}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="modal-unprocessed-pane">
                    <Sparkles size={40} className="empty-icon" />
                    <h4>Este video aún no tiene análisis completo</h4>
                    <p>Haz clic abajo para iniciar el análisis multimodal con IA.</p>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleAnalyzeVideo(selectedVideo.id)}
                    >
                      <Sparkles size={16} /> Analizar Video Ahora
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* API Key Modal */}
      {showKeyModal && (
        <div className="modal-backdrop" onClick={() => setShowKeyModal(false)}>
          <div className="modal-content glass-panel-elevated modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Configurar Gemini API Key</h3>
              <button className="modal-close-btn" onClick={() => setShowKeyModal(false)}><X size={20} /></button>
            </div>
            <form onSubmit={handleSaveApiKey} className="key-form">
              <p className="tab-hint">
                Para que la IA pueda "ver" los videos cuadro por cuadro y analizarlos de verdad, ingresa tu clave gratuita de <strong>Google Gemini API</strong> (obtenida en <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: '#84cc16' }}>Google AI Studio</a>).
              </p>
              <input
                type="password"
                className="input-field"
                placeholder="AIzaSy..."
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                required
              />
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowKeyModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary">
                  Guardar API Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
