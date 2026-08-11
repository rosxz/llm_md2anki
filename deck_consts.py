# Path to the root directory of your markdown notes
ROOT = ""

# Mapping of deck names to markdown directories
DECKS = {
    # deck name : markdown directory path
    "KUBE": "notes"  # deck name is math::math241, markdown directory path is @2.1/math241
}

# automatically builds full key/value path mapping
DECKS = {k: ROOT + v for k, v in DECKS.items()}
# if the title of the markdown file contains any of these keywords, it will be ignored. It will also be ignored if it starts with "_"
IGNORE_KEYWORDS = "discussion"
# output directory for any errors
OUTPUT_DIR = ""
