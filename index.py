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
parser.add_argument('final_output')
parser.add_argument('intermediate_output')
parser.add_argument('tour_name')

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
        link = row.find('a')
        results.append({
            'truncId': row.contents[1].string.strip(),
            'firstName': row.contents[3].string.strip(),
            'lastName': row.contents[5].string.strip(),
            'name': f"{row.contents[3].string.strip()} {row.contents[5].string.strip()}",
            'country': row.contents[7].string.strip(),
            'trainerName': row.contents[13].string.strip(),
            'teamlist': f"https://rk9.gg{link['href']}" if link is not None else "",
        })

    return results


def compare_records(a, b):
    if a['truncId'] != b['truncId']:
        return False
    if a['name'] != b['name']:
        return False
    if a['country'] != b['country']:
        return False
    if a['trainerName'] != b['trainerName']:
        return False
    return True


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


def mon_to_paste(mon):
    name_part = mon['species'] if mon.get('name', None) is None else f"{mon['name']} ({mon['species']})"
    first_line = name_part if mon.get('item', None) is None else f"{name_part} @ {mon['item']}"
    moves = '\r\n'.join([f"- {move}" for move in mon['moves']])

    return f"{first_line}\r\nAbility: {mon['ability']}\r\nTera Type: {mon['teraType']}\r\n{moves}"


def team_to_paste(team):
    return "\r\n\r\n".join([mon_to_paste(mon) for mon in team])


def remove_country(name):
    return name.split('[')[0].strip()


def make_pokepaste(player, tour_name):
    paste_name = f"{remove_country(player['name'])}'s {tour_name} Open Team List"
    author = "VGCPastes"
    paste_description = "Format: gen9vgc2024regulationf"
    paste = team_to_paste(player['fullTeam'])
    payload = {
        'title': paste_name,
        'paste': paste,
        'author': author,
        'notes': paste_description
    }
    response = requests.post('https://pokepast.es/create', data=payload)
    return response.url


def are_teamlists_available(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    for result in soup.tbody.find_all('i', class_='fal fa-lg fa-list-alt'):
        for string in result.parent.stripped_strings:
            if string == 'View':
                return True
    return False


if __name__ == '__main__':
    with open(args.players, 'r') as infile:
        players = json.load(infile)

    roster_players = get_players(f"https://rk9.gg/roster/{args.url}")

    players_out = {'matched': {}, 'unmatched': {}}
    try:
        with open(args.intermediate_output, 'r') as infile:
            players_out = json.load(infile)
    except FileNotFoundError:
        pass

    # remove loaded players from roster and pairings
    for i in players_out['matched']:
        current_player = players_out['matched'][i]
        record = [p for p in roster_players if compare_records(current_player['rosterInfo'], p)][0]
        roster_players.remove(record)
        current_player['rosterInfo'] = record

    players_left = [i for i in players if i not in players_out['matched']]

    # match players from pairings and roster
    # list comprehension so we can update the array while iterating
    for i in [player for player in players_left]:
        candidates = [p for p in roster_players
                      if players[i]['name'].lower() == f"{p['name']} [{p['country']}]".lower()]
        if len(candidates) == 1:
            players_out['matched'][i] = {
                'name': players[i]['name'],
                'rosterInfo': candidates[0]
            }
            roster_players.remove(candidates[0])
            players_left.remove(i)

    # some players lose their country code
    for i in [player for player in players_left]:
        candidates = [p for p in roster_players if players[i]['name'].lower() == p['name'].lower()]
        if len(candidates) == 1:
            players_out['matched'][i] = {
                'name': players[i]['name'],
                'rosterInfo': candidates[0]
            }
            roster_players.remove(candidates[0])
            players_left.remove(i)

    # see if the remining players are a gimme
    if len(players_left) == 1:
        player_id = players_left[0]
        players_out['matched'][player_id] = {
            'name': players[player_id]['name'],
            'rosterInfo': roster_players[0]
        }
        roster_players = []
        players_left = []

    if len(players_left) == 0 and are_teamlists_available(f"https://rk9.gg/roster/{args.url}"):
        # upload pastes
        for player_id in players_out['matched']:
            player = players_out['matched'][player_id]
            if player['rosterInfo']['teamlist'] != "" and player.get('paste') is None:
                player_team = get_team(player['rosterInfo']['teamlist'])
                player['team'] = [pokemon['species'] for pokemon in player_team]
                player['fullTeam'] = player_team
                player['paste'] = make_pokepaste(player, args.tour_name)

        teams_out = {
            player_id: {
                'name': players_out['matched'][player_id]['name'],
                'team': [mon['species'] for mon in players_out['matched'][player_id]['fullTeam']],
                'paste': players_out['matched'][player_id]['paste'],
                'fullTeam': players_out['matched'][player_id]['fullTeam'],
            } for player_id in players_out['matched'] if players_out['matched'][player_id].get('paste') is not None
        }
        if len(players_out['matched']) == len(teams_out):
            with open(args.final_output, 'w') as outfile:
                json.dump(teams_out, outfile, indent=2, ensure_ascii=False)
    else:
        for player_id in players_left:
            print(f"not found: {players[player_id]['name']}")

    with open(args.intermediate_output, 'w') as outfile:
        json.dump({
            'matched': players_out['matched'],
            'unmatched': {
                'roster': {{'rosterInfo': player} for player in roster_players},
                'pairings': {i: {'name': players[i]['name']} for i in players_left}
            }
        }, outfile, indent=2, ensure_ascii=False)
