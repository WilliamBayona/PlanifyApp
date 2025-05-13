document.addEventListener('DOMContentLoaded', function() {
  // Botones para crear rutinas
  const universityBtn = document.getElementById('createUniversityRoutine');
  const workBtn = document.getElementById('createWorkRoutine');
  const weekendBtn = document.getElementById('createWeekendRoutine');
  const deleteBtn = document.getElementById('deleteAllEvents');
  const statusElement = document.getElementById('status');

  // Rutina universitaria (lunes a viernes)
  const universityRoutine = [
    { name: 'Dormir', start: '23:00', end: '06:30', days: [0, 1, 2, 3, 4], color: '9' },
    { name: 'Desayuno', start: '06:45', end: '07:15', days: [0, 1, 2, 3, 4], color: '5' },
    { name: 'Transporte a la U', start: '07:30', end: '08:30', days: [0, 1, 2, 3, 4], color: '6' },
    { name: 'Almuerzo', start: '12:00', end: '13:00', days: [0, 1, 2, 3, 4], color: '4' },
    { name: 'Transporte a casa', start: '18:00', end: '19:00', days: [0, 1, 2, 3, 4], color: '6' },
    { name: 'Cena', start: '20:00', end: '20:30', days: [0, 1, 2, 3, 4], color: '4' }
  ];
  
  // Rutina de trabajo (lunes a viernes)
  const workRoutine = [
    { name: 'Dormir', start: '23:30', end: '07:00', days: [0, 1, 2, 3, 4], color: '9' },
    { name: 'Desayuno', start: '07:15', end: '07:45', days: [0, 1, 2, 3, 4], color: '5' },
    { name: 'Transporte al trabajo', start: '08:00', end: '09:00', days: [0, 1, 2, 3, 4], color: '6' },
    { name: 'Almuerzo', start: '13:00', end: '14:00', days: [0, 1, 2, 3, 4], color: '4' },
    { name: 'Transporte a casa', start: '18:30', end: '19:30', days: [0, 1, 2, 3, 4], color: '6' },
    { name: 'Cena', start: '20:30', end: '21:00', days: [0, 1, 2, 3, 4], color: '4' }
  ];
  
  // Rutina de fin de semana (sábado y domingo)
  const weekendRoutine = [
    { name: 'Dormir', start: '00:30', end: '09:00', days: [5, 6], color: '9' },
    { name: 'Desayuno/Brunch', start: '09:30', end: '10:30', days: [5, 6], color: '5' },
    { name: 'Actividad recreativa', start: '15:00', end: '18:00', days: [5, 6], color: '3' },
    { name: 'Cena', start: '20:30', end: '22:00', days: [5, 6], color: '4' }
  ];

  // Manejar clic en botón de rutina universitaria
  if (universityBtn) {
    universityBtn.addEventListener('click', async function() {
      await createRoutine(universityRoutine, 'universitaria');
    });
  }
  
  // Manejar clic en botón de rutina de trabajo
  if (workBtn) {
    workBtn.addEventListener('click', async function() {
      await createRoutine(workRoutine, 'de trabajo');
    });
  }
  
  // Manejar clic en botón de rutina de fin de semana
  if (weekendBtn) {
    weekendBtn.addEventListener('click', async function() {
      await createRoutine(weekendRoutine, 'de fin de semana');
    });
  }
  
  // Manejar clic en botón de borrar eventos
  if (deleteBtn) {
    deleteBtn.addEventListener('click', async function() {
      if (!confirm('¿Estás seguro de que quieres borrar TODOS los eventos creados por Planify? Esta acción no se puede deshacer.')) {
        return;
      }
      
      try {
        showStatus('Eliminando eventos...', 'loading');
        
        const response = await fetch('/delete-all-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        const result = await response.json();
        
        if (result.success) {
          showStatus(result.message, 'success');
        } else {
          showStatus(result.message, 'error');
        }
      } catch (error) {
        console.error('Error:', error);
        showStatus(`Error: ${error.message}`, 'error');
      }
    });
  }

  // Función para crear una rutina completa
  async function createRoutine(routineEvents, routineType) {
    try {
      showStatus(`Creando rutina ${routineType}...`, 'loading');
      
      let createdCount = 0;
      let errorCount = 0;
      
      // Crear cada evento de la rutina
      for (const event of routineEvents) {
        const response = await fetch('/create-generic-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name: event.name,
            start_time: event.start,
            end_time: event.end,
            days: event.days,
            color: event.color
          })
        });
        
        const result = await response.json();
        
        if (result.success) {
          createdCount++;
        } else {
          errorCount++;
          console.error(`Error en evento ${event.name}:`, result.message);
        }
      }
      
      if (errorCount === 0) {
        showStatus(`Rutina ${routineType} creada con éxito. Se crearon ${createdCount} eventos.`, 'success');
      } else {
        showStatus(`Rutina creada parcialmente. ${createdCount} eventos creados, ${errorCount} errores.`, 'warning');
      }
    } catch (error) {
      console.error('Error:', error);
      showStatus(`Error: ${error.message}`, 'error');
    }
  }

  // Función para mostrar mensajes de estado
  function showStatus(message, type) {
    if (!statusElement) return;
    
    statusElement.textContent = message;
    statusElement.className = 'status-message';
    
    switch (type) {
      case 'success':
        statusElement.classList.add('status-success');
        break;
      case 'error':
        statusElement.classList.add('status-error');
        break;
      case 'warning':
        statusElement.classList.add('status-warning');
        break;
      case 'loading':
        statusElement.classList.add('status-loading');
        break;
    }
    
    statusElement.style.display = 'block';
    
    if (type !== 'loading') {
      setTimeout(() => {
        statusElement.style.display = 'none';
      }, 7000);
    }
  }
});