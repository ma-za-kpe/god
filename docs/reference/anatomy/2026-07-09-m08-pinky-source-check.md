# M08 Right-Hand Digit Source Check

Date: 2026-07-09.

## Scope

M08 replaces the broad microstructure pass with one strict anatomical slice:
the full right-hand digit set as graph-backed chains inside the right hand and
right upper limb. The little finger remains the highlighted audit ray because it
exposed the original placement problem, but the source-backed graph now covers
thumb through little finger.

## Checked References

| Claim | Source |
| --- | --- |
| The upper limb includes the hand region; the hand contains eight carpals, five metacarpals, and fourteen phalanges. | OpenStax Anatomy and Physiology 2e, 8.2 Bones of the Upper Limb: https://openstax.org/books/anatomy-and-physiology-2e/pages/8-2-bones-of-the-upper-limb |
| Digits 2 through 5 have proximal, middle, and distal phalanges; the thumb/pollex has only proximal and distal phalanges. | OpenStax Anatomy and Physiology 2e, 8.2 Bones of the Upper Limb: https://openstax.org/books/anatomy-and-physiology-2e/pages/8-2-bones-of-the-upper-limb |
| FIPAT TA2 remains the naming baseline for canonical anatomical names and aliases such as pollex/digit numbering and little finger terminology. | FIPAT Terminologia Anatomica, 2nd edition: https://libraries.dal.ca/Fipat/ta2.html |
| Metacarpophalangeal joints support flexion, extension, limited abduction/adduction, and circumduction. | Gray, Anatomy of the Human Body, 20th ed., 1918, Syndesmology, metacarpophalangeal articulations: local OCR `gray-anatomy-of-the-human-body-1918-full-text.txt`, public scan https://archive.org/details/anatomyofhumanbo1918gray |
| Interphalangeal joints are hinge joints; their permitted movements are flexion and extension. | Gray, Anatomy of the Human Body, 20th ed., 1918, articulations of the digits: local OCR `gray-anatomy-of-the-human-body-1918-full-text.txt`, public scan https://archive.org/details/anatomyofhumanbo1918gray |
| The abductor and flexor digiti quinti brevis abduct and help flex the little finger; the opponens digiti quinti draws the fifth metacarpal forward to deepen the hollow of the palm. | Gray, Anatomy of the Human Body, 20th ed., 1918, medial volar muscles of the hand: local OCR `gray-anatomy-of-the-human-body-1918-full-text.txt`, public scan https://archive.org/details/anatomyofhumanbo1918gray |

## Design Decision

The five metacarpals are not counted as phalanges. They are included as the
upstream palm-side support bones because the metacarpophalangeal joints connect
them to the proximal phalanges. The hand phalanx count remains fourteen: two in
the thumb and three in each of digits 2 through 5.

M08 therefore models:

- `region:right_upper_limb`
- `region:right_hand`
- `digit:right_pollex`
- `digit:right_index_finger`
- `digit:right_middle_finger`
- `digit:right_ring_finger`
- `digit:right_little_finger`
- `bone:right_first_metacarpal` through `bone:right_fifth_metacarpal`
- `joint:right_first_carpometacarpal` through `joint:right_fifth_carpometacarpal`
- `joint:right_first_metacarpophalangeal` through `joint:right_fifth_metacarpophalangeal`
- `joint:right_pollex_interphalangeal`
- Proximal/middle/distal interphalangeal joint pairs for index, middle, ring,
  and little fingers.
- Two thumb phalanges and three phalanges for each non-thumb finger.
- `bone:right_fifth_metacarpal`
- `bone:right_little_finger_proximal_phalanx`
- `bone:right_little_finger_middle_phalanx`
- `bone:right_little_finger_distal_phalanx`
- `joint:right_fifth_metacarpophalangeal`
- `joint:right_little_finger_proximal_interphalangeal`
- `joint:right_little_finger_distal_interphalangeal`

## Functional Surface

For the LLM control registry, the right-hand digits expose:

- `flexion_extension` at MCP/IP/PIP/DIP joints.
- `abduction_adduction` at MCP joints, with the anatomical constraint that
  abduction/adduction is limited and not available while the finger is flexed.
- `circumduction_proxy` at MCP joints.
- `finger_curl` as a bundled semantic action over the non-thumb finger chains.
- `opposition` for the thumb/pollex.
- `palm_cupping` through the fourth and fifth metacarpal/hypothenar side, not
  by moving the distal phalanges alone.

The browser skeleton must render this as five hand rays: carpal context at the
wrist, metacarpal context in the palm, and phalanges continuing distally from
each metacarpal head. The little finger can be highlighted, but the other four
digits must still be visible and source-backed.

## Validation Expectation

Tests must prove the parent path, fourteen right-hand phalanx nodes, CMC/MCP/IP
joint connectivity for all five digits, and rejection of invented finger nodes.
