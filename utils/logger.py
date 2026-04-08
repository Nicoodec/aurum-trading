import logging, os, sys
from config import LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)
def get_logger(name='aurum'):
    log = logging.getLogger(name)
    if log.handlers: return log
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh = logging.FileHandler(os.path.join(LOG_DIR, 'aurum.log'), encoding='utf-8')
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(fh); log.addHandler(sh)
    return log
log = get_logger()