import csv
import os
import json
from tempfile import NamedTemporaryFile
import shutil

CONFIG_PATH = './data/config.json'
PLAYER_LIST_FILENAME = './data/player_list.txt'

PLAYER_LIST_FIELDS = ['name', 'cardname', 'rating', 'team', 'nation', 'cardtype', 'position',
           'internal_id', 'futbin_id', 'price', 'lastupdated', 'market_price', 'buy_pct',
           'buy_price_override', 'sell_price_override']

TABLE_LIST_FIELDS = ['cardname', 'rating', 'price', 'market_price', 'buy_ceiling',
'sell_ceiling', 'buy_price_override', 'sell_price_override']


def config_exists():
    if (not os.path.exists(CONFIG_PATH)):
        return False

    with open('./data/config.json', 'r', encoding='utf8') as f:
        try:
            json.load(f)
        except Exception:
            return False

    return True

def add_or_update_player_list_file(player_info: list):
    entry_dict = { PLAYER_LIST_FIELDS[i] : player_info[i] for i in range(len(PLAYER_LIST_FIELDS)) }

    tempfile = NamedTemporaryFile(mode='w', encoding='utf8', delete=False)
    is_update = False

    with open(PLAYER_LIST_FILENAME, 'r', encoding='utf8') as file, tempfile:
        reader = csv.DictReader(file, fieldnames=PLAYER_LIST_FIELDS)
        writer = csv.DictWriter(tempfile, fieldnames=PLAYER_LIST_FIELDS)
        for row in reader:
            if row['futbin_id'] == entry_dict['futbin_id']:
                print('Updating player: ' + row['name'])
                is_update = True
                row = entry_dict
            writer.writerow(row)

    if is_update:
        shutil.move(tempfile.name, PLAYER_LIST_FILENAME)
    else:
        full_entry = ','.join(player_info)
        print('Adding player: ' + full_entry)

        # Add new line to end
        hs = open(PLAYER_LIST_FILENAME, 'a', encoding='utf8')
        hs.write(full_entry + "\n")
        hs.close()

def find_player_in_list_file(player_id: str):
    with open(PLAYER_LIST_FILENAME, 'r', encoding='utf8') as file:
        reader = csv.DictReader(file, fieldnames=PLAYER_LIST_FIELDS)
        for row in reader:
            if row['futbin_id'] == player_id:
                return list(row.values())
    return None

def get_player_list():
    player_list = []
    with open(PLAYER_LIST_FILENAME, 'r', encoding='utf8') as file:
        reader = csv.DictReader(file, fieldnames=PLAYER_LIST_FIELDS)
        for row in reader:
            player_info = list(row.values())
            player_list.append(player_info)
    return player_list
