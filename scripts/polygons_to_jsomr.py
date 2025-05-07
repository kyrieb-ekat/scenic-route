import ast
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import os
from collections import defaultdict
import numpy as np

# Function to load polygons from a given file path
def load_polygon_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file at {file_path} does not exist.")

    with open(file_path, "r") as file:
        # Safely parse the list of polygons from the file
        polygon_data = ast.literal_eval(file.read())
    return polygon_data

# Function to perform basic vertical clustering of polygons
def group_polygons_vertically(polygons, vertical_tolerance=50):
    """Groups polygons into potential staves based on vertical proximity."""
    if not polygons:
        return []

    # Sort polygons by their top-most y-coordinate
    polygons_sorted_by_y = sorted(polygons, key=lambda poly: min(y for x, y in poly) if poly else float('inf'))

    grouped_staves = []
    current_staff_group = []

    for poly in polygons_sorted_by_y:
        if not poly: # Skip empty individual polygons
            continue

        poly_min_y = min(y for x, y in poly)
        poly_max_y = max(y for x, y in poly)
        # Avoid division by zero if min_y == max_y for a single point polygon
        poly_center_y = (poly_min_y + poly_max_y) / 2.0 if poly_min_y != poly_max_y else poly_min_y

        if not current_staff_group:
            current_staff_group.append(poly)
        else:
            # Calculate the average vertical center of the current group's points
            all_group_points = [point for p in current_staff_group for point in p if p]
            if all_group_points:
                group_center_y = np.mean([p_y for p_x, p_y in all_group_points])
            else:
                group_center_y = -float('inf') # If group is somehow empty, start a new one

            # If the current polygon is vertically close to the current group, add it
            # Use a slightly larger tolerance for checking against group center
            if abs(poly_center_y - group_center_y) < vertical_tolerance:
                current_staff_group.append(poly)
            else:
                # Otherwise, start a new group
                grouped_staves.append(current_staff_group)
                current_staff_group = [poly]

    # Add the last group
    if current_staff_group:
        grouped_staves.append(current_staff_group)

    return grouped_staves

# Define the file path - make sure this path is correct for your environment
file_path = "/Users/ekaterina/desktop/DDMAL/miyao_troubleshooting/polygons/polygons 3a - cho 107 - many detected.txt" # *** Update this to your new file path ***

try:
    # Step 1: Load the polygon data from the provided path
    polygon_data = load_polygon_data(file_path)
    print(f"Successfully loaded {len(polygon_data)} polygons")

    # Step 2: Group polygons into potential staves based on vertical proximity
    # You might need to adjust vertical_tolerance based on your manuscript
    vertical_tolerance = 100 # Example value, adjust based on your image scale
    grouped_staves = group_polygons_vertically(polygon_data, vertical_tolerance=vertical_tolerance)
    print(f"Grouped polygons into {len(grouped_staves)} potential staves with tolerance {vertical_tolerance}")


    # Step 3: Create a plot for visualization of grouped staves
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.set_aspect('equal')
    ax.set_title(f"Grouped Staff Polygons Visualization (Tolerance: {vertical_tolerance})")

    # Use a colormap that provides enough distinct colors for your number of groups
    colors = plt.cm.get_cmap('tab20', max(len(grouped_staves), 1))


    for i, staff_group in enumerate(grouped_staves):
        if not staff_group:
            continue

        color = colors(i % colors.N) # Use colors cyclically

        # Calculate bounding box for the group for visualization
        all_group_points_x = [x for poly in staff_group for x, y in poly if poly]
        all_group_points_y = [y for poly in staff_group for x, y in poly if poly]

        if all_group_points_x and all_group_points_y:
            group_min_x = min(all_group_points_x)
            group_min_y = min(all_group_points_y)
            group_max_x = max(all_group_points_x)
            group_max_y = max(all_group_points_y)

            # Draw bounding box for the group
            rect = plt.Rectangle((group_min_x, group_min_y), group_max_x - group_min_x, group_max_y - group_min_y,
                                 linewidth=1, edgecolor=color, facecolor='none')
            ax.add_patch(rect)

            # Label the group with its index
            group_center_x = np.mean(all_group_points_x)
            group_center_y = np.mean(all_group_points_y)
            ax.text(group_center_x, group_center_y, str(i), fontsize=12,
                    ha='center', va='center', color='black', bbox=dict(facecolor='white', alpha=0.7))

            # Optionally, draw the individual polygons within the group with a lighter shade
            for poly in staff_group:
                 if poly:
                    polygon_patch = Polygon(poly, closed=True,
                                            edgecolor=color,
                                            facecolor=color,
                                            alpha=0.2)
                    ax.add_patch(polygon_patch)
        else:
            print(f"Warning: Staff group {i} is empty or contains empty polygons after filtering.")


    # Step 4: Set axis limits and adjust view
    if polygon_data: # Adjust limits only if there's data
        all_x = [x for poly in polygon_data for x, y in poly if poly]
        all_y = [y for poly in polygon_data for x, y in poly if poly]
        if all_x and all_y:
            # Add some padding to the limits
            x_padding = (max(all_x) - min(all_x)) * 0.05
            y_padding = (max(all_y) - min(all_y)) * 0.05
            ax.set_xlim(min(all_x) - x_padding, max(all_x) + x_padding)
            ax.set_ylim(min(all_y) - y_padding, max(all_y) + y_padding)
        else:
             ax.autoscale_view() # Autoscale if no points after filtering


    ax.autoscale_view()
    plt.gca().invert_yaxis()  # Invert Y axis for image coordinates

    # Add grid for better readability
    ax.grid(True, linestyle='--', alpha=0.6)

    # Add axis labels
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')

    # Step 5: Save and show the plot
    plt.tight_layout()
    output_grouped_image = "visualized_grouped_staves.png"
    plt.savefig(output_grouped_image)
    print(f"Grouped staves visualization saved as '{output_grouped_image}'")
    # plt.show() # Uncomment to display the plot


    # Step 6: Convert grouped polygons to JSOMR format
    def convert_grouped_to_jsomr(grouped_polygons):
        jsomr_output = {
            "page": {
                "resolution": 0.0,
                "bounding_box": {
                    "ncols": 2681, # Ensure this matches your image dimensions
                    "nrows": 4037, # Ensure this matches your image dimensions
                    "ulx": 0,
                    "uly": 0
                }
            },
            "staves": [],
            "glyphs": [] # Glyphs section is kept for potential future use or if required by converter
        }

        num_points_per_line = 100 # You can experiment with this number

        for i, staff_group in enumerate(grouped_polygons):
            # --- Add checks for empty groups and invalid bounding boxes ---
            if not staff_group:
                print(f"Skipping empty staff group {i+1}")
                continue

            # Calculate bounding box for the entire staff group
            all_group_points = [point for poly in staff_group for point in poly if poly]
            if not all_group_points:
                 print(f"Skipping staff group {i+1} with no points after flattening")
                 continue # Should be caught by the above, but as a safeguard

            min_x = min(x for x, y in all_group_points)
            min_y = min(y for x, y in all_group_points)
            max_x = max(x for x, y in all_group_points)
            max_y = max(y for x, y in all_group_points)

            # Check for invalid bounding box dimensions
            if max_x <= min_x or max_y <= min_y:
                print(f"Skipping staff group {i+1} due to invalid bounding box dimensions: ulx={min_x}, uly={min_y}, lrx={max_x}, lry={max_y}")
                continue
            # ------------------------------------------------------------


            bounding_box = {
                "ulx": min_x,
                "uly": min_y,
                "ncols": max_x - min_x,
                "nrows": max_y - min_y
            }

            # --- Interpolation-based Line Position Generation ---
            line_positions = []
            total_staff_height = max_y - min_y

            if total_staff_height <= 0:
                 print(f"Warning: Staff group {i+1} has non-positive height ({total_staff_height}), cannot generate lines.")
                 continue # Skip if height is not positive

            # Calculate approximate y-coordinates for the 8 lines/spaces
            # These serve as anchors to identify relevant polygon points for each line
            approx_y_anchors = np.linspace(min_y, max_y, 8)

            # Prepare all points from the group for spatial lookup
            # Ensure points are filtered if the original polygon was empty
            all_group_points_filtered = [point for poly in staff_group for point in poly if poly]
            if not all_group_points_filtered:
                 print(f"Skipping staff group {i+1} with no points after filtering empty polygons for interpolation.")
                 continue


            all_x_points = np.array([x for x, y in all_group_points_filtered])
            all_y_points = np.array([y for x, y in all_group_points_filtered])


            num_points_per_line = 100 # You can experiment with this number
            # Ensure num_points_per_line > 1 for linspace
            x_intervals = np.linspace(min_x, max_x, num_points_per_line) if num_points_per_line > 1 else np.array([min_x])


            for j in range(8): # Generate points for each of the 8 lines (0-7)
                estimated_y = approx_y_anchors[j]

                # Define a vertical band around the estimated line y to find candidate polygon points for THIS line
                vertical_band_tolerance = total_staff_height / 8.0 * 1.5 # Look within 1.5 times an estimated space height vertically

                line_candidate_indices = np.where(
                    (all_y_points >= estimated_y - vertical_band_tolerance) &
                    (all_y_points <= estimated_y + vertical_band_tolerance)
                )[0]

                line_candidate_points = np.array([[all_x_points[idx], all_y_points[idx]] for idx in line_candidate_indices])

                line = []
                if len(line_candidate_points) >= 2: # Need at least 2 points for interpolation
                    # Sort candidate points by x-coordinate
                    sorted_candidate_points = line_candidate_points[np.argsort(line_candidate_points[:, 0])]

                    # Ensure unique x-coordinates for interpolation
                    xp_raw = sorted_candidate_points[:, 0]
                    yp_raw = sorted_candidate_points[:, 1]

                    # Use a small tolerance when checking for unique x-coordinates to handle floating point noise
                    # Find indices where the difference between consecutive x-coordinates is greater than a small tolerance
                    # This helps handle polygons that might have points with the same x-coordinate or very close x-coordinates
                    unique_indices_mask = np.diff(xp_raw, prepend=xp_raw[0] - 1) > 0.1 # Check for diff > a small tolerance
                    unique_xp = xp_raw[unique_indices_mask]
                    unique_yp = yp_raw[unique_indices_mask]


                    # Check if we have enough unique points for interpolation after handling duplicates
                    if len(unique_xp) >= 2:
                        # Perform linear interpolation over the horizontal intervals
                        try:
                            interpolated_y = np.interp(x_intervals, unique_xp, unique_yp)

                            for k in range(len(x_intervals)):
                                line.append([int(x_intervals[k]), int(interpolated_y[k])])
                        except Exception as e:
                            print(f"Error during interpolation for staff group {i+1}, Line {j+1}: {e}. Using equally spaced points as fallback.")
                            # Fallback on error during interpolation
                            y_pos = min_y + (j * total_staff_height / 7.0) if total_staff_height > 0 else min_y
                            for k in range(len(x_intervals)):
                                line.append([int(x_intervals[k]), int(y_pos)])

                    else:
                         # Fallback: if not enough unique points for interpolation, use equally spaced points
                         print(f"Warning: Staff group {i+1}, Line {j+1}: Not enough unique unique points ({len(unique_xp)}) for interpolation. Using equally spaced points as fallback.")
                         y_pos = min_y + (j * total_staff_height / 7.0) if total_staff_height > 0 else min_y
                         for k in range(len(x_intervals)):
                             line.append([int(x_intervals[k]), int(y_pos)])

                else:
                    # Fallback: if fewer than 2 candidate points, use equally spaced points
                    print(f"Warning: Staff group {i+1}, Line {j+1}: Fewer than 2 candidate points ({len(line_candidate_points)}). Using equally spaced points as fallback.")
                    y_pos = min_y + (j * total_staff_height / 7.0) if total_staff_height > 0 else min_y
                    for k in range(len(x_intervals)):
                        line.append([int(x_intervals[k]), int(y_pos)])

                line_positions.append(line)
            # -------------------------------------------


            # Create the staff entry
            staff = {
                "staff_no": i + 1,
                "bounding_box": bounding_box,
                "num_lines": 4, # Still specify 4 lines for the notation type
                "line_positions": line_positions
            }

            jsomr_output["staves"].append(staff)

            # Add a placeholder glyph for this staff
            # You will need to replace this with actual glyph detection and linking
            glyph = {
                "pitch": {
                    "staff": str(i + 1),
                    "offset": str(int(min_x + (max_x - min_x) * 0.1)), # Placeholder offset
                    "strt_pos": "1", # Placeholder
                    "note": "c",  # Placeholder
                    "octave": "4",  # Placeholder
                    "clef_pos": "None", # Placeholder
                    "clef": "None" # Placeholder
                },
                "glyph": {
                    "bounding_box": {
                        "ncols": 50,  # Placeholder size
                        "nrows": 50,
                        "ulx": int(min_x + (max_x - min_x) * 0.1), # Match offset ulx
                        # Place roughly in the middle vertically, handle zero height
                        "uly": int(min_y + (max_y - min_y) / 2 - 25) if max_y > min_y else min_y
                    },
                    "state": "AUTOMATIC", # Placeholder
                    "name": "note.black"  # Placeholder
                }
            }

            # Only add glyph if staff was not skipped
            jsomr_output["glyphs"].append(glyph)


        return jsomr_output

    # Step 7: Convert and save the grouped polygons as a .jsomr.json file
    jsomr_data = convert_grouped_to_jsomr(grouped_staves)
    output_file = "output_interpolated_lines.jsomr.json" # Changed output filename

    with open(output_file, "w") as json_file:
        json.dump(jsomr_data, json_file, indent=2)

    output_file_path = os.path.abspath(output_file)
    print(f"Grouped and interpolated lines JSOMR file saved to: '{output_file_path}'")
    print("Conversion completed successfully!")

except FileNotFoundError as e:
    print(f"Error: {e}")
except ValueError as e:
    print(f"Error parsing polygon data: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    import traceback
    traceback.print_exc()