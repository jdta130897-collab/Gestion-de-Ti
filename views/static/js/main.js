// Funciones generales

// Inicializar tooltips de Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
});

// Funciones para gráficos
function createDoughnutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function createBarChart(canvasId, labels, data, label, color) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: color,
                borderColor: color,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createLineChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Función para confirmación de eliminación
function confirmDelete(formId, message) {
    document.getElementById(formId).addEventListener('submit', function(event) {
        if (!confirm(message || '¿Estás seguro de que deseas eliminar este elemento? Esta acción no se puede deshacer.')) {
            event.preventDefault();
        }
    });
}

// Función para mostrar/ocultar contraseña
function togglePasswordVisibility(inputId, buttonId) {
    const passwordInput = document.getElementById(inputId);
    const toggleButton = document.getElementById(buttonId);
    
    if (passwordInput && toggleButton) {
        toggleButton.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Cambiar icono
            if (type === 'password') {
                toggleButton.innerHTML = '<i class="bi bi-eye"></i>';
            } else {
                toggleButton.innerHTML = '<i class="bi bi-eye-slash"></i>';
            }
        });
    }
}

const grabarAudioYEnviar = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mediaRecorder = new MediaRecorder(stream);
  const chunks = [];

  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: 'audio/mp3' });
    const formData = new FormData();
    formData.append("audio", blob, "grabacion.mp3");

    const response = await fetch("/api/tickets/voz", {
      method: "POST",
      body: formData
    });

    const data = await response.json();
    alert(JSON.stringify(data));
  };

  mediaRecorder.start();
  setTimeout(() => mediaRecorder.stop(), 5000); // 5 segundos
};
