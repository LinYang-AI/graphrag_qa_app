from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import tempfile
import logging
from pathlib import Path
from typing import List

from graphrag_core import GraphRAGSystem

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="GraphRAG Knowledge Assistant", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize GraphRAG system
graphrag = GraphRAGSystem()

@app.on_event("startup")
async def startup_event():
    """Initialize the GraphRAG system and process sample documents"""
    try:
        logger.info("🚀 Starting GraphRAG system...")
        await graphrag.initialize()
        
        # Process sample documents on startup
        sample_docs_path = Path("/app/sample_docs")
        if sample_docs_path.exists():
            logger.info("📚 Processing sample documents...")
            await graphrag.ingest_directory(str(sample_docs_path))
            logger.info("✅ Sample documents processed")
        else:
            logger.info("⚠️  No sample documents directory found")
            
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        # Remove raise - keep the app start anyway for debugging

@app.get("/")
async def root():
    return {"message": "GraphRAG Knowledge Assistant is running!", "version": "1.0.0"}

@app.post("/ask")
async def ask_question(question: dict):
    """Ask a question and get an answer with sources and graph context"""
    try:
        query = question.get("question", "")
        if not query:
            return {"error": "Question is required"}
        
        result = await graphrag.query(query)
        return result
    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        return {"error": f"Failed to process question: {str(e)}"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        stats = await graphrag.get_stats()
        return {"status": "healthy", "stats": stats}
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        return await graphrag.get_stats()
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form("default")
):
    """Upload and process a single document - simplified version"""
    tmp_path = None
    try:
        logger.info(f"📤 Receiving upload: {file.filename}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Save uploaded file temporarily
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ['.txt', '.pdf', '.md', '.docx', '.html']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        logger.info(f"📄 Processing {file.filename} (size: {len(content)} bytes)")
        
        # Use the basic ingestion method that we know works
        await graphrag.ingest_document(tmp_path)
        
        return {
            "status": "success",
            "message": f"Document '{file.filename}' processed successfully",
            "filename": file.filename,
            "tenant_id": tenant_id,
            "file_size": len(content)
        }
        
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return {
            "status": "error",
            "message": f"Failed to process document: {str(e)}"
        }
    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.get("/documents")
async def list_documents(tenant_id: str = "default", limit: int = 20):
    """List documents - simplified version"""
    try:
        logger.info(f"📋 Listing documents for tenant: {tenant_id}")
        
        if not graphrag.neo4j_driver:
            return {"status": "error", "message": "Neo4j not connected"}
        
        async with graphrag.neo4j_driver.session() as session:
            result = await session.run("""
                MATCH (d:Document)
                RETURN d.name as title, d.path as file_path, 
                       size(d.content_preview) as content_size,
                       d.processed_at as processed_at
                ORDER BY d.name
                LIMIT $limit
            """, limit=limit)
            
            documents = []
            async for record in result:
                doc_data = dict(record)
                # Convert any datetime objects to strings
                if doc_data.get("processed_at"):
                    doc_data["processed_at"] = str(doc_data["processed_at"])
                documents.append(doc_data)
            
            return {
                "status": "success",
                "documents": documents,
                "count": len(documents),
                "tenant_id": tenant_id
            }
            
    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        return {
            "status": "error",
            "message": f"Failed to list documents: {str(e)}"
        }

@app.get("/search")
async def simple_search(query: str, limit: int = 10):
    """Simple search endpoint"""
    try:
        logger.info(f"🔍 Simple search: {query}")
        
        if not graphrag.weaviate_client or not graphrag.embeddings_model:
            return {"status": "error", "message": "Search components not initialized"}
        
        # Generate query embedding
        query_embedding = graphrag.embeddings_model.encode(query).tolist()
        
        # Search Weaviate
        result = graphrag.weaviate_client.query.get(
            "DocumentChunk", 
            ["content", "source", "chunk_id"]
        ).with_near_vector({
            "vector": query_embedding
        }).with_limit(limit).do()
        
        chunks = result.get("data", {}).get("Get", {}).get("DocumentChunk", [])
        
        return {
            "status": "success",
            "query": query,
            "results": chunks,
            "count": len(chunks)
        }
        
    except Exception as e:
        logger.error(f"❌ Search error: {e}")
        return {
            "status": "error",
            "message": f"Search failed: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)