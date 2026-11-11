-- Hyprland anidado para pruebas (0.57+: la config es Lua; la sintaxis vieja,
-- notas_fase2/prueba_arrastre/anidado.conf, arranca en modo de emergencia). Se
-- abre como una ventana dentro de la sesión real: Hyprland -c tests/anidado.lua
-- (ver tests/entorno_aislado.sh). La salida mide lo que mida esa ventana, no
-- 1280x800. Cerrarlo matando SOLO su pid (cmdline con anidado.lua).
hl.monitor({ output = "", mode = "1280x800", position = "0x0", scale = 1 })

hl.config({
    misc = {
        disable_hyprland_logo   = true,
        disable_splash_rendering = true,
    },
    input = {
        follow_mouse = 1,
    },
    animations = {
        enabled = true,
    },
})

-- Mismas animaciones de capas que la sesión real.
hl.curve("emphasizedDecel", { type = "bezier", points = { { 0.05, 0.7 }, { 0.1, 1 } } })
hl.curve("emphasizedAccel", { type = "bezier", points = { { 0.3, 0 }, { 0.8, 0.15 } } })
hl.curve("standard", { type = "bezier", points = { { 0.2, 0 }, { 0, 1 } } })
hl.animation({ leaf = "layersIn", enabled = true, speed = 5, bezier = "emphasizedDecel", style = "slide" })
hl.animation({ leaf = "layersOut", enabled = true, speed = 4, bezier = "emphasizedAccel", style = "slide" })
hl.animation({ leaf = "fadeLayers", enabled = true, speed = 5, bezier = "standard" })
