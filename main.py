import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
]
isLogged = False
creds = None
service = None

def auth() -> Credentials:
  global isLogged
  global creds
  global service

  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    isLogged = True

  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        isLogged = True
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
        isLogged = True

  with open("token.json", "w") as token:
    token.write(creds.to_json())
  
  service = build("classroom", "v1", credentials=creds)

  return creds

def getCourses():
  if service is None:
    auth()
    
  results = service.courses().list(pageSize=10).execute()
  courses = results.get("courses", [])
  
  return courses
    
# ...existing code...
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

def main():
  global creds
  creds = auth() 
  
  cursos = getCourses
  clases_todos_cursos = getClases(cursos)

  print(clases_todos_cursos)

if __name__ == "__main__":
  main()
