"""Mapping of insurance company names to Merlin codes.

Used by _build_historial to convert the human-readable company name
(as provided by the user) into the code that Merlin expects.
"""

import re
from typing import Optional, Tuple

# Top companies (shown first in Merlin UI, separated by a divider)
_TOP_COMPANIES = [
    ("C0613", "REALE SEGUROS GENERALES, S.A."),
    ("C0109", "ALLIANZ, COMPAÑIA DE SEGUROS Y REASEGUROS, S.A."),
    ("C0517", "PLUS ULTRA SEGUROS GENERALES Y VIDA, S.A. DE SEGUROS Y REASEGUROS"),
    ("C0072", "GENERALI ESPAÑA, SOCIEDAD ANÓNIMA DE SEGUROS Y REASEGUROS"),
    ("C0723", "AXA SEGUROS GENERALES, S. A. DE SEGUROS Y REASEGUROS"),
    ("C0058", "MAPFRE ESPAÑA, COMPAÑIA DE SEGUROS Y REASEGUROS, S.A."),
    ("M0050", "PELAYO, MUTUA DE SEGUROS Y REASEGUROS A PRIMA FIJA"),
    ("E0189", "ZURICH INSURANCE PLC SUC.ESPAÑA"),
    ("L0639", "EUROINS INSURANCE JSC"),
    ("C0467", "LIBERTY SEGUROS, COMPAÑIA DE SEGUROS Y REASEGUROS, S.A."),
]

# Full list: (code, description)
_ALL_COMPANIES = _TOP_COMPANIES + [
    ("M0328", "A.M.A., AGRUPACIÓN MUTUAL ASEGURADORA, MUTUA DE SEGUROS A PRIMA FIJA"),
    ("C0808", "ABANCA GENERALES DE SEGUROS Y REASEGUROS, S.A."),
    ("C0805", "ADMIRAL EUROPE, COMPAÑÍA DE SEGUROS, S.A."),
    ("E0226", "AIG EUROPE S.A. SUCURSAL ESPAÑA"),
    ("C0682", "AMIC SEGUROS GENERALES, S.A. SOCIEDAD UNIPERSONAL"),
    ("C0715", "ASEFA S.A., SEGUROS Y REASEGUROS"),
    ("C0001", "ASEGURADORES AGRUPADOS, SOCIEDAD ANONIMA DE SEGUROS (ASEGRUP)"),
    ("C0723", "AXA SEGUROS GENERALES, S. A. DE SEGUROS Y REASEGUROS"),
    ("C0807", "BBVA ALLIANZ, SEGUROS Y REASEGUROS, S.A."),
    ("C0502", "BBVASEGUROS, S.A., DE SEGUROS Y REASEGUROS"),
    ("C0026", "BILBAO, COMPAÑIA ANONIMA DE SEGUROS Y REASEGUROS."),
    ("C0031", "CAJA DE SEGUROS REUNIDOS, COMPAÑÍA DE SEGUROS Y REASEGUROS, S.A."),
    ("E0155", "CHUBB EUROPEAN GROUP SE SUC.ESPAÑA"),
    ("C0247", "DIVINA PASTORA, SEGUROS GENERALES, S.A.U."),
    ("C0706", "FENIX DIRECTO, COMPAÑIA DE SEGUROS Y REASEGUROS, S.A."),
    ("M0134", "FIATC, MUTUA DE SEGUROS Y REASEGUROS"),
    ("E0118", "FIDELIDADE COMPANHIA DE SEGUROS S.A SUC.ESPAÑA"),
    ("C0708", "GACM SEGUROS GENERALES, COMPAÑÍA DE SEGUROS Y REASEGUROS, S.A."),
    ("C0089", "GES, SEGUROS Y REASEGUROS, S.A."),
    ("E0213", "HDI GLOBAL SE SUC.ESPAÑA"),
    ("C0804", "HELLO INSURANCE GROUP, COMPAÑÍA DE SEGUROS, S.A."),
    ("C0157", "HELVETIA COMPAÑIA SUIZA, SOCIEDAD ANONIMA DE SEGUROS Y REASEGUROS"),
    ("E0231", "HISCOX S.A SUC. ESPAÑA"),
    ("E0174", "LIBERTY MUTUAL INSURANCE EUROPE SE SUC.EN ESPAÑA"),
    ("C0188", "LA UNION ALCOYANA, S.A. DE SEGUROS Y REASEGUROS."),
    ("C0676", "MAPFRE FAMILIAR, COMPAÑIA DE SEGUROS Y REASEGUROS"),
    ("E0235", "MARKEL INSURANCE SE SUCURSAL EN ESPAÑA"),
    ("C0794", "MGS SEGUROS Y REASEGUROS S.A."),
    ("E0243", "MSIG INSURANCE EUROPE AG SUC.ESPAÑA"),
    ("M0107", "MUSSAP- MUTUA DE SEGUROS Y REASEGUROS A PRIMA FIJA"),
    ("M0140", "MUTUA LEVANTE, MUTUA DE SEGUROS"),
    ("M0083", "MUTUA MADRILEÑA AUTOMOVILISTA, SOCIEDAD DE SEGUROS A PRIMA FIJA"),
    ("M0084", "MUTUA MMT SEGUROS, SOCIEDAD MUTUA DE SEGUROS A PRIMA FIJA"),
    ("M0167", "MUTUA SEGORBINA DE SEGUROS A PRIMA FIJA"),
    ("M0216", "MUTUA TINERFEÑA, MUTUA DE SEGUROS Y REASEGUROS A PRIMA FIJA"),
    ("C0133", "OCASO, S.A., COMPAÑIA DE SEGUROS Y REASEGUROS."),
    ("C0139", "PATRIA HISPANA, S.A. DE SEGUROS Y REASEGUROS"),
    ("C0174", "SANTA LUCIA, S.A. COMPAÑIA DE SEGUROS Y REASEGUROS"),
    ("C0806", "SANTANDER MAPFRE SEGUROS Y REASEGUROS, S.A."),
    ("C0124", "SEGURCAIXA ADESLAS, SOCIEDAD ANONIMA DE SEGUROS Y REASEGUROS"),
    ("C0468", "SEGUROS CATALANA OCCIDENTE, SOCIEDAD ANONIMA DE SEGUROS Y REASEGUROS"),
    ("C0572", "SEGUROS LAGUN ARO, S.A."),
    ("M0191", "SOLISS MUTUA DE SEGUROS"),
    ("C0810", "TELEFONICA SEGUROS Y REASEGUROS COMPAÑÍA ASEGURADORA SAU"),
    ("M0363", "UMAS, UNION MUTUA ASISTENCIAL DE SEGUROS A PRIMA FIJA"),
    ("C0785", "VERTI ASEGURADORA, COMPAÑÍA DE SEGUROS Y REASEGUROS, S.A."),
    ("C0811", "WELCOME SEGUROS 2020, S.A."),
    ("E0134", "XL INSURANCE COMPANY SE, SUCURSAL EN ESPAÑA"),
    ("L0501", "ZURICH INSURANCE PLC."),
    ("E0252", "IPTIQ EMEA P&C S.A., SUCURSAL EN ESPAÑA"),
    ("E0130", "CARDIF ASSURANCES RISQUES DIVERS SUC.ESPAÑA"),
    ("E0196", "INTER PARTNER ASSISTANCE SA SUC.ESPAÑA"),
    ("E0229", "SI INSURANCE (EUROPE), SA SUC. ESPAÑA"),
    ("E0236", "TOKIO MARINE EUROPE S.A, SUC. ESPAÑA"),
    ("E0218", "W.R. BERKLEY EUROPE AG SUC. ESPAÑA"),
    ("E0230", "QBE EUROPE SA/NV SUCURSAL ESPAÑA"),
    ("L0645", "WAKAM"),
]

# Quick-lookup aliases: short name → code
_ALIASES = {
    "reale": "C0613",
    "allianz": "C0109",
    "plus ultra": "C0517",
    "generali": "C0072",
    "axa": "C0723",
    "mapfre": "C0058",
    "pelayo": "M0050",
    "zurich": "E0189",
    "euroins": "L0639",
    "liberty": "C0467",
    "mutua madrileña": "M0083",
    "mutua madrilena": "M0083",
    "catalana occidente": "C0468",
    "catalana": "C0468",
    "fenix directo": "C0706",
    "fénix directo": "C0706",
    "fenix": "C0706",
    "santa lucia": "C0174",
    "santa lucía": "C0174",
    "segurcaixa": "C0124",
    "adeslas": "C0124",
    "ocaso": "C0133",
    "divina pastora": "C0247",
    "helvetia": "C0157",
    "fiatc": "M0134",
    "mgs": "C0794",
    "verti": "C0785",
    "direct seguros": "C0785",
    "lagun aro": "C0572",
    "bbva": "C0502",
    "bbva allianz": "C0807",
    "soliss": "M0191",
    "hiscox": "E0231",
    "chubb": "E0155",
    "admiral": "C0805",
    "hello auto": "C0804",
    "hello": "C0804",
    "abanca": "C0808",
    "patria hispana": "C0139",
    "union alcoyana": "C0188",
    "la unión alcoyana": "C0188",
    "bilbao": "C0026",
    "caser": "C0031",
    "caja de seguros reunidos": "C0031",
    "asefa": "C0715",
    "ges": "C0089",
    "amic": "C0682",
    "mutua levante": "M0140",
    "mutua mmt": "M0084",
    "mussap": "M0107",
    "welcome": "C0811",
    "telefonica": "C0810",
    "santander": "C0806",
    "mapfre familiar": "C0676",
    "fidelidade": "E0118",
    "markel": "E0235",
    "wakam": "L0645",
    "cardif": "E0130",
    "iptiq": "E0252",
    "aig": "E0226",
    "tokio marine": "E0236",
    "hdi": "E0213",
    "liberty mutual": "E0174",
    "qbe": "E0230",
    "inter partner": "E0196",
    "xl insurance": "E0134",
    "gacm": "C0708",
    "asegrup": "C0001",
    "reale seguros": "C0613",
    "plus ultra seguros": "C0517",
    "generali españa": "C0072",
    "mapfre españa": "C0058",
    "zurich insurance": "E0189",
    "liberty seguros": "C0467",
    "mutua tinerfeña": "M0216",
    "mutua segorbina": "M0167",
    "umas": "M0363",
}

_NORM_RE = re.compile(r"[^a-z0-9\s]")


def _normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation for fuzzy matching."""
    t = text.lower().strip()
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for k, v in replacements.items():
        t = t.replace(k, v)
    return _NORM_RE.sub("", t).strip()


def find_aseguradora_code(name: str) -> Optional[str]:
    """Find the Merlin code for an insurance company by name.

    Tries exact alias match first, then substring match against the full list.
    Returns the code string (e.g. "C0058") or None if not found.
    """
    if not name:
        return None

    # Already a code?
    upper = name.strip().upper()
    if re.match(r"^[A-Z]\d{4}$", upper) or re.match(r"^INS\d+$", upper):
        return upper

    norm = _normalize(name)

    # 1. Exact alias
    if norm in _ALIASES:
        return _ALIASES[norm]

    # 2. Partial alias match (user input contains an alias key)
    best_alias = None
    best_len = 0
    for alias, code in _ALIASES.items():
        if alias in norm and len(alias) > best_len:
            best_alias = code
            best_len = len(alias)
    if best_alias:
        return best_alias

    # 3. Substring search in full company descriptions
    for code, desc in _ALL_COMPANIES:
        norm_desc = _normalize(desc)
        if norm in norm_desc or norm_desc.startswith(norm):
            return code

    # 4. Token overlap — pick the company with most matching words
    tokens = set(norm.split())
    if not tokens:
        return None

    best_score = 0
    best_code = None
    for code, desc in _ALL_COMPANIES:
        desc_tokens = set(_normalize(desc).split())
        overlap = len(tokens & desc_tokens)
        if overlap > best_score:
            best_score = overlap
            best_code = code
    if best_score >= 1:
        return best_code

    return None
