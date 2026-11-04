"""A hand-written theme spec, used by tests and the offline demo in place of a model reply."""

POKEMON = {
    "title": "Pokedex Explorer",
    "story": "Professor Oak's lab computer crashed, and the Pokedex data is scattered across three regions. "
             "Help the professor find Pokemon by region, spot the powerful and speedy ones, and build a "
             "report for new trainers.",
    "entity_singular": "pokemon",
    "entity_plural": "pokemon",
    "table": "pokedex",
    "group_column": "region",
    "group_description": "The region where the Pokemon is found",
    "groups": ["Kanto", "Johto", "Hoenn"],
    "number_column": "dex_number",
    "name_column": "name",
    "metric_a": {"column": "attack", "label": "powerful", "unit": "points",
                 "description": "Attack stat", "minimum": 10, "maximum": 190, "threshold": 100},
    "metric_b": {"column": "speed", "label": "speedy", "unit": "points",
                 "description": "Speed stat", "minimum": 5, "maximum": 160, "threshold": 90},
    "normal_label": "regular",
    "names": {
        "Kanto": ["Bulbasaur", "Charmander", "Squirtle", "Pikachu", "Jigglypuff", "Meowth", "Psyduck",
                  "Machop", "Geodude", "Farfetch'd", "Gengar", "Onix", "Mr. Mime", "Snorlax", "Dratini"],
        "Johto": ["Chikorita", "Cyndaquil", "Totodile", "Togepi", "Mareep", "Marill", "Sudowoodo",
                  "Wooper", "Umbreon", "Murkrow", "Heracross", "Teddiursa", "Phanpy", "Larvitar"],
        "Hoenn": ["Treecko", "Torchic", "Mudkip", "Ralts", "Shroomish", "Aron", "Plusle", "Minun",
                  "Roselia", "Wailmer", "Trapinch", "Swablu", "Absol", "Bagon", "Beldum"],
    },
}
