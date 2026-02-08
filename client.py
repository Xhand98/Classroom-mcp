import asyncio
import os
import dotenv
import json

from fastmcp import Client
from openai import OpenAI
from toon_python import encode

dotenv.load_dotenv()

# Token de GitHub
token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"

# Cliente IA (GitHub Models)
ai = OpenAI(
    base_url=endpoint,
    api_key=token,
)

SYSTEM_PROMPT = """Eres un asistente que determina si una pregunta está relacionada con tareas escolares o Google Classroom.

Si el usuario pregunta CUALQUIER COSA relacionada con:
- tareas, trabajos, asignaciones, deberes, actividades
- classroom, clases, cursos
- profesores y sus tareas
- fechas de entrega
- qué hay que hacer/entregar
- pendientes escolares

Responde ÚNICAMENTE con la palabra: CALL_CLASSROOM

Para CUALQUIER otra pregunta que NO sea sobre tareas/classroom, responde normalmente.

Ejemplos:
Usuario: "Que tareas hay de Jose Luis?" → CALL_CLASSROOM
Usuario: "Cuáles son mis tareas pendientes?" → CALL_CLASSROOM  
Usuario: "Qué tiempo hace hoy?" → Respuesta normal
Usuario: "Hola, cómo estás?" → Respuesta normal
"""

# Caché global de cursos y tareas
COURSES_CACHE = {}
TASKS_BY_COURSE = {}

def find_course_by_name(query: str, courses_dict: dict) -> list:
    """Busca cursos por nombre (fuzzy match)"""
    query = query.lower().strip()
    matches = []
    
    for course_id, course_info in courses_dict.items():
        course_name = course_info.get('name', '').lower()
        
        # Exact match
        if query == course_name:
            return [course_id]
        
        # Contains match
        if query in course_name or course_name in query:
            matches.append(course_id)
    
    # También buscar por palabras clave
    keywords = {
        'ingles': ['english', 'inglés', 'ingles'],
        'español': ['español', 'espanol', 'lengua española', 'lengua'],
        'matematicas': ['matemáticas', 'matematicas', 'math'],
        'ciencias': ['ciencias sociales', 'ciencias', 'sociales'],
        'informatica': ['informática', 'informatica', 'tecnología', 'tecnologia'],
    }
    
    for key, terms in keywords.items():
        if any(term in query for term in terms):
            for course_id, course_info in courses_dict.items():
                course_name = course_info.get('name', '').lower()
                if any(term in course_name for term in terms):
                    if course_id not in matches:
                        matches.append(course_id)
    
    return matches

# Unwrap function - definida antes para usarla múltiples veces
def unwrap_tool_result(obj):
    # Si es un CallToolResult de FastMCP
    if hasattr(obj, 'content'):
        content = obj.content
        if isinstance(content, list) and len(content) > 0:
            first = content[0]
            # TextContent tiene .text
            if hasattr(first, 'text'):
                import json
                try:
                    return json.loads(first.text)
                except:
                    return first.text
            return first
        return content
    
    # direct types
    if obj is None:
        return []
    if isinstance(obj, (list, dict)):
        return obj
    
    # common attribute names
    for attr in ("value", "result", "data", "payload"):
        if hasattr(obj, attr):
            try:
                v = getattr(obj, attr)
                if isinstance(v, (list, dict)):
                    return v
                obj = v
            except Exception:
                pass
    
    # to_dict support
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    
    # iterable (but not string)
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        try:
            return list(obj)
        except Exception:
            pass
    
    # fallback: try JSON parse of string representation
    try:
        import json
        return json.loads(str(obj))
    except Exception:
        return [str(obj)]

async def main():
    mcp = Client("main.py")

    async with mcp:
        print("IA lista. Escribe preguntas.\n")

        while True:
            user_input = input("> ").strip()

            if not user_input:
                continue
            
            # Salir
            if user_input.lower() in ['salir', 'exit', 'quit']:
                print("¡Hasta luego!")
                break

            # 1️⃣ Preguntamos a la IA si necesita classroom
            response = ai.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1,
            )

            answer = response.choices[0].message.content.strip()

            # 2️⃣ ¿La IA quiere llamar Classroom?
            if "CALL_CLASSROOM" in answer.upper():
                
                global COURSES_CACHE, TASKS_BY_COURSE
                
                try:
                    # Primero obtener/actualizar caché de cursos
                    if not COURSES_CACHE:
                        print("\n📚 Consultando tus cursos de Google Classroom...")
                        courses_result = await mcp.call_tool("getCourses", {})
                        courses_data = unwrap_tool_result(courses_result)
                        
                        if isinstance(courses_data, list):
                            for course in courses_data:
                                if isinstance(course, dict):
                                    cid = str(course.get('id'))
                                    COURSES_CACHE[cid] = course
                        
                        print(f"   ✓ {len(COURSES_CACHE)} cursos encontrados\n")
                    
                    # Buscar si el usuario menciona un curso específico
                    course_filter = find_course_by_name(user_input, COURSES_CACHE)
                    
                    if course_filter:
                        course_names = [COURSES_CACHE[cid].get('name') for cid in course_filter]
                        print(f"🎯 Buscando tareas de: {', '.join(course_names)}")
                        # Obtener solo tareas de esos cursos
                        all_tasks = []
                        for cid in course_filter:
                            course_name = COURSES_CACHE[cid].get('name', 'Sin nombre')
                            
                            # Verificar si ya tenemos en caché
                            if cid not in TASKS_BY_COURSE:
                                print(f"   📖 Cargando {course_name}...")
                                # getClases espera un dict con key "courses"
                                tasks_result = await mcp.call_tool("getClases", {"courses": [COURSES_CACHE[cid]]})
                                tasks_data = unwrap_tool_result(tasks_result)
                                TASKS_BY_COURSE[cid] = tasks_data if isinstance(tasks_data, list) else []
                            
                            # Agregar courseName a cada tarea
                            for task in TASKS_BY_COURSE[cid]:
                                if isinstance(task, dict):
                                    task['courseName'] = course_name
                                    all_tasks.append(task)
                        
                        result = all_tasks
                        print(f"   ✓ {len(result)} tareas encontradas\n")
                    
                    else:
                        # No hay filtro, obtener todas las tareas
                        print("\n📚 Obteniendo todas tus tareas...")
                        result = await mcp.call_tool("get_tasks", {})
                        result = unwrap_tool_result(result)
                        
                        # Agregar nombre del curso
                        if isinstance(result, list):
                            for task in result:
                                if isinstance(task, dict):
                                    cid = str(task.get('courseId', ''))
                                    task['courseName'] = COURSES_CACHE.get(cid, {}).get('name', f'Curso {cid}')
                        
                        print(f"   ✓ {len(result) if isinstance(result, list) else 0} tareas encontradas\n")
                    
                    
                except Exception as e:
                    print(f"\n❌ Ups! Algo salió mal: {e}\n")
                    continue

                # Si no hay tareas
                if not result or (isinstance(result, list) and len(result) == 0):
                    print("📭 No encontré tareas aquí")
                    print("   ¿Seguro que tienes tareas en ese curso?\n")
                    continue

                # 3️⃣ Preparar payload optimizado con TOON
                def format_tasks(items, max_items=100, max_chars=None):
                    compact = []
                    if isinstance(items, dict):
                        items = [items]
                    
                    for t in (items or [])[:max_items]:
                        if not isinstance(t, dict):
                            continue
                        task_info = {
                            "courseName": t.get("courseName", "Sin curso"),
                            "title": t.get("title") or t.get("name") or "Sin título",
                            "description": (t.get("description") or "")[:200],
                            "dueDate": t.get("dueDate"),
                        }
                        # Limpiar None
                        task_info = {k: v for k, v in task_info.items() if v}
                        compact.append(task_info)
                    
                    # Usar TOON en lugar de JSON (30-60% menos tokens!)
                    result_toon = encode(compact)
                    
                    # Si hay límite de caracteres y se excede
                    if max_chars and len(result_toon) > max_chars:
                        # Reducir items
                        compact = compact[:max(1, max_items // 2)]
                        result_toon = encode(compact)
                    
                    return result_toon

                payload = format_tasks(result, max_items=30)
                
                print(f"🤖 Analizando {len(result)} tareas...\n")

                system_msg = f"""Eres un asistente amigable de Google Classroom.

Usuario preguntó: "{user_input}"

Los datos están en formato TOON (Token-Oriented Object Notation) - un formato compacto similar a JSON.
Organiza y resume las tareas de forma clara y amigable. 
Si son de un curso específico, enfócate en ese.
Si son de varios cursos, agrúpalas por materia.
Usa emojis para hacerlo más divertido."""

                try:
                    followup = ai.chat.completions.create(
                        model="openai/gpt-4.1-mini",
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": payload},
                        ],
                    )
                except Exception as e:
                    # If request too large, retry with a smaller payload
                    err = str(e)
                    if "tokens_limit_reached" in err or "413" in err:
                        print("[DEBUG] Payload muy grande, reduciendo...")
                        payload = format_tasks(result, max_items=10, max_chars=3000)
                        try:
                            followup = ai.chat.completions.create(
                                model="openai/gpt-4.1-mini",
                                messages=[
                                    {"role": "system", "content": system_msg},
                                    {"role": "user", "content": payload},
                                ],
                            )
                        except Exception as e2:
                            print("Error llamando a la IA tras recorte:", e2)
                            continue
                    else:
                        print("Error llamando a la IA:", e)
                        continue

                print(followup.choices[0].message.content)

            else:
                print(answer)


if __name__ == "__main__":
    asyncio.run(main())
