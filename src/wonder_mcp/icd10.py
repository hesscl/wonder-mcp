"""
Local ICD-10-CM chapter and sub-chapter lookup for building CDC WONDER filters.

Source: ICD-10-CM Tabular List (CMS) and WHO ICD-10 Volume 1.
Covers all 22 chapters and the most epidemiologically relevant sub-chapters.

WONDER filter usage:
  - Group by chapter:     group_by=["D76.V2-level1"]
  - Group by sub-chapter: group_by=["D76.V2-level2"]
  - Filter by chapter:    filters={"D76.V2": <code_range>}
  - Filter by leading cause list: group_by=["D76.V4"]
"""

from __future__ import annotations

from typing import Optional


# Each entry: code, label, level, chapter_num
# level: "chapter" | "sub-chapter" | "special"
_ICD10_TABLE: list[dict] = [
    # -----------------------------------------------------------------------
    # Chapter I — Certain infectious and parasitic diseases (A00–B99)
    # -----------------------------------------------------------------------
    {"code": "A00-B99", "label": "Certain infectious and parasitic diseases", "level": "chapter", "chapter": "I"},
    {"code": "A00-A09", "label": "Intestinal infectious diseases", "level": "sub-chapter", "chapter": "I"},
    {"code": "A15-A19", "label": "Tuberculosis", "level": "sub-chapter", "chapter": "I"},
    {"code": "A30-A49", "label": "Other bacterial diseases", "level": "sub-chapter", "chapter": "I"},
    {"code": "A50-A64", "label": "Infections with a predominantly sexual mode of transmission", "level": "sub-chapter", "chapter": "I"},
    {"code": "A80-A89", "label": "Viral infections of the central nervous system", "level": "sub-chapter", "chapter": "I"},
    {"code": "B00-B09", "label": "Viral infections characterized by skin and mucous membrane lesions", "level": "sub-chapter", "chapter": "I"},
    {"code": "B20-B24", "label": "HIV disease", "level": "sub-chapter", "chapter": "I"},
    {"code": "B50-B64", "label": "Protozoal diseases", "level": "sub-chapter", "chapter": "I"},
    {"code": "B90-B94", "label": "Sequelae of infectious and parasitic diseases", "level": "sub-chapter", "chapter": "I"},

    # -----------------------------------------------------------------------
    # Chapter II — Neoplasms (C00–D49)
    # -----------------------------------------------------------------------
    {"code": "C00-D49", "label": "Neoplasms", "level": "chapter", "chapter": "II"},
    {"code": "C00-C14", "label": "Malignant neoplasms of lip, oral cavity and pharynx", "level": "sub-chapter", "chapter": "II"},
    {"code": "C15-C26", "label": "Malignant neoplasms of digestive organs", "level": "sub-chapter", "chapter": "II"},
    {"code": "C30-C39", "label": "Malignant neoplasms of respiratory and intrathoracic organs", "level": "sub-chapter", "chapter": "II"},
    {"code": "C40-C41", "label": "Malignant neoplasms of bone and articular cartilage", "level": "sub-chapter", "chapter": "II"},
    {"code": "C43-C44", "label": "Melanoma and other malignant neoplasms of skin", "level": "sub-chapter", "chapter": "II"},
    {"code": "C50",     "label": "Malignant neoplasm of breast", "level": "sub-chapter", "chapter": "II"},
    {"code": "C51-C58", "label": "Malignant neoplasms of female genital organs", "level": "sub-chapter", "chapter": "II"},
    {"code": "C60-C63", "label": "Malignant neoplasms of male genital organs", "level": "sub-chapter", "chapter": "II"},
    {"code": "C64-C68", "label": "Malignant neoplasms of urinary tract", "level": "sub-chapter", "chapter": "II"},
    {"code": "C70-C72", "label": "Malignant neoplasms of brain and other parts of central nervous system", "level": "sub-chapter", "chapter": "II"},
    {"code": "C73-C75", "label": "Malignant neoplasms of thyroid and other endocrine glands", "level": "sub-chapter", "chapter": "II"},
    {"code": "C76-C80", "label": "Malignant neoplasms of ill-defined and secondary sites", "level": "sub-chapter", "chapter": "II"},
    {"code": "C81-C96", "label": "Malignant neoplasms of lymphoid, haematopoietic and related tissue", "level": "sub-chapter", "chapter": "II"},
    {"code": "D00-D09", "label": "In situ neoplasms", "level": "sub-chapter", "chapter": "II"},
    {"code": "D10-D36", "label": "Benign neoplasms", "level": "sub-chapter", "chapter": "II"},
    {"code": "D37-D48", "label": "Neoplasms of uncertain or unknown behaviour", "level": "sub-chapter", "chapter": "II"},

    # -----------------------------------------------------------------------
    # Chapter III — Diseases of the blood (D50–D89)
    # -----------------------------------------------------------------------
    {"code": "D50-D89", "label": "Diseases of the blood and blood-forming organs and certain disorders involving the immune mechanism", "level": "chapter", "chapter": "III"},
    {"code": "D50-D53", "label": "Nutritional anaemias", "level": "sub-chapter", "chapter": "III"},
    {"code": "D55-D59", "label": "Haemolytic anaemias", "level": "sub-chapter", "chapter": "III"},
    {"code": "D60-D64", "label": "Aplastic and other anaemias", "level": "sub-chapter", "chapter": "III"},
    {"code": "D65-D69", "label": "Coagulation defects, purpura and other haemorrhagic conditions", "level": "sub-chapter", "chapter": "III"},
    {"code": "D80-D89", "label": "Certain disorders involving the immune mechanism", "level": "sub-chapter", "chapter": "III"},

    # -----------------------------------------------------------------------
    # Chapter IV — Endocrine, nutritional and metabolic diseases (E00–E89)
    # -----------------------------------------------------------------------
    {"code": "E00-E89", "label": "Endocrine, nutritional and metabolic diseases", "level": "chapter", "chapter": "IV"},
    {"code": "E00-E07", "label": "Disorders of thyroid gland", "level": "sub-chapter", "chapter": "IV"},
    {"code": "E10-E14", "label": "Diabetes mellitus", "level": "sub-chapter", "chapter": "IV"},
    {"code": "E40-E46", "label": "Malnutrition", "level": "sub-chapter", "chapter": "IV"},
    {"code": "E65-E68", "label": "Obesity and other hyperalimentation", "level": "sub-chapter", "chapter": "IV"},
    {"code": "E70-E88", "label": "Metabolic disorders", "level": "sub-chapter", "chapter": "IV"},

    # -----------------------------------------------------------------------
    # Chapter V — Mental and behavioural disorders (F01–F99)
    # -----------------------------------------------------------------------
    {"code": "F01-F99", "label": "Mental and behavioural disorders", "level": "chapter", "chapter": "V"},
    {"code": "F01-F09", "label": "Organic, including symptomatic, mental disorders", "level": "sub-chapter", "chapter": "V"},
    {"code": "F10-F19", "label": "Mental and behavioural disorders due to psychoactive substance use", "level": "sub-chapter", "chapter": "V"},
    {"code": "F20-F29", "label": "Schizophrenia, schizotypal and delusional disorders", "level": "sub-chapter", "chapter": "V"},
    {"code": "F30-F39", "label": "Mood (affective) disorders", "level": "sub-chapter", "chapter": "V"},
    {"code": "F40-F48", "label": "Neurotic, stress-related and somatoform disorders", "level": "sub-chapter", "chapter": "V"},

    # -----------------------------------------------------------------------
    # Chapter VI — Diseases of the nervous system (G00–G99)
    # -----------------------------------------------------------------------
    {"code": "G00-G99", "label": "Diseases of the nervous system", "level": "chapter", "chapter": "VI"},
    {"code": "G00-G09", "label": "Inflammatory diseases of the central nervous system", "level": "sub-chapter", "chapter": "VI"},
    {"code": "G10-G14", "label": "Systemic atrophies primarily affecting the central nervous system", "level": "sub-chapter", "chapter": "VI"},
    {"code": "G20-G26", "label": "Extrapyramidal and movement disorders (incl. Parkinson disease)", "level": "sub-chapter", "chapter": "VI"},
    {"code": "G30-G32", "label": "Other degenerative diseases of the nervous system (incl. Alzheimer disease)", "level": "sub-chapter", "chapter": "VI"},
    {"code": "G40-G47", "label": "Episodic and paroxysmal disorders (incl. epilepsy)", "level": "sub-chapter", "chapter": "VI"},

    # -----------------------------------------------------------------------
    # Chapter VII — Diseases of the eye (H00–H59)
    # -----------------------------------------------------------------------
    {"code": "H00-H59", "label": "Diseases of the eye and adnexa", "level": "chapter", "chapter": "VII"},

    # -----------------------------------------------------------------------
    # Chapter VIII — Diseases of the ear (H60–H95)
    # -----------------------------------------------------------------------
    {"code": "H60-H95", "label": "Diseases of the ear and mastoid process", "level": "chapter", "chapter": "VIII"},

    # -----------------------------------------------------------------------
    # Chapter IX — Diseases of the circulatory system (I00–I99)
    # -----------------------------------------------------------------------
    {"code": "I00-I99", "label": "Diseases of the circulatory system", "level": "chapter", "chapter": "IX"},
    {"code": "I00-I09", "label": "Acute rheumatic fever", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I10-I15", "label": "Hypertensive diseases", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I20-I25", "label": "Ischaemic heart diseases", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I26-I28", "label": "Pulmonary heart disease and diseases of pulmonary circulation", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I30-I52", "label": "Other forms of heart disease", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I60-I69", "label": "Cerebrovascular diseases", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I70-I79", "label": "Diseases of arteries, arterioles and capillaries", "level": "sub-chapter", "chapter": "IX"},
    {"code": "I80-I89", "label": "Diseases of veins, lymphatic vessels and lymph nodes", "level": "sub-chapter", "chapter": "IX"},

    # -----------------------------------------------------------------------
    # Chapter X — Diseases of the respiratory system (J00–J99)
    # -----------------------------------------------------------------------
    {"code": "J00-J99", "label": "Diseases of the respiratory system", "level": "chapter", "chapter": "X"},
    {"code": "J00-J06", "label": "Acute upper respiratory infections", "level": "sub-chapter", "chapter": "X"},
    {"code": "J09-J18", "label": "Influenza and pneumonia", "level": "sub-chapter", "chapter": "X"},
    {"code": "J20-J22", "label": "Other acute lower respiratory infections", "level": "sub-chapter", "chapter": "X"},
    {"code": "J30-J39", "label": "Other diseases of upper respiratory tract", "level": "sub-chapter", "chapter": "X"},
    {"code": "J40-J47", "label": "Chronic lower respiratory diseases (incl. COPD, asthma)", "level": "sub-chapter", "chapter": "X"},
    {"code": "J60-J70", "label": "Lung diseases due to external agents", "level": "sub-chapter", "chapter": "X"},
    {"code": "J80-J84", "label": "Other respiratory diseases principally affecting the interstitium", "level": "sub-chapter", "chapter": "X"},

    # -----------------------------------------------------------------------
    # Chapter XI — Diseases of the digestive system (K00–K93)
    # -----------------------------------------------------------------------
    {"code": "K00-K93", "label": "Diseases of the digestive system", "level": "chapter", "chapter": "XI"},
    {"code": "K00-K14", "label": "Diseases of oral cavity, salivary glands and jaws", "level": "sub-chapter", "chapter": "XI"},
    {"code": "K20-K31", "label": "Diseases of oesophagus, stomach and duodenum", "level": "sub-chapter", "chapter": "XI"},
    {"code": "K40-K46", "label": "Hernia", "level": "sub-chapter", "chapter": "XI"},
    {"code": "K50-K67", "label": "Noninfective enteritis and colitis; diseases of intestines", "level": "sub-chapter", "chapter": "XI"},
    {"code": "K70-K77", "label": "Diseases of liver (incl. cirrhosis, alcoholic liver disease)", "level": "sub-chapter", "chapter": "XI"},
    {"code": "K80-K87", "label": "Disorders of gallbladder, biliary tract and pancreas", "level": "sub-chapter", "chapter": "XI"},

    # -----------------------------------------------------------------------
    # Chapter XII — Diseases of the skin (L00–L99)
    # -----------------------------------------------------------------------
    {"code": "L00-L99", "label": "Diseases of the skin and subcutaneous tissue", "level": "chapter", "chapter": "XII"},

    # -----------------------------------------------------------------------
    # Chapter XIII — Musculoskeletal (M00–M99)
    # -----------------------------------------------------------------------
    {"code": "M00-M99", "label": "Diseases of the musculoskeletal system and connective tissue", "level": "chapter", "chapter": "XIII"},

    # -----------------------------------------------------------------------
    # Chapter XIV — Genitourinary (N00–N99)
    # -----------------------------------------------------------------------
    {"code": "N00-N99", "label": "Diseases of the genitourinary system", "level": "chapter", "chapter": "XIV"},
    {"code": "N17-N19", "label": "Renal failure", "level": "sub-chapter", "chapter": "XIV"},
    {"code": "N20-N23", "label": "Urolithiasis", "level": "sub-chapter", "chapter": "XIV"},
    {"code": "N40-N51", "label": "Diseases of male genital organs", "level": "sub-chapter", "chapter": "XIV"},
    {"code": "N60-N65", "label": "Disorders of breast", "level": "sub-chapter", "chapter": "XIV"},
    {"code": "N70-N77", "label": "Inflammatory diseases of female pelvic organs", "level": "sub-chapter", "chapter": "XIV"},

    # -----------------------------------------------------------------------
    # Chapter XV — Pregnancy, childbirth (O00–O9A)
    # -----------------------------------------------------------------------
    {"code": "O00-O9A", "label": "Pregnancy, childbirth and the puerperium", "level": "chapter", "chapter": "XV"},
    {"code": "O00-O08", "label": "Pregnancy with abortive outcome", "level": "sub-chapter", "chapter": "XV"},
    {"code": "O10-O16", "label": "Oedema, proteinuria and hypertensive disorders in pregnancy", "level": "sub-chapter", "chapter": "XV"},
    {"code": "O60-O75", "label": "Complications of labour and delivery", "level": "sub-chapter", "chapter": "XV"},
    {"code": "O85-O92", "label": "Complications predominantly related to the puerperium", "level": "sub-chapter", "chapter": "XV"},

    # -----------------------------------------------------------------------
    # Chapter XVI — Perinatal conditions (P00–P96)
    # -----------------------------------------------------------------------
    {"code": "P00-P96", "label": "Certain conditions originating in the perinatal period", "level": "chapter", "chapter": "XVI"},

    # -----------------------------------------------------------------------
    # Chapter XVII — Congenital malformations (Q00–Q99)
    # -----------------------------------------------------------------------
    {"code": "Q00-Q99", "label": "Congenital malformations, deformations and chromosomal abnormalities", "level": "chapter", "chapter": "XVII"},

    # -----------------------------------------------------------------------
    # Chapter XVIII — Symptoms and signs (R00–R99)
    # -----------------------------------------------------------------------
    {"code": "R00-R99", "label": "Symptoms, signs and abnormal clinical and laboratory findings, not elsewhere classified", "level": "chapter", "chapter": "XVIII"},
    {"code": "R95-R99", "label": "Ill-defined and unknown causes of mortality (incl. sudden infant death)", "level": "sub-chapter", "chapter": "XVIII"},

    # -----------------------------------------------------------------------
    # Chapter XIX — Injury and poisoning (S00–T88)
    # -----------------------------------------------------------------------
    {"code": "S00-T88", "label": "Injury, poisoning and certain other consequences of external causes", "level": "chapter", "chapter": "XIX"},
    {"code": "T36-T50", "label": "Poisoning by drugs, medicaments and biological substances", "level": "sub-chapter", "chapter": "XIX"},
    {"code": "T40",     "label": "Poisoning by narcotics and psychodysleptics (opioids, heroin, fentanyl)", "level": "sub-chapter", "chapter": "XIX"},
    {"code": "T51-T65", "label": "Toxic effects of substances chiefly nonmedicinal as to source", "level": "sub-chapter", "chapter": "XIX"},

    # -----------------------------------------------------------------------
    # Chapter XX — External causes of morbidity (V00–Y99)
    # -----------------------------------------------------------------------
    {"code": "V00-Y99", "label": "External causes of morbidity and mortality", "level": "chapter", "chapter": "XX"},
    {"code": "V01-V99", "label": "Transport accidents", "level": "sub-chapter", "chapter": "XX"},
    {"code": "V02-V04", "label": "Pedestrian injured in transport accident", "level": "sub-chapter", "chapter": "XX"},
    {"code": "V20-V29", "label": "Motorcycle rider injured in transport accident", "level": "sub-chapter", "chapter": "XX"},
    {"code": "V40-V49", "label": "Car occupant injured in transport accident", "level": "sub-chapter", "chapter": "XX"},
    {"code": "W00-W19", "label": "Falls", "level": "sub-chapter", "chapter": "XX"},
    {"code": "W65-W74", "label": "Accidental drowning and submersion", "level": "sub-chapter", "chapter": "XX"},
    {"code": "W85-W99", "label": "Exposure to electric current, radiation and extreme temperature/pressure", "level": "sub-chapter", "chapter": "XX"},
    {"code": "X00-X09", "label": "Exposure to smoke, fire and flames", "level": "sub-chapter", "chapter": "XX"},
    {"code": "X40-X49", "label": "Accidental poisoning by and exposure to noxious substances", "level": "sub-chapter", "chapter": "XX"},
    {"code": "X60-X84", "label": "Intentional self-harm (suicide)", "level": "sub-chapter", "chapter": "XX"},
    {"code": "X85-Y09", "label": "Assault (homicide)", "level": "sub-chapter", "chapter": "XX"},
    {"code": "Y10-Y34", "label": "Event of undetermined intent", "level": "sub-chapter", "chapter": "XX"},
    {"code": "Y35-Y38", "label": "Legal intervention, operations of war and terrorism", "level": "sub-chapter", "chapter": "XX"},

    # -----------------------------------------------------------------------
    # Chapter XXI — Factors influencing health status (Z00–Z99)
    # -----------------------------------------------------------------------
    {"code": "Z00-Z99", "label": "Factors influencing health status and contact with health services", "level": "chapter", "chapter": "XXI"},

    # -----------------------------------------------------------------------
    # Chapter XXII — Codes for special purposes (U00–U85)
    # -----------------------------------------------------------------------
    {"code": "U00-U85", "label": "Codes for special purposes", "level": "chapter", "chapter": "XXII"},
    {"code": "U07",     "label": "Emergency use of U07 — COVID-19 (U07.1) and related codes", "level": "sub-chapter", "chapter": "XXII"},
    {"code": "U07.1",   "label": "COVID-19", "level": "special", "chapter": "XXII"},
]


def get_icd10_codes(search_term: Optional[str] = None) -> list[dict]:
    """
    Search the local ICD-10-CM chapter/sub-chapter lookup table.

    Returns entries matching the search term in either their code or label.
    If no search_term is provided, returns all entries (chapters and sub-chapters).

    Each result includes:
      - code: ICD-10 code or range (e.g. "I20-I25", "T40", "U07.1")
      - label: descriptive name
      - level: "chapter" | "sub-chapter" | "special"
      - chapter: Roman numeral chapter (e.g. "IX")
      - wonder_group_by_chapter: B_ value to group by chapter in query_wonder
      - wonder_group_by_subchapter: B_ value to group by sub-chapter in query_wonder
      - wonder_filter_key: V_ parameter key to filter by this code in query_wonder
      - wonder_filter_value: suggested value to pass as the filter (the code/range)

    Usage in query_wonder:
      filters={"D76.V2": "I20-I25"}   # filter to ischaemic heart diseases

    Args:
        search_term: Optional case-insensitive string to filter by code or label.
                     Supports partial matches (e.g. "heart", "T40", "alzheimer").

    Returns:
        List of matching ICD-10 entry dicts, sorted by chapter then code.
    """
    if search_term:
        term = search_term.lower().strip()
        results = [
            e for e in _ICD10_TABLE
            if term in e["code"].lower() or term in e["label"].lower()
        ]
    else:
        results = list(_ICD10_TABLE)

    # Annotate each result with WONDER usage hints
    annotated = []
    for e in results:
        annotated.append({
            **e,
            "wonder_group_by_chapter": "D76.V2-level1",
            "wonder_group_by_subchapter": "D76.V2-level2",
            "wonder_filter_key": "D76.V2",
            "wonder_filter_value": e["code"],
            "note": (
                "Use wonder_filter_key + wonder_filter_value in the filters dict of query_wonder. "
                "Exact WONDER filter codes may differ slightly from ICD-10 ranges — "
                "verify via get_database_variables('D76') or the WONDER web UI."
            ),
        })

    return annotated
