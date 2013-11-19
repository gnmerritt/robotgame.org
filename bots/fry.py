import rg

class Robot(object):
    MAX_HP = 50
    GATHERING = rg.CENTER_POINT

    def act(self, game):
        self.g = game
        self.print_turn()
        self.surrounding = rg.locs_around(self.location,
                                          filter_out=('invalid', 'obstacle'))
        enemies = [r for _, r in self.g['robots'].items()
                   if not self.on_team(r)]
        print "{n} enemies alive this turn".format(n=len(enemies))
        neighbors = self.nearby_robots(self.location)
        print "saw {n} nearby robots".format(n=len(neighbors))
        neighbor_enemies = [r for r in neighbors
                            if not self.on_team(r)]
        print "saw {n} neighbor_enemies".format(n=len(neighbor_enemies))

        # Suicide?
        if self.should_suicide(neighbor_enemies):
            print "committing suicide - {e} neighbor_enemies / {hp} hp left" \
              .format(e=len(neighbor_enemies), hp=self.hp)
            return ['suicide']

        # Attack?
        target = self.choose_target(neighbor_enemies)
        if target:
            print "attacking {l}".format(l=target.location)
            return ['attack', target.location]

        # Nearby enemy?
        nearest_enemy, enemy_distance = \
           self.nearest_enemy(self.location, enemies)
        print "Nearest enemy is {d} away".format(d=enemy_distance)
        if self.should_chase(enemy_distance):
            print "chasing enemy @ {l}".format(l=nearest_enemy.location)
            return ['move',
                    rg.toward(self.location, nearest_enemy.location)]

        # Otherwise, go to the gathering point
        to_gathering = rg.toward(self.location, self.GATHERING)
        robot_in_way = [r for r in neighbors
                         if r.location == to_gathering]
        if not robot_in_way and to_gathering != self.location:
            print "moving towards gathering"
            return ['move', to_gathering]

        print "somebody in the way - guarding"
        return ['guard']

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

    CHASE_THRESHOLD = 5

    def should_chase(self, nearest_dist):
        return nearest_dist < self.CHASE_THRESHOLD

    SUICIDE_THRESHOLD = 7
    SUICIDE_TURN_THRESHOLD = 90

    def should_suicide(self, neighbor_enemies):
        return len(neighbor_enemies) > 1 \
          and self.hp < self.SUICIDE_THRESHOLD \
          and self.g['turn'] < self.SUICIDE_TURN_THRESHOLD

    def on_team(self, robot):
        return self.player_id == robot.player_id

    def print_turn(self):
        print "-- robot @ {l} starting turn {t} --" \
          .format(l=self.location, t=self.g['turn'])
