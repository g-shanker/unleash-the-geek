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

    def find_shortest_path(self, from_coord: Coord, to_coord: Coord) -> List[Coord]:
        """Find the shortest path between two coordinates using BFS.

        Follows the game's path priority rules: NORTH > EAST > SOUTH > WEST
        when multiple equally short paths exist.

        Args:
            from_coord: Starting coordinate
            to_coord: Destination coordinate

        Returns:
            List of coordinates representing the shortest path (excluding start, including end)
            Empty list if no path exists
        """
        from collections import deque

        if from_coord == to_coord:
            return []

        # BFS queue: (current_coord, path)
        queue = deque([(from_coord, [])])
        visited = {from_coord}

        # Direction priority: NORTH, EAST, SOUTH, WEST
        directions = [
            (0, -1),  # NORTH
            (1, 0),  # EAST
            (0, 1),  # SOUTH
            (-1, 0),  # WEST
        ]

        while queue:
            current, path = queue.popleft()

            # Try all directions in priority order
            for dx, dy in directions:
                next_x = current.x + dx
                next_y = current.y + dy

                # Check bounds
                if not (
                    0 <= next_x < self.grid.width and 0 <= next_y < self.grid.height
                ):
                    continue

                next_coord = Coord(next_x, next_y)

                # Skip if already visited
                if next_coord in visited:
                    continue

                # Skip if region is inked out or about to be inked (instability >= 2)
                tile = self.grid.tiles[next_y][next_x]
                region = self.get_region_at(next_coord)
                if tile.inked or region.instability >= 2:
                    continue

                visited.add(next_coord)
                new_path = path + [next_coord]

                # Found destination
                if next_coord == to_coord:
                    return new_path

                queue.append((next_coord, new_path))

        return []  # No path found

    def find_all_desired_paths(self) -> Dict[tuple, List[Coord]]:
        """Find shortest paths for all desired town connections.

        Returns:
            Dictionary mapping (from_town_id, to_town_id) tuples to path coordinates.
            Path includes all cells between towns (excluding town cells themselves).
        """
        paths = {}

        for town in self.towns:
            for target_id in town.desired_connections:
                # Find target town
                target_town = None
                for t in self.towns:
                    if t.id == target_id:
                        target_town = t
                        break

                if target_town:
                    path = self.find_shortest_path(town.coord, target_town.coord)
                    # Store path without the town coordinates themselves
                    # (path already excludes start, includes end which is the target town)
                    paths[(town.id, target_id)] = path[:-1] if path else []

        return paths

    def calculate_path_cost(self, path: List[Coord]) -> int:
        """Calculate the total paint cost to complete a path.

        Tiles with existing tracks (any player or neutral) cost 0.
        Only counts tiles where we need to place new tracks.

        Args:
            path: List of coordinates representing the path

        Returns:
            Total paint points needed to complete this path
        """
        # Terrain type to cost mapping
        terrain_costs = {0: 1, 1: 2, 2: 3, 3: 3}  # plains, river, mountain, POI

        total_cost = 0
        for coord in path:
            tile = self.grid.tiles[coord.y][coord.x]
            # If any track exists, cost is 0 (can use it for connections)
            if tile.tracks_owner == -1:
                # No track exists, need to place one
                total_cost += terrain_costs.get(tile.type, 1)

        return total_cost

    def get_prioritized_connections(self) -> List[tuple]:
        """Get list of connections ordered by cost to complete.

        Recalculates paths based on current game state (inked regions, etc.)

        Returns:
            List of (from_town_id, to_town_id, cost, path) tuples,
            sorted by cost (cheapest first)
        """
        connections = []

        for town in self.towns:
            for target_id in town.desired_connections:
                # Check if already connected
                source_tile = self.grid.tiles[town.coord.y][town.coord.x]
                already_connected = any(
                    conn.from_id == town.id and conn.to_id == target_id
                    for conn in source_tile.part_of_active_connections
                )

                if already_connected:
                    continue

                # Find target town
                target_town = next((t for t in self.towns if t.id == target_id), None)
                if not target_town:
                    continue

                # Recalculate path based on current state
                path = self.find_shortest_path(town.coord, target_town.coord)
                if not path:
                    continue

                # Remove town coordinates from path (only track cells)
                path = path[:-1] if path else []
                if not path:
                    continue

                cost = self.calculate_path_cost(path)
                connections.append((town.id, target_id, cost, path))

        # Sort by cost (cheapest first)
        connections.sort(key=lambda x: x[2])
        return connections

    def find_cheapest_placeable_tiles(
        self, path: List[Coord], max_points: int
    ) -> List[Coord]:
        """Find the cheapest tiles in a path where we can place tracks.

        Args:
            path: List of coordinates in the path
            max_points: Maximum paint points available

        Returns:
            List of coordinates to place tracks on, using up to max_points
        """
        # Terrain type to cost mapping
        terrain_costs = {0: 1, 1: 2, 2: 3, 3: 3}

        # Filter to tiles that need tracks and are placeable
        placeable = []
        for coord in path:
            tile = self.grid.tiles[coord.y][coord.x]
            region = self.get_region_at(coord)
            # Can place if no track exists, region isn't inked, and not too disrupted
            # Avoid placing in regions with instability >= 2 (will be inked next disruption)
            if tile.tracks_owner == -1 and not tile.inked and region.instability < 2:
                cost = terrain_costs.get(tile.type, 1)
                placeable.append((coord, cost))

        # Sort by cost (cheapest first)
        placeable.sort(key=lambda x: x[1])

        # Greedily select tiles within budget
        selected = []
        remaining_points = max_points

        for coord, cost in placeable:
            if cost <= remaining_points:
                selected.append(coord)
                remaining_points -= cost

        return selected

    def find_best_region_to_disrupt(self) -> int | None:
        """Find the best region to disrupt based on strategic value.

        Priority:
        1. Regions with active opponent connections (highest value)
        2. Regions where opponent has more tracks than us
        3. Cannot disrupt regions with towns or already inked

        Returns:
            Region ID to disrupt, or None if no valid target
        """
        foe_id = 1 - self.my_id
        best_region = None
        best_score = -1

        for region_id, region in self.region_by_id.items():
            # Skip invalid targets
            if region.has_town or region.inked or region.instability >= 3:
                continue

            my_tracks = 0
            foe_tracks = 0
            has_active_connection = False

            for coord in region.coords:
                tile = self.grid.tiles[coord.y][coord.x]

                # Count tracks
                if tile.tracks_owner == self.my_id:
                    my_tracks += 1
                elif tile.tracks_owner == foe_id:
                    foe_tracks += 1

                # Check for active opponent connections
                if tile.part_of_active_connections:
                    for conn in tile.part_of_active_connections:
                        # Check if this is part of opponent's desired connection
                        for town in self.towns:
                            if (
                                town.id == conn.from_id
                                and conn.to_id in town.desired_connections
                            ):
                                # This is an active connection - very valuable target
                                has_active_connection = True
                                break

            # Skip if opponent has no tracks here
            if foe_tracks == 0:
                continue

            # Calculate disruption value
            # Prioritize: active connections > track advantage
            score = 0
            if has_active_connection:
                score += 1000  # Very high priority for active connections
            score += foe_tracks - my_tracks  # Prefer regions where opponent dominates

            if score > best_score:
                best_score = score
                best_region = region_id

        return best_region

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

                # Update region state from tile data
                region = self.region_by_id[tile.region_id]
                region.instability = instability
                region.inked = inked

    def game_turn(self):
        """Execute one turn of the game by deciding actions and outputting them.

        Strategy:
        1. Disrupt: Target regions with opponent connections or track advantage
        2. Build: Prioritize completing cheapest connections

        Outputs to stdout:
        - DISRUPT action for strategic sabotage
        - PLACE_TRACKS actions for optimal tile placement
        - MESSAGE actions for debugging
        - WAIT if no actions available
        """
        actions = []
        paint_points = 3  # Available per turn

        #######################
        # Strategy: Disrupt opponent, then build our connections

        # 1. Find and disrupt best target region
        region_to_disrupt = self.find_best_region_to_disrupt()
        if region_to_disrupt is not None:
            actions.append(f"DISRUPT {region_to_disrupt}")
            region = self.region_by_id[region_to_disrupt]
            actions.append(
                f"MESSAGE Disrupting region {region_to_disrupt} ({region.instability + 1}/3)"
            )

        # 2. Build cheapest connections
        prioritized = self.get_prioritized_connections()

        if prioritized:
            # Focus on the cheapest connection
            from_id, to_id, cost, path = prioritized[0]

            # Find cheapest tiles to place within this path
            tiles_to_place = self.find_cheapest_placeable_tiles(path, paint_points)

            if tiles_to_place:
                for coord in tiles_to_place:
                    actions.append(f"PLACE_TRACKS {coord.x} {coord.y}")

                actions.append(f"MESSAGE Building {from_id}->{to_id} (cost:{cost})")
            else:
                # Path might be blocked or already complete, try next connection
                for from_id, to_id, cost, path in prioritized[1:3]:  # Try next 2
                    tiles_to_place = self.find_cheapest_placeable_tiles(
                        path, paint_points
                    )
                    if tiles_to_place:
                        for coord in tiles_to_place:
                            actions.append(f"PLACE_TRACKS {coord.x} {coord.y}")
                        actions.append(
                            f"MESSAGE Building {from_id}->{to_id} (cost:{cost})"
                        )
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
