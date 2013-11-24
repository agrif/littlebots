import json
import sys
from collections import MutableMapping

import rg

class AttrDict(MutableMapping):
    def __init__(self, *args, **kwargs):
        self.__dict__.update(*args, **kwargs)
    def __getitem__(self, key):
        return self.__getattribute__(key)
    def __setitem__(self, key, val):
        self.__setattr__(key, val)
    def __delitem__(self, key):
        self.__delattr__(key)
    def __iter__(self):
        return iter(self.__dict__)
    def __repr__(self):
        return repr(self.__dict__)
    def __len__(self):
        return len(self.__dict__)

def recv():
    return json.loads(input())

def send(o):
    print(json.dumps(o))

def debug(*args):
    print(*args, file=sys.stderr)

def runrobot(factory):
    r = factory()
    
    worldinfo = recv()
    width = worldinfo['width']
    height = worldinfo['height']
    
    rg.CENTER_POINT = (int(width / 2), int(height / 2))
    
    while True:
        world = recv()
        
        robots = {}
        for bot in world['robots']:
            bot['location'] = tuple(bot['location'])
            robots[tuple(bot['location'])] = AttrDict(bot)
        world['robots'] = robots
        
        for attr, val in world['local'].items():
            setattr(r, attr, val)
        r.location = tuple(r.location)
        
        result = r.act(AttrDict(world))
        send(result)
