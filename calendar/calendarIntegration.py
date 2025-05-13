import datetime
import os.path
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Rutas absolutas para los archivos de credenciales
BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Permisos necesarios
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_credentials():
    """Obtiene credenciales válidas para usar Google Calendar API."""
    creds = None
    
    # Verificar si el archivo de credenciales existe
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Archivo de credenciales no encontrado en: {CREDENTIALS_PATH}")
        print("Por favor, sigue estos pasos para crear el archivo:")
        print("1. Ve a https://console.cloud.google.com/apis/credentials")
        print("2. Crea un proyecto si no tienes uno")
        print("3. Crea credenciales de tipo 'ID de cliente OAuth'")
        print("4. Descarga el archivo JSON y guárdalo como 'credentials.json' en la carpeta calendar/")
        return None
    
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
            
    return creds

def export_to_calendar(schedule_result, start_date=None):
    """
    Exporta los resultados al calendario con verificación de conflictos
    """
    if not schedule_result:
        return {"success": True, "message": "No hay eventos para exportar"}
    
    # Si no se especifica fecha de inicio, usar la fecha actual
    if start_date is None:
        start_date = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    
    try:
        # Obtener credenciales
        creds = get_credentials()
        if not creds:
            return {"success": False, "message": "No se pudo obtener credenciales."}
        
        service = build("calendar", "v3", credentials=creds)
        
        # Eliminar eventos antiguos de Planify para evitar duplicados
        try:
            # Buscar y eliminar eventos futuros de Planify
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                q="Tarea planificada por Planify",
                singleEvents=True,
                maxResults=1000
            ).execute()
            
            events = events_result.get('items', [])
            deleted_count = 0
            
            for event in events:
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                deleted_count += 1
            
            print(f"Se eliminaron {deleted_count} eventos antiguos")
        except Exception as e:
            print(f"Error limpiando eventos: {e}")
        
        # Crear los nuevos eventos
        created_count = 0
        skipped_count = 0
        
        for task in schedule_result:
            task_name = task["tarea"]
            task_blocks = sorted(task["bloques"])
            materia = task.get("materia", "")
            
            if not task_blocks:
                continue
                
            # Agrupar bloques consecutivos
            groups = []
            current_group = [task_blocks[0]]
            
            for i in range(1, len(task_blocks)):
                if task_blocks[i] == task_blocks[i-1] + 1:
                    current_group.append(task_blocks[i])
                else:
                    groups.append(current_group)
                    current_group = [task_blocks[i]]
            groups.append(current_group)
            
            # Crear un evento para cada grupo consecutivo
            for group in groups:
                # Calcular hora y día
                start_block = group[0]
                end_block = group[-1]
                
                day = start_block // 48
                start_block_of_day = start_block % 48
                end_block_of_day = end_block % 48
                
                start_hour = start_block_of_day // 2
                start_minute = (start_block_of_day % 2) * 30
                
                end_hour = end_block_of_day // 2
                end_minute = ((end_block_of_day % 2) + 1) * 30
                if end_minute == 60:
                    end_hour += 1
                    end_minute = 0
                
                event_date = start_date + datetime.timedelta(days=day)
                
                start_time = event_date.replace(hour=start_hour, minute=start_minute)
                end_time = event_date.replace(hour=end_hour, minute=end_minute)
                
                # ===== VERIFICACIÓN FINAL DE CONFLICTOS =====
                # Verificar que el horario esté disponible antes de crear el evento
                try:
                    freebusy = service.freebusy().query(
                        body={
                            "timeMin": start_time.isoformat() + 'Z',
                            "timeMax": end_time.isoformat() + 'Z',
                            "items": [{"id": "primary"}],
                            "timeZone": "America/Bogota"
                        }
                    ).execute()
                    
                    busy_periods = freebusy['calendars']['primary']['busy']
                    
                    # Si hay períodos ocupados que no son de "Estudio:", omitir la creación
                    has_conflicts = False
                    if busy_periods:
                        # Verificar todos los eventos en este período
                        events_in_period = service.events().list(
                            calendarId='primary',
                            timeMin=start_time.isoformat() + 'Z',
                            timeMax=end_time.isoformat() + 'Z',
                            singleEvents=True
                        ).execute().get('items', [])
                        
                        # Solo considerar conflicto si hay eventos que no son de estudio
                        for event in events_in_period:
                            if not event.get('summary', '').startswith('Estudio:'):
                                has_conflicts = True
                                print(f"Conflicto detectado con evento: {event.get('summary', '')}")
                    
                    if not has_conflicts:  # Solo crear si no hay conflictos
                        event = {
                            'summary': f"Estudio: {task_name}",
                            'description': f"Materia: {materia}\nTarea planificada por Planify. Progreso estimado: {task['progreso']*100:.1f}%",
                            'start': {
                                'dateTime': start_time.isoformat(),
                                'timeZone': 'America/Bogota',
                            },
                            'end': {
                                'dateTime': end_time.isoformat(),
                                'timeZone': 'America/Bogota',
                            },
                            'colorId': '5',  # Color azul
                            'reminders': {
                                'useDefault': False,
                                'overrides': [
                                    {'method': 'popup', 'minutes': 10}
                                ]
                            }
                        }
                        
                        try:
                            service.events().insert(calendarId='primary', body=event).execute()
                            created_count += 1
                        except Exception as e:
                            print(f"Error al crear evento: {e}")
                    else:
                        skipped_count += 1
                        print(f"Se omitió un evento por conflicto: {task_name} {start_time} - {end_time}")
                except Exception as e:
                    print(f"Error verificando conflictos: {e}")
        
        return {"success": True, "message": f"Se crearon {created_count} eventos exitosamente, se omitieron {skipped_count} eventos por conflictos"}
    
    except Exception as e:
        print(f"Error general: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}

def get_busy_slots_from_calendar(start_date=None, days=7):
    """
    Obtiene eventos existentes de Google Calendar y los convierte en bloques ocupados
    
    Args:
        start_date: Fecha de inicio para buscar eventos (si es None, usa la fecha actual)
        days: Número de días a considerar
        
    Returns:
        Lista de índices de bloques ocupados
    """
    # Si no se especifica fecha de inicio, usar el día actual
    if start_date is None:
        start_date = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    
    # Fecha de fin es start_date + days
    end_date = start_date + datetime.timedelta(days=days)
    
    busy_slots = set()  # Usar un set para evitar duplicados
    
    try:
        # Obtener credenciales y servicio
        creds = get_credentials()
        if not creds:
            print("No se pudo obtener credenciales para acceder al calendario.")
            return list(busy_slots)
        
        service = build("calendar", "v3", credentials=creds)

        # MÉTODO 1: Usar FreeBusy API (más preciso para disponibilidad)
        try:
            body = {
                "timeMin": start_date.isoformat() + 'Z',
                "timeMax": end_date.isoformat() + 'Z',
                "items": [{"id": "primary"}],
                "timeZone": "America/Bogota"
            }
            
            freebusy_result = service.freebusy().query(body=body).execute()
            busy_periods = freebusy_result['calendars']['primary']['busy']
            
            for period in busy_periods:
                # Convertir a datetime
                start = datetime.datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                
                # Convertir a hora local si es necesario
                if start.tzinfo is not None:
                    start = start.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                if end.tzinfo is not None:
                    end = end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                
                # Calcular diferencia en días desde la fecha de inicio
                start_day_diff = (start.date() - start_date.date()).days
                end_day_diff = (end.date() - start_date.date()).days
                
                # Si el evento está fuera del rango de días, ignorarlo
                if start_day_diff < 0 or start_day_diff >= days:
                    continue
                
                # Convertir a bloques
                start_block_of_day = (start.hour * 2) + (1 if start.minute >= 30 else 0)
                start_block = (start_day_diff * 48) + start_block_of_day
                
                # Para la hora de finalización, asegurar que el bloque parcial se cuente completo
                end_block_of_day = (end.hour * 2) + (1 if end.minute > 0 else 0)
                
                # Si termina en un día posterior
                if end_day_diff > start_day_diff:
                    if end_day_diff >= days:  # Si termina fuera del periodo considerado
                        end_block = (days * 48) - 1  # último bloque del periodo
                    else:
                        end_block = (end_day_diff * 48) + end_block_of_day
                else:
                    end_block = (start_day_diff * 48) + end_block_of_day
                
                # Añadir todos los bloques entre start_block y end_block
                for block in range(start_block, end_block + 1):
                    if 0 <= block < days * 48:  # Asegurar que está en el rango
                        busy_slots.add(block)
                        
            print(f"FreeBusy API: Se encontraron {len(busy_slots)} bloques ocupados")
        except Exception as e:
            print(f"Error en FreeBusy API: {e}")
        
        # MÉTODO 2: Listar eventos individuales (respaldo y para eventos que no aparecen en FreeBusy)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date.isoformat() + 'Z',
            timeMax=end_date.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        for event in events:
            # Ignorar eventos de día completo o eventos sin hora específica
            if 'dateTime' not in event['start'] or 'dateTime' not in event['end']:
                continue
                
            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
            
            # Convertir a hora local
            if start.tzinfo is not None:
                start = start.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            if end.tzinfo is not None:
                end = end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            
            # Calcular diferencia en días desde la fecha de inicio
            start_day_diff = (start.date() - start_date.date()).days
            end_day_diff = (end.date() - start_date.date()).days
            
            # Si el evento está fuera del rango, ignorarlo
            if start_day_diff < 0 or start_day_diff >= days:
                continue
            
            # Convertir a bloques
            start_block_of_day = (start.hour * 2) + (1 if start.minute >= 30 else 0)
            start_block = (start_day_diff * 48) + start_block_of_day
            
            # Para bloques de finalización, siempre redondear hacia arriba
            end_block_of_day = (end.hour * 2) + (1 if end.minute > 0 else 0)
            
            # Si termina en un día posterior
            if end_day_diff > start_day_diff:
                if end_day_diff >= days:
                    end_block = (days * 48) - 1  # último bloque
                else:
                    end_block = (end_day_diff * 48) + end_block_of_day
            else:
                end_block = (start_day_diff * 48) + end_block_of_day
            
            # Añadir todos los bloques ocupados
            for block in range(start_block, end_block + 1):
                if 0 <= block < days * 48:
                    busy_slots.add(block)

        # MÉTODO ADICIONAL: Forzar la expansión de eventos recurrentes
        try:
            recurring_events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                singleEvents=True,  # Expandir eventos recurrentes
                orderBy='startTime',
                maxResults=2500
            ).execute()
            
            recurring_events = recurring_events_result.get('items', [])
            recurring_count = 0
            
            for event in recurring_events:
                # Identificar eventos creados por Planify o eventos genéricos
                is_planify = ('description' in event and 
                             ('Tarea planificada por Planify' in event.get('description', '') or
                              'Evento genérico creado por Planify App' in event.get('description', '')))
                
                # Ignorar eventos de día completo o eventos sin hora específica
                if 'dateTime' not in event['start'] or 'dateTime' not in event['end']:
                    continue
                    
                start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                
                # Convertir a hora local
                if start.tzinfo is not None:
                    start = start.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                if end.tzinfo is not None:
                    end = end.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                
                # Calcular diferencia en días desde la fecha de inicio
                start_day_diff = (start.date() - start_date.date()).days
                end_day_diff = (end.date() - start_date.date()).days
                
                # Si el evento está fuera del rango, ignorarlo
                if start_day_diff < 0 or start_day_diff >= days:
                    continue
                
                # Convertir a bloques
                start_block_of_day = (start.hour * 2) + (1 if start.minute >= 30 else 0)
                start_block = (start_day_diff * 48) + start_block_of_day
                
                # Para bloques de finalización, siempre considerar el bloque completo
                end_block_of_day = (end.hour * 2) + (1 if end.minute > 0 else 0)
                
                # Si termina en un día posterior
                if end_day_diff > start_day_diff:
                    if end_day_diff >= days:
                        end_block = (days * 48) - 1  # último bloque
                    else:
                        end_block = (end_day_diff * 48) + end_block_of_day
                else:
                    end_block = (start_day_diff * 48) + end_block_of_day
                
                # Añadir todos los bloques ocupados
                for block in range(start_block, end_block + 1):
                    if 0 <= block < days * 48:
                        busy_slots.add(block)
                        if is_planify:
                            recurring_count += 1
            
            if recurring_count > 0:
                print(f"Detectados {recurring_count} bloques ocupados por eventos recurrentes de Planify")
        except Exception as e:
            print(f"Error al procesar eventos recurrentes: {e}")

        print(f"Total final: {len(busy_slots)} bloques ocupados en el calendario")
        
        # Verificar si algún bloque aparece solo en eventos individuales pero no en FreeBusy
        # Esto es solo para depuración
        if len(busy_slots) > 0:
            example_blocks = sorted(list(busy_slots))[:5]
            print(f"Ejemplo de bloques ocupados: {example_blocks}")
            for block in example_blocks:
                day = block // 48
                block_of_day = block % 48
                hour = block_of_day // 2
                minute = (block_of_day % 2) * 30
                print(f"  Bloque {block}: Día {day+1}, {hour:02d}:{minute:02d}")
            
        return sorted(list(busy_slots))  # Devolver una lista ordenada
        
    except HttpError as error:
        print(f"Error API de Google Calendar: {error}")
        return list(busy_slots)
    except Exception as e:
        print(f"Error inesperado al obtener eventos: {str(e)}")
        import traceback
        traceback.print_exc()
        return list(busy_slots)

def create_generic_event(name, start_time, end_time, days, color_id="10", start_date=None):
    """
    Crea eventos genéricos recurrentes en el calendario
    
    Args:
        name: Nombre del evento
        start_time: Hora de inicio en formato "HH:MM"
        end_time: Hora de fin en formato "HH:MM"
        days: Lista de días de la semana (0=Lunes, 1=Martes, ..., 6=Domingo)
        color_id: ID de color de Google Calendar
        start_date: Fecha base para los eventos
    """
    try:
        creds = get_credentials()
        if not creds:
            return {"success": False, "message": "No se pudo obtener credenciales"}
            
        service = build("calendar", "v3", credentials=creds)
        
        # Si no se proporciona fecha de inicio, usar la fecha actual
        if start_date is None:
            start_date = datetime.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
        # Convertir horas a objetos datetime
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        
        # Días de la semana en formato RFC5545 (LU,MA,MI,JU,VI,SA,DO)
        weekday_map = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
        recurrence_days = [weekday_map[day] for day in days if 0 <= day <= 6]
        
        if not recurrence_days:
            return {"success": False, "message": "Ningún día válido seleccionado"}
            
        # Crear un evento recurrente que comience en el primer día seleccionado
        # Encontrar el primer día de la semana que corresponde
        current_weekday = start_date.weekday()  # 0=Lunes, 6=Domingo
        days_to_add = 0
        
        for i in range(7):
            check_day = (current_weekday + i) % 7
            if check_day in days:
                days_to_add = i
                break
                
        event_date = start_date + datetime.timedelta(days=days_to_add)
        
        # Crear el evento base
        event_start = event_date.replace(hour=start_hour, minute=start_minute)
        event_end = event_date.replace(hour=end_hour, minute=end_minute)
        
        # Si el evento termina antes de comenzar (p.ej., dormir de 23:00 a 07:00), ajustar
        if event_end <= event_start:
            event_end = event_end + datetime.timedelta(days=1)
            
        event = {
            'summary': name,
            'description': 'Evento genérico creado por Planify App',
            'start': {
                'dateTime': event_start.isoformat(),
                'timeZone': 'America/Bogota',
            },
            'end': {
                'dateTime': event_end.isoformat(),
                'timeZone': 'America/Bogota',
            },
            'recurrence': [
                f'RRULE:FREQ=WEEKLY;BYDAY={",".join(recurrence_days)}'
            ],
            'colorId': color_id,
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 15}
                ]
            }
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        return {"success": True, "message": f"Evento creado: {event.get('htmlLink')}"}
        
    except HttpError as error:
        return {"success": False, "message": f"Error API: {error}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def delete_all_events():
    """
    Borra todos los eventos creados por la aplicación (estudios y eventos genéricos)
    """
    try:
        creds = get_credentials()
        if not creds:
            return {"success": False, "message": "No se pudo obtener credenciales"}
            
        service = build("calendar", "v3", credentials=creds)
        
        deleted_count = 0
        
        # 1. Eliminar eventos de estudio (buscar por título y descripción)
        try:
            # Buscar en el futuro (incluir eventos recurrentes)
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            # Primero buscar por título
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                q="Estudio:",
                singleEvents=False,  # Incluir eventos recurrentes
                maxResults=2500  # Máximo permitido por la API
            ).execute()
            
            events = events_result.get('items', [])
            
            for event in events:
                if "Tarea planificada por Planify" in event.get('description', ''):
                    service.events().delete(calendarId='primary', eventId=event['id']).execute()
                    deleted_count += 1
                    
            print(f"Se eliminaron {deleted_count} eventos de estudio")
        except Exception as e:
            print(f"Error al eliminar eventos de estudio: {e}")
        
        # 2. Eliminar eventos genéricos (buscar por descripción)
        try:
            generic_events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                q="Evento genérico creado por Planify App",
                singleEvents=False,  # Incluir eventos recurrentes
                maxResults=2500
            ).execute()
            
            generic_events = generic_events_result.get('items', [])
            generic_count = 0
            
            for event in generic_events:
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                deleted_count += 1
                generic_count += 1
            
            print(f"Se eliminaron {generic_count} eventos genéricos")
        except Exception as e:
            print(f"Error al eliminar eventos genéricos: {e}")
        
        # Si no se encontró ningún evento para eliminar
        if deleted_count == 0:
            return {"success": True, "message": "No se encontraron eventos para eliminar"}
            
        return {"success": True, "message": f"Se eliminaron {deleted_count} eventos exitosamente"}
        
    except HttpError as error:
        return {"success": False, "message": f"Error API: {error}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}