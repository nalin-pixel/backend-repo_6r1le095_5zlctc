import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from database import get_documents, create_document, db
from schemas import Product

app = FastAPI(title="AMN LDA API", description="Backend for AMN LDA modern website")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "AMN LDA Backend Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the AMN LDA backend API"}


# ------------------------
# Health & Database checks
# ------------------------
@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ------------------------
# Schemas endpoint (for admin tools / validation UIs)
# ------------------------
@app.get("/schema")
def get_schema() -> Dict[str, Any]:
    """Expose available Pydantic schemas (name -> fields)"""
    from schemas import User, Product  # add more as they are defined

    def model_to_schema(m: BaseModel) -> Dict[str, Any]:
        return m.model_json_schema()

    return {
        "user": model_to_schema(User),
        "product": model_to_schema(Product),
    }


# ------------------------
# Products Catalog
# ------------------------
@app.get("/api/products")
def list_products(
    q: Optional[str] = Query(None, description="Full-text search over title/description"),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    in_stock: Optional[bool] = Query(None),
    sort: Optional[str] = Query("relevance", description="price_asc|price_desc|newest"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return products filtered by query params. Uses MongoDB when available."""
    # Build Mongo filter
    filter_dict: Dict[str, Any] = {}
    if category:
        filter_dict["category"] = category
    if in_stock is not None:
        filter_dict["in_stock"] = in_stock
    if q:
        # Basic text search using $or with regex
        filter_dict["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    if min_price is not None or max_price is not None:
        price_filter: Dict[str, Any] = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filter_dict["price"] = price_filter

    docs = []
    try:
        docs = get_documents("product", filter_dict, limit)
    except Exception as e:
        # Database not configured: return demo data to keep frontend working
        demo: List[Dict[str, Any]] = [
            {
                "_id": "demo-1",
                "title": "Cartão de Visita Premium",
                "description": "Impressão de alta qualidade com acabamento fosco/UV.",
                "price": 29.9,
                "category": "Cartões",
                "in_stock": True,
            },
            {
                "_id": "demo-2",
                "title": "Flyers Dobráveis",
                "description": "Papel couché 170g, dobra em 3 painéis.",
                "price": 49.0,
                "category": "Flyers",
                "in_stock": True,
            },
            {
                "_id": "demo-3",
                "title": "Lonas Publicitárias",
                "description": "Impressão resistente para exterior com ilhoses.",
                "price": 99.0,
                "category": "Grandes Formatos",
                "in_stock": False,
            },
        ]
        docs = demo[:limit]

    # Sorting (client can also handle). Only basic server sort for demo lists.
    if sort == "price_asc":
        docs = sorted(docs, key=lambda d: float(d.get("price", 0)))
    elif sort == "price_desc":
        docs = sorted(docs, key=lambda d: float(d.get("price", 0)), reverse=True)

    return {"items": docs, "count": len(docs)}


# ------------------------
# Posts / News
# ------------------------
@app.get("/api/posts")
def list_posts(limit: int = Query(6, ge=1, le=50)):
    try:
        docs = get_documents("blogpost", {}, limit)
    except Exception:
        docs = [
            {
                "_id": "n1",
                "title": "Nova linha de impressão sustentável",
                "excerpt": "Apresentamos materiais eco-friendly com a mesma qualidade premium.",
                "category": "Notícias",
                "date": "2025-01-10",
            },
            {
                "_id": "n2",
                "title": "Guia de acabamentos para cartões",
                "excerpt": "Como escolher entre laminação fosca, brilho UV localizado e mais.",
                "category": "Guias Técnicos",
                "date": "2025-02-05",
            },
            {
                "_id": "n3",
                "title": "Estúdio 3D para protótipos de embalagens",
                "excerpt": "Veja os seus produtos em 3D antes de produzir.",
                "category": "Lançamentos",
                "date": "2025-03-18",
            },
        ][:limit]
    return {"items": docs}


# ------------------------
# Simple AI Chatbot stub
# ------------------------
class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@app.post("/api/chatbot")
def chatbot(msg: ChatMessage):
    text = (msg.message or "").strip().lower()
    # Very simple rule-based demo to keep experience fluent without external LLMs
    if any(w in text for w in ["orcamento", "preço", "cotacao", "cotação"]):
        return {
            "reply": "Para orçamento rápido, indique produto, dimensões, tiragem e prazo. Podemos gerar uma proposta base automaticamente.",
            "suggestions": [
                "Cartões de visita 500 unid. 350g laminado fosco",
                "Flyers A5 1000 unid. 170g couché",
                "Lona 2x1m com ilhoses"
            ],
        }
    if any(w in text for w in ["horario", "assistencia", "visita", "técnico", "tecnico"]):
        return {
            "reply": "Podemos agendar assistência. Indique data/horário preferido e local. Enviaremos convite do Google Calendar.",
            "action": "schedule_suggest",
        }
    return {
        "reply": "Olá! Sou o assistente AMN. Posso ajudar com produtos, prazos, orçamentos e assistência técnica.",
        "suggestions": ["Ver catálogo", "Pedir orçamento", "Falar com humano"],
    }


# ------------------------
# Lightweight sitemap (SEO)
# ------------------------
@app.get("/sitemap.xml", response_class=PlainTextResponse)
def sitemap():
    base = os.getenv("FRONTEND_URL", "https://example.com")
    urls = [
        "",
        "catalogo",
        "noticias",
    ]
    xml_items = "\n".join([
        f"  <url><loc>{base}/{path}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>".rstrip("/")
        for path in urls
    ])
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{xml_items}
</urlset>
"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
