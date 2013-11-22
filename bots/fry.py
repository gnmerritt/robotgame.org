import rg
import math

class Robot(object):
    """Fry! My first crack at robotgame
    http://robotgame.org/viewrobot/4184
    """
    MAX_HP = 50
    GATHERING = rg.CENTER_POINT
    SILENT = False

    def act(self, game):
        self.g = game
        self.print_turn()
        self.surrounding = rg.locs_around(self.location,
                                          filter_out=('invalid', 'obstacle'))
        enemies = [r for _, r in self.g['robots'].items()
                   if not self.on_team(r)]
        self.say("{n} enemies alive this turn".format(n=len(enemies)))
        neighbors = self.nearby_robots(self.location)
        self.say("saw {n} nearby robots".format(n=len(neighbors)))
        neighbor_enemies = [r for r in neighbors
                            if not self.on_team(r)]
        self.say("saw {n} neighbor_enemies".format(n=len(neighbor_enemies)))

        # Suicide?
        if self.should_suicide(neighbor_enemies):
            self.say("committing suicide - {e} neighbor_enemies / {hp} hp left"
                     .format(e=len(neighbor_enemies), hp=self.hp))
            return ['suicide']

        # Run?
        if self.should_run(neighbor_enemies):
            self.say("trying to run")
            run_to = self.find_escape(neighbors)
            if run_to:
                self.say("found escape {l} going to it".format(l=run_to))
                return ['move', run_to]

        # Attack?
        target = self.choose_target(neighbor_enemies)
        if target:
            self.say("attacking {l}".format(l=target.location))
            return ['attack', target.location]

        # Nearby enemy?
        nearest_enemy, enemy_distance = \
           self.nearest_enemy(self.location, enemies)
        self.say("Nearest enemy is {d} away".format(d=enemy_distance))
        if self.should_chase(enemy_distance):
            self.say("try to chase enemy @ {l}".format(l=nearest_enemy.location))
            to_enemy = self.step_toward(self.location,
                                        nearest_enemy.location)
            if to_enemy:
                return ['move', to_enemy]

        # Otherwise, go to the gathering point
        to_gathering = self.step_toward(self.location, self.GATHERING)
        if to_gathering:
            self.say("moving towards gathering")
            return ['move', to_gathering]

        self.say("didn't move or attack, guarding")
        return ['guard']

    def step_toward(self, loc, dest):
        """Ant navigation with basic block checking
        Returns a move destination or None"""
        x0, y0 = loc
        x, y = dest
        x_diff, y_diff = x - x0, y - y0
        dx, dy = abs(x_diff), abs(y_diff)

        self.say("from {l} to {d}: delta={t}"
                 .format(l=loc, d=dest, t=(dx,dy)))

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
        filter = {'invalid', 'obstacle'}
        if not dest:
            return True
        for loc, bot in self.g['robots'].items():
            if loc == dest:
                return True
        if len(filter & set(rg.loc_types(dest))) != 0:
            return True
        return False

    def nearby_robots(self, loc):
        return [bot for loc, bot in self.g['robots'].items()
                if loc in self.surrounding]

    def choose_target(self, robots):
        """Always attack the weakest robot"""
        target = None
        min_hp = self.MAX_HP
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

    CHASE_DIST_THRESH = 5
    CHASE_HP_THRESH = 20

    def should_chase(self, nearest_dist):
        return nearest_dist < self.CHASE_DIST_THRESH \
          and self.hp > self.CHASE_HP_THRESH

    def should_run(self, enemies):
        """Run if the enemy is about to suicide or we're outnumbered"""
        return len(enemies) == 1 and \
          enemies[0].hp <= 8 \
          or len(enemies) > 1

    def find_escape(self, neighbors):
        neighbor_locs = set([n.location for n in neighbors])
        for s in self.surrounding:
            if not s in neighbor_locs:
                return s
        return None

    AVG_DAMAGE = 9

    def should_suicide(self, neighbor_enemies):
        return len(neighbor_enemies) * self.AVG_DAMAGE > self.hp

    def on_team(self, robot):
        return self.player_id == robot.player_id

    def print_turn(self):
        self.say("-- robot @ {l} [hp={hp}] starting turn {t} --"
                 .format(l=self.location, hp=self.hp, t=self.g['turn']))

    def say(self, what):
        if not self.SILENT:
            print what
