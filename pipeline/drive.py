"""구글드라이브 '쇼츠업로드' 폴더 읽기/정리.

필요 환경변수:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  DRIVE_REFRESH_TOKEN   드라이브 폴더가 있는 구글 계정으로 발급한 토큰
  DRIVE_INBOX_ID        영상 넣는 폴더 ID
  DRIVE_DONE_ID         게시 완료 후 옮길 폴더 ID
"""
import io
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]
GDOC = "application/vnd.google-apps.document"


class Drive:
    def __init__(self):
        creds = Credentials(
            token=None,
            refresh_token=os.environ["DRIVE_REFRESH_TOKEN"],
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.inbox = os.environ["DRIVE_INBOX_ID"]
        self.done = os.environ["DRIVE_DONE_ID"]

    def list_inbox(self):
        files, token = [], None
        while True:
            r = self.svc.files().list(
                q=f"'{self.inbox}' in parents and trashed=false",
                fields="nextPageToken,files(id,name,mimeType,appProperties,size)",
                pageSize=200, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            files += r.get("files", [])
            token = r.get("nextPageToken")
            if not token:
                return files

    def read_text(self, f) -> str:
        if f["mimeType"] == GDOC:
            req = self.svc.files().export_media(fileId=f["id"], mimeType="text/plain")
        else:
            req = self.svc.files().get_media(fileId=f["id"], supportsAllDrives=True)
        return self._fetch(req).decode("utf-8-sig")

    def download(self, f, dest: Path) -> Path:
        req = self.svc.files().get_media(fileId=f["id"], supportsAllDrives=True)
        with open(dest, "wb") as fh:
            dl = MediaIoBaseDownload(fh, req, chunksize=16 * 1024 * 1024)
            done = False
            while not done:
                _, done = dl.next_chunk()
        return dest

    def set_props(self, f, props: dict):
        self.svc.files().update(fileId=f["id"], body={"appProperties": props},
                                supportsAllDrives=True).execute()
        f.setdefault("appProperties", {}).update(props)

    def move_done(self, f):
        self.svc.files().update(fileId=f["id"], addParents=self.done, removeParents=self.inbox,
                                supportsAllDrives=True).execute()

    def _fetch(self, req) -> bytes:
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()
