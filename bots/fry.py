import rg

class Robot(object):
    MAX_HP = 50
    GATHERING = rg.CENTER_POINT

    def act(self, game):
        self.g = game
        self.print_turn()
        self.surrounding = rg.locs_around(self.location,
                                          filter_out=('invalid', 'obstacle'))
        neighbors = self.nearby_robots(self.location)
        print "saw {} nearby robots".format(len(neighbors))
        enemies = [r for r in neighbors
                   if not self.on_team(r)]
        print "saw {} enemies".format(len(enemies))

        if self.should_suicide(enemies):
            print "committing suicide - {e} enemies / {hp} hp left" \
              .format(e=len(enemies), hp=self.hp)
            return ['suicide']

        target = self.choose_target(enemies)
        if target:
            print "attacking {}".format(target.location)
            return ['attack', target.location]

        to_gathering = rg.toward(self.location, self.GATHERING)
        robot_in_way = [r for r in neighbors
                         if r.location == to_gathering]
        if not robot_in_way:
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

    SUICIDE_THRESHOLD = 7
    SUICIDE_TURN_THRESHOLD = 90

    def should_suicide(self, enemies):
        return len(enemies) > 1 \
          and self.hp < self.SUICIDE_THRESHOLD \
          and self.g['turn'] < self.SUICIDE_TURN_THRESHOLD

    def on_team(self, robot):
        return self.player_id == robot.player_id

    def print_turn(self):
        print "-- robot @ {l} starting turn {t} --" \
          .format(l=self.location, t=self.g['turn'])
