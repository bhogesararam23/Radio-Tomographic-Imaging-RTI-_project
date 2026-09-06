# rti-sim — my attempt at reproducing UbiqMap

Hi, I'm Ram bhogesara. This is a small project where I tried to reproduce the core idea from **UbiqMap: Ubiquitous Indoor Mapping using Mobile Radio Tomography** (Basu, Chakraborty & Jajal, IEEE TMC 2024), from the SeNSE group at IIT Madras.

## why I made this

I was going through Prof. Ayon Chakraborty's work on wireless sensing and UbiqMap stuck with me — the idea that you can map the inside of a building using **just radio signals, with no cameras**, sounded unreal. I learn best by actually building a thing, so instead of only reading the paper I wrote a simulation of the whole pipeline. Then I ported it to the browser so I could *see* it and share it easily.

## the idea, in my own words

A wall blocks a radio signal more than empty air. So if you measure how much signal is lost along a straight line from point A to point B, that single number tells you something about what's in between. Do that from enough different angles and you can solve backwards and recover where the walls are — like a CT scan, but with radio.

The whole thing is just one linear system:

    y = A * x + noise

- `x` — the map (one attenuation value per grid pixel). this is what we want
- `A` — which pixels each measurement's line crosses (Bresenham lines)
- `y` — the measured loss on each line

then you reconstruct `x` with regularised least squares. that's basically it. no ML, no physics engine.

## what's in here

- **`rti_sim.py`** — the whole pipeline in numpy (terminal + `result.png`)
- **`index.html`** — the same thing as an interactive web demo. you draw the
  building, watch the mobile radio sweep it, and compare three solvers live.
  it's a single self-contained file, no dependencies, works offline.
- **`result.png`** — output of the python version

## run the python version

```bash
pip install numpy matplotlib
python rti_sim.py
```

prints the metrics and saves `result.png`:

| method | rmse | layout IoU |
| --- | --- | --- |
| least squares | 0.438 | 0.65 |
| tikhonov | 0.365 | 0.85 |
| tv (irls) | 0.233 | **0.90** |

same measurements, better solver → 65% to 90% layout accuracy. that matches the paper's point: reconstruction quality matters as much as the data you collect.

## run the web demo

just open `index.html` in a browser. or serve it:

```bash
python -m http.server 8000
# then open http://localhost:8000
```

### putting it on github pages (free)

1. create a public repo (e.g. `rti-sim` or `ubiqmap-demo`)
2. upload `index.html` (and the rest if you want)
3. Settings → Pages → deploy from `main`, root folder
4. the demo is live at `https://bhogesararam23.github.io/Radio-Tomographic-Imaging-RTI-_project/`

## what I learned

- how radio tomographic imaging works (line integrals + an inverse problem)
- why plain least squares struggles on underdetermined systems, and what regularisation actually does to fix it
- Bresenham line drawing (I spent way too long on this)
- Otsu thresholding to turn a grayscale reconstruction into a layout
- writing a conjugate gradient solver by hand so the browser demo has zero dependencies

## honest limits

this is a **simulation of the math**, not a re-implementation of the hardware. the real UbiqMap uses actual RF radios, a moving robot/wearable, and fuses RTI with SLAM. I only reproduced the tomographic core. the hardware side is exactly what I want to learn next.

## things I want to try next

- [ ] a moving "person" obstacle to show real-time change detection
- [ ] map quality vs number of measurements curve
- [ ] compare side-by-side with the group's own rti-tutorial GUI
- [ ] get my hands on real radios instead of simulated ones

## references

- paper: https://ieeexplore.ieee.org/abstract/document/10634790
- project page: https://amartya-pixel.github.io/projects/ubiqmap/
- the group's tutorial (my model is based on this): https://github.com/ayoniitm/rti_tutorial
- SeNSE group: https://cse.iitm.ac.in/~sense/
