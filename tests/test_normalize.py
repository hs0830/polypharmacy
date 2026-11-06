from src.normalize import (ingredient_key, ko_lookup, normalize_component, paren_ingredient_lists,
                           parse_korean_ingredients, product_core)


def test_salt_and_as_clause():
    assert normalize_component("rosuvastatin calcium (as rosuvastatin)") == "rosuvastatin"
    assert normalize_component("amlodipine besylate (as amlodipine   5mg)") == "amlodipine"
    assert normalize_component("gemigliptin tartrate sesquihydrate (as gemigliptin") == "gemigliptin"  # 닫는 괄호 누락


def test_no_overstripping():
    assert normalize_component("potassium chloride") == "potassium chloride"
    assert normalize_component("caffeine anhydrous") == "caffeine"
    assert normalize_component("5-fluorouracil") == "fluorouracil"


def test_combo_key_is_sorted_and_keeps_all_components():
    assert ingredient_key("tegafur+gimeracil+oteracil potassium") == "gimeracil+oteracil+tegafur"
    assert ingredient_key("tramadol hydrochloride+acetaminophen") == "acetaminophen+tramadol"


def test_ko_lookup_strips_salts():
    d = {"메트포르민": "metformin", "아세트아미노펜": "acetaminophen"}
    assert ko_lookup("메트포르민염산염", d) == "metformin"
    assert ko_lookup("아세트아미노펜", d) == "acetaminophen"
    assert ko_lookup("모르는성분", d) is None


def test_paren_lists_split_and_skip_export():
    assert paren_ingredient_lists("비스포지정10/160밀리그램(암로디핀베실산염, 발사르탄)") == [["암로디핀베실산염", "발사르탄"]]
    assert paren_ingredient_lists("노텍정(수출용)") == []


def test_parse_korean_ingredients_handles_codes_and_separators():
    assert parse_korean_ingredients("[M040702]포도당|[M223547]아세트아미노펜(수출용)") == ["포도당", "아세트아미노펜"]
    assert parse_korean_ingredients("") == [] and parse_korean_ingredients(None) == []


def test_product_core():
    assert product_core("타이레놀정500밀리그램(아세트아미노펜)") == "타이레놀"
    assert product_core("노바스크정5밀리그램") == "노바스크"


def test_formulation_descriptors_are_stripped():
    assert normalize_component("itraconazole solid dispersions") == "itraconazole"
    assert normalize_component("dapagliflozin bis l-proline") == "dapagliflozin"
    assert normalize_component("cabozantinib -malate") == "cabozantinib"
    assert normalize_component("metformin hydrochloride with colloidal anhydrous silica") == "metformin"
    assert normalize_component("lansoprazole") == "lansoprazole"
    assert normalize_component("precipitated calcium carbonate") == "calcium carbonate"
    assert normalize_component("dilute nitroglycerin") == "nitroglycerin"
    assert normalize_component("microemulsion cyclosporine") == "cyclosporine"
    assert normalize_component("cimicifuga rhizome ext.") == normalize_component("cimicifuga rhizome extract")


def test_meaningful_names_are_protected():
    assert normalize_component("chloral hydrate") == "chloral hydrate"
    assert normalize_component("sodium chloride") == "sodium chloride"
    assert normalize_component("magnesium sulfate") == "magnesium sulfate"


def test_more_salt_words():
    assert normalize_component("dapagliflozin propanediol") == "dapagliflozin"
    assert normalize_component("atorvastatin calcium trihydrate granule") == "atorvastatin"
    assert normalize_component("dl-methylephedrine hci") == "dl-methylephedrine"
