"""
accent_adapter.py
Contextual Speech Intelligence & Accent Adaptation Engine for Sadie (Orb AI).
Applies common sense, phonetic compensation, and contextual grammar repair
to raw Speech-to-Text transcripts before injecting into chat.
"""

import os
import re
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOCAB_FILE = os.path.join(BASE_DIR, "custom_voice_vocabulary.json")

PHONETIC_PHRASE_RULES = [
    # Voice commands & UI
    (r"\bmassage[s]?\s+cute\b", "messages queued"),
    (r"\bmassage[s]?\s+queue[d]?\b", "messages queued"),
    (r"\bsound\s+sander\b", "send it"),
    (r"\bsand\s+through\b", "send through"),
    (r"\bsand\s+it\b", "send it"),
    (r"\bsand\s+say\b", "send, say"),
    (r"\bsand\s+say\s+go\b", "send, say go"),
    (r"\bsaying\s+sand\b", "saying send"),
    (r"\binstead\s+of\s+saying\s+sand\b", "instead of saying send"),
    (r"\bsand\s+now\b", "send now"),
    (r"\bpleas\s+sand\b", "please send"),
    (r"^\bcasting\b$", "testing"),
    (r"\bcasting\s+casting\b", "testing testing"),

    # Chat / Charts / Traps confusion
    (r"\bbetween\s+charts\b", "between chats"),
    (r"\bdifferent\s+charts\b", "different chats"),
    (r"\bongoing\s+charts\b", "ongoing chats"),
    (r"\bdifferent\s+traps\b", "different chats"),
    (r"\bcertain\s+trap\b", "certain chat"),
    (r"\bjump\s+between\s+a\s+chart\b", "jump between a chat"),
    (r"\bjump\s+between\s+charts\b", "jump between chats"),
    (r"\bin\s+this\s+chart\b", "in this chat"),
    (r"\bopen\s+chart\b", "open chat"),

    # Orb AI pronunciations
    (r"\borb\s+isnot\b", "Orb is not"),
    (r"\borb\s+ai\b", "Orb AI"),
    (r"\borb\s+voice\b", "Orb voice"),

    # Accounting / HMRC / Banking context
    (r"\b(h\s*m\s*r\s*c|age\s*m\s*r\s*c|h\s*mark)\b", "HMRC"),
    (r"\bfilling\s+accounts\b", "filing accounts"),
    (r"\bfilling\s+dormant\b", "filing dormant"),
    (r"\bdormant\s+a\b", "dormant accounts"),
    (r"\bdormant\s+account[s]?\b", "dormant accounts"),
    (r"\b(v\s*a\s*t|that\s+return|fat\s+return)\b", "VAT"),
    (r"\b(pay\s*e|p\s*a\s*y\s*e)\b", "PAYE"),
    (r"\b(cooperation\s+tax|corporate\s+tags)\b", "corporation tax"),
    (r"\b(company\s+house|company's\s+house)\b", "Companies House"),
    (r"\b(tied|tight)\s+bank\b", "Tide bank"),
    (r"\b(tied|tight)\s+account\b", "Tide account"),
    (r"\b(tied|tight)\s+statements\b", "Tide statements"),
    (r"\bmanzo\s+bank\b", "Monzo bank"),
    (r"\bmanzo\b", "Monzo"),
    (r"\brevolute\b", "Revolut"),
    (r"\bsterling\s+bank\b", "Starling bank"),
    (r"\bsouth\s+assessment\b", "self assessment"),
    (r"\b(you\s*t\s*r|u\s*t\s*r)\b", "UTR"),
    (r"\bcore\s+market\s+goods\b", "Coremarket Goods"),
    (r"\bcoremarketgoods\b", "Coremarket Goods"),
    (r"\bthermo\s+retreat\b", "Thermo Retreats"),
    (r"\bthermo\s+retreats\b", "Thermo Retreats"),
    (r"\bkelvin\b", "Kevin"),
    (r"\bdavid\s+ends\b", "dividends"),
    (r"\bbook\s+keeping\b", "bookkeeping"),
    (r"\bbalance\s+chic\b", "balance sheet"),
    (r"\bp\s+and\s+l\b", "P&L"),
    (r"\banti\s+gravity\b", "Antigravity"),

    # Common sense grammar & words
    (r"\b88d\s+adhd\b", "ADHD"),
    (r"\b88d\b", "ADHD"),
    (r"\bshort\s+hair\b", "shorter"),
    (r"\bacross\s+all\s+tracks\b", "across all chats"),
    (r"\bin\s+humans\b", "in human terms"),
    (r"\bcommunicaing\b", "communicating"),
    (r"\bunderdtanding\b", "understanding"),
    (r"\bhavnt\b", "haven't"),
    (r"\bpronounciations\b", "pronunciations"),
    (r"\bcommon\s+sence\b", "common sense"),
    (r"\binsentences\b", "in sentences"),
]

VERB_SAND_PATTERNS = [
    (r"\b(i|we|you|they|to|please|can\s+you|just|will)\s+sand\b", r"\1 send"),
    (r"\bsand\s+(me|you|it|that|this|them|him|her|through|now)\b", r"send \1"),
]

def load_custom_vocab():
    if os.path.exists(VOCAB_FILE):
        try:
            with open(VOCAB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"replacements": {}}

def adapt_speech_text(raw_text):
    if not raw_text or not raw_text.strip():
        return raw_text

    text = raw_text.strip()
    original = text

    # 1. Custom user dictionary replacements
    vocab = load_custom_vocab()
    for pattern, rep in vocab.get("replacements", {}).items():
        try:
            text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
        except Exception:
            pass

    # 2. Phonetic phrase rules
    for pattern, rep in PHONETIC_PHRASE_RULES:
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)

    # 3. Contextual verb repairs ('sand' -> 'send' when preceded by pronouns/verbs)
    for pattern, rep in VERB_SAND_PATTERNS:
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)

    # 4. Clean up spacing and punctuation
    text = re.sub(r"\s+", " ", text).strip()

    if text != original:
        print(f"[ACCENT-ADAPTER] Adapted: '{original[:60]}' -> '{text[:60]}'", flush=True)

    return text
