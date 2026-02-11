# Space Invaders 🎮

A small **Space Invaders clone built with Python and Pygame**, focusing on clean code, basic game architecture, and a tiny but readable codebase.  
It’s a simple project, but structured as a real application: clear modules, logging, and a separable game loop.

---

## Features

- Classic Space Invaders–style gameplay:
  - Move the ship left/right and shoot aliens.
  - Aliens move horizontally and bounce back on screen edges.
  - Score increases based on how many aliens are left.
  - Bullet “boost” unlocks after reaching a score threshold.
- Basic game architecture:
  - `Game` base class with a clear game loop (`events → logic → draw`).
  - `SpaceInvaders` concrete implementation.
- Utility layer:
  - Centralized image loading and error handling.
  - Simple logging setup for debugging.

---

## Tech Stack

- **Python 3.9+**
- **Pygame** for rendering and input
- **Black**, **isort**, **Pylint** for formatting and linting

---

## Project Structure

```text
space-invaders/
├─ manage.py              # Application entry point
└─ space_invaders/
   ├─ __init__.py
   ├─ app.py             # Game loop and main SpaceInvaders class
   ├─ alien.py           # Alien sprite logic
   ├─ ship.py            # Ship and Bullet classes
   ├─ constants.py       # Screen size and paths
   └─ utils.py           # Logging, image loading, screen setup
```

---

## How to Run

```bash
# Create and activate a virtualenv (optional but recommended)
python -m venv .venv
.\.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the game
python manage.py
```

---

## Controls

- ← / → – Move the ship
- Space – Shoot
- Close the window to exit the game.

## What I Focused On

-This project is intentionally small, but I treated it like a “real” application to practice and show:

- **Game loop architecture**
  A base Game class defines the structure (handle_events, handle_game_logic, draw_stuff, run), and SpaceInvaders provides the concrete behavior. It keeps the loop readable and easy to extend.
- **Separation of concerns**
  - ``alien.py``, ``ship.py``, ``constants.py``, and each have a clear responsibility.
  - Utility functions handle image loading, screen setup, and logging so the game logic stays focused on gameplay.
- **Sprite-based design**
  ``Alien``, ``Ship``, and ``Bullet`` all inherit from ``pygame.sprite.Sprite``, which matches how real Pygame projects structure entities.
- **Code quality & tooling**
  - Type hints throughout the code.
  - Linting with Pylint, formatting with Black, and import sorting with isort.
  - Some Pylint warnings are explicitly documented and disabled where they clash with game-style code (e.g. many attributes on a game object).
- **Room for evolution**
  There are TODOs in the code (e.g. moving from inheritance to composition in the game layer, splitting bullets into their own module) to make it clear how this could grow into a more complex project without becoming a ball of mud.
