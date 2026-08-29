import json
import os
import urllib.request
from google.oauth2 import service_account
import google.auth.transport.requests

def send_push():
    token = os.environ.get("FCM_TOKEN")
    sa_json = os.environ.get("FCM_SERVICE_ACCOUNT")
    
    if not token or not sa_json:
        print("Missing FCM_TOKEN or FCM_SERVICE_ACCOUNT. Skipping push notification.")
        return

    try:
        sa_info = json.loads(sa_json)
        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        access_token = credentials.token
    except Exception as e:
        print(f"Error authenticating with Service Account: {e}")
        return

    project_id = sa_info["project_id"]
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": "Daily News 📰",
                "body": "La nuova rassegna stampa è pronta da leggere!"
            },
            "webpush": {
                "fcm_options": {
                    "link": "https://djiglio.github.io/daily_news/"
                }
            }
        }
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        urllib.request.urlopen(req)
        print("FCM Push notification sent successfully!")
    except Exception as e:
        print(f"Error sending push: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))

if __name__ == "__main__":
    send_push()
