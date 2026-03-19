"""
System pipeline helpers for Space Invaders scene setup.
"""

from __future__ import annotations

from space_invaders.scenes.space_invaders.systems import (
    AlienAnimationSystem,
    AlienFireSystem,
    AlienSystem,
    BulletAlienCollisionSystem,
    BulletAnimationSystem,
    BulletBulletCollisionSystem,
    BulletCleanupSystem,
    BulletCullSystem,
    BulletMissileCollisionSystem,
    BulletMotionBundle,
    BulletShelterCollisionSystem,
    BulletShieldCollisionSystem,
    BulletShipCollisionSystem,
    BulletSpawnSystem,
    EffectsSystem,
    ExplosionSystem,
    MissileAlienCollisionSystem,
    MissileCleanupSystem,
    MissileCullSystem,
    MissileHomingSystem,
    MissileSpawnSystem,
    MissileTargetSystem,
    OmegaRayDamageSystem,
    OmegaRaySystem,
    RoundStateSystem,
    ShieldSystem,
    ShipExplosionLifecycleSystem,
    ShipMovementBundle,
    UfoCollisionSystem,
    UfoSystem,
)


def build_space_invaders_systems() -> tuple[object, ...]:
    """
    Build the ordered gameplay systems for Space Invaders.
    """
    return (
        ShieldSystem(),
        MissileTargetSystem(),
        ShipMovementBundle(),
        UfoSystem(),
        OmegaRaySystem(),
        MissileSpawnSystem(),
        BulletSpawnSystem(),
        BulletMissileCollisionSystem(),
        BulletBulletCollisionSystem(),
        AlienSystem(),
        AlienAnimationSystem(),
        AlienFireSystem(),
        BulletMotionBundle(),
        BulletAnimationSystem(),
        ShipExplosionLifecycleSystem(),
        MissileHomingSystem(),
        MissileAlienCollisionSystem(),
        UfoCollisionSystem(),
        BulletAlienCollisionSystem(),
        BulletShelterCollisionSystem(),
        BulletShieldCollisionSystem(),
        BulletShipCollisionSystem(),
        OmegaRayDamageSystem(),
        ExplosionSystem(),
        MissileCullSystem(),
        MissileCleanupSystem(),
        BulletCullSystem(),
        BulletCleanupSystem(),
        RoundStateSystem(),
        EffectsSystem(),
    )


__all__ = ["build_space_invaders_systems"]
