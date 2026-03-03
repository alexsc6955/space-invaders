"""
Custom DrawOps for Space Invaders overlays.
"""

from __future__ import annotations

from mini_arcade_core.backend import Backend
from mini_arcade_core.scenes.sim_scene import Drawable

from space_invaders.entities import Alien, EntityId, Ship
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersTickContext,
)


class DrawShieldOverlay(Drawable[SpaceInvadersTickContext]):
    """
    Draw ship shield effect when active.
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext) -> None:
        w = ctx.world
        if not w.shield_active or w.shield_anim is None:
            return

        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
        if ship is None or getattr(ship, "exploding", False):
            return

        sx, sy = ship.transform.center.to_tuple()
        sw, sh = ship.transform.size.to_tuple()
        scale = float(getattr(w, "shield_scale", 1.35))
        tw = sw * scale
        th = sh * scale
        tx = sx + sw / 2.0 - tw / 2.0
        ty = sy + sh / 2.0 - th / 2.0
        backend.render.draw_texture(
            int(w.shield_anim.current_frame),
            int(tx),
            int(ty),
            int(tw),
            int(th),
        )


class DrawEffects(Drawable[SpaceInvadersTickContext]):
    """
    Draw active transient effects.
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext) -> None:
        for fx in ctx.world.effects:
            if not fx.alive:
                continue
            backend.render.draw_texture(
                int(fx.texture),
                int(fx.position.x),
                int(fx.position.y),
                int(fx.size.width),
                int(fx.size.height),
            )


class DrawOmegaRay(Drawable[SpaceInvadersTickContext]):
    """
    Draw omega charge and beam overlays.
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext) -> None:
        w = ctx.world
        if w.omega_x is None:
            return

        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
        if ship is None:
            return

        _, sy = ship.transform.center.to_tuple()
        beam_w = float(w.omega_width)
        beam_x = float(w.omega_x)

        if w.omega_charge_timer > 0 and w.omega_charge_anim:
            backend.render.draw_texture(
                int(w.omega_charge_anim.current_frame),
                int(beam_x),
                int(max(0.0, sy - 24.0)),
                int(beam_w),
                24,
            )
            return

        if not (
            w.omega_active and w.omega_beam_anim and w.omega_beam_large_anim
        ):
            return

        beam_h = max(0.0, sy)
        if beam_h <= 0:
            return

        backend.render.draw_texture(
            int(w.omega_beam_anim.current_frame),
            int(beam_x),
            0,
            int(beam_w),
            int(beam_h),
        )
        base_h = min(float(w.omega_large_height), beam_h)
        base_y = max(0.0, sy - base_h)
        backend.render.draw_texture(
            int(w.omega_beam_large_anim.current_frame),
            int(beam_x),
            int(base_y),
            int(beam_w),
            int(base_h),
        )


class DrawMissileTarget(Drawable[SpaceInvadersTickContext]):
    """
    Draw target marker for missile mode.
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext) -> None:
        w = ctx.world
        if not w.missile_targeting or w.target_texture is None:
            return

        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        alive = [a for a in aliens if not getattr(a, "exploding", False)]
        idx = w.missile_target_idx
        if not alive or idx is None or not (0 <= idx < len(alive)):
            return

        alien = alive[idx]
        ax, ay = alien.transform.center.to_tuple()
        aw, ah = alien.transform.size.to_tuple()
        scale = float(getattr(w, "target_scale", 1.35))
        tw = aw * scale
        th = ah * scale
        tx = ax + aw / 2.0 - tw / 2.0
        ty = ay + ah / 2.0 - th / 2.0
        backend.render.draw_texture(
            int(w.target_texture),
            int(tx),
            int(ty),
            int(tw),
            int(th),
        )


class DrawRegionTint(Drawable[SpaceInvadersTickContext]):
    """
    Draw regional color bands to emulate cabinet-style screen tint.
    """

    shelter_tint = (90, 255, 120, 100)
    ufo_tint = (255, 70, 70, 110)
    _ufo_fallback_y = 36.0
    _ufo_fallback_h = 22.0
    _shelter_fallback_y_ratio = 0.76
    _shelter_fallback_h = 40.0
    _padding = 10.0
    _bg_delta_threshold = 18

    @staticmethod
    def _clamp_band(top: float, bottom: float, height: float) -> tuple[int, int]:
        y0 = max(0.0, min(height, top))
        y1 = max(0.0, min(height, bottom))
        if y1 <= y0:
            return (0, 0)
        return (int(y0), int(y1 - y0))

    @staticmethod
    def _alpha_index(pixels: bytes, *, count: int) -> int:
        if count <= 0:
            return 3
        sample_px = min(count, 2048)
        step = max(1, count // sample_px)
        sums = [0, 0, 0, 0]
        for px in range(0, count, step):
            i = px * 4
            sums[0] += pixels[i]
            sums[1] += pixels[i + 1]
            sums[2] += pixels[i + 2]
            sums[3] += pixels[i + 3]
        return max(range(4), key=lambda idx: sums[idx])

    @staticmethod
    def _rgb_indices(alpha_idx: int) -> tuple[int, int, int]:
        # Common cases:
        # - ARGB bytes: A,R,G,B -> alpha_idx=0
        # - BGRA bytes: B,G,R,A -> alpha_idx=3
        if alpha_idx == 0:
            return (1, 2, 3)
        if alpha_idx == 3:
            return (2, 1, 0)
        # Fallback for unusual layouts.
        channels = [0, 1, 2, 3]
        channels.remove(alpha_idx)
        return (channels[0], channels[1], channels[2])

    @classmethod
    def _paint_band(
        cls,
        out_rgba: bytearray,
        *,
        vw: int,
        vh: int,
        cap_w: int,
        cap_h: int,
        cap: bytes,
        rgb_idx: tuple[int, int, int],
        bg_rgb: tuple[int, int, int],
        y0: int,
        h: int,
        tint: tuple[int, int, int, int],
    ) -> None:
        if h <= 0 or vw <= 0 or vh <= 0:
            return
        y1 = min(vh, y0 + h)
        if y1 <= y0:
            return

        tr, tg, tb, ta = tint
        bg_r, bg_g, bg_b = bg_rgb
        ri, gi, bi = rgb_idx
        for y in range(y0, y1):
            sy = min(cap_h - 1, int((y * cap_h) / vh))
            src_row = sy * cap_w * 4
            dst_row = y * vw * 4
            for x in range(vw):
                sx = min(cap_w - 1, int((x * cap_w) / vw))
                si = src_row + (sx * 4)
                sr = cap[si + ri]
                sg = cap[si + gi]
                sb = cap[si + bi]
                delta = abs(int(sr) - bg_r) + abs(int(sg) - bg_g) + abs(
                    int(sb) - bg_b
                )
                if delta <= cls._bg_delta_threshold:
                    continue
                di = dst_row + (x * 4)
                out_rgba[di] = tr
                out_rgba[di + 1] = tg
                out_rgba[di + 2] = tb
                out_rgba[di + 3] = ta

    @staticmethod
    def _estimate_bg_rgb(
        cap: bytes, cap_w: int, cap_h: int, rgb_idx: tuple[int, int, int]
    ) -> tuple[int, int, int]:
        ri, gi, bi = rgb_idx
        hist: dict[tuple[int, int, int], int] = {}

        def add_at(x: int, y: int) -> None:
            i = ((y * cap_w) + x) * 4
            # Quantize slightly to stabilize against tiny capture noise.
            q = (
                int(cap[i + ri]) // 8,
                int(cap[i + gi]) // 8,
                int(cap[i + bi]) // 8,
            )
            hist[q] = hist.get(q, 0) + 1

        sx = max(1, cap_w // 80)
        sy = max(1, cap_h // 80)

        for x in range(0, cap_w, sx):
            add_at(x, 0)
            add_at(x, cap_h - 1)
        for y in range(0, cap_h, sy):
            add_at(0, y)
            add_at(cap_w - 1, y)

        if not hist:
            return (0, 0, 0)
        qbg = max(hist.items(), key=lambda kv: kv[1])[0]
        return (qbg[0] * 8, qbg[1] * 8, qbg[2] * 8)

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext) -> None:
        w = ctx.world
        vw = int(w.viewport[0])
        vh = int(w.viewport[1])
        if vw <= 0 or vh <= 0:
            return

        # UFO top-lane tint (red): draw full-width band where UFO travels.
        ufo = w.get_entity_by_id(EntityId.UFO)
        if ufo is not None:
            _, uy = ufo.transform.center.to_tuple()
            _, uh = ufo.transform.size.to_tuple()
            ufo_top = uy - self._padding
            ufo_bottom = uy + uh + self._padding
        else:
            ufo_top = self._ufo_fallback_y - self._padding
            ufo_bottom = self._ufo_fallback_y + self._ufo_fallback_h + self._padding

        ufo_y, ufo_h = self._clamp_band(ufo_top, ufo_bottom, vh)

        # Shelter lane tint (green): full-width band around shelters.
        shelters = w.get_entities_by_id_range(
            EntityId.SHELTER_START, EntityId.SHELTER_END
        )
        if shelters:
            min_y = float("inf")
            max_y = 0.0
            for shelter in shelters:
                _, sy = shelter.transform.center.to_tuple()
                _, sh = shelter.transform.size.to_tuple()
                min_y = min(min_y, sy)
                max_y = max(max_y, sy + sh)
            shelter_top = min_y - self._padding
            shelter_bottom = max_y + self._padding
        else:
            shelter_top = (vh * self._shelter_fallback_y_ratio) - self._padding
            shelter_bottom = shelter_top + self._shelter_fallback_h + (
                self._padding * 2.0
            )

        shelter_y, shelter_h = self._clamp_band(shelter_top, shelter_bottom, vh)
        if ufo_h <= 0 and shelter_h <= 0:
            return

        try:
            cap_w, cap_h, cap = backend.capture.argb8888_bytes()
        except Exception:  # pylint: disable=broad-exception-caught
            return
        if cap_w <= 0 or cap_h <= 0 or not cap:
            return

        cap_w = int(cap_w)
        cap_h = int(cap_h)
        pixel_count = min(cap_w * cap_h, len(cap) // 4)
        if pixel_count <= 0:
            return

        alpha_idx = self._alpha_index(cap, count=pixel_count)
        rgb_idx = self._rgb_indices(alpha_idx)
        bg_rgb = self._estimate_bg_rgb(cap, cap_w, cap_h, rgb_idx)

        overlay = bytearray(vw * vh * 4)
        self._paint_band(
            overlay,
            vw=vw,
            vh=vh,
            cap_w=cap_w,
            cap_h=cap_h,
            cap=cap,
            rgb_idx=rgb_idx,
            bg_rgb=bg_rgb,
            y0=int(ufo_y),
            h=int(ufo_h),
            tint=self.ufo_tint,
        )
        self._paint_band(
            overlay,
            vw=vw,
            vh=vh,
            cap_w=cap_w,
            cap_h=cap_h,
            cap=cap,
            rgb_idx=rgb_idx,
            bg_rgb=bg_rgb,
            y0=int(shelter_y),
            h=int(shelter_h),
            tint=self.shelter_tint,
        )

        tex = int(backend.render.create_texture_rgba(vw, vh, bytes(overlay)))
        if tex <= 0:
            return
        try:
            backend.render.draw_texture(tex, 0, 0, vw, vh)
        finally:
            backend.render.destroy_texture(tex)

