import asyncio, pygame, os, sys, random

WIDTH, HEIGHT = 900, 500
NET_WIDTH = 40
NET_HEIGHT = HEIGHT / 2
PLAYER_WIDTH, PLAYER_HEIGHT = 80, 120
BALL_RADIUS = 36

GRAVITY = 1100.0
PLAYER_SPEED = 360.0
JUMP_SPEED = -650.0
BALL_SPEED_X_INITIAL = 150.0
BALL_SPEED_Y_INITIAL = 150.0
SMASH_BOOST = 420.0

WIN_SCORE = 10
TARGET_FPS = 60

async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("2-Player Earthball Game")
    pygame.mixer.music.load("assets/audio/game.ogg")
    pygame.mixer.music.set_volume(0.6)
    pygame.mixer.music.play(-1)

    clock = pygame.time.Clock()

    bg_image = pygame.image.load("assets/img/space.jpg").convert()
    net_image = pygame.image.load("assets/img/wall.jpg").convert_alpha()
    net_image = pygame.transform.scale(net_image, (NET_WIDTH, NET_HEIGHT))

    hit_sound = pygame.mixer.Sound("assets/audio/hit.ogg")
    win_sound = pygame.mixer.Sound("assets/audio/win.ogg")
    end_sound = pygame.mixer.Sound("assets/audio/end.ogg")
    smash_sound = pygame.mixer.Sound("assets/audio/smash.ogg")

    font = pygame.font.SysFont(None, 30)

    def load_scaled_image(filename, size):
        image = pygame.image.load(filename).convert_alpha()
        return pygame.transform.scale(image, size)
    
    image_specs = [("assets/img/cloud.png", (300, 300)), ("assets/img/jupiter.png", (280, 280)), ("assets/img/mars.png", (200, 200)), ("assets/img/pluto.png", (180, 180)), ("assets/img/rocket.png", (200, 200)), ("assets/img/ufo.png", (200, 200)), ("assets/img/alien.png", (240, 240))]
    floating_objects = [load_scaled_image(file, size) for file, size in image_specs]
    current_object = random.choice(floating_objects)
    object_x, object_y, object_speed = WIDTH, random.randint(0, 450), 0.5

    # --- PLAYER CLASS ---
    class Player:
        def __init__(self, x, y, controls, side, character_name, player_name):
            self.x = x
            self.y = y
            self.vx = 0
            self.vy = 0
            self.on_ground = True
            self.controls = controls
            self.sliding = False
            self.slide_timer = 0
            self.slide_duration = 0.3
            self.slide_direction = 0
            self.side = side
            self.score = 0
            self.character_name = character_name
            self.player_name = player_name
            self.animation_count = 0
            self.ANIMATION_DELAY = 5
            self.load_sprites()

        def load_sprites(self):
            def slice_sheet(path, frame_width, frame_height, num_frames, flip=False):
                sheet = pygame.image.load(path).convert_alpha()
                frames = []
                for i in range(num_frames):
                    frame = sheet.subsurface(pygame.Rect(i * frame_width, 0, frame_width, frame_height))
                    if flip:
                        frame = pygame.transform.flip(frame, True, False)
                    frame = pygame.transform.scale(frame, (100, 100))
                    frames.append(frame)
                return frames
            
            base_path = f"assets/maincharacters/{self.character_name}/"
            self.SPRITES = {
                "idle": slice_sheet(base_path + "idle.png", 32, 32, 11),
                "run": slice_sheet(base_path + "run.png", 32, 32, 12),
                "jump": slice_sheet(base_path + "jump.png", 32, 32, 1),
                "fall": slice_sheet(base_path + "fall.png", 32, 32, 1),
                "slide": slice_sheet(base_path + "slide.png", 32, 32, 5)
            }
            self.sprite = self.SPRITES["idle"][0]
            self.direction = "right"

        def update_sprite(self):
            sprite_state = "idle"
            if self.vy < 0:
                sprite_state = "jump"
            elif self.vy > 1:
                sprite_state = "fall"
            elif self.sliding:
                sprite_state = "slide"
            elif self.vx != 0:
                sprite_state = "run"
            
            if self.vx > 0: self.direction = "right"
            elif self.vx < 0: self.direction = "left"
            
            frames = self.SPRITES[sprite_state]
            frame_index = (self.animation_count // self.ANIMATION_DELAY) % len(frames)
            sprite = frames[frame_index]
            if self.direction == "left":
                sprite = pygame.transform.flip(sprite, True, False)
            self.sprite = sprite
            self.animation_count += 1

        def draw(self, win, offset_x):
            win.blit(self.sprite, (self.x - offset_x, self.y))

        def move(self, keys, WIDTH, dt):
            self.vx = 0
            if self.sliding:
                self.slide_timer -= dt
                if self.slide_timer <= 0:
                    self.sliding = False
                else:
                    self.vx = 1.5 * PLAYER_SPEED * self.slide_direction
            
            if not self.sliding:
                if keys[self.controls['left']]: self.vx = -PLAYER_SPEED
                if keys[self.controls['right']]: self.vx = PLAYER_SPEED
                if self.on_ground and keys[self.controls['jump']]:
                    self.vy = JUMP_SPEED
                    self.on_ground = False
                if self.on_ground and keys[self.controls['slide']]:
                    slide_dir = 0
                    if keys[self.controls['right']]: slide_dir = 1
                    elif keys[self.controls['left']]: slide_dir = -1
                    if slide_dir != 0:
                        self.sliding = True
                        self.slide_direction = slide_dir
                        self.slide_timer = self.slide_duration
                        self.vx = 1.5 * PLAYER_SPEED * self.slide_direction

            self.x += self.vx * dt
            self.y += self.vy * dt
            
            if not self.on_ground:
                self.vy += GRAVITY * dt

            if self.y + PLAYER_HEIGHT >= HEIGHT:
                self.y = HEIGHT - PLAYER_HEIGHT
                self.vy = 0
                self.on_ground = True

            if self.side == 'left':
                self.x = max(0, min(self.x, WIDTH // 2 - NET_WIDTH - PLAYER_WIDTH))
            else:
                self.x = max(WIDTH // 2 + NET_WIDTH, min(self.x, WIDTH - PLAYER_WIDTH))

    # --- BALL CLASS ---
    class Ball:
        def __init__(self):
            self.reset(random.choice(['left', 'right']))
            self.angle = 0
            self.image = pygame.image.load("assets/img/ball.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (BALL_RADIUS * 2, BALL_RADIUS * 2))

        def reset(self, side):
            self.x = WIDTH//8 if side == 'left' else WIDTH*7//8
            self.y = HEIGHT//4
            angle = random.uniform(-0.5, 0.5)
            self.vx = BALL_SPEED_X_INITIAL * (1 if side == 'left' else -1)
            self.vy = BALL_SPEED_Y_INITIAL * angle

        def move(self, dt):
            hit_ground = False
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vy += GRAVITY * dt
            self.angle += self.vx * 0.1 * dt

            if self.x - BALL_RADIUS < 0: self.vx *= -1; self.x = BALL_RADIUS
            if self.x + BALL_RADIUS > WIDTH: self.vx *= -1; self.x = WIDTH - BALL_RADIUS
            if self.y + BALL_RADIUS >= HEIGHT:
                self.y = HEIGHT - BALL_RADIUS
                self.vy *= -0.85
                hit_ground = True
            if self.y - BALL_RADIUS < 0: self.vy *= -1; self.y = BALL_RADIUS
            
            net_rect = pygame.Rect(WIDTH//2 - NET_WIDTH//2, HEIGHT - NET_HEIGHT, NET_WIDTH, NET_HEIGHT)
            ball_rect = pygame.Rect(self.x - BALL_RADIUS, self.y - BALL_RADIUS, BALL_RADIUS*2, BALL_RADIUS*2)
            if ball_rect.colliderect(net_rect):
                self.vx *= -1
                if self.x < WIDTH//2: self.x = net_rect.left - BALL_RADIUS
                else: self.x = net_rect.right + BALL_RADIUS
            return hit_ground

        def draw(self, surface):
            rotated_image = pygame.transform.rotate(self.image, -self.angle)
            rect = rotated_image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(rotated_image, rect)

        def collide_with_player(self, player, smash_pressed):
            player_hitbox = player.sprite.get_rect(topleft=(player.x, player.y)).inflate(-30, -20)
            ball_rect = pygame.Rect(self.x - BALL_RADIUS, self.y - BALL_RADIUS, BALL_RADIUS * 2, BALL_RADIUS * 2)

            if ball_rect.colliderect(player_hitbox):
                self.vx = (self.x - player_hitbox.centerx) * 8
                self.vy = (self.y - player_hitbox.centery) * 9
                self.vy = -abs(self.vy)
                hit_sound.play()
                if smash_pressed:
                    self.vx *= 1.5
                    self.vy -= SMASH_BOOST
                    smash_sound.play()
        

    # --- CONTROLS AND SETUP ---
    controls1 = {'left': pygame.K_a, 'right': pygame.K_d, 'jump': pygame.K_w, 'smash': pygame.K_LSHIFT, 'slide': pygame.K_s}
    controls2 = {'left': pygame.K_LEFT, 'right': pygame.K_RIGHT, 'jump': pygame.K_UP, 'smash': pygame.K_RETURN, 'slide': pygame.K_DOWN}
    


    async def show_message(msg, clock, TARGET_FPS, duration=2000): # <-- Add clock and TARGET_FPS
        start_time = pygame.time.get_ticks()
        text_surface = font.render(msg, True, (250, 240, 200))
        text_rect = text_surface.get_rect(center=(WIDTH/2, HEIGHT/2))
        bg_rect = text_rect.inflate(40, 40)
        bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 150))
        
        while pygame.time.get_ticks() - start_time < duration:
            # Calculate its own dt to control animation speed
            dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.1)

            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            
            screen.blit(bg_surface, bg_rect)
            screen.blit(text_surface, text_rect)
            pygame.display.flip()
            await asyncio.sleep(0)

    def show_play_again_button():
        button_font = pygame.font.SysFont("Segoe UI Emoji", 24)
        button_text = button_font.render("PLAY AGAIN", True, (50, 50, 50))
        button_rect = button_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 50))
        pygame.draw.rect(screen, (250, 240, 200), button_rect.inflate(30, 40), border_radius=10)
        screen.blit(button_text, button_rect)
        return button_rect

    # --- INTRO SCREEN ---
    async def show_intro_screen():
        intro_font = pygame.font.SysFont("Segoe UI Emoji", 30, bold=True)
        small_font = pygame.font.SysFont("Segoe UI Emoji", 20)
        tiny_font = pygame.font.SysFont("Segoe UI Emoji", 18)
        title_text = intro_font.render(" 2-Player Earthball Game ", True, (250, 220, 40))
        instructions = [
            "- Game Rules:",
            "• You’re floating on a space court, battling with a volleyball that looks like planet Earth!",
            "• Hit the Earthball over the cosmic net.",
            "• If it falls on the opponent’s side, you score 1 point.",
            "• First player to reach 10 points wins and becomes the Galaxy Spike Champion!",
            "",
            "- Movement Controls:",
            # We'll use a tuple to indicate table rows for rendering
            ("", "Player 1", "Player 2"),
            ("Move Left", "A", "\u2190"),
            ("Move Right", "D", "\u2192"),
            ("Jump", "W", "\u2191"),
            ("Slide", "S", "\u2193"),
            ("Smash", "Left Shift", "Enter"),
        ]
        button_font = pygame.font.SysFont("Segoe UI Emoji", 24)
        button_text = button_font.render("PLAY", True, (50, 50, 50))
        button_rect = button_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 180))
        button_bg_rect = button_rect.inflate(40, 30)

        # Left alignment x
        left_margin = 80

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if button_bg_rect.collidepoint(event.pos):
                        waiting = False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        waiting = False

            # Draw background
            for x in range(0, WIDTH, bg_image.get_width()):
                for y in range(0, HEIGHT, bg_image.get_height()):
                    screen.blit(bg_image, (x, y))
            
            # Filled background with rounded corners
            rect = pygame.draw.rect(
                screen,
                (0, 0, 0),
                (50, 80, screen.get_width() - 100, screen.get_height() - 200),
                border_radius=40
            )
            pygame.draw.rect(screen, (255, 255, 255), rect, 2, border_radius=40)

            # Draw title 
            title_img = pygame.image.load("assets/img/alien.png").convert_alpha()
            title_img = pygame.transform.scale(title_img, (60, 60))
            title_y = 30 + title_text.get_height() // 2 - title_img.get_height() // 2
            screen.blit(title_img, (screen.get_width() // 2 - title_text.get_width() // 2 - title_img.get_width() - 10, title_y))
            screen.blit(title_img, (screen.get_width() // 2 + title_text.get_width() // 2 + 10, title_y))
            screen.blit(title_text, (screen.get_width() // 2 - title_text.get_width() // 2, 40))

            # Draw instructions (left aligned)
            y_offset = 90
            for idx, line in enumerate(instructions):
                # Make section headers larger and bold
                if isinstance(line, str) and line.strip() in ["- Movement Controls:", "- Game Rules:"]:
                    header_font = pygame.font.SysFont("Segoe UI Emoji", 20, bold=True)
                    text = header_font.render(line.replace("-", "").strip(), True, (230, 230, 255))
                    screen.blit(text, (left_margin, y_offset))
                    y_offset += 24
                elif isinstance(line, str):
                    font_to_use = small_font if idx == 0 else tiny_font
                    text = font_to_use.render(line, True, (230, 230, 255))
                    screen.blit(text, (left_margin, y_offset))
                    y_offset += 24 if idx == 0 else 22
                elif isinstance(line, tuple):
                    # Render as table row (no grid lines)
                    col_width = 120
                    for col_idx, col_text in enumerate(line):
                        align_x = left_margin + col_idx * col_width
                        table_font = small_font if idx == 6 else tiny_font
                        text = table_font.render(str(col_text), True, (230, 230, 255))
                        screen.blit(text, (align_x, y_offset))
                    y_offset += 22

            # Draw play button
            pygame.draw.rect(screen, (250, 240, 200), button_bg_rect, border_radius=12)
            screen.blit(button_text, button_rect)

            pygame.display.flip()
            await asyncio.sleep(0)

    await show_intro_screen()

    # --- CHARACTER SELECTION SCREEN ---
    async def show_character_selection():
        char_list = ['maskdude', 'ninjafrog', 'pinkman', 'virtualguy']
        char_images = {}
        for char in char_list:
            img = pygame.image.load(f"assets/maincharacters/{char}/idle.png").convert_alpha()
            img = img.subsurface(pygame.Rect(0, 0, 32, 32))
            img = pygame.transform.scale(img, (100, 100))
            char_images[char] = img

        # State for both players
        selections = [
            {'char_idx': 0, 'name': '', 'active': False},
            {'char_idx': 2, 'name': '', 'active': False}
        ]
        input_boxes = [
            pygame.Rect(WIDTH//4 - 100, HEIGHT//2 + 60, 200, 36),
            pygame.Rect(WIDTH*3//4 - 100, HEIGHT//2 + 60, 200, 36)
        ]
        confirm_font = pygame.font.SysFont("Segoe UI Emoji", 24)
        confirm_text = confirm_font.render("CONFIRM", True, (50, 50, 50))
        confirm_rect = confirm_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 180))
        confirm_bg_rect = confirm_rect.inflate(40, 30)
        arrow_font = pygame.font.SysFont("Segoe UI Emoji", 48)
        left_arrow = arrow_font.render("\u21E6", True, (230, 230, 255))
        right_arrow = arrow_font.render("\u21E8", True, (230, 230, 255))
        left_arrow_rects = [
            left_arrow.get_rect(center=(WIDTH//4 - 90, HEIGHT//2)),
            left_arrow.get_rect(center=(WIDTH*3//4 - 90, HEIGHT//2))
        ]
        right_arrow_rects = [
            right_arrow.get_rect(center=(WIDTH//4 + 90, HEIGHT//2)),
            right_arrow.get_rect(center=(WIDTH*3//4 + 90, HEIGHT//2))
        ]
        name_font = pygame.font.SysFont("Segoe UI Emoji", 22)
        label_font = pygame.font.SysFont("Segoe UI Emoji", 24, bold=True)

        active_box = 0
        selections[active_box]['active'] = True

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for i in range(2):
                        if left_arrow_rects[i].collidepoint(event.pos):
                            selections[i]['char_idx'] = (selections[i]['char_idx'] - 1) % len(char_list)
                        if right_arrow_rects[i].collidepoint(event.pos):
                            selections[i]['char_idx'] = (selections[i]['char_idx'] + 1) % len(char_list)
                        if input_boxes[i].collidepoint(event.pos):
                            active_box = i
                            selections[0]['active'] = selections[1]['active'] = False
                            selections[i]['active'] = True
                    if confirm_bg_rect.collidepoint(event.pos):
                        if all(s['name'].strip() for s in selections):
                            return (
                                char_list[selections[0]['char_idx']], selections[0]['name'].strip(),
                                char_list[selections[1]['char_idx']], selections[1]['name'].strip()
                            )
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        selections[active_box]['active'] = False
                        active_box = 1 - active_box
                        selections[active_box]['active'] = True
                    elif event.key == pygame.K_RETURN:
                        if all(s['name'].strip() for s in selections):
                            return (
                                char_list[selections[0]['char_idx']], selections[0]['name'].strip(),
                                char_list[selections[1]['char_idx']], selections[1]['name'].strip()
                            )
                    elif event.key == pygame.K_BACKSPACE:
                        selections[active_box]['name'] = selections[active_box]['name'][:-1]
                    elif len(selections[active_box]['name']) < 12 and event.unicode.isprintable():
                        selections[active_box]['name'] += event.unicode

            # Draw background
            for x in range(0, WIDTH, bg_image.get_width()):
                for y in range(0, HEIGHT, bg_image.get_height()):
                    screen.blit(bg_image, (x, y))

            # Panel
            panel_rect = pygame.draw.rect(
                screen,
                (0, 0, 0),
                (50, 80, screen.get_width() - 100, screen.get_height() - 200),
                border_radius=40
            )
            pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2, border_radius=40)

            # Title
            intro_font = pygame.font.SysFont("Segoe UI Emoji", 30, bold=True)
            title_text = intro_font.render(" 2-Player Earthball Game ", True, (250, 220, 40))
            title_img = pygame.image.load("assets/img/alien.png").convert_alpha()
            title_img = pygame.transform.scale(title_img, (60, 60))
            title_y = 30 + title_text.get_height() // 2 - title_img.get_height() // 2
            screen.blit(title_img, (screen.get_width() // 2 - title_text.get_width() // 2 - title_img.get_width() - 10, title_y))
            screen.blit(title_img, (screen.get_width() // 2 + title_text.get_width() // 2 + 10, title_y))
            screen.blit(title_text, (screen.get_width() // 2 - title_text.get_width() // 2, 40))
            
            text = label_font.render("Select Your Character and Input Your Name", True, (100, 100, 100))
            screen.blit(text, (WIDTH//2 - text.get_width()//2, 100))

            # Player 1 and 2 labels
            p1_label = label_font.render("Player 1", True, (230, 230, 255))
            p2_label = label_font.render("Player 2", True, (230, 230, 255))
            screen.blit(p1_label, (WIDTH//4 - p1_label.get_width()//2, HEIGHT//2 - 110))
            screen.blit(p2_label, (WIDTH*3//4 - p2_label.get_width()//2, HEIGHT//2 - 110))

            # Character previews and arrows
            for i in range(2):
                idx = selections[i]['char_idx']
                char = char_list[idx]
                img = char_images[char]
                x_center = WIDTH//4 if i == 0 else WIDTH*3//4
                screen.blit(img, (x_center - img.get_width()//2, HEIGHT//2 - img.get_height()//2))
                screen.blit(left_arrow, left_arrow_rects[i])
                screen.blit(right_arrow, right_arrow_rects[i])

            # Name input boxes
            for i in range(2):
                color = (250, 220, 40) if selections[i]['active'] else (200, 200, 200)
                pygame.draw.rect(screen, color, input_boxes[i], 2, border_radius=8)
                name_surface = name_font.render(selections[i]['name'] or "Enter your name...", True, (230, 230, 255) if selections[i]['name'] else (150, 150, 150))
                screen.blit(name_surface, (input_boxes[i].x + 8, input_boxes[i].y + 6))

            # Confirm button
            pygame.draw.rect(screen, (250, 240, 200), confirm_bg_rect, border_radius=12)
            screen.blit(confirm_text, confirm_rect)

            pygame.display.flip()
            await asyncio.sleep(0)

    # --- Show character selection and get choices ---
    char1, name1, char2, name2 = await show_character_selection()

    player1 = Player(120, HEIGHT - PLAYER_HEIGHT, controls1, side='left', character_name=char1, player_name=name1 or 'Player 1')
    player2 = Player(WIDTH - 120 - PLAYER_WIDTH, HEIGHT - PLAYER_HEIGHT, controls2, side='right', character_name=char2, player_name=name2 or 'Player 2')


    ball = Ball()

    game_state = "playing"
    winner = None
    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.1)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if game_state == "game_over":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    play_again_rect = show_play_again_button()
                    if play_again_rect.collidepoint(event.pos):
                        game_state, winner = "playing", None
                        player1.score, player2.score = 0, 0
                        ball.reset(random.choice(['left', 'right']))
                        player1.x, player1.y = 100, HEIGHT - PLAYER_HEIGHT
                        player2.x, player2.y = WIDTH - 100 - PLAYER_WIDTH, HEIGHT - PLAYER_HEIGHT
                        pygame.mixer.music.play(-1)

        # Draw Sky background        
        for x in range(0, WIDTH, bg_image.get_width()):
            for y in range(0, HEIGHT, bg_image.get_height()):
                screen.blit(bg_image, (x, y))
        
        # Floating object
        screen.blit(current_object, (object_x, object_y))
        object_x -= object_speed
        if object_x + current_object.get_width() < 0:
            current_object = random.choice(floating_objects)
            object_x = WIDTH
            object_y = random.randint(0, 450)
        
        #Ground
        pygame.draw.rect(screen, (50, 50, 50), (0, HEIGHT - 40, WIDTH, 40))

        # Net
        screen.blit(net_image, (WIDTH // 2 - NET_WIDTH // 2, HEIGHT - NET_HEIGHT))

        player1.draw(screen, 0)
        player2.draw(screen, 0)
        ball.draw(screen)
        name_text = font.render(f"{player1.player_name.upper()} : {player2.player_name.upper()}", True, (250, 240, 200))
        screen.blit(name_text, (WIDTH//2 - name_text.get_width()//2, 20))
        score_text = font.render(f"{player1.score} : {player2.score}", True, (250, 240, 200))
        screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, 60))

        if game_state == "playing":
            player1.update_sprite()
            player2.update_sprite()
            player1.move(keys, WIDTH, dt)
            player2.move(keys, WIDTH, dt)
            ground_was_hit = ball.move(dt)
            ball.collide_with_player(player1, keys[controls1['smash']])
            ball.collide_with_player(player2, keys[controls2['smash']])

            if ground_was_hit:
                scorer, reset_side = (player2, 'left') if ball.x < WIDTH / 2 else (player1, 'right')
                scorer.score += 1
                if scorer.score >= WIN_SCORE:
                    winner = f"{scorer.player_name.upper()} WINS!"
                    game_state = "game_over"
                    pygame.mixer.music.stop()
                    end_sound.play()
                else:
                    win_sound.play()
                    await show_message(f"{scorer.player_name.upper()} SCORES!", clock, TARGET_FPS)
                    ball.reset(reset_side)
                    player1.x, player1.y = 100, HEIGHT - PLAYER_HEIGHT
                    player2.x, player2.y = WIDTH - 100 - PLAYER_WIDTH, HEIGHT - PLAYER_HEIGHT

        if game_state == "game_over":
            winner_text = font.render(winner, True, (250, 240, 200))
            screen.blit(winner_text, (WIDTH//2 - winner_text.get_width()//2, HEIGHT//2 - winner_text.get_height()//2 - 50))
            show_play_again_button()

        
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()

asyncio.run(main())