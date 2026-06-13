#!/usr/bin/env python3
"""Caption, title, and description templates for Quran reels.

Maintainer-authored strings with placeholders, shared by the daily posting
pipeline and planned-reel rendering. These templates carry no commentary about
meaning; the passage name and reference come from the verse metadata.
"""

RECITER_NAMES = {
    "ar.alafasy": "Mishary Rashid al-Afasy",
    "ar.husary": "Mahmoud Khaleel al-Husary",
    "ar.minshawi": "Muhammad Siddiq al-Minshawi",
    "ar.muhammadayyoub": "Muhammad Ayyub",
    "ar.abdurrahmaansudais": "Abdul Rahman As-Sudais",
}


def _verse_ref(verse):
    s, a, e = verse["surah"], verse["ayah"], verse["ayah_end"]
    return f"{s}:{a}" if a == e else f"{s}:{a}-{e}"


def build_caption(verse):
    ref = _verse_ref(verse)
    reciter = RECITER_NAMES.get(verse["reciter"], verse["reciter"])
    return (
        f"{verse['name']} | {ref}\n\n"
        f"Recited by Sheikh {reciter}\n\n"
        f"May Allah grant us understanding of His words.\n\n"
        f"#Quran #QuranRecitation #Islam #Muslim #DailyQuran "
        f"#IslamicReminder #QuranVerses #Dawah #SadaqahJariyah"
    )


def build_youtube_title(verse):
    return f"{verse['name']} | {_verse_ref(verse)} | Quran Recitation #Shorts"


def build_youtube_description(verse):
    ref = _verse_ref(verse)
    reciter = RECITER_NAMES.get(verse["reciter"], verse["reciter"])
    return f"{verse['name']} | {ref}\n\nRecited by Sheikh {reciter}\n\nMay Allah grant us understanding of His words."
