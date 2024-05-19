"""
Alien class
"""


import pygame

from space_invaders.constants import WIDTH
from space_invaders.constants import HEIGHT

from space_invaders.utils import load_image


class Alien(pygame.sprite.Sprite):
    """
    Alien class
    """
    
    def __init__(self, x: int,y: int) -> None:
        
        pygame.sprite.Sprite.__init__(self)
        
        self.image = load_image('assets/alien.jpg', transparent=True)
        
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.centery = y
        
        self.speed = [0.2, 0.9]
        
    def update(self, time: int) -> None:
        """
        Update the position of the alien
        
        :param time: int
        :type time: int
        
        :return: None
        """
        
        self.rect.centerx += self.speed[0] * time
        
        if self.rect.left <= 0:
            self.speed[0] = -self.speed[0]
            self.speed[1] = -self.speed[1]
            
            self.rect.centerx += self.speed[0] * time
            self.rect.centery += self.speed[1] * time
            
        if self.rect.right >= WIDTH:
            self.speed[0] = -self.speed[0]
            self.speed[1] = -self.speed[1]
            
            self.rect.centerx += self.speed[0] * time
            self.rect.centery -= self.speed[1] * time
