import asyncio
import os
import dotenv
import json

from fastmcp import Client
from openai import OpenAI

dotenv.load_dotenv()

# Token de GitHub
token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"

# Cliente IA (GitHub Models)
ai = OpenAI(
    base_url=endpoint,
    api_key=token,
)

SYSTEM_PROMPT = """
Eres un asistente escolar.

Si el usuario pregunta por:
- tareas
- trabajos
- asignaciones
- classroom
- lo que ha puesto un profesor

responde SOLO con esta palabra exacta:
CALL_CLASSROOM

Si no, responde normalmente.
"""

async def main():
    mcp = Client("main.py")

    async with mcp:
        print("IA lista. Escribe preguntas.\n")

        while True:
            user_input = input("> ").strip()

            if not user_input:
                continue

            # 1️⃣ Preguntamos a la IA
            response = ai.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
            )

            answer = response.choices[0].message.content.strip()

            # 2️⃣ ¿La IA quiere llamar Classroom?
            if answer == "CALL_CLASSROOM":
                try:
                    result = await mcp.call_tool("get_tasks", {})
                except Exception as e:
                    print("Error llamando a Classroom:", e)
                    continue

                # Unwrap possible CallToolResult or wrapper objects into Python types
                def unwrap_tool_result(obj):
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
                        return json.loads(str(obj))
                    except Exception:
                        return [str(obj)]

                result = unwrap_tool_result(result)

                # 3️⃣ Prepare a compact payload (titles, due dates, short descs)
                def format_tasks(items, max_items=25, max_chars=6000):
                    compact = []
                    if isinstance(items, dict):
                        items = [items]
                    for t in (items or [])[:max_items]:
                        if not isinstance(t, dict):
                            continue
                        compact.append({
                            "title": t.get("title") or t.get("name") or t.get("summary"),
                            "description": (t.get("description") or t.get("details") or "")[:300],
                            "due": t.get("dueDate") or t.get("due") or t.get("dueDateTime"),
                            "courseId": t.get("courseId"),
                        })
                    s = json.dumps(compact, ensure_ascii=False)
                    if len(s) > max_chars:
                        s = s[:max_chars]
                    return s

                payload = format_tasks(result)

                system_msg = "Resume y explica estas tareas de forma clara. Si falta información, indica qué falta."

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
                        payload = format_tasks(result, max_items=5, max_chars=2000)
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
