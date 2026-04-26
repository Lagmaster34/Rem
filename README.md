# 🌸 Rem - Asistente Virtual

Asistente virtual con la personalidad de **Rem de Re:Zero**, con reconocimiento de voz, texto a voz y control de la PC.

---

## ⚠️ Requisitos

- **Python 3.10** (no funciona con otras versiones)
- Windows 10/11 64 bits
- Conexión a internet

---

## 📥 Instalación

### 1. Instalar Python 3.10
Descarga e instala Python 3.10 desde aquí:
👉 https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe

> ⚠️ Durante la instalación marca la opción **"Add Python to PATH"**

---

### 2. Instalar las dependencias

Abre la terminal y ejecuta:

```bash
py -3.10 -m pip install psutil pyautogui pycaw comtypes pillow speechrecognition edge-tts groq pygame sounddevice soundfile pyaudio
```

---

### 3. Descargar archivos de voz y Voice Changer

Descarga la carpeta con los archivos necesarios (voz RVC de Rem + MMVCServerSIO):

👉 [Descargar desde Google Drive](https://drive.google.com/file/d/1OCJaZU1vs0j6gZX49MeBX_9KNSxXU_SR/view?usp=drive_link) ← 

Dentro encontrarás:
- 📁 `MMVCServerSIO` — el voice changer
- 📁 `voz rv de rem` — los archivos `.pth` e `.index` de Rem
- `VBCABLE_Driver_Pack45.zip` — cable de audio virtual

---

### 4. Instalar VBCABLE

Extrae `VBCABLE_Driver_Pack45.zip` y ejecuta **`VBCABLE_Setup_x64.exe`** como administrador.

> ⚠️ Reinicia el PC después de instalar VBCABLE

---

### 5. Configurar la imagen de fondo

Edita la línea 8 del archivo `Rem.py` y cambia la ruta a una imagen tuya:

```python
IMAGEN_FONDO = r"TU\RUTA\imagen.png"
```

---

### 6. Ejecutar el Voice Changer

1. Abre la carpeta `MMVCServerSIO`
2. Ejecuta **`start_http.bat`**
3. Espera a que abra la interfaz en el navegador
4. Configura:
   - **input** → `CABLE Output (VB-Audio)`
   - **output** → `Speakers` o `Headphones` según lo que uses
   - Selecciona el modelo **Rem_600e_6600s**
   - Dale clic en **start**

---

### 7. Ejecutar Rem

```bash
py -3.10 Rem.py
```

---

## 🎮 Comandos de voz

Puedes pedirle a Rem que haga lo siguiente:

| Comando | Acción |
|---|---|
| "Abre fortnite" | Abre un programa |
| "Cierra brave" | Cierra un programa |
| "Sube el volumen a 80" | Ajusta el volumen |
| "Toma una captura de pantalla" | Guarda captura en el escritorio |
| "Optimiza la PC" | Limpia temporales y libera RAM |
| "Busca gatos en internet" | Abre Google con la búsqueda |
| "Apaga la PC" | Apaga en 10 segundos |
| "Reinicia la PC" | Reinicia en 10 segundos |

---

## 📝 Notas

- El micrófono y audio se detectan automáticamente (auriculares o speakers)
- Si usas auriculares, cambia el **output** del voice changer a **Headphones**
- La API de Groq es gratuita en https://console.groq.com

---

## 📜 Créditos

- Modelo de voz RVC: Rem de Re:Zero
- Voice Changer: [w-okada/voice-changer](https://github.com/w-okada/voice-changer)
- LLM: [Groq](https://groq.com) con Llama 3.3 70B
- TTS: [edge-tts](https://github.com/rany2/edge-tts)
