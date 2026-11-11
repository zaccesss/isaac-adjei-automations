# make the scraper package importable when pytest is run from anywhere in the repo: it
# lives in jobs/scraper, so jobs/ goes on the path.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs"))
