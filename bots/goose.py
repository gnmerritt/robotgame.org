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

    def incoming_spawns(self):
        """Returns True if spawning new robots this turn"""
        next_spawn = self.turn() % rgs.settings.spawn_every
        return next_spawn == 1

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

    def say(self, what, prefix="   "):
        if self.is_debug_robot():
            super(RobotBrain, self).say(what, prefix)

    def setup_turn(self, robot):
        self.robot = robot
        self.nav = Navigator(self.g)
        self.debug = None

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

        for loc, bot in self.friends.items():
            self.say("Finding move for robot at {l}".format(l=loc), prefix=" ")

            enemies_under_attack = [e for _, e in self.enemies.items() if
                                    self.under_attack(e, bot)]

            if self.nav.is_spawn_point(loc) and self.incoming_spawns():
                spawn_escape = self.nav.find_escape(loc)
                if spawn_escape:
                    away = self.nav.step_toward(loc, spawn_escape)
                    if away:
                        self.say("escaping spawn")
                        self.nav.add_destination(loc, away)
                        moves[loc] = ['move', away]
                else:
                    self.say("suicide (trapped on spawn)")
                    moves[loc] = ['suicide']

            # TODO: better breaking between moves
            if loc in moves:
                continue

            # See if we should attack or run away from a current enemy
            neighbor_enemies = self.nearby_robots(loc, allies=False)
            if neighbor_enemies:
                attacked_neighbors = [e for e in neighbor_enemies if
                                      e in enemies_under_attack]

                if not attacked_neighbors or len(neighbor_enemies) > 1 or \
                    self.expecting_suicide(neighbor_enemies):
                    self.say("trying to escape")

                    escape_safe = lambda e: self.safe_escape(e, neighbor_enemies)
                    escape = self.nav.step_toward(loc,
                                                  self.nav.find_escape(loc, escape_safe))
                    if escape:
                        self.say("successful escape")
                        self.nav.add_destination(loc, escape)
                        moves[loc] = ['move', escape]
                    elif len(neighbor_enemies) > 1:
                        # last ditch suicide
                        for e in neighbor_enemies:
                            low_hp = len(neighbor_enemies) * self.AVG_DAMAGE >= bot.hp
                            if e.hp <= rgs.settings.suicide_damage or low_hp:
                                self.say("suicide (surrounded) :-(")
                                moves[loc] = ['suicide']
                    elif not loc in moves:
                        # attack because we can't escape and didn't suicide
                        self.say("attack unfavorably - can't escape")
                        moves[loc] = ['attack',
                                      self.choose_target(neighbor_enemies).location]
                else:
                    target = self.choose_target(attacked_neighbors)
                    if target:
                        self.say("attacking enemy @ {e}".format(e=target.location))
                        moves[loc] = ['attack', target.location]

            # TODO: better breaking between moves
            if loc in moves:
                continue

            # Look for an enemy to go towards & attack
            best_target = None
            best_score = 9999
            for e in enemies_under_attack:
                dist = rg.wdist(loc, e.location)
                score = (4 * dist) + e.hp
                if score <= best_score:
                    towards_enemy = self.nav.step_toward(loc, e.location)
                    enemies_at_dest = len(self.nearby_robots(towards_enemy,
                                                             allies=False))
                    if enemies_at_dest <= 1:
                        best_target = e
                        best_score = score

            if best_target:
                towards_enemy = self.nav.step_toward(loc, best_target.location)
                if rg.wdist(loc, best_target.location) <= 1:
                    self.say("bug - attacking late")
                    moves[loc] = ['attack', best_target.location]
                elif towards_enemy:
                    self.say("moving towards enemy")
                    self.nav.add_destination(loc, towards_enemy)
                    moves[loc] = ['move', towards_enemy]

            # TODO: better breaking between moves
            if loc in moves:
                continue

            # defensive attack towards a space an enemy might move?
            for e_loc, e in self.enemies.items():
                if rg.wdist(loc, e_loc) == 2:
                    towards_empty = self.nav.step_toward(loc, e_loc)
                    if towards_empty:
                        self.say("attacking empty space")
                        moves[loc] = ['attack', towards_empty]
                        break

            # fall back to guarding
            if not loc in moves:
                self.say("guarding - probably not good")
                moves[loc] = ['guard']
            else:
                # sanity check - don't move onto our own location
                if moves[loc] == ['move', loc]:
                    self.say("bug - tried to move onto ourself")
                    moves[loc] = ['guard']

        return moves

    def nearby_robots(self, center, allies=True):
        if not center:
            return []
        locs = rg.locs_around(center)
        return [bot for loc, bot in self.g['robots'].items()
                if loc in locs and
                self.on_team(bot) == allies]

    def under_attack(self, enemy, us=None):
        attackers = self.nearby_robots(enemy.location, allies=True)
        num_attacking = len(attackers)
        if us in attackers:
            num_attacking -= 1

        locs_around = self.nav.locs_around(enemy.location, radius=2)
        friends_around = [self.g.robots[l] for l in locs_around
                          if l in self.g.robots and self.on_team(self.g.robots[l])]
        num_friends = len(friends_around)
        if us in friends_around:
            num_friends -= 1

        return num_attacking > 0 or num_friends > 2

    def safe_escape(self, escape, current_enemies):
        """Return True if the locations looks safe to flee too"""
        enemies_around_escape = self.nearby_robots(escape, allies=False)
        return not self.expecting_suicide(enemies_around_escape) and \
            len(enemies_around_escape) < len(current_enemies)

    def expecting_suicide(self, enemies):
        """Do we think one of these enemies will commit suicide"""
        for e in enemies:
            friends_around = self.nearby_robots(e.location, allies=True)
            if e.hp <= len(friends_around) * self.AVG_DAMAGE:
                return True
        return False

    def choose_target(self, robots):
        """Always attack the weakest robot"""
        target = None
        min_hp = rgs.settings.robot_hp
        for r in robots:
            if r.hp <= min_hp:
                target = r
                min_hp = r.hp
        return target

    def on_team(self, robot):
        return self.robot.player_id == robot.player_id

    def is_debug_robot(self):
        if self.debug is None:
            self.debug = self.robot.location == min(self.friends.keys())
        return self.debug

class Navigator(GameWatcher):
    """Handles point-to-point navigation for a single robot"""
    destinations = None
    departures = None

    def add_destination(self, current, dest):
        """Record a space as a destination so we don't have robot collisions"""
        if not self.destinations:
            self.destinations = set()
            self.departures = set()
        if current:
            self.departures.add(current)
        if dest:
            self.destinations.add(dest)

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
            # Our robot is about to vacate this space
            if self.departures and dest in self.departures:
                return False
            return True
        # Our robot is about to move into this space, don't collide
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
                if (not filter_func or filter_func(s)) and \
                  (not self.incoming_spawns() or not self.is_spawn_point(s)):
                    return s
        return None

    def is_spawn_point(self, loc):
        return 'spawn' in rg.loc_types(loc)
