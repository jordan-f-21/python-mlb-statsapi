import mlbstatsapi
from pprint import pprint
from flask import Flask, render_template, request, Response

mlb = mlbstatsapi.Mlb()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def getID(name):
    return mlb.get_people_id(name)[0]

#    PLAYER ID AND PLAYER OBJECT
mikeTroutID = getID("Mike Trout")
calRaleighID = mlb.get_people_id('Cal Raleigh')[0]
claytonKershawID = mlb.get_people_id('Clayton Kershaw')[0]
#person_object = mlb.get_person(mikeTroutID)
#pprint(person_object.__dict__)

#    TEAM ID AND TEAM OBJECT AND ROSTER
"""
giantsID = mlb.get_team_id('San Francisco Giants')[0]
team_object = mlb.get_team(giantsID)
team_roster = mlb.get_team_roster(giantsID)
print(team_object.__dict__)
for player in team_roster:
    name = getattr(player, "fullname", "Unknown")
    num = getattr(player, "jerseynumber", None)
    pos = getattr(player, "primaryposition", None)
    print(name + "   " + num + "   " + str(pos) + "\n")
"""

#     PLAYER STATS OBJECT

"""
stats = ['season', 'career']
groups = ['hitting', 'pitching', 'fielding', 'catching']

player_stats = mlb.get_player_stats(getID("Mike Trout"), stats, groups)
hitting_stats = player_stats["hitting"]["season"]
split = hitting_stats.splits[0]
for key, value in vars(split.stat).items():
    print(key + "  =  " + str(value))

"""


#      GAMEPACE OBJECT GIVING GAME STATISTICS
"""
gameData = mlb.get_gamepace("2024")
print(gameData)
"""

#      SCHEDULE OBJECT
"""
schedule = mlb.get_schedule('2024-9-15')
print(schedule)
"""

#     SEASON OBJECT
"""
season = mlb.get_season("2023")
print(season)
"""

#   LEAGUE STANDINGS
"""
aL = mlb.get_league_id("National League")
nL = mlb.get_league_id("American League")
aL_Stadings = mlb.get_standings(aL,"2023")
nL_Stadings = mlb.get_standings(nL,"2023")
print(aL_Stadings)
print(nL_Stadings)
"""

if __name__ == '__main__':
    app.run(debug=True)