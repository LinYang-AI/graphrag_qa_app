from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
import uvicorn
import os
import tempfile
import logging
from pathlib import Path
from typing import List

from graphrag_core import GraphRAGSystem
from auth import (
    auth_manager, get_current_user, require_role, require_permission,
    User, UserRole, TenantPermission
)
from security import security_validator, rate_limiter

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

# Security
security = HTTPBearer(auto_error=False)

# Initialize GraphRAG system
graphrag = GraphRAGSystem()


@app.on_event("startup")
async def startup_event():
    """Initialize the GraphRAG system"""
    try:
        logger.info("🚀 Starting GraphRAG system...")
        
        import asyncio
        await asyncio.sleep(5)  # Wait for dependencies
        
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


# ================================
# PUBLIC ENDPOINTS (NO AUTH)
# ================================

@app.get("/")
async def root():
    return {"message": "GraphRAG Knowledge Assistant is running!", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        stats = await graphrag.get_stats()
        return {"status": "healthy", "stats": stats}
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "error", "message": str(e)}


# ================================
# AUTHENTICATION ENDPOINTS
# ================================

@app.post("/auth/login")
async def login(credentials: dict):
    """Login endpoint"""
    try:
        email = credentials.get("email", "").strip()
        password = credentials.get("password", "")
        
        # Validate input
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        if not security_validator.validate_email(email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # Authenticate user
        user = auth_manager.authenticate_user(email, password)
        if not user:
            # Log failed attempt
            logger.warning(f"Failed login attempt for: {email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create tokens
        access_token = auth_manager.create_access_token(user)
        refresh_token = auth_manager.create_refresh_token(user)
        
        logger.info(f"User logged in: {email} ({user.role.value})")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "role": user.role.value,
                "tenant_id": user.tenant_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/auth/register")
async def register(user_data: dict, current_user: User = Depends(require_role(UserRole.ADMIN))):
    """Register new user (admin only)"""
    try:
        email = user_data.get("email", "").strip()
        password = user_data.get("password", "")
        role = user_data.get("role", "user")
        tenant_id = user_data.get("tenant_id", "default")
        
        # Validate input
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        if not security_validator.validate_email(email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        password_validation = security_validator.validate_password(password)
        if not password_validation["valid"]:
            raise HTTPException(status_code=400, detail=password_validation["issues"])
        
        if not security_validator.validate_tenant_id(tenant_id):
            raise HTTPException(status_code=400, detail="Invalid tenant ID format")
        
        # Set permissions based on role
        try:
            user_role = UserRole(role)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        permissions = [TenantPermission.READ]
        if user_role in [UserRole.USER, UserRole.ADMIN]:
            permissions.append(TenantPermission.WRITE)
        if user_role == UserRole.ADMIN:
            permissions.append(TenantPermission.ADMIN)
        
        # Create user
        new_user = auth_manager.create_user(email, password, user_role, tenant_id, permissions)
        
        logger.info(f"New user created: {email} ({user_role.value}) by {current_user.email}")
        
        return {
            "message": "User created successfully",
            "user": {
                "user_id": new_user.user_id,
                "email": new_user.email,
                "role": new_user.role.value,
                "tenant_id": new_user.tenant_id
            }
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/auth/refresh")
async def refresh_token(token_data: dict):
    """Refresh access token"""
    try:
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")
        
        # Verify refresh token
        payload = auth_manager.verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Get user and create new access token
        user = auth_manager.get_user_from_token(refresh_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        new_access_token = auth_manager.create_access_token(user)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=401, detail="Token refresh failed")


# ================================
# USER ENDPOINTS (AUTHENTICATED)
# ================================

@app.post("/ask")
async def ask_question(question: dict, current_user: User = Depends(get_current_user)):
    """Ask a question (authenticated users)"""
    try:
        query = question.get("question", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Question is required")
        
        # Rate limiting
        if not rate_limiter.is_allowed(current_user.user_id, "/ask", max_requests=50):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Sanitize input
        query = security_validator.sanitize_string(query, max_length=500)
        
        # Check for SQL injection attempts
        if security_validator.detect_sql_injection(query):
            logger.warning(f"SQL injection attempt by {current_user.email}: {query}")
            raise HTTPException(status_code=400, detail="Invalid query format")
        
        result = await graphrag.query(query)
        
        # Log query for audit
        logger.info(f"Query by {current_user.email}: {query[:50]}...")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        return {"error": f"Failed to process question: {str(e)}"}


@app.get("/documents")
async def list_documents(
    tenant_id: str = "default", 
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """List documents (authenticated users)"""
    try:
        # Tenant access control
        if current_user.role != UserRole.ADMIN and tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to this tenant")
        
        if not graphrag.neo4j_driver:
            return {"status": "error", "message": "Neo4j not connected"}

        async with graphrag.neo4j_driver.session() as session:
            # Add tenant filtering if not admin
            tenant_filter = ""
            params = {"limit": limit}
            
            if current_user.role != UserRole.ADMIN:
                tenant_filter = "WHERE d.tenant_id = $tenant_id"
                params["tenant_id"] = current_user.tenant_id
            
            result = await session.run(f"""
                MATCH (d:Document)
                {tenant_filter}
                RETURN d.name as title, d.path as file_path, 
                       size(d.content_preview) as content_size,
                       d.processed_at as processed_at,
                       d.tenant_id as tenant_id
                ORDER BY d.name
                LIMIT $limit
            """, **params)

            documents = []
            async for record in result:
                doc_data = dict(record)
                if doc_data.get("processed_at"):
                    doc_data["processed_at"] = str(doc_data["processed_at"])
                documents.append(doc_data)

            return {
                "status": "success",
                "documents": documents,
                "count": len(documents),
                "tenant_id": tenant_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        return {"status": "error", "message": f"Failed to list documents: {str(e)}"}


# ================================
# ADMIN ENDPOINTS
# ================================

@app.post("/admin/upload")
async def admin_upload_document(
    file: UploadFile = File(...), 
    tenant_id: str = Form("default"),
    current_user: User = Depends(require_permission(TenantPermission.WRITE))
):
    """Upload document (requires write permission)"""
    tmp_path = None
    try:
        logger.info(f"📤 Admin upload by {current_user.email}: {file.filename}")

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Read file content for validation
        content = await file.read()
        file_validation = security_validator.validate_file_upload(
            file.filename, len(content), max_size_mb=100
        )
        
        if not file_validation["valid"]:
            raise HTTPException(status_code=400, detail=file_validation["issues"])
        
        # Validate tenant access
        if not security_validator.validate_tenant_id(tenant_id):
            raise HTTPException(status_code=400, detail="Invalid tenant ID")
        
        if current_user.role != UserRole.ADMIN and tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to this tenant")

        # Save file temporarily
        suffix = Path(file.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        logger.info(f"📄 Processing {file.filename} (size: {len(content)} bytes)")

        # Process document
        await graphrag.ingest_document(tmp_path)

        # Log successful upload
        logger.info(f"✅ Document uploaded successfully by {current_user.email}: {file.filename}")

        return {
            "status": "success",
            "message": f"Document '{file.filename}' processed successfully",
            "filename": file.filename,
            "tenant_id": tenant_id,
            "file_size": len(content),
            "uploaded_by": current_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Admin upload error: {e}")
        return {"status": "error", "message": f"Failed to process document: {str(e)}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@app.delete("/admin/documents/{document_hash}")
async def delete_document(
    document_hash: str,
    current_user: User = Depends(require_permission(TenantPermission.ADMIN))
):
    """Delete document (admin only)"""
    try:
        # Sanitize input
        document_hash = security_validator.sanitize_string(document_hash, 50)
        
        async with graphrag.neo4j_driver.session() as session:
            # First check if document exists and get tenant info
            check_result = await session.run(
                "MATCH (d:Document {hash: $hash}) RETURN d.tenant_id as tenant_id, d.name as name",
                hash=document_hash
            )
            doc_record = await check_result.single()
            
            if not doc_record:
                raise HTTPException(status_code=404, detail="Document not found")
            
            doc_tenant = doc_record.get("tenant_id")
            doc_name = doc_record.get("name")
            
            # Check tenant access
            if (current_user.role != UserRole.ADMIN and 
                doc_tenant and doc_tenant != current_user.tenant_id):
                raise HTTPException(status_code=403, detail="Access denied to this tenant")
            
            # Delete document and related data
            delete_result = await session.run("""
                MATCH (d:Document {hash: $hash})
                OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
                OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
                DETACH DELETE d, c
                RETURN count(d) as deleted_docs, count(c) as deleted_chunks
            """, hash=document_hash)
            
            delete_stats = await delete_result.single()
            
            # Also clean up vector embeddings from Weaviate
            try:
                # Delete chunks from Weaviate
                graphrag.weaviate_client.batch.delete_objects(
                    class_name="DocumentChunk",
                    where={
                        "path": ["chunk_id"],
                        "operator": "Like",
                        "valueText": f"{document_hash}_*"
                    }
                )
            except Exception as e:
                logger.warning(f"Error cleaning up vector embeddings: {e}")
            
            logger.info(f"🗑️ Document deleted by {current_user.email}: {doc_name} ({document_hash})")
            
            return {
                "status": "success",
                "message": f"Document '{doc_name}' deleted successfully",
                "deleted_chunks": delete_stats.get("deleted_chunks", 0),
                "deleted_by": current_user.email
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@app.get("/admin/users")
async def list_users(current_user: User = Depends(require_role(UserRole.ADMIN))):
    """List all users (admin only)"""
    try:
        users_list = []
        for email, user_data in auth_manager.users.items():
            user = user_data['user']
            users_list.append({
                "user_id": user.user_id,
                "email": user.email,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
                "permissions": [p.value for p in user.permissions],
                "created_at": user.created_at.isoformat()
            })
        
        return {
            "status": "success",
            "users": users_list,
            "count": len(users_list)
        }
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@app.get("/admin/stats")
async def admin_stats(current_user: User = Depends(require_role(UserRole.ADMIN))):
    """Get comprehensive system stats (admin only)"""
    try:
        stats = await graphrag.get_stats()
        
        # Add user stats
        stats["users"] = len(auth_manager.users)
        stats["admin_users"] = len([
            user for user_data in auth_manager.users.values()
            if user_data['user'].role == UserRole.ADMIN
        ])
        
        # Add tenant stats
        tenants = set()
        for user_data in auth_manager.users.values():
            tenants.add(user_data['user'].tenant_id)
        stats["tenants"] = len(tenants)
        
        return {
            "status": "success",
            "stats": stats,
            "timestamp": "2024-01-01T00:00:00Z"  # Add current timestamp in production
        }
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system stats")


# ================================
# GRAPH API ENDPOINTS (AUTHENTICATED)
# ================================

@app.get("/graph/overview")
async def graph_overview(current_user: User = Depends(get_current_user)):
    """Get knowledge graph overview"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            # Add tenant filtering for non-admin users
            tenant_filter = ""
            params = {}
            
            if current_user.role != UserRole.ADMIN:
                tenant_filter = "WHERE d.tenant_id = $tenant_id"
                params["tenant_id"] = current_user.tenant_id
            
            stats_query = f"""
            MATCH (d:Document) {tenant_filter}
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
            
            result = await session.run(stats_query, **params)
            stats = dict(await result.single()) if result else {}
            
            # Get top entities with tenant filtering
            top_entities_query = f"""
            MATCH (d:Document) {tenant_filter}
            MATCH (d)-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE e.canonical_name IS NOT NULL 
            AND e.canonical_name <> ''
            AND e.canonical_name <> 'Unknown'
            RETURN e.canonical_name as name, e.type as type, 
                   e.mention_count as mentions
            ORDER BY e.mention_count DESC, e.canonical_name
            LIMIT 10
            """
            
            result = await session.run(top_entities_query, **params)
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


@app.get("/entities")
async def list_entities(
    entity_type: str = None, 
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """List entities with tenant filtering"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            # Base tenant filtering
            tenant_filter = ""
            params = {"limit": limit}
            
            if current_user.role != UserRole.ADMIN:
                tenant_filter = """
                WHERE EXISTS {
                    MATCH (d:Document {tenant_id: $tenant_id})-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e)
                }
                """
                params["tenant_id"] = current_user.tenant_id
            
            base_where = """
            e.canonical_name IS NOT NULL 
            AND e.canonical_name <> ''
            AND e.canonical_name <> 'Unknown'
            """
            
            if entity_type:
                type_filter = "AND e.type = $entity_type"
                params["entity_type"] = entity_type.upper()
            else:
                type_filter = ""
            
            query = f"""
                MATCH (e:Entity)
                {tenant_filter}
                AND {base_where}
                {type_filter}
                RETURN e.canonical_name as name, e.type as type,
                       e.mention_count as mentions, e.surface_forms as forms,
                       e.normalized_name as normalized
                ORDER BY e.mention_count DESC, e.canonical_name
                LIMIT $limit
            """
            
            result = await session.run(query, **params)
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
async def list_relationships(limit: int = 20, current_user: User = Depends(get_current_user)):
    """List relationships with tenant filtering"""
    try:
        async with graphrag.neo4j_driver.session() as session:
            # Add tenant filtering for non-admin users
            tenant_filter = ""
            params = {"limit": limit}
            
            if current_user.role != UserRole.ADMIN:
                tenant_filter = """
                WHERE EXISTS {
                    MATCH (d:Document {tenant_id: $tenant_id})-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e1)
                }
                """
                params["tenant_id"] = current_user.tenant_id
            
            query = f"""
            MATCH (e1:Entity)-[r:RELATED]->(e2:Entity)
            {tenant_filter}
            AND e1.canonical_name IS NOT NULL AND e2.canonical_name IS NOT NULL
            RETURN e1.canonical_name as source, 
                   e2.canonical_name as target,
                   r.type as relationship,
                   r.confidence as confidence,
                   r.context as context
            ORDER BY r.confidence DESC
            LIMIT $limit
            """
            
            result = await session.run(query, **params)
            relationships = []
            async for record in result:
                rel_data = dict(record)
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)