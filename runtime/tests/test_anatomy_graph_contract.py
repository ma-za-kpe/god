import pytest

from anatomy import (
    AnatomyEdge,
    AnatomyGraph,
    AnatomyGraphValidationError,
    AnatomyKind,
    AnatomyNode,
    EdgeKind,
    MaterializationState,
    SourceRef,
    ActionLOD,
    AnatomyActionRequest,
    build_m01_reference_graph,
    build_m02_reference_graph,
    compile_lod_action_bundle,
    neo4j_lod_retrieval_cypher,
    neo4j_cypher_script,
    neo4j_load_statements,
    neo4j_schema_statements,
    neo4j_validation_queries,
)


TEST_SOURCE = SourceRef(
    source_id="test-source",
    citation="Test anatomy source",
    url="https://example.test/anatomy",
)


def test_m01_seed_graph_is_source_cited_and_valid():
    graph = build_m01_reference_graph()

    graph.assert_valid()

    system_nodes = [node for node in graph.nodes.values() if node.kind == AnatomyKind.SYSTEM]
    assert len(system_nodes) == 11
    assert all(node.sources for node in graph.nodes.values())
    assert all(edge.sources for edge in graph.edges)


def test_llm_registry_exposes_only_bounded_control_nodes():
    graph = build_m01_reference_graph()

    registry = graph.llm_control_registry()
    registry_by_id = {item["id"]: item for item in registry}

    assert "skin:forehead" in registry_by_id
    assert "population:forehead_eccrine_sweat_glands" in registry_by_id
    assert "organ:brain" not in registry_by_id
    assert registry_by_id["skin:forehead"]["control_channels"] == [
        "sweat",
        "flush",
        "detail_lod",
    ]
    assert registry_by_id["skin:forehead"]["source_ids"] == ["fipat-ta2-2019"]


def test_working_set_keeps_population_templates_without_virtual_expansion():
    graph = build_m01_reference_graph()
    graph.add_node(
        AnatomyNode(
            id="virtual:forehead_sweat_gland_0001",
            label="Virtual forehead sweat gland 0001",
            kind=AnatomyKind.GLAND,
            materialization=MaterializationState.VIRTUAL_INSTANCE,
            sources=(TEST_SOURCE,),
        )
    )
    graph.add_edge(
        AnatomyEdge(
            from_id="population:forehead_eccrine_sweat_glands",
            to_id="virtual:forehead_sweat_gland_0001",
            kind=EdgeKind.MATERIALIZES_AS,
            sources=(TEST_SOURCE,),
        )
    )

    working_set = graph.compile_working_set("skin:forehead", max_depth=2)

    assert working_set.contains("population:forehead_eccrine_sweat_glands")
    assert working_set.contains("render:forehead_sweat_proxy")
    assert not working_set.contains("virtual:forehead_sweat_gland_0001")


def test_working_set_can_expand_virtual_instances_when_requested():
    graph = build_m01_reference_graph()
    graph.add_node(
        AnatomyNode(
            id="virtual:forehead_sweat_gland_0001",
            label="Virtual forehead sweat gland 0001",
            kind=AnatomyKind.GLAND,
            materialization=MaterializationState.VIRTUAL_INSTANCE,
            sources=(TEST_SOURCE,),
        )
    )
    graph.add_edge(
        AnatomyEdge(
            from_id="population:forehead_eccrine_sweat_glands",
            to_id="virtual:forehead_sweat_gland_0001",
            kind=EdgeKind.MATERIALIZES_AS,
            sources=(TEST_SOURCE,),
        )
    )

    working_set = graph.compile_working_set(
        "skin:forehead",
        max_depth=3,
        expand_virtual=True,
    )

    assert working_set.contains("virtual:forehead_sweat_gland_0001")


def test_neo4j_export_shape_is_constraint_ready():
    graph = build_m01_reference_graph()

    nodes = {record["id"]: record for record in graph.to_neo4j_nodes()}
    relationships = graph.to_neo4j_relationships()

    assert "AnatomyNode" in nodes["skin:forehead"]["labels"]
    assert "Skin" in nodes["skin:forehead"]["labels"]
    assert nodes["skin:forehead"]["properties"]["materialization"] == "aggregate"
    assert any(record["type"] == "PROJECTS_TO_RENDER" for record in relationships)
    assert any("REQUIRE n.id IS UNIQUE" in item for item in graph.neo4j_constraints())


def test_validation_rejects_missing_source_and_unbounded_llm_node():
    graph = AnatomyGraph()
    graph.add_node(
        AnatomyNode(
            id="skin:unsourced",
            label="Unsourced skin",
            kind=AnatomyKind.SKIN,
            sources=(),
            llm_visible=True,
        )
    )

    errors = graph.validate()

    assert {error.code for error in errors} >= {
        "MISSING_SOURCE",
        "LLM_VISIBLE_WITHOUT_CONTROLS",
    }
    with pytest.raises(AnatomyGraphValidationError):
        graph.assert_valid()


def test_validation_rejects_orphan_render_proxy_and_unknown_edges():
    graph = AnatomyGraph()
    graph.add_node(
        AnatomyNode(
            id="render:orphan",
            label="Orphan render proxy",
            kind=AnatomyKind.RENDER_PROXY,
            materialization=MaterializationState.RENDER_PROXY,
            sources=(TEST_SOURCE,),
            control_channels=("opacity",),
            llm_visible=True,
        )
    )
    graph.add_edge(
        AnatomyEdge(
            from_id="missing:node",
            to_id="render:orphan",
            kind=EdgeKind.PROJECTS_TO_RENDER,
            sources=(TEST_SOURCE,),
        )
    )

    errors = graph.validate()

    assert any(error.code == "UNKNOWN_EDGE_FROM" for error in errors)
    assert any(error.code == "ORPHAN_RENDER_PROXY" for error in errors)


def test_validation_rejects_proxy_without_anatomy_projection():
    graph = AnatomyGraph()
    graph.add_node(
        AnatomyNode(
            id="render:orphan",
            label="Orphan render proxy",
            kind=AnatomyKind.RENDER_PROXY,
            materialization=MaterializationState.RENDER_PROXY,
            sources=(TEST_SOURCE,),
            control_channels=("opacity",),
            llm_visible=True,
        )
    )

    errors = graph.validate()

    assert any(error.code == "ORPHAN_RENDER_PROXY" for error in errors)


def test_m02_seed_graph_expands_head_knee_hand_and_toe_with_sources():
    graph = build_m02_reference_graph()

    graph.assert_valid()

    expected_nodes = {
        "bone:skull",
        "aggregate:brain_case_bones",
        "aggregate:facial_bones",
        "region:right_hand",
        "aggregate:right_carpals",
        "digit:right_pollex",
        "joint:right_knee",
        "bone:right_femur",
        "bone:right_tibia",
        "bone:right_patella",
        "bone:right_fibula",
        "region:right_foot",
        "digit:right_hallux",
        "skin:right_hallux",
    }
    assert expected_nodes.issubset(graph.nodes)
    assert all(graph.node(node_id).sources for node_id in expected_nodes)


def test_m02_knee_model_does_not_make_fibula_part_of_knee_joint():
    graph = build_m02_reference_graph()

    fibula_edges = [
        edge
        for edge in graph.edges
        if edge.from_id == "bone:right_fibula" and edge.to_id == "joint:right_knee"
    ]

    assert [edge.kind for edge in fibula_edges] == [EdgeKind.ADJACENT_TO]
    assert any(
        edge.from_id == "bone:right_femur"
        and edge.to_id == "joint:right_knee"
        and edge.kind == EdgeKind.CONNECTS_TO
        for edge in graph.edges
    )
    assert any(
        edge.from_id == "bone:right_tibia"
        and edge.to_id == "joint:right_knee"
        and edge.kind == EdgeKind.CONNECTS_TO
        for edge in graph.edges
    )
    assert any(
        edge.from_id == "bone:right_patella"
        and edge.to_id == "joint:right_knee"
        and edge.kind == EdgeKind.CONNECTS_TO
        for edge in graph.edges
    )


def test_m02_hand_and_hallux_special_cases_have_two_phalanges_each():
    graph = build_m02_reference_graph()

    pollex_phalanges = [
        edge.from_id
        for edge in graph.edges
        if edge.to_id == "digit:right_pollex" and edge.kind == EdgeKind.PART_OF
    ]
    hallux_phalanges = [
        edge.from_id
        for edge in graph.edges
        if edge.to_id == "digit:right_hallux" and edge.kind == EdgeKind.PART_OF
    ]

    assert sorted(pollex_phalanges) == [
        "bone:right_pollex_distal_phalanx",
        "bone:right_pollex_proximal_phalanx",
    ]
    assert sorted(hallux_phalanges) == [
        "bone:right_hallux_distal_phalanx",
        "bone:right_hallux_proximal_phalanx",
    ]


def test_m02_llm_registry_exposes_new_anatomy_controls_without_unsourced_nodes():
    graph = build_m02_reference_graph()

    registry = {item["id"]: item for item in graph.llm_control_registry()}

    assert registry["joint:right_knee"]["control_channels"] == [
        "flexion_extension",
        "stability_state",
        "anatomy_layer",
    ]
    assert registry["region:right_hand"]["control_channels"] == [
        "open_close",
        "finger_curl",
        "anatomy_layer",
    ]
    assert registry["digit:right_hallux"]["control_channels"] == [
        "flexion_extension",
        "ground_contact",
    ]
    assert "bone:right_fibula" not in registry


def test_m03_neo4j_schema_is_idempotent_and_community_safe():
    statements = neo4j_schema_statements()

    assert any("FOR (n:AnatomyNode) REQUIRE n.id IS UNIQUE" in item for item in statements)
    assert any("CREATE TEXT INDEX anatomy_node_label_text" in item for item in statements)
    assert any("FOR ()-[r:PART_OF]-() REQUIRE r.graph_key IS UNIQUE" in item for item in statements)
    assert all("IF NOT EXISTS" in item for item in statements)
    assert not any(" IS NOT NULL" in item for item in statements)
    assert not any(" IS NODE KEY" in item for item in statements)
    assert not any(" IS TYPED" in item for item in statements)


def test_m03_neo4j_load_statements_cover_m02_nodes_and_edges():
    graph = build_m02_reference_graph()

    statements = neo4j_load_statements(graph, reset=True)
    node_merges = [item for item in statements if item.startswith("MERGE (n:")]
    relationship_merges = [item for item in statements if "MERGE (from)-[r:" in item]

    assert statements[0] == "MATCH (n:AnatomyNode) DETACH DELETE n"
    assert len(node_merges) == len(graph.nodes)
    assert len(relationship_merges) == len(graph.edges)
    assert any(
        "MERGE (n:AnatomyNode:Bone:Canonical {id: 'bone:skull'})" in item for item in node_merges
    )
    assert any("source_ids" in item and "llm_visible" in item for item in node_merges)
    assert any("graph_key:" in item and "PART_OF" in item for item in relationship_merges)


def test_m03_neo4j_validation_queries_pin_expected_counts():
    graph = build_m02_reference_graph()

    queries = neo4j_validation_queries(graph)

    assert any("invalid_node_count" in query for query in queries)
    assert any("invalid_relationship_count" in query for query in queries)
    assert any(f"{len(graph.nodes)} AS expected_nodes" in query for query in queries)
    assert any(f"{len(graph.edges)} AS expected_relationships" in query for query in queries)
    assert any("duplicate_node_id_count" in query for query in queries)


def test_m03_neo4j_cypher_script_is_cypher_shell_ready():
    graph = build_m02_reference_graph()

    script = neo4j_cypher_script(graph, reset=True)

    assert script.startswith("// Anatomy Neo4j schema\n")
    assert script.endswith(";\n")
    assert "CREATE CONSTRAINT anatomy_node_id_unique IF NOT EXISTS" in script
    assert "MATCH (n:AnatomyNode) DETACH DELETE n;" in script
    assert "MERGE (n:AnatomyNode:Bone:Canonical {id: 'bone:skull'})" in script
    assert "RETURN count(n) AS invalid_node_count;" in script


def test_m04_wave_request_compiles_to_bounded_upper_limb_bundle():
    graph = build_m02_reference_graph()
    request = AnatomyActionRequest(
        action="wave",
        seed_node_ids=("region:right_hand", "digit:right_pollex", "digit:right_index_finger"),
        lod=ActionLOD.MESO,
        max_nodes=16,
        requested_capabilities=("open_close", "finger_curl"),
    )

    bundle = compile_lod_action_bundle(graph, request)
    bundle_ids = {node.id for node in bundle.nodes}

    assert len(bundle.nodes) <= 16
    assert {"region:right_hand", "digit:right_pollex", "digit:right_index_finger"}.issubset(
        bundle_ids
    )
    assert "joint:right_knee" not in bundle_ids
    assert any(node.role.value == "primary" for node in bundle.nodes)
    assert "unsupported_capability:digit:right_pollex:open_close" in bundle.diagnostics
    assert "MATCH path=(seed)-[:" in bundle.cypher


def test_m04_run_request_stays_bounded_and_reports_no_context_explosion():
    graph = build_m02_reference_graph()
    request = AnatomyActionRequest(
        action="run",
        seed_node_ids=(
            "joint:right_knee",
            "digit:right_hallux",
            "system:muscular",
            "system:cardiovascular",
            "system:respiratory",
            "skin:forehead",
        ),
        lod=ActionLOD.MACRO,
        max_nodes=14,
    )

    bundle = compile_lod_action_bundle(graph, request)
    bundle_ids = {node.id for node in bundle.nodes}

    assert len(bundle.nodes) <= 14
    assert "joint:right_knee" in bundle_ids
    assert "digit:right_hallux" in bundle_ids
    assert "system:cardiovascular" in bundle_ids
    assert all(not diagnostic.startswith("missing_seed_node") for diagnostic in bundle.diagnostics)


def test_m04_sweat_request_uses_micro_lod_without_expanding_virtual_instances():
    graph = build_m02_reference_graph()
    request = AnatomyActionRequest(
        action="sweat_forehead",
        seed_node_ids=(
            "skin:forehead",
            "population:forehead_eccrine_sweat_glands",
            "render:forehead_sweat_proxy",
        ),
        lod=ActionLOD.MICRO,
        max_nodes=12,
        requested_capabilities=("sweat",),
    )

    bundle = compile_lod_action_bundle(graph, request)
    bundle_by_id = {node.id: node for node in bundle.nodes}

    assert len(bundle.nodes) <= 12
    assert bundle_by_id["skin:forehead"].role.value == "primary"
    assert bundle_by_id["render:forehead_sweat_proxy"].role.value == "primary"
    assert "virtual:forehead_sweat_gland_0001" not in bundle_by_id


def test_m04_missing_seed_nodes_become_diagnostics_not_fake_nodes():
    graph = build_m02_reference_graph()
    request = AnatomyActionRequest(
        action="blink",
        seed_node_ids=("region:right_eye", "bone:skull"),
        lod=ActionLOD.MESO,
        max_nodes=8,
    )

    bundle = compile_lod_action_bundle(graph, request)
    bundle_ids = {node.id for node in bundle.nodes}

    assert "missing_seed_node:region:right_eye" in bundle.diagnostics
    assert "region:right_eye" not in bundle_ids
    assert "bone:skull" in bundle_ids


def test_m04_neo4j_lod_cypher_uses_bounded_graph_traversal():
    cypher = neo4j_lod_retrieval_cypher(2)

    assert "seed.id IN $seed_node_ids" in cypher
    assert "*0..2" in cypher
    assert "LIMIT $max_nodes" in cypher
    assert "interior.kind IN ['body', 'system']" in cypher
    assert "PART_OF" in cypher
    assert "PROJECTS_TO_RENDER" in cypher
