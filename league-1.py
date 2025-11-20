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
        """Get the region object at the specified coordinate.

        Args:
            coord: The x,y coordinate on the grid

        Returns:
            Region object containing information about the region at that location
        """
        return self.region_by_id[self.grid.tiles[coord.y][coord.x].region_id]

    def init(self):
        """Initialize the game by reading the initial game state.

        Reads from stdin:
        - Player ID (0 or 1)
        - Grid dimensions (width x height)
        - Region and terrain type for each cell
        - Town count and details (id, position, desired connections)

        Sets up:
        - Grid with all tiles and their properties
        - Region mapping with coordinates
        - Town list with desired connections
        """
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
        """Parse the current turn state from stdin.

        Reads from stdin:
        - Current scores for both players
        - For each cell: track owner, instability, inked status, active connections

        Updates:
        - Player scores
        - Tile states (tracks, instability, connections)
        - Region states derived from tile data
        """
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
        """Execute one turn of the game by deciding actions and outputting them.

        Strategy:
        1. Disrupt: Find first region with opponent tracks (no town) and disrupt it
        2. Build: Attempt to create connections between towns using AUTOPLACE

        Outputs to stdout:
        - DISRUPT action if opponent tracks found in vulnerable region
        - AUTOPLACE actions for up to 2 town connections that don't exist yet
        - MESSAGE actions for debugging
        - WAIT if no actions available
        """
        actions = []

        #######################
        # Strategy: Build connections AND disrupt opponent tracks

        # 1. Find first region with opponent tracks (no town) and disrupt it
        foe_id = 1 - self.my_id
        region_to_disrupt = None

        for region_id, region in self.region_by_id.items():
            if region.inked or region.has_town:
                continue  # Skip inked regions and regions with towns

            # Check if opponent has tracks in this region
            has_foe_tracks = False
            for coord in region.coords:
                tile = self.grid.tiles[coord.y][coord.x]
                if tile.tracks_owner == foe_id:
                    has_foe_tracks = True
                    break

            # Found a valid target - disrupt it
            if has_foe_tracks:
                region_to_disrupt = region_id
                break

        # Disrupt the target region
        if region_to_disrupt is not None:
            actions.append(f"DISRUPT {region_to_disrupt}")
            region = self.region_by_id[region_to_disrupt]
            if region.instability + 1 >= 3:
                actions.append(f"MESSAGE Inking out region {region_to_disrupt}!")
            else:
                actions.append(
                    f"MESSAGE Disrupting region {region_to_disrupt} ({region.instability + 1}/3)"
                )

        # 2. Build connections - try to connect multiple towns
        connections_attempted = 0
        for town in self.towns:
            if not town.desired_connections:
                continue

            for target_town_id in town.desired_connections:
                # Find the target town
                target_town = None
                for t in self.towns:
                    if t.id == target_town_id:
                        target_town = t
                        break

                if target_town:
                    # Check if connection already exists by looking at the source town tile
                    source_tile = self.grid.tiles[town.coord.y][town.coord.x]
                    already_connected = False
                    for conn in source_tile.part_of_active_connections:
                        if conn.from_id == town.id and conn.to_id == target_town_id:
                            already_connected = True
                            break

                    if not already_connected:
                        # Use AUTOPLACE to create the cheapest path
                        action = f"AUTOPLACE {town.coord.x} {town.coord.y} {target_town.coord.x} {target_town.coord.y}"
                        actions.append(action)
                        connections_attempted += 1
                        break  # Try one connection per town per turn

            if connections_attempted >= 2:  # Limit attempts to avoid spam
                break

        #######################

        if actions:
            print(";".join(actions))
        else:
            print("WAIT")


def main():
    """Main game loop.

    Initializes the game once, then continuously:
    1. Parses the current turn state
    2. Executes game turn logic to output actions
    """
    game = Game()
    game.init()
    while True:
        game.parse()
        game.game_turn()


main()
