import rg
import settings as rgs


class GameWatcher(object):
    SILENT = False

    def __init__(self, game=None):
        self.g = game

    def say(self, what, prefix="   "):
        if not self.SILENT:
            print prefix + what

    def turn(self):
        return self.g['turn'] + 1


class Robot(GameWatcher):
    """Goose! Every robot calculates a complete set of the next
    turn's moves, and then returns the move for itself.
    http://robotgame.org/viewrobot/8130
    """

    def act(self, game):
        """Method called by the game controller"""
        self.g = game
        brain = RobotBrain(game).setup_turn(self)
        moves = brain.calculate_moves()

        if brain.is_debug_robot():
            self.print_turn()
            self.say("Move debugger: {m}".format(m=moves))
        my_move = moves[self.location]

        return my_move

    def print_turn(self):
        self.say("-- Goose: robot @ {l} [hp={hp}] starting turn {t} --"
                 .format(l=self.location, hp=self.hp, t=self.turn()),
                 prefix="")


class RobotBrain(GameWatcher):
    """A master controller that makes a set of moves for all robots"""

    AVG_DAMAGE = 9

    def say(self, what):
        if self.is_debug_robot():
            super(RobotBrain, self).say(what)


    def setup_turn(self, robot):
        self.robot = robot
        self.nav = Navigator(self.g)

        self.enemies = {}
        self.friends = {}
        for loc, bot in self.g['robots'].items():
            if self.on_team(bot):
                self.friends[loc] = bot
            else:
                self.enemies[loc] = bot
        return self

    def calculate_moves(self):
        """Calculates moves for all robots, and returns them in a map
        Robot loc -> [move list]"""
        moves = {}

        enemies_under_attack = [e for _, e in self.enemies.items() if
                                self.under_attack(e)]

        for loc, bot in self.friends.items():
            self.say("Finding move for robot at {l}".format(l=loc))

            if self.nav.is_spawn_point(loc) and self.incoming_spawns():
                spawn_escape = self.nav.find_escape(loc,
                                                    lambda l: not self.nav.is_spawn_point(l))
                if spawn_escape:
                    away = self.nav.step_toward(loc, spawn_escape)
                    if away:
                        self.nav.add_destination(away)
                        moves[loc] = ['move', away]

            # TODO: better breaking between moves
            if loc in moves:
                continue

            # See if we should attack or run away from a current enemy
            neighbor_enemies = self.nearby_robots(loc, allies=False)
            if neighbor_enemies:
                attacked_neighbors = [e for e in neighbor_enemies if
                                      e in enemies_under_attack]

                if not attacked_neighbors or len(neighbor_enemies) > 1:
                    escape = self.nav.step_toward(loc, self.nav.find_escape(loc))
                    if escape:
                        moves[loc] = ['move', escape]
                    elif len(neighbor_enemies) > 1:
                        # last ditch suicide
                        for e in neighbor_enemies:
                            if e.hp <= rgs.settings.suicide_damage \
                              or len(neighbor_enemies) * self.AVG_DAMAGE > bot.hp:
                                self.say("suicide :-(")
                                moves[loc] = ['suicide']
                else:
                    target = self.choose_target(attacked_neighbors)
                    if target:
                        self.say("attacking enemy @ {e}".format(e=target.location))
                        moves[loc] = ['attack', target.location]

            # TODO: better breaking between moves
            if loc in moves:
                continue

            # Look for an enemy to go attack
            best_target = None
            best_score = 9999
            for e in enemies_under_attack:
                dist = rg.wdist(loc, e.location)
                score = (2 * dist) + e.hp
                if score <= best_score:
                    best_target = e
                    best_score = score

            if best_target:
                towards_enemy = self.nav.step_toward(loc, best_target.location)
                if towards_enemy:
                    self.nav.add_destination(towards_enemy)
                    moves[loc] = ['move', towards_enemy]

            # fall back to guarding
            if not loc in moves:
                moves[loc] = ['guard']

        return moves

    def nearby_robots(self, center, allies=True):
        locs = rg.locs_around(center)
        return [bot for loc, bot in self.g['robots'].items()
                if loc in locs and
                self.on_team(bot) == allies]

    def under_attack(self, enemy):
        num_attacking = len(self.nearby_robots(enemy.location, allies=True))

        locs_around = self.nav.locs_around(enemy.location, radius=2)
        friends_around = [self.g.robots[l] for l in locs_around
                          if l in self.g.robots and self.on_team(self.g.robots[l])]
        num_friends = len(friends_around)

        return num_attacking > 0 or num_friends > 1

    def choose_target(self, robots):
        """Always attack the weakest robot"""
        target = None
        min_hp = rgs.settings.robot_hp
        for r in robots:
            if r.hp <= min_hp:
                target = r
                min_hp = r.hp
        return target

    def should_attack_empty(self, enemy, nearest_dist):
        if nearest_dist == 2:
            self.say("Defensive attack: current={current},them={them}"
                     .format(current=self.location, them=enemy.location))
            return self.nav.step_toward(self.location, enemy.location)
        return None

    def incoming_spawns(self):
        """Returns True if spawning new robots this turn or next"""
        next_spawn = self.turn() % rgs.settings.spawn_every
        return (next_spawn == 0 or
                next_spawn == rgs.settings.spawn_every - 1)

    def on_team(self, robot):
        return self.robot.player_id == robot.player_id

    def is_debug_robot(self):
        return self.robot.location == min(self.friends.keys())

class Navigator(GameWatcher):
    """Handles point-to-point navigation for a single robot"""
    destinations = None

    def add_destination(self, loc):
        """Record a space as a destination so we don't have robot collisions"""
        if not self.destinations:
            self.destinations = set()
        if loc:
            self.destinations.add(loc)

    def step_toward(self, loc, dest):
        """Ant navigation with basic block checking
        Returns a move destination or None"""
        if not dest:
            return None
        x0, y0 = loc
        x, y = dest
        x_diff, y_diff = x - x0, y - y0
        dx, dy = abs(x_diff), abs(y_diff)

        forward_x = (self.add_sign(x0, x_diff), y0)
        forward_y = (x0, self.add_sign(y0, y_diff))

        can_x = not self.is_blocked(forward_x) and dx > 0
        can_y = not self.is_blocked(forward_y) and dy > 0

        # Both open, take bigger vector first
        if can_x and can_y:
            if dx > dy:
                return forward_x
            return forward_y
        elif can_x:
            return forward_x
        elif can_y:
            return forward_y
        return None

    def add_sign(self, num, diff):
        if diff > 0:
            return num + 1
        elif diff < 0:
            return num - 1
        else:
            return num

    def is_blocked(self, dest):
        if not dest:
            return True
        if dest in self.g.robots:
            return True
        if self.destinations and dest in self.destinations:
            return True
        filter = set(['invalid', 'obstacle'])
        if len(filter & set(rg.loc_types(dest))) != 0:
            return True
        return False

    def locs_around(self, location, radius=1, top_level=True):
        around = rg.locs_around(location,
                                filter_out=('invalid', 'obstacle'))
        # base case
        if radius == 1:
            if not top_level:
                around.append(location)
            return around

        # recursively accumulate
        results = []
        for l in around:
            results.extend(self.locs_around(l, radius=radius-1, top_level=False))

        # don't return the original location
        if top_level and location in results:
            results.remove(location)
        return results

    def find_escape(self, from_loc, filter_func=None):
        for s in self.locs_around(from_loc):
            if not self.is_blocked(s):
                if not filter_func or filter_func(s):
                    return s
        return None

    def is_spawn_point(self, loc):
        return 'spawn' in rg.loc_types(loc)
