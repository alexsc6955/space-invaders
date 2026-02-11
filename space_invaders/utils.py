"""
Space Invaders utils
"""

import logging

import pygame


class Logger:
    """
    Logger class for Space Invaders
    """

    def __init__(self):

        logging.basicConfig(level=logging.DEBUG)


Logger()


logger = logging.getLogger("space_invaders")


def load_image(filename: str, transparent: bool = False) -> pygame.Surface:
    """
    Load an image

    :param filename: Name of the file
    :type filename: str

    :param transparent: Transparency flag
    :type transparent: bool

    :return: the image
    :rtype: pygame.Surface

    :raise pygame.locals.SystemExit: If the image cannot be loaded
    """
    try:
        image = pygame.image.load(filename)
    except pygame.error as message:
        raise pygame.locals.SystemExit(message)

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

    :return: the screen
    :rtype: pygame.Surface
    """
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(caption)

    return screen
