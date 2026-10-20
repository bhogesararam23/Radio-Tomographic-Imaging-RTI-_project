# RTI Experiment Report

## 1. What I wanted to test

I wanted to understand how much of an indoor floor plan can be recovered from radio-path attenuation measurements, and how much the reconstruction method matters when the measurements are limited.

The experiment is inspired by *Ubiquitous Indoor Mapping using Mobile Radio Tomography* (UbiqMap, Basu, Chakraborty and Jajal, IEEE TMC 2024). I focused on the tomographic reconstruction part rather than trying to reproduce the full hardware system.

The main question was:

> With the same simulated radio measurements, does adding spatial regularisation improve the reconstructed layout compared with plain least squares?

This is a simulation of the mathematics. It does not use real radio hardware or real RF measurements.

## 2. Experimental setup

The Python experiment is implemented in `rti_sim.py`.

| Parameter | Setting |
| --- | --- |
| Grid | 40 × 40 cells |
| Unknown attenuation values | 1,600 |
| Empty-space attenuation | 0.10 |
| Wall / furniture attenuation | 2.0 |
| Measurement noise standard deviation | 0.02 |
| Random seed | 0 |
| Route | Perimeter of the grid |
| Survey offsets | 6 |
| Measurements | 468 |
| Reconstruction methods | Least squares, Tikhonov, TV (IRLS) |

The 156-cell perimeter route is sampled every second step, giving 78 transmitter–receiver links for each of the six offsets. That gives 468 simulated measurements for 1,600 unknown cell values, so the inverse problem is underdetermined.

### Ground-truth layout

The simulation creates a known floor plan for evaluation:

- Boundary walls around the grid.
- A wall across the middle, with a gap representing a doorway.
- A second wall on the right side.
- Three rectangular blocks representing furniture.

Each cell is assigned an attenuation value. Empty cells use 0.10 and wall/furniture cells use 2.0. The survey routine uses the known layout to generate measurements, but the reconstruction algorithms receive the measurements rather than the ground-truth layout.

## 3. How the measurements are generated

The experiment uses the linear model

```text
y = A x + noise
```

where:

- `x` is the unknown attenuation map, flattened into one value per cell.
- `A` represents which grid cells each radio path crosses.
- `y` contains the simulated attenuation measurement for each link.
- `noise` is Gaussian measurement noise.

The transmitter and receiver move along the perimeter route. For each link, the code uses Bresenham's line algorithm to identify the grid cells crossed by the straight path. Their attenuation values are summed, then noise is added to create the observation.

The same resulting measurement set is used to compare all three reconstruction methods. This keeps the comparison focused on the solver rather than giving one method different input data.

## 4. Reconstruction methods

### A. Least squares

The baseline estimates the map by minimizing the squared difference between the predicted and measured attenuation:

```text
minimize ||A x - y||²
```

It is a useful starting point, but there are more unknown pixels than measurements. By itself, the objective does not provide enough information to uniquely determine the full map.

### B. Tikhonov regularisation

The second method adds a discrete Laplacian penalty:

```text
minimize ||A x - y||² + λ ||L x||²
```

Here, `L` is the grid Laplacian and `λ` controls the strength of the regularisation. The penalty discourages noisy, rapidly varying reconstructions and encourages neighboring cells to be spatially consistent.

### C. Total variation using IRLS

The third method uses an iteratively reweighted least-squares (IRLS) approach to approximate total-variation regularisation. Instead of simply smoothing the whole map, it penalises neighboring-cell differences in a way that can preserve sharper transitions.

That is useful for this task because walls are expected to form relatively sharp boundaries between open areas and obstructed cells.

## 5. Evaluation

I use two metrics in the Python experiment.

**Root mean squared error (RMSE)** compares the reconstructed attenuation values with the known attenuation map:

```text
RMSE = sqrt(mean((x_estimated - x_true)²))
```

Lower RMSE means the estimated attenuation values are closer to the synthetic ground truth.

**Intersection over union (IoU)** evaluates the binary wall layout. Otsu thresholding converts each reconstruction into a wall / non-wall mask, which is compared with the ground-truth wall mask:

```text
IoU = intersection / union
```

Higher IoU means greater overlap between the estimated and ground-truth wall regions. IoU is a layout-overlap metric; it should not be interpreted as a universal measure of real-world mapping accuracy.

## 6. Results

The following are the Python results currently recorded in the project's README.

| Method | RMSE | Layout IoU |
| --- | ---: | ---: |
| Least squares | 0.438 | 0.65 |
| Tikhonov | 0.365 | 0.85 |
| TV (IRLS) | 0.233 | 0.90 |

### What the results suggest

- **Least squares** gives the weakest result of the three on this synthetic layout.
- **Tikhonov regularisation** reduces RMSE from 0.438 to 0.365 and improves IoU from 0.65 to 0.85.
- **TV (IRLS)** gives the lowest reported RMSE and highest reported IoU in this comparison: 0.233 and 0.90.

The recorded IoU rises from 0.65 for least squares to 0.90 for TV (IRLS). Since all three methods use the same measurements, this comparison illustrates how the choice of regularisation can substantially affect a reconstructed map when the available data are insufficient to recover every cell directly.

These numbers describe this particular synthetic experiment. They do not demonstrate the same performance on a physical building or on real radio measurements.

## 7. Reproducing the experiment

Install the Python dependencies and run the script from the repository root:

```bash
pip install numpy matplotlib
python rti_sim.py
```

The script sets the NumPy random seed to 0, prints the measurement count and metrics, and saves the reconstruction comparison as `result.png`.

The figure compares the ground truth with the least-squares, Tikhonov and TV reconstructions.

The browser version in `index.html` is a separate, interactive implementation. It lets me draw or select a layout, adjust the grid size, survey rounds, noise and regularisation strength, and compare the three reconstruction views. Its solver implementation and default grid differ from the Python version, so the Python metrics above should not be assumed to apply to every browser configuration.

## 8. Limitations

There are several important limits to this experiment:

1. **Synthetic measurements only.** Attenuation is generated directly from the occupancy grid. The model does not simulate the full complexity of radio propagation, multipath, antenna behavior, calibration errors or uncertain sensor positions.
2. **Simplified ray model.** Each link is represented by the cells selected by Bresenham's line algorithm. This is a convenient grid approximation, not a complete physical propagation model.
3. **Underdetermined reconstruction.** There are 1,600 unknown cells but 468 measurements. The output therefore depends strongly on the assumptions introduced by the solver and its regularisation.
4. **Known ground truth.** The generated layout is available for evaluation. A real deployment would not have that ground truth available while reconstructing the building.
5. **Not a full UbiqMap reproduction.** This repository focuses on the RTI mathematical core. It does not implement a physical mobile-radio setup or fuse radio tomography with SLAM.

The values in the results table are carried over from the current README and have not been independently re-run as part of preparing this report. Running `rti_sim.py` will regenerate the figure and print metrics for the installed environment.

## 9. Conclusion and next experiments

For this synthetic setup, the regularised methods outperform the plain least-squares baseline, and TV (IRLS) gives the strongest result among the three reported methods. The experiment made the inverse-problem trade-off clearer to me: collecting radio links matters, but how the measurements are reconstructed matters as well.

The next useful experiments would be to measure layout quality as the number and geometry of links change, test multiple noise levels and random seeds, and compare the simulation more systematically with the reference tutorial. After that, the main research challenge is moving beyond the simplified model and understanding what changes when the measurements come from actual radio hardware.

## References

- Basu, Chakraborty and Jajal, *Ubiquitous Indoor Mapping using Mobile Radio Tomography*, IEEE Transactions on Mobile Computing, 2024: https://ieeexplore.ieee.org/abstract/document/10634790
- UbiqMap project page: https://amartya-pixel.github.io/projects/ubiqmap/
- SeNSE group's RTI tutorial: https://github.com/ayoniitm/rti_tutorial
- SeNSE group, IIT Madras: https://cse.iitm.ac.in/~sense/
