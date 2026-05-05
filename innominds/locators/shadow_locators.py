import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IMAGES_DIR = os.path.join(BASE_DIR, "testdata", "images")

OPEN_EULA_BTN = os.path.join(IMAGES_DIR, "open_eula.png")
EULA_LABEL_ANCHOR = os.path.join(IMAGES_DIR, "eula_label_anchor.png")
ACCEPT_EULA_BTN = os.path.join(IMAGES_DIR, "accept_eula.png")

# Screen focus helpers (relative clicks)
NOTIFICATION_RELATIVE_X = 0.86
NOTIFICATION_RELATIVE_Y = 0.91
FOCUS_CLICK_X = 400
FOCUS_CLICK_Y = 300
