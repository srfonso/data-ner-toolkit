# settings.py

# Global timeout for service requests in seconds.
MAX_TIMEOUT_SERVICES = 1800

# Default settings for the tool.
DEFAULT_ENDPOINT = "http://ner.localhost:65430/ner"
DEFAULT_APIKEY = "cewi3423e3w"
DEFAULT_MAX_DATA_BY_REQUEST = 500
DEFAULT_MAX_PARALLEL_REQUESTS = 4*2 # Nºworkers*Nºcontainers
DEFAULT_BATCH_SIZE = 5
DEFAULT_CHECKPOINT_FREQUENCY = 10000 # Each N items
DEFAULT_CHECKPOINT_FOLDER = ".checkpoints"
DEFAULT_RESULT_FOLDER = "results"

# Logger settings.
LOG_DIR = ".logs"