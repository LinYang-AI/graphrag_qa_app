from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from pathlib import Path

from graphrag_core import GraphRAGSystem

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
    print("🚀 Starting GraphRAG system...")
    try:
        await graphrag.initialize()
        
        # Process sample documents on startup
        sample_docs_path = Path("/app/sample_docs")
        if sample_docs_path.exists():
            print("📚 Processing sample documents...")
            await graphrag.ingest_directory(str(sample_docs_path))
            print("✅ Sample documents processed")
        else:
            print("⚠️  No sample documents directory found")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

@app.get("/")
async def root():
    return {"message": "GraphRAG Knowledge Assistant is running!", "version": "1.0.0"}

@app.post("/ask")
async def ask_question(question: dict):
    """Ask a question and get an answer with sources and graph context"""
    query = question.get("question", "")
    if not query:
        return {"error": "Question is required"}
    
    result = await graphrag.query(query)
    return result

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "neo4j": "connected", "weaviate": "connected"}

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    return await graphrag.get_stats()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)