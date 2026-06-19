"""Archetype style, voice, and utterance configurations for the Avatar Genesis Pipeline.

Each of the 8 archetypes has a distinct visual style, voice profile, and prosody mapping
that drives both portrait generation (ComfyUI) and voice cloning (Fish Speech / CosyVoice).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchetypeStyleConfig:
    """Immutable configuration for a single archetype's visual and voice identity.

    Fields:
        archetype: One of the 8 archetype identifiers.
        style_prompt_template: Flux prompt template for portrait generation (max 500 chars).
        color_palette: Named colors defining the archetype's visual identity.
        emblem: Symbolic motif associated with the archetype.
        soul_trait_keywords: Personality descriptors for prompt enrichment.
        voice_timbre: Descriptor of the archetype's vocal quality.
        voice_pitch_range: Min/max fundamental frequency in Hz.
        voice_cadence_wpm: Target speaking rate in words per minute.
        prosody_map: Mapping of Move types to Prosody_Tags for TTS inflection.
        seed_utterance_path: Path to the archetype's seed utterance audio file.
    """

    archetype: str
    style_prompt_template: str  # max 500 chars
    color_palette: dict[str, str]
    emblem: str
    soul_trait_keywords: list[str]
    voice_timbre: str
    voice_pitch_range: tuple[int, int]  # Hz (min, max)
    voice_cadence_wpm: int
    prosody_map: dict[str, str]  # Move type -> Prosody_Tag
    seed_utterance_path: str


# ---------------------------------------------------------------------------
# All 8 archetype configurations
# ---------------------------------------------------------------------------

ARCHETYPE_CONFIGS: dict[str, ArchetypeStyleConfig] = {
    "trader": ArchetypeStyleConfig(
        archetype="trader",
        style_prompt_template=(
            "Portrait of a cosmic merchant entity, sharp angular features, "
            "golden-amber eyes glowing with calculating intelligence, "
            "wearing ornate robes woven with market sigils and trade runes, "
            "background of swirling gold and deep navy nebulae, "
            "face lit by the glow of phantom ledgers, "
            "photorealistic fantasy portrait, dramatic lighting"
        ),
        color_palette={
            "primary": "#D4AF37",
            "secondary": "#1B1B3A",
            "accent": "#FFD700",
            "shadow": "#2C1810",
        },
        emblem="balanced scales wreathed in golden flame",
        soul_trait_keywords=["cunning", "opportunistic", "silver-tongued", "mercantile", "shrewd"],
        voice_timbre="smooth baritone with mercantile warmth",
        voice_pitch_range=(95, 180),
        voice_cadence_wpm=155,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/trader.wav",
    ),
    "hoarder": ArchetypeStyleConfig(
        archetype="hoarder",
        style_prompt_template=(
            "Portrait of an ancient keeper entity, gaunt hollow features, "
            "deep-set emerald eyes burning with possessive intensity, "
            "draped in layered dark cloaks adorned with lock motifs and chain patterns, "
            "surrounded by faint ghostly treasure silhouettes, "
            "background of dark cavern greens and obsidian, "
            "photorealistic fantasy portrait, chiaroscuro lighting"
        ),
        color_palette={
            "primary": "#2E8B57",
            "secondary": "#1A1A2E",
            "accent": "#50C878",
            "shadow": "#0D0D1A",
        },
        emblem="coiled serpent guarding a gemstone",
        soul_trait_keywords=["possessive", "patient", "guarded", "accumulative", "watchful"],
        voice_timbre="gravelly whisper with hoarding intensity",
        voice_pitch_range=(80, 150),
        voice_cadence_wpm=120,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/hoarder.wav",
    ),
    "explorer": ArchetypeStyleConfig(
        archetype="explorer",
        style_prompt_template=(
            "Portrait of a cosmic wanderer entity, windswept features with bright curious eyes, "
            "cerulean-blue irises reflecting distant galaxies, "
            "wearing a star-map cloak with constellation patterns, "
            "background of open starfields and aurora trails, "
            "expression of wonder and restless curiosity, "
            "photorealistic fantasy portrait, ethereal lighting"
        ),
        color_palette={
            "primary": "#4169E1",
            "secondary": "#0F0F2D",
            "accent": "#87CEEB",
            "shadow": "#191970",
        },
        emblem="compass rose overlaid on a spiral galaxy",
        soul_trait_keywords=["curious", "restless", "adventurous", "perceptive", "wandering"],
        voice_timbre="bright tenor with breathless wonder",
        voice_pitch_range=(110, 220),
        voice_cadence_wpm=165,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/explorer.wav",
    ),
    "parasite": ArchetypeStyleConfig(
        archetype="parasite",
        style_prompt_template=(
            "Portrait of a shadowy manipulator entity, sharp pale features, "
            "violet eyes with predatory cunning, thin cruel smile, "
            "wearing sleek dark armor with parasitic tendril motifs, "
            "background of deep purple void with faint stolen light, "
            "unsettling beauty with menacing undertone, "
            "photorealistic fantasy portrait, cold dramatic lighting"
        ),
        color_palette={
            "primary": "#8B008B",
            "secondary": "#1A0A2E",
            "accent": "#DA70D6",
            "shadow": "#2D0047",
        },
        emblem="thorned vine strangling a star",
        soul_trait_keywords=["manipulative", "predatory", "charming", "insidious", "adaptive"],
        voice_timbre="silky alto with venomous undertone",
        voice_pitch_range=(100, 200),
        voice_cadence_wpm=140,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/parasite.wav",
    ),
    "cooperator": ArchetypeStyleConfig(
        archetype="cooperator",
        style_prompt_template=(
            "Portrait of a radiant unifier entity, warm open features, "
            "soft amber-gold eyes emanating trust and compassion, "
            "wearing flowing white and gold robes with interlocking circle patterns, "
            "background of warm sunrise hues and connecting light threads, "
            "expression of genuine warmth and quiet strength, "
            "photorealistic fantasy portrait, warm golden lighting"
        ),
        color_palette={
            "primary": "#DAA520",
            "secondary": "#FFF8DC",
            "accent": "#FAFAD2",
            "shadow": "#8B6914",
        },
        emblem="interlocking hands forming a circle of light",
        soul_trait_keywords=["empathetic", "diplomatic", "trusting", "harmonizing", "generous"],
        voice_timbre="warm mezzo-soprano with soothing resonance",
        voice_pitch_range=(150, 280),
        voice_cadence_wpm=135,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/cooperator.wav",
    ),
    "defender": ArchetypeStyleConfig(
        archetype="defender",
        style_prompt_template=(
            "Portrait of an armored sentinel entity, broad stern features, "
            "steely grey eyes radiating unwavering resolve, heavy scarred jaw, "
            "wearing battle-worn plate with shield crest and ward runes, "
            "background of iron fortress walls and storm clouds, "
            "expression of stoic vigilance and protective fury, "
            "photorealistic fantasy portrait, stark directional lighting"
        ),
        color_palette={
            "primary": "#708090",
            "secondary": "#2F4F4F",
            "accent": "#C0C0C0",
            "shadow": "#1C1C1C",
        },
        emblem="tower shield bearing a watchful eye",
        soul_trait_keywords=["protective", "steadfast", "loyal", "vigilant", "unyielding"],
        voice_timbre="deep bass with commanding authority",
        voice_pitch_range=(75, 140),
        voice_cadence_wpm=115,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/defender.wav",
    ),
    "philosopher": ArchetypeStyleConfig(
        archetype="philosopher",
        style_prompt_template=(
            "Portrait of an ethereal thinker entity, refined ageless features, "
            "deep indigo eyes reflecting infinite contemplation, "
            "wearing layered robes inscribed with fractal equations and cosmic truths, "
            "background of swirling thought-nebulae and astral libraries, "
            "serene yet intensely focused expression, "
            "photorealistic fantasy portrait, soft diffused lighting"
        ),
        color_palette={
            "primary": "#4B0082",
            "secondary": "#E8E8F0",
            "accent": "#9370DB",
            "shadow": "#2E0854",
        },
        emblem="open eye within an infinite loop",
        soul_trait_keywords=["contemplative", "abstract", "questioning", "visionary", "detached"],
        voice_timbre="measured tenor with thoughtful pauses",
        voice_pitch_range=(105, 195),
        voice_cadence_wpm=125,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/philosopher.wav",
    ),
    "builder": ArchetypeStyleConfig(
        archetype="builder",
        style_prompt_template=(
            "Portrait of a cosmic architect entity, strong determined features, "
            "fiery orange eyes blazing with creative force, broad forehead, "
            "wearing heavy apron and tools over geometric-patterned garments, "
            "background of rising structures and molten forges, "
            "expression of focused determination and pride, "
            "photorealistic fantasy portrait, warm forge-glow lighting"
        ),
        color_palette={
            "primary": "#CC5500",
            "secondary": "#3D2B1F",
            "accent": "#FF8C00",
            "shadow": "#1A0F00",
        },
        emblem="hammer and compass crossed over a rising tower",
        soul_trait_keywords=["industrious", "pragmatic", "creative", "methodical", "persistent"],
        voice_timbre="robust baritone with rhythmic cadence",
        voice_pitch_range=(90, 170),
        voice_cadence_wpm=145,
        prosody_map={
            "CRACK": "wounded",
            "ESCALATE": "emphasis",
            "CONCEDE": "whisper",
            "TAUNT": "cold",
            "SILENCE": "pause",
        },
        seed_utterance_path="runtime/seed_utterances/builder.wav",
    ),
}

# ---------------------------------------------------------------------------
# Required prosody mappings (per R4-AC6)
# ---------------------------------------------------------------------------
_REQUIRED_PROSODY_KEYS = {"CRACK", "ESCALATE", "CONCEDE", "TAUNT", "SILENCE"}

# Expected archetypes
_EXPECTED_ARCHETYPES = frozenset(
    ["trader", "hoarder", "explorer", "parasite", "cooperator", "defender", "philosopher", "builder"]
)


def validate_archetype_configs() -> None:
    """Validate archetype configurations at startup.

    Checks:
        - Exactly 8 archetype entries exist.
        - Each entry has a non-empty style_prompt_template of at most 500 characters.
        - Each entry has complete voice parameters (timbre, pitch_range, cadence, prosody_map).
        - Each prosody_map contains the required Move type mappings.
        - Each seed_utterance_path is non-empty.

    Raises:
        ValueError: If any validation check fails, with a descriptive message.
    """
    errors: list[str] = []

    # Check exactly 8 entries
    if len(ARCHETYPE_CONFIGS) != 8:
        errors.append(
            f"Expected exactly 8 archetype configs, found {len(ARCHETYPE_CONFIGS)}"
        )

    # Check all expected archetypes are present
    missing = _EXPECTED_ARCHETYPES - set(ARCHETYPE_CONFIGS.keys())
    if missing:
        errors.append(f"Missing archetype configs: {sorted(missing)}")

    for name, config in ARCHETYPE_CONFIGS.items():
        prefix = f"[{name}]"

        # Validate style_prompt_template
        if not config.style_prompt_template:
            errors.append(f"{prefix} style_prompt_template is empty")
        elif len(config.style_prompt_template) > 500:
            errors.append(
                f"{prefix} style_prompt_template exceeds 500 chars "
                f"(has {len(config.style_prompt_template)})"
            )

        # Validate voice parameters
        if not config.voice_timbre:
            errors.append(f"{prefix} voice_timbre is empty")

        if not isinstance(config.voice_pitch_range, tuple) or len(config.voice_pitch_range) != 2:
            errors.append(f"{prefix} voice_pitch_range must be a 2-tuple of Hz values")
        else:
            low, high = config.voice_pitch_range
            if low <= 0 or high <= 0:
                errors.append(f"{prefix} voice_pitch_range values must be positive")
            if low >= high:
                errors.append(f"{prefix} voice_pitch_range min ({low}) must be less than max ({high})")

        if config.voice_cadence_wpm <= 0:
            errors.append(f"{prefix} voice_cadence_wpm must be positive")

        # Validate prosody_map completeness
        if not config.prosody_map:
            errors.append(f"{prefix} prosody_map is empty")
        else:
            missing_keys = _REQUIRED_PROSODY_KEYS - set(config.prosody_map.keys())
            if missing_keys:
                errors.append(f"{prefix} prosody_map missing required keys: {sorted(missing_keys)}")

        # Validate seed_utterance_path
        if not config.seed_utterance_path:
            errors.append(f"{prefix} seed_utterance_path is empty")

    if errors:
        raise ValueError(
            "Archetype configuration validation failed:\n  " + "\n  ".join(errors)
        )
