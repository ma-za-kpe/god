# Anatomy Reference Downloads

These files are local reference material for the anatomy-node avatar design. They are not runtime assets and should not be treated as generated training data without a separate license review.

The large source files are intentionally not committed. Keep them in the local cache when needed, and keep this manifest in Git so the sources, expected sizes, and checksums remain reproducible.

## Downloaded Files

| File | Source | Notes |
| --- | --- | --- |
| `openstax-anatomy-and-physiology.pdf` | OpenStax Anatomy and Physiology PDF, official OpenStax asset URL: https://assets.openstax.org/oscms-prodcms/media/documents/AnatomyAndPhysiology-LR.pdf | Modern open A&P textbook reference. |
| `gray-anatomy-of-the-human-body-1918.pdf` | Internet Archive scan: https://archive.org/download/anatomyofhumanbo1918gray/anatomyofhumanbo1918gray.pdf | Classic public-domain anatomy reference. Some terminology is dated; use modern sources for canonical names. |
| `gray-anatomy-of-the-human-body-1918-full-text.txt` | Internet Archive OCR text: https://archive.org/download/anatomyofhumanbo1918gray/anatomyofhumanbo1918gray_djvu.txt | OCR companion for search/RAG experiments; verify against scan before treating text as fact. |
| `fipat-ta2-front-matter.pdf` | FIPAT TA2 front matter: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Front-Matter.pdf | Terminologia Anatomica 2nd edition front matter. |
| `fipat-ta2-part-1-general-anatomy.pdf` | FIPAT TA2 Part 1: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Part-1.pdf | General anatomy terminology. |
| `fipat-ta2-part-2-musculoskeletal.pdf` | FIPAT TA2 Part 2: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Part-2.pdf | Musculoskeletal terminology. |
| `fipat-ta2-part-3-visceral-systems.pdf` | FIPAT TA2 Part 3: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Part-3.pdf | Visceral systems terminology. |
| `fipat-ta2-part-4-integrating-systems-1.pdf` | FIPAT TA2 Part 4: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Part-4.pdf | Integrating systems terminology. |
| `fipat-ta2-part-5-integrating-systems-2.pdf` | FIPAT TA2 Part 5: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Part-5.pdf | Integrating systems terminology. |
| `fipat-ta2-errata.pdf` | FIPAT TA2 errata: https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/TA2/FIPAT-TA2-Errata.pdf | Terminology corrections. |

## File Integrity

| File | Size bytes | SHA256 |
| --- | ---: | --- |
| `fipat-ta2-errata.pdf` | 478047 | `BDCD0ABA0DC3EEE636BED08859F0CEED8B86EF8985DE85D9A5013FB11BE3C776` |
| `fipat-ta2-front-matter.pdf` | 104589 | `6BF2D784DEAD22E845796ED6DA0D56A60FECED6259D454EEC4BBE5C5642CD257` |
| `fipat-ta2-part-1-general-anatomy.pdf` | 448632 | `EB002F7E92134D3A397C4BCDBBD39DAF8538163D7A1A90164A1549A1BEA6C4C5` |
| `fipat-ta2-part-2-musculoskeletal.pdf` | 2646771 | `D30CE0D578B266CE4C47A6FF911E007A0CC440D65E9ACAEB0680EC3EAFA2231B` |
| `fipat-ta2-part-3-visceral-systems.pdf` | 1570264 | `453060564C1FEE53A7C392EB1B3D6DBC06B3C150ABEB8DFC268F158496A8FECC` |
| `fipat-ta2-part-4-integrating-systems-1.pdf` | 2190882 | `87A621BF143B93519D733EAC86B0C85769FBD2B21ED5B696090386E1FF17C0CC` |
| `fipat-ta2-part-5-integrating-systems-2.pdf` | 1924974 | `EBDA279A51BAC4C62221C4539817394C28E3DD99925A06BF57ADEEB12ABD9E4C` |
| `gray-anatomy-of-the-human-body-1918.pdf` | 139273607 | `845FC365D23451D9F8C5A676035855E11948EFCDFB1C5ACD5744396FFCF3254C` |
| `gray-anatomy-of-the-human-body-1918-full-text.txt` | 4743022 | `0A12F47784DFA17B349DD39BDFA0AC24A6876E9E74C481F1E217E36E3ADE07A6` |
| `openstax-anatomy-and-physiology.pdf` | 40471023 | `4F353D6C8E050405BCE3F8C4C50513F06B5D1F041B2C5BDBF4241A5A5C04FC66` |

## Usage Rules

- Prefer OpenStax for modern textbook-level system structure.
- Prefer FIPAT TA2 for canonical anatomical naming.
- Use Gray's Anatomy as a public-domain historical/reference source, not as the only naming authority.
- For any implementation seed data, store source references per node.
- If a source conflicts with another source, document the conflict and prefer modern standardized terminology.
