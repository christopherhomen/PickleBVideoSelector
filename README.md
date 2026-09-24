# 🎾 PickleScout AI | Analizador y Clasificador de Videos de Pickleball

Aplicación Web Fullstack impulsada por Inteligencia Artificial Multimodal (**Google Gemini**) para analizar, auditar y clasificar videos de Pickleball cuadro por cuadro como un analista profesional.

---

## 🚀 Características Principales

1. **📥 Importación desde Google Drive:**
   - Descarga automática en lote (videos `.mp4`, `.mov`, `.avi`, etc.) desde carpetas compartidas o enlaces individuales de Drive.
2. **📤 Subida directa (Drag & Drop):**
   - Carga rápida de archivos de video locales.
3. **🧠 Análisis Multimodal con IA (Gemini):**
   - Conteo y detección de jugadores (Singles 1v1, Dobles 2v2, Drills).
   - Crónica detallada paso a paso de la jugada (saque, tercer golpe, rallies en cocina/NVZ, ataques).
   - Identificación de técnicas (Dinks, Drop shots, Speedups, Voleas, Remates, Foot faults).
   - Recomendación y clasificación estratégica para redes (Reels, Shorts, análisis técnico o descarte).
4. **🎬 Panel Interactivo y Reproductor Integrado:**
   - Filtros dinámicos por formato y categoría.
   - Exportación de reportes a **CSV (Excel)** y **JSON**.

---

## 💻 Requisitos Previos

- **Python 3.10** o superior
- **Node.js 18+** y `npm`
- **Clave API de Gemini** (Gratuita en [Google AI Studio](https://aistudio.google.com/app/apikey))

---

## 🛠️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/PickleScout-AI.git
cd PickleScout-AI
```

### 2. Configurar el entorno de Backend (Python)

**En Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**En macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar el Frontend (React + Vite)
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Configurar variables de entorno
Copia el archivo de ejemplo `.env.example` a `.env`:
```bash
cp .env.example .env
```
Edita `.env` e ingresa tu clave API:
```env
GEMINI_API_KEY=tu_clave_api_aqui
```
*(También puedes ingresar o actualizar la API Key directamente desde la interfaz web).*

---

## ▶️ Ejecución de la Aplicación

### En Windows:
Puedes hacer doble clic en `iniciar_app.bat` o ejecutar:
```bash
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

### En macOS / Linux:
```bash
./venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Abre tu navegador en:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## ⚙️ Desarrollo (Frontend independiente)

Si deseas modificar el frontend en tiempo real con Hot Reload:
```bash
cd frontend
npm run dev
```
Accede a `http://localhost:5173` (las llamadas `/api` se redirigen automáticamente al backend FastAPI en el puerto 8000).

---

## 📄 Licencia
MIT License. Libre para uso personal y académico.
