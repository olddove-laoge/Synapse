from llama_index.core.llms import ChatMessage

from packages.graph.service import LocalGraphService
from packages.llm.deepseek_client import DeepSeekClient
from packages.retrieval.service import LocalEmbeddingRetrievalService


class LearningPathAgent:
    def __init__(self) -> None:
        self.graph_service = LocalGraphService()
        self.retrieval_service = LocalEmbeddingRetrievalService()
        self.llm = DeepSeekClient()

    def classify_question(self, question: str) -> str:
        lowered = question.lower()
        if any(token in lowered for token in ['why', 'how', 'prerequisite', 'dependency', '先学', '前置', '为什么', '如何']):
            return 'path_analysis'
        if any(token in lowered for token in ['difference', 'compare', '区别', '对比']):
            return 'comparison'
        return 'direct'

    def run_node_learning_agent(self, graph_id: str, node_id: str, question: str) -> dict:
        mode = self.classify_question(question)
        focus = self.graph_service.focus_view(graph_id=graph_id, node_id=node_id)
        retrieval = self.retrieval_service.retrieve_for_node(graph_id=graph_id, node_id=node_id, query=question)

        center_node = next((node for node in focus.nodes if node.node_id == node_id), None)
        local_titles = [node.title for node in focus.nodes[:8]]
        prompt = (
            'You are a recursive learning coach. '
            'Given a focus concept, a user question, and nearby graph concepts, decide whether the question needs prerequisite analysis and propose 2-4 subquestions that should be answered first. '
            'Return plain JSON with keys mode, reasoning, subquestions.\n\n'
            f"Focus node: {center_node.title if center_node else node_id}\n"
            f"User question: {question}\n"
            f"Nearby concepts: {local_titles}\n"
        )
        response = self.llm.chat(prompt)
        return {
            'mode': mode,
            'agent_output': response,
            'retrieved_passages': [p.model_dump() for p in retrieval.retrieved_passages],
        }
