"""
 Planificador de estudio con programación lineal entera mixta (MILP) usando PuLP
 ------------------------------------------------------------------------------
 
 Modelo basado en variables x_{i,t} binarias (si se asigna bloque t a tarea i), yᵢ continuas (progreso relativo de la tarea).
 Alpha[materia]: tiempo esperado de dedicación por materia (en horas).
 Beta[(materia, t)]: preferencia o penalización de asignar un bloque horario a una materia.

 CÓMO USAR
 ---------
 Se puede usar como parte de una API (FastAPI).

 Considera:
 - No más de 4 bloques consecutivos.
 - Preferencias de horario.
 - Restricción de progreso (se puede cumplir parcialmente).
 - Evita solapamiento con eventos ya existentes.

 Bloques: 30 minutos. Cada día tiene 48 bloques. Una semana tiene 336 bloques (7 días).
 """

import pulp
from math import ceil
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Set, Optional
import datetime
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from ..calendar.calendarIntegration import export_to_calendar, get_busy_slots_from_calendar, create_generic_event, delete_all_events

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "public")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "public"))

@app.get("/rutinas", response_class=HTMLResponse)
async def get_routines(request: Request):
    return templates.TemplateResponse("rutinas.html", {"request": request})


@app.get("/profile", response_class=HTMLResponse)
async def get_routines(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/notifications", response_class=HTMLResponse)
async def get_routines(request: Request):
    return templates.TemplateResponse("notifications.html", {"request": request})


@app.get("/subjects", response_class=HTMLResponse)
async def get_routines(request: Request):
    return templates.TemplateResponse("subjects.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

class Tarea(BaseModel):
    nombre: str
    peso: float  # [0,1]
    deadline: datetime.datetime  # fecha y hora real de deadline
    materia: str
    creditos: int = 0

class EntradaPlan(BaseModel):
    tareas: List[Tarea]
    alpha: Dict[str, float] = {}
    beta: Dict[str, Dict[str, float]] = {}
    export_to_calendar: bool = True  # Por defecto siempre exportar a calendar
    start_date: Optional[datetime.date] = None
    gamma1: float = 1.0
    gamma2: float = 0.1
    gamma3: float = 0.5

@app.post("/planificar")
def planificar_estudio(data: EntradaPlan, background_tasks: BackgroundTasks):
    tareas = [t.dict() for t in data.tareas]

    if not tareas:
        return {"estado": "No_Tasks", "plan": [], "mensaje": "No hay tareas para planificar"}

    # Fecha base
    base_datetime = datetime.datetime.combine(data.start_date or datetime.date.today(), 
                                           datetime.time(hour=0, minute=0))
    time_slots = list(range(336))  # 336 bloques de 30 min (7 días)

    # Convertir deadlines a bloques
    for tarea in tareas:
        if not (0 <= tarea["peso"] <= 1):
            return {"estado": "Invalid_Weight", "plan": [], "mensaje": f"Peso inválido: {tarea['nombre']} {tarea['peso']}"}

        deadline = tarea["deadline"]
        if hasattr(deadline, 'tzinfo') and deadline.tzinfo is not None:
            deadline = deadline.replace(tzinfo=None)
            
        delta = deadline - base_datetime
        tarea["deadline"] = max(0, min(335, int(delta.total_seconds() // 1800)))

    # ===== DETECCIÓN DE SLOTS OCUPADOS (MEJORADO) =====
    busy_slots = set()
    
    # 1. Primera capa: Obtener eventos directamente desde Calendar API
    print("PASO 1: Obteniendo eventos desde Calendar API...")
    calendar_slots = get_busy_slots_from_calendar(base_datetime)
    busy_slots.update(calendar_slots)
    print(f"Se detectaron {len(busy_slots)} bloques ocupados desde Calendar API")
    
    # 2. Segunda capa: Verificación específica y exhaustiva de todos los eventos
    print("PASO 2: Verificación exhaustiva de todos los eventos...")
    try:
        from googleapiclient.discovery import build
        from ..calendar.calendarIntegration import get_credentials
        
        creds = get_credentials()
        if creds:
            service = build("calendar", "v3", credentials=creds)
            end_date = base_datetime + datetime.timedelta(days=7)
            
            # 2.1 Verificar usando FreeBusy API (más preciso para disponibilidad)
            try:
                body = {
                    "timeMin": base_datetime.isoformat() + 'Z',
                    "timeMax": end_date.isoformat() + 'Z',
                    "items": [{"id": "primary"}],
                    "timeZone": "America/Bogota"
                }
                
                freebusy_result = service.freebusy().query(body=body).execute()
                busy_periods = freebusy_result['calendars']['primary']['busy']
                
                print(f"FreeBusy API reporta {len(busy_periods)} períodos ocupados")
                
                for period in busy_periods:
                    # Convertir a datetime
                    start = datetime.datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                    end = datetime.datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                    
                    # Convertir a hora local si es necesario
                    if start.tzinfo is not None:
                        start = start.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    if end.tzinfo is not None:
                        end = end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    
                    # Calcular bloques ocupados y agregarlos al conjunto
                    start_day = (start.date() - base_datetime.date()).days
                    end_day = (end.date() - base_datetime.date()).days
                    
                    if 0 <= start_day < 7:
                        start_block = (start_day * 48) + (start.hour * 2) + (1 if start.minute >= 30 else 0)
                        
                        # Determinar el bloque final
                        if end_day >= 7:
                            end_block = 7 * 48 - 1  # Último bloque de la semana
                        else:
                            end_block = (end_day * 48) + (end.hour * 2) + (0 if end.minute == 0 else 1)
                        
                        # Marcar todos los bloques en este período como ocupados
                        for block in range(start_block, end_block + 1):
                            if 0 <= block < 336:
                                busy_slots.add(block)
                
                print(f"Después de FreeBusy API: {len(busy_slots)} bloques ocupados")
            except Exception as e:
                print(f"Error en FreeBusy API: {e}")
            
            # 2.2 Listado exhaustivo de todos los eventos
            print("Buscando todos los eventos en el calendario...")
            all_events = service.events().list(
                calendarId='primary',
                timeMin=base_datetime.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                singleEvents=True,  # Expandir eventos recurrentes
                maxResults=2500
            ).execute().get('items', [])
            
            print(f"Se encontraron {len(all_events)} eventos individuales en el calendario")
            
            # Procesar todos los eventos para extraer bloques ocupados
            for event in all_events:
                # Solo procesar eventos con hora específica (no todo el día)
                if 'dateTime' in event['start'] and 'dateTime' in event['end']:
                    # Extraer información del evento
                    summary = event.get('summary', 'Sin título')
                    start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    
                    # Ajustar zona horaria
                    if start.tzinfo:
                        start = start.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    if end.tzinfo:
                        end = end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    
                    # Calcular bloques ocupados
                    start_day = (start.date() - base_datetime.date()).days
                    end_day = (end.date() - base_datetime.date()).days
                    
                    if 0 <= start_day < 7:
                        # Calcular el bloque inicial
                        start_block = (start_day * 48) + (start.hour * 2)
                        if start.minute >= 30:
                            start_block += 1
                        
                        # Calcular el bloque final
                        if end_day >= 7:
                            # Si el evento termina después de la semana de planificación
                            end_block = 7 * 48 - 1  # Último bloque de la semana
                        else:
                            # Calcular bloque normal
                            end_block = (end_day * 48) + (end.hour * 2)
                            # Si hay minutos, ocupar el bloque completo
                            if end.minute > 0:
                                end_block += 1
                        
                        # Marcar bloques como ocupados
                        for block in range(start_block, end_block + 1):
                            if 0 <= block < 336:
                                busy_slots.add(block)
                                
                                # Imprimir detalles para depuración de eventos específicos
                                if "Dormir" in summary or "Transporte" in summary or "Cena" in summary or "Almuerzo" in summary:
                                    day = block // 48
                                    hour = (block % 48) // 2
                                    minute = (block % 2) * 30
                                    print(f"  Bloque {block} ocupado por '{summary}': Día {day+1}, {hour:02d}:{minute:02d}")
            
            print(f"Total final: {len(busy_slots)} bloques ocupados después de verificación")
            
            # Mostrar algunos ejemplos de bloques ocupados
            if busy_slots:
                print("Ejemplos de bloques ocupados:")
                sample_blocks = sorted(list(busy_slots))[:10]
                for block in sample_blocks:
                    day = block // 48
                    hour = (block % 48) // 2
                    minute = (block % 2) * 30
                    print(f"  Bloque {block}: Día {day+1}, {hour:02d}:{minute:02d}")
                
                # Identificar categorías de bloques ocupados por día para facilitar depuración
                for day in range(7):
                    day_blocks = [b for b in busy_slots if day * 48 <= b < (day + 1) * 48]
                    if day_blocks:
                        day_name = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][day]
                        print(f"  {day_name}: {len(day_blocks)} bloques ocupados")
    
    except Exception as e:
        print(f"Error en verificación de eventos: {e}")
        import traceback
        traceback.print_exc()

    # Configuración del modelo
    alpha = data.alpha.copy()
    for tarea in tareas:
        if tarea["materia"] not in alpha:
            alpha[tarea["materia"]] = 3 * tarea["creditos"]

    beta = {(mat, int(slot)): val for mat, d in data.beta.items() for slot, val in d.items()}

    # Resolver el modelo
    print(f"Resolviendo modelo con {len(tareas)} tareas y {len(busy_slots)} bloques ocupados...")
    model, x, y = build_schedule_model(tareas, time_slots, busy_slots, alpha, beta,
                                     gamma1=1.5, gamma2=0.1, gamma3=0.0)  # Priorizar progreso
    
    status = model.solve()
    print(f"Modelo resuelto con estado: {pulp.LpStatus[status]}")

    if status != pulp.LpStatusOptimal:
        # Intento más simple, priorizando solo el progreso
        print("Intentando con modelo más simple...")
        model, x, y = build_schedule_model(tareas, time_slots, busy_slots, alpha, {}, 
                                         gamma1=2.0, gamma2=0.0, gamma3=0.0)
        status = model.solve()
        
    if status != pulp.LpStatusOptimal:
        return {"estado": pulp.LpStatus[status], "plan": [], 
                "mensaje": "No se encontró solución. Es posible que no haya suficiente tiempo disponible."}

    # PROCESAMIENTO DE RESULTADOS CON VERIFICACIÓN ESTRICTA
    resultado = []
    
    print("Verificando resultados finales...")
    for i, tarea in enumerate(tareas):
        # Solo asignar bloques que realmente estén disponibles
        bloques_asignados = []
        for t in time_slots:
            # Triple verificación:
            # 1. ¿Existe la variable para esta combinación tarea-bloque?
            # 2. ¿El valor de la variable es 1?
            # 3. ¿El bloque NO está en la lista de ocupados?
            if (i, t) in x and x[i, t].varValue and x[i, t].varValue > 0.5 and t not in busy_slots:
                bloques_asignados.append(t)
        
        # Verificar si hay conflictos con bloques ocupados
        conflictos = [b for b in bloques_asignados if b in busy_slots]
        if conflictos:
            print(f"ALERTA: La tarea '{tarea['nombre']}' tiene {len(conflictos)} conflictos. Eliminando bloques conflictivos.")
            # Eliminar los bloques conflictivos
            bloques_asignados = [b for b in bloques_asignados if b not in busy_slots]
        
        # Solo añadir tareas que tengan bloques asignados
        if bloques_asignados:
            progreso = round(y[i].varValue, 2) if y[i].varValue is not None else 0
            
            # Ajustar el progreso si se eliminaron bloques conflictivos
            if conflictos:
                bloques_requeridos = ceil(alpha.get(tarea["materia"], 3) * tarea["peso"] * 2)
                if bloques_requeridos > 0:
                    progreso = round(len(bloques_asignados) / bloques_requeridos, 2)
            
            # Ordenar bloques para mejor visualización
            bloques_asignados.sort()
            
            resultado.append({
                "tarea": tarea["nombre"], 
                "bloques": bloques_asignados, 
                "progreso": progreso, 
                "materia": tarea["materia"]
            })
    
    # Exportar a Calendar si se solicitó, pero con verificación adicional
    if getattr(data, 'export_to_calendar', True):
        print(f"Exportando {len(resultado)} tareas al calendario...")
        calendar_result = export_to_calendar(resultado, base_datetime)
    else:
        calendar_result = {"success": True, "message": "No se exportó al calendario (desactivado)"}
    
    return {
        "estado": pulp.LpStatus[status], 
        "plan": resultado,
        "calendar_status": calendar_result,
        "busy_slots_count": len(busy_slots)
    }

@app.post("/debug_params")
def debug_params(data: EntradaPlan):
    tareas = [t.dict() for t in data.tareas]
    return {
        "num_tareas": len(tareas),
        "tareas": tareas,
        "alpha": data.alpha,
        "beta_keys": [f"{m}_{s}" for m, slots in data.beta.items() for s in slots]
    }

@app.post("/create-generic-events")
def create_generic_events(data: dict):
    """
    Crea eventos genéricos recurrentes en el calendario (como dormir, comer, etc.)
    
    Espera un JSON con:
    - name: Nombre del evento
    - start_time: Hora de inicio (HH:MM)
    - end_time: Hora de fin (HH:MM)
    - days: Lista de días de la semana (0=Lunes a 6=Domingo)
    - color: ID de color para el evento (opcional)
    - start_date: Fecha de inicio para los eventos (opcional)
    """
    try:
        name = data.get("name", "")
        start_time = data.get("start_time", "")
        end_time = data.get("end_time", "")
        days = data.get("days", [])
        color = data.get("color", "10")  # Default: verde
        start_date = data.get("start_date")
        
        # Validaciones básicas
        if not name or not start_time or not end_time or not days:
            return {"success": False, "message": "Faltan datos requeridos"}
            
        # Convertir start_date a datetime si se proporciona
        if start_date:
            base_date = datetime.datetime.fromisoformat(start_date)
        else:
            base_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Crear eventos
        result = create_generic_event(name, start_time, end_time, days, color, base_date)
        return result
        
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.post("/delete-all-events")
def delete_all_events_route():
    """
    Borra todos los eventos creados por la aplicación
    """
    try:
        result = delete_all_events()
        return result
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def build_schedule_model(tasks, time_slots, busy_slots, alpha, beta, gamma1=1.0, gamma2=0.1, gamma3=0.5):
    """
    Versión simplificada y robusta del modelo de planificación.
    Prioriza evitar conflictos y maximizar el progreso.
    """
    model = pulp.LpProblem("PlanEstudio", pulp.LpMaximize)
    x = {}  # Variable binaria para asignar bloques a tareas
    y = {}  # Variable continua para el progreso
    
    # Conjunto actualizado de slots ocupados (para verificación doble)
    busy_slots_set = set(busy_slots)
    
    # 1. Crear variables de decisión - SOLO para slots NO OCUPADOS
    print(f"Creando modelo con {len(tasks)} tareas y {len(time_slots)} slots ({len(busy_slots_set)} ocupados)")
    for i, tarea in enumerate(tasks):
        for t in time_slots:
            # Solo crear variables para slots disponibles y antes del deadline
            if t <= tarea["deadline"] and t not in busy_slots_set:
                x[i, t] = pulp.LpVariable(f"x_{i}_{t}", cat="Binary")
        # Variable de progreso para cada tarea
        y[i] = pulp.LpVariable(f"y_{i}", lowBound=0, upBound=1)
    
    print(f"Creadas {len(x)} variables de asignación y {len(y)} variables de progreso")
    
    # 2. OBJETIVO: Maximizar progreso y preferencias de horario
    model += (
        # Progreso ponderado por peso de tarea (prioridad alta)
        gamma1 * pulp.lpSum(y[i] * tasks[i]["peso"] for i in range(len(tasks))) +
        # Preferencias de horario (prioridad secundaria)
        gamma2 * pulp.lpSum(beta.get((tasks[i]["materia"], t), 1.0) * x[i, t] for (i, t) in x)
    )
    
    # 3. RESTRICCIÓN: Cada bloque solo puede tener una tarea
    for t in time_slots:
        if t not in busy_slots_set:
            model += pulp.lpSum(x.get((i, t), 0) for i in range(len(tasks))) <= 1, f"OneTask_{t}"
    
    # 4. RESTRICCIÓN: Bloques ocupados NUNCA SE PUEDEN USAR (redundante por seguridad)
    for t in busy_slots_set:
        relevant_tasks = [i for i in range(len(tasks)) if (i, t) in x]
        if relevant_tasks:  # Solo si hay variables creadas para este slot
            model += pulp.lpSum(x[i, t] for i in relevant_tasks) == 0, f"NoUse_{t}"
    
    # 5. RESTRICCIÓN: Limitar número de bloques por tarea según alpha
    for i, tarea in enumerate(tasks):
        bloques_requeridos = ceil(alpha.get(tarea["materia"], 3) * tarea["peso"] * 2)  # 2 bloques por hora
        
        # Máximo de bloques por tarea
        task_slots = [(i, t) for t in time_slots if (i, t) in x]
        if task_slots:
            model += pulp.lpSum(x[i, t] for (i, t) in task_slots) <= bloques_requeridos, f"MaxBlocks_{i}"
        
        # Intento de asignar al menos un bloque si es posible
        slots_disponibles = len([t for t in time_slots if t <= tarea["deadline"] and t not in busy_slots_set])
        if slots_disponibles > 0:
            model += pulp.lpSum(x.get((i, t), 0) for t in time_slots if (i, t) in x) >= min(1, slots_disponibles), f"MinBlocks_{i}"
        
        # Progreso proporcional a los bloques asignados
        if bloques_requeridos > 0 and any((i, t) in x for t in time_slots):
            model += y[i] == pulp.lpSum(x.get((i, t), 0) for t in time_slots if (i, t) in x) / bloques_requeridos, f"Progress_{i}"
        else:
            model += y[i] == 0, f"NoProgress_{i}"  # Si no hay variables, progreso es 0
    
    # 6. RESTRICCIÓN SIMPLIFICADA: Evitar sesiones muy largas
    for i in range(len(tasks)):
        for day in range(7):
            # Limitar a máximo 4 horas (8 bloques) por día para cada tarea
            day_start = day * 48
            day_end = (day + 1) * 48
            day_slots = [t for t in range(day_start, day_end) if (i, t) in x]
            
            if day_slots:
                model += pulp.lpSum(x[i, t] for t in day_slots) <= 8, f"MaxDaily_{i}_{day}"
    
    # 7. RESTRICCIÓN ADICIONAL: Intentar agrupar bloques contiguos
    # Esta restricción incentiva asignar bloques contiguos pero no es obligatoria
    try:
        # Variables auxiliares para identificar bloques contiguos
        # (no afecta la factibilidad, solo la optimización)
        contiguous = {}
        for i in range(len(tasks)):
            for t in range(max(time_slots) - 1):
                if (i, t) in x and (i, t+1) in x:
                    contiguous[i, t] = pulp.LpVariable(f"cont_{i}_{t}", cat="Binary")
                    model += contiguous[i, t] <= x[i, t], f"Cont1_{i}_{t}"
                    model += contiguous[i, t] <= x[i, t+1], f"Cont2_{i}_{t}"
                    model += contiguous[i, t] >= x[i, t] + x[i, t+1] - 1, f"Cont3_{i}_{t}"
        
        if contiguous:
            # Añadir término adicional al objetivo para incentivar bloques contiguos
            model += 0.2 * pulp.lpSum(contiguous.values())
    except Exception as e:
        # Si hay un error con las restricciones de contiguidad, ignorarlas
        # y continuar con el modelo básico
        print(f"Error configurando restricciones de contiguidad: {e}")
    
    return model, x, y
