import rg
import settings as rgs

class Robot(object):
    """Goose!
    http://robotgame.org/viewrobot/8130
    """
    AVG_DAMAGE = 9
    GATHERING = rg.CENTER_POINT

    SILENT = True

    def setup_turn(self, game):
        self.g = game
        self.nav = Navigator(game)
        self.enemies = [r for _, r in self.g['robots'].items()
                        if not self.on_team(r)]
        self.friends = [r for _, r in self.g['robots'].items()
                        if self.on_team(r)]
        self.__scores = {}
        self.__hp_grad = {}

    def act(self, game):
        self.setup_turn(game)
        self.print_turn()

        search_locs = self.nav.locs_around(self.location, radius=5)
        destination = self.select_destination(search_locs)

        if destination:
            if destination == self.location:
                self.say("best destination is current location, staying put")
                target = self.choose_target(
                    self.nearby_robots(self.location, allies=False))
                if target:
                    self.say("attacking robot @ {l} with hp={hp}"
                             .format(l=target.location, hp=target.hp))
                    return ['attack', target.location]
                else:
                    return ['guard']
            else:
                self.say("moving to {d}".format(d=destination))
                towards = self.nav.step_toward(self.location, destination)
                if towards:
                    return ['move', towards]

        self.say("didn't move or attack, guarding")
        return ['guard']

    def select_destination(self, locs):
        best_dest = self.location
        best_score = self.weigh_location(best_dest)

        self.say("current loc has score of {b}".format(b=best_score))

        for loc in locs:
            score = self.weigh_location(loc)
            self.say("got score {s} @ {l}".format(s=score, l=loc))
            if score > best_score:
                best_score = score
                best_dest = loc
        return best_dest

    def weigh_location(self, location):
        """Returns a number indicating how favorable moving here is"""
        def inner(location):
            # avoid spawn points
            if self.nav.is_spawn_point(location) and \
                self.incoming_spawns():
                return -1000

            enemies = self.nearby_robots(location, allies=False)
            friends = self.nearby_robots(location, allies=True)

            if len(enemies) > 0:
                for enemy in enemies:
                    self.say("AA - see enemy")
                    if enemy.hp <= self.AVG_DAMAGE * 2 or \
                      len(self.nearby_robots(enemy.location, allies=True)) >= 1:
                      self.say("AA - hp low or already somebody attacking")
                      # favorable attack, go here
                      if rg.dist(self.location, enemy.location) == 1:
                          self.say("AA - in position to attack {l}"
                                   .format(l=enemy.location))
                          return 1000
                      else:
                          return 900

            hp_gradient = self.hp_gradient(location)
            if len(friends) > 1:
                hp_gradient *= -1

            total = hp_gradient

            towards_loc = self.nav.step_toward(self.location, location)
            if not towards_loc:
                total -= 50

            return total

        # memoize
        if not location in self.__scores:
            self.__scores[location] = inner(location)
        return self.__scores[location]

    def hp_gradient(self, location):
        def inner(location):
            sum = 0
            search_locs = self.nav.locs_around(location, radius=4)

            for loc in search_locs:
                if loc in self.g.robots:
                    robot = self.g.robots[loc]
                    dist = rg.wdist(location, robot.location)
                    hp_weight = robot.hp / max(dist, 1)
                    if self.on_team(robot):
                        sum += hp_weight
                    else:
                        sum -= hp_weight
            return sum

        # memoize
        if not location in self.__hp_grad:
            self.__hp_grad[location] = inner(location)
        return self.__hp_grad[location]

    def nearby_robots(self, center, allies=True):
        locs = rg.locs_around(center)
        return [bot for loc, bot in self.g['robots'].items()
                if loc in locs and
                self.on_team(bot) == allies]

    def hp_sum(self, robots):
        sum = 0
        for r in robots:
            sum += r.hp
        return sum

    def choose_target(self, robots):
        """Always attack the weakest robot"""
        target = None
        min_hp = rgs.settings.robot_hp
        for r in robots:
            if r.hp <= min_hp:
                target = r
                min_hp = r.hp
        return target

    def nearest_enemy(self, location, enemies):
        nearest = None
        nearest_dist = -1
        for robot in enemies:
            robot_walk_dist = rg.wdist(robot.location, location)
            if robot_walk_dist < nearest_dist \
                or nearest_dist == -1:
                nearest_dist = robot_walk_dist
                nearest = robot
        return nearest, nearest_dist

    def should_attack_empty(self, enemy, nearest_dist):
        if nearest_dist == 2:
            self.say("Defensive attack: us={us},them={them}"
                     .format(us=self.location, them=enemy.location))
            return self.nav.step_toward(self.location, enemy.location)
        return None

    def incoming_spawns(self):
        """Returns True if spawning new robots this turn or next"""
        next_spawn = self.turn() % rgs.settings.spawn_every
        return (next_spawn == 0 or
                next_spawn == rgs.settings.spawn_every - 1)

    def should_suicide(self, neighbor_enemies):
        return len(neighbor_enemies) * self.AVG_DAMAGE > self.hp

    def on_team(self, robot):
        return self.player_id == robot.player_id

    def print_turn(self):
        self.say("-- Goose: robot @ {l} [hp={hp}] starting turn {t} --"
                 .format(l=self.location, hp=self.hp, t=self.turn()),
                 prefix="")

    def say(self, what, prefix="   ", level=0):
        if not self.SILENT:
            print prefix + what

    def turn(self):
        return self.g['turn'] + 1

class Navigator(object):
    def __init__(self, game):
        self.g = game

    def step_toward(self, loc, dest):
        """Ant navigation with basic block checking
        Returns a move destination or None"""
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
        filter = set(['invalid', 'obstacle'])
        if len(filter & set(rg.loc_types(dest))) != 0:
            return True
        return False

    def locs_around(self, location, radius=1, top_level=True):
        around = rg.locs_around(location,
                                filter_out=('invalid', 'obstacle'))
        # base case
        if radius == 1:
            return around

        # recursively accumulate
        results = []
        for l in around:
            results.extend(self.locs_around(l, radius=radius-1, top_level=False))

        results = set(results)

        # don't return the original location
        if top_level and location in results:
            results.remove(location)
        return results

    def find_escape(self, from_loc, neighbor_bots):
        neighbor_locs = set([n.location for n in neighbor_bots])
        for s in self.locs_around(from_loc):
            if not s in neighbor_locs:
                return s
        return None

    def is_spawn_point(self, loc):
        return 'spawn' in rg.loc_types(loc)
