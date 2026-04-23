import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
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

mcp = FastMCP("hubspot-cms")

@mcp.tool()
async def get_blogs() -> str:
    """Hämta lista över tillgängliga Stratsys-bloggar med deras ID:n och språk."""
    result = [
        {"language": "sv", "id": BLOG_IDS["sv"], "url": "www.stratsys.com/sv/kunskapshub"},
        {"language": "no", "id": BLOG_IDS["no"], "url": "www.stratsys.com/no/knowledge-hub"},
        {"language": "en", "id": BLOG_IDS["en"], "url": "www.stratsys.com/knowledge-hub"}
    ]
    return str(result)

@mcp.tool()
async def get_blog_posts(language: str = "", state: str = "", limit: int = 10) -> str:
    """Hämta blogginlägg från HubSpot sorterade på senaste publish date.
    
    Args:
        language: Språk: sv=Svenska, no=Norska, en=Engelska
        state: Status: DRAFT eller PUBLISHED
        limit: Antal inlägg att hämta (max 100)
    """
    params = {"limit": limit, "sort": "-publish_date"}
    if state:
        params["state"] = state
    if language and language in BLOG_IDS:
        params["contentGroupId"] = BLOG_IDS[language]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, params=params)
        posts = r.json().get("results", [])
    result = [{"id": p["id"], "title": p["name"], "state": p["state"], "published": p.get("publishDate", ""), "url": p.get("url", "")} for p in posts]
    return str(result)

@mcp.tool()
async def get_blog_post(post_id: str = "", search: str = "", language: str = "") -> str:
    """Hämta ett specifikt blogginlägg via ID eller sök på titel/nyckelord.
    
    Args:
        post_id: Exakt ID på blogginlägget
        search: Sökterm för att hitta inlägg på titel
        language: Filtrera på språk vid sökning: sv, no eller en
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if post_id:
            r = await client.get(f"{BASE}/cms/v3/blogs/posts/{post_id}", headers=HEADERS)
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
            return str(result)
        elif search:
            params = {"limit": 10, "sort": "-publish_date", "name__icontains": search}
            if language and language in BLOG_IDS:
                params["contentGroupId"] = BLOG_IDS[language]
            r = await client.get(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, params=params)
            posts = r.json().get("results", [])
            result = [{"id": p["id"], "title": p["name"], "state": p["state"], "publishDate": p.get("publishDate", ""), "url": p.get("url", "")} for p in posts]
            return str(result)
    return "Ange antingen post_id eller search."

@mcp.tool()
async def get_blog_authors(language: str = "sv") -> str:
    """Hämta lista över Stratsys bloggförfattare med rätt author_id per språk.
    
    Args:
        language: Språk: sv, no eller en (default: sv)
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BASE}/blogs/v3/blog-authors", headers=HEADERS, params={"limit": 100})
        authors = r.json().get("objects", [])
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
        if language == "sv":
            author_id = str(a["id"])
        else:
            translations = a.get("translations", {})
            if language in translations:
                author_id = str(translations[language]["id"])
            else:
                author_id = str(a["id"])
        result.append({
            "author_id": author_id,
            "name": a.get("fullName") or a.get("name"),
            "language": language
        })
    return str(result)

@mcp.tool()
async def get_landing_pages(state: str = "", limit: int = 10) -> str:
    """Hämta landningssidor från HubSpot.
    
    Args:
        state: Status: DRAFT eller PUBLISHED
        limit: Antal sidor att hämta
    """
    params = {"limit": limit}
    if state:
        params["state"] = state
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BASE}/cms/v3/pages/landing-pages", headers=HEADERS, params=params)
        pages = r.json().get("results", [])
    result = [{"id": p["id"], "title": p["name"], "state": p["state"]} for p in pages]
    return str(result)

@mcp.tool()
async def create_blog_post(
    name: str,
    language: str = "sv",
    post_body: str = "",
    meta_description: str = "",
    blog_author_id: str = "",
    featured_image: str = "",
    featured_image_alt: str = ""
) -> str:
    """Skapa ett nytt blogginlägg som utkast i HubSpot.
    
    Args:
        name: Titel på blogginlägget
        language: Språk: sv, no eller en
        post_body: HTML-innehåll i inlägget
        meta_description: SEO-beskrivning max 155 tecken
        blog_author_id: ID på bloggförfattaren
        featured_image: URL till featured image
        featured_image_alt: Alt-text för featured image
    """
    content_group_id = BLOG_IDS.get(language, BLOG_IDS["sv"])
    payload = {
        "name": name,
        "contentGroupId": content_group_id,
        "state": "DRAFT"
    }
    if post_body:
        payload["postBody"] = post_body
    if meta_description:
        payload["metaDescription"] = meta_description
    if blog_author_id:
        payload["blogAuthorId"] = blog_author_id
    if featured_image:
        payload["featuredImage"] = featured_image
        payload["useFeaturedImage"] = True
    if featured_image_alt:
        payload["featuredImageAltText"] = featured_image_alt
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(f"{BASE}/cms/v3/blogs/posts", headers=HEADERS, json=payload)
        post = r.json()
    return f"Skapat inlägg med ID: {post.get('id')} — Titel: {post.get('name')} — Språk: {language}"

@mcp.tool()
async def update_blog_post(
    post_id: str,
    name: str = "",
    post_body: str = "",
    meta_description: str = "",
    featured_image: str = "",
    featured_image_alt: str = ""
) -> str:
    """Uppdatera ett befintligt blogginlägg i HubSpot.
    
    Args:
        post_id: ID på blogginlägget
        name: Ny titel
        post_body: Nytt HTML-innehåll
        meta_description: Ny SEO-beskrivning
        featured_image: URL till featured image
        featured_image_alt: Alt-text för featured image
    """
    payload = {}
    if name:
        payload["name"] = name
    if post_body:
        payload["postBody"] = post_body
    if meta_description:
        payload["metaDescription"] = meta_description
    if featured_image:
        payload["featuredImage"] = featured_image
        payload["useFeaturedImage"] = True
    if featured_image_alt:
        payload["featuredImageAltText"] = featured_image_alt
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.patch(f"{BASE}/cms/v3/blogs/posts/{post_id}", headers=HEADERS, json=payload)
    return f"Uppdaterat inlägg {post_id}"


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
