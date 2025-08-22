"""
config.py: Configuration values. Secrets to be handled with Secrets Manager
"""

import logging
import socket

SKID_NAME = "nfhl_skid"

AGOL_ORG = "https://utah-em.maps.arcgis.com"
SENDGRID_SETTINGS = {  #: Settings for SendGridHandler
    "from_address": "noreply@utah.gov",
    "to_addresses": ["ugrc-developers@utah.gov", "hstrand@utah.gov"],
    "prefix": f"{SKID_NAME} on {socket.gethostname()}: ",
}
LOG_LEVEL = logging.INFO
LOG_FILE_NAME = "log"

TIMEOUT = 20
SERVICE_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
DFIRM_WHERE = "DFIRM_ID LIKE '49%'"
LAT_LON_WHERE = "LAT > 36.95 and LAT < 42.05 AND LON > -114.05 AND LON < -109.04 AND NOT (LAT > 41 AND LON >-111.05)"
FEMA_LAYERS = {
    "S_LOMR": {
        "number": 1,
        "itemid": "647c5dfc31044b0aba7611f0b7b3ed62",
        "name": "S_LOMR",
        "date_fields": ["eff_date"],
        "where_clause": DFIRM_WHERE,
    },
    "S_FIRM_Pan": {
        "number": 3,
        "itemid": "cb041caea3ad4b48bef4502e10e14368",
        "name": "S_FIRM_Pan",
        "date_fields": ["pre_date", "eff_date"],
        "where_clause": DFIRM_WHERE,
    },
    "S_XS": {
        "number": 14,
        "itemid": "4c87be2e986643e2b82b787d630c83a6",
        "name": "S_XS",
        "double_fields": ["stream_stn", "wsel_reg", "strmbed_el"],
        "int_fields": ["seq"],
        "where_clause": DFIRM_WHERE,
    },
    "S_BFE": {
        "number": 16,
        "itemid": "8cab946b96d94167bd75314c32584d1a",
        "name": "S_BFE",
        "double_fields": ["elev"],
        "where_clause": DFIRM_WHERE,
    },
    "S_PROFIL_BASLN": {
        "number": 17,
        "itemid": "c0e92cf18ed14dc883b5ce9cae69e288",
        "name": "S_PROFIL_BASLN",
        "where_clause": DFIRM_WHERE,
    },
    "S_Wtr_Ln": {
        "number": 20,
        "itemid": "f784f6c8b32a4f7abe180c4e37ffb8d6",
        "name": "S_Wtr_Ln",
        "where_clause": DFIRM_WHERE,
    },
    "S_LEVEE": {
        "number": 23,
        "itemid": "295a02bbe0694dbfb5c827e073df2f9e",
        "name": "S_LEVEE",
        "date_fields": ["const_date", "pal_date"],
        "double_fields": ["freeboard"],
        "where_clause": DFIRM_WHERE,
    },
    "S_Fld_Haz_Ar": {
        "number": 28,
        "itemid": "b2c606f13a4c4a59b3c253647883833f",
        "name": "S_Fld_Haz_Ar",
        "double_fields": ["static_bfe", "depth", "velocity", "bfe_revert", "dep_revert"],
        "where_clause": DFIRM_WHERE,
    },
    "S_LOMAs": {
        "number": 34,
        "itemid": "db07fd59e21846a993c32b1d048ba38f",
        "name": "S_LOMAs",
        "date_fields": ["dateended"],
        "where_clause": LAT_LON_WHERE,
        "double_fields": ["lat", "lon"],
    },
}
