from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
import sys
import math


@dataclass(frozen=True)
class Coord:
    x: int
    y: int

    def __repr__(self) -> str:
        return f"{self.x} {self.y}"


@dataclass
class Connection:
    from_id: int
    to_id: int


@dataclass
class Tile:
    region_id: int
    type: int
    tracks_owner: int
    inked: bool
    instability: int
    part_of_active_connections: List[Connection]


@dataclass
class Town:
    id: int
    coord: Coord
    desired_connections: List[int]


@dataclass
class Grid:
    width: int
    height: int
    tiles: List[List[Tile]]


@dataclass
class Region:
    id: int
    instability: int
    inked: bool
    coords: List[Coord]
    has_town: bool


# Connect towns with your train tracks and disrupt the opponent's.
class Game:
    my_id: int
    grid: Grid
    towns: List[Town]
    region_by_id: Dict[int, Region]
    my_score: int
    foe_score: int

    def get_region_at(self, coord: Coord) -> Region:
        return self.region_by_id[self.grid.tiles[coord.y][coord.x].region_id]

    def init(self):
        self.my_id = int(input())  # 0 or 1
        width = int(input())  # map size
        height = int(input())
        self.region_by_id = {}
        self.towns = []
        self.grid = Grid(width, height, tiles=[])

        for i in range(height):
            row: List[Tile] = []
            for j in range(width):
                # _type: 0 (PLAINS), 1 (RIVER), 2 (MOUNTAIN), 3 (POI)
                region_id, _type = [int(k) for k in input().split()]
                tileData = Tile(
                    region_id,
                    _type,
                    tracks_owner=-1,
                    inked=False,
                    instability=0,
                    part_of_active_connections=[],
                )
                row.append(tileData)

                if region_id not in self.region_by_id:
                    self.region_by_id[region_id] = Region(
                        region_id, instability=0, inked=False, coords=[], has_town=False
                    )
                region = self.region_by_id[region_id]
                coord = Coord(x=j, y=i)
                region.coords.append(coord)
            self.grid.tiles.append(row)

        town_count = int(input())
        for i in range(town_count):
            # desired_connections: comma-separated town ids e.g. 0,1,2,3
            town_id, town_x, town_y, desired_connections = input().split()
            town_id = int(town_id)
            town_x = int(town_x)
            town_y = int(town_y)
            desired_connections = (
                []
                if desired_connections == "x"
                else [int(x) for x in desired_connections.split(",")]
            )
            coord = Coord(town_x, town_y)
            town = Town(town_id, coord, desired_connections)
            self.towns.append(town)
            self.get_region_at(coord).has_town = True

    def parse(self):
        self.my_score = int(input())
        self.foe_score = int(input())
        for i in range(self.grid.height):
            for j in range(self.grid.width):
                # instability: region inked (destroyed) when this >= 3.
                # inked: true if region is destroyed.
                # part_of_active_connections: if this cell is part of one or more railway connections, this will be town ids (separated by -) in a list separated by commas. e.g. 0-1,1-2,1-3. "x" otherwise.
                (
                    tracks_owner,
                    instability,
                    inked,
                    part_of_active_connections,
                ) = input().split()
                tracks_owner = int(tracks_owner)
                instability = int(instability)
                inked = inked != "0"
                connections: List[Connection] = []
                if part_of_active_connections == "x":
                    connections = []
                else:
                    connections = []
                    for connection in part_of_active_connections.split(","):
                        from_id, to_id = connection.split("-")
                        connections.append(Connection(int(from_id), int(to_id)))
                tile = self.grid.tiles[i][j]
                tile.tracks_owner = tracks_owner
                tile.inked = inked
                tile.instability = instability
                tile.part_of_active_connections = connections

    def game_turn(self):
        actions = []

        #######################

        source_town = None
        target_town_id = None

        for town in self.towns:
            if town.desired_connections:
                source_town = town
                target_town_id = town.desired_connections[0]
                break

        if source_town and target_town_id is not None:
            # Find the target town
            target_town = None
            for town in self.towns:
                if town.id == target_town_id:
                    target_town = town
                    break

            if target_town:
                # Use AUTOPLACE to create the cheapest path
                action = f"AUTOPLACE {source_town.coord.x} {source_town.coord.y} {target_town.coord.x} {target_town.coord.y}"
                actions.append(action)
                actions.append(
                    f"MESSAGE Connecting town {source_town.id} to {target_town.id}"
                )

        #######################

        if actions:
            print(";".join(actions))
        else:
            print("WAIT")


def main():
    game = Game()
    game.init()
    while True:
        game.parse()
        game.game_turn()


main()
