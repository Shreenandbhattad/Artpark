import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DOMAIN", "environment")
os.environ.setdefault("PROVIDER", "mock")
os.environ.setdefault("DATA_ROOT", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
os.environ.setdefault("IMAGE_TAG", "test")
