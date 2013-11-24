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
