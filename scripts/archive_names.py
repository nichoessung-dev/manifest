# -*- coding: utf-8 -*-
"""Names for the Archive import (scripts/import_archive.py, scripts/archive_photos.py): brand detection, the
house-style title, colours, the "model words" the duplicate check compares and a category guess from a name.

House style, as the catalogue writes its 15,000 titles (catalog_ai.py, import_friend.py): "Brand Model Item Colour",
2 to 7 words, Title Case, the brand spelled as the catalogue spells it, never the words replica, fake, rep, 1:1 or a
seller code, no dashes as punctuation (hyphens inside a word such as T-Shirt are fine).
Brands: the catalogue's own brand list (its most common spelling of each), BRAND_ALIAS from clean_catalog.py, the
nicknames below (YSL, LV, TNF ...) and a few brands of the sheet the catalogue does not have yet. The brand is the
earliest one named in the sheet's name (the longest when two start at the same word).
"""
import collections, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_common import ROOT, COLOURS, load_catalog  # noqa: E402

BANNED = r"replicas?|reps?|fake|1\s*:\s*1|batch|best quality|top quality|high quality|quelity|god version|ljr|pk|og batch"
FILLER = {"new", "best", "batch", "quality", "version", "the", "and", "with", "for", "of", "men", "mens", "man",
          "women", "womens", "woman", "ladies", "unisex", "official", "original", "premium", "edition", "style",
          "styles", "collection", "many", "colors", "colours", "color", "colour", "all", "models", "model", "etc",
          "hot", "cool", "sale", "full", "set", "pcs", "pairs", "pair", "pack", "x", "in", "on", "a", "an", "by",
          "fashion", "classic", "luxury", "designer", "assortment", "options", "option", "available", "multiple",
          "various", "selection", "real", "authentic", "genuine", "custom", "limited"}
# words a title never keeps (catalog_ai.py: no seller words, no Men's / Women's); small words such as "in", "of" and
# "the" stay ("Peace in War", "Lord of the Rings")
TITLE_DROP = {"best", "batch", "quality", "version", "men", "mens", "men's", "man", "women", "womens", "women's",
              "woman", "ladies", "unisex", "official", "original", "premium", "hot", "sale", "etc", "pcs", "budget",
              "cheap", "assortment", "options", "available", "various", "selection", "authentic", "genuine", "colorways",
              "colourways", "colorway", "colourway", "styles", "fashion"}
CAPS = {"sb", "ma1", "ss", "fw", "aw", "usa", "uk", "nyc", "la", "ny", "psg", "nba", "nfl", "mlb", "cdg", "mm6", "tnf",
        "lv", "gg", "erd", "rl", "bv", "ysl", "nfs", "jbl", "gta", "ai", "ap", "f1", "gt", "amg", "bmw", "uvu", "vvs",
        "ii", "iii", "iv", "btd", "ym", "csgo", "dj", "mlb", "ac", "bb", "tn", "sk8"}
TYPO = {"cordoy": "Corduroy", "gray": "Grey", "fleace": "Fleece", "jewelery": "Jewelry", "sweather": "Sweater", "corduroy": "Corduroy", "venetta": "Veneta", "buerberry": "Burberry", "fotball": "Football",
        "fotbal": "Football", "vaccum": "Vacuum", "disstressed": "Distressed", "backpacs": "Backpacks", "bots": "Boots",
        "scarfs": "Scarves", "quelity": "Quality", "longsleeve": "Long Sleeve", "longsleeves": "Long Sleeves",
        "tshirt": "T-Shirt", "tshirts": "T-Shirt", "t-shirt": "T-Shirt", "t-shirts": "T-Shirt", "zip-up": "Zip-Up",
        "zipup": "Zip-Up", "hoody": "Hoodie", "playbutton": "Play Button", "ashtrays": "Ashtrays", "ash": "Ash"}
# nicknames and spellings -> the catalogue's brand (folded keys, see fold())
ALIAS = {"ysl": "Saint Laurent", "yves saint laurent": "Saint Laurent", "saint laurent paris": "Saint Laurent",
         "lv": "Louis Vuitton", "rl": "Ralph Lauren", "polo ralph lauren": "Ralph Lauren", "tnf": "The North Face",
         "north face": "The North Face", "nb": "New Balance", "cdg": "Comme des Garcons", "margiela": "Maison Margiela",
         "mm6": "MM6 Maison Margiela", "bv": "Bottega Veneta", "bottega": "Bottega Veneta",
         "bottega venetta": "Bottega Veneta", "arcteryx": "Arc'teryx", "arc teryx": "Arc'teryx", "a bathing ape": "Bape",
         "off white": "Off-White", "offwhite": "Off-White", "fear of god essentials": "Essentials",
         "fog essentials": "Essentials", "air jordan": "Jordan", "ggdb": "Golden Goose", "birks": "Birkenstock",
         "buerberry": "Burberry", "nfs": "No Faith Studios", "acne": "Acne Studios", "van cleef": "Van Cleef & Arpels",
         "ap": "Audemars Piguet", "erd": "Enfants Riches Déprimés", "e r d": "Enfants Riches Déprimés", "gallery dept": "Gallery Dept",
         "c p company": "CP Company", "cp company": "CP Company", "hermes": "Hermes", "lulu": "Lululemon",
         "alo": "Alo Yoga", "dsquared": "Dsquared2", "d g": "Dolce & Gabbana", "mcqueen": "Alexander McQueen",
         "chrome heart": "Chrome Hearts", "stussy": "Stussy", "gymshark": "Gymshark", "young la": "YoungLA",
         "youngla": "YoungLA", "rimowa": "Rimowa", "loro piana": "Loro Piana", "evisu": "Evisu", "ugg": "UGG",
         "uggs": "UGG", "experiment five": "Experiment Five", "union kingdom": "Union Kingdom",
         "sp5der": "Sp5der", "spider worldwide": "Sp5der", "chanel": "Chanel", "dior homme": "Dior",
         "christian dior": "Dior", "louis vuitton": "Louis Vuitton", "goyard": "Goyard", "kaws": "Kaws",
         "murakami": "Takashi Murakami", "takashi murakami": "Takashi Murakami", "pokemon": "Pokemon",
         "masion margiela": "Maison Margiela", "maison margiela": "Maison Margiela", "lululemon": "Lululemon",
         "the north face": "The North Face", "new balance": "New Balance", "stone island": "Stone Island",
         # spellings of the sheet (26 Nov 2026)
         "christian loubutin": "Christian Louboutin", "loubutin": "Christian Louboutin", "carhatt": "Carhartt",
         "cathart": "Carhartt", "carhatt wip": "Carhartt", "number n ine": "Number Nine", "number nine": "Number Nine",
         "dsquared 2": "Dsquared2", "company": "CP Company", "cb": "Cole Buxton"}
# brands of the sheet the catalogue does not have yet (one spelling each)
EXTRA = ["Havaianas", "Swatch", "Creed", "Our Legacy", "Wales Bonner", "YoungLA", "Satisfy", "Whoop", "Logitech",
         "Harman Kardon", "Funko", "Hot Wheels", "Shinzo", "Menes", "Velour Garments", "Trendt Vision", "Brain Dead",
         "Dover Street Market", "Isabel Marant", "Glock", "Ray-Ban", "Meta", "Bearbrick", "Labubu", "Starbucks",
         "Maybach", "Mutimer", "Discont'd", "Berlinc", "CirrusMesh", "Parasite", "Mastermind", "Apple", "Nintendo",
         "Sony", "Samsung", "Marshall", "Beats", "JBL", "Dyson", "Stanley", "Loewe", "Miu Miu", "Celine", "Swarovski",
         "Golden Goose", "Timberland", "Birkenstock", "Hoka", "On", "Salomon", "Asics", "Puma", "Diesel", "Erd"]
NOT_BRAND = {"on": r"\bon\s+(cloud|running|cloudmonster|cloudtilt)\b"}   # "On" only for the running shoes
# product words that name their brand; the word itself stays in the title ("Apple Airpods Max", "Adidas Samba")
PRODUCT_BRAND = [(r"\b(airpods?|iphone|ipad|macbook|apple watch|magsafe)\b", "Apple"), (r"\b(ps5|playstation|psp)\b", "Sony"),
                 (r"\bgalaxy\b", "Samsung"), (r"\b(dunks?|air force|af1|air max|tech fleece|nike tech)\b", "Nike"),
                 (r"\b(sambas?|gazelles?|superstars?|campus|spezia|adizero|adiracer)\b", "Adidas"),
                 (r"\b(gats|tabi)\b", "Maison Margiela"), (r"\b(b22|b23|b30)\b", "Dior"),
                 (r"\b(3xl|triple s|track runner)\b", "Balenciaga"), (r"\bspeedcat\b", "Puma"), (r"\bnintendo\b", "Nintendo")]
SINGULAR = {"hoodies": "Hoodie", "sweaters": "Sweater", "t-shirts": "T-Shirt", "tees": "Tee", "sambas": "Samba",
            "superstars": "Superstar", "gazelles": "Gazelle", "belts": "Belt", "wallets": "Wallet", "rings": "Ring",
            "necklaces": "Necklace", "bracelets": "Bracelet", "jerseys": "Jersey", "jackets": "Jacket", "caps": "Cap",
            "hats": "Hat", "beanies": "Beanie", "bags": "Bag", "henleys": "Henley", "scarves": "Scarf", "scarfs": "Scarf",
            "pillows": "Pillow", "rugs": "Rug", "carpets": "Carpet", "sets": "Set", "knits": "Knit",
            "sweatshirts": "Sweatshirt", "crewnecks": "Crewneck", "cardigans": "Cardigan", "polos": "Polo",
            "shirts": "Shirt", "vests": "Vest", "coats": "Coat", "puffers": "Puffer", "parkas": "Parka",
            "windbreakers": "Windbreaker", "tracksuits": "Tracksuit", "tops": "Top", "tanks": "Tank", "singlets": "Singlet",
            "pendants": "Pendant", "cases": "Case", "mats": "Mat", "cups": "Cup", "trays": "Tray", "figures": "Figure",
            "headbands": "Headband", "dresses": "Dress", "skirts": "Skirt", "jorts": "Jorts", "boxers": "Boxers"}
COLOUR_ZH = [("藏青", "Navy"), ("藏蓝", "Navy"), ("深蓝", "Navy"), ("宝蓝", "Royal Blue"), ("天蓝", "Light Blue"),
             ("浅蓝", "Light Blue"), ("雾霾蓝", "Light Blue"), ("军绿", "Olive"), ("墨绿", "Dark Green"), ("深绿", "Dark Green"),
             ("浅绿", "Light Green"), ("酒红", "Burgundy"), ("枣红", "Burgundy"), ("卡其", "Khaki"), ("咖啡", "Brown"),
             ("深灰", "Dark Grey"), ("浅灰", "Light Grey"), ("花灰", "Grey"), ("米白", "Off White"), ("奶白", "Cream"),
             ("杏", "Apricot"), ("米", "Beige"), ("黑", "Black"), ("白", "White"), ("灰", "Grey"), ("红", "Red"),
             ("蓝", "Blue"), ("绿", "Green"), ("黄", "Yellow"), ("粉", "Pink"), ("紫", "Purple"), ("棕", "Brown"),
             ("咖", "Brown"), ("驼", "Camel"), ("橙", "Orange"), ("橘", "Orange"), ("银", "Silver"), ("金", "Gold"),
             ("彩", "Multicolour"), ("迷彩", "Camo")]
COLOUR_EN = {"black": "Black", "white": "White", "grey": "Grey", "gray": "Grey", "navy": "Navy", "blue": "Blue",
             "light blue": "Light Blue", "dark blue": "Navy", "baby blue": "Light Blue", "sky blue": "Light Blue",
             "royal blue": "Royal Blue", "red": "Red", "burgundy": "Burgundy", "maroon": "Burgundy",
             "pink": "Pink", "purple": "Purple", "lilac": "Lilac", "green": "Green", "olive": "Olive", "khaki": "Khaki",
             "army green": "Olive", "dark green": "Dark Green", "mint": "Mint", "yellow": "Yellow", "orange": "Orange",
             "brown": "Brown", "dark brown": "Brown", "tan": "Tan", "beige": "Beige", "cream": "Cream",
             "off-white": "Off White", "off white": "Off White", "ivory": "Cream", "camel": "Camel", "sand": "Sand",
             "silver": "Silver", "gold": "Gold", "golden": "Gold", "multicolour": "Multicolour", "multicolor": "Multicolour",
             "charcoal": "Charcoal", "teal": "Teal", "turquoise": "Turquoise", "coffee": "Brown", "apricot": "Apricot",
             "neon green": "Neon Green", "light grey": "Light Grey", "dark grey": "Dark Grey",
             "light green": "Light Green", "camo": "Camo", "denim": "", "blonde": "Beige"}
# item words from a Chinese listing title, for a sheet name without one (first match wins, longest words first)
ITEM_ZH = [("羽绒服", "Down Jacket"), ("羽绒马甲", "Down Vest"), ("冲锋衣", "Shell Jacket"), ("棉服", "Padded Jacket"),
           ("夹克", "Jacket"), ("外套", "Jacket"), ("大衣", "Coat"), ("风衣", "Trench Coat"), ("马甲", "Vest"),
           ("连帽卫衣", "Hoodie"), ("拉链卫衣", "Zip Hoodie"), ("卫衣", "Sweatshirt"), ("毛衣", "Sweater"), ("针织衫", "Knit Sweater"),
           ("开衫", "Cardigan"), ("衬衫", "Shirt"), ("衬衣", "Shirt"), ("polo", "Polo"), ("长袖", "Long Sleeve"),
           ("短袖", "T-Shirt"), ("t恤", "T-Shirt"), ("背心", "Tank Top"), ("套装", "Set"), ("牛仔裤", "Jeans"),
           ("短裤", "Shorts"), ("卫裤", "Sweatpants"), ("运动裤", "Track Pants"), ("工装裤", "Cargo Pants"), ("裤", "Pants"),
           ("连衣裙", "Dress"), ("半身裙", "Skirt"), ("裙", "Skirt"), ("运动鞋", "Sneakers"), ("板鞋", "Sneakers"),
           ("跑鞋", "Running Shoes"), ("拖鞋", "Slides"), ("凉鞋", "Sandals"), ("靴", "Boots"), ("乐福", "Loafers"),
           ("鞋", "Shoes"), ("双肩包", "Backpack"), ("斜挎包", "Crossbody Bag"), ("手提包", "Handbag"), ("钱包", "Wallet"),
           ("卡包", "Card Holder"), ("包", "Bag"), ("鸭舌帽", "Cap"), ("棒球帽", "Cap"), ("毛线帽", "Beanie"), ("渔夫帽", "Bucket Hat"),
           ("发箍", "Headband"), ("发带", "Headband"), ("帽", "Hat"), ("围巾", "Scarf"), ("手套", "Gloves"), ("袜", "Socks"),
           ("内裤", "Underwear"), ("腰带", "Belt"), ("皮带", "Belt"), ("项链", "Necklace"), ("手链", "Bracelet"),
           ("手镯", "Bracelet"), ("戒指", "Ring"), ("耳环", "Earrings"), ("耳钉", "Earrings"), ("墨镜", "Sunglasses"),
           ("太阳镜", "Sunglasses"), ("眼镜", "Glasses"), ("手表", "Watch"), ("香水", "Perfume"), ("地毯", "Rug"),
           ("抱枕", "Pillow"), ("手机壳", "Phone Case")]
ITEM_WORDS = re.compile(r"(?i)\b(t-?shirts?|tees?|long ?sleeves?|polos?|shirts?|hoodies?|zip-?ups?|zip hoodie|sweaters?|"
                        r"sweatshirts?|crewnecks?|cardigans?|knits?|jerseys?|tank tops?|tanks?|tops?|henleys?|tracksuits?|"
                        r"sets?|jackets?|puffers?|parkas?|coats?|windbreakers?|vests?|gilets?|fleece|bombers?|peacoats?|"
                        r"overshirts?|jeans|pants|trousers|joggers?|sweatpants|cargos?|leggings?|shorts|jorts|sneakers?|"
                        r"shoes?|trainers?|boots?|loafers?|slides?|sandals?|slippers?|clogs?|mules?|runners?|flip ?flops?|"
                        r"bags?|backpacks?|totes?|wallets?|card ?holders?|caps?|hats?|beanies?|belts?|watch(es)?|"
                        r"necklaces?|bracelets?|rings?|earrings?|sunglasses|glasses|socks?|scarf|scarves|gloves?|"
                        r"underwear|boxers?|perfume|cologne|dress(es)?|skirts?|rugs?|carpets?|pillows?|cases?|"
                        r"headbands?|hair ?bands?|singlets?|denim|knits?)\b")
_vocab, _new = {}, set()


def fold(s):
    """Lower case, accents off, '&' and punctuation to spaces: the key brands and words are compared by."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = s.replace("'", "").replace("’", "").replace(".", " ")
    return re.sub(r"[^a-z0-9+]+", " ", s).strip()


def vocab():
    """{folded brand or alias: catalogue spelling}."""
    if _vocab: return _vocab
    import clean_catalog
    c = collections.Counter((p.get("brand") or "").strip() for p in load_catalog()[1])
    best = {}
    for b, n in c.most_common():
        if not b or b == "Uncategorized": continue
        b = clean_catalog.BRAND_ALIAS.get(b, b)
        k = fold(b)
        if k and k not in best: best[k] = b        # the most common spelling of each folded name wins
    for b in EXTRA:
        best.setdefault(fold(b), b)
    for k, v in clean_catalog.BRAND_ALIAS.items():
        if fold(k) not in ("polo", "purple", "aime", "cp"): best.setdefault(fold(k), best.get(fold(v), v))
    for k, v in ALIAS.items():
        best[fold(k)] = best.get(fold(v), v)
    # never a brand on its own: words that name things, colours or places too often
    for k in ("polo", "purple", "on", "vale", "arte", "chai", "spider", "replay", "opium", "revenge", "polar", "marathon",
              "shark", "arsenal", "dodge", "mercedes", "running dog", "garms", "ultralight", "empyre", "attere", "bazo",
              "numeris", "brazil", "portugal", "england", "italy", "france", "japan", "spain", "germany", "argentina",
              "mexico", "netherlands", "usa", "korea", "colombia", "senegal", "switzerland", "croatia", "morocco",
              "tunisia", "ecuador", "canada", "austria", "australia", "south korea", "chelsea", "barcelona", "sicko",
              "rebel wave", "mixed emotions", "vicinity", "reaven", "jee", "cotevue", "6pm", "akimbo", "huni", "rhode",
              "kakaazy", "vless", "colesice", "mmy", "erl", "psd", "csonline", "panini", "porsche", "ferrari", "suzuki",
              "subaru", "marlboro", "chrome", "meta", "stanley", "dragon ball", "travelite", "fragment"):
        best.pop(k, None)
    have = {fold(clean_catalog.BRAND_ALIAS.get(b, b)) for b in c if b}
    _new.update(v for k, v in best.items() if fold(v) not in have)
    _vocab.update(best)
    return _vocab


def brands_in(text):
    """[(brand, start, end)] for every brand named in the text, left to right (word positions in fold(text))."""
    words, v, out, i = fold(text).split(), vocab(), [], 0
    while i < len(words):
        for n in (4, 3, 2, 1):
            k = " ".join(words[i:i + n])
            if len(words[i:i + n]) == n and k in v and not (k in NOT_BRAND and not re.search(NOT_BRAND[k], fold(text))):
                out.append((v[k], i, i + n)); i += n; break
        else:
            i += 1
    return out


def find_brand(text):
    """(brand, start, end): the earliest brand named, but a brand the catalogue has before one it does not ("Wales
    Bonner Adidas Superstars" is filed under Adidas); a product word that names its brand when none is named ("Airpods
    Max" is Apple; start -1, the word stays in the title). ('', -1, -1) when there is none."""
    found = brands_in(text)
    if found:
        if found[0][0] in _new:
            for b in found[1:]:
                if b[0] not in _new: return b
        return found[0]
    f = fold(text)
    for rx, b in PRODUCT_BRAND:
        if re.search(rx, f): return (b, -1, -1)
    return ("", -1, -1)


def colour_from_zh(zh):
    zh = str(zh or "")
    for k, en in COLOUR_ZH:
        if k in zh: return en
    m = re.search(r"(?i)\b(" + "|".join(sorted(map(re.escape, COLOUR_EN), key=len, reverse=True)) + r")\b", zh)
    return COLOUR_EN.get(m.group(1).lower(), "") if m else ""


def colour_in(text, brand=""):
    """The first colour word of an English text, as the catalogue writes it ('' when none). Words of a brand do not
    count ("Off-White", "Golden Goose", "Black Scale")."""
    words = fold(text).split()
    gone = set()
    for b, i0, i1 in brands_in(text):
        gone |= set(range(i0, i1))
    for bw in fold(brand).split() if brand else []:
        gone |= {j for j, w in enumerate(words) if w == bw}
    t = " " + " ".join(w for j, w in enumerate(words) if j not in gone) + " "
    best = None
    for k in sorted(COLOUR_EN, key=len, reverse=True):
        m = re.search(r" " + re.escape(fold(k)) + r" ", t)
        if m and COLOUR_EN[k] and (best is None or m.start() < best[0]): best = (m.start(), COLOUR_EN[k])
    return best[1] if best else ""


def item_from_zh(zh):
    z = str(zh or "").lower()
    for k, en in ITEM_ZH:
        if k in z: return en
    return ""


def _case(w, orig):
    """Title Case for one word, keeping acronyms (PSG, UVU, JBL), words with inner capitals (MothTech) and codes."""
    if re.search(r"\d", w): return w.upper() if re.fullmatch(r"[a-z]{1,3}\d{1,4}", w, re.I) else w
    if w.lower() in ("x",): return "x"
    if w.lower() in CAPS: return w.upper()
    if orig.isupper() and len(orig) <= 3 and orig.isalpha(): return orig
    if re.search(r"[a-z][A-Z]", orig) and orig[:1].isupper(): return orig   # MothTech, not rEVenge
    if "-" in w: return "-".join(_case(p, p) for p in w.split("-"))
    return w[:1].upper() + w[1:].lower()


def clean_words(name):
    """The sheet's name without banned words, prices, notes, emojis and dashes used as punctuation."""
    s = unicodedata.normalize("NFKC", str(name or ""))
    s = re.sub(r"[\u2014\u2013]", " ", s)
    s = re.sub(r"\$\s*\d+(?:[.,]\d+)?", " ", s)
    s = re.sub(r"(?i)\b(" + BANNED + r")\b", " ", s)
    s = re.sub(r"(?i)\(?\+?\s*\d*\+?\s*(many |all |other |more )?colou?r(s|ways?)?\)?", " ", s) \
        if re.search(r"(?i)colou?r(s|ways?)?\b", s) else s
    s = re.sub(r"[()（）\[\]{}\"“”,;:!?…|/\\*#@~^]+", " ", s)
    s = re.sub(r"(?<=\s)-+(?=\s)|^-+|-+$", " ", s)
    s = re.sub(r"\.{2,}|\betc\b\.?", " ", s, flags=re.I)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "S" or ch in "&'+%")
    return [w for w in s.split() if w and w not in ("&", "+", "'")]


def house_title(name, brand="", item="", colour="", cat=""):
    """'Brand Model Item Colour' from the sheet's name: the brand spelled as the catalogue does and put first (every
    mention of it, "YSL Saint Laurent Loafers" -> "Saint Laurent Loafers"), typos of the sheet fixed, item words in the
    singular as the catalogue writes them, an item word added when the name has none, the colour when it has none."""
    words = clean_words(name)
    text = " ".join(words)
    b = brand or find_brand(text)[0]
    gone = set()
    for bb, i0, i1 in brands_in(text):
        if bb == b: gone |= set(range(i0, i1))
    fw, bw = fold(text).split(), fold(b).split()
    if len(bw) >= 3:                                   # "CDG 1986 comme des Tee": a cut-short repeat of the brand
        for j in range(len(fw) - 1):
            if fw[j:j + 2] == bw[:2]: gone |= {j, j + 1}
    out, k = [], 0
    for wi, w in enumerate(words):
        n = len(fold(w).split()) or 1
        span = range(k, k + n)
        k += n
        if b and span and all(j in gone for j in span): continue        # the brand goes first, spelled right
        lw = w.lower()
        if lw in TITLE_DROP: continue
        if lw == "new" and (wi == 0 or wi == len(words) - 1): continue   # "New" alone, not "Chinese New Year"
        if re.fullmatch(r"\+?\d+\+?", lw) and re.search(r"\+", lw): continue   # "15+" (styles in the listing)
        fx = TYPO.get(lw.strip(".'")) or SINGULAR.get(lw)
        out.append(fx if fx else _case(w, w))
    while out and out[0].lower() in (("and", "&") if b else ("x", "and", "&")): out.pop(0)
    while out and out[-1].lower() in ("x", "and", "&", "in", "the", "of", "with", "for"): out.pop()
    if out and out[-1].lower() == "short": out[-1] = "Shorts"
    if not b and len(out) > 1 and out[0].lower() == "polo" and not ITEM_WORDS.fullmatch(out[1]):
        b = "Ralph Lauren"                                               # "Polo basic tees" (BRAND_ALIAS: Polo)
    t = re.sub(r"(?i)\b([\w-]+) \1\b", r"\1", " ".join(out))               # "Hoodie Hoodie"
    if item and not ITEM_WORDS.search(t): t = (t + " " + item).strip()
    if colour and not colour_in(t) and colour.lower() not in t.lower(): t = (t + " " + colour).strip()
    lead = "Air Jordan" if b == "Jordan" and "air jordan" in fold(name) else b
    if lead == "Air Jordan": t = re.sub(r"(?i)^air\s+", "", t)
    t = re.sub(r"\s+", " ", ((lead + " ") if lead else "") + t).strip()
    if not t: t = (b + " " + (item or cat or "Find")).strip()
    return t[:70].rsplit(" ", 1)[0] if len(t) > 70 else t


# ---------------------------------------------------------------- the duplicate check's view of a title
SIZE_TOKEN = re.compile(r"^(xxs|xs|s|m|l|xl|xxl|xxxl|[2-6]xl|eu\d{2}|us\d{1,2}|uk\d{1,2}|\d{2,3}cm|\d{1,3}%|\d{2,3}mm)$")
SYN = {"tee": "tshirt", "tees": "tshirt", "t": "", "shirt": "shirt", "tshirt": "tshirt", "hoody": "hoodie",
       "trainers": "sneaker", "trainer": "sneaker", "sneakers": "sneaker", "shoes": "shoe", "longsleeve": "longsleeve",
       "zipup": "zip", "zip-up": "zip", "jumper": "sweater", "pullover": "sweater", "joggers": "sweatpants",
       "jogger": "sweatpants", "pant": "pants", "trouser": "pants", "trousers": "pants", "cap": "cap", "caps": "cap",
       "hats": "hat", "beanies": "beanie", "bags": "bag", "jackets": "jacket", "hoodies": "hoodie", "sweaters": "sweater",
       "jerseys": "jersey", "belts": "belt", "wallets": "wallet", "boots": "boot", "slides": "slide", "loafers": "loafer",
       "sets": "set", "socks": "sock", "rings": "ring", "necklaces": "necklace", "bracelets": "bracelet"}
NOISE = FILLER - {"set"}


def model_words(title, brand=""):
    """The words of a title that name the model: no brand, colours, sizes, seller codes or filler words; plurals and
    spellings folded ('Tees' = 'T-Shirt'). Sorted tuple."""
    t = re.sub(r"t-?shirts?", "tshirt", str(title or "").lower())
    t = fold(re.sub(r"long[- ]?sleeves?", "longsleeve", re.sub(r"zip[- ]?ups?", "zipup", t)))
    words = t.split()
    bw = set(fold(brand).split()) if brand else set()
    b, i0, i1 = find_brand(title)
    drop = set(range(i0, i1)) if i0 >= 0 else set()
    cw = set()
    for k in COLOUR_EN:
        cw |= set(fold(k).split())
    out = []
    for j, w in enumerate(words):
        if j in drop or w in bw or w in cw or w in NOISE or SIZE_TOKEN.match(w): continue
        if re.fullmatch(r"\d{5,}", w) or re.fullmatch(r"(?=.*\d)(?=.*[a-z])[a-z0-9]{6,}", w): continue   # seller codes
        w = SYN.get(w, w)
        if not w: continue
        if len(w) > 4 and w.endswith("ies"): w = w[:-3] + "y"
        elif len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "is", "us")) and w not in (
                "shorts", "pants", "jeans", "glasses", "sunglasses", "sweatpants", "leggings", "chinos", "trunks",
                "boxers", "gats", "jorts"): w = w[:-1]
        out.append(w)
    return tuple(sorted(set(out)))


# item words and plain descriptions: two finds that share only these are not the same model ("Ami Sweater" and "Ami
# Sweater" can be two designs); the model rule of the duplicate check (scripts/import_archive.py) needs at least one other word
GENERIC = {"tshirt", "shirt", "longsleeve", "polo", "hoodie", "zipup", "zip", "zipper", "sweater", "sweatshirt", "crewneck",
           "cardigan", "knit", "jersey", "tank", "top", "henley", "tracksuit", "set", "jacket", "puffer", "parka", "coat",
           "windbreaker", "vest", "gilet", "fleece", "bomber", "overshirt", "jeans", "pants", "trouser", "jogger",
           "sweatpants", "cargo", "legging", "shorts", "jorts", "sneaker", "shoe", "trainer", "boot", "loafer", "slide",
           "sandal", "slipper", "clog", "mule", "runner", "bag", "backpack", "tote", "wallet", "card", "holder", "cap",
           "hat", "beanie", "belt", "watch", "necklace", "bracelet", "ring", "earring", "sunglasses", "glasses", "sock",
           "scarf", "glove", "underwear", "boxers", "perfume", "dres", "dress", "skirt", "rug", "carpet", "pillow", "case",
           "headband", "basic", "graphic", "logo", "print", "printed", "striped", "stripe", "plain", "classic", "leather",
           "suede", "wool", "cotton", "knitted", "denim", "washed", "vintage", "oversized", "cropped", "boxy", "full",
           "half", "quarter", "high", "low", "mid", "short", "long", "sleeve", "crew", "neck", "mock", "sport", "sports",
           "running", "training", "compression", "mesh", "down", "padded", "embroidered", "small", "big", "mini", "large",
           "heavy", "light", "lightweight", "thick", "thin", "warm", "summer", "winter", "casual", "simple", "slim",
           "loose", "baggy", "straight", "wide", "leg", "fit", "pair", "pack", "piece", "up", "track", "hooded", "button",
           "flannel", "check", "checked", "plaid", "camo", "nylon", "silk", "linen", "cashmere", "velvet", "corduroy",
           "heel", "flat", "platform", "chain", "pendant", "lock", "keychain", "phone", "air", "pro", "max", "plus"}


def distinctive(mw):
    """True when model words name a model, not only an item ("Triple S", "9060", "Box Logo" do; "Hoodie" does not)."""
    return any(w not in GENERIC and not re.fullmatch(r"\d{1,2}", w) for w in mw)


# ---------------------------------------------------------------- a colour name from the item's pixels
def _lab(rgb):
    """sRGB (N x 3, 0..255) to CIELAB (D65)."""
    import numpy as np
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def colour_name(px):
    """A plain colour name ('Black', 'Navy', 'Beige' ...) for the main colour of an item, from its solid pixels (N x 3
    RGB): the biggest of three colour clusters, named by lightness, chroma and hue. '' when there are too few pixels or
    no colour covers a third of the item (a print or a multicolour item: no colour is better than a wrong one)."""
    import numpy as np
    px = np.asarray(px, np.float64).reshape(-1, 3)
    if len(px) < 200: return ""
    if len(px) > 20000: px = px[np.random.default_rng(0).choice(len(px), 20000, replace=False)]
    lab = _lab(px)
    cen = lab[np.linspace(0, len(lab) - 1, 3).astype(int)]
    cen = np.array(sorted(cen, key=lambda v: v[0]))
    for _ in range(12):
        lbl = np.argmin(((lab[:, None, :] - cen[None, :, :]) ** 2).sum(axis=2), axis=1)
        cen = np.array([lab[lbl == k].mean(axis=0) if (lbl == k).any() else cen[k] for k in range(3)])
    share = np.bincount(lbl, minlength=3) / len(lbl)
    # clusters that are the same colour family count together (the light and dark side of one black sweater)
    k = int(np.argmax(share))
    L, a, b = np.median(lab[lbl == k], axis=0)
    near = [j for j in range(3) if np.hypot(*(cen[j][1:] - cen[k][1:])) < 12 and abs(cen[j][0] - L) < 30]
    if share[near].sum() < 0.34: return ""
    C = float(np.hypot(a, b)); h = float(np.degrees(np.arctan2(b, a)) % 360)
    # CIELAB hue angles: red about 40, orange 60, yellow 100, green 135, cyan 200, blue 300, purple 325, pink 0 to 20
    if C < 9:
        return "Black" if L < 22 else "White" if L >= 86 else "Grey"
    if C < 16 and L < 30: return "Brown" if 20 <= h < 110 else "Black"
    if 230 <= h < 312: return "Navy" if L < 30 else "Light Blue" if L >= 70 else "Blue"
    if 312 <= h < 340: return "Purple" if L < 65 else "Pink"
    if h >= 340 or h < 18: return "Pink" if L >= 50 else "Burgundy"
    if h < 45:
        if L >= 70: return "Pink"
        if C < 20 and L < 45: return "Brown"
        return "Burgundy" if L < 30 else "Red"
    if 45 <= h < 80:
        if L < 45: return "Brown"
        if C >= 50: return "Orange"
        return "Beige" if C < 25 and L >= 65 else "Tan" if L < 72 else "Beige"
    if 80 <= h < 120:
        if L < 50: return "Olive" if C >= 20 else "Brown"
        if C >= 45 and h < 110: return "Yellow"
        if h >= 110: return "Green"
        return "Beige" if C < 22 and L >= 70 else "Khaki"
    if 120 <= h < 185: return "Dark Green" if L < 35 else "Green"
    if 185 <= h < 230: return "Teal" if C >= 15 else "Grey"
    return ""


# ---------------------------------------------------------------- a category from a name
# For a sheet row outside a named section: first match wins, so the things that are not clothes come first
# ("Dartboard and darts set", "Bearbrick Garage Kit", "Polo Socks"). The site's nine categories (catalog_common.CATS).
GUESS = [
    ("Toys", r"\b(lego|toys?|figures?|funko|hot ?wheels|beyblade|labubu|bear ?bricks?|plush|garage kit|"
             r"fingerboard|skateboard|dartboard|darts?)\b"),
    ("Accessories", r"\b(socks?|boxers?|briefs?|underwears?|wallets?|card ?holders?|cardholders?|belts?|ties|tie(?![- ]?dye)|"
                    r"watch(es)?|watch strap|smart ?watch|bracelets?|necklaces?|chains?|rings?|earrings?|pendants?|"
                    r"sunglass(es)?|glasses|scarfs?|scarves|gloves?|perfumes?|colognes?|parfum|fragrance|keychains?|"
                    r"key chains?|lanyard|cases?|airpods|earbuds|headphones?|speakers?|keyboards?|chargers?|"
                    r"controllers?|lamp|dress(es)?|skirts?|blankets?|pillows?|rugs?|carpets?|mats?|mousepad|towels?|"
                    r"bottles?|cups?|thermos|trays?|ash ?trays?|stool|books?|stickers?|pins|umbrella|lighter|combs?)\b"),
    ("Headwear", r"\b(caps?|hats?|beanies?|balaclavas?|bucket|trucker|snapback|head ?bands?|hair ?bands?|durag)\b"),
    ("Shorts", r"\b(shorts|short(?![- ]?sleeves?)|jorts|swim ?trunks)\b"),
    ("Shoes", r"\b(shoes?|sneakers?|trainers?|boots?|loafers?|slides?|sandals?|slippers?|clogs?|mules?|"
              r"runners?|flip ?flops?|cleats?|derby|oxfords?|heels|pumps)\b"),
    ("Bags", r"\b(bags?|backpacks?|totes?|duffel|duffle|pouch|crossbody|messenger|handbags?|luggage|suitcase)\b"),
    ("Outerwear", r"\b(jackets?|puffers?|parkas?|coats?|windbreakers?|gilets?|anoraks?|fleece|bombers?|varsity|"
                  r"peacoats?|overshirts?)\b"),
    ("Pants", r"\b(pants|jeans|trousers|joggers?|sweatpants|cargos?|leggings?|flares?|denim)\b"),
    ("Tops", r"\b(t-?shirts?|tees?|longsleeves?|long-? ?sleeves?|polos?|shirts?|hoodies?|hoody|zip-? ?ups?|full zip|"
             r"sweaters?|sweatshirts?|crewnecks?|cardigans?|knits?|jerseys?|tanks?|tank tops?|tops?|henleys?|"
             r"tracksuits?|sets?|quarter ?zip|half ?zip|jumpers?|blouses?|bodysuits?|corsets?|vests?)\b"),
    ("Shoes", r"\b(havaianas|uggs?|jordans?|dunks?|yeezys?|air max|af1|air force|sambas?|gazelles?|superstars?|"
              r"campus|spezia|speedcat|tabi|b22|b23|b30|3xl|track ?runner|triple ?s|golden goose|birkenstock|birks|"
              r"gats|timberlands?)\b"),
]


def guess_cat(name):
    """The site category a name points to, or None."""
    n = (name or "").lower()
    for cat, rx in GUESS:
        if re.search(rx, n): return cat
    return None


def item_in(text):
    """The first item word of an English text, as the catalogue writes it ('Flip Flops', 'T-Shirt'), or ''."""
    m = ITEM_WORDS.search(str(text or ""))
    if not m: return ""
    w = m.group(0).lower()
    fx = TYPO.get(w) or SINGULAR.get(w)
    return fx if fx else " ".join(_case(x, x) for x in w.split())
