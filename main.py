import os
import json
import datetime
import urllib.parse
import concurrent.futures
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

max_api_wait_time = (3.0, 8.0)
max_time = 10.0

invidious_apis = [
    'https://invidious.lunivers.trade/',
    'https://invidious.ducks.party/',
    'https://super8.absturztau.be/',
    'https://invidious.nikkosphere.com/',
    'https://yt.omada.cafe/',
    'https://iv.melmac.space/',
    'https://iv.duti.dev/',
    'https://invid-api.poketube.fun/',
]

EDU_VIDEO_API = "https://siawaseok.duckdns.org/api/video2/"
STREAM_API = "https://ytdl-0et1.onrender.com/stream/"

def get_user_agent():
    return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def is_json(text):
    try:
        json.loads(text)
        return True
    except:
        return False

def request_api(path, apis):
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(apis)) as executor:
        future_to_api = {
            executor.submit(
                requests.get,
                api + 'api/v1' + path,
                headers=get_user_agent(),
                timeout=max_api_wait_time
            ): api for api in apis
        }
        for future in concurrent.futures.as_completed(future_to_api, timeout=max_time):
            try:
                res = future.result()
                if res.status_code == 200 and is_json(res.text):
                    return res.text
            except:
                continue
    return None

def format_search_result(item):
    item_type = item.get("type", "unknown")
    if item_type == "video":
        return {
            "type": "video",
            "title": item.get("title", ""),
            "id": item.get("videoId", ""),
            "author": item.get("author", ""),
            "published": item.get("publishedText", ""),
            "length": str(datetime.timedelta(seconds=item.get("lengthSeconds", 0))),
            "views": item.get("viewCountText", "")
        }
    elif item_type == "channel":
        thumbs = item.get('authorThumbnails', [{}])
        thumb = thumbs[-1].get('url', '') if thumbs else ''
        if thumb and not thumb.startswith("https"):
            thumb = "https://" + thumb.lstrip("http://").lstrip("//")
        return {
            "type": "channel",
            "author": item.get("author", ""),
            "id": item.get("authorId", ""),
            "thumbnail": thumb
        }
    elif item_type == "playlist":
        return {
            "type": "playlist",
            "title": item.get("title", ""),
            "id": item.get("playlistId", ""),
            "count": item.get("videoCount", 0)
        }
    return {"type": "unknown"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", page: int = 1):
    if not q:
        return templates.TemplateResponse("index.html", {"request": request})
    
    path = f"/search?q={urllib.parse.quote(q)}&page={page}&hl=jp"
    result = request_api(path, invidious_apis)
    
    results = []
    if result:
        data = json.loads(result)
        results = [format_search_result(item) for item in data]
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": results,
        "page": page
    })

@app.get("/watch", response_class=HTMLResponse)
async def watch(request: Request, v: str = ""):
    if not v:
        return templates.TemplateResponse("index.html", {"request": request})
    
    video_data = {
        "title": "動画を読み込み中...",
        "author": "",
        "author_id": "",
        "author_icon": "",
        "description": "",
        "views": "",
        "likes": "",
        "published": "",
        "subscribers": ""
    }
    related = []
    
    try:
        res = requests.get(
            f"{EDU_VIDEO_API}{urllib.parse.quote(v)}",
            headers=get_user_agent(),
            timeout=max_api_wait_time
        )
        if res.status_code == 200:
            data = res.json()
            video_data = {
                "title": data.get("title", ""),
                "author": data.get("author", {}).get("name", ""),
                "author_id": data.get("author", {}).get("id", ""),
                "author_icon": data.get("author", {}).get("thumbnail", ""),
                "description": data.get("description", {}).get("formatted", ""),
                "views": data.get("views", ""),
                "likes": data.get("likes", ""),
                "published": data.get("relativeDate", ""),
                "subscribers": data.get("author", {}).get("subscribers", "")
            }
            for rel in data.get("related", [])[:10]:
                vid = rel.get("videoId", "")
                related.append({
                    "id": vid,
                    "title": rel.get("title", ""),
                    "author": rel.get("channel", ""),
                    "views": rel.get("views", ""),
                    "thumbnail": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
                })
    except:
        pass
    
    return templates.TemplateResponse("watch.html", {
        "request": request,
        "videoid": v,
        "video": video_data,
        "related": related
    })

@app.get("/channel/{channel_id}", response_class=HTMLResponse)
async def channel(request: Request, channel_id: str):
    path = f"/channels/{urllib.parse.quote(channel_id)}"
    result = request_api(path, invidious_apis)
    
    channel_data = {"name": "チャンネル", "icon": "", "banner": "", "description": "", "subscribers": ""}
    videos = []
    
    if result:
        data = json.loads(result)
        thumbs = data.get("authorThumbnails", [])
        icon = thumbs[-1].get("url", "") if thumbs else ""
        banners = data.get("authorBanners", [])
        banner = banners[0].get("url", "") if banners else ""
        
        channel_data = {
            "name": data.get("author", ""),
            "icon": icon,
            "banner": banner,
            "description": data.get("descriptionHtml", ""),
            "subscribers": data.get("subCount", "")
        }
        
        for vid in data.get("latestVideos", [])[:20]:
            videos.append({
                "id": vid.get("videoId", ""),
                "title": vid.get("title", ""),
                "views": vid.get("viewCountText", ""),
                "published": vid.get("publishedText", ""),
                "length": str(datetime.timedelta(seconds=vid.get("lengthSeconds", 0)))
            })
    
    return templates.TemplateResponse("channel.html", {
        "request": request,
        "channel": channel_data,
        "videos": videos
    })

@app.get("/api/stream/{videoid}")
async def get_stream(videoid: str):
    try:
        res = requests.get(
            f"{STREAM_API}{videoid}",
            headers=get_user_agent(),
            timeout=(5, 15)
        )
        if res.status_code == 200:
            data = res.json()
            formats = data.get("formats", [])
            for f in formats:
                if f.get("itag") == "18" and f.get("url"):
                    return {"url": f["url"]}
    except:
        pass
    return {"url": None}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
