#!/usr/bin/env python3
"""
Generate a comprehensive verses.json covering the entire Quran.

Groups verses into meaningful passages (not random single-verse picks).
Rotates reciters and scenery queries for variety.

The Quran has 6,236 verses across 114 surahs. This script produces ~1,500-2,000
passage entries that collectively cover every verse, with special attention to
well-known passages getting their own dedicated entries.
"""

import json
import random

# ── Surah metadata: (name_en, total_ayahs) ──────────────────────────────────
# Source: standard Uthmani mushaf ayah counts

SURAHS = {
    1: ("Al-Fatihah", 7),
    2: ("Al-Baqarah", 286),
    3: ("Aal-Imran", 200),
    4: ("An-Nisa", 176),
    5: ("Al-Ma'idah", 120),
    6: ("Al-An'am", 165),
    7: ("Al-A'raf", 206),
    8: ("Al-Anfal", 75),
    9: ("At-Tawbah", 129),
    10: ("Yunus", 109),
    11: ("Hud", 123),
    12: ("Yusuf", 111),
    13: ("Ar-Ra'd", 43),
    14: ("Ibrahim", 52),
    15: ("Al-Hijr", 99),
    16: ("An-Nahl", 128),
    17: ("Al-Isra", 111),
    18: ("Al-Kahf", 110),
    19: ("Maryam", 98),
    20: ("Taha", 135),
    21: ("Al-Anbiya", 112),
    22: ("Al-Hajj", 78),
    23: ("Al-Mu'minun", 118),
    24: ("An-Nur", 64),
    25: ("Al-Furqan", 77),
    26: ("Ash-Shu'ara", 227),
    27: ("An-Naml", 93),
    28: ("Al-Qasas", 88),
    29: ("Al-Ankabut", 69),
    30: ("Ar-Rum", 60),
    31: ("Luqman", 34),
    32: ("As-Sajdah", 30),
    33: ("Al-Ahzab", 73),
    34: ("Saba", 54),
    35: ("Fatir", 45),
    36: ("Ya-Sin", 83),
    37: ("As-Saffat", 182),
    38: ("Sad", 88),
    39: ("Az-Zumar", 75),
    40: ("Ghafir", 85),
    41: ("Fussilat", 54),
    42: ("Ash-Shura", 53),
    43: ("Az-Zukhruf", 89),
    44: ("Ad-Dukhan", 59),
    45: ("Al-Jathiyah", 37),
    46: ("Al-Ahqaf", 35),
    47: ("Muhammad", 38),
    48: ("Al-Fath", 29),
    49: ("Al-Hujurat", 18),
    50: ("Qaf", 45),
    51: ("Adh-Dhariyat", 60),
    52: ("At-Tur", 49),
    53: ("An-Najm", 62),
    54: ("Al-Qamar", 55),
    55: ("Ar-Rahman", 78),
    56: ("Al-Waqi'ah", 96),
    57: ("Al-Hadid", 29),
    58: ("Al-Mujadilah", 22),
    59: ("Al-Hashr", 24),
    60: ("Al-Mumtahanah", 13),
    61: ("As-Saff", 14),
    62: ("Al-Jumu'ah", 11),
    63: ("Al-Munafiqun", 11),
    64: ("At-Taghabun", 18),
    65: ("At-Talaq", 12),
    66: ("At-Tahrim", 12),
    67: ("Al-Mulk", 30),
    68: ("Al-Qalam", 52),
    69: ("Al-Haqqah", 52),
    70: ("Al-Ma'arij", 44),
    71: ("Nuh", 28),
    72: ("Al-Jinn", 28),
    73: ("Al-Muzzammil", 20),
    74: ("Al-Muddaththir", 56),
    75: ("Al-Qiyamah", 40),
    76: ("Al-Insan", 31),
    77: ("Al-Mursalat", 50),
    78: ("An-Naba", 40),
    79: ("An-Nazi'at", 46),
    80: ("Abasa", 42),
    81: ("At-Takwir", 29),
    82: ("Al-Infitar", 19),
    83: ("Al-Mutaffifin", 36),
    84: ("Al-Inshiqaq", 25),
    85: ("Al-Buruj", 22),
    86: ("At-Tariq", 17),
    87: ("Al-A'la", 19),
    88: ("Al-Ghashiyah", 26),
    89: ("Al-Fajr", 30),
    90: ("Al-Balad", 20),
    91: ("Ash-Shams", 15),
    92: ("Al-Layl", 21),
    93: ("Ad-Duha", 11),
    94: ("Ash-Sharh", 8),
    95: ("At-Tin", 8),
    96: ("Al-Alaq", 19),
    97: ("Al-Qadr", 5),
    98: ("Al-Bayyinah", 8),
    99: ("Az-Zalzalah", 8),
    100: ("Al-Adiyat", 11),
    101: ("Al-Qari'ah", 11),
    102: ("At-Takathur", 8),
    103: ("Al-Asr", 3),
    104: ("Al-Humazah", 9),
    105: ("Al-Fil", 5),
    106: ("Quraysh", 4),
    107: ("Al-Ma'un", 7),
    108: ("Al-Kawthar", 3),
    109: ("Al-Kafirun", 6),
    110: ("An-Nasr", 3),
    111: ("Al-Masad", 5),
    112: ("Al-Ikhlas", 4),
    113: ("Al-Falaq", 5),
    114: ("An-Nas", 6),
}

# ── Verified reciters ────────────────────────────────────────────────────────

RECITERS = [
    "ar.alafasy",
    "ar.husary",
    "ar.minshawi",
    "ar.muhammadayyoub",
    "ar.abdurrahmaansudais",
]

# ── Nature-only scenery queries  ──────────────────────────────────

SCENERY_QUERIES = [
    "ocean waves aerial drone",
    "mountain clouds timelapse",
    "forest canopy aerial drone",
    "desert sand dunes wind",
    "waterfall rainforest mist",
    "northern lights sky timelapse",
    "moonlit clouds timelapse",
    "autumn forest leaves falling",
    "peaceful lake reflection landscape",
    "river stream rocks close up",
    "snowy mountain peak aerial",
    "flower field meadow close up",
    "deep blue ocean aerial drone",
    "galaxy milky way timelapse",
    "tropical waterfall jungle aerial",
    "starry night sky timelapse",
    "calm sea horizon aerial drone",
    "vast open plains aerial landscape",
    "blue sky clouds timelapse",
    "desert night stars timelapse",
    "morning mist valley aerial",
    "spring cherry blossom close up",
    "snowfall pine trees close up",
    "underwater coral reef fish",
    "fog mountain forest aerial",
    "volcanic landscape aerial drone",
    "sunset clouds golden aerial",
    "rice terraces aerial landscape",
    "frozen lake ice aerial",
    "lavender field aerial drone",
    "canyon rock formation aerial",
    "bamboo forest green close up",
    "sand ripples desert aerial",
    "rain drops leaves close up",
    "wheat field golden wind",
    "glacier ice blue close up",
    "moss rocks stream close up",
    "storm clouds dramatic timelapse",
    "tulip field colorful aerial",
    "cave stalactites close up",
    "palm trees tropical aerial",
    "wildflowers mountain meadow close up",
    "crystal clear water stream aerial",
    "misty forest morning aerial",
    "sand dunes sahara aerial drone",
    "coastline rocky waves aerial",
    "snow capped mountains aerial drone",
    "tropical island aerial drone",
    "rolling hills green aerial",
    "autumn lake trees reflection",
    "pine forest snow aerial drone",
    "sea foam waves close up",
    "meadow flowers sunshine close up",
    "cliff edge ocean aerial",
    "rainforest canopy aerial drone",
    "dry lake bed cracked earth close up",
    "waterlily pond close up",
    "aurora borealis landscape timelapse",
    "coral underwater ocean close up",
    "mountain river rapids aerial",
    "volcanic lava flow aerial drone",
    "prairie grassland wind aerial",
    "icicles frozen waterfall close up",
    "mangrove roots underwater close up",
    "dew drops spider web close up",
    "sunflower field aerial drone",
    "fjord norway aerial drone",
    "sahara stars night timelapse",
    "bioluminescent waves ocean night",
    "bamboo leaves rain close up",
]

# ── Curated passage breakpoints for major surahs ────────────────────────────
# These define thematic passage boundaries based on Quranic structure.
# Format: list of (start_ayah, end_ayah, passage_name) tuples.
# For surahs not listed here, auto-chunking is used.

CURATED_PASSAGES = {
    1: [
        (1, 7, "Al-Fatihah"),
    ],
    2: [
        (1, 5, "Guidance for the Righteous"),
        (6, 7, "Sealed Hearts"),
        (8, 16, "The Hypocrites"),
        (17, 20, "Parable of Fire and Rain"),
        (21, 25, "Call to Worship"),
        (26, 29, "Parable of the Mosquito"),
        (30, 33, "Creation of Adam"),
        (34, 39, "Adam and Iblis"),
        (40, 46, "Reminder to Bani Isra'il"),
        (47, 49, "Favor Upon Bani Isra'il"),
        (50, 57, "Parting of the Sea and the Calf"),
        (58, 62, "Forgiveness and Provision"),
        (63, 66, "The Covenant and the Sabbath"),
        (67, 73, "The Cow"),
        (74, 82, "Hard Hearts"),
        (83, 86, "Covenant of Bani Isra'il"),
        (87, 96, "Rejecting Messengers"),
        (97, 103, "Enmity to Jibril"),
        (104, 112, "Abrogation and Jealousy"),
        (113, 119, "Jews and Christians"),
        (120, 123, "Following Ibrahim"),
        (124, 129, "Ibrahim Builds the Ka'bah"),
        (130, 134, "The Way of Ibrahim"),
        (135, 141, "Be Muslims"),
        (142, 145, "Changing of the Qiblah"),
        (146, 152, "The Qiblah and Remembrance"),
        (153, 157, "Patience and Perseverance"),
        (158, 162, "Safa and Marwah"),
        (163, 167, "One God"),
        (168, 176, "Lawful Food and Following Shaytan"),
        (177, 177, "Righteousness"),
        (178, 182, "Qisas"),
        (183, 187, "Fasting"),
        (188, 188, "Do Not Consume Wealth Unjustly"),
        (189, 194, "Fighting in Allah's Cause"),
        (195, 196, "Spend in Allah's Way and Hajj"),
        (197, 203, "Hajj"),
        (204, 210, "Types of People"),
        (211, 214, "Trials"),
        (215, 218, "Spending and Fighting"),
        (219, 220, "Wine and Gambling"),
        (221, 228, "Marriage Laws"),
        (229, 232, "Divorce"),
        (233, 237, "Children and Widows"),
        (238, 242, "Prayer and Provisions"),
        (243, 245, "Fighting and Lending"),
        (246, 252, "Talut and Jalut"),
        (253, 254, "Messengers and Spending"),
        (255, 255, "Ayat al-Kursi"),
        (256, 257, "No Compulsion in Religion"),
        (258, 260, "Ibrahim's Arguments"),
        (261, 266, "Spending in Allah's Way"),
        (267, 274, "Charity"),
        (275, 281, "Prohibition of Riba"),
        (282, 283, "Recording Debts"),
        (284, 286, "Closing of Al-Baqarah"),
    ],
    3: [
        (1, 9, "Allah's Revelation"),
        (10, 13, "Warning to Disbelievers"),
        (14, 20, "Beautified Desires and Submission"),
        (21, 25, "Those Who Reject Signs"),
        (26, 32, "Sovereignty and Obedience"),
        (33, 41, "Chosen Families and Maryam"),
        (42, 51, "Isa Son of Maryam"),
        (52, 58, "Disciples and Scheming"),
        (59, 63, "Truth About Isa"),
        (64, 68, "Common Word"),
        (69, 74, "People of the Book"),
        (75, 80, "Trust and Covenants"),
        (81, 85, "Covenant of Prophets"),
        (86, 91, "Rejecting After Belief"),
        (92, 97, "Spending and the Ka'bah"),
        (98, 103, "Hold Fast to the Rope of Allah"),
        (104, 109, "Enjoin Good"),
        (110, 115, "Best Nation"),
        (116, 120, "Spending and Enemies"),
        (121, 129, "Battle of Uhud"),
        (130, 136, "Do Not Consume Riba"),
        (137, 143, "Travel the Earth"),
        (144, 148, "Muhammad is a Messenger"),
        (149, 155, "Lessons from Uhud"),
        (156, 163, "Trust in Allah"),
        (164, 171, "Blessing of the Prophet"),
        (172, 176, "Those Who Responded"),
        (177, 180, "Disbelief and Withholding"),
        (181, 186, "Tested in Wealth"),
        (187, 189, "Covenant of Scholars"),
        (190, 195, "Signs in Creation"),
        (196, 200, "Patience and Perseverance"),
    ],
    18: [
        (1, 5, "Praise to Allah for the Quran"),
        (6, 8, "Adornment of the Earth"),
        (9, 12, "Companions of the Cave"),
        (13, 16, "Youth Who Believed"),
        (17, 20, "The Cave"),
        (21, 22, "Discovery of the Sleepers"),
        (23, 26, "Say Insha'Allah"),
        (27, 31, "Recite the Book and Gardens"),
        (32, 44, "Parable of Two Gardens"),
        (45, 46, "Life of This World"),
        (47, 49, "Day of Judgment"),
        (50, 53, "Iblis Refuses to Prostrate"),
        (54, 59, "Parables and Destruction"),
        (60, 65, "Musa and Al-Khidr Begin"),
        (66, 70, "Musa and Al-Khidr — The Boat"),
        (71, 73, "Musa and Al-Khidr — The Boy"),
        (74, 78, "Musa and Al-Khidr — The Wall"),
        (79, 82, "Al-Khidr Explains"),
        (83, 91, "Dhul-Qarnayn Travels"),
        (92, 98, "Dhul-Qarnayn and Ya'juj Ma'juj"),
        (99, 101, "The Trumpet"),
        (102, 106, "Disbelievers' Loss"),
        (107, 110, "Gardens of Firdaws"),
    ],
    19: [
        (1, 6, "Zakariyya's Dua"),
        (7, 11, "Glad Tidings of Yahya"),
        (12, 15, "Yahya's Qualities"),
        (16, 21, "Maryam and Jibril"),
        (22, 26, "Birth of Isa"),
        (27, 33, "Isa Speaks in the Cradle"),
        (34, 40, "Truth About Isa"),
        (41, 50, "Ibrahim and His Father"),
        (51, 53, "Musa"),
        (54, 55, "Isma'il"),
        (56, 57, "Idris"),
        (58, 65, "Those Who Were Favored"),
        (66, 72, "Resurrection"),
        (73, 76, "Believers and Disbelievers"),
        (77, 82, "The Boastful"),
        (83, 87, "Shayateen and Intercession"),
        (88, 95, "They Attribute a Son"),
        (96, 98, "Love for the Believers"),
    ],
    20: [
        (1, 8, "Ta-Ha Opening"),
        (9, 16, "Musa and the Fire"),
        (17, 24, "Staff and Hand of Musa"),
        (25, 28, "Dua of Musa"),
        (29, 36, "Musa Asks for Harun"),
        (37, 40, "Allah's Favor on Musa"),
        (41, 48, "Go to Fir'awn"),
        (49, 55, "Musa Before Fir'awn"),
        (56, 64, "Fir'awn's Sorcerers"),
        (65, 70, "The Sorcerers Believe"),
        (71, 76, "Punishment and Forgiveness"),
        (77, 82, "Crossing the Sea"),
        (83, 89, "The Golden Calf"),
        (90, 98, "Musa Confronts Harun and Samiri"),
        (99, 104, "Day of the Trumpet"),
        (105, 114, "The Earth on That Day"),
        (115, 123, "Adam and Iblis"),
        (124, 128, "Turning Away from Remembrance"),
        (129, 132, "Patience and Prayer"),
        (133, 135, "Signs and Guidance"),
    ],
    24: [
        (1, 5, "Punishment for Zina"),
        (6, 10, "Li'an"),
        (11, 20, "The Slander — Ifk"),
        (21, 22, "Do Not Follow Shaytan"),
        (23, 26, "Accusing Chaste Women"),
        (27, 29, "Etiquette of Entering Houses"),
        (30, 31, "Lowering the Gaze"),
        (32, 34, "Marriage and Chastity"),
        (35, 35, "Ayat an-Nur — Light Verse"),
        (36, 38, "Houses of Remembrance"),
        (39, 40, "Deeds of Disbelievers"),
        (41, 46, "Everything Glorifies Allah"),
        (47, 54, "Obedience"),
        (55, 57, "Promise of Succession"),
        (58, 60, "Etiquette of Privacy"),
        (61, 64, "Etiquette of Gatherings"),
    ],
    36: [
        (1, 12, "Ya-Sin Opening and the Messengers"),
        (13, 19, "The Messengers to the Town"),
        (20, 27, "The Believer from the Town"),
        (28, 32, "Destroyed Generations"),
        (33, 40, "Signs of Allah in Creation"),
        (41, 44, "The Ark and Mercy"),
        (45, 47, "Turning Away from Signs"),
        (48, 54, "The Final Trumpet"),
        (55, 58, "People of Paradise"),
        (59, 64, "Separation of Sinners"),
        (65, 68, "Testimony of Limbs"),
        (69, 70, "The Quran is Not Poetry"),
        (71, 76, "Cattle and Gratitude"),
        (77, 83, "Creation from a Drop to Resurrection"),
    ],
    55: [
        (1, 4, "Ar-Rahman — He Taught the Quran"),
        (5, 9, "The Sun, Moon, Stars, and Balance"),
        (10, 13, "The Earth and Its Fruits"),
        (14, 16, "Creation of Man and Jinn"),
        (17, 21, "Two Easts and Two Wests"),
        (22, 25, "Pearls and Coral"),
        (26, 28, "Everything Will Perish"),
        (29, 30, "All Ask of Him"),
        (31, 34, "You Will Be Held to Account"),
        (35, 36, "Flames of Fire"),
        (37, 38, "The Sky Split Open"),
        (39, 40, "No One Asked About Sin"),
        (41, 45, "Sinners Seized"),
        (46, 51, "Two Gardens for the God-Fearing"),
        (52, 55, "Fruits and Springs"),
        (56, 61, "Untouched Companions"),
        (62, 67, "Two More Gardens"),
        (68, 73, "Green Gardens"),
        (74, 78, "Untouched by Man or Jinn"),
    ],
    56: [
        (1, 6, "The Event"),
        (7, 10, "Three Groups"),
        (11, 14, "The Foremost"),
        (15, 26, "Companions of the Right"),
        (27, 40, "More on the Right"),
        (41, 48, "Companions of the Left"),
        (49, 56, "All Will Be Gathered"),
        (57, 62, "Creation and Death"),
        (63, 67, "Crops"),
        (68, 70, "Water"),
        (71, 74, "Fire"),
        (75, 80, "Oath by the Stars — The Quran"),
        (81, 87, "Do You Deny This"),
        (88, 96, "The Three at Death"),
    ],
    67: [
        (1, 2, "Blessed is He — Dominion"),
        (3, 5, "Perfection of Creation"),
        (6, 11, "Punishment of Disbelievers"),
        (12, 14, "Allah Knows What You Conceal"),
        (15, 18, "The Earth Made Manageable"),
        (19, 22, "Birds and Provision"),
        (23, 27, "Gratitude and Resurrection"),
        (28, 30, "Say: What If I Am Destroyed"),
    ],
    73: [
        (1, 8, "Stand in Prayer at Night"),
        (9, 14, "Trust in Allah"),
        (15, 19, "Warning Like to Fir'awn"),
        (20, 20, "Recite What is Easy"),
    ],
    78: [
        (1, 5, "The Great News"),
        (6, 16, "Signs of Allah's Creation"),
        (17, 20, "Day of Sorting"),
        (21, 30, "Hell"),
        (31, 36, "Paradise"),
        (37, 40, "The Day They Stand"),
    ],
    87: [
        (1, 5, "Glorify the Name of Your Lord"),
        (6, 8, "We Will Make You Recite"),
        (9, 13, "Remind"),
        (14, 19, "Success and the First Scriptures"),
    ],
    89: [
        (1, 5, "The Dawn — Oaths"),
        (6, 14, "Past Nations Destroyed"),
        (15, 20, "Trial of Man"),
        (21, 26, "The Day the Earth is Crushed"),
        (27, 30, "The Tranquil Soul"),
    ],
    93: [
        (1, 5, "By the Morning Light"),
        (6, 8, "Did He Not Find You"),
        (9, 11, "So As for the Orphan"),
    ],
    94: [
        (1, 4, "Did We Not Expand Your Chest"),
        (5, 8, "With Hardship Comes Ease"),
    ],
    96: [
        (1, 5, "Read! — First Revelation"),
        (6, 8, "Transgression of Man"),
        (9, 14, "He Who Forbids Prayer"),
        (15, 19, "Prostrate and Draw Near"),
    ],
    97: [
        (1, 5, "Laylat al-Qadr"),
    ],
}

# ── Curated "famous standalone verses" ───────────────────────────────────────
# These get their own entries even if they're within a larger passage
# (surah, ayah, ayah_end, name)

FAMOUS_VERSES = [
    (2, 255, 255, "Ayat al-Kursi"),
    (2, 256, 257, "No Compulsion in Religion"),
    (2, 286, 286, "End of Al-Baqarah — Dua"),
    (2, 152, 152, "Remember Me"),
    (2, 186, 186, "I Am Near"),
    (2, 216, 216, "Perhaps You Dislike Something Good for You"),
    (3, 26, 27, "Owner of Sovereignty"),
    (3, 139, 139, "Do Not Weaken"),
    (3, 173, 174, "Sufficient is Allah"),
    (3, 185, 185, "Every Soul Shall Taste Death"),
    (5, 32, 32, "Saving a Life"),
    (6, 59, 59, "Keys of the Unseen"),
    (6, 162, 163, "My Prayer is for Allah"),
    (7, 56, 56, "Mercy of Allah is Near"),
    (9, 51, 51, "Nothing Befalls Us"),
    (10, 62, 63, "Friends of Allah — No Fear"),
    (12, 86, 86, "I Complain Only to Allah"),
    (12, 87, 87, "Do Not Despair of Allah's Mercy"),
    (13, 28, 28, "Hearts Find Rest in Remembrance"),
    (14, 7, 7, "Be Grateful and I Will Increase You"),
    (16, 97, 97, "Good Life for the Righteous"),
    (17, 23, 24, "Be Kind to Parents"),
    (17, 80, 80, "Dua for Entry and Exit"),
    (17, 82, 82, "Quran as Healing"),
    (18, 10, 10, "Dua of the Cave"),
    (18, 109, 109, "Words of Allah — Ink of the Sea"),
    (20, 25, 28, "Dua of Musa"),
    (21, 87, 87, "Dua of Yunus"),
    (21, 83, 84, "Dua of Ayyub"),
    (23, 115, 115, "Created Without Purpose?"),
    (23, 118, 118, "Lord Forgive and Have Mercy"),
    (24, 35, 35, "Ayat an-Nur — Light Verse"),
    (25, 74, 74, "Coolness of Our Eyes"),
    (27, 62, 62, "Who Responds to the Distressed"),
    (28, 24, 24, "Dua of Musa — In Need of Good"),
    (29, 69, 69, "Strive in Our Way"),
    (33, 21, 21, "Beautiful Example in the Messenger"),
    (33, 41, 42, "Remember Allah Abundantly"),
    (33, 56, 56, "Salawat upon the Prophet"),
    (33, 72, 72, "The Trust"),
    (35, 32, 32, "Inheritors of the Book"),
    (36, 58, 58, "Peace from a Merciful Lord"),
    (36, 82, 82, "Be! And It Is"),
    (39, 53, 53, "Despair Not of Allah's Mercy"),
    (40, 60, 60, "Call Upon Me"),
    (41, 34, 35, "Repel Evil with Good"),
    (42, 11, 11, "Nothing is Like Him"),
    (42, 19, 19, "Allah is Subtle with His Servants"),
    (48, 29, 29, "Muhammad is the Messenger"),
    (49, 13, 13, "Created You as Nations and Tribes"),
    (50, 16, 16, "Closer Than the Jugular Vein"),
    (51, 56, 56, "Created Jinn and Mankind to Worship"),
    (53, 39, 40, "Man Gets Only What He Strives For"),
    (57, 4, 4, "He is With You Wherever You Are"),
    (59, 22, 24, "Names of Allah"),
    (64, 11, 11, "Trust in Allah — Tawakkul"),
    (65, 2, 3, "Allah Makes a Way Out"),
    (65, 7, 7, "After Hardship — Ease"),
    (67, 1, 2, "Blessed is He — Sovereignty"),
    (72, 18, 18, "Mosques Belong to Allah"),
    (73, 8, 8, "Devote Yourself to Him"),
    (76, 8, 9, "Feeding for the Sake of Allah"),
    (94, 5, 6, "With Hardship Comes Ease"),
    (112, 1, 4, "Al-Ikhlas"),
    (113, 1, 5, "Al-Falaq"),
    (114, 1, 6, "An-Nas"),
]


def get_surah_name(surah_num):
    return SURAHS[surah_num][0]


def get_surah_ayah_count(surah_num):
    return SURAHS[surah_num][1]


def auto_chunk_surah(surah_num, chunk_size=5):
    """
    Automatically break a surah into passages of ~chunk_size verses.
    Used for surahs without curated breakpoints.
    """
    name = get_surah_name(surah_num)
    total = get_surah_ayah_count(surah_num)
    
    # Short surahs (<=15 verses): treat as single entry
    if total <= 15:
        return [(1, total, name)]
    
    passages = []
    ayah = 1
    part = 1
    while ayah <= total:
        end = min(ayah + chunk_size - 1, total)
        # Don't leave a tiny remainder (1-2 verses)
        if total - end > 0 and total - end < 3:
            end = total
        passages.append((ayah, end, f"{name} {ayah}-{end}"))
        ayah = end + 1
        part += 1
    
    return passages


def generate_all_passages():
    """Generate passage entries for the ENTIRE Quran."""
    all_entries = []
    reciter_idx = 0
    scenery_idx = 0
    
    for surah_num in range(1, 115):
        if surah_num in CURATED_PASSAGES:
            passages = CURATED_PASSAGES[surah_num]
        else:
            passages = auto_chunk_surah(surah_num)
        
        for (start, end, passage_name) in passages:
            entry = {
                "surah": surah_num,
                "ayah": start,
                "ayah_end": end,
                "name": passage_name,
                "reciter": RECITERS[reciter_idx % len(RECITERS)],
                "scenery_query": SCENERY_QUERIES[scenery_idx % len(SCENERY_QUERIES)],
            }
            all_entries.append(entry)
            reciter_idx += 1
            scenery_idx += 1
    
    return all_entries


def add_famous_verses(entries):
    """
    Ensure famous standalone verses have their own dedicated entries.
    If they're already covered by a passage, add them as separate entries
    with a dedicated reciter assignment for variety.
    """
    existing = set()
    for e in entries:
        for a in range(e["ayah"], e["ayah_end"] + 1):
            existing.add((e["surah"], a))
    
    famous_entries = []
    reciter_idx = 2  # offset so famous verses get different reciters
    scenery_idx = 7  # offset for variety
    
    for (surah, start, end, name) in FAMOUS_VERSES:
        entry = {
            "surah": surah,
            "ayah": start,
            "ayah_end": end,
            "name": f"★ {name}",
            "reciter": RECITERS[reciter_idx % len(RECITERS)],
            "scenery_query": SCENERY_QUERIES[scenery_idx % len(SCENERY_QUERIES)],
        }
        famous_entries.append(entry)
        reciter_idx += 1
        scenery_idx += 3  # larger step for more variety
    
    return famous_entries + entries


def main():
    # Generate all passages covering the entire Quran
    all_passages = generate_all_passages()
    
    # Add famous verses as dedicated entries at the top
    full_list = add_famous_verses(all_passages)
    
    # Shuffle the non-famous entries for variety in daily posting
    famous_count = len(FAMOUS_VERSES)
    famous = full_list[:famous_count]
    rest = full_list[famous_count:]
    random.seed(42)  # reproducible shuffle
    random.shuffle(rest)
    
    # Famous verses first, then shuffled full coverage
    final = famous + rest
    
    # Stats
    total_verses_covered = set()
    for e in all_passages:
        for a in range(e["ayah"], e["ayah_end"] + 1):
            total_verses_covered.add((e["surah"], a))
    
    print(f"Total entries: {len(final)}")
    print(f"  Famous standalone verses: {famous_count}")
    print(f"  Full Quran passages: {len(all_passages)}")
    print(f"  Unique verses covered: {len(total_verses_covered)} / 6236")
    print(f"  Reciters used: {len(RECITERS)}")
    print(f"  Scenery queries: {len(SCENERY_QUERIES)}")
    
    # Write output
    output_path = "/home/claude/verses.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    
    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    main()
