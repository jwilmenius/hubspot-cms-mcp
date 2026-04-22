import sys
import os
import asyncio
import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

TOKEN = os.getenv("HUBSPOT_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
BASE = "https://api.hubapi.com"

# Stratsys blogg-ID:n per språk
BLOG_IDS = {
    "sv": "5423796480",
    "no": "164698421914",
    "en": "167463790880"
}

app = Server("hubspot-cms")

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_blogs",
            description="Hämta lista över tillgängliga Stratsys-bloggar med deras ID:n och språk.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
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
                "Skapa ett nytt blogginlägg som utkast i HubSpot. "
                "Ange language='sv', 'no' eller 'en' — rätt blogg väljs automatiskt."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Titel på blogginlägget"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["sv", "no", "en"],
                        "description": "Språk: sv=Svenska, no=Norska, en=Engelska",
                        "default": "sv"
                    },
                    "blog_author_id": {
                        "type": "string",
                        "description": "ID på bloggförfattaren (valfritt)"
                    },
                    "post_body": {
                        "type": "string",
                        "description": "HTML-innehåll i inlägget"
                    },
                    "meta_description": {
                        "type": "string",
                        "description": "SEO-beskrivning"
                    }
                },
                "required": ["name", "language"]
            }
        ),
        types.Tool(
            name="update_blog_post",
            description="Uppdatera ett befintligt blogginlägg i HubSpot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "ID på blogginlägget"
                    },
                    "name": {"type": "string"},
                    "post_body": {"type": "string"},
                    "meta_description": {"type": "string"}
                },
                "required": ["post_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient() as client:

        if name == "get_blogs":
            result = [
                {"language": "sv", "id": BLOG_IDS["sv"], "url": "www.stratsys.com/sv/kunskapshub"},
                {"language": "no", "id": BLOG_IDS["no"], "url": "www.stratsys.com/no/knowledge-hub"},
                {"language": "en", "id": BLOG_IDS["en"], "url": "www.stratsys.com/knowledge-hub"}
            ]
            return [types.TextContent(type="text", text=str(result))]

        elif name == "get_blog_posts":
            params = {
                "limit": arguments.get("limit", 10),
                "sort": "-publish_date"
            }
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
                r = await client.get(
                    f"{BASE}/cms/v3/blogs/posts/{arguments['post_id']}",
                    headers=HEADERS
                )
                p = r.json()
                result = {
                    "id": p.get("id"),
                    "title": p.get("name"),
                    "state": p.get("currentState"),
                    "publishDate": p.get("publishDate"),
                    "metaDescription": p.get("metaDescription"),
                    "url": p.get("url"),
                    "postBody": p.get("postBody", "")
                }
                return [types.TextContent(type="text", text=str(result))]

            elif "search" in arguments:
                params = {
                    "limit": 10,
                    "sort": "-publish_date",
                    "name__icontains": arguments["search"]
                }
                if "language" in arguments:
                    params["contentGroupId"] = BLOG_IDS[arguments["language"]]
                r = await client.get(
                    f"{BASE}/cms/v3/blogs/posts",
                    headers=HEADERS,
                    params=params
                )
                posts = r.json().get("results", [])
                result = [{"id": p["id"], "title": p["name"], "state": p["state"], "publishDate": p.get("publishDate", ""), "url": p.get("url", "")} for p in posts]
                return [types.TextContent(type="text", text=str(result))]

            return [types.TextContent(type="text", text="Ange antingen post_id eller search.")]

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
            content_group_id = BLOG_IDS[language]
            payload = {
                "name": arguments["name"],
                "contentGroupId": content_group_id,
                "state": "DRAFT"
            }
            if "post_body" in arguments:
                payload["postBody"] = arguments["post_body"]
            if "meta_description" in arguments:
                payload["metaDescription"] = arguments["meta_description"]
            if "blog_author_id" in arguments:
                payload["blogAuthorId"] = arguments["blog_author_id"]
            r = await client.post(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, json=payload)
            post = r.json()
            return [types.TextContent(type="text", text=f"Skapat inlägg med ID: {post.get('id')} — Titel: {post.get('name')} — Språk: {language}")]

        elif name == "update_blog_post":
            post_id = arguments.pop("post_id")
            payload = {k: v for k, v in arguments.items() if v}
            if "post_body" in payload:
                payload["postBody"] = payload.pop("post_body")
            if "meta_description" in payload:
                payload["metaDescription"] = payload.pop("meta_description")
            r = await client.patch(f"{BASE}/cms/v3/blogs/posts/{post_id}", headers=HEADERS, json=payload)
            return [types.TextContent(type="text", text=f"Uppdaterat inlägg {post_id}")]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
