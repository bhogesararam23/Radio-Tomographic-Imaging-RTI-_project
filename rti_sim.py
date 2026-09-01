# rti_sim.py
# trying to reproduce the main idea from UbiqMap:
#   "Ubiquitous Indoor Mapping using Mobile Radio Tomography"
#   Basu, Chakraborty, Jajal - IEEE TMC 2024 (SeNSE group, IIT Madras)
#
# the idea still feels a bit unreal to me: you can map a building using just
# radio signals, no cameras. a wall blocks a signal more than empty air, so if
# you send a signal from point A to point B and measure how much got lost, that
# one number tells you something about the stuff in between. do it from enough
# different angles and you can solve the whole map backwards - like a CT scan
# but with radio.
#
# i based the forward model and solvers on the group's own tutorial code:
#   https://github.com/ayoniitm/rti_tutorial
#   https://cse.iitm.ac.in/~sense/

import numpy as np
import matplotlib
matplotlib.use("Agg")  # no screen here, just save a png
import matplotlib.pyplot as plt

# attenuation per pixel. same numbers as the tutorial.
OPEN = 0.10    # empty air, barely blocks anything
WALL = 2.0     # walls / furniture block a lot
NOISE = 0.02   # a bit of measurement noise so it's not too easy

N = 40  # 40x40 grid = 1600 unknown pixels to recover


def make_world():
    # the "real" floor plan. the algorithm only ever sees the measurements,
    # never this grid - i keep it around just to check how well it did.
    w = np.zeros((N, N))

    # outside walls
    w[0, :] = w[-1, :] = 1
    w[:, 0] = w[:, -1] = 1

    # wall down the middle with a gap for the door
    w[18:20, :] = 1
    w[18:20, 16:24] = 0

    # second wall on the right side
    w[26:36, 28:30] = 1

    # some furniture blocks (pretend: sofa, table)
    w[6:9, 6:11] = 1
    w[28:31, 8:13] = 1
    w[8:11, 28:34] = 1
    return w


def bresenham(p0, p1):
    # all the cells a straight line between p0 and p1 passes through.
    # same bresenham as the tutorial's waypoints.py. (i first tried
    # np.linspace + rounding, but it skipped cells sometimes.)
    r0, c0 = p0
    r1, c1 = p1
    dcol = abs(c1 - c0)
    drow = -abs(r1 - r0)
    sc = 1 if c0 < c1 else -1
    sr = 1 if r0 < r1 else -1
    err = dcol + drow
    r, c = r0, c0
    cells = []
    while True:
        cells.append((r, c))
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 >= drow:
            err += drow
            c += sc
        if e2 <= dcol:
            err += dcol
            r += sr
    return cells


def walk_route():
    # the mobile radio walks around the outside edge, one cell at a time.
    # (in the real system this is a robot / wearable walking the building)
    cells = [(0, c) for c in range(N)]
    cells += [(r, N - 1) for r in range(1, N)]
    cells += [(N - 1, c) for c in range(N - 2, -1, -1)]
    cells += [(r, 0) for r in range(N - 2, 0, -1)]
    return cells


def survey(world, offsets):
    # tx and rx both walk the same route, but rx starts a bit behind tx.
    # each offset gives a whole new set of links at different angles, which
    # is what actually makes the map recoverable. more offsets = better map.
    route = walk_route()
    L = len(route)

    att = world * WALL + (1 - world) * OPEN  # per-pixel attenuation
    A = []
    y = []
    for off in offsets:
        for t in range(0, L, 2):  # measure every 2nd step to keep it light
            tx = route[t % L]
            rx = route[(t + off) % L]
            if tx == rx:
                continue
            ray = bresenham(tx, rx)
            row = np.zeros(N * N)
            for (r, c) in ray:
                row[r * N + c] = 1
            # what we'd actually measure along this link
            loss = row @ att.ravel()
            A.append(row)
            y.append(loss + np.random.normal(0, NOISE))
    return np.array(A), np.array(y)


def solve_ls(A, y):
    # plain least squares. with ~470 measurements for 1600 unknowns it's
    # underdetermined, so this comes out noisy. you'll see.
    x, *_ = np.linalg.lstsq(A, y, rcond=None)
    return x


def laplacian():
    # L matrix: "each pixel should look like its neighbours". multiplying the
    # solution by it and punishing the result kills the speckle noise.
    # dense matrix is lazy but N is small so it doesn't matter.
    L = np.zeros((N * N, N * N))
    for r in range(N):
        for c in range(N):
            i = r * N + c
            deg = 0
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                if 0 <= rr < N and 0 <= cc < N:
                    L[i, rr * N + cc] = -1
                    deg += 1
            L[i, i] = deg
    return L


def solve_tikhonov(A, y, lam=0.1):
    # tikhonov = least squares + a penalty on noisy pixels.
    # trick: stack [A; sqrt(lam)*L] and throw it all at lstsq. this is
    # literally what the tutorial does - took me a sec to get why it works.
    L = laplacian()
    A2 = np.vstack([A, np.sqrt(lam) * L])
    y2 = np.concatenate([y, np.zeros(L.shape[0])])
    x, *_ = np.linalg.lstsq(A2, y2, rcond=None)
    return x


def solve_tv(A, y, lam=0.1, iters=6):
    # total variation - keeps edges sharp so walls come out cleanest.
    # i just do the reweighting loop from the tutorial. i still don't fully
    # get the math behind it, but the result is clearly better.
    rows = []
    for r in range(N):  # horizontal differences
        for c in range(N - 1):
            d = np.zeros(N * N)
            d[r * N + c] = -1
            d[r * N + c + 1] = 1
            rows.append(d)
    for r in range(N - 1):  # vertical differences
        for c in range(N):
            d = np.zeros(N * N)
            d[r * N + c] = -1
            d[(r + 1) * N + c] = 1
            rows.append(d)
    G = np.array(rows)

    x = solve_tikhonov(A, y, lam)
    for _ in range(iters):
        g = G @ x
        w = 1.0 / np.sqrt(g ** 2 + 1e-3 ** 2)  # downweight big jumps less
        A2 = np.vstack([A, np.sqrt(lam) * (G * np.sqrt(w)[:, None])])
        y2 = np.concatenate([y, np.zeros(G.shape[0])])
        x, *_ = np.linalg.lstsq(A2, y2, rcond=None)
    return x


def otsu(img):
    # global otsu threshold, same as the tutorial's layout tab. turns the
    # grayscale reconstruction into a binary "wall / no wall" map.
    hist, edges = np.histogram(img, bins=256)
    centers = (edges[:-1] + edges[1:]) / 2
    total = hist.sum()
    best_t, best = 0, -1
    for t in range(1, 256):
        w0 = hist[:t].sum()
        w1 = total - w0
        if w0 == 0 or w1 == 0:
            continue
        m0 = (hist[:t] * centers[:t]).sum() / w0
        m1 = (hist[t:] * centers[t:]).sum() / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > best:
            best, best_t = v, t
    return centers[best_t]


def check(x_hat, world):
    # how close did we get? rmse on the raw values + iou on the binarised map
    truth = world * WALL + (1 - world) * OPEN
    rmse = np.sqrt(np.mean((x_hat - truth.ravel()) ** 2))

    thr = otsu(x_hat)
    est = (x_hat > thr).reshape(N, N)
    tru = world.astype(bool)
    inter = (est & tru).sum()
    union = (est | tru).sum()
    return rmse, inter / union


def main():
    np.random.seed(0)
    world = make_world()
    route = walk_route()
    L = len(route)

    # rx offsets. i first tried just 3 offsets but the middle wall barely
    # showed up. 6 spread around the loop works well.
    offsets = [L // 8, L // 4, 3 * L // 8, L // 2, 5 * L // 8, 3 * L // 4]

    A, y = survey(world, offsets)
    print(f"grid {N}x{N} = {N*N} pixels, {A.shape[0]} measurements")

    x_ls = solve_ls(A, y)
    x_tk = solve_tikhonov(A, y)
    x_tv = solve_tv(A, y)

    print(f"{'method':15s} {'rmse':>8s} {'iou':>8s}")
    for name, x in [("least squares", x_ls), ("tikhonov", x_tk), ("tv", x_tv)]:
        rmse, iou = check(x, world)
        print(f"{name:15s} {rmse:8.3f} {iou:8.3f}")

    # truth | least squares | tikhonov | tv
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    axes[0].imshow(world, cmap="gray", vmin=0, vmax=1)
    axes[0].set_title("ground truth")
    for ax, name, x in zip(axes[1:],
                           ["least squares", "tikhonov", "tv"],
                           [x_ls, x_tk, x_tv]):
        ax.imshow(x.reshape(N, N), cmap="gray", vmin=OPEN, vmax=WALL)
        ax.set_title(name)
    for ax in axes:
        ax.axis("off")
    plt.tight_layout()
    plt.savefig("result.png", dpi=110)
    print("saved result.png")


if __name__ == "__main__":
    main()
