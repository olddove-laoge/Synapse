import os
import sys
import types
import importlib
from pathlib import Path

from dotenv import load_dotenv

from packages.contracts.document import ParsedChunk
from packages.contracts.graph import GraphDelta, CandidateNode, CandidateEdge, EvidenceItem


class HippoRAGOpenIEAdapter:
    def __init__(self) -> None:
        self._openie = None

    def _lazy_init(self):
        if self._openie is not None:
            return self._openie

        repo_root = Path(__file__).resolve().parents[2]
        load_dotenv(repo_root / ".env")

        if (not os.getenv("OPENAI_API_KEY")) and os.getenv("SYNAPSE_LLM_API_KEY"):
            os.environ["OPENAI_API_KEY"] = os.getenv("SYNAPSE_LLM_API_KEY", "")

        hipporag_src = repo_root / "HippoRAG" / "src"
        if str(hipporag_src) not in sys.path:
            sys.path.append(str(hipporag_src))

        hipporag_pkg = types.ModuleType("hipporag")
        hipporag_pkg.__path__ = [str(hipporag_src / "hipporag")]
        sys.modules.setdefault("hipporag", hipporag_pkg)

        BaseConfig = importlib.import_module("hipporag.utils.config_utils").BaseConfig
        CacheOpenAI = importlib.import_module("hipporag.llm.openai_gpt").CacheOpenAI
        OpenIE = importlib.import_module("hipporag.information_extraction.openie_openai").OpenIE

        cfg = BaseConfig()
        cfg.save_dir = str(repo_root / "data" / "hipporag_tmp")
        cfg.llm_name = os.getenv("SYNAPSE_LLM_MODEL", "deepseek-chat")
        cfg.llm_base_url = os.getenv("SYNAPSE_LLM_API_BASE", "https://api.deepseek.com/v1")

        llm_model = CacheOpenAI.from_experiment_config(cfg)
        self._openie = OpenIE(llm_model=llm_model)
        return self._openie

    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta:
        if not chunks:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        openie = self._lazy_init()

        chunk_map = {
            chunk.chunk_id: {
                "content": chunk.content,
                "num_tokens": len(chunk.content.split()),
                "chunk_order": [],
                "full_doc_ids": [chunk.document_id],
            }
            for chunk in chunks
        }

        _, triple_results = openie.batch_openie(chunk_map)

        node_title_to_id: dict[str, str] = {}
        nodes: list[CandidateNode] = []
        edges: list[CandidateEdge] = []
        evidence: list[EvidenceItem] = []

        def get_node_id(title: str) -> str:
            key = title.strip()
            if key not in node_title_to_id:
                node_id = f"node_ent_{abs(hash(key)) % 10**12}"
                node_title_to_id[key] = node_id
                nodes.append(
                    CandidateNode(
                        node_id=node_id,
                        title=key[:200],
                        node_type="Concept",
                        status="draft",
                    )
                )
            return node_title_to_id[key]

        for chunk in chunks:
            chunk_id = chunk.chunk_id
            result = triple_results.get(chunk_id)
            if result is None:
                continue

            for idx, triple in enumerate(result.triples):
                if len(triple) != 3:
                    continue
                subject, relation, obj = [str(x).strip() for x in triple]
                if (not subject) or (not relation) or (not obj):
                    continue

                source_id = get_node_id(subject)
                target_id = get_node_id(obj)
                edge_id = f"edge_rel_{abs(hash((source_id, relation, target_id, chunk_id, idx))) % 10**12}"

                edges.append(
                    CandidateEdge(
                        edge_id=edge_id,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        relation_type=relation[:120],
                        status="draft",
                    )
                )
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{chunk_id}_{idx}",
                        chunk_id=chunk_id,
                        score=0.8,
                    )
                )

        if not nodes or not edges:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        return GraphDelta(nodes=nodes, edges=edges, evidence=evidence)
