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

def auth():
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

def getCourses():
  

def main():
    creds = None

    

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("classroom", "v1", credentials=creds)

    course_id = "780379512906"

    response = service.courses().courseWork().list(
        courseId=course_id
    ).execute()

    coursework = response.get("courseWork", [])

    for work in coursework:
        print(work["id"], "-", work["title"], "-", work["workType"])

if __name__ == "__main__":
    main()
