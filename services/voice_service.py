import os
import assemblyai as aai
from dotenv import load_dotenv
load_dotenv()

class VoiceService:
    def __init__(self):
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

    def save_temp_audio(self, file_stream):
        """Guarda un archivo de audio temporalmente."""
        import tempfile
        from pathlib import Path
        suffix = Path(file_stream.filename or "audio.webm").suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp_path = temp.name
        file_stream.save(temp_path)
        print(f"Archivo guardado en: {temp_path}")
        if os.path.getsize(temp_path) == 0:
            os.remove(temp_path)
            raise ValueError("El archivo de audio está vacío")
        return temp_path

    def transcribe_audio(self, audio_path):
        """Transcribe un archivo de audio a texto usando AssemblyAI."""
        print(f"Transcribiendo archivo: {audio_path}")
        if not aai.settings.api_key:
            raise ValueError("Configura ASSEMBLYAI_API_KEY para habilitar la transcripcion de voz")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_path)
        if transcript.status == 'completed':
            return transcript.text
        raise ValueError("Error en la transcripción: " + transcript.error)
