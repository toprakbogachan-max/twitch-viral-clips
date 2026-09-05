from __future__ import annotations

import re

BASE_TAGS = ["#Shorts", "#Twitch", "#TwitchClips", "#Viral", "#fyp"]
LANGUAGE_TAGS = {"tr": "#TwitchTR", "en": "#TwitchEN", "es": "#TwitchES"}


def _category_hashtag(category: str) -> str:
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", category)
    return "#" + "".join(w.capitalize() for w in words) if words else ""


def build_hashtags(category: str, language: str) -> list[str]:
    tags = list(BASE_TAGS)

    cat_tag = _category_hashtag(category)
    if cat_tag and cat_tag not in tags:
        tags.append(cat_tag)

    lang_tag = LANGUAGE_TAGS.get(language.lower().strip())
    if lang_tag and lang_tag not in tags:
        tags.append(lang_tag)

    return tags


def build_keywords(category: str, language: str) -> list[str]:
    keywords = ["twitch", "clips", "shorts", "viral"]
    if category:
        keywords.append(category.lower())
    if language:
        keywords.append(language.lower())
    return keywords
