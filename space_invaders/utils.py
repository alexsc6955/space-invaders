"""
Space Invaders utils
"""


import logging

import pygame
from pygame.locals import *


class Logger:
    """
    Logger class for Space Invaders
    """
    
    def __init__(self) -> None:
        
        logging.basicConfig(level=logging.DEBUG)

    def log(self, message: str) -> None:
        """
        Log a message.
        """
        
        logging.debug(message)


logger = Logger()


def load_image(filename: str, transparent: bool = False) -> pygame.Surface:
    """
    Load an image
    
    :param filename: Name of the file
    :type filename: str
    
    :param transparent: Transparency flag
    :type transparent: bool
    
    :return: pygame.Surface
    """
    
    try:
        image = pygame.image.load(filename)
    except pygame.error as message:
        raise SystemExit(message)
    
    image = image.convert()
    if transparent:
        color = image.get_at((0, 0))
        image.set_colorkey(color, pygame.RLEACCEL)
        
    return image

def set_screen(caption: str, width: int, height: int) -> pygame.Surface:
    """
    Set the screen
    
    :param caption: Caption of the screen
    :type caption: str
    
    :param width: Width of the screen
    :type width: int
    
    :param height: Height of the screen
    :type height: int
    
    :return: pygame.Surface
    """
    
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(caption)
    
    return screen

