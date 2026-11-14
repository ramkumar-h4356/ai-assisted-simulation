# M12 Visualization Workflows

M12 consumes saved M9 execution results. It does not require a new scenario or another simulation run.

1. Generate and save a ready-to-execute M8 artifact.
2. Execute it with M9 (CLI option 9) or create M9 results through M10/M11.
3. Run `python main.py`, choose option 15, and select the M9 result.
4. Optionally supply an M10 analysis JSON and/or M11 uncertainty report JSON. Each report must refer to the exact selected M9 result and M8 artifact.
5. Open the generated `*_m12_dashboard.html` file with option 16 or directly in a browser.

M12 stores `*_m12_visualization.json` as a reusable, fingerprinted intermediate artifact and `*_m12_dashboard.html` as the offline interactive presentation.

The M10/M11 attachment paths are optional. A report from a different experiment, even if it uses the same conceptual revision, is rejected to prevent combining unrelated results.
