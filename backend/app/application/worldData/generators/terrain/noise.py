def cell_z_noise(world_seed_val: int, x: int, y: int, base_z: int, amplitude: int = 1) -> int:
    h = (world_seed_val ^ (x * 73856093) ^ (y * 19349663)) & 0xFFFFFFFF
    noise = (h % (2 * amplitude + 1)) - amplitude
    return base_z + noise
