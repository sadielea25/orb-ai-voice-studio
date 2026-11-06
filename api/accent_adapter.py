"""
accent_adapter.py
Contextual Speech Intelligence, Accent Adaptation & Habit Memory Engine for Sadie (Orb AI).
Applies phonetic compensation, British dialect adaptation, UK English normalization,
and persistent project/habit memory recall before injecting into chat or assistants.
"""

import os
import re
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'api' else BASE_DIR

VOCAB_PATHS = [
    os.path.join(BASE_DIR, 'custom_voice_vocabulary.json'),
    os.path.join(ROOT_DIR, 'custom_voice_vocabulary.json'),
    os.path.join(ROOT_DIR, 'api', 'custom_voice_vocabulary.json')
]

MEMORY_PATHS = [
    os.path.join(BASE_DIR, 'orb_user_memory.json'),
    os.path.join(ROOT_DIR, 'orb_user_memory.json'),
    os.path.join(ROOT_DIR, 'api', 'orb_user_memory.json')
]

PHONETIC_PHRASE_RULES = [
    # Regional Dialect & Accent Phonetic Normalization
    (r"\bversal\s+length\b", "Vercel link"),
    (r"\bversal\s+link\b", "Vercel link"),
    (r"\bversal\b", "Vercel"),
    (r"\bvessel\b", "Vercel"),
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

    # Projects, Businesses & Brands
    (r"\bcall\s+market\s+goods\b", "CoreMarketGoods"),
    (r"\bcall\s+market\b", "CoreMarket"),
    (r"\bcore\s+market\s+goods\b", "CoreMarketGoods"),
    (r"\bcore\s+market\b", "CoreMarket"),
    (r"\bcorn\s+market\s+goods\b", "CoreMarketGoods"),
    (r"\bcorn\s+market\b", "CoreMarket"),
    (r"\bspoke\s+studio\b", "Spook Studio"),
    (r"\bspooky\s+studio\b", "Spook Studio"),
    (r"\bdolled\s+up\s+to\s+death\b", "Dolled Up To Death"),
    (r"\bdoll\s+up\s+to\s+death\b", "Dolled Up To Death"),
    (r"\bh\s*m\s*r\s*c\b", "HMRC"),
    (r"\bhm\s+rc\b", "HMRC"),
    (r"\bh\s+m\s+rc\b", "HMRC"),
    (r"\banti\s+gravity\b", "Antigravity"),
    (r"\bantigrav\b", "Antigravity"),
    (r"\bdo\s+stuff\b", "DoStuff"),
    (r"\bdostuff\b", "DoStuff"),

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
    (r"\beighty\s+eight\s+d\b", "ADHD"),
    (r"\bshort\s+hair\b", "shorter"),
    (r"\bacross\s+all\s+tracks\b", "across all chats"),
    (r"\bin\s+humans\b", "in human terms"),
    (r"\bcommunicaing\b", "communicating"),
    (r"\bunderdtanding\b", "understanding"),
    (r"\bhavnt\b", "haven't"),
    (r"\bpronounciations\b", "pronunciations"),
    (r"\bcommon\s+sence\b", "common sense"),
    (r"\binsentences\b", "in sentences"),
    (r"\bbalance\s+chic\b", "balance sheet"),

    # UK English Spelling Normalization
    (r"\bcolor\b", "colour"),
    (r"\bcolors\b", "colours"),
    (r"\bcustomize\b", "customise"),
    (r"\bcustomized\b", "customised"),
    (r"\bcustomizing\b", "customising"),
    (r"\bcenter\b", "centre"),
    (r"\bcenters\b", "centres"),
    (r"\borganize\b", "organise"),
    (r"\borganized\b", "organised"),
    (r"\borganizing\b", "organising"),
    (r"\bprioritize\b", "prioritise"),
    (r"\bprioritized\b", "prioritised"),
    (r"\bprioritizing\b", "prioritising"),
]

VERB_SAND_PATTERNS = [
    (r"\b(i|we|you|they|to|please|can\s+you|just|will|could|should|would)\s+sand\b", r"\1 send"),
    (r"\bsand\s+(me|you|it|that|this|them|him|her|through|now|to|into|out)\b", r"send \1"),
    (r"\bsand\s+(a|an|the)\s+(message|prompt|chat|update|request)\b", r"send \1 \2"),
    (r"\bsand\b", "send"),
    (r"\bsans\b", "send"),
]

def load_custom_vocab():
    for p in VOCAB_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"replacements": {}, "vocabulary_words": []}

def save_custom_vocab(vocab_data):
    saved_any = False
    for p in VOCAB_PATHS:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(vocab_data, f, indent=2)
            saved_any = True
        except Exception:
            pass
    return saved_any

def load_user_memory():
    for p in MEMORY_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def save_user_memory(mem_data):
    saved_any = False
    for p in MEMORY_PATHS:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(mem_data, f, indent=2)
            saved_any = True
        except Exception:
            pass
    return saved_any

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

    # 3. Contextual verb repairs
    for pattern, rep in VERB_SAND_PATTERNS:
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)

    # 4. Clean up spacing and punctuation
    text = re.sub(r"\s+", " ", text).strip()

    if text != original:
        print(f"[ACCENT-ADAPTER] Adapted: '{original[:60]}' -> '{text[:60]}'", flush=True)

    return text
