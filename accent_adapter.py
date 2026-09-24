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
    # Regional Dialect & Accent Phonetic Normalization
    (r"\bversal\s+length\b", "Vercel link"),
    (r"\bversal\s+link\b", "Vercel link"),
    (r"\bversal\b", "Vercel"),
    (r"\bgerman\s+i\b", "Gemini"),
    (r"\bgerman\s+eye\b", "Gemini"),
    (r"\bgermany\b", "Gemini"),
    (r"\boil\s+budget\b", "Orb widget"),
    (r"\ball\s+budget\b", "Orb widget"),
    (r"\borb\s+budget\b", "Orb widget"),
    (r"\bpolicy\s+jesus\b", "Polish feature"),
    (r"\bthe\s+policy\b", "the Polish"),
    (r"\blassa\s+version\b", "lighter version"),
    (r"\bsans\s+better\b", "send button"),
    (r"\bsans\s+button\b", "send button"),
    (r"\bsand\s+button\b", "send button"),
    (r"\bfor\s+spots\b", "voice box"),
    (r"\bfor\s+a\s+spots\b", "voice box"),
    (r"\bthem\s+for\s+a\s+spots\b", "the voice box"),
    (r"\bvoice\s+box\s+type\b", "voice box"),
    (r"\blunch\s+pack\b", "launchpad"),
    (r"\blunch\s+pad\b", "launchpad"),
    (r"\bdex\s+builder\b", "dexBuilder"),
    (r"\bapk\s+s\b", "APKs"),
    (r"\bapk\.s\b", "APKs"),
    (r"\bblack\s+tax\b", "black text"),
    (r"\bwhite\s+tax\b", "white text"),
    (r"\btax\s+box\b", "text box"),
    (r"\bwhite\s+background\s+black\s+tax\b", "white background black text"),
    (r"\bsquash\s+is\b", "squashes"),
    (r"\binto\s+the\s+herds\b", "in terms of this"),
    (r"\bautosense\b", "auto-sends"),
    (r"\bauto\s+sense\b", "auto-sends"),
    (r"\bautosending\b", "auto-sending"),

    # Voice commands & UI
    (r"\bmassage[s]?\s+cute\b", "messages queued"),
    (r"\bmassage[s]?\s+queue[d]?\b", "messages queued"),
    (r"\bfull\s+massage\b", "full message"),
    (r"\bsee\s+the\s+massage\b", "see the message"),
    (r"\bthe\s+massage\b", "the message"),
    (r"\ba\s+massage\b", "a message"),
    (r"\bmassages\b", "messages"),
    (r"\bsend\s+in\s+a\s+massive\b", "send in a message"),
    (r"\bsending\s+a\s+massive\b", "sending a message"),
    (r"\bsound\s+sander\b", "send it"),
    (r"\bsand\s+through\b", "send through"),
    (r"\bsub[- ]through\b", "send through"),
    (r"\bsand\s+it\b", "send it"),
    (r"\bsand\s+say\b", "send, say"),
    (r"\bsand\s+say\s+go\b", "send, say go"),
    (r"\bsaying\s+sand\b", "saying send"),
    (r"\binstead\s+of\s+saying\s+sand\b", "instead of saying send"),
    (r"\bsand\s+now\b", "send now"),
    (r"\bpleas\s+sand\b", "please send"),
    (r"^\bcasting\b$", "testing"),
    (r"\bcasting\s+casting\b", "testing testing"),
    (r"\bfor\s+so\s+for\s+up\b", "first off"),
    (r"\bso\s+for\s+up\b", "so first off"),
    (r"\bfor\s+up\b", "first off"),

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
    (r"\b(i|we|you|they|to|please|can\s+you|just|will|could|should|would)\s+sand\b", r"\1 send"),
    (r"\bsand\s+(me|you|it|that|this|them|him|her|through|now|to|into|out)\b", r"send \1"),
    (r"\bsand\s+(a|an|the)\s+(message|prompt|chat|update|request)\b", r"send \1 \2"),
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
