"""Small source-cited seed graphs for anatomy contract tests."""

from __future__ import annotations

from .graph import (
    AnatomyEdge,
    AnatomyGraph,
    AnatomyKind,
    AnatomyNode,
    EdgeKind,
    MaterializationState,
    SourceRef,
)

OPENSTAX_1_2 = SourceRef(
    source_id="openstax-ap-2e-1.2",
    citation="OpenStax Anatomy and Physiology 2e, 1.2 Structural Organization of the Human Body",
    url="https://openstax.org/books/anatomy-and-physiology-2e/pages/1-2-structural-organization-of-the-human-body",
    version="2e",
    license="CC BY 4.0",
)

FIPAT_TA2 = SourceRef(
    source_id="fipat-ta2-2019",
    citation="FIPAT. Terminologia Anatomica. 2nd ed. FIPAT.library.dal.ca, 2019",
    url="https://libraries.dal.ca/Fipat/ta2.html",
    version="TA2 v2.07",
    license="CC BY-ND 4.0 for publication; individual terms public domain per FIPAT page",
)

HRA_KG = SourceRef(
    source_id="hra-kg-v2.2-paper",
    citation="Construction, Deployment, and Usage of the Human Reference Atlas Knowledge Graph",
    url="https://www.nature.com/articles/s41597-025-05183-6",
    version="HRA KG v2.2 paper",
    license="CC BY 4.0",
)


def build_m01_reference_graph() -> AnatomyGraph:
    """Build the smallest graph that exercises M01 invariants.

    This seed is intentionally compact. It proves the contract can represent the
    OpenStax body/system level, FIPAT-style named structures, HRA-style
    population templates, and renderer proxies without loading a full atlas.
    """

    graph = AnatomyGraph()

    def add_node(
        node_id: str,
        label: str,
        kind: AnatomyKind,
        *,
        sources: tuple[SourceRef, ...] = (OPENSTAX_1_2,),
        materialization: MaterializationState = MaterializationState.CANONICAL,
        aliases: tuple[str, ...] = (),
        control_channels: tuple[str, ...] = (),
        llm_visible: bool = False,
    ) -> None:
        graph.add_node(
            AnatomyNode(
                id=node_id,
                label=label,
                kind=kind,
                sources=sources,
                materialization=materialization,
                aliases=aliases,
                control_channels=control_channels,
                llm_visible=llm_visible,
            )
        )

    def add_edge(
        from_id: str,
        to_id: str,
        kind: EdgeKind,
        *,
        sources: tuple[SourceRef, ...] = (OPENSTAX_1_2,),
    ) -> None:
        graph.add_edge(AnatomyEdge(from_id=from_id, to_id=to_id, kind=kind, sources=sources))

    add_node("body:human", "Human body", AnatomyKind.BODY, aliases=("organism",))

    systems = (
        ("system:integumentary", "Integumentary system"),
        ("system:skeletal", "Skeletal system"),
        ("system:muscular", "Muscular system"),
        ("system:nervous", "Nervous system"),
        ("system:endocrine", "Endocrine system"),
        ("system:cardiovascular", "Cardiovascular system"),
        ("system:lymphatic", "Lymphatic system"),
        ("system:respiratory", "Respiratory system"),
        ("system:digestive", "Digestive system"),
        ("system:urinary", "Urinary system"),
        ("system:reproductive", "Reproductive system"),
    )
    for node_id, label in systems:
        add_node(node_id, label, AnatomyKind.SYSTEM)
        add_edge(node_id, "body:human", EdgeKind.PART_OF)

    add_node(
        "region:head",
        "Head",
        AnatomyKind.REGION,
        sources=(FIPAT_TA2,),
        control_channels=("camera_focus", "anatomy_layer", "pose_focus"),
        llm_visible=True,
    )
    add_edge("region:head", "body:human", EdgeKind.PART_OF, sources=(FIPAT_TA2,))

    add_node("organ:brain", "Brain", AnatomyKind.ORGAN, sources=(FIPAT_TA2,))
    add_edge("organ:brain", "system:nervous", EdgeKind.PART_OF, sources=(FIPAT_TA2,))
    add_edge("organ:brain", "region:head", EdgeKind.LOCATED_IN, sources=(FIPAT_TA2,))

    add_node("organ:skin", "Skin", AnatomyKind.SKIN, sources=(OPENSTAX_1_2, FIPAT_TA2))
    add_edge("organ:skin", "system:integumentary", EdgeKind.PART_OF, sources=(OPENSTAX_1_2,))

    add_node("structure:hair", "Hair", AnatomyKind.HAIR, sources=(OPENSTAX_1_2, FIPAT_TA2))
    add_edge("structure:hair", "system:integumentary", EdgeKind.PART_OF, sources=(OPENSTAX_1_2,))

    add_node("structure:nails", "Nails", AnatomyKind.NAIL, sources=(OPENSTAX_1_2, FIPAT_TA2))
    add_edge("structure:nails", "system:integumentary", EdgeKind.PART_OF, sources=(OPENSTAX_1_2,))

    add_node(
        "skin:forehead",
        "Skin of forehead",
        AnatomyKind.SKIN,
        sources=(FIPAT_TA2,),
        materialization=MaterializationState.AGGREGATE,
        control_channels=("sweat", "flush", "detail_lod"),
        llm_visible=True,
    )
    add_edge("skin:forehead", "organ:skin", EdgeKind.PART_OF, sources=(FIPAT_TA2,))
    add_edge("skin:forehead", "region:head", EdgeKind.LOCATED_IN, sources=(FIPAT_TA2,))

    add_node(
        "population:forehead_eccrine_sweat_glands",
        "Forehead eccrine sweat gland population",
        AnatomyKind.POPULATION_TEMPLATE,
        sources=(FIPAT_TA2, HRA_KG),
        materialization=MaterializationState.POPULATION_TEMPLATE,
        control_channels=("sweat_emission", "materialize_visible_instances"),
        llm_visible=True,
    )
    add_edge(
        "population:forehead_eccrine_sweat_glands",
        "skin:forehead",
        EdgeKind.PART_OF,
        sources=(FIPAT_TA2,),
    )

    add_node(
        "population:scalp_hair_follicles",
        "Scalp hair follicle population",
        AnatomyKind.POPULATION_TEMPLATE,
        sources=(FIPAT_TA2, HRA_KG),
        materialization=MaterializationState.POPULATION_TEMPLATE,
        control_channels=("bend_proxy", "sway_proxy", "materialize_visible_instances"),
        llm_visible=True,
    )
    add_edge(
        "population:scalp_hair_follicles",
        "structure:hair",
        EdgeKind.PART_OF,
        sources=(FIPAT_TA2,),
    )
    add_edge("population:scalp_hair_follicles", "region:head", EdgeKind.LOCATED_IN, sources=(FIPAT_TA2,))

    add_node(
        "render:forehead_sweat_proxy",
        "Forehead sweat droplet render proxy",
        AnatomyKind.RENDER_PROXY,
        sources=(HRA_KG,),
        materialization=MaterializationState.RENDER_PROXY,
        control_channels=("opacity", "droplet_rate"),
        llm_visible=True,
    )
    add_edge(
        "population:forehead_eccrine_sweat_glands",
        "render:forehead_sweat_proxy",
        EdgeKind.PROJECTS_TO_RENDER,
        sources=(HRA_KG,),
    )

    return graph
