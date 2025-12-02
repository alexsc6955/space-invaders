"""
This is the main file to run the game.
It imports the main function from the space_invaders file and runs it.
"""

from space_invaders.app import SpaceInvaders

if __name__ == "__main__":
    game = SpaceInvaders()
    game.run()
