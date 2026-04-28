import os
import sys
import types
import importlib
from pathlib import Path

from dotenv import load_dotenv

from packages.contracts.document import ParsedChunk
from packages.contracts.graph import GraphDelta, CandidateNode, CandidateEdge, EvidenceItem
from packages.graph.entity_resolution import EntityResolutionService


class HippoRAGOpenIEAdapter:
    def __init__(self) -> None:
        self._openie = None
        self._entity_resolution = EntityResolutionService()

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
        existing_entities: dict[str, dict] = {}
        nodes: list[CandidateNode] = []
        edges: list[CandidateEdge] = []
        evidence: list[EvidenceItem] = []

        def get_or_create_node(title: str, context: str, neighbors: set[str]) -> tuple[str, list[tuple[str, str]]]:
            resolution = self._entity_resolution.resolve_entity(
                title=title,
                context=context,
                existing_entities=existing_entities,
                neighbors=neighbors,
            )
            if resolution.get('action') == 'drop':
                return '', []

            normalized_name = resolution['normalized_name']
            synonymy_edges: list[tuple[str, str]] = []
            if resolution.get('action') == 'merge' and normalized_name in node_title_to_id:
                return node_title_to_id[normalized_name], []

            if resolution.get('action') == 'synonymy':
                canonical_name = resolution.get('canonical_name')
                if canonical_name and canonical_name in node_title_to_id:
                    node_id = node_title_to_id.get(normalized_name)
                    if node_id is None:
                        node_id = f"node_ent_{abs(hash(normalized_name)) % 10**12}"
                        node_title_to_id[normalized_name] = node_id
                        nodes.append(
                            CandidateNode(
                                node_id=node_id,
                                title=normalized_name[:200],
                                node_type=self._entity_resolution.classify_entity_type(normalized_name, context),
                                summary='',
                                status='draft',
                            )
                        )
                        existing_entities[normalized_name] = {
                            'normalized_name': normalized_name,
                            'title': normalized_name,
                            'neighbors': set(neighbors),
                        }
                    synonymy_edges.append((node_id, node_title_to_id[canonical_name]))
                    return node_id, synonymy_edges

            if normalized_name not in node_title_to_id:
                node_id = f"node_ent_{abs(hash(normalized_name)) % 10**12}"
                node_title_to_id[normalized_name] = node_id
                nodes.append(
                    CandidateNode(
                        node_id=node_id,
                        title=normalized_name[:200],
                        node_type=self._entity_resolution.classify_entity_type(normalized_name, context),
                        status='draft',
                    )
                )
                existing_entities[normalized_name] = {
                    'normalized_name': normalized_name,
                    'title': normalized_name,
                    'neighbors': set(neighbors),
                }
            else:
                existing_entities[normalized_name]['neighbors'].update(neighbors)
            return node_title_to_id[normalized_name], []

        synonymy_seen: set[tuple[str, str]] = set()
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

                source_id, source_synonymy = get_or_create_node(subject, chunk.content, neighbors={obj})
                target_id, target_synonymy = get_or_create_node(obj, chunk.content, neighbors={subject})
                if not source_id or not target_id:
                    continue

                edge_id = f"edge_rel_{abs(hash((source_id, relation, target_id, chunk_id, idx))) % 10**12}"
                edges.append(
                    CandidateEdge(
                        edge_id=edge_id,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        relation_type=relation[:120],
                        status='draft',
                    )
                )

                for src_id, dst_id in source_synonymy + target_synonymy:
                    key = tuple(sorted((src_id, dst_id)))
                    if key in synonymy_seen:
                        continue
                    synonymy_seen.add(key)
                    edges.append(
                        CandidateEdge(
                            edge_id=f"edge_syn_{abs(hash(key)) % 10**12}",
                            source_node_id=src_id,
                            target_node_id=dst_id,
                            relation_type='similar_to',
                            status='draft',
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
