import os

MODEL_API_URL = os.environ.get('MODEL_API_URL', '').rstrip('/')
MODEL_API_KEY = os.environ.get('MODEL_API_KEY', '')
MODEL_ID = os.environ.get('MODEL_ID', 'mock')
MODELS = tuple(m.strip() for m in os.environ.get('MODELS', 'mlp,cnn,resnet18').split(',') if m.strip())
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'resnet18')
MODEL_TIMEOUT_SECONDS = float(os.environ.get('MODEL_TIMEOUT_SECONDS', '20'))
MAX_IMAGE_BYTES = int(os.environ.get('MAX_IMAGE_BYTES', str(4 * 1024 * 1024)))

CACHE_ENDPOINT = os.environ.get('CACHE_ENDPOINT', '')
CACHE_NAME = os.environ.get('CACHE_NAME', 'isitai-cache')
CACHE_USER = os.environ.get('CACHE_USER', 'default.iam-user')
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', '86400'))
HISTORY_TABLE = os.environ.get('HISTORY_TABLE', '')
HISTORY_RETENTION_DAYS = int(os.environ.get('HISTORY_RETENTION_DAYS', '30'))
