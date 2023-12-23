#!/usr/bin/env python3
import re
import argparse
import json

import requests
from bs4 import BeautifulSoup

parser = argparse.ArgumentParser(
    prog='RK9 Scraper',
    description='Gets teams from RK9'
)
parser.add_argument('url')
parser.add_argument('players')

args = parser.parse_args()

with open('rk9Formes.json', 'r') as formeList:
    formes = json.load(formeList)


def get_players(url):
    page = requests.get(url)

    soup = BeautifulSoup(page.content, "html.parser")

    results = []

    for row in soup.tbody.find_all('tr'):
        if row.contents[9].string.strip() != "Masters":
            continue
        results.append({
            'name': f"{row.contents[3].string.strip()} {row.contents[5].string.strip()}",
            'country': row.contents[7].string.strip(),
            'teamlist': f"https://rk9.gg{row.find('a')['href']}",
        })

    return results


def get_field(node, label):
    result = None
    label_node = node.find(string=label)
    if label_node is not None:
        result = label_node.parent.next_sibling.string.strip()
    return result


def get_team(url):
    page = requests.get(url)

    soup = BeautifulSoup(page.content, "html.parser")

    teamlist = []

    for mon in soup.find(id="lang-EN").find_all(class_="pokemon"):
        name_items = mon.contents[2].string.strip().split('"')
        species = formes.get(name_items[0].strip(), name_items[0].strip())
        nickname = None
        if len(name_items) > 1:
            nickname = name_items[1].strip()

        item = get_field(mon, 'Held Item:')
        ability = get_field(mon, 'Ability:')
        tera_type = get_field(mon, 'Tera Type:')

        moves = [
            move_node.string.strip() for move_node in mon.find('h5').find_all(class_="badge", string=re.compile(".+"))
        ]

        pokemon_set = {
            'species': species,
            'ability': ability,
            'teraType': tera_type,
            'moves': moves
        }
        if nickname is not None:
            pokemon_set['name'] = nickname
        if item is not None:
            pokemon_set['item'] = item
        teamlist.append(pokemon_set)

    return teamlist


with open(args.players, 'r') as infile:
    players = json.load(infile)

raw_players = get_players(f"https://rk9.gg/roster/{args.url}")
input(f"{len(raw_players)} players. ENTER to continue, Ctrl-C to exit.")

roster_players = []
for player in raw_players:
    print(f"Grabbing {player['name']}'s team...")
    roster_players.append({
        'name': player['name'],
        'country': player['country'],
        'team': get_team(player['teamlist'])
    })

players_out = {}
players_left = []

for i in players:
    candidates = [p for p in roster_players if players[i]['name'] == f"{p['name']} [{p['country']}]"]
    if len(candidates) == 1:
        players_out[i] = {
            'name': players[i]['name'],
            'team': candidates[0]['team']
        }
        roster_players.remove(candidates[0])
    else:
        players_left.append(i)

# some players lose their country code
# list comprehension so we can update the array while iterating
for i in [player for player in players_left]:
    candidates = [p for p in roster_players if players[i]['name'] == p['name']]
    if len(candidates) == 1:
        players_out[i] = {
            'name': players[i]['name'],
            'team': candidates[0]['team']
        }
        roster_players.remove(candidates[0])
        players_left.remove(i)

with open('output/teams.json', 'w') as outfile:
    json.dump(players_out, outfile, indent=2, ensure_ascii=False)

with open('output/unmatched.json', 'w') as outfile:
    json.dump({
        'roster': roster_players
    }, outfile, indent=2, ensure_ascii=False)
