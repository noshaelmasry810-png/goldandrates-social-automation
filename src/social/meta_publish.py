import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = "v23.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def graph_post(path, fields=None, files=None):
    url = GRAPH_BASE + path
    data = {}
    if fields:
        data.update(fields)
    if files:
        boundary = "----GoldAndRatesBoundary"
        body = bytearray()
        for name, value in data.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(str(value).encode())
            body.extend(b"\r\n")
        for name, (filename, content, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(content)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    else:
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=encoded, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def graph_get(path, params):
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(GRAPH_BASE + path + "?" + query, method="GET")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def publish_facebook(video_path, page_id, page_token, title, description):
    with open(video_path, "rb") as f:
        result = graph_post(
            f"/{page_id}/videos",
            fields={"access_token": page_token, "title": title, "description": description},
            files={"source": (Path(video_path).name, f.read(), "video/mp4")},
        )
    video_id = result.get("id")
    if not video_id:
        raise RuntimeError(f"Facebook upload failed: {result}")
    print(f"Facebook Page video published: {video_id}")


def publish_instagram(video_path, page_id, page_token, ig_token, caption):
    account = graph_get(f"/{page_id}", {"fields": "instagram_business_account", "access_token": page_token})
    ig = account.get("instagram_business_account", {})
    ig_user_id = ig.get("id")
    if not ig_user_id:
        raise RuntimeError("No Instagram professional account is connected to the Facebook Page.")

    # Create a Reel container using the resumable upload flow.
    container = graph_post(
        f"/{ig_user_id}/media",
        fields={"media_type": "REELS", "upload_type": "resumable", "caption": caption, "access_token": ig_token},
    )
    container_id = container.get("id")
    upload_uri = container.get("uri")
    if not container_id or not upload_uri:
        raise RuntimeError(f"Instagram container creation failed: {container}")

    with open(video_path, "rb") as f:
        video = f.read()

    upload_req = urllib.request.Request(
        upload_uri,
        data=video,
        headers={
            "Authorization": f"OAuth {ig_token}",
            "offset": "0",
            "file_size": str(len(video)),
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(upload_req) as response:
        upload_result = json.loads(response.read().decode("utf-8")) if response.read else {}
    print(f"Instagram upload response: {upload_result}")

    for _ in range(30):
        status = graph_get(f"/{container_id}", {"fields": "status_code,status", "access_token": ig_token})
        code = status.get("status_code")
        print(f"Instagram container status: {code}")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container failed: {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram container did not finish within the expected time.")

    published = graph_post(
        f"/{ig_user_id}/media_publish",
        fields={"creation_id": container_id, "access_token": ig_token},
    )
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError(f"Instagram publish failed: {published}")
    print(f"Instagram Reel published: {media_id}")


def main():
    video_path = os.environ["META_VIDEO_PATH"]
    content_path = os.environ["META_CONTENT_PATH"]
    page_id = os.environ["FACEBOOK_PAGE_ID"]
    page_token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
    ig_token = os.environ["META_INSTAGRAM_ACCESS_TOKEN"]

    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    title = content.get("hook") or content.get("videoData", {}).get("title") or "أسعار الذهب اليوم"
    description = content.get("description") or content.get("caption") or ""
    if "www.goldandrates.com" not in description:
        description += "\n\nموقع ذهب وأسعار\nwww.goldandrates.com"

    publish_facebook(video_path, page_id, page_token, title, description)
    publish_instagram(video_path, page_id, page_token, ig_token, description)
    print("Meta publishing completed successfully.")


if __name__ == "__main__":
    main()
