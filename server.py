import os
import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp import types
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
import uvicorn

load_dotenv()

TOKEN = os.getenv("HUBSPOT_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
BASE = "https://api.hubapi.com"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

BLOG_IDS = {
    "sv": "5423796480",
    "no": "164698421914",
    "en": "167463790880"
}

CASE_IDS = {
    "sv": "6082252317",
    "no": "",   # fyll i när NO-blogg finns
    "en": ""    # fyll i när EN-blogg finns
}

app = Server("hubspot-cms")

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_blogs",
            description="Hämta lista över tillgängliga Stratsys-bloggar med deras ID:n och språk.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_blog_posts",
            description=(
                "Hämta blogginlägg från HubSpot, sorterade på senaste publish date. "
                "Ange language='sv', 'no' eller 'en' för att filtrera per språk. "
                "Kan även filtrera på status DRAFT eller PUBLISHED."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "description": "Språk: sv=Svenska, no=Norska, en=Engelska"
                    },
                    "state": {
                        "type": "string",
                        "enum": ["DRAFT", "PUBLISHED"],
                        "description": "Status på inläggen"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Antal inlägg att hämta (max 100)",
                        "default": 10
                    }
                }
            }
        ),
        types.Tool(
            name="get_blog_post",
            description="Hämta ett specifikt blogginlägg via ID eller sök på titel/nyckelord.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Exakt ID på blogginlägget"
                    },
                    "search": {
                        "type": "string",
                        "description": "Sökterm för att hitta inlägg på titel"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "description": "Filtrera på språk (valfritt vid sökning)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_blog_authors",
            description=(
                "Hämta lista över Stratsys bloggförfattare i HubSpot. "
                "Ange language='sv', 'no' eller 'en' för att få rätt author_id per språk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "description": "Språk att hämta author ID:n för (default: sv)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_landing_pages",
            description="Hämta landningssidor från HubSpot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["DRAFT", "PUBLISHED"],
                        "description": "Status på sidorna"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10
                    }
                }
            }
        ),
        types.Tool(
            name="create_blog_post",
            description=(
                "Skapa ett nytt blogginlägg som utkast i HubSpot (kunskapshubben). "
                "Ange language='sv', 'no' eller 'en' — rätt blogg väljs automatiskt."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Titel på blogginlägget"},
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "default": "sv"
                    },
                    "blog_author_id": {"type": "string", "description": "ID på bloggförfattaren"},
                    "post_body": {"type": "string", "description": "HTML-innehåll i inlägget"},
                    "meta_description": {"type": "string", "description": "SEO-beskrivning"},
                    "featured_image": {"type": "string", "description": "URL till featured image"},
                    "featured_image_alt": {"type": "string", "description": "Alt-text för featured image"}
                },
                "required": ["name", "language"]
            }
        ),
        types.Tool(
            name="create_case",
            description=(
                "Skapa ett nytt kundcase som utkast i HubSpot (Customer Cases-bloggen). "
                "Använd detta verktyg — INTE create_blog_post — för alla kundcase. "
                "Ange language='sv', 'no' eller 'en'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Titel på kundcaset"},
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "default": "sv"
                    },
                    "blog_author_id": {"type": "string", "description": "ID på bloggförfattaren"},
                    "post_body": {"type": "string", "description": "HTML-innehåll i caset"},
                    "meta_description": {"type": "string", "description": "SEO-beskrivning"},
                    "featured_image": {"type": "string", "description": "URL till featured image"},
                    "featured_image_alt": {"type": "string", "description": "Alt-text för featured image"}
                },
                "required": ["name", "language"]
            }
        ),
        types.Tool(
            name="update_blog_post",
            description=(
                "Uppdatera ett befintligt publicerat blogginlägg i HubSpot genom att skriva till "
                "draft-bufferten. Ändringen publiceras INTE direkt — inlägget får en pending draft "
                "som redaktören granskar och publicerar manuellt via 'Update'-knappen i HubSpot. "
                "Använd push_blog_post_draft för att publicera via API om redaktören godkänt i chatten."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "ID på blogginlägget"},
                    "name": {"type": "string"},
                    "post_body": {"type": "string"},
                    "meta_description": {"type": "string"},
                    "featured_image": {"type": "string", "description": "URL till featured image"},
                    "featured_image_alt": {"type": "string", "description": "Alt-text för featured image"}
                },
                "required": ["post_id"]
            }
        ),
        types.Tool(
            name="push_blog_post_draft",
            description=(
                "Publicerar den väntande draft-bufferten på ett befintligt publicerat blogginlägg. "
                "Använd detta ENDAST när användaren explicit godkänt ändringen i chatten. "
                "Motsvarar att klicka 'Update' i HubSpot-editorn."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "ID på blogginlägget vars draft ska publiceras"}
                },
                "required": ["post_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:

        if name == "get_blogs":
            result = [
                {"language": "sv", "id": BLOG_IDS["sv"], "url": "www.stratsys.com/sv/kunskapshub"},
                {"language": "no", "id": BLOG_IDS["no"], "url": "www.stratsys.com/no/knowledge-hub"},
                {"language": "en", "id": BLOG_IDS["en"], "url": "www.stratsys.com/knowledge-hub"},
                {"language": "sv (cases)", "id": CASE_IDS["sv"], "url": "www.stratsys.com/sv/kundcase"}
            ]
            return [types.TextContent(type="text", text=str(result))]

        elif name == "get_blog_posts":
            params = {"limit": arguments.get("limit", 10), "sort": "-publish_date"}
            if "state" in arguments:
                params["state"] = arguments["state"]
            if "language" in arguments:
                params["contentGroupId"] = BLOG_IDS[arguments["language"]]
            r = await client.get(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, params=params)
            posts = r.json().get("results", [])
            result = [{"id": p["id"], "title": p["name"], "state": p["state"], "published": p.get("publishDate", ""), "url": p.get("url", "")} for p in posts]
            return [types.TextContent(type="text", text=str(result))]

        elif name == "get_blog_post":
            if "post_id" in arguments:
                r = await client.get(f"{BASE}/cms/v3/blogs/posts/{arguments['post_id']}", headers=HEADERS)
                p = r.json()
                result = {
                    "id": p.get("id"),
                    "title": p.get("name"),
                    "state": p.get("currentState"),
                    "publishDate": p.get("publishDate"),
                    "metaDescription": p.get("metaDescription"),
                    "featuredImage": p.get("featuredImage", ""),
                    "featuredImageAltText": p.get("featuredImageAltText", ""),
                    "url": p.get("url"),
                    "postBody": p.get("postBody", "")
                }
                return [types.TextContent(type="text", text=str(result))]
            elif "search" in arguments:
                params = {"limit": 10, "sort": "-publish_date", "name__icontains": arguments["search"]}
                if "language" in arguments:
                    params["contentGroupId"] = BLOG_IDS[arguments["language"]]
                r = await client.get(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, params=params)
                posts = r.json().get("results", [])
                result = [{"id": p["id"], "title": p["name"], "state": p["state"], "publishDate": p.get("publishDate", ""), "url": p.get("url", "")} for p in posts]
                return [types.TextContent(type="text", text=str(result))]
            return [types.TextContent(type="text", text="Ange antingen post_id eller search.")]

        elif name == "get_blog_authors":
            r = await client.get(f"{BASE}/blogs/v3/blog-authors", headers=HEADERS, params={"limit": 100})
            authors = r.json().get("objects", [])
            language = arguments.get("language", "sv")
            result = []
            for a in authors:
                if a.get("deletedAt", 0) != 0:
                    continue
                if a.get("name") == "Sample HubSpot User":
                    continue
                if not a.get("email", "").endswith("@stratsys.se"):
                    continue
                if a.get("translatedFromId"):
                    continue
                author_id = str(a["id"]) if language == "sv" else str(a.get("translations", {}).get(language, {}).get("id", a["id"]))
                result.append({"author_id": author_id, "name": a.get("fullName") or a.get("name"), "language": language})
            return [types.TextContent(type="text", text=str(result))]

        elif name == "get_landing_pages":
            params = {"limit": arguments.get("limit", 10)}
            if "state" in arguments:
                params["state"] = arguments["state"]
            r = await client.get(f"{BASE}/cms/v3/pages/landing-pages", headers=HEADERS, params=params)
            pages = r.json().get("results", [])
            result = [{"id": p["id"], "title": p["name"], "state": p["state"]} for p in pages]
            return [types.TextContent(type="text", text=str(result))]

        elif name == "create_blog_post":
            language = arguments.get("language", "sv")
            payload = {
                "name": arguments["name"],
                "contentGroupId": BLOG_IDS.get(language, BLOG_IDS["sv"]),
                "state": "DRAFT"
            }
            if arguments.get("post_body"):
                payload["postBody"] = arguments["post_body"]
            if arguments.get("meta_description"):
                payload["metaDescription"] = arguments["meta_description"]
            if arguments.get("blog_author_id"):
                payload["blogAuthorId"] = arguments["blog_author_id"]
            if arguments.get("featured_image"):
                payload["featuredImage"] = arguments["featured_image"]
                payload["useFeaturedImage"] = True
            if arguments.get("featured_image_alt"):
                payload["featuredImageAltText"] = arguments["featured_image_alt"]
            r = await client.post(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, json=payload)
            post = r.json()
            return [types.TextContent(type="text", text=f"Skapat inlägg med ID: {post.get('id')} — Titel: {post.get('name')} — Språk: {language}")]

        elif name == "create_case":
            language = arguments.get("language", "sv")
            payload = {
                "name": arguments["name"],
                "contentGroupId": CASE_IDS.get(language, CASE_IDS["sv"]),
                "state": "DRAFT"
            }
            if arguments.get("post_body"):
                payload["postBody"] = arguments["post_body"]
            if arguments.get("meta_description"):
                payload["metaDescription"] = arguments["meta_description"]
            if arguments.get("blog_author_id"):
                payload["blogAuthorId"] = arguments["blog_author_id"]
            if arguments.get("featured_image"):
                payload["featuredImage"] = arguments["featured_image"]
                payload["useFeaturedImage"] = True
            if arguments.get("featured_image_alt"):
                payload["featuredImageAltText"] = arguments["featured_image_alt"]
            r = await client.post(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, json=payload)
            post = r.json()
            return [types.TextContent(type="text", text=f"Skapat kundcase med ID: {post.get('id')} — Titel: {post.get('name')} — Språk: {language}")]

        elif name == "update_blog_post":
            post_id = arguments.pop("post_id")
            payload = {}
            if arguments.get("name"):
                payload["name"] = arguments["name"]
            if arguments.get("post_body"):
                payload["postBody"] = arguments["post_body"]
            if arguments.get("meta_description"):
                payload["metaDescription"] = arguments["meta_description"]
            if arguments.get("featured_image"):
                payload["featuredImage"] = arguments["featured_image"]
                payload["useFeaturedImage"] = True
            if arguments.get("featured_image_alt"):
                payload["featuredImageAltText"] = arguments["featured_image_alt"]
            r = await client.patch(f"{BASE}/cms/blogs/2026-03/posts/{post_id}/draft", headers=HEADERS, json=payload)
            result = r.json()
            return [types.TextContent(type="text", text=f"Draft sparad för inlägg {post_id} — titel: {result.get('name')} — ändringen är INTE publicerad. Redaktören behöver öppna inlägget i HubSpot och klicka 'Update' för att publicera.")]

        elif name == "push_blog_post_draft":
            post_id = arguments["post_id"]
            r = await client.post(f"{BASE}/cms/blogs/2026-03/posts/{post_id}/draft/push-live", headers=HEADERS)
            if r.status_code in (200, 204):
                return [types.TextContent(type="text", text=f"Draft för inlägg {post_id} är nu publicerad live.")]
            else:
                return [types.TextContent(type="text", text=f"Fel vid publicering: {r.status_code} — {r.text}")]


sse = SseServerTransport("/messages/")

async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
EOF
