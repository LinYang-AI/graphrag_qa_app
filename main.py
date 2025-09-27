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
    """Initialize the GraphRAG system"""
    try:
        logger.info("🚀 Starting GraphRAG system...")
        
        # Add startup delay to let dependencies initialize
        import asyncio
        await asyncio.sleep(5)  # Wait 5 seconds for Neo4j to be ready
        
        await graphrag.initialize()
        
        # Process sample documents on startup
        sample_docs_path = Path("/app/sample_docs")
        if sample_docs_path.exists():
            logger.info("📚 Processing sample documents...")
            await graphrag.ingest_directory(str(sample_docs_path))
            logger.info("✅ Sample documents processed")
        
        logger.info("✅ GraphRAG system started successfully")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        # Don't raise - let the app start anyway for debugging


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
    file: UploadFile = File(...), tenant_id: str = Form("default")
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
        if suffix not in [".txt", ".pdf", ".md", ".docx", ".html"]:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {suffix}"
            )

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
            "file_size": len(content),
        }

    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return {"status": "error", "message": f"Failed to process document: {str(e)}"}
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
            result = await session.run(
                """
                MATCH (d:Document)
                RETURN d.name as title, d.path as file_path, 
                       size(d.content_preview) as content_size,
                       d.processed_at as processed_at
                ORDER BY d.name
                LIMIT $limit
            """,
                limit=limit,
            )

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
                "tenant_id": tenant_id,
            }

    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        return {"status": "error", "message": f"Failed to list documents: {str(e)}"}


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
        result = (
            graphrag.weaviate_client.query.get(
                "DocumentChunk", ["content", "source", "chunk_id"]
            )
            .with_near_vector({"vector": query_embedding})
            .with_limit(limit)
            .do()
        )

        chunks = result.get("data", {}).get("Get", {}).get("DocumentChunk", [])

        return {
            "status": "success",
            "query": query,
            "results": chunks,
            "count": len(chunks),
        }

    except Exception as e:
        logger.error(f"❌ Search error: {e}")
        return {"status": "error", "message": f"Search failed: {str(e)}"}


@app.get("/graph/overview")
async def graph_overview():
    """Get knowledge graph overview and statistics"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            # Get accurate counts excluding null entities
            stats_query = """
            MATCH (d:Document) 
            OPTIONAL MATCH (e:Entity) WHERE e.canonical_name IS NOT NULL
            OPTIONAL MATCH (c:Chunk)
            OPTIONAL MATCH (t:Topic)
            OPTIONAL MATCH ()-[r:RELATED]->()
            RETURN count(DISTINCT d) as documents,
                   count(DISTINCT e) as entities,
                   count(DISTINCT c) as chunks,
                   count(DISTINCT t) as topics,
                   count(DISTINCT r) as relationships
            """
            
            result = await session.run(stats_query)
            stats = dict(await result.single()) if result else {}
            
            # Get top entities with actual names
            top_entities_query = """
            MATCH (e:Entity)
            WHERE e.canonical_name IS NOT NULL 
            AND e.canonical_name <> ''
            AND e.canonical_name <> 'Unknown'
            RETURN e.canonical_name as name, e.type as type, 
                   e.mention_count as mentions
            ORDER BY e.mention_count DESC, e.canonical_name
            LIMIT 10
            """
            
            result = await session.run(top_entities_query)
            top_entities = []
            async for record in result:
                top_entities.append(dict(record))
            
            stats["top_entities"] = top_entities
            
            return {
                "status": "success",
                "graph_stats": stats
            }
            
    except Exception as e:
        logger.error(f"Graph overview error: {e}")
        return {
            "status": "error", 
            "message": f"Failed to get graph overview: {str(e)}"
        }


@app.get("/graph/entity/{entity_name}")
async def get_entity_graph(entity_name: str, max_depth: int = 2):
    """Get entity neighborhood graph for visualization"""
    try:
        graph_data = await graphrag.get_entity_graph(entity_name, max_depth)
        return {"status": "success", "entity": entity_name, "graph": graph_data}
    except Exception as e:
        logger.error(f"Entity graph error: {e}")
        return {"status": "error", "message": f"Failed to get entity graph: {str(e)}"}


@app.get("/entities")
async def list_entities(entity_type: str = None, limit: int = 50):
    """List entities with proper filtering"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            # Base query that filters out null/empty entities
            base_where = """
            WHERE e.canonical_name IS NOT NULL 
            AND e.canonical_name <> ''
            AND e.canonical_name <> 'Unknown'
            """
            
            if entity_type:
                query = f"""
                    MATCH (e:Entity)
                    {base_where}
                    AND e.type = $entity_type
                    RETURN e.canonical_name as name, e.type as type, 
                           e.mention_count as mentions, e.surface_forms as forms,
                           e.normalized_name as normalized
                    ORDER BY e.mention_count DESC, e.canonical_name
                    LIMIT $limit
                """
                result = await session.run(query, entity_type=entity_type.upper(), limit=limit)
            else:
                query = f"""
                    MATCH (e:Entity)
                    {base_where}
                    RETURN e.canonical_name as name, e.type as type,
                           e.mention_count as mentions, e.surface_forms as forms,
                           e.normalized_name as normalized
                    ORDER BY e.mention_count DESC, e.canonical_name
                    LIMIT $limit
                """
                result = await session.run(query, limit=limit)
            
            entities = []
            async for record in result:
                entities.append(dict(record))
            
            return {
                "status": "success",
                "entities": entities,
                "count": len(entities),
                "filter": entity_type
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list entities: {str(e)}"
        }

@app.get("/relationships")
async def list_relationships(limit: int = 20):
    """List relationships between entities"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            query = """
            MATCH (e1:Entity)-[r:RELATED]->(e2:Entity)
            WHERE e1.canonical_name IS NOT NULL AND e2.canonical_name IS NOT NULL
            RETURN e1.canonical_name as source, 
                   e2.canonical_name as target,
                   r.type as relationship,
                   r.confidence as confidence,
                   r.context as context
            ORDER BY r.confidence DESC
            LIMIT $limit
            """
            
            result = await session.run(query, limit=limit)
            relationships = []
            async for record in result:
                rel_data = dict(record)
                # Truncate context for readability
                if rel_data.get("context"):
                    rel_data["context"] = rel_data["context"][:100] + "..." if len(rel_data["context"]) > 100 else rel_data["context"]
                relationships.append(rel_data)
            
            return {
                "status": "success",
                "relationships": relationships,
                "count": len(relationships)
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list relationships: {str(e)}"
        }
        
@app.get("/debug/all-entities")
async def debug_all_entities():
    """Debug endpoint to see all entities including nulls"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            query = """
            MATCH (e:Entity)
            RETURN e.canonical_name as name, e.type as type, 
                   e.mention_count as mentions, e.surface_forms as forms,
                   labels(e) as labels
            ORDER BY e.canonical_name IS NULL DESC, e.mention_count DESC
            LIMIT 50
            """
            
            result = await session.run(query)
            entities = []
            async for record in result:
                entities.append(dict(record))
            
            # Separate good and bad entities
            good_entities = [e for e in entities if e.get("name") not in [None, "", "Unknown"]]
            bad_entities = [e for e in entities if e.get("name") in [None, "", "Unknown"]]
            
            return {
                "status": "success",
                "total_entities": len(entities),
                "good_entities": good_entities,
                "good_count": len(good_entities),
                "bad_entities": bad_entities,
                "bad_count": len(bad_entities)
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Debug query failed: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
