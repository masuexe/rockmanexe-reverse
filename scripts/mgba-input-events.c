// Test-only SDL event source for the ordinary mGBA SDL frontend.
// Compile: cc -shared -fPIC -o input-events.so mgba-input-events.c -ldl
// EXE6_INPUT_MASK_FILE contains a decimal GBA key bitmask (0..1023).
// This changes frontend key input; it does not patch ROM or game RAM.
#define _GNU_SOURCE
#include <SDL2/SDL.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int SDL_PollEvent(SDL_Event *event) {
    static int (*original)(SDL_Event *);
    static unsigned delivered;
    static const SDL_Keycode keys[10] = {
        SDLK_x, SDLK_z, SDLK_BACKSPACE, SDLK_RETURN,
        SDLK_RIGHT, SDLK_LEFT, SDLK_UP, SDLK_DOWN, SDLK_s, SDLK_a
    };
    static const SDL_Scancode scans[10] = {
        SDL_SCANCODE_X, SDL_SCANCODE_Z, SDL_SCANCODE_BACKSPACE, SDL_SCANCODE_RETURN,
        SDL_SCANCODE_RIGHT, SDL_SCANCODE_LEFT, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN,
        SDL_SCANCODE_S, SDL_SCANCODE_A
    };
    if (!original) original = dlsym(RTLD_NEXT, "SDL_PollEvent");
    unsigned wanted = delivered;
    const char *path = getenv("EXE6_INPUT_MASK_FILE");
    FILE *file = path ? fopen(path, "r") : NULL;
    if (file) {
        if (fscanf(file, "%u", &wanted) != 1) wanted = delivered;
        fclose(file);
    }
    wanted &= 1023;
    if (event) {
        for (unsigned i = 0; i < 10; ++i) {
            unsigned bit = 1u << i;
            if (!((wanted ^ delivered) & bit)) continue;
            memset(event, 0, sizeof(*event));
            event->type = (wanted & bit) ? SDL_KEYDOWN : SDL_KEYUP;
            event->key.state = (wanted & bit) ? SDL_PRESSED : SDL_RELEASED;
            event->key.keysym.sym = keys[i];
            event->key.keysym.scancode = scans[i];
            delivered ^= bit;
            return 1;
        }
    }
    return original(event);
}
