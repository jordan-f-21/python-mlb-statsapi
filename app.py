import mlbstatsapi

mlb = mlbstatsapi.Mlb()

def getId(name):
    return mlb.get_people_id(name)[0]

player_id = mlb.get_people_id('Mike Trout')[0]

stats = ['season','career']
group = ['hitting']
params = {'season': 2022}

stat_dict = mlb.get_player_stats(player_id, stats=['season'], groups=['hitting'], season=2025)
season_hitting_stat = stat_dict['hitting']['season']
for split in season_hitting_stat.splits:
    for k, v in split.stat.__dict__.items():
        print(k, v)