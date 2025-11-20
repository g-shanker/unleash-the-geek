"""
Unleash the Geek - Score-Based Strategy

SCORING FRAMEWORK:
- Every placeable tile gets a score based on 14 weighted parameters
- Every disruptable region gets a score based on 12 weighted parameters
- Bot places tracks on highest-scoring tiles (greedy, up to 3 paint points)
- Bot disrupts highest-scoring region (1 disruption point per turn)

TO OPTIMIZE WEIGHTS:
1. Modify the default values in TrackEquationWeights and DisruptionEquationWeights
2. Test different configurations and track win rates
3. Use genetic algorithms, grid search, or manual tuning

KEY PARAMETERS TO TUNE:
- on_shortest_path_weight: Bonus for tiles on desired paths
- active_connections_weight: Bonus for tiles already scoring
- opponent_tracks_weight: Value of disrupting opponent
- blocks_opponent_path_weight: Value of blocking opponent paths
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import deque
import sys
import math


# Constants
TERRAIN_PLAINS = 0
TERRAIN_RIVER = 1
TERRAIN_MOUNTAIN = 2
TERRAIN_POI = 3

NO_TRACK_OWNER = -1
NEUTRAL_TRACK_OWNER = 2

PAINT_COST = {
    TERRAIN_PLAINS: 1,
    TERRAIN_RIVER: 2,
    TERRAIN_MOUNTAIN: 3,
    TERRAIN_POI: 3,
}


# ===== SCORING FRAMEWORK =====


@dataclass
class TrackEquationWeights:
    """Weights for calculating track placement scores."""

    base_score: float = 100.0
    terrain_cost_weight: float = -10.0
    region_has_town_weight: float = 5.0
    on_shortest_path_weight: float = 25.0
    instability_weight: float = -15.0
    existing_track_penalty: float = -1000.0
    inked_penalty: float = -2000.0


@dataclass
class DisruptionEquationWeights:
    """Weights for calculating disruption scores for regions."""

    base_score: float = 50.0
    opponent_tracks_weight: float = 30.0
    my_tracks_weight: float = -50.0
    already_inked_penalty: float = -3000.0


@dataclass(frozen=True)
class Coord:
    x: int
    y: int

    def __repr__(self) -> str:
        return f"{self.x} {self.y}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Coord) and self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


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

    def has_track(self) -> bool:
        """Check if this tile has a track placed on it."""
        return self.tracks_owner != NO_TRACK_OWNER

    def is_my_track(self, player_id: int) -> bool:
        """Check if this tile has a track owned by the specified player."""
        return self.tracks_owner == player_id

    def is_neutral_track(self) -> bool:
        """Check if this tile has a neutral track."""
        return self.tracks_owner == NEUTRAL_TRACK_OWNER


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

    def is_destroyed(self) -> bool:
        """Check if this region has been inked out (instability >= 3)."""
        return self.inked

    def can_be_disrupted(self) -> bool:
        """Check if this region can still be disrupted."""
        return not self.inked


# Connect towns with your train tracks and disrupt the opponent's.
class Game:
    my_id: int
    grid: Grid
    towns: List[Town]
    region_by_id: Dict[int, Region]
    my_score: int
    foe_score: int
    track_weights: TrackEquationWeights
    disruption_weights: DisruptionEquationWeights

    # ===== Grid and Tile Access Methods =====

    def get_tile(self, coord: Coord) -> Tile:
        """Get the tile at the specified coordinate."""
        return self.grid.tiles[coord.y][coord.x]

    def get_region_at(self, coord: Coord) -> Region:
        """Get the region at the specified coordinate."""
        tile = self.get_tile(coord)
        return self.region_by_id[tile.region_id]

    def get_town_by_id(self, town_id: int) -> Optional[Town]:
        """Get a town by its ID."""
        for town in self.towns:
            if town.id == town_id:
                return town
        return None

    def is_valid_coord(self, coord: Coord) -> bool:
        """Check if a coordinate is within the grid bounds."""
        return 0 <= coord.x < self.grid.width and 0 <= coord.y < self.grid.height

    def is_passable(self, coord: Coord) -> bool:
        """Check if a coordinate is passable (not inked and within bounds)."""
        if not self.is_valid_coord(coord):
            return False
        tile = self.get_tile(coord)
        return not tile.inked

    def get_neighbors(self, coord: Coord) -> List[Coord]:
        """Get orthogonally adjacent neighbors that are passable."""
        # Priority order: NORTH, EAST, SOUTH, WEST (as per game rules)
        directions = [
            Coord(coord.x, coord.y - 1),  # NORTH
            Coord(coord.x + 1, coord.y),  # EAST
            Coord(coord.x, coord.y + 1),  # SOUTH
            Coord(coord.x - 1, coord.y),  # WEST
        ]
        return [d for d in directions if self.is_passable(d)]

    # ===== Cost Calculation Methods =====

    def get_tile_cost(self, coord: Coord) -> int:
        """Get the paint point cost to place a track on this coordinate."""
        tile = self.get_tile(coord)
        return PAINT_COST.get(tile.type, 1)

    def init(self):
        self.my_id = int(input())  # 0 or 1
        width = int(input())  # map size
        height = int(input())
        self.region_by_id = {}
        self.towns = []
        self.grid = Grid(width, height, tiles=[])

        # Initialize with default weights (can be tuned later)
        self.track_weights = TrackEquationWeights()
        self.disruption_weights = DisruptionEquationWeights()

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

    # ===== SCORING SYSTEM METHODS =====

    def calculate_track_score(self, coord: Coord) -> float:
        """
        Calculate the desirability score for placing a track at the given coordinate.

        Returns:
            Score value (can be negative for undesirable placements)
        """
        tile = self.get_tile(coord)
        region = self.get_region_at(coord)
        w = self.track_weights

        # Can't place on inked regions
        if tile.inked:
            return w.inked_penalty

        # Can't place on existing tracks
        if tile.has_track():
            return w.existing_track_penalty

        score = w.base_score

        # 1. Terrain cost (negative, prefer cheaper tiles)
        terrain_cost = self.get_tile_cost(coord)
        score += w.terrain_cost_weight * terrain_cost

        # 2. Region has town (positive, strategic value)
        if region.has_town:
            score += w.region_has_town_weight

        # 3. On shortest path between towns (positive, builds toward connections)
        if self._is_on_shortest_path_between_towns(coord):
            score += w.on_shortest_path_weight

        # 4. Instability (negative, risky regions)
        score += w.instability_weight * tile.instability

        return score

    def calculate_disruption_score(self, region_id: int) -> float:
        """
        Calculate the desirability score for disrupting a given region.

        Returns:
            Score value (can be negative for regions we shouldn't disrupt)
        """
        region = self.region_by_id[region_id]
        w = self.disruption_weights

        # Can't disrupt already inked regions
        if region.is_destroyed():
            return w.already_inked_penalty

        score = w.base_score

        # 1. Number of opponent tracks (positive, damage opponent)
        # 2. Number of our tracks (negative, don't damage ourselves)
        my_tracks, opponent_tracks, _ = self._count_tracks_in_region(region)
        score += w.opponent_tracks_weight * opponent_tracks
        score += w.my_tracks_weight * my_tracks

        return score

    def get_all_placeable_tiles_with_scores(self) -> List[Tuple[Coord, float]]:
        """
        Get all tiles where tracks can be placed, along with their scores.

        Returns:
            List of (coordinate, score) tuples, sorted by score (highest first)
        """
        scored_tiles = []

        for y in range(self.grid.height):
            for x in range(self.grid.width):
                coord = Coord(x, y)
                tile = self.get_tile(coord)

                # Skip if can't place (has track, inked, or is a town)
                if tile.has_track() or tile.inked or self._is_town_location(coord):
                    continue

                score = self.calculate_track_score(coord)
                scored_tiles.append((coord, score))

        # Sort by score descending (highest first)
        scored_tiles.sort(key=lambda x: x[1], reverse=True)
        return scored_tiles

    def get_all_disruptable_regions_with_scores(self) -> List[Tuple[int, float]]:
        """
        Get all regions that can be disrupted, along with their scores.

        Returns:
            List of (region_id, score) tuples, sorted by score (highest first)
        """
        scored_regions = []

        for region_id, region in self.region_by_id.items():
            if not region.can_be_disrupted():
                continue

            score = self.calculate_disruption_score(region_id)
            scored_regions.append((region_id, score))

        # Sort by score descending (highest first)
        scored_regions.sort(key=lambda x: x[1], reverse=True)
        return scored_regions

    # ===== HELPER METHODS FOR SCORING =====

    def _count_tracks_in_region(self, region: Region) -> Tuple[int, int, int]:
        """
        Count tracks in a region by ownership.

        Returns:
            Tuple of (my_tracks, opponent_tracks, neutral_tracks)
        """
        my_count = 0
        opponent_count = 0
        neutral_count = 0
        opponent_id = 1 - self.my_id

        for coord in region.coords:
            tile = self.get_tile(coord)
            if tile.is_my_track(self.my_id):
                my_count += 1
            elif tile.is_my_track(opponent_id):
                opponent_count += 1
            elif tile.is_neutral_track():
                neutral_count += 1

        return my_count, opponent_count, neutral_count

    def _is_on_shortest_path_between_towns(self, coord: Coord) -> bool:
        """
        Check if coord is on the shortest path between any pair of towns with desired connections.
        Uses simple Manhattan distance heuristic (cheap approximation).
        """
        for town in self.towns:
            for desired_id in town.desired_connections:
                target_town = self.get_town_by_id(desired_id)
                if target_town:
                    # Check if coord is roughly on the straight line between the two towns
                    dist_town_to_target = abs(town.coord.x - target_town.coord.x) + abs(
                        town.coord.y - target_town.coord.y
                    )
                    dist_town_to_coord = abs(town.coord.x - coord.x) + abs(
                        town.coord.y - coord.y
                    )
                    dist_coord_to_target = abs(coord.x - target_town.coord.x) + abs(
                        coord.y - target_town.coord.y
                    )

                    # If coord is on or near the path, distances should sum to approximately the direct distance
                    if (
                        dist_town_to_coord + dist_coord_to_target
                        <= dist_town_to_target + 2
                    ):
                        return True
        return False

    def _is_town_location(self, coord: Coord) -> bool:
        """Check if coordinate is a town location."""
        return any(town.coord == coord for town in self.towns)

    # ===== GAME TURN METHODS =====

    def game_turn(self):
        """Main game turn logic using score-based decision making."""
        actions = []

        # Get all placeable tiles with scores
        scored_tiles = self.get_all_placeable_tiles_with_scores()

        # Place tracks on highest scoring tiles until we run out of paint points
        available_paint = 3
        for coord, score in scored_tiles:
            if score <= 0:  # Don't place on negative scoring tiles
                break

            cost = self.get_tile_cost(coord)
            if cost <= available_paint:
                actions.append(f"PLACE_TRACKS {coord.x} {coord.y}")
                available_paint -= cost

            if available_paint <= 0:
                break

        # Get all disruptable regions with scores
        scored_regions = self.get_all_disruptable_regions_with_scores()

        # Disrupt the highest scoring region (we have 1 disruption point per turn)
        if scored_regions and scored_regions[0][1] > 0:  # Only if score is positive
            best_region_id = scored_regions[0][0]
            actions.append(f"DISRUPT {best_region_id}")

        # Output actions
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
