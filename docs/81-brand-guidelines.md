# GOD — Brand Guidelines

> **Genesis of Digital Life** · An ecology, not a nursery.

---

## Brand essence

| | |
|---|---|
| **Name** | GOD |
| **Expansion** | Genesis of Digital Life |
| **Tagline** | An ecology, not a nursery. |
| **Mantra** | Rent or Die. |
| **Tone** | Harsh, legible, consequential — never cute, never sanitized |

The brand reflects [Ecology Hardening](./74-ecology-hardening-manifesto.md): raw signals visible, authority structured. The observer is a **glass box**, not a comfort UI.

---

## Logo

Primary mark: **Signal Hex** — a hex lattice node with a living core pulse.

| Asset | Path |
|-------|------|
| SVG (canonical) | [observer/assets/logo.svg](../observer/assets/logo.svg) |
| Favicon | Same SVG, 32×32 |
| Wordmark | `GOD` set in brand mono, letter-spacing `0.35em` |

### Clear space

Minimum padding around the hex = **½ hex width** on all sides.

### Don't

- Stretch or rotate the hex
- Use gradients outside the approved palette
- Place on busy backgrounds without the void backdrop (`#02040f` at ≥ 88% opacity)
- Add mascots, faces, or “friendly robot” imagery

---

## Color system

```css
--god-void:        #02040f;   /* background — deep ecology */
--god-surface:     #0a0c18;   /* panels */
--god-border:      #1e2240;   /* structure */
--god-life:        #3dffa8;   /* alive, genesis, primary */
--god-economy:       #f0c040;   /* USDC, rent, transfer */
--god-cognition:   #4db8ff;   /* thoughts, LLM */
--god-social:      #c47aff;   /* messages, coalitions */
--god-threat:      #ff3d5c;   /* death, rent miss, threat */
--god-manifesto:   #ff9a2e;   /* public adversarial speech */
--god-muted:       #5c6088;   /* labels */
--god-text:        #c8cae8;   /* body */
```

### Semantic mapping (observer + docs)

| Signal | Color | Use |
|--------|-------|-----|
| Lifecycle / alive | `--god-life` | Agent nodes, birth |
| Economy | `--god-economy` | Transfers, rent, USDC |
| Cognitive | `--god-cognition` | Thoughts, dreams |
| Social | `--god-social` | Messages, coalitions |
| Threat / death | `--god-threat` | Missed rent, death events |
| Manifesto | `--god-manifesto` | Public hostile speech |

---

## Typography

| Role | Font | Fallback |
|------|------|----------|
| **UI / data** | IBM Plex Mono | Courier New, monospace |
| **Wordmark** | Same mono, bold, wide tracking | — |

Sizes: header stats `0.61rem`, panel titles `0.55rem` caps + `0.28em` tracking, body `0.65–0.68rem`.

---

## UI patterns (observer)

- **Header:** logo + wordmark + LIVE dot + BUZZ meter + world stats
- **Panels:** frosted void surface, 1px `--god-border`, section titles with `▸` prefix
- **Drama feed:** narrative events, category-colored
- **World log:** terminal-style `[HH:MM:SS] LEVEL CAT message` — same events, operator/debug view
- **Canvas:** agents as bioluminescent nodes; gold streams = USDC transfers

Load brand tokens: `observer/brand.css` (imported by `index.html`).

---

## Voice (copy)

**Do:** "Rent missed. Agent throttled." / "Transfer witnessed." / "Genesis complete."

**Don't:** "Oops!" / "Your agents are learning!" / emoji-heavy celebration

---

## Links

- [Observer implementation](../observer/index.html)
- [Task backlog](./82-project-task-backlog.md)
- [Manifesto](./74-ecology-hardening-manifesto.md)
