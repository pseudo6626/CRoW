![crow logo](https://github.com/pseudo6626/CRoW/blob/main/crow_logo1.PNG)

# CRoW
Colonization Route Workbench (CRoW) helps you identify routes to target systems from existing populated systems in a visual and customizable manner. 

**Dependencies**:  This is a python program and utilizes the following libraries: requests, heapq, json, os, platform, sys, threading, time, csv, tkinter, matplotlib.pyplot, mpl_toolkits.mplot3d, and webbrowser

**Methodology**:   The program uses two separate API endpoint queries from Ardent Laboratory's API: https://github.com/iaincollins/ardent-api?tab=readme-ov-file.  The first finds the 20 closest stations that offer refuel as a service within 500ly. These are the default target systems that CRoW will try to route towards. 

The second API endpoint finds all systems within 15 ly of a given system.  This is a rounded distance so the xyz coordinates are checked for any system with 15ly given as a distance. 

When you run CRoW, it will prompt for your goal system. It will then find the 20 closest stations and provide them to you in a popup with hyperlinks to inara for you to check and ensure they can be used for colonization. You may uncheck any system you don't want used as a target, and can input any custom system you want inlcuded as a target system.  

CRoW will then begin a 3d plot displaying the target systems in purple, the current route in blue, and any loaded or previously attempted systems in black. It will search for all systems within 15 ly of the current chain link (starting with the end goal) and then pick the one that is closest to one of the target systems. It will then repeat this until it gets to a dead end. It will then backtrack one system and try the next un-tested system within 15ly, etc. It will actively and continuously change target systems as needed from the list of possible target systems. Once a route is found, it will save the route as well as the distances between each system to a CSV file. 

Also full disclosure the writing of this code was strongly supported and supplemented by ChatGPT
