#!/usr/bin/env python3
"""Append German→English learning rows to final_words_translated.csv.

Constraints:
- No external translation APIs/libraries.
- Translations/examples are hand-authored via the rule + override tables below.

This script:
- Reads .green_words.txt (index\ttext)
- Appends translated rows for indices >= .translation_progress
- Deduplicates by german (case-insensitive)
- Splits some combined OCR lines into multiple items
- Normalizes obvious case/article forms to learner-friendly base forms
- Updates .translation_progress to last_index+1 when finished

If a line is too unclear, it is skipped.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / ".green_words.txt"
OUT_PATH = ROOT / "final_words_translated.csv"
PROGRESS_PATH = ROOT / ".translation_progress"


def norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).casefold()


@dataclass(frozen=True)
class Row:
    german: str
    english: str
    example_de: str
    info: str


# --- Small hand-authored override tables (extend as needed) ---
# Keep these minimal; most rows should be covered by simple, human-sensible rules.

PHRASE_OVERRIDES: dict[str, Row] = {
    "das war wahnsinnig gut": Row(
        german="Das war wahnsinnig gut",
        english="That was insanely good",
        example_de="Das war wahnsinnig gut!",
        info="Redemittel; 'wahnsinnig' = sehr / total.",
    ),
    "einverstanden sein": Row(
        german="einverstanden sein",
        english="to agree / to be fine with it",
        example_de="Ich bin einverstanden.",
        info="Adjektiv + sein; oft: 'Ich bin (damit) einverstanden.'",
    ),
    "schlecht gelaunt sein": Row(
        german="schlecht gelaunt sein",
        english="to be in a bad mood",
        example_de="Heute bin ich schlecht gelaunt.",
        info="Redemittel; 'gelaunt' = in einer Stimmung.",
    ),
    "unter anderem": Row(
        german="unter anderem",
        english="among other things",
        example_de="Unter anderem kaufe ich Brot.",
        info="Feste Wendung = 'zum Beispiel auch'.",
    ),
    "also gut": Row(
        german="also gut",
        english="alright then / okay",
        example_de="Also gut, wir machen das.",
        info="Umgangssprachlich; oft am Satzanfang.",
    ),
    "das sehe ich anders": Row(
        german="Das sehe ich anders",
        english="I see that differently",
        example_de="Das sehe ich anders.",
        info="Redemittel, um höflich zu widersprechen.",
    ),
    "das ist ja toll": Row(
        german="Das ist ja toll",
        english="That's great!",
        example_de="Das ist ja toll!",
        info="Ausruf; 'ja' = Betonung/Überraschung.",
    ),
    "auf keinen fall": Row(
        german="auf keinen Fall",
        english="no way / under no circumstances",
        example_de="Auf keinen Fall!",
        info="Starke Verneinung.",
    ),
    "fließend sprechen": Row(
        german="fließend sprechen",
        english="to speak fluently",
        example_de="Ich spreche Deutsch fließend.",
        info="Adverb + Verb.",
    ),
    "ein paar dinge": Row(
        german="ein paar Dinge",
        english="a few things",
        example_de="Ich habe noch ein paar Dinge.",
        info="Feste Menge; 'ein paar' = einige.",
    ),
}

# Lemma overrides: normalized-source -> normalized/base learner form
LEMMA_OVERRIDES: dict[str, str] = {
    "die die cousine": "die Cousine",
    "einem führer": "der Führer",

    "einen helm": "der Helm",
    "den lärm": "der Lärm",
    "den ball": "der Ball",
    "den baum": "der Baum",
    "dem wasser": "das Wasser",
    "dem roller": "der Roller",
    "den bergen": "der Berg",

    "einem notfall": "der Notfall",
    "einem bild": "das Bild",
    "dem bild": "das Bild",
    "dem titel": "der Titel",
    "dem sofa": "das Sofa",
    "dem land": "das Land",

    "der wohnung": "die Wohnung",
    "der familie": "die Familie",
    "der hand": "die Hand",
    "der bank": "die Bank",
    "der polizei": "die Polizei",

    "einen kuchen": "der Kuchen",
    "einen kurzen text": "der kurze Text",
    "den letzten ausflug": "der letzte Ausflug",

    "einen antrag": "der Antrag",
    "den pass": "der Pass",
    "einen betrag": "der Betrag",
    "einen gefallen": "der Gefallen",
    "einen rat": "der Rat",
    "einen plan": "der Plan",
    "einen termin": "der Termin",
    "einen monat": "der Monat",

    "ein visum": "das Visum",
    "eine antwort": "die Antwort",
    "ein spiel": "das Spiel",
    "ein fest": "das Fest",
    "ein formular": "das Formular",
    "ein konto": "das Konto",
    "ein job": "der Job",
    "ein ticket": "das Ticket",
    "ein blatt": "das Blatt",
    "ein glück": "das Glück",

    "eine führung": "die Führung",
    "eine chance": "die Chance",
    "eine sprache": "die Sprache",

    "der karte": "die Karte",
    "der party": "die Party",
    "den lebensphasen": "die Lebensphase",

    "die führerschein": "der Führerschein",

    "ein paar dinge": "ein paar Dinge",
    "eine gute zugverbindung": "die gute Zugverbindung",
    "eine stadt-tour": "die Stadt-Tour",
    "eine fahrtkarte": "die Fahrtkarte",
    "eine einladung": "die Einladung",
    "einer hochzeit": "die Hochzeit",
    "ein start-up": "das Start-Up",

    "den beruf": "der Beruf",
    "der klasse": "die Klasse",
    "der behörde": "die Behörde",
    "dem studium": "das Studium",
    "verbringt": "verbringen",
    "unterhält": "sich unterhalten",
    "gebeten": "bitten",
    "entschieden": "entscheiden",

    # common conjugated/participle forms (OCR source often has full sentences)
    "fährt": "fahren",
    "fliegt": "fliegen",
    "geht": "gehen",
    "kommt": "kommen",
    "hält": "halten",
    "gehalten": "halten",
    "liegt": "liegen",
    "empfängt": "empfangen",
    "schläft": "schlafen",
    "schlägt": "schlagen",
    "ruft": "rufen",
    "gerufen": "rufen",
    "spricht": "sprechen",
    "entscheidet": "entscheiden",
    "gewinnt": "gewinnen",
    "stirbt": "sterben",
    "verschläft": "verschlafen",

    "verspricht": "versprechen",
    "bietet": "bieten",
    "bleiben": "bleiben",
    "nimmt": "nehmen",
    "gibt": "geben",
    "kennt": "kennen",
    "hängt": "hängen",
    "stinkt": "stinken",
    "trägt": "tragen",

    "verlässt": "verlassen",

    "abgeschlossen": "abschließen",
    "vorgeschlagen": "vorschlagen",
    "unternommen": "unternehmen",
    "verschoben": "verschieben",
    "zurückgegeben": "zurückgeben",
    "weggeworfen": "wegwerfen",
    "eingezogen": "einziehen",
    "weggelaufen": "weglaufen",
    "zurückgelaufen": "zurücklaufen",
    "vorgekommen": "vorkommen",
    "verbracht": "verbringen",
    "angeboten": "anbieten",

    "benimmt": "sich benehmen",
    "benommen": "sich benehmen",

    "die ur": "die Uhr",
}

# Gender/plural overrides for irregular forms we care about.
# Key is base noun WITHOUT article.
PLURAL_OVERRIDES: dict[str, str] = {
    "Berg": "Berge",
    "Wahnsinn": "-",
    "Erfolg": "Erfolge",
    "Wettbewerb": "Wettbewerbe",
    "Katastrophe": "Katastrophen",
    "Nationalpark": "Nationalparks",
    "Tal": "Täler",
    "Staat": "Staaten",
    "Höhle": "Höhlen",
    "Kanton": "Kantone",
    "Führer": "Führer",
    "Cousin": "Cousins",
    "Cousine": "Cousinen",
    "Sendung": "Sendungen",
    "Temperatur": "Temperaturen",
    "Hinweis": "Hinweise",
    "Nebel": "-",
    "Zuhause": "-",
    "Päckchen": "Päckchen",
    "Bauernhof": "Bauernhöfe",
    "Ferienwohnung": "Ferienwohnungen",
    "Lärm": "-",
    "Stadtrand": "Stadtränder",
    "Ufer": "Ufer",
    "Wasser": "-",
    "Wein": "Weine",
    "Luxus": "-",
    "Spielzeug": "-",
    "Altbau": "Altbauten",
    "Stockwerk": "Stockwerke",
    "Keller": "Keller",
    "Dach": "Dächer",
    "Boden": "Böden",
    "Baum": "Bäume",
    "Fläche": "Flächen",
    "Quadratmeter": "Quadratmeter",
    "Mitbewohner": "Mitbewohner",
    "Nebenkosten": "-",
    "Haustier": "Haustiere",
    "Katze": "Katzen",
    "Kätzchen": "Kätzchen",
    "Vogel": "Vögel",
    "Zulassung": "Zulassungen",
    "Ratte": "Ratten",
    "Maus": "Mäuse",
    "Hase": "Hasen",
    "Kuh": "Kühe",
    "Schaf": "Schafe",
    "Schwein": "Schweine",
    "Bär": "Bären",
    "Besitzerin": "Besitzerinnen",
    "Futter": "-",
    "Vergangenheit": "Vergangenheiten",
    "Tierarzt": "Tierärzte",
    "Ehe": "Ehen",
    "Hausfrau": "Hausfrauen",
    "Hausmann": "Hausmänner",
    "Zimmer": "Zimmer",
    "Feuer": "Feuer",
    "Gas": "-",
    "Heizung": "Heizungen",
    "Werktag": "Werktage",
    "Export": "Exporte",
    "Strom": "-",
    "Import": "Importe",
    "Hektik": "-",
    "Frist": "Fristen",
    "Helfer": "Helfer",
    "Helferin": "Helferinnen",
    "Notfall": "Notfälle",
    "Handy": "Handys",
    "Polizei": "-",
    "Unterkunft": "Unterkünfte",
    "Einkaufszentrum": "Einkaufszentren",
    "Lücke": "Lücken",
    "Mitleid": "-",
}

# Base translations (for frequent standalone words)
# Key should be lemma form (as output in german column).
EN_OVERRIDES: dict[str, str] = {
    "der Kletterer": "climber",
    "die Kletterin": "(female) climber",
    "genial": "brilliant / awesome",
    "die Wanderung": "hike",
    "der Wahnsinn": "madness / crazy thing",
    "die Strecke": "distance / route",
    "die Kondition": "fitness / stamina",
    "die Hoffnung": "hope",
    "die Gesundheit": "health",
    "der Erfolg": "success",
    "die Enttäuschung": "disappointment",
    "der Wettbewerb": "competition",
    "der Fußballschuh": "soccer shoe / cleat",
    "die Katastrophe": "disaster",
    "der Klettergurt": "climbing harness",
    "der Helm": "helmet",
    "die Matte": "mat",
    "sollen": "should / to be supposed to",
    "das Mountainbike": "mountain bike",
    "die Anreise": "journey there / getting there",
    "der Einwohner": "resident / inhabitant",
    "außer": "except / besides",
    "die Einwohnerin": "(female) resident",
    "das Gasthaus": "guesthouse / inn",
    "die Kette": "chain",
    "das Material": "material",
    "das Gebiet": "area / region",
    "die Umgebung": "surroundings / area",
    "der Nationalpark": "national park",
    "das Tal": "valley",
    "der Staat": "state / country",
    "die Höhle": "cave",
    "der Kanton": "canton",
    "der Führer": "guide",
    "die Führerin": "(female) guide",
    "der Cousin": "cousin (male)",
    "die Cousine": "cousin (female)",
    "die Sendung": "TV/radio programme",
    "die Antwort": "answer",
    "die Temperatur": "temperature",
    "der Hinweis": "tip / hint",
    "der Nebel": "fog",
    "neulich": "recently",
    "das Spiel": "game",
    "der Blumentopf": "flower pot",
    "der Briefkasten": "mailbox",
    "das Zuhause": "home (place)",
    "das Päckchen": "small parcel",
    "der Bauernhof": "farm",
    "die Ferienwohnung": "holiday apartment",
    "der Lärm": "noise",
    "der Bauer": "farmer",
    "bitte": "please / you're welcome",
    "der Stadtrand": "outskirts (edge of town)",
    "das": "that / this (neuter)",
    "das Hausboot": "houseboat",
    "das Fest": "festival / party",
    "das Ufer": "shore / riverbank",
    "das Sommerfest": "summer festival",
    "das Wasser": "water",
    "die Torte": "cake (cream cake)",
    "nass": "wet",
    "der Wein": "wine",
    "das Poster": "poster",
    "der Lampion": "paper lantern",
    "die Kerze": "candle",
    "der Luxus": "luxury",
    "das Spielzeug": "toy(s)",
    "das Gartenhaus": "garden shed / summer house",
    "der Roller": "scooter",
    "der Altbau": "old building (pre-war)",
    "das Stockwerk": "floor / storey",
    "das Kissen": "pillow",
    "der Keller": "basement / cellar",
    "das Dach": "roof",
    "der Boden": "floor / ground",
    "der Baum": "tree",
    "die Länge": "length",
    "die Breite": "width",
    "die Höhe": "height",
    "die Fläche": "area / surface",
    "der Quadratmeter": "square meter",
    "die Mieterin": "(female) tenant",
    "der Mitbewohner": "roommate / flatmate",
    "möbliert": "furnished",
    "die Nebenkosten": "additional costs (utilities)",
    "die Wohnung": "apartment / flat",
    "gießen": "to water (plants) / to pour",
    "gespannt": "curious / excited",
    "auskennen": "to know one's way around",
    "aus": "out / off; from",
    "kündigen": "to quit / to cancel",
    "das Haustier": "pet",
    "die Katze": "cat",
    "zurücklaufen": "to run back",
    "das Kätzchen": "kitten",
    "der Vogel": "bird",
    "die Zulassung": "admission / registration",
    "die Ratte": "rat",
    "die Maus": "mouse",
    "der Hase": "hare / bunny",
    "die Kuh": "cow",
    "das Schaf": "sheep",
    "das Schwein": "pig",
    "der Bär": "bear",
    "die Besitzerin": "(female) owner",
    "das Futter": "animal feed / food",
    "füttern": "to feed (an animal)",
    "zumindest": "at least",
    "dick": "thick / fat",
    "die Vergangenheit": "past",
    "der Stil": "style",
    "der Tierarzt": "vet",
    "die Veränderung": "change",
    "das Bild": "picture",
    "der kurze Text": "short text",
    "vergehen": "to pass (time)",
    "interessieren": "to interest",
    "die Ehe": "marriage",
    "die Hausfrau": "housewife",
    "der Hausmann": "househusband",
    "backen": "to bake",
    "der Kuchen": "cake",
    "das Zimmer": "room",
    "die Hand": "hand",
    "verreisen": "to travel (go away)",
    "der letzte Ausflug": "the last trip",
    "entlassen": "to dismiss / to fire",
    "das Feuer": "fire",
    "behalten": "to keep",
    "das Gas": "gas",
    "die Heizung": "heating",
    "heizen": "to heat",
    "der Werktag": "weekday (workday)",
    "der Export": "export",
    "der Strom": "electricity",
    "der Import": "import",
    "die Hektik": "hectic rush / stress",
    "die Frist": "deadline",
    "der Helfer": "helper",
    "die Helferin": "(female) helper",
    "der Notfall": "emergency",
    "das Handy": "mobile phone",
    "die Polizei": "police",
    "die Unterkunft": "accommodation",
    "das Einkaufszentrum": "shopping mall / shopping center",
    "verbringen": "to spend (time)",
    "träumen": "to dream",
    "die Lücke": "gap",
    "verzichten": "to do without / to give up",
    "das Mitleid": "pity",
    "das Beste": "the best",
    "modern": "modern",
    "funktionieren": "to work / to function",

    "das Sprichwort": "proverb",
    "die Erklärung": "explanation",
    "der Alkohol": "alcohol",
    "das Gold": "gold",
    "der Rat": "advice",
    "hereinkommen": "to come in",
    "brechen": "to break",
    "die Lebensphase": "phase of life",
    "das Berufsleben": "working life",
    "die Schulzeit": "time at school",
    "die Reihe": "row / series",
    "die Unterhaltung": "entertainment / conversation",
    "der Warenkorb": "shopping cart",
    "die Mehrwertsteuer": "VAT (value-added tax)",
    "die Gesellschaft": "society / company",
    "das Werk": "work (piece) / plant",
    "das Schloss": "castle / lock",
    "der König": "king",
    "die Königin": "queen",
    "die Vorwahl": "area code (phone)",
    "die Führung": "guided tour",
    "die Versandkosten": "shipping costs",
    "die Gebühr": "fee",
    "der Roman": "novel",
    "die Zahlungsart": "payment method",
    "der Bestseller": "bestseller",
    "die Überweisung": "bank transfer",
    "jährlich": "yearly / annually",
    "die Verfilmung": "film adaptation",
    "die Meldung": "report / message",
    "die Prominente": "celebrity",
    "der Nachrichtensprecher": "news anchor",
    "die Nachrichtensprecherin": "(female) news anchor",
    "das Festival": "festival",
    "der Hörer": "listener",
    "die Hörerin": "(female) listener",
    "der Hit": "hit (song)",
    "der Musikstil": "music genre",
    "der Einsatz": "effort / use",
    "die Stimme": "voice / vote",
    "die Stille": "silence",
    "rockig": "rocky / rock-style",
    "verschlafen": "sleepy / overslept",
    "der Sammler": "collector",
    "die Sammlerin": "(female) collector",
    "die Stimmung": "mood / atmosphere",
    "der Campingplatz": "campsite",
    "das Schnäppchen": "bargain",
    "die Übernachtung": "overnight stay",
    "die Verpflegung": "meals / catering",
    "der Wert": "value",
    "der Rucksack": "backpack",
    "das Ticket": "ticket",
    "der Kauf": "purchase",
    "der Stehplatz": "standing place / standing ticket",
    "der Sitzplatz": "seat",
    "das Quiz": "quiz",
    "die Malerei": "painting (art)",
    "der Titel": "title",
    "die Gewalt": "violence",
    "die Bedeutung": "meaning / importance",
    "der Ausblick": "view / outlook",
    "das Meer": "sea",
    "das Blatt": "leaf / sheet",
    "unendlich": "endless / infinite",
    "hübsch": "pretty",
    "abschließend": "finally / in conclusion",
    "abstrakt": "abstract",
    "erhalten": "to receive",
    "der Vordergrund": "foreground",
    "die Hauptrolle": "leading role",
    "der Hintergrund": "background",
    "der Wanderer": "hiker",
    "die Wanderin": "(female) hiker",
    "die Stelle": "position / place",
    "die Rückfrage": "follow-up question",
    "der Supermarkt": "supermarket",
    "abmalen": "to trace / copy (a drawing)",
    "erleben": "to experience",
    "der Trainer": "coach",
    "die Tätigkeit": "activity / job",
    "der Termin": "appointment",
    "beraten": "to advise",
    "der Beruf": "profession / job",
    "der Berufswunsch": "desired job / career wish",
    "der Ärger": "trouble / annoyance",
    "der Neuanfang": "new start",
    "die Bahn": "train / railway",
    "der Fahrplan": "timetable",
    "die Zugverbindung": "train connection",
    "die Durchsage": "announcement",
    "die Chance": "chance",
    "der Wagen": "carriage / car (train)",
    "die Geschäftsreise": "business trip",
    "der Schalter": "counter / switch",
    "die Umwelt": "environment",
    "die Hinfahrt": "trip there",
    "das Plastik": "plastic",
    "die Rückfahrt": "trip back",
    "zurückkommen": "to come back",
    "das Gehalt": "salary",
    "das Risiko": "risk",
    "die Klasse": "class",
    "die Übersetzerin": "translator",
    "die Fahrtkarte": "(travel) ticket",
    "der Chirurg": "surgeon",
    "die Oberärztin": "senior doctor",
    "der Leiter": "head / manager",
    "der Gang": "corridor / aisle",
    "der Lastwagen": "truck",
    "der Lkw": "truck (abbr.)",
    "das Stadtprogramm": "city programme",
    "die Ermäßigung": "discount",
    "die Freiheit": "freedom",
    "preiswert": "good value / inexpensive",
    "die Band": "band",
    "der Musiker": "musician",
    "das Telefonat": "phone call",
    "die Sängerin": "singer",
    "der Anrufer": "caller",
    "das Album": "album",
    "der Anrufbeantworter": "answering machine / voicemail",
    "sich konzentrieren": "to concentrate",
    "helfen": "to help",
    "lächeln": "to smile",
    "mobil": "mobile / flexible",
    "das Wissen": "knowledge",
    "die Kompetenz": "skills / competence",
    "hinterlassen": "to leave behind",
    "lebenslang": "lifelong",
    "die Hausarbeit": "housework",
    "zurückrufen": "to call back",
    "die moderne Arbeitswelt": "modern working world",
    "der Arbeitstag": "workday",
    "der Betrieb": "company / operation",
    "die Fabrik": "factory",
    "komisch": "strange / funny",
    "die Maschine": "machine",
    "der Roboter": "robot",
    "unnötig": "unnecessary",
    "die Digitalisierung": "digitalization",
    "virtuell": "virtual",
    "einige": "some / several",
    "das Bier": "beer",
    "zunehmen": "to gain weight / to increase",
    "der Schritt": "step",
    "der Austausch": "exchange",
    "der Feiertag": "public holiday",
    "das Jahrhundert": "century",
    "die Zusammenarbeit": "cooperation",
    "die Aushilfe": "temp worker",
    "das Verkehrsmittel": "means of transport",
    "die Gäste": "guests",
    "öffentlich": "public",
    "der Fahrer": "driver",
    "die Fahrerin": "(female) driver",
    "die Zutat": "ingredient",
    "transportieren": "to transport",
    "die Behörde": "authority / government office",
    "das Amt": "office / agency",
    "die Feuerwehr": "fire department",
    "die Sicherheit": "safety / security",
    "der Beamte": "civil servant",
    "die Beamtin": "(female) civil servant",
    "die Straßenreinigung": "street cleaning",
    "der Antrag": "application",
    "die Ordnung": "order",
    "der Müll": "trash / garbage",
    "die Müllabfuhr": "garbage collection",
    "die Einbürgerung": "naturalization",
    "die Mülltonne": "trash can",
    "das Dokument": "document",
    "die Mülltonnen": "trash cans",
    "der Personalausweis": "ID card",
    "die Stellenanzeige": "job ad",
    "sich bewerben": "to apply (for a job)",
    "der Pass": "passport",
    "die Unterlagen": "documents / paperwork",
    "die Kenntnis": "knowledge (specific)",
    "die Grenze": "border",
    "die Teilzeit": "part-time",
    "die Bezahlung": "payment / pay",
    "die Angestellte": "employee",
    "der Lohn": "wage",
    "der Bescheid": "official decision / notice",
    "der Betrag": "amount (of money)",
    "der Dom": "cathedral",
    "die Bankkarte": "bank card",
    "sperren": "to block / to lock",
    "der Kredit": "loan / credit",
    "der Gefallen": "favor",
    "die Geldbörse": "wallet",
    "leihen": "to lend / to borrow",
    "die Nächste": "the next one",
    "der Fan": "fan",
    "der Diebstahl": "theft",
    "der Daumen": "thumb",
    "die Daumen": "thumbs",
    "die Stadt-Tour": "city tour",
    "der Gedanke": "thought",
    "der Stadtplan": "city map",
    "die Ruhe": "peace / quiet",
    "der Tourist": "tourist",
    "die Touristin": "(female) tourist",
    "die Entspannung": "relaxation",
    "der Politiker": "politician",
    "die Politikerin": "(female) politician",
    "das Studium": "studies / degree course",
    "das Parlament": "parliament",
    "das Gesetz": "law",
    "die Verwaltung": "administration",
    "das Gebäude": "building",
    "das Wunder": "miracle",
    "der Monat": "month",
    "die Geburt": "birth",
    "die Laune": "mood",

    "die Liebe": "love",
    "die Geburtstagsparty": "birthday party",
    "der Schultag": "school day",
    "die Freude": "joy",
    "der Führerschein": "driver's license",
    "das Glück": "luck",
    "bestehen": "to pass (an exam)",
    "der Club": "club",
    "das Brautpaar": "wedding couple",
    "der Ring": "ring",
    "das Bedauern": "regret",
    "der Sieg": "victory",
    "die Medaille": "medal",
    "das Feuerwerk": "fireworks",
    "die Glückwunschkarte": "congratulation card",
    "die Karte": "card / ticket",
    "die Absage": "cancellation / rejection",
    "stehen": "to stand",
    "unglücklich": "unhappy",
    "das Gefühl": "feeling",
    "die Währung": "currency",
    "tauschen": "to exchange",
    "das Frühjahr": "spring (season)",
    "fallen": "to fall",
    "das Gegenteil": "opposite",
    "sich unterhalten": "to chat / talk",
    "das Wohnheim": "dormitory",
    "der Verkehr": "traffic",
    "die Party": "party",
    "anbieten": "to offer",
    "sprechen": "to speak",
    "bewundern": "to admire",
    "hilfsbereit": "helpful",
    "sich entscheiden": "to decide",
    "ordentlich": "tidy / proper",
    "weltweit": "worldwide",
    "unterrichten": "to teach",
    "wegfahren": "to drive off / leave",
    "die Einladung": "invitation",
    "die Hochzeit": "wedding",
    "der Vergleich": "comparison",
    "das Start-Up": "start-up",
    "die Studierende": "student",
    "privat": "private",
    "die Umfrage": "survey",
    "der Actionfilm": "action film",
    "der Fantasy-Film": "fantasy film",
    "die Komödie": "comedy",
    "der Liebesfilm": "romance film",
    "die Filmmusik": "soundtrack",
    "der Thriller": "thriller",
    "blöd": "stupid / silly",

    "der E-Book-Reader": "e-book reader",
    "das Smartphone": "smartphone",
    "die Spielekonsole": "game console",
    "der Bildschirm": "screen",
    "der Lautsprecher": "speaker",
    "das E-Book": "e-book",
    "der Laptop": "laptop",
    "das Radio": "radio",
    "das Tablet": "tablet",
    "die Tastatur": "keyboard",
    "die Webseite": "website",
    "der Kontakt": "contact",
    "das Kabel": "cable",
    "der Link": "link",
    "nah": "near",
    "näher": "nearer / closer",
    "am nächsten": "closest / next",
    "die Freundschaft": "friendship",
    "die Sorge": "worry / concern",
    "die Enkelin": "granddaughter",
    "die Kindheit": "childhood",
    "überhaupt": "at all / anyway",
    "das Schicksal": "fate",
    "mancher": "some / many a",
    "fröhlich": "cheerful",
    "schwierig": "difficult",
    "vorsichtig": "careful",
    "der Enkel": "grandson",
    "das Tier": "animal",
    "plötzlich": "suddenly",
    "unbedingt": "definitely",
    "tot": "dead",
    "zuletzt": "finally / last",
    "die Buchstaben": "letters",
    "die Hauptperson": "main character",
    "die Handlung": "plot / story",
    "dumm": "dumb",
    "dümmer": "dumber",
    "der Humor": "humor",
    "der Trailer": "trailer (film)",
    "das Talent": "talent",
    "der Witz": "joke",
    "gewinnen": "to win",
    "verlieren": "to lose",

    "der Berg": "mountain",
    "die Familie": "family",
    "die Bank": "bank",
    "bitten": "to ask (for) / to request",
    "sich ausruhen": "to rest",
    "entscheiden": "to decide",

    "die gute Zugverbindung": "good train connection",
    "die Einladung": "invitation",
    "die Mail": "email",
    "das Foto": "photo",
    "real": "real",

    "der Hotelkaufmann": "hotel clerk (male)",
    "die Hotelkauffrau": "hotel clerk (female)",
    "die Krankenschwester": "nurse",
    "der Krankenpfleger": "nurse (male)",
    "die Auszubildende": "trainee / apprentice",
    "die Berufserfahrung": "work experience",
    "die Arztpraxis": "doctor's office",
    "die Grundschule": "primary school",
    "die Hauptschule": "secondary school (Hauptschule)",
    "die Gesamtschule": "comprehensive school",
    "die Realschule": "secondary school (Realschule)",
    "die Berufsschule": "vocational school",
    "das Schulsystem": "school system",
    "das Bundesland": "federal state",
    "die Arzthelferin": "medical assistant",
    "das Gymnasium": "grammar school (Gymnasium)",
    "der Altenpfleger": "geriatric nurse",
    "der Englischlehrer": "English teacher",
    "die Arbeitswelt": "working world",
    "die Erfahrung": "experience",
    "das Handwerk": "skilled trade / craft",
    "die Werbeagentur": "advertising agency",
    "das Reisebüro": "travel agency",
    "die AG": "club / working group (AG)",
    "das Au-pair": "au pair",
    "der Grafiker": "graphic designer",
    "der Azubi": "trainee (Azubi)",
    "die Lehre": "apprenticeship",
    "die Messe": "trade fair",
    "der Schulabschluss": "school-leaving qualification",
    "der Abschluss": "graduation / qualification",
    "die Direktorin": "principal",
    "der Direktor": "principal (male)",
    "die Schülerin": "pupil / student (female)",
    "der Schüler": "pupil / student (male)",
    "der Klasse": "class (dative/genitive form)",
    "das Klassenzimmer": "classroom",
    "die Unterrichtszeit": "lesson time",
    "die Cafeteria": "cafeteria",
    "der Stundenplan": "timetable",
    "die Fremdsprache": "foreign language",
    "die Klassenfahrt": "class trip",
    "die Schuluniform": "school uniform",
    "die Vorbereitung": "preparation",
    "der Schulweg": "way to school",
    "der Vokabeltest": "vocabulary test",
    "das Abitur": "Abitur (school-leaving exam)",
    "das Zeugnis": "certificate / report card",
    "die Dauer": "duration",
    "die Ferien": "holidays / vacation",
    "das Fach": "school subject",

    "einhunderteins": "one hundred and one (101)",
    "achtundachtzig": "eighty-eight (88)",
    "ausschlafen": "to sleep in",

    "die Grafik": "graphic",
    "die Behinderung": "disability",
    "der Rollstuhl": "wheelchair",
    "die Erholung": "recovery / relaxation",
    "die Erinnerung": "memory",
    "die Weltreise": "world trip",
    "erwachsen": "adult / grown-up",
    "unabhängig": "independent",
    "sozial": "social",

    "die Vorlesung": "lecture",
    "die Gemeinsamkeit": "similarity / common point",
    "die Hauptsache": "main thing",
    "der Unterschied": "difference",
    "zustimmen": "to agree",
    "überraschen": "to surprise",
    "wenigstens": "at least",
    "teilnehmen": "to take part",
    "liegen": "to lie / be located",
    "empfangen": "to receive / welcome",
    "der Platz": "place / seat",
    "der Plan": "plan",

    "anmelden": "to register / sign up",
    "der Flohmarkt": "flea market",
    "das Sofa": "sofa",
    "der Aufenthalt": "stay",
    "die Reservierung": "reservation",
    "spätestens": "at the latest",
    "der Verein": "club / association",
    "absagen": "to cancel",
    "zusagen": "to accept / confirm",
    "gemeinsam": "together",
    "organisieren": "to organize",
    "der Eingang": "entrance",
    "informieren": "to inform",
    "weiterhelfen": "to help further",
    "die Zigarette": "cigarette",
    "das WC": "toilet",
    "bitter": "bitter",
    "salzig": "salty",
    "sauer": "sour",
    "scharf": "spicy / sharp",

    "abschließen": "to lock / to finish",
    "die Rentnerin": "(female) retiree",
    "der Rentner": "retiree",
    "die Ausbildung": "training / apprenticeship",
    "geboren": "born",
    "geschieden": "divorced",
    "die Überstunde": "overtime hour",
    "der Augenoptiker": "optician",
    "die Bankkauffrau": "bank clerk",
    "das Stadtzentrum": "city center",
    "das Land": "country / countryside",
    "vor": "before / in front of",
    "zusammenleben": "to live together",
    "die Note": "grade / mark",
    "weitersuchen": "to keep looking",
    "das Apartment": "apartment",
    "wohnen": "to live (reside)",
    "die Sprache": "language",
    "fließend": "fluent",
    "die Kollegen": "colleagues",
    "die Angst": "fear",
    "die Sätze": "sentences",
    "der Gegenstand": "object",
    "der Sinn": "meaning / sense",
    "der Bruder": "brother",
    "fast": "almost",

    "das Visum": "visa",

    "sein": "to be",
    "fahren": "to drive / go",
    "fliegen": "to fly",
    "gehen": "to go / walk",
    "kommen": "to come",
    "halten": "to hold / stop",
    "empfangen": "to receive / welcome",
    "schlafen": "to sleep",
    "sterben": "to die",
    "schlagen": "to hit / beat",
    "rufen": "to call",
    "sprechen": "to speak",

    "herunterladen": "to download",
    "hochladen": "to upload",
    "wegwerfen": "to throw away",
    "abgeben": "to hand in / give away",
    "ausgeben": "to spend (money)",
    "hergeben": "to hand over",
    "mithelfen": "to help (out)",
    "einziehen": "to move in",
    "weglaufen": "to run away",
    "vorkommen": "to happen / occur",
    "verschieben": "to postpone",
    "unternehmen": "to do / undertake",
    "vorschlagen": "to suggest",
    "zurückgeben": "to give back / return",
    "ausfallen": "to be cancelled / to break down",
    "auffallen": "to stand out / be noticeable",
    "sich benehmen": "to behave",

    "knapp": "just / barely",
    "kostenlos": "free of charge",
    "dringend": "urgent",
    "genervt": "annoyed",
    "stolz": "proud",
    "sympathisch": "likeable",
    "modisch": "fashionable",
    "neutral": "neutral",
    "inklusive": "including",
    "nirgends": "nowhere",
    "fremd": "foreign / strange",
    "wahr": "true",
    "ausgesprochen": "pronounced / very",

    "die andere Währung": "other currency",
    "die Gärtnerin": "gardener",
    "die Uhr": "clock / watch",

    "versprechen": "to promise",
    "bieten": "to offer",
    "bleiben": "to stay",
    "nehmen": "to take",
    "geben": "to give",
    "kennen": "to know (a person/place)",
    "hängen": "to hang",
    "stinken": "to stink",
    "tragen": "to carry / to wear",

    "treu": "loyal",
}

SEPARABLE_PREFIXES = (
    "ab",
    "an",
    "auf",
    "aus",
    "ein",
    "fest",
    "her",
    "hin",
    "hoch",
    "los",
    "mit",
    "nach",
    "vor",
    "weg",
    "weiter",
    "zurück",
    "zusammen",
    "zu",
)


def guess_plural(noun: str) -> str:
    """Best-effort plural guess (only used when we don't have an override)."""
    if noun in PLURAL_OVERRIDES:
        return PLURAL_OVERRIDES[noun]

    # some common patterns
    if noun.endswith("ung"):
        return noun + "en"
    if noun.endswith(("heit", "keit", "schaft")):
        return noun + "en"
    if noun.endswith(("tion", "sion")):
        return noun + "en"
    if noun.endswith("tät"):
        return noun + "en"
    if noun.endswith("e"):
        return noun + "n"
    if noun.endswith("chen") or noun.endswith("lein"):
        return noun
    if noun.endswith("er"):
        return noun
    if noun.endswith("el"):
        return noun
    if noun.endswith("um"):
        return noun[:-2] + "en"
    # fallback
    return noun + "e"


def noun_info(gender: str, noun: str) -> str:
    pl = guess_plural(noun)
    if pl == "-":
        return f"Nomen ({gender}); meist ohne Plural."
    return f"Nomen ({gender}); Plural: {pl}."


def is_separable_verb(v: str) -> bool:
    return any(v.startswith(pref) and len(v) > len(pref) + 2 for pref in SEPARABLE_PREFIXES)


def verb_info(v: str) -> str:
    if is_separable_verb(v):
        return f"Verb (trennbar): {v}."
    return f"Verb: {v}."


def default_example_for(row: Row) -> str:
    g = row.german
    if g.startswith(("der ", "die ", "das ")):
        return f"Das ist {g}."
    if g.endswith(" sein"):
        return "Ich bin einverstanden."
    if re.match(r"^[a-zäöüß].*en$", g) or g in {"sollen"}:
        return f"Ich will {g}."
    if re.match(r"^[a-zäöüß].*", g):
        return f"Heute ist es {g}."
    # phrase/sentence
    return g


def translate_simple(g: str) -> Row | None:
    key = norm_key(g)

    if key in PHRASE_OVERRIDES:
        return PHRASE_OVERRIDES[key]

    # Skip bare articles/particles
    if key in {"die", "der", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer"}:
        return None

    # obvious truncations / useless fragments
    if key in {"sich aus", "au", "mi", "en", "der/", "th", "pr"}:
        return None

    # Drop nonsense artifacts
    if g.strip() in {"", "*", "-"}:
        return None

    # Remove leading list hyphen markers
    if g.startswith("-"):
        g2 = g.lstrip("-").strip()
        g = g2

    # Apply lemma overrides (case/article normalization)
    lemma_key = norm_key(g)
    if lemma_key in LEMMA_OVERRIDES:
        g = LEMMA_OVERRIDES[lemma_key]

    # normalize double 'die'
    g = re.sub(r"^die\s+die\s+", "die ", g, flags=re.I)

    # If still starts with ein/eine/einen/einem/einer, keep as phrase (gender unclear), but try override.
    if re.match(r"^(ein|eine|einen|einem|einer)\b", g, flags=re.I):
        # Without override we skip: it's usually a case-form item.
        return None

    # Base english
    english = EN_OVERRIDES.get(g)

    # If not found, try some lightweight cognate guesses
    if english is None:
        bare = re.sub(r"^(der|die|das)\s+", "", g)
        if bare.endswith("tion"):
            english = bare[:-4] + "tion"
        elif bare.endswith("tät"):
            english = bare[:-3] + "ity"
        elif bare.endswith("ität"):
            english = bare[:-4] + "ity"
        elif bare.endswith("ismus"):
            english = bare[:-5] + "ism"
        elif bare.lower() in {"job", "poster", "disco", "konto", "formular"}:
            english = bare.lower()

    # If still unknown, skip.
    if english is None:
        return None

    # Build info
    info = ""
    if g.startswith("der "):
        noun = g[4:]
        info = noun_info("m", noun)
    elif g.startswith("die "):
        noun = g[4:]
        info = noun_info("f", noun)
    elif g.startswith("das "):
        noun = g[4:]
        info = noun_info("n", noun)
    else:
        # verb/adj/adv/phrase
        if re.match(r"^[a-zäöüß].*en$", g) or g in {"sollen"}:
            info = verb_info(g)
        else:
            info = "Wort/Redemittel."

    row = Row(german=g, english=english, example_de="", info=info)
    ex = default_example_for(row)
    row = Row(german=row.german, english=row.english, example_de=ex, info=row.info)
    return row


def split_combined(text: str) -> list[str]:
    """Split some OCR-combined entries into separate items."""
    t = text.strip()
    if not t:
        return []

    # explicit dot split
    if "." in t:
        parts = [p.strip() for p in re.split(r"[.!?]+", t) if p.strip()]
        t = " | ".join(parts)

    # If we inserted separators, split those.
    if "|" in t:
        return [p.strip() for p in t.split("|") if p.strip()]

    # split by repeated articles (der/die/das/den/dem/des/ein...)
    art = r"(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer)"
    matches = list(re.finditer(rf"\b{art}\b", t, flags=re.I))
    if len(matches) <= 1:
        # some known combined patterns without articles
        cf = t.casefold()
        if cf == "gossen gespannt":
            return ["gießen", "gespannt"]
        if cf == "füttern zumindest":
            return ["füttern", "zumindest"]
        if cf.endswith("interessieren") and "vergeht" in cf:
            return ["vergehen", "interessieren"]

        # spaced separable-verb spellings
        if cf in {"herein kommen", "kommt herein"}:
            return ["hereinkommen"]
        if cf in {"zurück kommen", "kommt zurück"}:
            return ["zurückkommen"]

        # trim obvious OCR tails
        if re.search(r"\bde$", cf) and len(cf.split()) == 2:
            return [t.rsplit(" ", 1)[0]]

        # split short lists of adjectives/adverbs/verbs (all lowercase tokens)
        tokens = t.split()
        fixed_phrases = {
            "unter anderem",
            "also gut",
            "auf keinen fall",
            "fließend sprechen",
            "schlecht gelaunt sein",
            "einverstanden sein",
            "am nächsten",
        }
        if cf in fixed_phrases:
            return [t]

        # keep reflexive verbs together
        if len(tokens) == 2 and tokens[0].casefold() == "sich":
            return ["sich " + tokens[1]]

        # common separable-verb pairs in the OCR data (conjugated form + particle)
        pair_map = {
            "lädt herunter": "herunterladen",
            "lädt hoch": "hochladen",
            "fliegt ab": "abfliegen",
            "fährt weg": "wegfahren",
            "ruft zurück": "zurückrufen",
            "zieht ein": "einziehen",
            "wirft weg": "wegwerfen",
            "gibt ab": "abgeben",
            "gibt aus": "ausgeben",
            "gibt her": "hergeben",
            "hilft mit": "mithelfen",
            "läuft lang": "langlaufen",
            "fällt aus": "ausfallen",
            "fällt auf": "auffallen",
        }
        if len(tokens) == 2:
            pair = " ".join(tok.casefold() for tok in tokens)
            if pair in pair_map:
                return [pair_map[pair]]
        if len(tokens) == 3 and tokens[0].casefold() in {"er", "sie", "es", "ich", "wir", "ihr"}:
            pair = " ".join(tok.casefold() for tok in tokens[1:])
            if pair in pair_map:
                return [pair_map[pair]]

        articles = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer"}
        if (
            len(tokens) > 1
            and all(re.fullmatch(r"[a-zäöüß-]+", tok.casefold()) for tok in tokens)
            and not any(tok.casefold() in articles for tok in tokens)
        ):
            # common OCR split: "sich aus ruhen" -> ausruhen
            if cf.startswith("sich aus ruhen"):
                return ["sich ausruhen"]
            return [
                tok
                for tok in tokens
                if tok.casefold()
                not in {
                    "niemand",
                    "uns",
                    "über",
                    "unsere",
                    "inzwischen",
                    "er",
                    "sie",
                    "es",
                    "ich",
                    "wir",
                    "ihr",
                    "hat",
                    "ist",
                }
            ]

        return [t]

    # keep as a whole if it looks like a normal noun phrase with adjective
    if t.lower().startswith("eine gute "):
        return [t]

    parts: list[str] = []
    starts = [m.start() for m in matches]
    for a, b in zip(starts, starts[1:] + [len(t)]):
        parts.append(t[a:b].strip())
    # Sometimes the first chunk is missing start (if article at pos 0, ok). If not, keep leading too.
    if starts and starts[0] != 0:
        parts.insert(0, t[: starts[0]].strip())

    # filter empties
    parts = [p for p in parts if p]
    return parts


def read_progress() -> int:
    try:
        return int(PROGRESS_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        return 1


def write_progress(n: int) -> None:
    PROGRESS_PATH.write_text(str(n) + "\n", encoding="utf-8")


def load_existing() -> tuple[int, set[str]]:
    existing = set()
    max_sn = 0
    with OUT_PATH.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                max_sn = max(max_sn, int(row["sn"]))
            except Exception:
                pass
            existing.add(norm_key(row["german"]))
    return max_sn, existing


def iter_source(start_idx: int) -> Iterable[tuple[int, str]]:
    with SRC_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                idx_s, text = line.split("\t", 1)
                idx = int(idx_s)
            except ValueError:
                continue
            if idx < start_idx:
                continue
            yield idx, text.strip()


def append_rows(rows: list[Row]) -> int:
    if not rows:
        return 0

    max_sn, existing = load_existing()
    appended = 0

    with OUT_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            k = norm_key(r.german)
            if k in existing:
                continue
            max_sn += 1
            w.writerow([max_sn, r.german, r.english, r.example_de, r.info])
            existing.add(k)
            appended += 1

    return appended


def main() -> None:
    start = read_progress()

    max_src = 0
    batch: list[Row] = []

    # track unknowns for iterative improvement
    unknown: list[str] = []
    skipped = 0

    _, existing = load_existing()

    for idx, raw in iter_source(start):
        max_src = max(max_src, idx)
        for piece in split_combined(raw):
            row = translate_simple(piece)
            if row is None:
                skipped += 1
                # Only log if it's not already present (dedupe)
                if norm_key(piece) not in existing:
                    unknown.append(piece)
                continue
            if norm_key(row.german) in existing:
                continue
            batch.append(row)

    appended = append_rows(batch)

    # Write unknowns list for reference
    unk_path = ROOT / "unknown_remaining.txt"
    # de-dup while preserving order
    seen = set()
    unk_unique: list[str] = []
    for u in unknown:
        k = norm_key(u)
        if k in seen:
            continue
        seen.add(k)
        unk_unique.append(u)

    unk_path.write_text("\n".join(unk_unique) + ("\n" if unk_unique else ""), encoding="utf-8")

    # Only advance progress marker when we've fully covered the source list.
    # During iterative improvement runs, keep progress unchanged so reruns can fill gaps.
    if max_src and not unk_unique:
        write_progress(max_src + 1)

    # Print summary for CLI use
    total_rows = sum(1 for _ in OUT_PATH.open(encoding="utf-8")) - 1
    print(f"Appended: {appended}")
    print(f"Total rows (excluding header): {total_rows}")
    print(f"Skipped (raw pieces): {skipped}")
    print(f"Unknown remaining written to: {unk_path} ({len(unk_unique)} items)")


if __name__ == "__main__":
    main()
