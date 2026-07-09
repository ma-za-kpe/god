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

OPENSTAX_7_2 = SourceRef(
    source_id="openstax-ap-2e-7.2",
    citation="OpenStax Anatomy and Physiology 2e, 7.2 The Skull",
    url="https://openstax.org/books/anatomy-and-physiology-2e/pages/7-2-the-skull",
    version="2e",
    license="CC BY-NC-SA 4.0",
)

OPENSTAX_8_2 = SourceRef(
    source_id="openstax-ap-2e-8.2",
    citation="OpenStax Anatomy and Physiology 2e, 8.2 Bones of the Upper Limb",
    url="https://openstax.org/books/anatomy-and-physiology-2e/pages/8-2-bones-of-the-upper-limb",
    version="2e",
    license="CC BY-NC-SA 4.0",
)

OPENSTAX_8_4 = SourceRef(
    source_id="openstax-ap-2e-8.4",
    citation="OpenStax Anatomy and Physiology 2e, 8.4 Bones of the Lower Limb",
    url="https://openstax.org/books/anatomy-and-physiology-2e/pages/8-4-bones-of-the-lower-limb",
    version="2e",
    license="CC BY-NC-SA 4.0",
)

NCBI_KNEE = SourceRef(
    source_id="ncbi-statpearls-knee-2023",
    citation="StatPearls/NCBI Bookshelf, Anatomy, Bony Pelvis and Lower Limb, Knee",
    url="https://www.ncbi.nlm.nih.gov/books/NBK500017/",
    version="2023 update",
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

GRAY_1918 = SourceRef(
    source_id="gray-anatomy-1918",
    citation="Gray, Anatomy of the Human Body, 20th ed., 1918",
    url="https://archive.org/details/anatomyofhumanbo1918gray",
    version="1918",
    license="Public domain",
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
    add_edge(
        "population:scalp_hair_follicles", "region:head", EdgeKind.LOCATED_IN, sources=(FIPAT_TA2,)
    )

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


def build_m02_reference_graph() -> AnatomyGraph:
    """Build the M02 source-cited body/head/knee/hand/toe seed graph."""

    graph = build_m01_reference_graph()

    def add_node(
        node_id: str,
        label: str,
        kind: AnatomyKind,
        *,
        sources: tuple[SourceRef, ...],
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
        sources: tuple[SourceRef, ...],
    ) -> None:
        graph.add_edge(AnatomyEdge(from_id=from_id, to_id=to_id, kind=kind, sources=sources))

    # Head and skull.
    add_node(
        "bone:skull",
        "Skull",
        AnatomyKind.BONE,
        sources=(OPENSTAX_7_2, FIPAT_TA2),
        aliases=("cranium",),
        control_channels=("anatomy_layer", "head_pose_proxy"),
        llm_visible=True,
    )
    add_edge("bone:skull", "system:skeletal", EdgeKind.PART_OF, sources=(OPENSTAX_7_2,))
    add_edge("bone:skull", "region:head", EdgeKind.LOCATED_IN, sources=(OPENSTAX_7_2,))

    add_node(
        "aggregate:brain_case_bones",
        "Brain-case bones",
        AnatomyKind.STRUCTURE,
        sources=(OPENSTAX_7_2,),
        materialization=MaterializationState.AGGREGATE,
        aliases=("neurocranium",),
    )
    add_edge("aggregate:brain_case_bones", "bone:skull", EdgeKind.PART_OF, sources=(OPENSTAX_7_2,))

    for node_id, label in (
        ("bone:frontal", "Frontal bone"),
        ("bone:parietal_pair", "Parietal bones"),
        ("bone:temporal_pair", "Temporal bones"),
        ("bone:occipital", "Occipital bone"),
        ("bone:sphenoid", "Sphenoid bone"),
        ("bone:ethmoid", "Ethmoid bone"),
    ):
        add_node(node_id, label, AnatomyKind.BONE, sources=(OPENSTAX_7_2, FIPAT_TA2))
        add_edge(node_id, "aggregate:brain_case_bones", EdgeKind.PART_OF, sources=(OPENSTAX_7_2,))

    add_node(
        "aggregate:facial_bones",
        "Facial bones",
        AnatomyKind.STRUCTURE,
        sources=(OPENSTAX_7_2,),
        materialization=MaterializationState.AGGREGATE,
    )
    add_edge("aggregate:facial_bones", "bone:skull", EdgeKind.PART_OF, sources=(OPENSTAX_7_2,))

    for node_id, label in (
        ("bone:maxilla_pair", "Maxillae"),
        ("bone:zygomatic_pair", "Zygomatic bones"),
        ("bone:nasal_pair", "Nasal bones"),
        ("bone:mandible", "Mandible"),
        ("bone:vomer", "Vomer"),
    ):
        add_node(node_id, label, AnatomyKind.BONE, sources=(OPENSTAX_7_2, FIPAT_TA2))
        add_edge(node_id, "aggregate:facial_bones", EdgeKind.PART_OF, sources=(OPENSTAX_7_2,))

    # Right hand seed.
    add_node(
        "region:right_hand",
        "Right hand",
        AnatomyKind.REGION,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
        control_channels=("open_close", "finger_curl", "anatomy_layer"),
        llm_visible=True,
    )
    add_edge("region:right_hand", "body:human", EdgeKind.PART_OF, sources=(FIPAT_TA2,))

    for node_id, label, count in (
        ("aggregate:right_carpals", "Right carpal bones", 8),
        ("aggregate:right_metacarpals", "Right metacarpal bones", 5),
        ("aggregate:right_hand_phalanges", "Right hand phalanges", 14),
    ):
        add_node(
            node_id,
            label,
            AnatomyKind.BONE,
            sources=(OPENSTAX_8_2,),
            materialization=MaterializationState.AGGREGATE,
            aliases=(f"{count} bones",),
        )
        add_edge(node_id, "region:right_hand", EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))

    add_node(
        "digit:right_pollex",
        "Right thumb",
        AnatomyKind.STRUCTURE,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
        aliases=("pollex", "digit 1"),
        control_channels=("opposition", "flexion_extension"),
        llm_visible=True,
    )
    add_edge("digit:right_pollex", "region:right_hand", EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))

    for node_id, label in (
        ("bone:right_pollex_proximal_phalanx", "Right thumb proximal phalanx"),
        ("bone:right_pollex_distal_phalanx", "Right thumb distal phalanx"),
    ):
        add_node(node_id, label, AnatomyKind.BONE, sources=(OPENSTAX_8_2, FIPAT_TA2))
        add_edge(node_id, "digit:right_pollex", EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))

    add_node(
        "digit:right_index_finger",
        "Right index finger",
        AnatomyKind.STRUCTURE,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
        aliases=("digit 2",),
        control_channels=("flexion_extension", "abduction_adduction"),
        llm_visible=True,
    )
    add_edge(
        "digit:right_index_finger", "region:right_hand", EdgeKind.PART_OF, sources=(OPENSTAX_8_2,)
    )

    # Right knee seed.
    add_node(
        "joint:right_knee",
        "Right knee joint",
        AnatomyKind.JOINT,
        sources=(OPENSTAX_8_4, NCBI_KNEE, FIPAT_TA2),
        control_channels=("flexion_extension", "stability_state", "anatomy_layer"),
        llm_visible=True,
    )
    add_edge("joint:right_knee", "body:human", EdgeKind.PART_OF, sources=(FIPAT_TA2,))

    for node_id, label in (
        ("bone:right_femur", "Right femur"),
        ("bone:right_tibia", "Right tibia"),
        ("bone:right_patella", "Right patella"),
    ):
        add_node(node_id, label, AnatomyKind.BONE, sources=(OPENSTAX_8_4, FIPAT_TA2))
        add_edge(node_id, "system:skeletal", EdgeKind.PART_OF, sources=(OPENSTAX_8_4,))
        add_edge(node_id, "joint:right_knee", EdgeKind.CONNECTS_TO, sources=(OPENSTAX_8_4,))

    add_node(
        "bone:right_fibula",
        "Right fibula",
        AnatomyKind.BONE,
        sources=(OPENSTAX_8_4, NCBI_KNEE, FIPAT_TA2),
        aliases=("not part of knee joint",),
    )
    add_edge("bone:right_fibula", "system:skeletal", EdgeKind.PART_OF, sources=(OPENSTAX_8_4,))
    add_edge("bone:right_fibula", "joint:right_knee", EdgeKind.ADJACENT_TO, sources=(NCBI_KNEE,))

    for node_id, label in (
        ("ligament:right_acl", "Right anterior cruciate ligament"),
        ("ligament:right_pcl", "Right posterior cruciate ligament"),
        ("ligament:right_mcl", "Right medial collateral ligament"),
        ("ligament:right_lcl", "Right lateral collateral ligament"),
    ):
        add_node(node_id, label, AnatomyKind.LIGAMENT, sources=(NCBI_KNEE, FIPAT_TA2))
        add_edge(node_id, "joint:right_knee", EdgeKind.PART_OF, sources=(NCBI_KNEE,))

    # Right foot and hallux seed.
    add_node(
        "region:right_foot",
        "Right foot",
        AnatomyKind.REGION,
        sources=(OPENSTAX_8_4, FIPAT_TA2),
        control_channels=("weight_bearing", "toe_curl", "anatomy_layer"),
        llm_visible=True,
    )
    add_edge("region:right_foot", "body:human", EdgeKind.PART_OF, sources=(FIPAT_TA2,))

    for node_id, label, count in (
        ("aggregate:right_tarsals", "Right tarsal bones", 7),
        ("aggregate:right_metatarsals", "Right metatarsal bones", 5),
        ("aggregate:right_foot_phalanges", "Right foot phalanges", 14),
    ):
        add_node(
            node_id,
            label,
            AnatomyKind.BONE,
            sources=(OPENSTAX_8_4,),
            materialization=MaterializationState.AGGREGATE,
            aliases=(f"{count} bones",),
        )
        add_edge(node_id, "region:right_foot", EdgeKind.PART_OF, sources=(OPENSTAX_8_4,))

    add_node(
        "digit:right_hallux",
        "Right great toe",
        AnatomyKind.STRUCTURE,
        sources=(OPENSTAX_8_4, FIPAT_TA2),
        aliases=("hallux", "digit 1"),
        control_channels=("flexion_extension", "ground_contact"),
        llm_visible=True,
    )
    add_edge("digit:right_hallux", "region:right_foot", EdgeKind.PART_OF, sources=(OPENSTAX_8_4,))

    for node_id, label in (
        ("bone:right_hallux_proximal_phalanx", "Right great toe proximal phalanx"),
        ("bone:right_hallux_distal_phalanx", "Right great toe distal phalanx"),
    ):
        add_node(node_id, label, AnatomyKind.BONE, sources=(OPENSTAX_8_4, FIPAT_TA2))
        add_edge(node_id, "digit:right_hallux", EdgeKind.PART_OF, sources=(OPENSTAX_8_4,))

    # Skin patches keep the tiny-to-toe direction alive without exploding rows.
    add_node(
        "skin:right_hallux",
        "Skin of right great toe",
        AnatomyKind.SKIN,
        sources=(FIPAT_TA2, HRA_KG),
        materialization=MaterializationState.AGGREGATE,
        control_channels=("pressure_flush", "sweat", "contact_deformation"),
        llm_visible=True,
    )
    add_edge("skin:right_hallux", "organ:skin", EdgeKind.PART_OF, sources=(FIPAT_TA2,))
    add_edge("skin:right_hallux", "digit:right_hallux", EdgeKind.LOCATED_IN, sources=(FIPAT_TA2,))

    return graph


def build_m08_pinky_reference_graph() -> AnatomyGraph:
    """Build the M08 right-hand digit graph.

    This started as a strict little-finger correction, then expanded to the
    whole right hand: thumb through little finger, each metacarpal, each
    phalanx, and explicit CMC/MCP/IP/PIP/DIP joint nodes rather than implied
    renderer-only links.
    """

    graph = build_m02_reference_graph()

    graph.edges = [
        edge
        for edge in graph.edges
        if not (
            edge.from_id == "region:right_hand"
            and edge.to_id == "body:human"
            and edge.kind == EdgeKind.PART_OF
        )
    ]

    def add_node(
        node_id: str,
        label: str,
        kind: AnatomyKind,
        *,
        sources: tuple[SourceRef, ...],
        materialization: MaterializationState = MaterializationState.CANONICAL,
        aliases: tuple[str, ...] = (),
        properties: dict[str, object] | None = None,
        control_channels: tuple[str, ...] = (),
        llm_visible: bool = False,
    ) -> None:
        node = AnatomyNode(
            id=node_id,
            label=label,
            kind=kind,
            sources=sources,
            materialization=materialization,
            aliases=aliases,
            properties=properties or {},
            control_channels=control_channels,
            llm_visible=llm_visible,
        )
        if node_id in graph.nodes:
            graph.nodes[node_id] = node
        else:
            graph.add_node(node)

    def add_edge(
        from_id: str,
        to_id: str,
        kind: EdgeKind,
        *,
        sources: tuple[SourceRef, ...],
        properties: dict[str, object] | None = None,
    ) -> None:
        if any(
            edge.from_id == from_id and edge.to_id == to_id and edge.kind == kind
            for edge in graph.edges
        ):
            return
        graph.add_edge(
            AnatomyEdge(
                from_id=from_id,
                to_id=to_id,
                kind=kind,
                sources=sources,
                properties=properties or {},
            )
        )

    add_node(
        "region:right_upper_limb",
        "Right upper limb",
        AnatomyKind.REGION,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
        aliases=("right arm and hand",),
        properties={"side": "right"},
        control_channels=("anatomy_layer", "pose_focus"),
        llm_visible=True,
    )
    add_edge(
        "region:right_upper_limb",
        "body:human",
        EdgeKind.PART_OF,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
    )
    add_edge(
        "region:right_hand",
        "region:right_upper_limb",
        EdgeKind.PART_OF,
        sources=(OPENSTAX_8_2, FIPAT_TA2),
    )

    hand_sources = (OPENSTAX_8_2, FIPAT_TA2, GRAY_1918)
    finger_digit_channels = (
        "flexion_extension",
        "abduction_adduction",
        "circumduction_proxy",
        "finger_curl",
    )

    digit_specs = (
        {
            "key": "pollex",
            "digit_id": "digit:right_pollex",
            "label": "Right thumb",
            "digit_index": 1,
            "ordinal": "first",
            "metacarpal_id": "bone:right_first_metacarpal",
            "metacarpal_label": "Right first metacarpal",
            "aliases": ("thumb", "pollex", "digit 1", "digit I"),
            "digit_channels": ("opposition", "flexion_extension", "abduction_adduction"),
            "metacarpal_channels": ("anatomy_layer", "pose_proxy", "opposition_proxy"),
            "phalanges": (
                ("proximal", "bone:right_pollex_proximal_phalanx", "Right thumb proximal phalanx"),
                ("distal", "bone:right_pollex_distal_phalanx", "Right thumb distal phalanx"),
            ),
            "mcp_controls": ("flexion_extension",),
            "cmc_controls": ("opposition", "carpometacarpal_glide"),
        },
        {
            "key": "index_finger",
            "digit_id": "digit:right_index_finger",
            "label": "Right index finger",
            "digit_index": 2,
            "ordinal": "second",
            "metacarpal_id": "bone:right_second_metacarpal",
            "metacarpal_label": "Right second metacarpal",
            "aliases": ("index finger", "digit 2", "digit II"),
            "digit_channels": finger_digit_channels,
            "metacarpal_channels": ("anatomy_layer", "pose_proxy", "limited_glide_proxy"),
            "phalanges": (
                (
                    "proximal",
                    "bone:right_index_finger_proximal_phalanx",
                    "Right index finger proximal phalanx",
                ),
                (
                    "middle",
                    "bone:right_index_finger_middle_phalanx",
                    "Right index finger middle phalanx",
                ),
                (
                    "distal",
                    "bone:right_index_finger_distal_phalanx",
                    "Right index finger distal phalanx",
                ),
            ),
            "mcp_controls": ("flexion_extension", "abduction_adduction", "circumduction_proxy"),
            "cmc_controls": ("limited_glide",),
        },
        {
            "key": "middle_finger",
            "digit_id": "digit:right_middle_finger",
            "label": "Right middle finger",
            "digit_index": 3,
            "ordinal": "third",
            "metacarpal_id": "bone:right_third_metacarpal",
            "metacarpal_label": "Right third metacarpal",
            "aliases": ("middle finger", "digit 3", "digit III"),
            "digit_channels": finger_digit_channels,
            "metacarpal_channels": ("anatomy_layer", "pose_proxy", "limited_glide_proxy"),
            "phalanges": (
                (
                    "proximal",
                    "bone:right_middle_finger_proximal_phalanx",
                    "Right middle finger proximal phalanx",
                ),
                (
                    "middle",
                    "bone:right_middle_finger_middle_phalanx",
                    "Right middle finger middle phalanx",
                ),
                (
                    "distal",
                    "bone:right_middle_finger_distal_phalanx",
                    "Right middle finger distal phalanx",
                ),
            ),
            "mcp_controls": ("flexion_extension", "abduction_adduction", "circumduction_proxy"),
            "cmc_controls": ("limited_glide",),
        },
        {
            "key": "ring_finger",
            "digit_id": "digit:right_ring_finger",
            "label": "Right ring finger",
            "digit_index": 4,
            "ordinal": "fourth",
            "metacarpal_id": "bone:right_fourth_metacarpal",
            "metacarpal_label": "Right fourth metacarpal",
            "aliases": ("ring finger", "digit 4", "digit IV"),
            "digit_channels": finger_digit_channels + ("palm_cupping",),
            "metacarpal_channels": (
                "anatomy_layer",
                "pose_proxy",
                "limited_glide_proxy",
                "palm_cupping_proxy",
            ),
            "phalanges": (
                (
                    "proximal",
                    "bone:right_ring_finger_proximal_phalanx",
                    "Right ring finger proximal phalanx",
                ),
                (
                    "middle",
                    "bone:right_ring_finger_middle_phalanx",
                    "Right ring finger middle phalanx",
                ),
                (
                    "distal",
                    "bone:right_ring_finger_distal_phalanx",
                    "Right ring finger distal phalanx",
                ),
            ),
            "mcp_controls": ("flexion_extension", "abduction_adduction", "circumduction_proxy"),
            "cmc_controls": ("limited_glide", "palm_cupping_proxy"),
        },
        {
            "key": "little_finger",
            "digit_id": "digit:right_little_finger",
            "label": "Right little finger",
            "digit_index": 5,
            "ordinal": "fifth",
            "metacarpal_id": "bone:right_fifth_metacarpal",
            "metacarpal_label": "Right fifth metacarpal",
            "aliases": (
                "pinky",
                "little finger",
                "digit 5",
                "digit V",
                "fifth finger",
                "digitus minimus manus",
            ),
            "digit_channels": finger_digit_channels + ("palm_cupping",),
            "metacarpal_channels": (
                "anatomy_layer",
                "pose_proxy",
                "limited_glide_proxy",
                "palm_cupping_proxy",
            ),
            "phalanges": (
                (
                    "proximal",
                    "bone:right_little_finger_proximal_phalanx",
                    "Right little finger proximal phalanx",
                ),
                (
                    "middle",
                    "bone:right_little_finger_middle_phalanx",
                    "Right little finger middle phalanx",
                ),
                (
                    "distal",
                    "bone:right_little_finger_distal_phalanx",
                    "Right little finger distal phalanx",
                ),
            ),
            "mcp_controls": ("flexion_extension", "abduction_adduction", "circumduction_proxy"),
            "cmc_controls": ("limited_glide", "palm_cupping_proxy"),
        },
    )

    ordinal_to_digit = {
        "first": "1",
        "second": "2",
        "third": "3",
        "fourth": "4",
        "fifth": "5",
    }

    for spec in digit_specs:
        digit_index = spec["digit_index"]
        digit_id = spec["digit_id"]
        metacarpal_id = spec["metacarpal_id"]
        phalanges = spec["phalanges"]
        ordinal = spec["ordinal"]

        add_node(
            digit_id,
            spec["label"],
            AnatomyKind.STRUCTURE,
            sources=hand_sources,
            aliases=spec["aliases"],
            properties={"side": "right", "digit_index": digit_index},
            control_channels=spec["digit_channels"],
            llm_visible=True,
        )
        add_edge(digit_id, "region:right_hand", EdgeKind.PART_OF, sources=(OPENSTAX_8_2, FIPAT_TA2))

        add_node(
            metacarpal_id,
            spec["metacarpal_label"],
            AnatomyKind.BONE,
            sources=hand_sources,
            aliases=(f"metacarpal {ordinal_to_digit[ordinal]}", f"metacarpal {ordinal}"),
            properties={"side": "right", "ray": digit_index},
            control_channels=spec["metacarpal_channels"],
            llm_visible=True,
        )
        add_edge(
            metacarpal_id,
            "aggregate:right_metacarpals",
            EdgeKind.PART_OF,
            sources=(OPENSTAX_8_2, FIPAT_TA2),
        )
        add_edge(metacarpal_id, "region:right_hand", EdgeKind.LOCATED_IN, sources=hand_sources)

        cmc_joint_id = f"joint:right_{ordinal}_carpometacarpal"
        add_node(
            cmc_joint_id,
            f"Right {ordinal} carpometacarpal joint",
            AnatomyKind.JOINT,
            sources=(GRAY_1918, FIPAT_TA2),
            aliases=("CMC", f"{ordinal} CMC"),
            properties={"side": "right", "digit_index": digit_index, "joint_code": "cmc"},
            control_channels=spec["cmc_controls"] + ("anatomy_layer",),
            llm_visible=True,
        )
        add_edge(
            cmc_joint_id, "region:right_hand", EdgeKind.PART_OF, sources=(GRAY_1918, FIPAT_TA2)
        )
        for bone_or_aggregate_id in ("aggregate:right_carpals", metacarpal_id):
            add_edge(
                bone_or_aggregate_id,
                cmc_joint_id,
                EdgeKind.CONNECTS_TO,
                sources=(GRAY_1918, FIPAT_TA2),
            )

        for order, (segment, phalanx_id, label) in enumerate(phalanges, start=1):
            add_node(
                phalanx_id,
                label,
                AnatomyKind.BONE,
                sources=(OPENSTAX_8_2, FIPAT_TA2),
                aliases=(f"{segment} phalanx of digit {digit_index}",),
                properties={
                    "side": "right",
                    "digit_index": digit_index,
                    "segment": segment,
                    "proximal_to_distal_order": order,
                },
                control_channels=("anatomy_layer", "pose_proxy", "flexion_extension_proxy"),
                llm_visible=True,
            )
            add_edge(phalanx_id, digit_id, EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))
            add_edge(
                phalanx_id,
                "aggregate:right_hand_phalanges",
                EdgeKind.MEMBER_OF,
                sources=(OPENSTAX_8_2,),
            )

        proximal_phalanx_id = phalanges[0][1]
        mcp_joint_id = f"joint:right_{ordinal}_metacarpophalangeal"
        add_node(
            mcp_joint_id,
            f"Right {ordinal} metacarpophalangeal joint",
            AnatomyKind.JOINT,
            sources=hand_sources,
            aliases=("MCP", f"{ordinal} MCP"),
            properties={"side": "right", "digit_index": digit_index, "joint_code": "mcp"},
            control_channels=spec["mcp_controls"] + ("anatomy_layer",),
            llm_visible=True,
        )
        add_edge(mcp_joint_id, digit_id, EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))
        for bone_id in (metacarpal_id, proximal_phalanx_id):
            add_edge(bone_id, mcp_joint_id, EdgeKind.CONNECTS_TO, sources=hand_sources)

        if len(phalanges) == 2:
            ip_joint_id = "joint:right_pollex_interphalangeal"
            add_node(
                ip_joint_id,
                "Right thumb interphalangeal joint",
                AnatomyKind.JOINT,
                sources=hand_sources,
                aliases=("IP", "thumb IP"),
                properties={"side": "right", "digit_index": digit_index, "joint_code": "ip"},
                control_channels=("flexion_extension", "anatomy_layer"),
                llm_visible=True,
            )
            add_edge(ip_joint_id, digit_id, EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))
            for bone_id in (phalanges[0][1], phalanges[1][1]):
                add_edge(bone_id, ip_joint_id, EdgeKind.CONNECTS_TO, sources=hand_sources)
        else:
            joint_pairs = (
                ("proximal_interphalangeal", "PIP", phalanges[0][1], phalanges[1][1]),
                ("distal_interphalangeal", "DIP", phalanges[1][1], phalanges[2][1]),
            )
            for joint_name, alias, proximal_bone_id, distal_bone_id in joint_pairs:
                joint_id = f"joint:right_{spec['key']}_{joint_name}"
                add_node(
                    joint_id,
                    f"{spec['label']} {joint_name.replace('_', ' ')} joint",
                    AnatomyKind.JOINT,
                    sources=hand_sources,
                    aliases=(alias,),
                    properties={
                        "side": "right",
                        "digit_index": digit_index,
                        "joint_code": alias.lower(),
                    },
                    control_channels=("flexion_extension", "anatomy_layer"),
                    llm_visible=True,
                )
                add_edge(joint_id, digit_id, EdgeKind.PART_OF, sources=(OPENSTAX_8_2,))
                for bone_id in (proximal_bone_id, distal_bone_id):
                    add_edge(bone_id, joint_id, EdgeKind.CONNECTS_TO, sources=hand_sources)

    return graph


def build_m08_right_hand_digits_reference_graph() -> AnatomyGraph:
    """Build the source-backed M08 graph for all right-hand digits."""

    return build_m08_pinky_reference_graph()
