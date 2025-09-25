import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import logging
import time

# Updated imports with error handling
try:
    from neo4j import AsyncGraphDatabase
    print("✅ Neo4j driver imported successfully")
except ImportError as e:
    print(f"❌ Neo4j import error: {e}")
    raise

try:
    import weaviate
    print("✅ Weaviate client imported successfully")
except ImportError as e:
    print(f"❌ Weaviate import error: {e}")
    raise

try:
    from sentence_transformers import SentenceTransformer
    print("✅ SentenceTransformers imported successfully")
except ImportError as e:
    print(f"❌ SentenceTransformers import error: {e}")
    print("Try: pip install sentence-transformers==2.3.1 transformers==4.36.2")
    raise

try:
    import spacy
    print("✅ spaCy imported successfully")
except ImportError as e:
    print(f"❌ spaCy import error: {e}")
    raise

try:
    import PyPDF2
    print("✅ PyPDF2 imported successfully")
except ImportError as e:
    print(f"❌ PyPDF2 import error: {e}")
    raise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GraphRAGSystem:
    def __init__(self):
        self.neo4j_driver = None
        self.weaviate_client = None
        self.embeddings_model = None
        self.nlp = None
        self.initialized = False
        
    async def initialize(self):
        """Initialize all components with proper error handling"""
        if self.initialized:
            logger.info("System already initialized")
            return
            
        logger.info("🚀 Initializing GraphRAG components...")
        
        # Initialize Neo4j with retry logic
        await self._init_neo4j()
        
        # Initialize Weaviate with retry logic
        await self._init_weaviate()
        
        # Initialize embedding model
        await self._init_embeddings()
        
        # Initialize spaCy for NER
        await self._init_nlp()
        
        self.initialized = True
        logger.info("✅ GraphRAG system initialized successfully")

    async def _init_neo4j(self, max_retries=5):
        """Initialize Neo4j with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to Neo4j (attempt {attempt + 1}/{max_retries})")
                self.neo4j_driver = AsyncGraphDatabase.driver(
                    "bolt://neo4j:7687",
                    auth=("neo4j", "password123")
                )
                
                # Test connection
                async with self.neo4j_driver.session() as session:
                    await session.run("RETURN 1")
                
                logger.info("✅ Neo4j connected successfully")
                return
                
            except Exception as e:
                logger.warning(f"Neo4j connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to connect to Neo4j after {max_retries} attempts")

    async def _init_weaviate(self, max_retries=5):
        """Initialize Weaviate with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to Weaviate (attempt {attempt + 1}/{max_retries})")
                self.weaviate_client = weaviate.Client("http://weaviate:8080")
                
                # Test connection
                self.weaviate_client.schema.get()
                
                # Create schema if it doesn't exist
                await self._create_weaviate_schema()
                
                logger.info("✅ Weaviate connected successfully")
                return
                
            except Exception as e:
                logger.warning(f"Weaviate connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"Failed to connect to Weaviate after {max_retries} attempts")

    async def _create_weaviate_schema(self):
        """Create Weaviate schema for document chunks"""
        schema = {
            "classes": [
                {
                    "class": "DocumentChunk",
                    "vectorizer": "none",  # We'll provide our own vectors
                    "properties": [
                        {"name": "content", "dataType": ["text"]},
                        {"name": "source", "dataType": ["string"]},
                        {"name": "chunk_id", "dataType": ["string"]},
                        {"name": "tenant_id", "dataType": ["string"]},
                        {"name": "chunk_index", "dataType": ["int"]},
                    ],
                }
            ]
        }
        
        try:
            existing_classes = self.weaviate_client.schema.get()["classes"]
            class_names = [cls["class"] for cls in existing_classes]
            
            if "DocumentChunk" not in class_names:
                self.weaviate_client.schema.create(schema)
                logger.info("✅ Created Weaviate schema")
            else:
                logger.info("✅ Weaviate schema already exists")
                
        except Exception as e:
            logger.error(f"Error creating Weaviate schema: {e}")
            raise

    async def _init_embeddings(self):
        """Initialize embedding model with error handling"""
        try:
            logger.info("Loading embedding model (this may take a few minutes on first run)...")
            self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    async def _init_nlp(self):
        """Initialize spaCy model with fallback"""
        try:
            logger.info("Loading spaCy model...")
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("✅ spaCy model loaded successfully")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Using basic tokenizer.")
            # Create a basic pipeline for tokenization
            self.nlp = spacy.blank("en")
            logger.info("✅ Basic spaCy pipeline created")

    async def ingest_directory(self, directory_path: str):
        """Ingest all documents from a directory"""
        if not self.initialized:
            await self.initialize()
            
        path = Path(directory_path)
        if not path.exists():
            logger.error(f"Directory not found: {directory_path}")
            return
            
        files_processed = 0
        for file_path in path.glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.txt', '.pdf', '.md']:
                logger.info(f"📄 Processing: {file_path.name}")
                try:
                    await self.ingest_document(str(file_path))
                    files_processed += 1
                except Exception as e:
                    logger.error(f"❌ Failed to process {file_path.name}: {e}")
        
        logger.info(f"✅ Processed {files_processed} files from {path}")

    async def ingest_document(self, file_path: str):
        """Ingest a single document with comprehensive error handling"""
        try:
            # Extract text
            text = self._extract_text(file_path)
            if not text or len(text.strip()) < 10:
                logger.warning(f"No meaningful text extracted from {file_path}")
                return
            
            # Create chunks
            chunks = self._create_chunks(text, chunk_size=500)
            if not chunks:
                logger.warning(f"No chunks created from {file_path}")
                return
            
            # Extract entities and create graph
            await self._create_knowledge_graph(file_path, text, chunks)
            
            # Create embeddings and store in vector DB
            await self._create_embeddings(file_path, chunks)
            
            logger.info(f"✅ Successfully processed {Path(file_path).name} ({len(chunks)} chunks)")
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path}: {e}")
            raise

    def _extract_text(self, file_path: str) -> str:
        """Extract text from different file formats with error handling"""
        path = Path(file_path)
        
        try:
            if path.suffix.lower() == '.pdf':
                with open(file_path, 'rb') as file:
                    pdf = PyPDF2.PdfReader(file)
                    text = ""
                    for page_num, page in enumerate(pdf.pages):
                        try:
                            text += page.extract_text() + "\n"
                        except Exception as e:
                            logger.warning(f"Error extracting page {page_num} from {path.name}: {e}")
                    return text.strip()
            else:
                # Handle .txt, .md files
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read().strip()
                    
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""

    def _create_chunks(self, text: str, chunk_size: int = 500) -> List[str]:
        """Split text into overlapping chunks"""
        if not text:
            return []
            
        words = text.split()
        if len(words) < 10:  # Skip very short texts
            return []
            
        chunks = []
        overlap = 50
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if len(chunk.strip()) > 20:  # Only add meaningful chunks
                chunks.append(chunk.strip())
        
        return chunks

    async def _create_knowledge_graph(self, file_path: str, full_text: str, chunks: List[str]):
        """Create knowledge graph with comprehensive error handling"""
        try:
            async with self.neo4j_driver.session() as session:
                # Create document node
                doc_name = Path(file_path).name
                await session.run(
                    "MERGE (d:Document {name: $name}) "
                    "SET d.path = $path, d.content_preview = substring($text, 0, 200), "
                    "d.processed_at = datetime()",
                    name=doc_name, path=file_path, text=full_text
                )
                
                # Process chunks and extract entities
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{doc_name}_chunk_{i}"
                    
                    # Create chunk node
                    await session.run(
                        "MATCH (d:Document {name: $doc_name}) "
                        "MERGE (c:Chunk {id: $chunk_id}) "
                        "SET c.content = $content, c.index = $index, c.created_at = datetime() "
                        "MERGE (d)-[:CONTAINS]->(c)",
                        doc_name=doc_name, chunk_id=chunk_id, content=chunk, index=i
                    )
                    
                    # Extract entities using spaCy (if available)
                    if self.nlp and hasattr(self.nlp, 'pipe'):
                        try:
                            doc = self.nlp(chunk[:1000])  # Limit text length for performance
                            for ent in doc.ents:
                                if ent.label_ in ["PERSON", "ORG", "GPE", "EVENT", "MONEY", "PRODUCT"]:
                                    await session.run(
                                        "MATCH (c:Chunk {id: $chunk_id}) "
                                        "MERGE (e:Entity {name: $name, type: $type}) "
                                        "MERGE (c)-[:MENTIONS]->(e)",
                                        chunk_id=chunk_id, name=ent.text.strip(), type=ent.label_
                                    )
                        except Exception as e:
                            logger.warning(f"Entity extraction failed for chunk {i}: {e}")
                            
        except Exception as e:
            logger.error(f"Error creating knowledge graph for {file_path}: {e}")
            raise

    async def _create_embeddings(self, file_path: str, chunks: List[str]):
        """Create embeddings and store in Weaviate with error handling"""
        try:
            doc_name = Path(file_path).name
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_name}_chunk_{i}"
                
                try:
                    # Generate embedding
                    embedding = self.embeddings_model.encode(chunk).tolist()
                    
                    # Store in Weaviate
                    self.weaviate_client.data_object.create(
                        {
                            "content": chunk,
                            "source": doc_name,
                            "chunk_id": chunk_id,
                            "tenant_id": "default",
                            "chunk_index": i
                        },
                        "DocumentChunk",
                        vector=embedding
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to create embedding for chunk {i} of {doc_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error creating embeddings for {file_path}: {e}")
            raise

    async def query(self, question: str) -> Dict[str, Any]:
        """Query the GraphRAG system with comprehensive error handling"""
        try:
            if not self.initialized:
                await self.initialize()
            
            logger.info(f"🔍 Processing query: {question[:50]}...")
            
            # Step 1: Vector similarity search
            vector_results = await self._vector_search(question)
            
            # Step 2: Graph-based search
            graph_results = await self._graph_search(question)
            
            # Step 3: Generate answer
            answer = await self._generate_answer(question, vector_results, graph_results)
            
            return {
                "question": question,
                "answer": answer,
                "sources": {
                    "vector_matches": len(vector_results),
                    "graph_entities": len(graph_results),
                    "top_chunks": [
                        {
                            "content": item.get("content", "")[:100] + "...",
                            "source": item.get("source", "unknown")
                        } 
                        for item in vector_results[:3]
                    ]
                },
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error processing query '{question}': {e}")
            return {
                "question": question,
                "answer": f"Sorry, I encountered an error processing your question: {str(e)}",
                "sources": {"error": str(e)},
                "status": "error"
            }

    async def _vector_search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for similar chunks using vector embeddings"""
        try:
            query_embedding = self.embeddings_model.encode(query).tolist()
            
            result = self.weaviate_client.query.get("DocumentChunk", ["content", "source", "chunk_id", "chunk_index"]) \
                .with_near_vector({"vector": query_embedding}) \
                .with_limit(limit) \
                .do()
            
            chunks = result.get("data", {}).get("Get", {}).get("DocumentChunk", [])
            logger.info(f"Found {len(chunks)} similar chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    async def _graph_search(self, query: str) -> List[Dict]:
        """Search for relevant entities in the knowledge graph"""
        try:
            async with self.neo4j_driver.session() as session:
                # Extract potential entities from the query
                query_words = query.lower().split()
                search_terms = [word for word in query_words if len(word) > 2]
                
                if not search_terms:
                    return []
                
                # Search for entities that match query terms
                result = await session.run(
                    "MATCH (e:Entity) "
                    "WHERE any(term in $terms WHERE toLower(e.name) CONTAINS term) "
                    "OPTIONAL MATCH (e)<-[:MENTIONS]-(c:Chunk)<-[:CONTAINS]-(d:Document) "
                    "RETURN e.name as entity, e.type as type, "
                    "collect(DISTINCT d.name) as documents, count(c) as mentions "
                    "ORDER BY mentions DESC "
                    "LIMIT 5",
                    terms=search_terms
                )
                
                entities = [record.data() async for record in result]
                logger.info(f"Found {len(entities)} relevant entities")
                return entities
                
        except Exception as e:
            logger.error(f"Graph search error: {e}")
            return []

    async def _generate_answer(self, question: str, vector_results: List, graph_results: List) -> str:
        """Generate answer using retrieved context"""
        try:
            if not vector_results and not graph_results:
                return "I couldn't find any relevant information to answer your question. Please try rephrasing or ask about topics covered in the uploaded documents."
            
            # Build context from vector results
            context_parts = []
            if vector_results:
                context_parts.append("Relevant information from documents:")
                for i, item in enumerate(vector_results[:3]):
                    content = item.get("content", "")
                    source = item.get("source", "unknown")
                    # Limit context length
                    snippet = content[:300] + "..." if len(content) > 300 else content
                    context_parts.append(f"{i+1}. From {source}: {snippet}")
            
            # Build context from graph results
            if graph_results:
                entities = [item["entity"] for item in graph_results if item.get("entity")]
                if entities:
                    context_parts.append(f"\nRelated entities mentioned in documents: {', '.join(entities[:5])}")
            
            # Generate a simple template-based answer
            answer = f"Based on the available information:\n\n{chr(10).join(context_parts)}\n\n"
            answer += f"This response is based on {len(vector_results)} document segments"
            if graph_results:
                answer += f" and {len(graph_results)} related entities"
            answer += " from the knowledge base."
            
            return answer
            
        except Exception as e:
            logger.error(f"Answer generation error: {e}")
            return f"I found some relevant information but encountered an error generating the response: {str(e)}"

    async def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            stats = {"status": "healthy"}
            
            # Neo4j stats
            if self.neo4j_driver:
                async with self.neo4j_driver.session() as session:
                    doc_result = await session.run("MATCH (d:Document) RETURN count(d) as count")
                    doc_count = await doc_result.single()
                    stats["documents"] = doc_count["count"] if doc_count else 0
                    
                    chunk_result = await session.run("MATCH (c:Chunk) RETURN count(c) as count")
                    chunk_count = await chunk_result.single()
                    stats["chunks"] = chunk_count["count"] if chunk_count else 0
                    
                    entity_result = await session.run("MATCH (e:Entity) RETURN count(e) as count")
                    entity_count = await entity_result.single()
                    stats["entities"] = entity_count["count"] if entity_count else 0
            
            # Weaviate stats
            if self.weaviate_client:
                try:
                    result = self.weaviate_client.query.aggregate("DocumentChunk").with_meta_count().do()
                    vector_count = result.get("data", {}).get("Aggregate", {}).get("DocumentChunk", [{}])[0].get("meta", {}).get("count", 0)
                    stats["vector_embeddings"] = vector_count
                except:
                    stats["vector_embeddings"] = "unknown"
            
            return stats
            
        except Exception as e:
            return {"status": "error", "message": str(e)}