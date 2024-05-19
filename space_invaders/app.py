"""
Space Invaders game
"""


from typing import List

import pygame
from pygame.locals import *

from space_invaders.constants import WIDTH
from space_invaders.constants import HEIGHT
from space_invaders.constants import ASSETS_DIR

from space_invaders.utils import logger
from space_invaders.utils import load_image
from space_invaders.utils import set_screen

from space_invaders.ship import Ship

from space_invaders.alien import Alien


class Game:
    """
    Game class
    """
    
    _logger = logger
    
    _clock = pygame.time.Clock()
    _time = 0
    
    _carry_on = True
    
    _points = 0
    
    def __init__(self, name: str) -> None:
        
        self._logger.log(f'Initializing {name}')
        
        self._name = name
        
        pygame.init()
        
    def _set_screen(self, width: int, height: int) -> pygame.Surface:
        """
        Set the screen
        """
        
        self._logger.log('Setting screen')
        
        return set_screen(self._name, width, height)
    
    def _handle_events(self) -> None:
        """
        Handle the events
        """
        
        raise NotImplementedError('Subclasses must implement this method')
    
    def _handle_game_logic(self) -> None:
        """
        Handle the game logic
        """
        
        raise NotImplementedError('Subclasses must implement this method')
    
    def _draw_stuff(self) -> None:
        """
        Draw the stuff
        """
        
        raise NotImplementedError('Subclasses must implement this method')
        
    def _load_image(self, file: str) -> pygame.Surface:
        """
        Load the images
        """
        
        self._logger.log(f'Loading image {file}')
        
        return load_image(file) 
    
class SpaceInvaders(Game):
    """
    Space Invaders class
    """
    
    _alien_boxes: List[Alien] = []
    _aliens_count = 0
    _aliens_currnet_count = 0
    _ship = None
    _has_been_boosted = False
    
    def __init__(self) -> None:
        
        super().__init__('Space Invaders')

        self._screen = self._set_screen(WIDTH, HEIGHT)
        self._background_image = self._load_image(f'{ASSETS_DIR}/background.jpg')
        
    def _set_alien_boxes(self) -> None:
        """
        Set the boxes
        """
        
        self._logger.log('Setting boxes')
        
        for x in range(100, WIDTH - 150, 100):
            for y in range(10, 200, 60):
                self._alien_boxes.append(Alien(x, y))
                
        self._aliens_count = len(self._alien_boxes)
        self._aliens_currnet_count = self._aliens_count
        self._logger.log(f'Aliens count: {self._aliens_count}')
                
    def _set_ship(self) -> None:
        """
        Set the ship
        """
        
        self._logger.log('Setting ship')
        
        self._ship = Ship(HEIGHT - 30)
        
    def _handle_events(self) -> None:
        """
        Handle the events
        """
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._logger.log('Quitting the game')
                self._carry_on = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self._ship.shoot(self._time)
                
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self._ship.move_left(5)
        if keys[pygame.K_RIGHT]:
            self._ship.move_right(5)
                
    def _handle_game_logic(self) -> None:
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
                        self._logger.log('Hit!')
                        self._aliens_currnet_count -= 1
                        
                        # If alients count
                        if self._aliens_currnet_count <= self._aliens_count * 0.25:
                            self._points += 10
                        elif self._aliens_currnet_count <= self._aliens_count * 0.5:
                            self._points += 5
                        elif self._aliens_currnet_count <= self._aliens_count * 0.75:
                            self._points += 3
                        else:
                            self._points += 1
                            
                        self._logger.log(f'Points: {self._points}')
                        
        # if points are greater than 100, shot multiple bullets
        if self._points > 50 and not self._has_been_boosted:
            self._ship.boost()
            self._ship.shoot(self._time)
            self._has_been_boosted = True
            
        
        # Check if there are no more boxes
        if not self._alien_boxes:
            self._logger.log('You won!')
            self._carry_on = False
            
        # Check if the boxes have reached the ship
        for box in self._alien_boxes:
            if box.rect.centery >= HEIGHT - 30:
                self._logger.log('You lost!')
                self._carry_on = False
    
    def _draw_stuff(self) -> None:
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
                
    def run(self) -> None:
        """
        Run the game
        """
        
        self._logger.log('Running the game')
        
        self._set_alien_boxes()
        self._set_ship()
        
        while self._carry_on:
            self._time = self._clock.tick(60)
            self._handle_events()
            self._handle_game_logic()
            self._draw_stuff()
            
        pygame.quit()
        