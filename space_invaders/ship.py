"""
Ship class
"""


from typing import List

import pygame

from space_invaders.constants import WIDTH

from space_invaders.utils import logger
from space_invaders.utils import load_image


class Bullet(pygame.sprite.Sprite):
    """
    Bullet class
    """
    
    def __init__(self, color: str, size: tuple, position: tuple, speed: int, diagonal_speed: int = 0) -> None:
        
        pygame.sprite.Sprite.__init__(self)
        
        self.image = pygame.Surface(size)
        self.image.fill(color)
        
        self.rect = self.image.get_rect()
        self.rect.center = position
        
        self.speed = speed
        self.diagonal_speed = diagonal_speed
        
    def update(self) -> None:
        """
        Update the position of the bullet
        """
        
        self.rect.centery -= self.speed
        
        if self.diagonal_speed > 0:
            self.rect.centerx += self.diagonal_speed
        elif self.diagonal_speed < 0:
            self.rect.centerx -= self.diagonal_speed
            
        if self.rect.top <= 0:
            self.kill()
            
        if self.rect.left <= 0:
            self.kill()
            
        if self.rect.right >= WIDTH:
            self.kill()
            
        if self.rect.bottom <= 0:
            self.kill()

class Ship(pygame.sprite.Sprite):
    """
    Ship class
    """
    
    _logger = logger
    
    is_shooting = False
    bullets: List[Bullet] = []
    _cooldown = 0
    _bullet_boost = False
    
    def __init__(self, y: int) -> None:
        
        pygame.sprite.Sprite.__init__(self)
        
        self.image = load_image('assets/ship.jpg', transparent=True)
        
        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH / 2
        self.rect.centery = y
        
        self.speed = 0.5
        
    def move_left(self, pixels: int) -> None:
        """
        Move the ship left
        
        :param pixels: int
        :type pixels: int
        """
        
        self.rect.centerx -= pixels
        
        if self.rect.left <= 0:
            self.rect.left = 0
        
    def move_right(self, pixels: int) -> None:
        """
        Move the ship right
        
        :param pixels: int
        :type pixels: int
        """
        
        self.rect.centerx += pixels
        
        if self.rect.right >= WIDTH:
            self.rect.right = WIDTH

    def boost(self) -> None:
        """
        Boost the ship
        """
        
        self._bullet_boost = True

    def shoot(self, time: int) -> None:
        """
        Shoot a bullet
        
        :param time: To calculate the cooldown
        :type time: int
        """
        
        if self.is_shooting and self._cooldown > 0:
            self._cooldown -= time
            self._logger.log(f'Cooldown: {self._cooldown}')
            return
        
        if self._bullet_boost:
            # Shoot 3 bullets at once
            bullet_center = Bullet((255, 0, 0), (5, 10), (self.rect.centerx, self.rect.top), 3)
            bullet_left = Bullet((255, 0, 0), (5, 10), (self.rect.centerx - 10, self.rect.top), 5, diagonal_speed=2)
            bullet_right = Bullet((255, 0, 0), (5, 10), (self.rect.centerx + 10, self.rect.top), 5, diagonal_speed=-2)
            
            self.bullets.append(bullet_center)
            self.bullets.append(bullet_left)
            self.bullets.append(bullet_right)
            
            self._bullet_boost = False
            self._cooldown = 10
            
            self._logger.log(f'Shooting bullets at {bullet_center.rect.center}, {bullet_left.rect.center}, {bullet_right.rect.center}')
            return
            
        bullet = Bullet((255, 0, 0), (5, 10), (self.rect.centerx, self.rect.top), 3)
        self.is_shooting = True
        self.bullets.append(bullet)
        self._cooldown = 10
        
        self._logger.log(f'Shooting bullet at {bullet.rect.center}')
