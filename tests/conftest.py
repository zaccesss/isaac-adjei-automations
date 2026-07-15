# Make the scraper package importable when pytest is run from anywhere in the repo.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
