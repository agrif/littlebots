#!/usr/bin/env python3.3

import sys
import asyncio
import json
import random
import time

from uuid import uuid1 as uuid

class BotProtocol:
    def __init__(self):
        self.t = None
        self.connected = False
        self.exc = None
        self.queue = []
        
    def connection_made(self, transport):
        self.t = transport
        self.stdin = transport.get_pipe_transport(0)
        self.connected = True
    
    def connection_lost(self, exc):
        self.connected = False
        if not self.exc:
            self.exc = exc
        for fut in self.queue:
            fut.cancel()
        self.queue = []
    
    def pipe_connection_lost(self, fd, exc):
        pass
    
    def process_exited(self):
        pass
    
    def kill(self, exc=None):
        if not self.connected:
            return
        
        self.exc = exc
        self.t.terminate()
        self.connected = False
    
    def pipe_data_received(self, fd, data):
        if fd == 2:
            try:
                data = data.decode('utf-8').splitlines()
                for d in data:
                    print("bot", self.t.get_pid(), d)
            except UnicodeDecodeError:
                pass
        if fd != 1:
            return
        
        try:
            data = data.decode('utf-8', errors='strict').splitlines()
        except UnicodeDecodeError as e:
            return self.kill(e)
        
        try:
            commands = [json.loads(s) for s in data]
        except ValueError as e:
            return self.kill(e)
        
        for c in commands:
            if not self.queue:
                return self.kill(RuntimeError("unexpected response"))
            fut = self.queue.pop(0)
            fut.set_result(c)
    
    def _send(self, data, returns, timeout):
        if not self.connected:
            raise RuntimeError("not connected")
        data = json.dumps(data).encode('utf-8') + b'\n'
        fut = None
        if returns:
            fut = asyncio.Future()
            self.queue.append(fut)
        self.stdin.write(data)
        
        def check_error_callback(f):
            e = f.exception()
            if e:
                self.kill(e)
        
        if fut:
            if timeout:
                fut = asyncio.async(asyncio.wait_for(fut, timeout))
            fut.add_done_callback(check_error_callback)
        
        return fut
    
    @asyncio.coroutine
    def send(self, data, returns=False, timeout=None, default=None):
        try:
            if returns:
                result = yield from self._send(data, returns=returns, timeout=timeout)
            else:
                self._send(data, returns=returns, timeout=timeout)
                result = default
        except Exception as e:
            result = default
        return result

class Bot:
    def __init__(self, prot, player_id, hp):
        self.prot = prot
        self.location = None
        self.hp = hp
        self.player_id = player_id
        # FIXME better robot id!
        self.robot_id = hash(uuid().hex) & 0xffffffff
    
    @property
    def bot_info(self):
        return {
            'location': self.location,
            'hp': self.hp,
            'player_id': self.player_id,
            'robot_id': self.robot_id,
        }
    
    @classmethod
    @asyncio.coroutine
    def launch(cls, subname, player_id, hp):
        loop = asyncio.get_event_loop()
        _, prot = yield from loop.subprocess_shell(BotProtocol, subname)
        return cls(prot, player_id, hp)
    
    def _verify_step(self, act):
        try:
            name = act[0]
            if name == 'move' or name == 'attack':
                _, (x, y) = act
                x = int(x)
                y = int(y)
                
                lx, ly = self.location
                dist = (lx - x)**2 + (ly - y)**2
                if dist != 1:
                    return None
                return [name, (x, y)]
            elif name == 'guard' or name == 'suicide':
                if len(act) == 1:
                    return [name]
                return None
            else:
                return None
        except Exception:
            return None
    
    @asyncio.coroutine
    def setup(self, world):
        world_info = {
            'width': world.width,
            'height': world.height,
        }
        yield from self.prot.send(world_info)
    
    @asyncio.coroutine
    def step(self, world):
        data = {}
        bots = []
        for bot in world.bots.values():
            bots.append(bot.bot_info)
        data['robots'] = bots
        data['turn'] = world.turn
        data['self'] = self.bot_info
        
        r = yield from self.prot.send(data, returns=True, timeout=0.3, default=['guard'])
        r = self._verify_step(r)
        if r is None:
            r = ['guard']
        return r
    
    def kill(self):
        self.hp = 0
        self.prot.kill()

TILE_BLOCKED, TILE_SPAWN = range(2)

class World:
    def __init__(self, tracer=None, attack_damages=[8, 9, 10], collision_damages=[5], suicide_damages=[15]):
        self.attack_damages = attack_damages
        self.collision_damages = collision_damages
        self.suicide_damages = suicide_damages
        self.bots = {}
        self.turn = 0
        self.tracer = tracer
        self.width, self.height, self.map = self.generate_map()
        self.spawns = self.iterate_spawns()
        
    def generate_map(self):
        width = 19
        height = 19
        cx = width / 2 - 0.5
        cy = height / 2 - 0.5
        radius = min([cx, cy])
        m = {}
        for y in range(height):
            for x in range(width):
                dist = (x - cx)**2 + (y - cy)**2
                if dist < (radius - 1)**2:
                    continue
                elif (radius - 1)**2 <= dist and dist < radius**2:
                    m[(x, y)] = TILE_SPAWN
                else:
                    m[(x, y)] = TILE_BLOCKED
        return (width, height, m)
    
    def iterate_spawns(self):
        spawns = []
        for loc, tile in self.map.items():
            if tile == TILE_SPAWN:
                spawns.append(loc)
        while True:
            yield random.choice(spawns)
    
    def trace(self, func, *args):
        if not self.tracer:
            return
        func = getattr(self.tracer, func, None)
        if not func:
            return
        func(self, *args)
    
    @asyncio.coroutine
    def add(self, bot):
        # put the bot on a spawn point
        spawn = next(self.spawns)
        try:
            ibot = self.bots[spawn]
            ibot.kill()
            del self.bots[spawn]
            self.trace('kill', ibot)
        except KeyError:
            pass
        
        bot.location = spawn
        self.bots[spawn] = bot
        self.trace('spawn', bot)
        yield from bot.setup(self)
    
    @asyncio.coroutine
    def launch(self, subname, player_id, hp=50):
        bot = yield from Bot.launch(subname, player_id, hp)
        yield from self.add(bot)
        return bot
    
    @asyncio.coroutine
    def step(self):
        bots = self.bots.values()
        resultlist = yield from asyncio.gather(*[bot.step(self) for bot in bots])
        results = dict(zip(bots, resultlist))
        
        # damage helper
        def damage(bot, amounts, sources=[], guard_blocks_all=False):
            if sources and all(bot.player_id == s.player_id for s in sources):
                # friendly fire disabled
                return
            
            guarding = (results[bot][0] == 'guard')
            if guarding and guard_blocks_all is None:
                return
            
            amount = random.choice(amounts)
            if guarding:
                amount = int(amount / 2)
            bot.hp -= amount
            if bot.hp < 0:
                bot.hp = 0
        
        # resolve all movement first
        while True:
            nextbots = {}
            for bot, act in results.items():
                if not act[0] == 'move':
                    cur = nextbots.get(bot.location)
                    if not cur:
                        cur = list()
                    cur.append(bot)
                    nextbots[bot.location] = cur
                    continue
                
                _, pos = act
                pos = tuple(pos)
                
                cur = nextbots.get(pos)
                if not cur:
                    cur = list()
                cur.append(bot)
                nextbots[pos] = cur
            
            # now nextbots is a mapping from location to a list of bots in
            # that position
            foundcollision = False
            for loc, locbots in nextbots.items():
                if len(locbots) != 1:
                    # collision!
                    foundcollision = True
                    for bot in locbots:
                        # cancel movements for bots that collide
                        if results[bot][0] == 'move':
                            results[bot] = ['cancelled']
                        # damage the bot
                        damage(bot, self.collision_damages, sources=locbots, guard_blocks_all=True)
            
            # if there were no collisions, finalize the movements
            if not foundcollision:
                self.bots = {}
                for loc, locbots in nextbots.items():
                    bot = locbots[0]

                    if results[bot][0] == 'move':
                        self.trace('move', bot, loc)
                    bot.location = tuple(loc)
                    self.bots[loc] = bot
                break
        
        # resolve attacks and suicides
        for bot, act in results.items():
            if act[0] == 'attack':
                _, loc = act
                loc = tuple(loc)
                
                if loc in self.bots:
                    d = random.choice([8, 9, 10])
                    damage(self.bots[loc], self.attack_damages, sources=[bot])
                self.trace('attack', bot, loc)
            elif act[0] == 'suicide':
                x, y = bot.location
                adjacents = [
                    (x+1, y),
                    (x, y+1),
                    (x-1, y),
                    (x, y-1),
                ]
                for loc in adjacents:
                    if loc in self.bots:
                        damage(self.bots[loc], self.suicide_damages, sources=[bot])
                bot.hp = 0
                self.trace('suicide', bot)
        
        # remove dead bots from play
        deadlocs = []
        for loc, bot in self.bots.items():
            if bot.hp <= 0:
                bot.kill()
                deadlocs.append(loc)
                self.trace('kill', bot)
        for loc in deadlocs:
            del self.bots[loc]
        
        # end of turn trace
        self.trace('step')
        self.turn += 1
        
        return bool(self.bots)
    
    def close(self):
        for bot in self.bots.values():
            bot.kill()
            self.trace('kill', bot)
        self.bots = {}

class DebugTracer:
    def kill(self, world, bot):
        print(bot.robot_id, "killed at", bot.location)
    def spawn(self, world, bot):
        print(bot.robot_id, "spawned at", bot.location)
    def move(self, world, bot, loc):
        print(bot.robot_id, "moving from", bot.location, "to", loc)
    def attack(self, world, bot, loc):
        print(bot.robot_id, "attacking from", bot.location, "to", loc)
    def suicide(self, world, bot):
        print(bot.robot_id, "suiciding at", bot.location)
    def step(self, world):
        print("end of turn", world.turn)

class SimpleMapTracer:
    def step(self, world):
        print("turn", world.turn)
        for y in range(19):
            for x in range(19):
                bot = world.bots.get((x, y))
                if bot is None:
                    tile = world.map.get((x, y))
                    if tile == TILE_BLOCKED:
                        print('XXX ', end='')
                    elif tile == TILE_SPAWN:
                        print('--- ', end='')
                    else:
                        print('    ', end='')
                else:
                    team = ['a', 'b'][bot.player_id - 1]
                    hp = str(bot.hp)
                    while len(hp) < 2:
                        hp = '0' + hp
                    hp = hp[-2:]
                    print(team + hp + ' ', end='')
            print()
        print()
        time.sleep(1)

@asyncio.coroutine
def main(worldcls=World):
    subname1 = sys.argv[1]
    subname2 = sys.argv[2]
    world = worldcls(tracer=SimpleMapTracer())
    
    player1 = 1
    player2 = 2
    
    while world.turn < 100:
        if world.turn % 10 == 0:
            # add 5 robots for each team
            for _ in range(5):
                yield from world.launch(subname1, player1)
                yield from world.launch(subname2, player2)
                    
        running = yield from world.step()
    
    world.close()
    
    return 0

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    ret = loop.run_until_complete(main())
    loop.close()
    sys.exit(ret)
