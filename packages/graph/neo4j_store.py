from neo4j import GraphDatabase


class Neo4jGraphStore:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def verify_connection(self) -> None:
        with self.driver.session() as session:
            session.run("RETURN 1").single()

    def sync_graph_delta(self, graph_id: str, candidate_delta_id: str, delta: dict, evidence_chunk_ids: list[str]) -> None:
        node_rows = delta.get("nodes", [])
        edge_rows = delta.get("edges", [])
        with self.driver.session() as session:
            for node in node_rows:
                session.run(
                    """
                    MERGE (n:Entity {id: $node_id, graph_id: $graph_id})
                    SET n.title = $title,
                        n.node_type = $node_type,
                        n.status = $status,
                        n.candidate_delta_id = $candidate_delta_id
                    """,
                    node_id=node.get("node_id"),
                    graph_id=graph_id,
                    title=node.get("title", ""),
                    node_type=node.get("node_type", "Concept"),
                    status=node.get("status", "published"),
                    candidate_delta_id=candidate_delta_id,
                )

            for chunk_id in evidence_chunk_ids:
                session.run(
                    """
                    MERGE (p:Passage {id: $chunk_id, graph_id: $graph_id})
                    SET p.candidate_delta_id = $candidate_delta_id
                    """,
                    chunk_id=chunk_id,
                    graph_id=graph_id,
                    candidate_delta_id=candidate_delta_id,
                )

            for edge in edge_rows:
                session.run(
                    """
                    MATCH (a:Entity {id: $source_node_id, graph_id: $graph_id})
                    MATCH (b:Entity {id: $target_node_id, graph_id: $graph_id})
                    MERGE (a)-[r:REL {id: $edge_id, graph_id: $graph_id}]->(b)
                    SET r.relation_type = $relation_type,
                        r.status = $status,
                        r.candidate_delta_id = $candidate_delta_id
                    """,
                    source_node_id=edge.get("source_node_id"),
                    target_node_id=edge.get("target_node_id"),
                    edge_id=edge.get("edge_id"),
                    graph_id=graph_id,
                    relation_type=edge.get("relation_type", "related_to"),
                    status=edge.get("status", "published"),
                    candidate_delta_id=candidate_delta_id,
                )

                for chunk_id in evidence_chunk_ids:
                    session.run(
                        """
                        MATCH (p:Passage {id: $chunk_id, graph_id: $graph_id})
                        MATCH (a:Entity {id: $source_node_id, graph_id: $graph_id})
                        MATCH (b:Entity {id: $target_node_id, graph_id: $graph_id})
                        MERGE (p)-[:MENTIONS {graph_id: $graph_id}]->(a)
                        MERGE (p)-[:MENTIONS {graph_id: $graph_id}]->(b)
                        """,
                        chunk_id=chunk_id,
                        graph_id=graph_id,
                        source_node_id=edge.get("source_node_id"),
                        target_node_id=edge.get("target_node_id"),
                    )
