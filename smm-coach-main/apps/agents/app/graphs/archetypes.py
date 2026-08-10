"""Stage 1 — the 12 Jung/Pearson marketing archetypes as a DETERMINISTIC
taxonomy mapped from OCEAN, replacing the scriptwriter/psych-extractor's ad-hoc
LLM guess. Each archetype has a characteristic Big-Five profile; we pick the
nearest match (+ runner-up) to the user's scores, so the brand voice is grounded
in the actual personality signal and consistent across every generated script.

Pure (no I/O) → unit-testable. `match_archetype(ocean)` is the entry point.
"""
from __future__ import annotations

# Each archetype: characteristic OCEAN target (0-100) + an Uzbek label + voice
# guidance the scriptwriter/caption layers can lean on. Targets are research-
# informed approximations — exact values matter less than relative ordering, since
# we pick by nearest match.
_ARCHETYPES: list[dict] = [
    {"key": "Creator", "label": "Ijodkor", "ocean": {"O": 88, "C": 72, "E": 48, "A": 50, "N": 52},
     "tone": "original, ilhomlantiruvchi, estetik", "anti": ["zerikarli shablon", "klishe"]},
    {"key": "Sage", "label": "Bilimdon", "ocean": {"O": 85, "C": 70, "E": 38, "A": 55, "N": 40},
     "tone": "tahliliy, ishonchli, dalilga asoslangan", "anti": ["yuzaki", "asossiz da'vo"]},
    {"key": "Explorer", "label": "Kashshof", "ocean": {"O": 82, "C": 45, "E": 68, "A": 42, "N": 45},
     "tone": "erkin, sarguzashtli, mustaqil", "anti": ["qotib qolgan qoidalar", "monotonlik"]},
    {"key": "Innocent", "label": "Sof", "ocean": {"O": 55, "C": 58, "E": 55, "A": 78, "N": 25},
     "tone": "soda, optimistik, samimiy", "anti": ["sinizm", "murakkablashtirish"]},
    {"key": "Hero", "label": "Qahramon", "ocean": {"O": 55, "C": 80, "E": 72, "A": 48, "N": 28},
     "tone": "jasur, natijaga yo'naltirilgan, rag'batlantiruvchi", "anti": ["nolish", "passivlik"]},
    {"key": "Rebel", "label": "Isyonkor", "ocean": {"O": 78, "C": 38, "E": 62, "A": 28, "N": 55},
     "tone": "dadil, qoidabuzar, provokatsion", "anti": ["konformizm", "yumshoq til"]},
    {"key": "Magician", "label": "Sehrgar", "ocean": {"O": 86, "C": 68, "E": 64, "A": 55, "N": 45},
     "tone": "transformatsion, vizyoner, ta'sirli", "anti": ["oddiy faktlar", "quruq ko'rsatma"]},
    {"key": "Lover", "label": "Oshiq", "ocean": {"O": 68, "C": 50, "E": 74, "A": 76, "N": 50},
     "tone": "hissiy, yaqin, estetik-sezgir", "anti": ["sovuq rasmiyat", "befarqlik"]},
    {"key": "Jester", "label": "Hazilkash", "ocean": {"O": 72, "C": 38, "E": 80, "A": 60, "N": 38},
     "tone": "kulgili, yengil, o'ynoqi", "anti": ["jiddiy ma'ruza", "zerikarlilik"]},
    {"key": "Everyman", "label": "Oddiy inson", "ocean": {"O": 50, "C": 55, "E": 60, "A": 75, "N": 40},
     "tone": "samimiy, do'stona, tushunarli", "anti": ["takabburlik", "elitizm"]},
    {"key": "Caregiver", "label": "G'amxo'r", "ocean": {"O": 52, "C": 70, "E": 55, "A": 86, "N": 35},
     "tone": "qo'llab-quvvatlovchi, mehribon, foydali", "anti": ["qattiqqo'llik", "e'tiborsizlik"]},
    {"key": "Ruler", "label": "Yetakchi", "ocean": {"O": 38, "C": 85, "E": 64, "A": 45, "N": 38},
     "tone": "ishonchli, tartibli, nufuzli", "anti": ["tarqoqlik", "ikkilanish"]},
]

_DIMS = ("O", "C", "E", "A", "N")


def _distance(a: dict, target: dict) -> float:
    return sum((float(a.get(d, 50)) - float(target[d])) ** 2 for d in _DIMS) ** 0.5


def match_archetype(ocean: dict | None) -> dict:
    """Nearest + runner-up archetype to the OCEAN scores. Returns
    {primary, primaryLabel, secondary, secondaryLabel, tone, antiVoice}. With no
    usable OCEAN, defaults to Everyman (the safe, broadly-likable default)."""
    if not isinstance(ocean, dict) or not any(k in ocean for k in _DIMS):
        a = _ARCHETYPES[9]  # Everyman
        return {
            "primary": a["key"], "primaryLabel": a["label"],
            "secondary": None, "secondaryLabel": None,
            "tone": a["tone"], "antiVoice": list(a["anti"]),
        }
    ranked = sorted(_ARCHETYPES, key=lambda a: _distance(ocean, a["ocean"]))
    primary, secondary = ranked[0], ranked[1]
    return {
        "primary": primary["key"], "primaryLabel": primary["label"],
        "secondary": secondary["key"], "secondaryLabel": secondary["label"],
        "tone": primary["tone"], "antiVoice": list(primary["anti"]),
    }
