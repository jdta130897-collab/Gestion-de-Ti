// static/js/voice_chatbot.js
function startRecognition() {
  const recognition = new webkitSpeechRecognition();
  recognition.lang = 'es-PE';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.start();

  recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript;
    document.getElementById("transcription").textContent = transcript;

    // Aquí se envía a backend (ajusta usuario/prioridad si deseas)
    fetch('/api/chatbot/ticket', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        usuario: 'usuario_demo',
        prioridad: 'alta',
        descripcion: transcript
      })
    })
    .then(response => response.json())
    .then(data => alert("Reporte generado correctamente"))
    .catch(error => alert("Error al crear el reporte"));
  };

  recognition.onerror = function(event) {
    alert("Error: " + event.error);
  };
}
