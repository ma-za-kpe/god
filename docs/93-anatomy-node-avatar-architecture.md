# Anatomy Node Avatar Architecture

Status: concept design, no implementation yet.

This document defines the next avatar direction: build our own avatar body from a factual anatomy graph, then render and control that graph through LLM intent. The goal is not to keep swapping static GLB clothing or morph targets. The goal is to make the body itself the control surface.

## Goal

Create a `Body` model whose anatomy is represented as nodes and relationships:

- Whole body -> regions -> systems -> organs -> tissues -> anatomical structures -> renderable/control instances.
- Bones, joints, muscles, tendons, ligaments, arteries, veins, lymphatics, nerves, organs, skin, glands, hair follicles, nails, vessels, and sensory structures are all graph nodes.
- The LLM never invents nodes. It queries a registry/RAG layer, receives valid nodes and capabilities, and returns bounded control intent.
- Code owns schema, source attribution, validation, safety clamps, renderer adapters, and diagnostics.
- The LLM owns semantic intent: wave, sit, run, look left, sweat, blush, breathe faster, raise both hands, change visible wardrobe layer, expose anatomy layer, etc.

This is TDD-heavy. We should not render a fake "knee" if the knee graph does not pass anatomy coverage and relationship tests.

## Project Stance

We are building this.

The correction is not to lower the ambition. The correction is to avoid the naive implementation. The avatar body should become an addressable biological graph, including microscopic and population-level structures when the use case needs them. But "addressable node" does not always mean "hand-authored physical row, active every frame, sent to the LLM context, and rendered as a unique mesh."

The project bet:

```text
explicit anatomy addressability + hierarchical abstraction + lazy materialization + mature execution backends
```

That means:

- The graph can represent a hair follicle population, a sweat gland population, a capillary bed, or a skin receptor population as first-class addressable nodes.
- Individual instances can be materialized procedurally or cached only when a view/action needs them.
- Full-body actions activate compiled bundles, not every microscopic descendant.
- The LLM plans at semantic and bounded-control levels; deterministic planners, graph traversal, and simulation backends expand that plan.
- We use existing anatomy atlases, ontologies, biomechanics tools, rigging tools, and simulation engines wherever they already solve a hard part.

## Reference Stack

Use authoritative anatomy sources as the source-of-truth path:

- OpenStax Anatomy and Physiology 2e for system structure, organization levels, and textbook anatomy sequencing. It organizes the body by levels, regions, integument, skeletal, muscular, nervous, blood, cardiovascular, lymphatic, respiratory, digestive, urinary, reproductive, endocrine, and senses.
- FIPAT Terminologia Anatomica, 2nd edition, for standardized anatomical naming. FIPAT terms are the naming baseline for canonical ids and aliases.
- Foundational Model of Anatomy (FMA) for ontology structure. FMA is explicitly a machine-navigable representation of human anatomy classes and relationships.
- NCBI Bookshelf/StatPearls for focused factual checks, especially system details such as integumentary components and lymphatic structures.

Sources:

- OpenStax Anatomy and Physiology 2e: https://openstax.org/books/anatomy-and-physiology-2e
- OpenStax Ch. 1 Introduction: https://openstax.org/books/anatomy-and-physiology-2e/pages/1-introduction
- OpenStax skeletal divisions: https://openstax.org/books/anatomy-and-physiology-2e/pages/7-1-divisions-of-the-skeletal-system
- OpenStax blood vessels: https://openstax.org/books/anatomy-and-physiology-2e/pages/20-1-structure-and-function-of-blood-vessels
- FIPAT Terminologia Anatomica: https://libraries.dal.ca/Fipat/ta2.html
- Foundational Model of Anatomy, University of Washington: https://bime.uw.edu/research/foundational-model-of-anatomy/
- NCBI/StatPearls integument: https://www.ncbi.nlm.nih.gov/books/NBK554386/
- NCBI/StatPearls lymphatic system: https://www.ncbi.nlm.nih.gov/books/NBK513247/
- Human Reference Atlas KG docs: https://docs.humanatlas.io/apps/kg
- HRA KG repository: https://github.com/hubmapconsortium/hra-kg
- HRA KG supporting information: https://cns-iu.github.io/hra-kg-supporting-information/
- OpenSim: https://simtk.org/projects/opensim
- OpenSim Moco: https://simtk.org/projects/opensim-moco
- OpenSimRT: https://github.com/mitkof6/OpenSimRT
- MuSkeMo: https://github.com/PashavanBijlert/MuSkeMo
- SOFA: https://www.sofa-framework.org/
- FEBio: https://simtk.org/projects/febio
- Neo4j GraphRAG package: https://neo4j.com/developer/genai-ecosystem/graphrag-python/
- KRAGEN biomedical KG-RAG: https://pmc.ncbi.nlm.nih.gov/articles/PMC11164829/

## Non-Negotiable Design Rules

1. Anatomy is data, not prompt text.
2. Every node must have provenance: source, source version/date when available, and confidence.
3. Every rendered/control node must map back to an anatomy node.
4. The graph must support multiple levels of detail. We cannot feed "all follicles in the scalp" to the LLM every frame.
5. The LLM can request activation and control, but code validates node existence, permissions, ranges, and renderer support.
6. Unsupported anatomy/control requests must degrade visibly in diagnostics.
7. Hardcoded anatomy is allowed only as test fixtures or seed data until replaced by sourced loaders.
8. Rendering is a projection of the graph. It must not become the source of truth.
9. Do not reinvent mature anatomy, rigging, biomechanics, or simulation tooling. Our product layer is the semantic graph, RAG planner, control contract, renderer bridge, and body-scale node operating model.

## Do Not Reinvent The Wheel

The anatomy-node graph is not a replacement for musculoskeletal simulators, medical physics engines, Blender rigging, GLB pipelines, or existing anatomical ontologies. It is the orchestration layer that lets an LLM safely talk to them.

Use existing tools as execution backends:

| Problem | Mature Tooling To Reuse | How It Fits |
| --- | --- | --- |
| Canonical human anatomy names and relationships | FIPAT Terminologia Anatomica, FMA, Uberon, UMLS where licensing allows | Seed canonical ids, aliases, synonyms, hierarchy, and cross-references. |
| 3D anatomical geometry | BodyParts3D/Anatomography, Z-Anatomy, Open Anatomy Project, HuBMAP/Human Reference Atlas, SPARC scaffolds | Import or map anatomy nodes to real meshes/scaffolds instead of modeling everything manually. |
| Musculoskeletal modeling and movement | OpenSim, OpenSim Moco, MuSkeMo, AnyBody where license/business fit allows, MyoSuite/MyoSim for muscle-driven RL-style control | Compute or validate joint/muscle activation plans, then project to avatar controls. |
| Soft tissue, organs, medical simulation | SOFA, FEBio | Use as optional high-fidelity sidecars for offline/precomputed simulations or specific educational anatomy views. |
| Web/game avatar delivery | Blender, glTF/GLB, Three.js, VRM, standard armature/skinning/morph targets | Keep browser runtime practical and GPU-friendly. |
| Massive retrieval | GraphRAG, RAPTOR, LightRAG, graph DB + vector search, hierarchical summaries | Retrieve compact action bundles instead of sending huge anatomy graphs to the LLM. |

The project should not eagerly hand-author one physical database row for every hair follicle unless a specific LOD needs materialized instances. We model "scalp hair follicle population" as a sourced, queryable node with density/region metadata, then expand it procedurally for rendering or cache selected materialized instances when needed.

## Scale Problem

The dangerous naive design is:

```text
one anatomical microstructure = one always-loaded LLM node
```

That fails quickly:

- Roughly 206 bones.
- 600+ named skeletal muscles, each with origin, insertion, innervation, action, and blood supply.
- Thousands of named vessels/nerves plus capillary beds and regional branches.
- Skin as one continuous organ with regional patches, layers, glands, receptors, hair-bearing and non-hair-bearing regions.
- Hair follicles, sweat glands, sebaceous glands, cutaneous receptors, capillary loops, and immune/cell populations that can reach millions of renderable instances.

The scalable design is:

```text
anatomy graph -> hierarchy/community summaries -> semantic action bundle -> renderer-supported control subset
```

For "running," the LLM should not receive every vessel, follicle, and capillary. It should receive a bounded activation bundle:

- primary effectors: hips, knees, ankles, toes, pelvis, spine, shoulders, elbows
- muscle groups: gluteals, quadriceps, hamstrings, calves, core, arm swing muscles
- physiological responders: heart rate, breathing, sweat, skin flush, hair/clothing inertia
- passive deformation nodes: skin and clothing surfaces
- optional anatomy layer nodes: skeleton/muscle overlay if the view requests it

Microstructures remain reachable by drill-down queries, not by default context.

## Scale Doctrine

The core difficulty is not storage. A graph database can hold millions of nodes. The hard problem is real-time compilation:

```text
massive biological address space -> small, action-specific working set -> renderer/simulation commands
```

So the architecture must distinguish:

- stored graph: the factual anatomy source of truth
- virtual graph: procedurally addressable microscopic structures
- retrieval graph: indexes, communities, embeddings, and summaries
- activation graph: the current action's active working set
- render graph: what the renderer can draw this frame
- simulation graph: what a backend such as OpenSim, SOFA, FEBio, or MuSkeMo needs
- LLM context: the smallest meaningful bundle the model needs for planning

These are not the same graph view.

For a full-body action like running, the planner should activate a large percentage of body systems conceptually, but it should not expand every descendant into low-level control records. It compiles a hierarchy:

```text
run
  locomotion_controller
    pelvis/spine/hips/knees/ankles/toes
    lower_limb_muscle_groups
    arm_swing_groups
    breathing_pulse_sweat_skin_response
    optional anatomy_overlay_nodes
```

For a microscope/close-up action like "show sweat forming on the forehead," the same system intentionally narrows the body region and increases LOD:

```text
forehead_skin_patch
  epidermis/dermis/hypodermis
  eccrine_sweat_gland_population
  capillary_bed_proxy
  droplet_render_instances
```

This is how we can build the system we want without letting context windows, graph traversals, and animation latency collapse.

## What We Are Actually Inventing

We are not inventing anatomy names, finite-element solvers, musculoskeletal dynamics, Blender rigging, or GLB delivery.

We are inventing the body-scale control operating model:

1. A factual, source-cited, addressable anatomy graph that spans macro, meso, and micro levels.
2. A lazy materialization system for microscopic/procedural biological nodes.
3. A GraphRAG/action compiler that turns language into compact anatomy working sets.
4. A validator that prevents the LLM from inventing anatomy or invalid physical controls.
5. A backend bridge that can target OpenSim/Moco, MuSkeMo/Blender, SOFA/FEBio, GLB/VRM, and browser renderers.
6. A diagnostic layer that says exactly which anatomy was real, approximated, simulated, projected, or unsupported.

That is the product. The mature tools are engines and data sources underneath it.

## Node Materialization Model

A node can exist at different runtime states:

| State | Meaning | Example |
| --- | --- | --- |
| canonical | Stored as a sourced anatomy graph node. | `right_femur`, `mandible`, `heart`, `brainstem` |
| aggregate | Represents a region, tissue, or system collection. | `skin_of_right_great_toe`, `genicular_arterial_network` |
| population_template | Represents many similar biological structures without instantiating every member. | `scalp_hair_follicle_population`, `forehead_eccrine_sweat_gland_population` |
| virtual_instance | Addressable by generated id/range but not stored until needed. | `scalp_hair_follicle_population[patch=frontal,index=1200]` |
| materialized_instance | Stored or cached because an interaction, render layer, or test needs it. | selected follicles in a close-up scalp view |
| render_proxy | A visual/control approximation mapped back to anatomy. | instanced follicle particles, sweat shader, capillary texture |
| simulation_proxy | Backend-specific representation for a simulator. | OpenSim muscle path, SOFA tetrahedral soft-tissue mesh |

This keeps the ambition intact: the LLM and runtime can refer to microscopic structures, but most microstructures exist as procedural or aggregate address space until a query demands detail.

## LOD Activation Policy

Every action compiles to a level-of-detail activation plan:

```text
semantic action -> retrieve anatomical community -> choose LOD -> materialize bundle -> validate -> execute
```

Example: `run`

| Layer | Runtime Treatment |
| --- | --- |
| skeleton/joints | Active direct controls for pelvis, spine, hips, knees, ankles, toes, shoulders, elbows. |
| muscles | Active group-level or simulator-level controls; individual muscles only if needed for anatomy/diagnostics view. |
| cardiovascular | Aggregate responders: heart rate, pulse shader, large-vessel overlay if visible. |
| respiratory | Aggregate breathing controls. |
| skin | Surface deformation, sweat/flush shader, regional patches. |
| follicles/glands/capillaries | Population-template activation, not millions of explicit control outputs. |
| brain/nervous system | Control-state abstraction plus optional visible anatomy layer. |

Example: `close-up sweat on forehead`

| Layer | Runtime Treatment |
| --- | --- |
| face/head | Stable pose and camera close-up. |
| forehead skin | Materialized regional skin patch. |
| sweat glands | Population template expanded to visible droplets/shader emission. |
| capillary beds | Optional color/flush proxy. |
| follicles | Optional visible population instances if camera distance requires it. |

This is how the system can honestly say "the sweat gland nodes are part of the body graph" without asking the LLM to emit millions of per-gland controls.

## Modern Research And Tooling Map

### Anatomy Knowledge Graphs And Ontologies

- FMA is still the most directly relevant machine-oriented human anatomy ontology. It represents anatomical classes and relationships in a machine-parseable form.
- FIPAT Terminologia Anatomica is the naming baseline. Use it for canonical display labels and Latin names.
- Uberon is useful for cross-ontology and cross-species anatomy mapping; HuBMAP/HRA work has extended anatomical and cell-type terminology for healthy human atlas construction.
- UMLS/SNOMED CT can help synonym and clinical mapping, but licensing and distribution must be reviewed before use.
- HRA KG is the best practical proof that large, cross-scale human-body knowledge graphs are real engineering artifacts, not fantasy. Exact graph counts vary by release and graph subset, so we should query the HRA dashboard/API during implementation instead of hardcoding public claims.

### 3D Atlases And Whole-Body Scaffolds

- BodyParts3D/Anatomography maps anatomical concepts to 3D structure data for a whole-body adult human male model.
- Z-Anatomy builds an open 3D anatomy atlas in Blender, using and reorganizing BodyParts3D-style anatomical objects.
- Open Anatomy Project focuses on open, high-quality digital anatomy atlases.
- HuBMAP Human Reference Atlas is a multiscale, multimodal 3D atlas of healthy human anatomical structures and cells.
- SPARC uses 2D flatmaps and 3D anatomical organ/whole-body scaffolds to map nerve-organ anatomy and function.

These are better starting points than hand-modeling bones, organs, vessels, and nerves.

### Biomechanics And Simulation

- OpenSim is the default open musculoskeletal modeling and simulation candidate.
- OpenSim Moco adds optimal-control workflows for tracking, predicting, and optimizing movement in OpenSim models.
- MuSkeMo is useful because it lives in Blender and is designed to construct, analyze, and visualize musculoskeletal models and movement.
- SOFA is appropriate for interactive mechanical simulation with emphasis on biomechanics and robotics.
- FEBio is appropriate for nonlinear finite-element biomechanics/biophysics.
- SCONE and OpenSim Moco are relevant for predictive/optimized movement.
- AnyBody is relevant as a commercial high-fidelity validation/reference path when licensing and budget make sense.
- MyoSuite/MyoSim and related muscle-driven RL environments are interesting for learning/control experiments where muscle actuation matters.

Use these for validation, precomputation, or sidecar simulation. The browser renderer should consume simplified results, not run medical-grade FEM every frame.

### GraphRAG And Hierarchical Retrieval

The RAG direction should follow modern graph/hierarchical retrieval:

- GraphRAG: extract/build graph, detect communities, summarize communities, retrieve local entity neighborhoods or global summaries.
- RAPTOR: recursively cluster and summarize content into a retrieval tree.
- LightRAG: dual-level retrieval over graph structures and vector representations.
- Biomedical GraphRAG work such as MedGraphRAG/BioGraphRAG shows the same idea applied to medical/biomedical knowledge.
- KRAGEN is directly relevant because it combines knowledge graphs, RAG, and graph-of-thought-style decomposition for biomedical problem solving.
- Neo4j's `VectorCypherRetriever` pattern is especially relevant: vector retrieval finds likely entities, then Cypher expands the graph neighborhood into structured context.

For us, this means:

```text
query: "wave right hand"
local graph retrieval: right shoulder/elbow/wrist/hand/fingers + nerve/muscle/skin dependencies
community summary: upper-limb waving mechanics
renderer intersection: only nodes current renderer can apply now
LLM prompt: compact bundle, not full body graph
```

For body control, use a two-pass retrieval contract:

```text
Pass 1: semantic planner
  input: user action + current body state
  output: action class, body regions, required LOD, candidate systems

Pass 2: graph compiler
  input: action class + regions + renderer/simulator capabilities
  output: bounded node bundle with primary, secondary, passive, diagnostic roles
```

Only the second pass goes to the LLM for fine intent, and even then the validator owns the final authority.

## Proposed Layered Architecture

```text
Anatomy Source Layer
  textbooks, FIPAT, FMA, BodyParts3D, Z-Anatomy, HuBMAP/HRA, SPARC

Canonical Anatomy Graph
  sourced nodes, edges, synonyms, hierarchy, LOD, capabilities

Action Knowledge Layer
  action templates, motion primitives, biomechanical dependencies,
  GraphRAG community summaries, vector embeddings

Simulation/Validation Backends
  OpenSim/Moco, MuSkeMo/Blender, SOFA/FEBio, MyoSuite, offline caches

Runtime Planner
  query -> retrieve bundle -> intersect renderer capabilities -> ask LLM

Renderer Projection
  GLB/VRM/Three.js meshes, curves, morphs, skeletons, materials,
  instanced population proxies, diagnostics
```

The LLM should never see "millions of nodes." It should see the current level of abstraction plus exact valid handles it can operate.

More precisely: the system may contain millions of virtual or materialized nodes, but a single LLM request should receive only the compiled working set for the current action, camera, layer mode, and renderer capability.

## Core Domain Model

### Entity Classes

`Body`

- Root aggregate for one avatar body.
- Owns identity, biological template, scale, sex/age/body-shape parameters where relevant, graph version, and render profile.
- Contains systems, regions, and node registry.

`AnatomyNode`

- The universal base node.
- Examples: skull, frontal bone, cerebral cortex, popliteal artery, epidermis of right great toe, eccrine sweat gland population of right palm, hair follicle population of scalp.

`AnatomyEdge`

- Typed relationship between nodes.
- Examples: `part_of`, `contains`, `adjacent_to`, `articulates_with`, `originates_from`, `inserts_on`, `innervated_by`, `vascularized_by`, `drains_to`, `covered_by`, `surface_of`, `controls_motion_of`, `mirrors`.

`NodeCapability`

- What the runtime can do with a node.
- Examples: `render_mesh`, `render_volume`, `deform`, `rotate_joint`, `contract_muscle`, `pulse_vessel`, `color_shift`, `secrete`, `hide_layer`, `xray_layer`, `label`, `simulate_signal`.

`ControlIntent`

- Bounded LLM output.
- Targets real node ids or semantic action ids resolved through RAG.

`RenderProjection`

- Maps anatomy nodes to Three.js meshes, materials, skeleton bones, shader layers, labels, particle systems, or instanced geometry.

### Node Fields

Minimum schema:

```text
id                    Stable canonical id, e.g. body.head.skull.frontal_bone
canonical_name         Preferred English/FIPAT-compatible label
latin_name             Latin name when available
aliases                Common names and renderer aliases
node_type              body, region, organ_system, organ, bone, joint, muscle, tendon,
                       ligament, artery, vein, capillary_bed, lymphatic, nerve,
                       gland, skin_layer, hair_follicle, nail, tooth, brain_region,
                       sensory_organ, connective_tissue, fluid, cell_population,
                       population_template, render_proxy
system                 skeletal, muscular, nervous, cardiovascular, lymphatic,
                       integumentary, respiratory, digestive, urinary, endocrine,
                       reproductive, immune, sensory, fascial/connective, fluid
region                 head, neck, thorax, abdomen, pelvis, upper_limb, lower_limb, etc.
laterality             midline, left, right, bilateral, none
parent_id              Direct containment parent
source_refs            Source urls/books/ontology ids
capabilities           Control/render capabilities
lod                    canonical, regional, tissue, micro, cellular, procedural_instance
render_policy          visible, internal, layer_only, aggregate_only, instanced
control_policy         direct, indirect, semantic_only, simulated, diagnostic_only
safety                 clamps, biomechanical limits, medical-sensitivity flags
```

### Edge Types

The graph must model more than parent/child:

```text
part_of                A is structurally part of B
contains               A spatially contains B
articulates_with       Bone/joint articulation
originates_from        Muscle origin
inserts_on             Muscle insertion
innervated_by          Nerve supply
vascularized_by        Arterial/capillary supply
drains_to              Venous or lymphatic drainage
covered_by             Skin/fascia coverage
passes_through         Vessel/nerve path through region
adjacent_to            Spatial neighbor
controls_motion_of     Contractile/control relationship
deforms_surface        Internal node influences visible skin/mesh
mirrors                Left/right counterpart
depends_on             Motion/action dependency
```

## Top-Level Body Ecosystem

The graph starts with major systems and regions.

```text
body
  regions
    head
    neck
    thorax
    abdomen
    pelvis
    back
    upper_limb.left
    upper_limb.right
    lower_limb.left
    lower_limb.right
  systems
    integumentary
    skeletal
    articular
    muscular
    nervous
    endocrine
    cardiovascular
    lymphatic_immune
    respiratory
    digestive
    urinary
    reproductive
    sensory
    fascial_connective
    fluid
```

OpenStax is useful for the first pass because it already separates organization levels and systems. FIPAT/FMA then provide canonical naming and ontology relationships.

## Granularity Strategy

The user goal says "everything," including hair follicles, sweat glands, toe skin, veins, and brain. The system should support that without requiring us to hand-author billions of individual records.

Use three node granularities:

1. Canonical nodes
   - Named anatomical structures.
   - Example: frontal bone, mandible, right femur, popliteal artery, cerebellum.

2. Regional tissue nodes
   - Region-specific tissue coverage and internal layers.
   - Example: skin of right great toe, dermis of scalp, subcutaneous tissue of left palm.

3. Procedural population nodes
   - Counted or density-driven populations represented by templates.
   - Example: scalp hair follicle population, eccrine sweat gland population of palm, capillary bed of toe skin.
   - The graph stores population metadata; renderer expands into instances only at the needed LOD.

This lets the LLM target "scalp hair follicles" or "sweat glands of the right palm" without loading every individual follicle as prompt context.

## Head First Breakdown

The first implementation milestone should be the head, because it contains visible identity, facial expression, brain, sensory organs, hair, skin, mouth, teeth, cranial nerves, skull, and vessels.

```text
body.head
  integumentary
    scalp_skin
      epidermis
      dermis
      hypodermis
      hair_follicle_population
      sebaceous_gland_population
      sweat_gland_population
      cutaneous_nerve_endings
      capillary_bed
    face_skin
      forehead_skin
      eyelid_skin.left/right
      cheek_skin.left/right
      nose_skin
      lip_skin.upper/lower
      chin_skin
  skeletal
    skull
      neurocranium
        frontal_bone
        parietal_bone.left/right
        temporal_bone.left/right
        occipital_bone
        sphenoid_bone
        ethmoid_bone
      viscerocranium
        mandible
        maxilla.left/right
        zygomatic_bone.left/right
        nasal_bone.left/right
        lacrimal_bone.left/right
        palatine_bone.left/right
        inferior_nasal_concha.left/right
        vomer
      cranial_sutures
      temporomandibular_joint.left/right
  nervous
    brain
      cerebrum
        frontal_lobe.left/right
        parietal_lobe.left/right
        temporal_lobe.left/right
        occipital_lobe.left/right
      diencephalon
      brainstem
        midbrain
        pons
        medulla_oblongata
      cerebellum
      ventricles
      meninges
    cranial_nerves
      CN_I_olfactory
      CN_II_optic
      CN_III_oculomotor
      CN_IV_trochlear
      CN_V_trigeminal
      CN_VI_abducens
      CN_VII_facial
      CN_VIII_vestibulocochlear
      CN_IX_glossopharyngeal
      CN_X_vagus
      CN_XI_accessory
      CN_XII_hypoglossal
  sensory
    eye.left/right
      globe
      cornea
      sclera
      iris
      pupil
      lens
      retina
      optic_nerve
      extraocular_muscles
      lacrimal_gland
    ear.left/right
      external_ear
      tympanic_membrane
      middle_ear
      ossicles
      inner_ear
      cochlea
      vestibular_apparatus
    nose
      nasal_cavity
      nasal_septum
      nasal_conchae
      olfactory_epithelium
      paranasal_sinuses
    tongue
      intrinsic_muscles
      extrinsic_muscles
      taste_bud_population
  oral
    lips
    oral_cavity
    teeth
      maxillary_teeth
      mandibular_teeth
    tongue
    palate
    salivary_glands
      parotid.left/right
      submandibular.left/right
      sublingual.left/right
  muscular
    muscles_of_facial_expression
    muscles_of_mastication
    extraocular_muscles
    tongue_muscles
  cardiovascular
    arterial_supply
      carotid_system
      facial_artery.left/right
      superficial_temporal_artery.left/right
    venous_drainage
      jugular_system
      facial_vein.left/right
  lymphatic_immune
    cervical_lymph_node_groups
    lymphatic_vessels_head_neck
```

The brain is a first-class node. It is not only a visual object; it is also the command-center abstraction for gaze, expression, speech intent, emotional tone, and autonomic simulation.

## Toe-Level Breakdown

The smallest visible regions should still be structured.

Example: right great toe.

```text
body.lower_limb.right.foot.great_toe
  skeletal
    distal_phalanx
    proximal_phalanx
    interphalangeal_joint
    metatarsophalangeal_joint
  articular
    joint_capsule
    collateral_ligaments
    plantar_plate
  muscular_tendon
    flexor_hallucis_longus_tendon
    extensor_hallucis_longus_tendon
    intrinsic_foot_muscle_insertions
  integumentary
    dorsal_skin
      epidermis
      dermis
      hypodermis
      hair_follicle_population_if_region_allows
      sweat_gland_population
      sebaceous_gland_population_if_hairy_skin
      sensory_receptor_population
      capillary_bed
    plantar_skin
      thick_epidermis
      stratum_lucidum_region
      dermis
      hypodermis
      sweat_gland_population
      sensory_receptor_population
    nail_unit
      nail_plate
      nail_bed
      nail_matrix
      cuticle
  cardiovascular
    digital_arteries
    digital_veins
    capillary_beds
  nervous
    digital_nerves
  lymphatic
    superficial_lymphatics
```

This is the pattern for every toe, finger, eyelid, nostril, lip region, and skin patch.

## Knee Example

If the LLM asks to bend the knee, sit, walk, kneel, kick, or run, the system should retrieve a knee subgraph like this:

```text
body.lower_limb.right.knee
  skeletal
    distal_femur
      medial_condyle
      lateral_condyle
    proximal_tibia
      medial_condyle
      lateral_condyle
      tibial_tuberosity
    patella
    proximal_fibula
  articular
    tibiofemoral_joint
    patellofemoral_joint
    articular_cartilage
    medial_meniscus
    lateral_meniscus
    joint_capsule
    synovial_membrane
    anterior_cruciate_ligament
    posterior_cruciate_ligament
    medial_collateral_ligament
    lateral_collateral_ligament
    patellar_ligament
    quadriceps_tendon
    bursae
  muscular
    quadriceps_group
    hamstrings_group
    gastrocnemius_heads
    popliteus
    sartorius
    gracilis
  cardiovascular
    popliteal_artery
    popliteal_vein
    genicular_arterial_network
    superficial_veins
  nervous
    tibial_nerve
    common_fibular_nerve
    saphenous_nerve
  lymphatic
    popliteal_lymph_nodes
    superficial_lymphatics
  integumentary
    anterior_knee_skin
    posterior_knee_skin
    sweat_gland_population
    hair_follicle_population
    cutaneous_receptors
```

Semantic action query:

```text
action: sit
retrieve: hips, knees, ankles, spine, pelvis, major lower-limb muscles,
          balance/gaze nodes, skin/clothing deformation, cardiovascular/breathing support
control: flex hips, flex knees, dorsiflex ankles, stabilize trunk,
         contract agonists/antagonists, update skin and clothing deformation
render: visible mesh joints, muscle volume proxy, skin folds, optional xray anatomy overlay
```

## Movement as Graph Activation

A semantic motion is not one bone rotation. It is a graph activation plan.

Example: wave.

```text
intent: wave
primary nodes:
  shoulder joint
  elbow joint
  wrist joint
  hand and finger joints
  deltoid, rotator cuff, biceps/triceps, forearm muscles
secondary nodes:
  clavicle, scapula, humerus, radius, ulna, hand bones
  brachial artery, superficial veins
  brachial plexus branches
  skin of upper limb, sweat/hair populations
  torso counterbalance muscles
passive nodes:
  skin deformation
  clothing deformation
  hair/body sway
  breathing and cardiovascular pulse
```

Example: running.

```text
intent: run
primary nodes:
  pelvis, spine, hips, knees, ankles, toes, shoulders, elbows
  gluteals, quadriceps, hamstrings, calves, intrinsic foot muscles
secondary nodes:
  respiratory system, heart, major arteries/veins, skin/sweat glands
  vestibular system, visual gaze, cerebellum/balance abstraction
  arm swing, neck stabilization
passive nodes:
  skin, hair, clothing, soft tissue, foot impact, visible sweat/pulse
```

The RAG system should return a compact activation bundle, not the whole anatomy graph. The bundle contains:

- Primary effectors.
- Required dependent structures.
- Passive visual/physiological responders.
- Renderer-supported nodes.
- Unsupported but requested nodes for diagnostics.

## Storage Model

Use a graph-friendly relational model first, with optional vector search.

Tables:

```text
anatomy_nodes
  id primary key
  canonical_name
  latin_name
  node_type
  system
  region
  laterality
  parent_id
  lod
  render_policy
  control_policy
  metadata_json

anatomy_edges
  id primary key
  from_node_id
  edge_type
  to_node_id
  metadata_json

anatomy_sources
  id primary key
  citation
  url
  source_type
  version
  license

anatomy_node_sources
  node_id
  source_id
  evidence_note
  confidence

node_capabilities
  node_id
  capability
  min_value
  max_value
  units
  renderer_adapter
  metadata_json

semantic_actions
  id
  name
  description
  embedding
  metadata_json

semantic_action_nodes
  action_id
  node_id
  role              primary, secondary, passive, diagnostic
  activation_hint
  weight
```

This can run in Postgres first. If we need graph traversal beyond SQL comfort, add a graph projection later. If we need semantic search, add pgvector or a separate vector DB.

## RAG and LLM Control Flow

1. User or agent says: "wave with the right hand."
2. Planner embeds/query-expands the action.
3. Retrieval selects relevant action templates and anatomy nodes.
4. Capability resolver intersects anatomy nodes with renderer-supported controls.
5. LLM receives:
   - user goal
   - compact anatomy bundle
   - available renderer/control capabilities
   - previous body state
   - constraints and output schema
6. LLM returns bounded control intent.
7. Validator checks:
   - every node id exists
   - every capability is allowed
   - values are in range
   - biomechanics are plausible enough for current phase
8. Renderer adapter applies:
   - visible body motion
   - internal anatomy overlay if enabled
   - skin/hair/clothing deformation
   - diagnostic report

## Renderer Projection

Every anatomy node should be renderable somehow, but not every node needs a unique mesh at every frame.

Render classes:

```text
mesh_exact           bones, organs, major muscles
mesh_proxy           small muscles, glands, ligaments at low LOD
curve                vessels, nerves, lymphatics
surface_layer        skin, fascia, membranes
volume               brain regions, soft tissue masses
instanced_population hair follicles, sweat glands, capillary beds
shader_state         blush, sweat, pallor, pulse, inflammation-like color
label_only           diagnostic or non-visible nodes
```

Layer modes:

```text
skin                 normal avatar surface
muscle               skin hidden or translucent, muscles visible
skeletal             bones/joints/ligaments visible
vascular             arteries/veins/capillary beds visible
nervous              brain/spinal cord/nerves visible
lymphatic            lymph vessels/nodes visible
integument_micro     skin layers, follicles, glands, receptors
full_anatomy         composited educational anatomy view
```

## TDD Strategy

No renderer work until graph tests pass for the targeted region.

Test categories:

1. Schema tests
   - Every node has id, type, system, region, parent, source.
   - Every edge references valid nodes.
   - Every canonical node has at least one source.

2. Taxonomy tests
   - Body has required top-level systems.
   - Head has skull, brain, sensory organs, skin, vessels, nerves.
   - Knee has bones, joints, ligaments, menisci, muscles, vessels, nerves, skin.
   - Toe has bones, joints, skin layers, nail unit, vessels, nerves.

3. Relationship tests
   - Muscles have origin/insertion/action where expected.
   - Vessels have directional flow/drainage edges.
   - Nerves innervate real target regions.
   - Skin regions contain epidermis, dermis, hypodermis where appropriate.

4. Retrieval tests
   - "wave" retrieves shoulder/elbow/wrist/hand, not random torso nodes.
   - "sit" retrieves hips/knees/ankles/spine.
   - "blink" retrieves eyelids, facial nerve pathway, orbicularis oculi, eye surface.
   - "sweat on forehead" retrieves forehead skin and sweat gland population.

5. Control validation tests
   - LLM cannot target unknown nodes.
   - LLM cannot rotate an artery like a bone.
   - LLM cannot claim wardrobe mesh swap if no mesh capability exists.
   - Unsupported requests produce degraded diagnostics.

6. Renderer tests
   - Every exposed renderer node maps to an anatomy node.
   - Layer toggles reveal expected structures.
   - Control intent changes visible frame state.

## First Milestones

### Milestone 1: Anatomy Graph Seed

Create sourced, tested seed graph for:

- Body root and top-level systems.
- Head region.
- Right upper limb enough for wave.
- Right knee enough for sit/run.
- Right great toe enough to prove micro-region modeling.

### Milestone 2: RAG Query Layer

Build semantic action retrieval:

- wave
- sit
- run
- blink
- smile
- sweat
- look left
- make fist

### Milestone 3: Renderer Prototype

Render graph layers in browser:

- Skin mesh/proxy.
- Skeleton overlay for seed regions.
- Brain/head internal overlay.
- Vessel/nerve curves for seed regions.
- Instanced hair/sweat/fingerprint-like skin structures at selected LOD.

### Milestone 4: LLM Control Contract

LLM returns:

```json
{
  "schema": "god.body_control.v1",
  "action": "wave",
  "nodes": [
    {
      "id": "body.upper_limb.right.shoulder.glenohumeral_joint",
      "capability": "rotate_joint",
      "value": [0.2, 0.0, 0.4],
      "weight": 0.8
    }
  ],
  "diagnostic_expectations": [
    "right shoulder participates",
    "right wrist participates",
    "skin deforms passively"
  ]
}
```

The schema above is illustrative only. The real schema must be tested before use.

## Open Questions

- Do we seed from FMA/TA data directly, or hand-author a small sourced seed and build importers later?
- Should graph traversal live in Postgres first, or should we introduce a graph DB only after SQL becomes painful?
- How much anatomy should be visible by default versus available through layer toggles?
- Should "brain as node" be only anatomical, or also the avatar's cognitive/control state anchor?
- How do we represent anatomical variation without breaking canonical tests?

## Immediate Next Step

Do not code the renderer first.

Start with tests and seed data:

1. Define `AnatomyNode`, `AnatomyEdge`, and source schema.
2. Write tests for body top-level systems, head, knee, and great toe.
3. Add sourced seed fixtures until tests pass.
4. Only then expose a graph query endpoint and renderer registry.
