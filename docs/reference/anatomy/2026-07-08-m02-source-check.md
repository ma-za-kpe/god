# M02 Source Check: Head, Knee, Hand, And Toe Seed Graph

Date: 2026-07-08

Milestone: M02 canonical seed graph expansion for body, systems, head, knee,
hand, and toe.

## Sources Checked

| Claim Used By M02 | Source |
| --- | --- |
| The skull consists of brain-case and facial bones; the brain case has eight bones and facial bones include paired/unpaired bones such as maxilla, zygomatic, nasal, mandible, and vomer. | OpenStax Anatomy and Physiology 2e, 7.2 The Skull: https://openstax.org/books/anatomy-and-physiology-2e/pages/7-2-the-skull |
| The upper limb has arm, forearm, and hand regions; the hand has eight carpals, five metacarpals, and fourteen phalanges; the thumb/pollex has two phalanges while digits 2-5 have three each. | OpenStax Anatomy and Physiology 2e, 8.2 Bones of the Upper Limb: https://openstax.org/books/anatomy-and-physiology-2e/pages/8-2-bones-of-the-upper-limb |
| The lower limb has thigh, leg, and foot regions; each lower limb has femur, patella, tibia, fibula, tarsals, metatarsals, and phalanges; toes have fourteen phalanges and the hallux has two. | OpenStax Anatomy and Physiology 2e, 8.4 Bones of the Lower Limb: https://openstax.org/books/anatomy-and-physiology-2e/pages/8-4-bones-of-the-lower-limb |
| The patella articulates with the distal femur and does not articulate with the tibia; tibial condyles articulate with femoral condyles to form the knee joint. | OpenStax Anatomy and Physiology 2e, 8.4 Bones of the Lower Limb: https://openstax.org/books/anatomy-and-physiology-2e/pages/8-4-bones-of-the-lower-limb |
| The knee articulates femur, tibia, and patella; the fibula is not part of the knee joint; major stabilizing ligaments include ACL, PCL, MCL, and LCL. | StatPearls/NCBI Bookshelf, Anatomy, Bony Pelvis and Lower Limb, Knee: https://www.ncbi.nlm.nih.gov/books/NBK500017/ |
| FIPAT TA2 remains the naming baseline for canonical anatomy labels and aliases. | FIPAT Terminologia Anatomica, 2nd edition: https://libraries.dal.ca/Fipat/ta2.html |

## M02 Design Consequences

- Seed graph expansion must distinguish regions, bones, joints, ligaments,
  skin, and population templates.
- Knee modeling must not claim the fibula is part of the knee joint. It may be
  adjacent/nearby in later models, but not a knee articular bone.
- Hand and toe seed data should include aggregates before exhaustive named
  per-digit expansion. The great toe/hallux and thumb/pollex are special cases
  with two phalanges.
- The browser morph proof must visibly change from M01: more nodes, highlighted
  hand/knee/toe regions, and milestone label M02.
