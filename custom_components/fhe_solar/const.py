DOMAIN = "fhe_solar"
PLATFORMS = ["sensor"]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_HOME_ID = "home_id"
CONF_TOKEN = "token"

API_BASE = "https://api.fhe.fhe-france.fr/fhemaster/v2"
DEFAULT_SCAN_INTERVAL_ACTIVE = 5         # Sekunden wenn Produktion vorhanden
DEFAULT_SCAN_INTERVAL_IDLE = 1800         # Sekunden nachts/ohne Produktion
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

ATTR_SERIALS = "serials"