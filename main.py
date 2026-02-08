import os.path
import sys
from fastmcp import FastMCP
import dotenv
dotenv.load_dotenv()

import os
from openai import OpenAI
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

mcp = FastMCP("classroom-mcp")

# If run with --authorize, perform an interactive auth flow and exit.
STANDALONE_AUTHORIZE = "--authorize" in sys.argv

token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1-mini"

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
]
isLogged = False
creds = None
service = None
courses_cache = None
cache_file = "courses_cache.json"

def auth() -> Credentials:
  global isLogged
  global creds
  global service

  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    isLogged = True

  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      print("🔄 Refrescando token...", file=sys.stderr)
      creds.refresh(Request())
      isLogged = True
    else:
      # If running as a JSON-RPC server over stdio, we must not read from stdin
      # or write human messages to stdout (it would break the protocol). Instead,
      # require the user to run the authorization flow manually with --authorize.
      if not STANDALONE_AUTHORIZE:
        print(
          "❌ Error: Falta token de autorización.",
          file=sys.stderr,
        )
        print(
          "Ejecuta: python main.py --authorize",
          file=sys.stderr,
        )
        raise RuntimeError("Authorization required; run with --authorize")

      print("🔐 Iniciando flujo de autorización de Google Classroom...", file=sys.stderr)
      print("", file=sys.stderr)
      flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
      
      # Configurar redirect_uri explícitamente
      flow.redirect_uri = flow.client_config.get('redirect_uris', ['http://localhost'])[0]
      
      # Manual console-based authorization flow (standalone only)
      try:
        auth_url, _ = flow.authorization_url(
          prompt="consent",
          access_type='offline',
          include_granted_scopes='true'
        )
        print(f"📋 Visita esta URL para autorizar:\n{auth_url}\n", file=sys.stderr)
      except Exception as e:
        print(
          f"Error generando URL: {e}",
          file=sys.stderr,
        )
        print(
          "Por favor abre tu navegador y visita la URL de autorización provista por Google OAuth.",
          file=sys.stderr,
        )

      code = input("🔑 Pega aquí el código de autorización: ").strip()
      
      if not code:
        print("❌ No se proporcionó código. Abortando.", file=sys.stderr)
        sys.exit(1)
      
      try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        isLogged = True
        print("✅ Autorización exitosa!", file=sys.stderr)
      except Exception as e:
        print(f"❌ Error al obtener token: {e}", file=sys.stderr)
        sys.exit(1)

  with open("token.json", "w") as token:
    token.write(creds.to_json())

  service = build("classroom", "v1", credentials=creds)

  return creds


def fetch_courses():
  """Internal helper: fetch courses using cache or API. Returns a list of course dicts."""
  global service, courses_cache
  if service is None:
    auth()

  if courses_cache is not None:
    return courses_cache

  if os.path.exists(cache_file):
    try:
      with open(cache_file, "r", encoding="utf-8") as f:
        courses_cache = json.load(f)
        return courses_cache
    except Exception:
      pass

  try:
    results = service.courses().list(pageSize=100).execute()
    courses = results.get("courses", [])
  except Exception:
    courses = []

  courses_cache = courses
  try:
    with open(cache_file, "w", encoding="utf-8") as f:
      json.dump(courses_cache, f, ensure_ascii=False, indent=2)
  except Exception:
    pass

  return courses_cache

@mcp.tool
def getCourses():
  # Expose as a tool but delegate to internal fetcher to avoid calling the tool wrapper
  return fetch_courses()
    
@mcp.tool
def getClases(courses):
  global service
  if service is None:
    auth()

  if isinstance(courses, dict):
    courses = [courses]
  if not isinstance(courses, list):
    raise TypeError("courses must be a dict or a list of dicts")

  all_coursework = []
  for course in courses:
    if not isinstance(course, dict):
      continue
    course_id = course.get("id")
    if not course_id:
      continue
    try:
      resp = service.courses().courseWork().list(
        courseId=str(course_id)
      ).execute()
      all_coursework.extend(resp.get("courseWork", []))
    except Exception:
      all_coursework.append([])

  return all_coursework


@mcp.tool
def refresh_courses(_params=None):
  """Force refresh the courses cache from Classroom API."""
  return refresh_courses_internal()


def refresh_courses_internal():
  """Internal helper that refreshes the courses cache and returns the list."""
  global service, courses_cache
  if service is None:
    auth()

  try:
    results = service.courses().list(pageSize=200).execute()
    courses = results.get("courses", [])
  except Exception:
    courses = []

  courses_cache = courses
  try:
    with open(cache_file, "w", encoding="utf-8") as f:
      json.dump(courses_cache, f, ensure_ascii=False, indent=2)
  except Exception:
    pass

  return courses_cache

@mcp.tool
def get_tasks(_params=None):
  """Return a flattened list of coursework (tasks).

  Supports optional params:
  - courseName: search cached courses by name (substring, case-insensitive)
  - courseId: use this id directly
  If no params given, returns tasks from all courses.
  """
  global service
  if service is None:
    auth()

  # helper to find course by name using cache
  def find_course_by_name(name: str):
    courses = fetch_courses() or []
    if not name or not courses:
      return None
    q = name.strip().casefold()
    # exact match first
    for c in courses:
      title = c.get("name") or c.get("title") or ""
      if title and title.casefold() == q:
        return c
    # substring match
    for c in courses:
      title = c.get("name") or c.get("title") or ""
      if title and q in title.casefold():
        return c
    return None

  course_id = None
  if isinstance(_params, dict):
    if "courseId" in _params and _params.get("courseId"):
      course_id = str(_params.get("courseId"))
    elif "courseName" in _params and _params.get("courseName"):
      found = find_course_by_name(_params.get("courseName"))
      if found:
        course_id = str(found.get("id"))

  tasks = []

  # If course_id provided, fetch only that course's coursework
  if course_id:
    try:
      resp = service.courses().courseWork().list(courseId=course_id).execute()
      course_work = resp.get("courseWork", [])
      if isinstance(course_work, list):
        tasks.extend(course_work)
    except Exception:
      pass
    return tasks

  # Otherwise fetch for all courses
  courses = fetch_courses() or []
  for course in courses:
    cid = course.get("id")
    if not cid:
      continue
    try:
      resp = service.courses().courseWork().list(courseId=str(cid)).execute()
      course_work = resp.get("courseWork", [])
      if isinstance(course_work, list):
        tasks.extend(course_work)
    except Exception:
      continue

  return tasks

def main():
  global creds
  creds = auth() 
  
  cursos = getCourses()
  clases_todos_cursos = getClases(cursos)

  print(clases_todos_cursos)

if __name__ == "__main__":
  # If --authorize flag is present, run auth and exit
  if STANDALONE_AUTHORIZE:
    try:
      auth()
      print("✅ Autorización completada. Token guardado en token.json", file=sys.stderr)
    except Exception as e:
      print(f"❌ Error durante autorización: {e}", file=sys.stderr)
      sys.exit(1)
    sys.exit(0)
  
  # Otherwise start the MCP server
  mcp.run(transport="stdio")

