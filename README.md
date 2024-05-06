# YOLO Microservices for Inference on the Cloud

Welcome to a containerized, cloud implementation of YOLO, performing object detection as a service.

## API Overview

### /register and /login
Both of these endpoints can be used to create and log into an account

### /track
This is the core functionality of this project, and allows streaming the webcam in real time for inference (depending on the availability of compute and the chosen model)
This also stores the amount of found objects, allowing you to see the history of how many times each object was found.

### /admin-service-page
This endpoint is specifically designed to view the endpoint metrics for an admin. It also contains all tracks for all users since the server session was started.

## Installation and Usage Instructions

Building:
```bash
cd cloud-final-yolo
docker build -t [username]/[container_name]
```

Running Locally:
```bash
docker run -p 8000:5000 [username]/[container_name]
```