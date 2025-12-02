"""
Space Invaders game
"""

from typing import List

import pygame

from space_invaders.alien import Alien
from space_invaders.constants import ASSETS_DIR, HEIGHT, WIDTH
from space_invaders.ship import Ship
from space_invaders.utils import load_image, logger, set_screen


class Game:
    """
    Game class
    """

    _clock = pygame.time.Clock()
    _time = 0

    _carry_on = True

    _points = 0

    def __init__(self, name: str):
        """
        :param name: Name of the game
        :type name: str
        """
        logger.debug(f"Initializing {name}")
        self._name = name
        pygame.init()

    def _set_screen(self, width: int, height: int) -> pygame.Surface:
        """
        Set the screen

        :param width: Width of the screen
        :type width: int

        :param height: Height of the screen
        :type height: int

        :return: pygame.Surface
        :rtype: pygame.Surface
        """

        logger.debug("Setting screen")

        return set_screen(self._name, width, height)

    def handle_events(self):
        """
        Handle the events

        :raise NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")

    def handle_game_logic(self):
        """
        Handle the game logic

        :raise NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")

    def draw_stuff(self):
        """
        Draw the stuff

        :raise NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _load_image(self, file: str) -> pygame.Surface:
        """
        Load the images

        :param file: File to load
        :type file: str

        :return: pygame.Surface
        :rtype: pygame.Surface
        """
        logger.debug(f"Loading image {file}")

        try:
            return load_image(file)
        except pygame.locals.SystemExit as e:
            logger.error(f"Failed to load image {file}: {e}")
            raise


# TODO: Refactor to use composition instead of inheritance
class SpaceInvaders(Game):  # pylint: disable=too-many-instance-attributes
    """
    Space Invaders class
    """

    _alien_boxes: List[Alien] = []
    _aliens_count = 0
    _aliens_current_count = 0
    _ship = None
    _has_been_boosted = False

    def __init__(self):
        super().__init__("Space Invaders")

        self._screen = self._set_screen(WIDTH, HEIGHT)
        self._background_image = self._load_image(f"{ASSETS_DIR}/background.jpg")

    def _set_alien_boxes(self):
        """
        Set the boxes
        """
        logger.debug("Setting boxes")

        for x in range(100, WIDTH - 150, 100):
            for y in range(10, 200, 60):
                self._alien_boxes.append(Alien(x, y))

        self._aliens_count = len(self._alien_boxes)
        self._aliens_current_count = self._aliens_count
        logger.debug(f"Aliens count: {self._aliens_count}")

    def _set_ship(self):
        """
        Set the ship
        """
        logger.debug("Setting ship")

        self._ship = Ship(HEIGHT - 30)

    def handle_events(self):
        """
        Handle the events
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.debug("Quitting the game")
                self._carry_on = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self._ship.shoot(self._time)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self._ship.move_left(5)
        if keys[pygame.K_RIGHT]:
            self._ship.move_right(5)

    def handle_game_logic(self):
        """
        Handle the game logic
        """
        # Check if the bullet has hit the boxes
        if self._ship.is_shooting:
            for bullet in self._ship.bullets:
                for box in self._alien_boxes:
                    if box.rect.colliderect(bullet.rect):
                        self._alien_boxes.remove(box)
                        self._ship.bullets.remove(bullet)
                        logger.debug("Hit!")
                        self._aliens_current_count -= 1

                        # If alients count
                        if self._aliens_current_count <= self._aliens_count * 0.25:
                            self._points += 10
                        elif self._aliens_current_count <= self._aliens_count * 0.5:
                            self._points += 5
                        elif self._aliens_current_count <= self._aliens_count * 0.75:
                            self._points += 3
                        else:
                            self._points += 1

                        logger.debug(f"Points: {self._points}")

        # if points are greater than 100, shot multiple bullets
        if self._points > 50 and not self._has_been_boosted:
            self._ship.boost()
            self._ship.shoot(self._time)
            self._has_been_boosted = True

        # Check if there are no more boxes
        if not self._alien_boxes:
            logger.debug("You won!")
            self._carry_on = False

        # Check if the boxes have reached the ship
        for box in self._alien_boxes:
            if box.rect.centery >= HEIGHT - 30:
                logger.debug("You lost!")
                self._carry_on = False

    def draw_stuff(self):
        """
        Draw the stuff
        """
        self._screen.blit(self._background_image, (0, 0))

        for alien in self._alien_boxes:
            alien.update(self._time)
            self._screen.blit(alien.image, alien.rect)

        if self._ship.is_shooting:
            for bullet in self._ship.bullets:
                bullet.update()
                self._screen.blit(bullet.image, bullet.rect)

        self._screen.blit(self._ship.image, self._ship.rect)

        pygame.display.flip()

    def run(self):
        """
        Run the game
        """
        logger.debug("Running the game")

        self._set_alien_boxes()
        self._set_ship()

        while self._carry_on:
            self._time = self._clock.tick(60)
            self.handle_events()
            self.handle_game_logic()
            self.draw_stuff()

        pygame.quit()
