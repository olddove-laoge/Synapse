import json

from packages.graph.manual_chunk_service import LocalManualChunkService
from packages.graph.notes_service import LocalNodeNoteService
from packages.graph.service import LocalGraphService
from packages.llm.deepseek_client import DeepSeekClient
from packages.retrieval.service import LocalEmbeddingRetrievalService


class LearningPathAgent:
    def __init__(self) -> None:
        self.graph_service = LocalGraphService()
        self.retrieval_service = LocalEmbeddingRetrievalService()
        self.manual_chunk_service = LocalManualChunkService()
        self.note_service = LocalNodeNoteService()
        self.llm = DeepSeekClient()

    def classify_question(self, question: str) -> str:
        lowered = question.lower()
        if any(token in lowered for token in ['why', 'how', 'prerequisite', 'dependency', '先学', '前置', '为什么', '如何']):
            return 'path_analysis'
        if any(token in lowered for token in ['difference', 'compare', '区别', '对比']):
            return 'comparison'
        return 'direct'

    def should_link_existing_notes(self, question: str, retrieved_passages: list[dict]) -> bool:
        if not retrieved_passages:
            return False
        lowered = question.lower()
        if any(token in lowered for token in ['相关', '联系', '笔记', 'related', 'connection']):
            return True
        return len(retrieved_passages) >= 2

    def run_node_learning_agent(self, graph_id: str, node_id: str, question: str) -> dict:
        mode = self.classify_question(question)
        focus = self.graph_service.focus_view(graph_id=graph_id, node_id=node_id)
        center_node = self.graph_service.summarize_node(graph_id=graph_id, node_id=node_id)
        retrieval = self.retrieval_service.retrieve_for_node(graph_id=graph_id, node_id=node_id, query=question)
        retrieved_passages = [p.model_dump() for p in retrieval.retrieved_passages]

        local_titles = [node.title for node in focus.nodes[:8]]
        related_chunks = []
        related_notes = []
        if self.should_link_existing_notes(question, retrieved_passages):
            manual_chunks = self.manual_chunk_service.list_chunks(graph_id)
            related_chunks = [
                chunk.model_dump()
                for chunk in manual_chunks
                if node_id in chunk.linked_node_ids
            ][:5]
            related_notes = [note.model_dump() for note in self.note_service.list_notes(node_id)[:5]]

        learning_hint = None
        learning_path_node_ids = []
        learning_path_edge_ids = []
        if mode == 'path_analysis':
            facts = self.retrieval_service.list_facts(graph_id)
            retrieved_chunk_ids = {item['chunk_id'] for item in retrieved_passages}
            supporting_facts = [fact for fact in facts if any(chunk_id in retrieved_chunk_ids for chunk_id in fact.chunk_ids)]
            node_score: dict[str, float] = {}
            edge_score: dict[str, float] = {}
            for idx, passage in enumerate(retrieved_passages, start=1):
                base = 1.0 / idx
                for fact in supporting_facts:
                    if passage['chunk_id'] not in fact.chunk_ids:
                        continue
                    node_score[fact.source_node_id] = node_score.get(fact.source_node_id, 0.0) + base
                    node_score[fact.target_node_id] = node_score.get(fact.target_node_id, 0.0) + base
                    edge_score[fact.fact_id] = edge_score.get(fact.fact_id, 0.0) + base
            node_score[node_id] = max(node_score.get(node_id, 0.0), 10.0)

            sorted_nodes = sorted(node_score.items(), key=lambda x: x[1], reverse=True)
            if sorted_nodes:
                max_score = sorted_nodes[0][1]
                threshold = max_score * 0.18
                learning_path_node_ids = [nid for nid, score in sorted_nodes if score >= threshold]
                if node_id not in learning_path_node_ids:
                    learning_path_node_ids.insert(0, node_id)
            else:
                learning_path_node_ids = [node_id]

            sorted_edges = sorted(edge_score.items(), key=lambda x: x[1], reverse=True)
            if sorted_edges:
                max_edge = sorted_edges[0][1]
                edge_threshold = max_edge * 0.15
                learning_path_edge_ids = [eid for eid, score in sorted_edges if score >= edge_threshold]

            node_title_map = {node.node_id: node.title for node in self.graph_service.graph_view(graph_id).nodes}
            prompt = (
                'You are a recursive learning coach. A graph retrieval system has already identified a learning subgraph that may help answer the user question. '
                'Explain what should be learned first and propose 2-4 subquestions. '
                'Return JSON only with keys reasoning and subquestions.\n\n'
                f"Focus node: {center_node.title}\n"
                f"User question: {question}\n"
                f"Learning subgraph candidate: {[node_title_map.get(nid, nid) for nid in learning_path_node_ids]}\n"
            )
            raw_hint = self.llm.chat(prompt)
            try:
                parsed = json.loads(raw_hint)
                subquestions = parsed.get('subquestions', [])
                reasoning = parsed.get('reasoning', '')
                learning_hint = '建议先理解：\n' + '\n'.join([f"{idx + 1}. {q}" for idx, q in enumerate(subquestions)])
                if reasoning:
                    learning_hint += f"\n\n原因：{reasoning}"
            except Exception:
                learning_hint = raw_hint

        evidence_block = '\n\n'.join([f"[{idx + 1}] {item['content']}" for idx, item in enumerate(retrieved_passages[:4])])
        note_block = '\n'.join([f"- {item['content']}" for item in related_notes[:3]]) or '无'
        chunk_block = '\n'.join([f"- {item['title']}: {item['content'][:120]}" for item in related_chunks[:3]]) or '无'
        answer_prompt = (
            'You are a learning-oriented graph notebook assistant. '
            'Answer the main user question first using the retrieved evidence and the focus node summary. '
            'If a learning path hint exists, briefly incorporate it as study advice after the main answer. '
            'Keep the answer clear and useful for learning.\n\n'
            f"Focus node: {center_node.title}\n"
            f"Focus summary: {center_node.summary}\n"
            f"Nearby concepts: {local_titles}\n"
            f"Retrieved evidence:\n{evidence_block}\n\n"
            f"Related knowledge blocks:\n{chunk_block}\n\n"
            f"Related notes:\n{note_block}\n\n"
            f"Learning hint:\n{learning_hint or '无'}\n\n"
            f"User question: {question}"
        )
        final_answer = self.llm.chat(answer_prompt)

        full_graph = self.graph_service.graph_view(graph_id)
        learning_path_nodes = [
            node.model_dump()
            for node in full_graph.nodes
            if node.node_id in set(learning_path_node_ids)
        ]
        learning_path_edges = [
            edge.model_dump()
            for edge in full_graph.edges
            if edge.edge_id in set(learning_path_edge_ids)
            or (edge.source_node_id in set(learning_path_node_ids) and edge.target_node_id in set(learning_path_node_ids))
        ]

        return {
            'mode': mode,
            'learning_hint': learning_hint,
            'answer': final_answer,
            'retrieved_passages': retrieved_passages,
            'related_chunks': related_chunks,
            'related_notes': related_notes,
            'focus': focus.model_dump(),
            'learning_path_nodes': learning_path_nodes,
            'learning_path_edges': learning_path_edges,
        }
