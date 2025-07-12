import requests
import heapq
import json
import os
import platform
import sys
import threading
import time
import csv
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import Button

ARDENT_BASE = "https://api.ardent-insight.com/v2/system/name"
coords_cache = {}
nearby_cache = {}
refuel_cache = {}
current_path = []
latest_status = {"current": "", "target": "", "path_len": 0, "remaining": 0.0, "targets": [], "legend_extra": ""}
search_stop_event = threading.Event()

def distance_squared(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))

def get_coordinates(system_name):
    if system_name not in coords_cache:
        raise ValueError(f"No cached coordinates for {system_name}")
    return coords_cache[system_name]

def get_populated_targets(start_system):
    if start_system in refuel_cache:
        return refuel_cache[start_system]
    url = f"{ARDENT_BASE}/{start_system}/nearest/refuel"
    r = requests.get(url)
    r.raise_for_status()
    systems = [s['systemName'] for s in r.json() if 'systemName' in s]
    seen = set()
    unique_systems = []
    for s in systems:
        if s not in seen:
            seen.add(s)
            unique_systems.append(s)
    refuel_cache[start_system] = unique_systems
    return unique_systems

def get_nearby_systems(system_name):
    if system_name in nearby_cache:
        return nearby_cache[system_name]

    url = f"{ARDENT_BASE}/{system_name}/nearby?maxDistance=15.0000"
    r = requests.get(url)
    r.raise_for_status()
    raw_systems = r.json()

    if system_name not in coords_cache:
        origin = requests.get(f"{ARDENT_BASE}/{system_name}").json()
        if all(k in origin for k in ['systemX', 'systemY', 'systemZ']):
            coords_cache[system_name] = (origin['systemX'], origin['systemY'], origin['systemZ'])
        else:
            nearby_cache[system_name] = []
            return []

    origin_coords = coords_cache[system_name]
    verified = []
    for s in raw_systems:
        try:
            if all(k in s for k in ['systemName', 'systemX', 'systemY', 'systemZ']):
                coords = (s['systemX'], s['systemY'], s['systemZ'])
                dist = distance_squared(origin_coords, coords) ** 0.5
                if dist <= 15.0:
                    s['distance'] = dist
                    verified.append(s)
                    coords_cache[s['systemName']] = coords
        except Exception:
            continue

    nearby_cache[system_name] = verified
    return verified

def find_path(start, targets):
    visited = set()
    path = []

    for t in targets:
        if t not in coords_cache:
            try:
                data = requests.get(f"{ARDENT_BASE}/{t}").json()
                coords_cache[t] = (data['systemX'], data['systemY'], data['systemZ'])
            except Exception:
                continue

    target_coords = {t: coords_cache[t] for t in targets if t in coords_cache}
    heap = [(0, [start], start)]

    while heap:
        if search_stop_event.is_set():
            print("🛑 Search interrupted by user. Returning current partial path.")
            return path

        _, path, current = heapq.heappop(heap)
        if current in visited:
            continue
        visited.add(current)

        if current not in coords_cache:
            try:
                data = requests.get(f"{ARDENT_BASE}/{current}").json()
                coords_cache[current] = (data['systemX'], data['systemY'], data['systemZ'])
            except Exception:
                continue

        current_coords = coords_cache[current]
        closest_target, remaining_dist = min(
            ((t, distance_squared(current_coords, coords)) for t, coords in target_coords.items()),
            key=lambda x: x[1]
        )

        latest_status.update({
            "current": current,
            "target": closest_target,
            "path_len": len(path),
            "remaining": remaining_dist ** 0.5,
            "targets": targets
        })

        current_path.clear()
        current_path.extend([(p, coords_cache[p]) for p in path if p in coords_cache])

        if current in targets:
            return path

        neighbors = get_nearby_systems(current)
        for neighbor in neighbors:
            neighbor_name = neighbor['systemName']
            if neighbor_name in visited or neighbor_name not in coords_cache:
                continue
            h = min(distance_squared(coords_cache[neighbor_name], tc) for tc in target_coords.values())
            heapq.heappush(heap, (h, path + [neighbor_name], neighbor_name))

    return None

def live_plot_thread(targets_set):
    plt.ion()
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Add Stop and Save button
    button_ax = fig.add_axes([0.80, 0.01, 0.18, 0.05])
    stop_button = Button(button_ax, 'Stop and Save', color='red', hovercolor='salmon')
    stop_button.on_clicked(lambda event: search_stop_event.set())

    while True:
        ax.clear()
        all_names = [n for n, c in coords_cache.items() if c != (0.0, 0.0, 0.0)]
        vx = [coords_cache[n][0] for n in all_names]
        vy = [coords_cache[n][1] for n in all_names]
        vz = [coords_cache[n][2] for n in all_names]
        ax.scatter(vx, vy, vz, color='black', s=10, label="Visited")

        if current_path:
            px = [c[1][0] for c in current_path]
            py = [c[1][1] for c in current_path]
            pz = [c[1][2] for c in current_path]
            ax.plot(px, py, pz, marker='o', color='cyan', label="Current Path")

        target_coords = [(name, coords_cache[name]) for name in targets_set if name in coords_cache]
        if target_coords:
            tx = [c[1][0] for c in target_coords]
            ty = [c[1][1] for c in target_coords]
            tz = [c[1][2] for c in target_coords]
            ax.scatter(tx, ty, tz, color='purple', marker='^', s=40, label="Targets")

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_title("Live Route Search")
        ax.legend(title=(
            f"Current: {latest_status['current']}\n"
            f"Target: {latest_status['target']}\n"
            f"Path Length: {latest_status['path_len']}\n"
            f"Remaining Distance: {latest_status['remaining']:.2f} ly"
            + latest_status.get("legend_extra", "")
        ))
        plt.draw()
        plt.pause(0.2)

def print_route_with_distances(route):
    print("\n📡 Final route with distances between jumps:")
    total_distance = 0.0
    for i in range(len(route)):
        print(f"{i+1}. {route[i]}", end="")
        if i > 0:
            a = get_coordinates(route[i - 1])
            b = get_coordinates(route[i])
            dist = distance_squared(a, b) ** 0.5
            total_distance += dist
            print(f" — {dist:.4f} ly from previous")
        else:
            print(" (start)")
    print(f"\n🧮 Total distance: {total_distance:.4f} ly")

if __name__ == "__main__":
    start_system = input("Enter starting system name: ").strip()
    try:
        targets = get_populated_targets(start_system)

        # Tkinter popup to filter targets
        root = tk.Tk()
        root.title("Select Target Systems")
        tk.Label(root, text="Uncheck any systems you do NOT want to include:", font=("Helvetica", 12)).pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(padx=10, pady=10)
        check_vars = {}

        def open_link(system_name):
            import webbrowser
            url = f"https://inara.cz/elite/starsystems/?search={system_name.replace(' ', '+')}"
            webbrowser.open_new_tab(url)

        start_coords = requests.get(f"{ARDENT_BASE}/{start_system}").json()
        coords_cache[start_system] = (start_coords['systemX'], start_coords['systemY'], start_coords['systemZ'])

        targets_with_dist = []
        for t in targets:
            try:
                coords = requests.get(f"{ARDENT_BASE}/{t}").json()
                coords_cache[t] = (coords['systemX'], coords['systemY'], coords['systemZ'])
                dist = distance_squared(coords_cache[start_system], coords_cache[t]) ** 0.5
                targets_with_dist.append((t, dist))
            except Exception:
                continue

        targets_with_dist.sort(key=lambda x: x[1])

        def add_system_to_popup(system_name):
            try:
                if system_name in check_vars:
                    return  # prevent duplicate
                coords = requests.get(f"{ARDENT_BASE}/{system_name}").json()
                coords_cache[system_name] = (coords['systemX'], coords['systemY'], coords['systemZ'])
                dist = distance_squared(coords_cache[start_system], coords_cache[system_name]) ** 0.5

                row = tk.Frame(frame)
                row.pack(anchor="w", fill="x")
                var = tk.BooleanVar(value=True)
                check_vars[system_name] = var
                cb = tk.Checkbutton(row, variable=var)
                cb.pack(side="left")
                label = tk.Label(row, text=f"{system_name} ({dist:.2f} ly)", fg="blue", cursor="hand2", font=("Helvetica", 11))
                label.pack(side="left")
                label.bind("<Button-1>", lambda e, name=system_name: open_link(name))
            except Exception as e:
                messagebox.showerror("Error", f"Could not resolve system: {system_name}\n\n{e}")

        # Populate initial target checkboxes
        for t, dist in targets_with_dist:
            add_system_to_popup(t)

        # Add custom input field
        entry_frame = tk.Frame(root)
        entry_frame.pack(pady=(10, 0))
        tk.Label(entry_frame, text="Add custom system name:", font=("Helvetica", 11)).pack(side="left", padx=(0, 10))
        custom_entry = tk.Entry(entry_frame, font=("Helvetica", 11), width=30)
        custom_entry.pack(side="left")

        def on_add():
            name = custom_entry.get().strip()
            if name:
                add_system_to_popup(name)
                custom_entry.delete(0, tk.END)

        tk.Button(root, text="Add", command=on_add, font=("Helvetica", 11)).pack(pady=5)

        ttk.Button(root, text="Start Search", command=lambda: (root.quit(), root.destroy())).pack(pady=10)
        root.mainloop()

        targets = [t for t, var in check_vars.items() if var.get()]
        if not targets:
            print("❌ No targets selected. Exiting.")
            sys.exit(0)

        threading.Thread(target=live_plot_thread, args=(set(targets),), daemon=True).start()
        route = find_path(start_system, targets)

        if route:
            print_route_with_distances(route)
            with open("route_output.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Step", "System", "X", "Y", "Z", "Distance from Previous"])
                total = 0.0
                for i in range(len(route)):
                    coords = get_coordinates(route[i])
                    if i == 0:
                        writer.writerow([1, route[i], *coords, 0])
                    else:
                        prev = get_coordinates(route[i-1])
                        dist = distance_squared(coords, prev) ** 0.5
                        total += dist
                        writer.writerow([i+1, route[i], *coords, dist])
                latest_status["legend_extra"] = f"\nRoute Saved: route_output.csv\nTotal Distance: {total:.2f} ly"
            print("\n✅ Route (partial or full) saved. Plot will remain open. Close the plot window or press Ctrl+C to exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Exiting.")
        else:
            print("❌ No route found or saved.")

    except Exception as e:
        print(f"⚠️ Error: {e}")
