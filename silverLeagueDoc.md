# Silver League Code Documentation

## Overview
This code successfully passed the Silver League by implementing a dual strategy: **disrupting opponent tracks** while **building connections between towns**. The Silver League objective requires washing away at least one opponent's track by causing a region to ink out (instability ≥ 3).

---

## Data Structures

### Core Classes

#### `Coord`
- **Purpose**: Represents a position on the grid
- **Attributes**: 
  - `x`, `y`: Integer coordinates
- **Method**: `__repr__()` returns formatted string for output commands

#### `Connection`
- **Purpose**: Represents an active railway connection between two towns
- **Attributes**:
  - `from_id`: Source town ID
  - `to_id`: Destination town ID

#### `Tile`
- **Purpose**: Represents a single cell on the map
- **Attributes**:
  - `region_id`: ID of the region this tile belongs to
  - `type`: Terrain type (0=PLAINS, 1=RIVER, 2=MOUNTAIN, 3=POI)
  - `tracks_owner`: Who owns the track (-1=none, 0/1=player, 2=neutral)
  - `inked`: Boolean indicating if the region is destroyed
  - `instability`: Current instability level of the region
  - `part_of_active_connections`: List of Connection objects this tile is part of

#### `Town`
- **Purpose**: Represents a town on the map
- **Attributes**:
  - `id`: Unique town identifier
  - `coord`: Position on the map
  - `desired_connections`: List of town IDs this town wants to connect to

#### `Region`
- **Purpose**: Represents a contiguous area of tiles
- **Attributes**:
  - `id`: Unique region identifier
  - `instability`: How close the region is to being inked (≥3 = destroyed)
  - `inked`: Boolean indicating if region is destroyed
  - `coords`: List of all coordinates in this region
  - `has_town`: Boolean indicating if region contains a town

#### `Grid`
- **Purpose**: Container for the entire map
- **Attributes**:
  - `width`, `height`: Map dimensions
  - `tiles`: 2D list of Tile objects

---

## Game Class

### Key Attributes
- `my_id`: Player's ID (0 or 1)
- `grid`: The game map
- `towns`: List of all towns
- `region_by_id`: Dictionary mapping region IDs to Region objects
- `my_score`, `foe_score`: Current scores

### Key Methods

#### `get_region_at(coord: Coord) -> Region`
- **Purpose**: Get the Region object for a given coordinate
- **Usage**: Used to check region properties at specific locations

#### `init()`
- **Purpose**: One-time initialization at game start
- **Process**:
  1. Read player ID (0 or 1)
  2. Read map dimensions (width × height)
  3. Build the grid:
     - For each cell, read `region_id` and `type`
     - Create Tile objects
     - Create/update Region objects with coordinates
  4. Read town data:
     - Parse town ID, position, and desired connections
     - Mark regions containing towns
- **Key Logic**: Groups tiles into regions and identifies which regions have towns

#### `parse()`
- **Purpose**: Update game state each turn
- **Process**:
  1. Read current scores
  2. For each cell (in same order as init):
     - Read `tracks_owner`, `instability`, `inked`, `part_of_active_connections`
     - Parse connection strings (e.g., "0-1,1-2" → Connection objects)
     - Update tile state
- **Key Logic**: Keeps track of where tracks are placed and which connections are active

#### `game_turn()`
**This is the main strategy method that won Silver League**

##### Strategy Overview
The code implements a two-phase strategy each turn:

1. **Disruption Phase** (DISRUPT action - uses 1 disruption point)
2. **Building Phase** (AUTOPLACE actions - uses paint points)

---

### Disruption Phase (Lines 159-186)

#### Goal
Find and disrupt regions containing opponent tracks to eventually ink them out (instability ≥ 3).

#### Algorithm
```
1. Calculate opponent's ID: foe_id = 1 - my_id
2. Initialize region_to_disrupt = None
3. For each region in the map:
   a. Skip if region is already inked
   b. Skip if region has a town (strategic - avoid disrupting valuable areas)
   c. Check all tiles in region for opponent tracks
   d. If opponent has tracks:
      - Select this region as target
      - Break (disrupt first match found)
4. If target found:
   a. Add DISRUPT command
   b. Check if this disruption will ink out the region (instability + 1 ≥ 3)
   c. Add appropriate MESSAGE
```

#### Key Decisions
- **Skip regions with towns**: Avoids disrupting valuable strategic locations
- **Skip already inked regions**: Can't disrupt what's already destroyed
- **Target first match**: Simple but effective - consistently applies pressure
- **Instability tracking**: Shows progress toward inking out regions

#### Why This Works
- Consistently disrupts opponent's infrastructure
- Eventually causes regions to ink out (instability ≥ 3)
- Meets Silver League objective: wash away at least one opponent's track

---

### Building Phase (Lines 188-225)

#### Goal
Build railway connections to score points while disrupting opponent.

#### Algorithm
```
1. Initialize connections_attempted = 0
2. For each town:
   a. Skip if town has no desired connections
   b. For each desired connection target:
      i. Find the target town object
      ii. Get source town tile to check existing connections
      iii. Check if connection already active:
          - Look through part_of_active_connections
          - Check if from_id and to_id match
      iv. If not connected:
          - Add AUTOPLACE command from source to target
          - Increment connections_attempted
          - Break (one connection per town per turn)
   c. If connections_attempted ≥ 2: break
```

#### Key Decisions
- **Check existing connections**: Avoids redundant AUTOPLACE commands
- **One connection per town**: Spreads effort across multiple objectives
- **Limit to 2 attempts per turn**: Prevents command spam
- **Uses AUTOPLACE**: Automatically finds cheapest path considering terrain costs

#### AUTOPLACE Details
- Automatically calculates cheapest path based on terrain costs:
  - Plains: 1 paint point
  - River: 2 paint points
  - Mountain/POI: 3 paint points
- Handles pathfinding automatically
- Places multiple tracks if paint points allow

---

## Complete Turn Flow

```
Turn Start
    ↓
1. Parse game state (scores, tiles, connections)
    ↓
2. Find opponent's tracks in non-town regions
    ↓
3. DISRUPT first region with opponent tracks
    ↓
4. Check town connections
    ↓
5. AUTOPLACE up to 2 new connections
    ↓
6. Output all actions (semicolon-separated)
    ↓
Turn End
```

---

## Why This Strategy Wins Silver League

### Meets Primary Objective
- **Requirement**: Wash away at least one opponent's track via disruption
- **Solution**: Every turn targets opponent tracks with DISRUPT
- **Result**: Regions reach instability 3 → ink out → opponent tracks destroyed

### Dual Strategy Balance
1. **Offensive**: Disrupts opponent infrastructure continuously
2. **Defensive/Scoring**: Builds own connections for points
3. **Resource Management**: Uses both disruption point (1) and paint points (3)

### Smart Target Selection
- Avoids disrupting regions with towns (keeps valuable areas intact)
- Skips already inked regions (no wasted actions)
- Targets first match found (simple, consistent pressure)

### Connection Building
- Checks for existing connections (efficiency)
- Attempts multiple connections (spreads progress)
- Uses AUTOPLACE (optimal pathfinding)

### Output Format
- All actions joined with semicolons
- MESSAGE commands provide visibility for debugging
- Fallback to WAIT if no actions (defensive programming)

---

## Example Turn Output

```
DISRUPT 5;MESSAGE Disrupting region 5 (2/3);AUTOPLACE 3 4 7 8;AUTOPLACE 2 1 9 6
```

This output:
1. Disrupts region 5 (bringing instability to 2/3)
2. Displays debug message
3. Creates path from town at (3,4) to town at (7,8)
4. Creates path from town at (2,1) to town at (9,6)

---

## Paint Point Economics

Each turn provides **3 paint points** (non-cumulative):
- AUTOPLACE automatically distributes points optimally
- Cheapest path selected based on terrain
- Remaining points used if path requires < 3 points
- Multiple short tracks can be placed per turn

---

## Strategic Insights

### What Makes This Code Effective

1. **Consistency**: Every turn attempts disruption
2. **Simplicity**: First-match targeting is predictable and reliable
3. **Balance**: Offensive (disrupt) + Scoring (build)
4. **Safety**: Skips towns and inked regions
5. **Efficiency**: Checks existing connections before building
6. **Automation**: AUTOPLACE handles complex pathfinding

### Potential Improvements (Not needed for Silver)
- Prioritize regions with higher existing instability
- Count opponent tracks per region (target dense areas)
- Track which regions have been disrupted before
- Build connections that avoid disruption-vulnerable regions
- Defensive disruption (protect own tracks by disrupting nearby regions)

---

## Conclusion

This code successfully passes Silver League by implementing a straightforward yet effective strategy: **consistently disrupt opponent tracks while building scoring connections**. The key insight is that simple, consistent pressure through DISRUPT actions will eventually ink out regions and destroy opponent infrastructure, meeting the league objective while simultaneously scoring points through connection building.
