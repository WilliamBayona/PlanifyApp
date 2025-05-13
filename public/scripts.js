console.log("Prototipo cargado correctamente");

// Espera a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
  // Ahora es seguro acceder a los elementos del DOM
  const exportToCalendarElement = document.getElementById("exportToCalendar");
  const planFormElement = document.getElementById("planForm");
  
  // Inicializar los controles deslizantes de parámetros
  const gamma1Slider = document.getElementById('gamma1');
  const gamma2Slider = document.getElementById('gamma2');
  const gamma3Slider = document.getElementById('gamma3');
  
  if (gamma1Slider) {
    gamma1Slider.addEventListener('input', function() {
      document.getElementById('gamma1Value').textContent = this.value;
    });
  }
  
  if (gamma2Slider) {
    gamma2Slider.addEventListener('input', function() {
      document.getElementById('gamma2Value').textContent = this.value;
    });
  }
  
  if (gamma3Slider) {
    gamma3Slider.addEventListener('input', function() {
      document.getElementById('gamma3Value').textContent = this.value;
    });
  }
  
  if (exportToCalendarElement) {
    exportToCalendarElement.addEventListener("change", function() {
      document.getElementById("startDateContainer").style.display = this.checked ? "block" : "none";
    });
  }
  
  // Función para agregar una nueva tarea al formulario
  window.addTask = function() {
    const tasksContainer = document.getElementById('tasks-container');
    const taskId = document.querySelectorAll('.task-item').length + 1;
    
    const taskHTML = `
      <div class="task-item" data-task-id="${taskId}">
        <h3>Tarea ${taskId}</h3>
        <div class="form-group">
          <label for="nombre${taskId}">Nombre:</label>
          <input type="text" id="nombre${taskId}" name="nombre" required>
        </div>
        <div class="form-group">
          <label for="materia${taskId}">Materia:</label>
          <input type="text" id="materia${taskId}" name="materia" required onchange="updateSubjects()">
        </div>
        <div class="form-group">
          <label for="peso${taskId}">Peso (0-1):</label>
          <input type="number" id="peso${taskId}" name="peso" min="0" max="1" step="0.01" value="0.3" required>
        </div>
        <div class="form-group">
          <label for="deadline${taskId}">Deadline:</label>
          <input type="datetime-local" id="deadline${taskId}" name="deadline" required>
        </div>
        <div class="form-group">
          <label for="creditos${taskId}">Créditos de la materia:</label>
          <input type="number" id="creditos${taskId}" name="creditos" min="1" max="6" value="3" onchange="updateSubjects()">
        </div>
        <button type="button" class="remove-task" onclick="removeTask(${taskId})">Eliminar</button>
      </div>
    `;
    
    // Agregar el HTML al contenedor
    tasksContainer.insertAdjacentHTML('beforeend', taskHTML);
    
    // Establecer fecha/hora mínima para el deadline (ahora)
    const deadlineInput = document.getElementById(`deadline${taskId}`);
    const now = new Date();
    const localISOTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    deadlineInput.value = localISOTime;
    deadlineInput.min = localISOTime;
    
    // Actualizar la lista de materias
    updateSubjects();
  }
  
  // Función para eliminar una tarea
  window.removeTask = function(taskId) {
    const taskElement = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
    if (taskElement) {
      taskElement.remove();
      updateSubjects();
    }
  }
  
  // Función para actualizar la lista de materias
  window.updateSubjects = function() {
    const subjectsContainer = document.getElementById('subjects-container');
    if (!subjectsContainer) return;
    
    // Obtener materias únicas
    const subjects = new Map();
    document.querySelectorAll('.task-item').forEach(taskElement => {
      const materia = taskElement.querySelector('[name="materia"]').value;
      const creditos = parseInt(taskElement.querySelector('[name="creditos"]').value || "3");
      
      if (materia && !subjects.has(materia)) {
        subjects.set(materia, creditos);
      }
    });
    
    // Limpiar el contenedor
    subjectsContainer.innerHTML = '';
    
    // Si no hay materias, no hacer nada más
    if (subjects.size === 0) return;
    
    // Crear un elemento para cada materia
    subjects.forEach((creditos, materia) => {
      const subjectHTML = `
        <div class="subject-item" data-subject="${materia}">
          <h4>${materia} (${creditos} créditos)</h4>
          <div class="form-group">
            <label for="alpha_${materia}">Tiempo esperado (h/semana):</label>
            <input type="number" id="alpha_${materia}" name="alpha-value" min="1" value="${3 * creditos}" step="0.5">
            <input type="hidden" name="subject-name" value="${materia}">
          </div>
          <p class="min-time-info">Tiempo mínimo: ${Math.max(0, 3 * creditos - 3)} h/semana</p>
        </div>
      `;
      
      subjectsContainer.insertAdjacentHTML('beforeend', subjectHTML);
    });
  }
  
  // Función para obtener las tareas del formulario
  function getTasksFromForm() {
    const taskElements = document.querySelectorAll('.task-item');
    const tareas = [];
    
    taskElements.forEach(taskElement => {
      const nombre = taskElement.querySelector('[name="nombre"]').value;
      const materia = taskElement.querySelector('[name="materia"]').value;
      const peso = parseFloat(taskElement.querySelector('[name="peso"]').value);
      const deadlineStr = taskElement.querySelector('[name="deadline"]').value;
      const creditos = parseInt(taskElement.querySelector('[name="creditos"]').value || "3");
      
      if (nombre && materia && !isNaN(peso) && deadlineStr) {
        const deadline = new Date(deadlineStr);
        
        tareas.push({
          nombre,
          materia,
          peso,
          deadline,
          creditos
        });
      }
    });
    
    return tareas;
  }
  
  // Función para obtener los valores de alpha (tiempo por materia)
  function getAlphaValues() {
    const alpha = {};
    document.querySelectorAll('.subject-item').forEach(element => {
      const materia = element.getAttribute('data-subject');
      const valor = parseFloat(element.querySelector('[name="alpha-value"]').value);
      
      if (materia && !isNaN(valor)) {
        alpha[materia] = valor;
      }
    });
    
    return alpha;
  }
  
  // Manejo del envío del formulario
  if (planFormElement) {
    planFormElement.addEventListener("submit", async function (e) {
      e.preventDefault();
      
      // Mostrar indicador de carga
      const loadingElement = document.getElementById('loading');
      if (loadingElement) loadingElement.style.display = 'block';
      
      // Obtener las tareas del formulario
      const tareas = getTasksFromForm();
      
      if (tareas.length === 0) {
        alert("Por favor, ingresa al menos una tarea para planificar");
        if (loadingElement) loadingElement.style.display = 'none';
        return;
      }
      
      // Obtener la fecha de inicio
      const startDate = document.getElementById("startDate").value || null;
      
      // Obtener valores gamma (si tienes sliders para esto)
      const gamma1 = parseFloat(document.getElementById("gamma1")?.value || "1.0");
      const gamma2 = parseFloat(document.getElementById("gamma2")?.value || "0.1");
      const gamma3 = parseFloat(document.getElementById("gamma3")?.value || "0.5");
      
      // Obtener alpha (tiempo por materia)
      const alpha = getAlphaValues();
      
      const payload = { 
        tareas,
        alpha,
        beta: {},  // Por ahora vacío, implementar si es necesario
        start_date: startDate,
        gamma1, 
        gamma2,
        gamma3
      };
    
      try {
        const response = await fetch('/planificar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload)
        });
        
        // Ocultar indicador de carga
        if (loadingElement) loadingElement.style.display = 'none';
        
        if (!response.ok) {
          throw new Error(`Error HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Resultado:', result);
        
        // Actualizar la UI con el resultado
        displaySchedule(result);
        
        // Mostrar mensaje sobre la exportación al calendario
        if (result.calendar_status && result.calendar_status.success) {
          alert(`Los eventos han sido creados exitosamente en tu Google Calendar. ${result.calendar_status.message}`);
        } else if (result.calendar_status) {
          alert(`Hubo un problema al exportar a Google Calendar: ${result.calendar_status.message}`);
        }
        
      } catch (error) {
        // Ocultar indicador de carga en caso de error
        if (loadingElement) loadingElement.style.display = 'none';
        console.error('Error:', error);
        alert(`Error: ${error.message}`);
      }
    });
  } else {
    console.error('No se encontró el formulario de planificación');
  }
  
  // Agregar una tarea inicial al cargar la página
  if (document.getElementById('tasks-container')) {
    window.addTask();
  }
});

function displaySchedule(result) {
  // Implementar la lógica para mostrar el horario en la interfaz
  const scheduleDiv = document.getElementById('schedule-results');
  if (!scheduleDiv) return;
  
  if (result.estado === 'Optimal') {
    // Ordenar las tareas por materia para mejor visualización
    result.plan.sort((a, b) => a.materia.localeCompare(b.materia));
    
    let html = '<h2>Plan de Estudio Optimizado</h2>';
    
    // Agrupar por materia
    const materiaGroups = {};
    for (const task of result.plan) {
      if (!materiaGroups[task.materia]) {
        materiaGroups[task.materia] = [];
      }
      materiaGroups[task.materia].push(task);
    }
    
    // Mostrar estadísticas generales
    html += '<div class="stats-summary">';
    html += `<div class="stat"><strong>Tareas planificadas:</strong> ${result.plan.length}</div>`;
    
    // Contar bloques totales
    let totalBloques = 0;
    for (const task of result.plan) {
      totalBloques += task.bloques.length;
    }
    html += `<div class="stat"><strong>Bloques asignados:</strong> ${totalBloques}</div>`;
    html += `<div class="stat"><strong>Horas de estudio:</strong> ${(totalBloques * 0.5).toFixed(1)}h</div>`;
    html += '</div>';
    
    // Mostrar el horario por materia
    html += '<div class="schedule-by-subject">';
    
    for (const materia in materiaGroups) {
      const tasks = materiaGroups[materia];
      
      html += `
        <div class="subject-schedule">
          <h3>${materia}</h3>
          <div class="subject-tasks">
      `;
      
      let materiaBloques = 0;
      for (const task of tasks) {
        materiaBloques += task.bloques.length;
        
        // Ordenar los bloques para mejor visualización
        const bloques = [...task.bloques].sort((a, b) => a - b);
        
        // Convertir bloques a formato legible
        const bloquesFormatted = bloques.map(convertBlockToTimeString).join(', ');
        
        html += `
          <div class="task-card">
            <h4>${task.tarea}</h4>
            <div class="task-progress">
              <div class="progress-bar" style="width: ${task.progreso * 100}%"></div>
              <span>${(task.progreso * 100).toFixed(0)}%</span>
            </div>
            <p><strong>Tiempo asignado:</strong> ${(bloques.length * 0.5).toFixed(1)}h</p>
            <p><strong>Bloques:</strong> ${bloquesFormatted}</p>
          </div>
        `;
      }
      
      html += `
          </div>
          <div class="subject-summary">
            <p><strong>Total ${materia}:</strong> ${(materiaBloques * 0.5).toFixed(1)} horas</p>
          </div>
        </div>
      `;
    }
    
    html += '</div>';
    
    // Mostrar vista de calendario semanal
    html += '<h3>Vista de Calendario</h3>';
    html += generateCalendarView(result.plan);
    
    scheduleDiv.innerHTML = html;
  } else {
    scheduleDiv.innerHTML = `
      <div class="error-message">
        <h3>No se pudo encontrar una solución óptima</h3>
        <p>Estado: ${result.estado}</p>
        <p>${result.mensaje || 'Intente modificar los parámetros o reducir restricciones'}</p>
      </div>
    `;
  }
}

// Función auxiliar para convertir un bloque a formato de hora
function convertBlockToTimeString(block) {
  const day = Math.floor(block / 48);  // 48 bloques por día (30 min cada uno)
  const dayNames = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
  
  const timeBlock = block % 48;  // Bloque dentro del día
  
  // Cada día comienza a las 00:00
  const hour = Math.floor(timeBlock / 2);  // Sin offset, 00:00 es el primer bloque
  const minute = (timeBlock % 2) * 30;
  
  // Formato de 12 horas con AM/PM
  const ampm = hour < 12 ? 'AM' : 'PM';
  const hour12 = hour % 12 || 12;  // Convertir 0 a 12 para medianoche
  
  return `${dayNames[day]} ${hour12}:${minute === 0 ? '00' : minute} ${ampm}`;
}

// Función para generar vista de calendario
function generateCalendarView(plan) {
  const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
  let html = '<div class="calendar-view">';
  
  // Encabezados de los días
  html += '<div class="calendar-row header">';
  html += '<div class="calendar-time-column">Hora</div>';
  days.forEach(day => {
    html += `<div class="calendar-day-column">${day}</div>`;
  });
  html += '</div>';
  
  // Crear una matriz de bloques ocupados
  const occupiedBlocks = {};
  for (const task of plan) {
    for (const block of task.bloques) {
      occupiedBlocks[block] = {
        task: task.tarea,
        materia: task.materia
      };
    }
  }
  
  // Generar filas por hora (24 horas completas, empezando a las 00:00)
  for (let hour = 0; hour < 24; hour++) {
    const ampm = hour < 12 ? 'AM' : 'PM';
    const displayHour = hour % 12 || 12;  // Convertir 0 a 12
    
    html += `<div class="calendar-row">`;
    html += `<div class="calendar-time-column">${displayHour} ${ampm}</div>`;
    
    // Para cada día (7 días)
    for (let day = 0; day < 7; day++) {
      // Dos bloques por hora (00 y 30)
      const block1 = day * 48 + hour * 2;        // Primer bloque (hora:00)
      const block2 = block1 + 1;                 // Segundo bloque (hora:30)
      
      html += `<div class="calendar-day-column">`;
      
      // Primer bloque (hora:00)
      if (occupiedBlocks[block1]) {
        html += `<div class="calendar-block occupied" style="background-color: ${getColorFromString(occupiedBlocks[block1].materia)}">
          ${occupiedBlocks[block1].task}
        </div>`;
      } else {
        html += `<div class="calendar-block">:00</div>`;
      }
      
      // Segundo bloque (hora:30)
      if (occupiedBlocks[block2]) {
        html += `<div class="calendar-block occupied" style="background-color: ${getColorFromString(occupiedBlocks[block2].materia)}">
          ${occupiedBlocks[block2].task}
        </div>`;
      } else {
        html += `<div class="calendar-block">:30</div>`;
      }
      
      html += `</div>`;
    }
    
    html += `</div>`;
  }
  
  html += '</div>';
  return html;
}

// Función para generar un color basado en el nombre de la materia
function getColorFromString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  const c = (hash & 0x00FFFFFF)
    .toString(16)
    .toUpperCase()
    .padStart(6, '0');
  
  // Ajustar transparencia para no hacer el texto ilegible
  return `#${c}80`;  // 80 es 50% de opacidad en hex
}

// Funcionalidad para eventos genéricos
document.addEventListener('DOMContentLoaded', function() {
  const createGenericEventBtn = document.getElementById('createGenericEvent');
  const deleteAllEventsBtn = document.getElementById('deleteAllEvents');
  const statusElement = document.getElementById('genericEventStatus');
  
  if (createGenericEventBtn) {
    createGenericEventBtn.addEventListener('click', async function() {
      // Validar campos
      const name = document.getElementById('genericEventName').value;
      const startTime = document.getElementById('genericStartTime').value;
      const endTime = document.getElementById('genericEndTime').value;
      const colorId = document.getElementById('genericEventColor').value;
      
      // Obtener días seleccionados
      const days = [];
      for (let i = 0; i <= 6; i++) {
        const checkbox = document.getElementById(`day${i}`);
        if (checkbox && checkbox.checked) {
          days.push(parseInt(checkbox.value));
        }
      }
      
      // Validar datos
      if (!name) {
        showStatus('Debes ingresar un nombre para el evento', false);
        return;
      }
      
      if (!startTime || !endTime) {
        showStatus('Debes especificar hora de inicio y fin', false);
        return;
      }
      
      if (days.length === 0) {
        showStatus('Selecciona al menos un día de la semana', false);
        return;
      }
      
      // Obtener fecha de inicio si existe
      const startDateInput = document.getElementById('startDate');
      const startDate = startDateInput ? startDateInput.value : null;
      
      try {
        // Mostrar indicador de carga
        showStatus('Creando eventos...', true, 'loading');
        
        const response = await fetch('/create-generic-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name,
            start_time: startTime,
            end_time: endTime,
            days,
            color: colorId,
            start_date: startDate
          })
        });
        
        const result = await response.json();
        
        if (result.success) {
          showStatus(result.message, true);
        } else {
          showStatus(result.message, false);
        }
      } catch (error) {
        console.error('Error:', error);
        showStatus(`Error: ${error.message}`, false);
      }
    });
  }
  
  if (deleteAllEventsBtn) {
    deleteAllEventsBtn.addEventListener('click', async function() {
      if (!confirm('¿Estás seguro de que quieres borrar TODOS los eventos creados por Planify? Esta acción no se puede deshacer.')) {
        return;
      }
      
      try {
        // Mostrar indicador de carga
        showStatus('Eliminando eventos...', true, 'loading');
        
        const response = await fetch('/delete-all-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        const result = await response.json();
        
        if (result.success) {
          showStatus(result.message, true);
        } else {
          showStatus(result.message, false);
        }
      } catch (error) {
        console.error('Error:', error);
        showStatus(`Error: ${error.message}`, false);
      }
    });
  }
  
  function showStatus(message, isSuccess, type = '') {
    if (!statusElement) return;
    
    statusElement.textContent = message;
    statusElement.classList.remove('status-success', 'status-error', 'status-loading');
    
    if (type === 'loading') {
      statusElement.classList.add('status-loading');
    } else {
      statusElement.classList.add(isSuccess ? 'status-success' : 'status-error');
    }
    
    statusElement.style.display = 'block';
    
    // Ocultar mensaje después de 5 segundos si no es de carga
    if (type !== 'loading') {
      setTimeout(() => {
        statusElement.style.display = 'none';
      }, 5000);
    }
  }
});