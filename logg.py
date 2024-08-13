import logging
from logging.handlers import RotatingFileHandler
from utils import make_path

logger = logging.getLogger('uplaud')
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(make_path('uplaud.log'), maxBytes=3*1024*1024, backupCount=1)
handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)