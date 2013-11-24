littlebots
==========

Littlebots is a language-agnostic re-implementation of
[robotgame.org][], using JSON to talk to individual bot processes over
stdio.

To run the littlebots simulator (written in Python), you'll need
Python 3.3 or later. If you're running 3.3 exactly, you'll also need
the [asyncio][] module.

 [robotgame.org]: http://robotgame.org/
 [asyncio]: http://code.google.com/p/tulip/
 
Quick Start
-----------
 
 You can run two test bots against each other with
 
     python3.3 littlebots.py ./testbot.py ./testbot.py

To write your own Python bots, read testbot.py and the documentation
for [robotgame.org][]. The `rg` module included in this source is
exactly the same as the one used on [robotgame.org][], and the
`littlerg` module provides a thin compatibility layer.

For other languages, know that the server sends one introductory line
of JSON right after the process is started. Then it repeatedly sends
lines of world state, which expect an action in return (within
300ms). All things written to stderr are reprinted by the server.

Example JSON
------------

Here's an example of the first line sent to each process:

~~~~
{
    "height": 19,
	"width": 19,
	"settings": {
	    "robot_hp": 50,
		"spawn_every": 10,
		"max_turns": 100,
		"spawn_per_player": 5,
		"collision_damages": [5],
		"attack_damages": [8, 9, 10],
		"suicide_damages": [15]
	},
	"blocks": [ list of [x, y] pairs ],
	"spawns": [ list of [x, y] pairs ]
}
~~~~

Here's an example of world state:

~~~~
{
    "robots": [
	  {
		"player_id": 1,
		"location": [1, 5],
		"robot_id": 0,
		"hp": 50
	  },
	  ... more like that ...
	  ],
	"turn": 0,
	"local": {
	    "player_id": 2,
		"location": [5, 16],
		"robot_id": 676734496,
		"hp": 50
	}
}
~~~~

Note that robots with a different `player_id` than your local robot
have a useless `robot_id` field.

In response to each of these, you need to send an action, which is one of these:

~~~~
["move", [x, y]]
["attack", [x, y]]
["guard"]
["suicide"]
~~~~

Positions for move and attack are absolute, and will fail unless they
are exactly one square away from your current position.
