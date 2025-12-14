import configparser
import psycopg2
from pathlib import Path


odoo_conf_path = Path(__file__).resolve().parents[4] / 'odoo.conf'
config = configparser.ConfigParser()
config.read(odoo_conf_path)

# db_name = config.get('options', 'db_name')
db_name = "odoo"
db_user = config.get('options', 'db_user')
db_password = config.get('options', 'db_password', fallback=None)
db_host = config.get('options', 'db_host', fallback='localhost')
db_port = config.get('options', 'db_port', fallback='5432')

def get_db_connection():
    """ Get Connection """
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    return conn