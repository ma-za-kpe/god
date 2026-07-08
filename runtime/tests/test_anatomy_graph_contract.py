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
    build_m01_reference_graph,
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
