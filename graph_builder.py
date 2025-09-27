import asyncio
import re
from typing import Dict, List, Set, Tuple, Optional
import logging
from collections import defaultdict, Counter
from dataclasses import dataclass

import spacy
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


@dataclass
class EntityMention:
    """Represents an entity mention in text"""

    text: str
    label: str
    start_char: int
    end_char: int
    chunk_id: str
    confidence: float = 1.0
    normalized_form: str | None = None


@dataclass
class EntityRelationship:
    """Represents a relationship between two entities"""

    source_entity: str
    target_entity: str
    relation_type: str
    context: str
    confidence: float
    chunk_id: str


class AdvancedGraphBuilder:
    """Advanced knowledge graph builder with entity linking and relationship extraction"""

    def __init__(self, neo4j_driver, nlp_model=None):
        self.driver = neo4j_driver
        self.nlp = nlp_model

        # Relationship patterns for different entity types
        self.relationship_patterns = {
            ("PERSON", "ORG"): [
                (r"(works?\s+(?:at|for))", "WORKS_FOR"),
                (r"(founded|created|started)", "FOUNDED"),
                (r"(CEO|CTO|CFO|president|director)", "LEADS"),
            ],
            ("ORG", "ORG"): [
                (r"(partner(?:ed|ship)?)", "PARTNERS_WITH"),
                (r"(acquired|bought)", "ACQUIRED"),
                (r"(collaborat)", "COLLABORATES_WITH"),
            ],
            ("ORG", "MONEY"): [
                (r"(revenue|income|sales)", "HAS_REVENUE"),
                (r"(invested|funding|raised)", "RAISED_FUNDING"),
            ],
            ("PERSON", "PERSON"): [
                (r"(co-founded|founded)", "CO_FOUNDED_WITH"),
                (r"(reports\s+to)", "REPORTS_TO"),
            ],
        }

        # Entity normalization rules
        self.normalization_rules = {
            "ORG": self._normalize_organization,
            "PERSON": self._normalize_person,
            "GPE": self._normalize_location,
            "MONEY": self._normalize_money,
        }

    async def build_enhanced_graph(
        self, document_hash: str, chunks: List, metadata: Dict
    ):
        """Build enhanced knowledge graph with entities, relationships, and document structure"""
        try:
            logger.info(
                f"🔗 Building enhanced graph for document: {metadata.get('title', 'Unknown')}"
            )

            # Step 1: Extract all entity metions
            all_entities = await self._extract_all_entities(chunks)

            # Step 2: Normalize and deduplicate entities
            normalized_entities = await self._normalize_entities(all_entities)

            # Step 3: Extract relationships between entities
            relationships = await self._extract_relationships(
                chunks, normalized_entities
            )

            # Step 4: Store in Neo4j with enhanced schema
            await self._store_enhanced_graph(
                document_hash, chunks, normalized_entities, relationships, metadata
            )

            # Step 5: Create document-level topic nodes
            await self._create_topic_nodes(document_hash, normalized_entities, metadata)

            logger.info(
                f"✅ Enhanced graph created: {len(normalized_entities)} entities, {len(relationships)} relationships"
            )

            return {
                "entities": len(normalized_entities),
                "relationships": len(relationships),
                "chunks": len(chunks),
            }

        except Exception as e:
            logger.error(f"❌ Error building enhanced graph: {e}")
            raise

    async def _extract_all_entities(self, chunks: List) -> List[EntityMention]:
        """Extract all entity mentions from all chunks"""
        all_entities = []

        if not self.nlp:
            logger.warning("⚠️ NLP model not loaded, skipping entity extraction")
            return all_entities

        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{i}"
            content = (
                chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
            )

            try:
                # Process with spaCy
                doc = self.nlp(content[:2000])  # Limit to first 20k chars

                for ent in doc.ents:
                    if ent.label_ in [
                        "PERSON",
                        "ORG",
                        "GPE",
                        "MONEY",
                        "PRODUCT",
                        "EVENT",
                        "DATE",
                    ]:
                        mention = EntityMention(
                            text=ent.text.strip(),
                            label=ent.label_,
                            start_char=ent.start_char,
                            end_char=ent.end_char,
                            chunk_id=chunk_id,
                            confidence=1.0,
                            normalized_form=None,
                        )
                        all_entities.append(mention)

            except Exception as e:
                logger.warning(f"Entity extraction failed for chunk {i}: {e}")

        logger.info(f"Extracted {len(all_entities)} entity mentions")
        return all_entities

    async def _normalize_entities(
        self, entities: List[EntityMention]
    ) -> Dict[str, EntityMention]:
        """Normalize and group similar entities together"""
        normalized_groups = defaultdict(list)

        for entity in entities:
            # Apply normalization rules based on entity type
            normalizer = self.normalization_rules.get(
                entity.label, self._default_normalize
            )
            normalized_form = normalizer(entity.text)
            entity.normalized_form = normalized_form

            # Group by normalized form and label
            key = f"{entity.label}:{normalized_form}"
            normalized_groups[key].append(entity)

        # For each group, select the most common surface form as canonical
        canonical_entities = {}
        for key, mentions in normalized_groups.items():
            if len(mentions) >= 1:
                # Find most common surface form
                surface_forms = Counter(mention.text for mention in mentions)
                canonical_form = surface_forms.most_common(1)[0][0]

                canonical_entities[key] = {
                    "canonical_name": canonical_form,
                    "normalized_name": mentions[0].normalized_form,
                    "entity_type": mentions[0].label,
                    "mentions": mentions,
                    "mention_count": len(mentions),
                }

        logger.info(f"Normalized to {len(canonical_entities)} unique entities")
        return canonical_entities

    def _normalize_organization(self, org_name: str) -> str:
        """Normalize organization names"""
        name = org_name.strip()
        # Remove common suffixes
        suffixes = [
            "Inc.",
            "Corp.",
            "Corporation",
            "Ltd.",
            "LLC",
            "Co.",
            "Company",
            "GmbH",
            "AG",
            "S.A.",
            "Pvt. Ltd.",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: len(suffix)].strip()
        return name.lower()

    def _normalize_person(self, person_name: str) -> str:
        """Normalize person names"""
        name = person_name.strip()
        # Handle titles
        titles = ["Dr.", "Mr.", "Ms.", "Mrs.", "Prof.", "CEO", "CTO", "CFO"]
        for title in titles:
            name = name.replace(title, "").strip()
        return name.lower()

    def _normalize_location(self, location: str) -> str:
        """Normalize location names"""
        return location.strip().lower()

    def _normalize_money(self, money: str) -> str:
        """Normalize money amounts"""
        # Extract numeric value and convert to standard format
        numbers = re.findall(r"[\d,]_", money)
        if numbers:
            return numbers[0].replace(",", "")
        return money.strip().lower()

    def _default_normalize(self, text: str) -> str:
        """Default normalization"""
        return text.strip().lower()

    async def _extract_relationships(
        self, chunks: List, entities: Dict
    ) -> List[EntityRelationship]:
        """Extract relationships between entities using simple keyword matching"""
        relationships = []

        # Create lookup for entity mentions by chunk
        chunk_entities = defaultdict(list)
        for entity_key, entity_data in entities.items():
            for mention in entity_data["mentions"]:
                chunk_entities[mention.chunk_id].append(
                    {
                        "key": entity_key,
                        "mention": mention,
                        "canonical": entity_data["canonical_name"],
                        "type": entity_data["entity_type"],
                    }
                )

        # Simple keyword-based relationship detection
        relationship_keywords = {
            "WORKS_FOR": ["works for", "works at", "employed by", "employee of"],
            "FOUNDED": ["founded", "created", "started", "established"],
            "LEADS": [
                "CEO of",
                "CTO of",
                "CFO of",
                "leads",
                "director of",
                "president of",
            ],
            "PARTNERS_WITH": [
                "partnership with",
                "partnered with",
                "collaboration with",
            ],
            "RAISED_FUNDING": [
                "raised funding",
                "received investment",
                "funding round",
            ],
            "CO_FOUNDED": ["co-founded", "founded together", "co-founded with"],
        }

        # Process each chunk for relationships
        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{i}"
            content = (
                chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
            )
            content_lower = content.lower()
            chunk_ents = chunk_entities.get(chunk_id, [])

            # Look for specific relationship keywords
            for relation_type, keywords in relationship_keywords.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        # Find entities mentioned near this keyword
                        keyword_pos = content_lower.find(keyword)
                        context_start = max(0, keyword_pos - 100)
                        context_end = min(
                            len(content), keyword_pos + len(keyword) + 100
                        )
                        context = content[context_start:context_end]
                        context_lower = context.lower()

                        # Find entities in this context
                        context_entities = []
                        for ent in chunk_ents:
                            if ent["canonical"].lower() in context_lower:
                                context_entities.append(ent)

                        # Create relationships between entities in context
                        if len(context_entities) >= 2:
                            for i, source_ent in enumerate(context_entities):
                                for target_ent in context_entities[i + 1 :]:
                                    relationship = EntityRelationship(
                                        source_entity=source_ent["canonical"],
                                        target_entity=target_ent["canonical"],
                                        relation_type=relation_type,
                                        context=context.strip(),
                                        confidence=0.7,
                                        chunk_id=chunk_id,
                                    )
                                    relationships.append(relationship)

            # Extract general co-occurrence relationships
            if len(chunk_ents) > 1:
                for i, ent1 in enumerate(chunk_ents):
                    for ent2 in chunk_ents[i + 1 :]:
                        relationship = EntityRelationship(
                            source_entity=ent1["canonical"],
                            target_entity=ent2["canonical"],
                            relation_type="CO_MENTIONED",
                            context=(
                                content[:200] + "..." if len(content) > 200 else content
                            ),
                            confidence=0.3,
                            chunk_id=chunk_id,
                        )
                        relationships.append(relationship)

        # Deduplicate relationships
        unique_relationships = []
        seen = set()
        for rel in relationships:
            key = f"{rel.source_entity}|{rel.relation_type}|{rel.target_entity}"
            reverse_key = f"{rel.target_entity}|{rel.relation_type}|{rel.source_entity}"

            if key not in seen and reverse_key not in seen:
                seen.add(key)
                unique_relationships.append(rel)

        logger.info(f"Extracted {len(unique_relationships)} unique relationships")
        return unique_relationships

    async def _store_enhanced_graph(
        self,
        document_hash: str,
        chunks: List,
        entities: Dict,
        relationships: List,
        metadata: Dict,
    ):
        """Store enhanced graph structure in Neo4j with improved error handling"""
        try:
            async with self.driver.session() as session:
                # Create document node with metadata
                await session.run(
                    """
                    MERGE (d:Document {hash: $hash})
                    SET d.title = $title,
                        d.file_type = $file_type,
                        d.word_count = $word_count,
                        d.chunk_count = $chunk_count,
                        d.processed_at = datetime()
                """,
                    hash=document_hash,
                    title=metadata.get("title", "Unknown"),
                    file_type=metadata.get("file_type", "unknown"),
                    word_count=metadata.get("word_count", 0),
                    chunk_count=len(chunks),
                )

                logger.info(f"Created document node: {metadata.get('title')}")

                # Create chunk nodes
                for i, chunk in enumerate(chunks):
                    chunk_data = (
                        chunk
                        if isinstance(chunk, dict)
                        else {"content": str(chunk), "index": i}
                    )
                    chunk_id = f"{document_hash}_chunk_{i}"
                    content = chunk_data.get("content", "")

                    await session.run(
                        """
                        MATCH (d:Document {hash: $doc_hash})
                        MERGE (c:Chunk {id: $chunk_id})
                        SET c.content = $content,
                            c.index = $index,
                            c.word_count = $word_count,
                            c.created_at = datetime()
                        MERGE (d)-[:CONTAINS {sequence: $index}]->(c)
                    """,
                        doc_hash=document_hash,
                        chunk_id=chunk_id,
                        content=content,
                        index=i,
                        word_count=len(content.split()),
                    )

                logger.info(f"Created {len(chunks)} chunk nodes")

                # Create entity nodes with enhanced properties
                entity_count = 0
                for entity_key, entity_data in entities.items():
                    try:
                        # Ensure we have valid data
                        canonical_name = entity_data.get("canonical_name", "Unknown")
                        entity_type = entity_data.get("entity_type", "UNKNOWN")
                        mention_count = entity_data.get("mention_count", 0)
                        normalized_name = entity_data.get(
                            "normalized_name", canonical_name.lower()
                        )

                        # Get surface forms safely
                        mentions = entity_data.get("mentions", [])
                        surface_forms = []
                        for mention in mentions:
                            if hasattr(mention, "text"):
                                surface_forms.append(mention.text)
                            elif isinstance(mention, dict):
                                surface_forms.append(mention.get("text", ""))

                        if not canonical_name or canonical_name == "Unknown":
                            logger.warning(
                                f"Skipping entity with invalid name: {entity_key}"
                            )
                            continue

                        await session.run(
                            """
                            MERGE (e:Entity {canonical_name: $canonical_name, type: $entity_type})
                            SET e.normalized_name = $normalized_name,
                                e.mention_count = $mention_count,
                                e.surface_forms = $surface_forms,
                                e.last_updated = datetime()
                        """,
                            canonical_name=canonical_name,
                            entity_type=entity_type,
                            normalized_name=normalized_name,
                            mention_count=mention_count,
                            surface_forms=surface_forms,
                        )

                        entity_count += 1

                        # Link entities to chunks where they're mentioned
                        for mention in mentions:
                            try:
                                if hasattr(mention, "chunk_id"):
                                    chunk_index = mention.chunk_id.replace("chunk_", "")
                                    full_chunk_id = (
                                        f"{document_hash}_chunk_{chunk_index}"
                                    )

                                    await session.run(
                                        """
                                        MATCH (e:Entity {canonical_name: $canonical_name, type: $entity_type})
                                        MATCH (c:Chunk {id: $chunk_id})
                                        MERGE (c)-[r:MENTIONS]->(e)
                                        SET r.surface_form = $surface_form,
                                            r.confidence = $confidence
                                    """,
                                        canonical_name=canonical_name,
                                        entity_type=entity_type,
                                        chunk_id=full_chunk_id,
                                        surface_form=getattr(mention, "text", ""),
                                        confidence=getattr(mention, "confidence", 1.0),
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to link mention: {e}")

                    except Exception as e:
                        logger.warning(f"Failed to create entity {entity_key}: {e}")
                        continue

                logger.info(f"Created {entity_count} entity nodes")

                # Create relationship edges
                relationship_count = 0
                for relationship in relationships:
                    try:
                        await session.run(
                            """
                            MATCH (e1:Entity {canonical_name: $source})
                            MATCH (e2:Entity {canonical_name: $target})
                            MERGE (e1)-[r:RELATED {type: $rel_type}]->(e2)
                            SET r.context = $context,
                                r.confidence = $confidence
                        """,
                            source=relationship.source_entity,
                            target=relationship.target_entity,
                            rel_type=relationship.relation_type,
                            context=relationship.context[:500],  # Limit context length
                            confidence=relationship.confidence,
                        )
                        relationship_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to create relationship: {e}")

                logger.info(f"Created {relationship_count} relationships")

        except Exception as e:
            logger.error(f"Error storing enhanced graph: {e}")
            raise

    async def _create_topic_nodes(
        self, document_hash: str, entities: Dict, metadata: Dict
    ):
        """Create topic nodes based on entity clustering"""
        try:
            # Group entities by type to create topic clusters
            entity_types = defaultdict(list)
            for entity_data in entities.values():
                entity_types[entity_data["entity_type"]].append(
                    entity_data["canonical_name"]
                )

            async with self.driver.session() as session:
                # Create topic nodes for entity clusters
                for entity_type, entity_names in entity_types.items():
                    if (
                        len(entity_names) >= 2
                    ):  # Only create topics with multiple entities
                        topic_name = f"{metadata.get('title', 'Document')} - {entity_type.title()} Topics"

                        await session.run(
                            """
                            MATCH (d:Document {hash: $doc_hash})
                            MERGE (t:Topic {name: $topic_name, type: $entity_type})
                            SET t.entity_count = $entity_count,
                                t.document_hash = $doc_hash
                            MERGE (d)-[:HAS_TOPIC]->(t)
                            """,
                            doc_hash=document_hash,
                            topic_name=topic_name,
                            entity_type=entity_type,
                            entity_count=len(entity_names),
                        )

                        # Link entities to topic
                        for entity_name in entity_names:
                            await session.run(
                                """
                                MATCH (t:Topic {name: $topic_name})
                                MATCH (e:Entity {canonical_name: $entity_name, type: $entity_type})
                                MERGE (t)-[:INCLUDES]->(e)
                                """,
                                topic_name=topic_name,
                                entity_name=entity_name,
                                entity_type=entity_type,
                            )
        except Exception as e:
            logger.error(f"❌ Error creating topic nodes: {e}")

    async def get_entity_neighborhood(
        self, entity_name: str, max_depth: int = 2
    ) -> Dict:
        """Get the neighborhood of an entity for visualization"""
        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity {canonical_name: $entity_name})
                    OPTIONAL MATCH path = (e)-[r:RELATED*1..$max_depth]-(connected)
                    OPTIONAL MATCH (e)<-[:MENTIONS]-(c:Chunk)-[:CONTAINS]-(d:Document)
                    RETURN e, collect(DISTINCT path) as paths,
                    collect(DISTINCT {chunk_id: c.id, document: d.title}) as sources
                    """,
                    entity_name=entity_name,
                    max_depth=max_depth,
                )

                record = await result.single()
                if not record:
                    return {"entity": None, "connections": [], "sources": []}

                # Process the graph data for visualization
                nodes = set()
                edges = []

                # Add central entity
                central_entity = dict(record["e"])
                nodes.add((central_entity["canonical_name"], central_entity["type"]))

                # Process paths to connected entities
                for path in record["paths"] or []:
                    if path:
                        for i in range(len(path.nodes)):
                            node = dict(path.nodes[i])
                            nodes.add((node["canonical_name"], node["type"]))

                            if i < len(path.relationships):
                                rel = dict(path.relationships[i])
                                source_node = dict(path.nodes[i])
                                target_node = dict(path.nodes[i + 1])

                                edges.append(
                                    {
                                        "source": source_node["canonical_name"],
                                        "target": target_node["canonical_name"],
                                        "relationship": rel.get("type", "RELATED"),
                                        "confidence": rel.get("confidence", 0.5),
                                    }
                                )

                return {
                    "entity": entity_name,
                    "nodes": [{"name": name, "type": type_} for name, type_ in nodes],
                    "edges": edges,
                    "sources": record["sources"] or [],
                }

        except Exception as e:
            logger.error(f"❌ Error retrieving entity neighborhood: {e}")
            return {"entity": entity_name, "nodes": [], "edges": [], "sources": []}

    async def get_graph_stats(self) -> Dict:
        """Get statistics about the knowledge graph"""
        try:
            async with self.driver.session() as session:
                stats_query = """
                    MATCH (d:Document)
                    OPTIONAL MATCH (e:Entity)
                    OPTIONAL MATCH (c:Chunk)
                    OPTIONAL MATCH (t:Topic)
                    OPTIONAL MATCH ()-[r:RELATED]->()
                    RETURN count(DISTINCT d) as document_count,
                            count(DISTINCT e) as entities,
                            count(DISTINCT c) as chunks,
                            count(DISTINCT t) as topics,
                            count(DISTINCT r) as relationships
                """

                result = await session.run(stats_query)
                record = await result.single()

                return dict(record) if record else {}

        except Exception as e:
            logger.error(f"❌ Error retrieving graph stats: {e}")
            return {}
