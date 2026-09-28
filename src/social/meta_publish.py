import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = "v26.0"
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
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
    else:
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph API HTTP {exc.code} for {path}: {error_body}") from exc


def graph_get(path, params):
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(GRAPH_BASE + path + "?" + query, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph API GET HTTP {exc.code} for {path}: {error_body}") from exc


def publish_facebook(video_path, page_id, page_token, title, description):
    """Publish a Page video using Meta's resumable Page Videos upload flow."""
    file_size = os.path.getsize(video_path)
    videos_path = f"/{page_id}/videos"

    # Phase 1: initialize the upload session.
    start = graph_post(
        videos_path,
        fields={
            "upload_phase": "start",
            "file_size": str(file_size),
            "access_token": page_token,
        },
    )
    upload_session_id = start.get("upload_session_id")
    start_offset = int(start.get("start_offset", 0))
    end_offset = int(start.get("end_offset", 0))
    if not upload_session_id:
        raise RuntimeError(f"Facebook upload initialization failed: {start}")

    print(
        f"Facebook upload initialized: session={upload_session_id}, "
        f"offset={start_offset}/{end_offset}, size={file_size}"
    )

    # Phase 2: transfer chunks until Meta reports the full file is uploaded.
    with open(video_path, "rb") as f:
        while start_offset < file_size:
            f.seek(start_offset)
            chunk_size = max(1, end_offset - start_offset)
            chunk = f.read(chunk_size)
            if not chunk:
                raise RuntimeError(
                    f"Facebook upload stopped before the file was fully transferred: "
                    f"offset={start_offset}, size={file_size}"
                )

            transfer = graph_post(
                videos_path,
                fields={
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": str(start_offset),
                    "access_token": page_token,
                },
                files={
                    "video_file_chunk": (
                        Path(video_path).name,
                        chunk,
                        "video/mp4",
                    )
                },
            )

            next_offset = int(transfer.get("start_offset", start_offset + len(chunk)))
            next_end = int(transfer.get("end_offset", file_size))
            print(f"Facebook upload progress: {next_offset}/{file_size}")

            if next_offset <= start_offset:
                raise RuntimeError(f"Facebook upload did not advance: {transfer}")

            start_offset = next_offset
            end_offset = next_end if next_end > start_offset else file_size

    # Phase 3: finish and publish the video.
    finish = graph_post(
        videos_path,
        fields={
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "title": title,
            "description": description,
            "published": "true",
            "access_token": page_token,
        },
    )

    if finish.get("success") is not True:
        raise RuntimeError(f"Facebook video publish failed: {finish}")

    video_id = finish.get("video_id") or finish.get("id")
    print(f"Facebook Page video published successfully: {video_id or 'success'}")


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
    try:
        with urllib.request.urlopen(upload_req) as response:
            raw = response.read().decode("utf-8")
            upload_result = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Instagram resumable upload HTTP {exc.code}: {error_body}") from exc
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

    platforms = content.get("platforms") or {}
    facebook = platforms.get("facebook") or {}
    instagram = platforms.get("instagram") or {}

    title = facebook.get("title") or content.get("hook") or content.get("videoData", {}).get("title") or "أسعار الذهب اليوم"
    facebook_caption = facebook.get("caption") or content.get("description") or content.get("caption") or ""
    instagram_caption = instagram.get("caption") or facebook_caption

    if "www.goldandrates.com" not in facebook_caption:
        facebook_caption += "\n\nموقع ذهب وأسعار\nwww.goldandrates.com"
    if "www.goldandrates.com" not in instagram_caption:
        instagram_caption += "\n\nموقع ذهب وأسعار\nwww.goldandrates.com"

    publish_facebook(video_path, page_id, page_token, title, facebook_caption)
    publish_instagram(video_path, page_id, page_token, ig_token, instagram_caption)
    print("Meta publishing completed successfully.")


if __name__ == "__main__":
    main()
